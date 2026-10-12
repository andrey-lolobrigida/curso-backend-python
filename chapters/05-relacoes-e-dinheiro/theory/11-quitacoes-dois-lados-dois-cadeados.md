# Lição 11 — Quitações: dois lados, dois cadeados

O FairFare já sabe quem deve para quem. Falta o último passo: alguém pagar.

Esta lição traz o `POST /groups/{id}/settlements`, a **quitação**. "O Bruno pagou 30 reais à Ana." E com ela volta um velho conhecido do capítulo 4: duas requests ao mesmo tempo, uma regra checada antes de gravar, e o banco aceitando as duas. Desta vez, com dinheiro.

## A regra dos dois lados

Uma quitação diz: X paga V a Y, dentro do grupo. No saldo, o pagador sobe V e o recebedor desce V. A tabela nova, `settlements`, guarda exatamente isso: `de_user_id`, `para_user_id`, `valor`. Ela chega por uma migração nova, `quitacoes` (autogenerate, com os dois `CHECK` nomeados já escritos). Antes de qualquer coisa desta lição, inclusive a bancada, aplique no banco de dev:

```console
$ uv run alembic upgrade head
```

Sem ela, a primeira quitação morre com `relation "settlements" does not exist`. E o saldo da lição 10 ganha as duas fontes que ela prometeu. Em `app/repositories/group.py`, o `WITH` cresce assim:

```diff
           JOIN expenses e ON e.id = p.expense_id
          WHERE e.group_id = :grupo
+        UNION ALL
+        SELECT de_user_id, valor FROM settlements WHERE group_id = :grupo
+        UNION ALL
+        SELECT para_user_id, -valor FROM settlements WHERE group_id = :grupo
     )
```

Duas linhas de SQL a mais, como a lição 10 disse que seriam. E com `:grupo`, nunca f-string.

Agora, quando uma quitação vale? A regra do FairFare olha **os dois lados**:

> "X paga V a Y" só vale se saldo(X) ≤ −V **e** saldo(Y) ≥ +V. Senão, `409`.

Quem paga precisa dever pelo menos V. Quem recebe precisa ter pelo menos V a receber.

O cenário dos testes: a Ana pagou R$ 100 de chalé entre os três. Pela regra do centavo, Ana +66,66, Bruno −33,33, Carla −33,33.

- Bruno paga 33,33 à Ana: vale. Bruno vai a zero, Ana a +33,33.
- Bruno paga 40 à Ana: `409`. Ele só deve 33,33.
- Carla paga 10 ao Bruno: `409`. A Carla deve, mas o Bruno não tem nada a receber. Sem o segundo lado, a Carla "quitaria" com o Bruno, que passaria a dever ainda mais. É o caso que só a regra dos dois lados pega.

Quitar para si mesmo é `422`, barrado no schema (`ninguém quita uma dívida consigo mesmo`) e, por garantia, num `CHECK` no banco. Quitar com quem não é membro também é `422`.

## A corrida

O service, numa primeira versão, faz o óbvio. Dentro do `begin()` da lição 08: confere que o grupo existe, confere que os dois são membros, lê os saldos, aplica a regra, grava.

Agora o Bruno, nervoso, clica oito vezes em "pagar 30 à Ana". O teste faz isso com `asyncio.gather`:

```python
async def test_quitacoes_simultaneas_nao_pagam_a_mesma_divida_duas_vezes(client):
    g = await ana_bruno_carla(client)
    respostas = await asyncio.gather(
        *(quita(client, g, de=2, para=1, valor="30.00") for _ in range(8))
    )
    assert sorted(r.status_code for r in respostas) == [201] + [409] * 7
    assert await saldos(client, g) == ["36.66", "-3.33", "-33.33"]
```

Uma passa (30 cabe em 33,33). A segunda já não cabe: sobraria 3,33 de dívida, e 30 é mais que isso. Sete `409`.

Na versão sem cadeado, isso falhou **dez de dez vezes**:

```console
E       assert [201, 201, 20...201, 201, ...] == [201, 409, 40...409, 409, ...]
E         
E         At index 1 diff: 201 != 409
```

