# Lição 10 — Trancando a porta certa

A lição 08 terminou com uma frase: **transação não é cadeado**. A 09 tentou deixar a transação mais desconfiada e pagou caro por isso: abortos, retry obrigatório, e gente que nem disputava a mesma quadra perdendo a vez.

Esta lição faz o óbvio. Pega um cadeado de verdade e tranca **exatamente** o que está em disputa. Nem mais, nem menos.

A pergunta difícil não é *como* trancar. É *o quê*.

## O que está em disputa?

O primeiro reflexo é trancar a reserva. Afinal, é ela que sai duplicada.

Só que a reserva ainda não existe. Quando a request A faz a verificação, não há linha nenhuma para trancar: a reserva dela só nasce no `INSERT`, lá no fim. E a de B também. Não dá para pôr cadeado numa porta que ainda não foi construída.

Volte para a agenda de papel do clube. O que Ana e Bruno disputam não é a anotação de cada um. É a **agenda da quadra 3**. Quem precisa de exclusividade é ela.

Então imagine que o clube muda a regra. A agenda de cada quadra fica numa **prancheta**, e só existe uma prancheta por quadra. Quem quer reservar pega a prancheta, olha, anota e devolve. Quem chega enquanto ela está na mão de alguém espera no balcão. Quando a prancheta volta, a próxima pessoa olha, e agora vê a anotação de quem veio antes.

Repare em duas coisas. A espera é só para quem quer a **mesma** prancheta: a quadra 5 tem a dela, e ninguém da quadra 5 espera por ninguém da quadra 3. E quem pega a prancheta **olha e anota sem soltar**. É isso que fecha a janela da lição 07.

No FairFare, a prancheta já existe. É a linha da quadra na tabela `resources`. Ela existe antes de qualquer reserva, existe uma só por quadra, e toda reserva aponta para ela. É o lugar natural para o cadeado.

## `SELECT ... FOR UPDATE`

O PostgreSQL tem esse cadeado pronto. Um `SELECT` comum só lê. Um `SELECT ... FOR UPDATE` lê **e tranca as linhas que leu**, até o fim da transação. Outra transação que pedir `FOR UPDATE` na mesma linha fica parada, esperando, até a primeira terminar com `COMMIT` ou `ROLLBACK`.

O nome vem da intenção: "vou ler isto, e talvez atualizar, então ninguém mais mexe enquanto eu decido". No nosso caso a gente nem vai atualizar a quadra. Usa o cadeado só pelo efeito de fila.

Dá para ver acontecer com três `psql` abertos lado a lado:

```bash
docker compose exec postgres psql -U fairfare
```

No terminal **A**, abra uma transação e tranque a quadra 1:

```console
fairfare=# BEGIN;
BEGIN
fairfare=*# SELECT * FROM resources WHERE id = 1 FOR UPDATE;
 id |   nome   |  tipo  
----+----------+--------
  1 | Quadra 1 | quadra
(1 row)
```

Não comite ainda. No terminal **B**, peça a mesma coisa:

```console
fairfare=# BEGIN;
BEGIN
fairfare=*# SELECT * FROM resources WHERE id = 1 FOR UPDATE;
```

E o B fica ali. Sem resposta, sem erro, cursor parado. Ele não falhou: está na fila.

No terminal **C**, pergunte ao PostgreSQL quem está esperando por um lock:

```console
fairfare=# SELECT pid, wait_event_type, state, query FROM pg_stat_activity WHERE wait_event_type = 'Lock';
  pid  | wait_event_type | state  |                      query                       
-------+-----------------+--------+--------------------------------------------------
 27548 | Lock            | active | SELECT * FROM resources WHERE id = 1 FOR UPDATE;
(1 row)
```

A `pg_stat_activity` é uma visão com uma linha por conexão aberta no servidor. Uma linha só, a do B: `state = active` (ele está no meio de um comando) e `wait_event_type = Lock` (o comando está esperando um cadeado).

Agora volte ao **A** e comite:

```console
fairfare=*# COMMIT;
COMMIT
```

Na hora, o **B** destrava e devolve a linha.

Para registrar a espera com número, eu não abri três janelas na mão. Rodei os três `psql` a partir de um script de shell, com o `\timing on` ligado no B e um `sleep 4` no meio do A fazendo o papel de "você, pensando antes de comitar". As saídas acima são dessas sessões. *(O script rodou o `psql` sem prompt. Os `fairfare=#` acima eu acrescentei, para ficar igual ao que você vai ver no seu terminal. O resto é a saída como saiu.)* O tempo do `SELECT ... FOR UPDATE` do B:

```console
Time: 2849.300 ms (00:02.849)
```

Quase três segundos para um `SELECT` de uma linha. Não é lentidão: é o B esperando o A soltar a prancheta.

## O diff

No app, a mudança tem duas partes. No `ResourceRepository`, um método novo:

```python
    async def get_for_update(self, resource_id: int) -> Resource | None:
        """Busca o recurso e tranca a linha até o fim da transação (lição 10)."""
        stmt = select(Resource).where(Resource.id == resource_id).with_for_update()
        return await self.db.scalar(stmt)
```

O `with_for_update()` é como o SQLAlchemy escreve o `FOR UPDATE`. O SQL que sai é este:

```sql
SELECT resources.id, resources.nome, resources.tipo 
FROM resources 
WHERE resources.id = $1::INTEGER FOR UPDATE
```

Por que não reaproveitar o `get`? Porque o `get` pode nem ir ao banco. Se o recurso já estiver na sessão, o `db.get` devolve o objeto da memória (o *identity map*: a sessão guarda os objetos que já carregou), e aí não tem `SELECT`, e sem `SELECT` não tem cadeado. Um método com nome próprio também deixa a intenção escrita: quem lê `get_for_update` sabe que ali alguém pode esperar.

No `BookingService.create`, troca uma linha:

```python
    async def create(self, data: BookingCreate) -> BookingOut:
        user = await self.users.get(data.user_id)
        # Tranca o recurso: quem chegar depois espera aqui até o commit do create
        # (ou o rollback, se der conflito). Não dá para trancar a reserva: ela ainda não existe.
        resource = await self.resources.get_for_update(data.resource_id)
        if user is None or resource is None:
            raise RelatedNotFoundError
        overlapping = await self.bookings.find_overlapping(
            data.resource_id, data.starts_at, data.ends_at
        )
        if overlapping:
            raise BookingConflictError
        booking = await self.bookings.create(
            data.user_id, data.resource_id, data.starts_at, data.ends_at
        )
        return await self._to_out(booking)
```

O que importa é a **ordem**. O cadeado vem **antes** do `find_overlapping`. Se viesse depois, as duas requests já teriam olhado a agenda, e o cadeado só organizaria quem anota primeiro. É a "caneta única" do SQLite, da lição 07, de novo: fila para anotar não adianta, a fila tem que ser para **olhar**.

## Quanto tempo o cadeado dura

O `FOR UPDATE` tranca até o fim da transação. Então a pergunta vira: onde a transação de um `POST /bookings` termina? A lição 08 já respondeu, com o log na mão.

Ela começa no autobegin, no primeiro `SELECT` do `create` (o do usuário). O cadeado entra logo depois, no `get_for_update`. E a transação termina de um de dois jeitos:

- **Horário livre.** O `BookingRepository.create` faz o `INSERT` e chama `commit()`. O `COMMIT` grava a reserva **e** solta o cadeado, no mesmo instante. A próxima request da fila destrava, roda o `find_overlapping` dela, e agora a reserva nova está lá: `409`.
- **Conflito.** O service levanta `BookingConflictError` e ninguém chama `commit()`. O router transforma o erro em `409`, e o `async with SessionLocal()` do `get_db` fecha a sessão. Fechar uma sessão com transação aberta é `ROLLBACK`, e o `ROLLBACK` solta o cadeado. O mesmo vale para o `404` e para qualquer exceção inesperada.

Repare no "agora a reserva nova está lá". Isso só é verdade porque o FairFare roda em `READ COMMITTED`, o padrão do PostgreSQL. É o nível da lição 09 em que cada **comando** tira um retrato novo. O `find_overlapping` de quem esperou é um comando novo, e começa depois do `COMMIT` da outra. O retrato dele já tem a reserva.

Em `REPEATABLE READ`, o retrato é um só, tirado no primeiro comando da transação. Aqui, o `users.get`: **antes** da espera. Eu medi. Troquei o nível da engine dos testes para `REPEATABLE READ` (só na minha máquina, isso não está no repositório) e rodei dez vezes o teste da próxima seção. Dez de dez falharam. Em cada rodada, as dez requests deram `201`, e o banco ficou com dez reservas iguais. Nenhum erro de serialização. O cadeado funcionou, a fila andou de um em um, e cada um olhou um retrato velho, em que a quadra estava livre. O `REPEATABLE READ` só aborta quem tenta trancar uma linha que outra transação **mudou**, e o `FOR UPDATE` não muda o recurso. Só tranca.

Então o cadeado e o nível de isolamento são um combinado só. Trocar um sem olhar o outro desfaz a correção, sem aviso nenhum.

Não precisou escrever `BEGIN`, nem `COMMIT`, nem `ROLLBACK` em lugar nenhum. O começo é o autobegin. O fim é o `commit()` que já mora no repository (a lição 08 explicou por que ele fica lá neste capítulo), ou o fechamento da sessão. O cadeado só pegou carona numa transação que já existia.

Isso tem um corolário que vale guardar: **o cadeado dura o que a transação dura.** Cada `await` entre o `get_for_update` e o `commit()` é tempo em que a fila daquela quadra fica parada. Hoje são só o `find_overlapping` e o `INSERT`. Se um dia alguém puser uma chamada HTTP lenta no meio, a fila inteira espera por ela.

## A prova

Primeiro, o teste. A lição 07 terminou dizendo que nenhum teste da suíte manda duas requests ao mesmo tempo. Agora um manda, em `tests/test_concorrencia.py`:

```python
async def test_reservas_simultaneas_so_uma_passa(client):
    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    respostas = await asyncio.gather(
        *(
            cria_reserva(
                client, user["id"], resource["id"], "2030-01-01T10:00:00Z", "2030-01-01T12:00:00Z"
            )
            for _ in range(10)
        )
    )
    assert sorted(r.status_code for r in respostas) == [201] + [409] * 9
```

Dez reservas idênticas, ao mesmo tempo. A resposta certa é uma só: um `201` e nove `409`.

Escrevi o teste **antes** do cadeado, e rodei. Três vezes seguidas, três falhas:

```console
$ for i in 1 2 3; do uv run pytest tests/test_concorrencia.py -q | tail -1; done
1 failed in 0.31s
1 failed in 0.27s
1 failed in 0.32s
```

E a mensagem de cada uma:

```console
E       assert [201, 201, 40...409, 409, ...] == [201, 409, 40...409, 409, ...]
```

Dois `201`. Reserva dupla, dentro da suíte.

Só que esse vermelho é **intermitente**. Rodei vinte vezes, contando os `201` de cada rodada (com uma cópia descartável do teste que gravava a contagem num arquivo):

| `201` na rodada | rodadas |
|---|---|
| 1 (o certo) | 9 |
| 2 | 4 |
| 5 | 1 |
| 6 | 1 |
| 9 | 1 |
| 10 | 4 |

Onze vermelhos em vinte. Nas outras nove, o teste passou **por sorte**: as requests não caíram juntas dentro da janela. É a corrida sendo corrida. Um teste de concorrência que passa uma vez não prova nada. Ele só prova alguma coisa quando passa sempre.

Com o cadeado, vinte de vinte:

```console
$ for i in $(seq 1 20); do uv run pytest tests/test_concorrencia.py -q | tail -1; done | sed 's/ in .*//' | sort | uniq -c
     20 1 passed
```

E a suíte inteira, com avisos virando erro:

```console
$ uv run pytest -q -W error
.............................                                            [100%]
29 passed in 1.37s
```

Agora a prova pelo caminho de verdade: uvicorn, HTTP, o `corrida.py` da lição 07. Lá ele deu `201×5` em quase toda rodada. Agora:

```console
$ B=chapters/04-o-banco-de-dados-de-verdade/bancada
$ uv run python $B/corrida.py --n 5 --rodadas 10
rodada  1: 201×1  409×4
rodada  2: 201×1  409×4
...
rodada 10: 201×1  409×4

rodadas com mais de uma reserva criada: 0/10
```

E com dez pessoas por rodada:

```console
$ uv run python $B/corrida.py --n 10 --rodadas 10
rodada  1: 201×1  409×9
rodada  2: 201×1  409×9
...
rodada 10: 201×1  409×9

rodadas com mais de uma reserva criada: 0/10
```

*(Cortei as rodadas do meio: todas iguais.)*

Zero de dez, nas duas. E repare no que **não** aparece: nenhum `500`, nenhuma rodada com "abortada", nenhum retry. Ninguém perdeu a vez. Quem chegou depois esperou a prancheta, olhou, viu a reserva de quem chegou antes, e recebeu o `409` certo de primeira.

## O custo

Cadeado tem preço. O da prancheta é este: **todas** as reservas da mesma quadra viram uma fila. Mesmo as que nem se tocam.

A Ana quer a quadra 1 de manhã. O Bruno quer a quadra 1 à noite. Não existe conflito. Mas o cadeado está na quadra, não no horário. Então o Bruno espera a Ana terminar.

Medi isso com o app de pé. Num `psql`, tranquei a quadra 1 com `FOR UPDATE` e segurei por quatro segundos. No meio, mandei duas reservas pelo `curl`, ao mesmo tempo, num horário livre (1º de fevereiro de 2040): uma na quadra 1, outra na quadra 2.