Não foi uma a mais. Foram as oito. No banco de testes, depois da rodada:

```console
 quitacoes | total  
-----------+--------
         8 | 240.00
```

O Bruno devia 33,33 e pagou 240. Ficou com saldo de +206,67: agora o grupo deve a ele. Dinheiro criado do nada.

A `bancada/quitacao.py` repete isso pelo uvicorn de verdade, como o `corrida.py` do capítulo 4. Cada rodada monta um grupo novo e dispara cinco quitações de 30:

```console
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/quitacao.py --n 5 --rodadas 10
rodada  1: 201×1  409×4  saldo do Bruno: -3.33
rodada  2: 201×5  saldo do Bruno: 116.67
rodada  3: 201×5  saldo do Bruno: 116.67
(...)
rodada 10: 201×5  saldo do Bruno: 116.67

rodadas em que o Bruno pagou além da dívida: 9/10
```

(As rodadas 3 a 10 saíram iguais à 2. A primeira escapou, logo depois de o app subir. Corrida é isso: depende de quem chega quando. Nove de dez basta.)

Essa versão sem cadeado **não está no repositório**. Ela existiu na minha máquina para gerar essas saídas.

Você já viu esse filme. É a lição 07 do capítulo 4: *check-then-act*. Cada request lê os saldos, vê "o Bruno deve 33,33", aprova e grava. Todas leem antes de qualquer uma gravar. A transação não ajuda, pelo mesmo motivo da lição 08 de lá: transação não é cadeado.

## O que trancar

No capítulo 4, a resposta foi `SELECT ... FOR UPDATE` na linha do recurso: a prancheta da quadra. Quem quer reservar pega a prancheta, e quem chega depois espera.

Aqui, qual é a prancheta? O instinto diz: a linha do saldo. Só que não existe linha de saldo. A lição 09 decidiu que o saldo é **calculado**, nunca guardado. Não dá para trancar uma soma.

Então tranque o que representa cada lado. Toda pessoa num grupo tem exatamente uma linha em `group_members`. Ela não guarda o saldo, mas é a identidade "Bruno, neste grupo". Se toda quitação tranca a linha de quem paga e a de quem recebe antes de ler os saldos, duas quitações que envolvem a mesma pessoa fazem fila.

Repare que a linha não muda. Ninguém dá `UPDATE` nela. Ela é só o ponto de encontro combinado, como a quadra era no capítulo 4. O cadeado é um combinado: funciona porque todo caminho que decide com base no saldo passa por ele.

E é aqui que a lição 04 se paga. Lá, `GroupMember` virou classe, e não uma `Table` solta com `secondary=`. A docstring já avisava:

```python
class GroupMember(Base):
    """Quem é de qual grupo. Uma classe, e não uma Table solta: a lição 11 tranca linhas dela."""
```

Com classe, é um `select(GroupMember)` comum, com `.with_for_update()` no fim.

## Dois cadeados, ordem errada

Primeira tentativa, que também não está no repositório: dois `SELECT ... FOR UPDATE`, um por membro, na ordem do pedido. Primeiro quem paga, depois quem recebe.

O teste das direções opostas manda cinco quitações Bruno→Ana e cinco Ana→Bruno ao mesmo tempo. Bruno→Ana tranca Bruno, depois Ana. Ana→Bruno tranca Ana, depois Bruno. Dez de dez rodadas do teste falharam, cada uma levando 1,7 s:

```console
E   sqlalchemy.exc.DBAPIError: (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'asyncpg.exceptions.DeadlockDetectedError'>: deadlock detected
E   DETAIL:  Process 43784 waits for AccessExclusiveLock on tuple (0,2) of relation 168111 of database 16449; blocked by process 43786.
E   Process 43786 waits for ShareLock on transaction 79940; blocked by process 43785.
E   Process 43785 waits for AccessExclusiveLock on tuple (0,1) of relation 168111 of database 16449; blocked by process 43787.
E   Process 43787 waits for ShareLock on transaction 79939; blocked by process 43792.
E   Process 43792 waits for AccessExclusiveLock on tuple (0,2) of relation 168111 of database 16449; blocked by process 43784.
```