```console
quadra 2: 201 em 0.023431s
quadra 1: 201 em 2.526615s
```

As duas deram `201`: o horário estava livre nas duas quadras. A da quadra 2 passou em 23 ms, porque ninguém segurava a prancheta dela. A da quadra 1 esperou dois segundos e meio pelo cadeado, sem conflito nenhum. *(Apaguei as duas reservas depois, para não sujar o banco de dev.)*

No mundo real, quem segura a prancheta não é um `psql` parado. É outra reserva, que leva milissegundos. A fila é curta. Mas ela existe, e cresce com o movimento de **uma** quadra.

Compare com o falso positivo do `SERIALIZABLE`, na lição 09. Lá, duas reservas em quadras **diferentes** abortavam, porque as leituras moravam na mesma página do índice. Aqui:

- quadras diferentes **não esperam**: cada uma tem a sua linha, e o cadeado é por linha;
- na mesma quadra, quem chega depois **espera**, não aborta: não tem erro, não tem retry, não tem transação recomeçando do zero.

A troca é deliberada. A prancheta é grossa no tempo (a agenda inteira de uma quadra, não um horário) e fina no espaço (uma quadra, não uma página cheia de quadras vizinhas). Para um clube, em que a mesma quadra raramente recebe dezenas de pedidos no mesmo milissegundo, essa conta fecha.

E se uma operação precisar de **duas** quadras? Uma reserva que tranca a quadra 1 e depois a 2, enquanto outra tranca a 2 e depois a 1. Cada uma segura uma prancheta e espera a da outra. Para sempre? O exercício 3.2 trata disso.

## E o que sobra

O cadeado fechou a corrida **do app**. Mas olhe onde a regra mora: num `if overlapping` dentro do `BookingService.create`. E o cadeado é um combinado. Só espera quem pede `FOR UPDATE`.

Medi os dois lados disso, com a quadra 1 trancada num `psql`. Um `SELECT` comum na quadra 1, de outro `psql`, voltou em 0,5 ms: ele nem vê o cadeado. E um `INSERT` direto em `bookings`, na quadra 1, **esperou** 2,3 s. Esse é curioso: ele espera por causa da chave estrangeira, porque o PostgreSQL precisa garantir que a quadra não suma enquanto a reserva aponta para ela. Mas, depois de esperar, gravou sem perguntar nada a ninguém. Não tem `find_overlapping` num `INSERT` feito à mão. *(Desfiz com `ROLLBACK`.)*

Então qualquer caminho que grave uma reserva sem passar pelo `BookingService.create` passa por cima da regra. Um script de manutenção. Um job em segundo plano, no capítulo 8. Alguém no `psql`, numa sexta à noite. E as duplicatas da lição 07, nas quadras 51 a 70, continuam lá.

A prancheta funciona enquanto todo mundo combina de usá-la. A lição 11 tira a regra do combinado e a põe dentro do próprio banco, onde ninguém passa por cima.

## O que fica declarado

- **A corrida do `POST /bookings` está fechada**, pelo cadeado no recurso. Só por esse caminho: a regra ainda mora no service, e a lição 11 a leva para o banco.
- **As duplicatas antigas continuam no banco de dev** (quadras 51 a 70). O cadeado impede duplicatas novas pelo app; ele não conserta as velhas. De propósito: a lição 11 tropeça nelas.
- **Os três terminais e a medição do custo** vieram de sessões `psql` dirigidas por um script de shell, com `sleep` no papel da pessoa que demora a comitar. O script não está no repositório.
- **A contagem dos vinte vermelhos** usou uma cópia descartável do teste, que gravava os status num arquivo. Foi apagada. O teste do repositório é o de cima.
- **Os números são desta máquina.** A proporção de vermelhos sem o cadeado muda de máquina para máquina, e de execução para execução. O vinte de vinte com o cadeado não deveria mudar.

## O que você deve conseguir fazer agora

- Explicar por que o cadeado vai na linha do recurso e não na reserva.
- Dizer onde o cadeado começa (o `get_for_update`) e onde termina (o `commit()` do `BookingRepository.create`, ou o `ROLLBACK` quando o `get_db` fecha a sessão).
- Explicar por que o cadeado tem que vir **antes** do `find_overlapping`.
- Reproduzir a espera com três `psql` e achar quem está esperando na `pg_stat_activity`.
- Prever o que acontece com duas reservas na mesma quadra em horários diferentes, e com duas reservas em quadras diferentes no mesmo horário.
- Dizer o que o cadeado não protege: quem grava sem passar pelo `BookingService.create`.