É o deadlock do bloco 3 dos exercícios do capítulo 4, com dinheiro no lugar das quadras. A diferença é o tamanho: com dez requests, o ciclo passou por cinco processos, e não dois. Os `tuple (0,1)` e `(0,2)` são as linhas da Ana e do Bruno em `group_members`; quem espera por uma linha entra na fila dela, e a fila também conta no ciclo. Apesar do nome, o `AccessExclusiveLock on tuple` não tranca a tabela. É o cadeado que o Postgres usa para organizar essa fila de espera de **uma linha** (o *tuple lock*); o modo `AccessExclusive` é só o que corresponde a um `FOR UPDATE`. O Postgres esperou o `deadlock_timeout` de 1 s, achou o ciclo e matou uma das transações. A regra para desfazer o nó está no SOLUTIONS daquele capítulo: **"Se você precisa de mais de um cadeado ao mesmo tempo, combine uma ordem e respeite-a sempre."**

## O cadeado certo

Em `app/repositories/group.py`:

```python
    async def lock_members(self, group_id: int, user_ids: list[int]) -> list[GroupMember]:
        # Tranca as linhas de quem paga e de quem recebe até o fim da transação.
        # SEMPRE em ordem de user_id: quem tranca na mesma ordem nunca forma um ciclo,
        # e sem ciclo não há deadlock (lição 11; capítulo 4, SOLUTIONS do bloco 3).
        stmt = (
            select(GroupMember)
            .where(GroupMember.group_id == group_id, GroupMember.user_id.in_(user_ids))
            .order_by(GroupMember.user_id)
            .with_for_update()
        )
        return list(await self.db.scalars(stmt))
```

Um `SELECT` só, para as duas linhas, com `ORDER BY user_id`. Bruno→Ana e Ana→Bruno trancam os dois na mesma ordem: Ana (1), depois Bruno (2). Quem chega depois espera na linha da Ana, sem segurar nada. Fila, e não nó.

Mas um `ORDER BY` garante a ordem do **resultado**. Garante a ordem dos **cadeados**? Depende de onde o Postgres tranca. O `EXPLAIN` responde. Colei a consulta no `psql`, com os ids do meu banco de dev:

```console
fairfare=# EXPLAIN SELECT group_id, user_id FROM group_members
           WHERE group_id = 1 AND user_id IN (2, 3) ORDER BY user_id FOR UPDATE;
                                   QUERY PLAN                                    
---------------------------------------------------------------------------------
 LockRows  (cost=1.05..1.08 rows=2 width=14)
   ->  Sort  (cost=1.05..1.06 rows=2 width=14)
         Sort Key: user_id
         ->  Seq Scan on group_members  (cost=0.00..1.04 rows=2 width=14)
               Filter: ((user_id = ANY ('{2,3}'::integer[])) AND (group_id = 1))
```

O `LockRows` é o nó que tranca, e ele fica **acima** do `Sort`. As linhas chegam a ele já ordenadas, e ele tranca uma por uma, na ordem em que chegam. Se o `LockRows` ficasse abaixo do `Sort`, trancaria na ordem da tabela, e o `ORDER BY` só arrumaria a saída.

No service, os cadeados entram **antes** de ler os saldos, e substituem a conferência de membros (se uma das linhas não existe, voltam menos de duas):

```python
            # Os dois cadeados ANTES de ler os saldos: quem chegar depois espera aqui,
            # e lê os saldos já com a quitação de quem chegou antes (READ COMMITTED:
            # cada comando vê o que já foi comitado, como na lição 10 do capítulo 4).
            trancados = await self.groups.lock_members(
                group_id, [data.de_user_id, data.para_user_id]
            )
            if len(trancados) != 2:
                raise NotAMemberError
            saldo = {b.user_id: b.saldo for b in await self.groups.balances(group_id)}
```

## Por que funciona em `READ COMMITTED`

A segunda quitação do Bruno espera no `lock_members`. A primeira lê os saldos, grava, comita e solta. A segunda acorda e roda o `balances`.

Que saldo ela vê? A lição 10 do capítulo 4 respondeu, para reservas: em `READ COMMITTED`, cada **comando** tira um retrato novo do banco. O `balances` é um comando novo, que começa depois do `COMMIT` da primeira. O retrato já tem a quitação de 30. O Bruno deve 3,33, a regra diz `409`.

É por isso que a ordem no service importa tanto quanto a ordem dos cadeados. Se os saldos fossem lidos antes do `lock_members`, a espera não adiantaria: a segunda decidiria com um número velho. Fila para olhar, e não fila para anotar.

## A prova

A suíte inteira, e depois os testes das quitações vinte vezes:

```console
$ uv run pytest -q -W error
77 passed in 3.75s
$ for i in $(seq 1 20); do uv run pytest -q tests/test_quitacoes.py | tail -1; done | sed 's/ in .*//' | sort | uniq -c
     20 7 passed
```

Vinte de vinte, incluindo as direções opostas: nenhum deadlock. E a bancada, pelo uvicorn, com cinco e com dez cliques simultâneos:

```console
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/quitacao.py --n 5 --rodadas 10
rodada  1: 201×1  409×4  saldo do Bruno: -3.33
(...)
rodada 10: 201×1  409×4  saldo do Bruno: -3.33

rodadas em que o Bruno pagou além da dívida: 0/10
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/quitacao.py --n 10 --rodadas 10
rodada  1: 201×1  409×9  saldo do Bruno: -3.33
(...)
rodada 10: 201×1  409×9  saldo do Bruno: -3.33

rodadas em que o Bruno pagou além da dívida: 0/10
```

Todas as vinte rodadas, idênticas. O resultado deixou de depender de quem chega primeiro. É determinístico.

## E a despesa, não tranca?

Uma pergunta justa: a despesa também mexe nos saldos. Ela não deveria passar pelo mesmo cadeado?

Não, e o motivo é o critério mais útil desta lição. A quitação **decide** com base nos saldos: ela lê, compara com V e só então grava. Duas quitações decidem uma sobre a outra, e é aí que mora a corrida. A despesa não decide nada com base nos saldos. Ela só confere quem é membro, e grava.

Imagine uma despesa comitando no meio de uma quitação. A quitação leu os saldos de antes da despesa, num comando só, e decidiu. O estado final é exatamente o de "primeiro a quitação, depois a despesa", em série. E essa ordem é legal: a despesa não tem regra para violar. É a ideia da lição 09 do capítulo 4: se o resultado é o de alguma ordem em série válida, não há anomalia. Trancar a despesa só acrescentaria espera.

Nem toda escrita concorrente é corrida. A pergunta é: **alguém decide com base no que o outro escreve?** Se sim, cadeado. Se não, deixe passar.

## O que fica declarado

- **A regra obriga a pagar em parcelas.** Se a Carla deve 20, e a Ana e o Bruno têm 10 cada a receber, a Carla não paga 20 à Ana: a Ana só tem 10 a receber. São duas quitações, 10 para cada. Achar o menor conjunto de pagamentos que zera o grupo é a *simplificação de dívidas*, um problema de algoritmo, não de backend. Fica fora do curso.
- **O cadeado é um combinado.** Ele só protege porque toda quitação passa pelo `lock_members`. Um script que grave em `settlements` direto, sem trancar, reabre a corrida. A regra de saldo mora no service, não no banco.

## O que você deve conseguir fazer agora

- Dizer o que trancar quando o dado protegido é calculado: uma linha que represente cada parte envolvida, trancada antes da leitura.
- Explicar por que a ordem resolve o deadlock: com todo mundo trancando na mesma ordem, quem espera não segura nada, e o ciclo não se forma.
- Ler um `EXPLAIN` e dizer se o `LockRows` tranca na ordem do `ORDER BY`.
- Prever o resultado de oito quitações iguais de 30 sobre uma dívida de 33,33: um `201`, sete `409`, e a dívida em 3,33.
