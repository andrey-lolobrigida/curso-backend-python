# Lição 09 — Saldos: quem soma?

As despesas existem. Agora a pergunta que todo grupo de viagem faz no último dia: quem deve para quem?

O FairFare responde com um número por pessoa, o **saldo**. Positivo: o grupo te deve. Negativo: você deve ao grupo. Esta lição traz o `GET /groups/{id}/balances` e uma pergunta que parece boba: quem faz a soma, o Python ou o banco?

## O saldo não é guardado

Daria para ter uma coluna `saldo` em `group_members` e atualizá-la a cada despesa. Uma leitura e pronto.

Não vamos fazer isso. O saldo é **calculado** a partir das despesas e das partes, toda vez que alguém pergunta.

O motivo é ter uma fonte de verdade só. Pense num caderno de contas e num post-it na geladeira com o total. Enquanto todo mundo lembra de atualizar o post-it, ele é ótimo. No dia em que alguém esquece, você tem dois números, e nenhum jeito de saber qual está certo.

No banco, é igual. Uma coluna `saldo` é uma cópia derivada das despesas. Toda escrita precisaria atualizar as duas coisas, na mesma transação, sem exceção. Uma despesa lançada por um script, uma correção feita no `psql`, um bug num caminho novo, e a cópia diverge em silêncio. Calculando, não tem cópia para divergir.

O preço é recalcular a cada request. Guardar o resultado para não recalcular tem nome: cache. É o assunto do capítulo 7, com todos os problemas de invalidação que ele traz.

## A conta à mão

Antes de escrever qualquer consulta, a conta no papel. É o cenário do `test_saldos_conferidos_a_mao`. Quatro amigos: Ana, Bruno, Carla e Davi.

- A Ana paga R$ 100 de mercado, dividido entre Ana, Bruno e Carla. Pela regra da lição 07, as partes são 33,34 (Ana), 33,33 e 33,33.
- O Bruno paga R$ 30 de pizza, dividido entre Ana e Bruno: 15,00 para cada.

O saldo de cada um é o que **pagou** menos o que **consumiu**:

| Quem | Pagou | Consumiu | Saldo |
|---|---|---|---|
| Ana | 100,00 | 33,34 + 15,00 | **+51,66** |
| Bruno | 30,00 | 33,33 + 15,00 | **−18,33** |
| Carla | 0,00 | 33,33 | **−33,33** |
| Davi | 0,00 | 0,00 | **0,00** |

Some a coluna da direita: 51,66 − 18,33 − 33,33 + 0 = **zero**.

Não é coincidência. Todo real pago por alguém foi consumido por alguém. Cada despesa entra uma vez com sinal de mais (quem pagou) e, somadas as partes, uma vez com sinal de menos (quem consumiu). E as partes fecham o total ao centavo, pela regra da lição 07. Então a soma de todos os saldos de um grupo é zero, sempre. É um invariante de graça: se um dia der diferente de zero, tem bug.

E o Davi está na tabela, com zero. Ele não gastou nada, mas é membro. Guarde isso. Ele vai tentar sumir daqui a pouco.

## Três jeitos de somar

Escrevi a mesma conta de três jeitos em `bancada/saldos.py`. O script cria no banco de dev um grupo da bancada com 10 membros próprios e 2000 despesas, cada uma dividida entre os 10. São 2000 linhas em `expenses` e 20000 em `expense_shares`. Antes de medir, ele roda um `ANALYZE` nessas tabelas. Sem isso, o Postgres ainda não sabe que o grupo recém-criado tem 2000 despesas, planeja a consulta para meia dúzia e o tempo do (c) passa a depender de quando o autovacuum resolveu atualizar as estatísticas. No fim, ele apaga tudo.

**(a) Python ingênuo.** Para cada membro, uma consulta do que ele pagou e outra das partes dele. A soma é feita no Python:

```python
for user_id in membros:
    pagos = list(await db.scalars(select(Expense.valor).where(...)))
    partes = list(await db.scalars(select(ExpenseShare.valor).join(...).where(...)))
    saldos[user_id] = sum(pagos, Decimal("0")) - sum(partes, Decimal("0"))
```

Uma consulta para listar os membros, mais duas por membro. É o 2N+1 da lição 03 com outra roupa. Lá, o N eram as reservas. Aqui, são os membros.

**(b) Python carregando tudo.** As despesas com `selectinload(Expense.partes)`, a lição 03 aplicada direitinho, e um laço que soma.

**(c) O banco soma.** O `GroupRepository.balances`, a consulta que o app usa. Ela devolve uma linha por membro, já somada.

Os números, cada um rodado 3 vezes, numa sessão nova a cada rodada:

```console
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/saldos.py
banco=fairfare membros=10 despesas=2000
(a) python ingênuo      rodada 1: consultas=21 linhas=22010 tempo=48ms
(a) python ingênuo      rodada 2: consultas=21 linhas=22010 tempo=31ms
(a) python ingênuo      rodada 3: consultas=21 linhas=22010 tempo=42ms
(b) python carrega tudo rodada 1: consultas=5 linhas=22000 tempo=222ms
(b) python carrega tudo rodada 2: consultas=5 linhas=22000 tempo=226ms
(b) python carrega tudo rodada 3: consultas=5 linhas=22000 tempo=239ms
(c) o banco soma        rodada 1: consultas=1 linhas=10 tempo=12ms
(c) o banco soma        rodada 2: consultas=1 linhas=10 tempo=9ms
(c) o banco soma        rodada 3: consultas=1 linhas=10 tempo=12ms
os três concordam; soma dos saldos = 0.00
dados da bancada apagados
```

E com dez vezes mais despesas:

```console
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/saldos.py --despesas 20000
banco=fairfare membros=10 despesas=20000
(a) python ingênuo      rodada 1: consultas=21 linhas=220010 tempo=330ms
(a) python ingênuo      rodada 2: consultas=21 linhas=220010 tempo=319ms
(a) python ingênuo      rodada 3: consultas=21 linhas=220010 tempo=316ms
(b) python carrega tudo rodada 1: consultas=41 linhas=220000 tempo=3086ms
(b) python carrega tudo rodada 2: consultas=41 linhas=220000 tempo=3179ms
(b) python carrega tudo rodada 3: consultas=41 linhas=220000 tempo=3255ms
(c) o banco soma        rodada 1: consultas=1 linhas=10 tempo=72ms
(c) o banco soma        rodada 2: consultas=1 linhas=10 tempo=67ms
(c) o banco soma        rodada 3: consultas=1 linhas=10 tempo=69ms
os três concordam; soma dos saldos = 0.00
dados da bancada apagados
```

Os tempos são desta máquina, com o Postgres no mesmo computador. Os seus vão ser outros. Olhe as proporções, não os milissegundos.

Agora, com calma, porque tem surpresa aqui.

**O (b) perdeu do (a).** O jeito "certo" da lição 03 foi o mais lento, de longe. Olhe a coluna `linhas`. Nas duas medições, os dois trazem o mesmo volume para o Python: 22 mil linhas com 2000 despesas, 220 mil com 20000 (os 10 a mais do (a) são a consulta dos membros). A diferença está no que o Python faz com cada uma. O (a) recebe um `Decimal` solto. O (b) monta um objeto `Expense` ou `ExpenseShare`, registra no identity map e pendura nas coleções. Não isolei o custo de cada passo, mas a diferença entre os dois está toda aí. O `selectinload` resolve o problema do número de consultas. Ele não resolve o problema de trazer dados que você não precisava.

**O "poucas consultas" do (b) não é fixo.** Foram 5 consultas com 2000 despesas, e 41 com 20000. O `selectinload` manda os ids das despesas num `IN (...)` de 500 em 500. Com 20000 despesas, são 40 lotes de partes, mais a consulta das despesas.

**O (a) só parece bom.** Ele ficou em 21 consultas porque o grupo tem 10 membros, e o banco está a um passo de distância. O N dele são os membros. Com 100 membros, são 201 consultas. Com o banco do outro lado de uma rede, cada uma paga a ida e a volta. E ele também carrega as 22 mil, ou 220 mil, linhas para somar no Python.

**O (c) traz 10 linhas.** Uma por membro, nas duas medições. As 22 mil, ou 220 mil, linhas são lidas, sim, mas lá dentro do Postgres, perto do disco, por um código feito para isso. Pelo fio passam só os resultados.

A regra que sai daqui: **leve a conta para onde os dados estão**. Se você precisa de cada linha, como na listagem de reservas, carregue as linhas, com `selectinload`. Se você precisa de um resumo, uma soma, uma contagem, peça o resumo ao banco.

## A consulta, peça por peça

O `GroupRepository.balances`, em Core, que é a camada de SQL do SQLAlchemy, sem objetos ORM:

```python
async def balances(self, group_id: int):
    # Cada movimento de dinheiro vira uma linha (user_id, valor): quem pagou ganha,
    # quem consumiu perde. O saldo é a soma por membro (lição 09).
    movimentos = union_all(
        select(Expense.paid_by.label("user_id"), Expense.valor).where(
            Expense.group_id == group_id
        ),
        select(ExpenseShare.user_id, (-ExpenseShare.valor).label("valor"))
        .join(Expense, Expense.id == ExpenseShare.expense_id)
        .where(Expense.group_id == group_id),
    ).cte("movimentos")
    stmt = (
        select(
            GroupMember.user_id,
            User.nome,
            # Membro sem movimento: o SUM dá NULL, e o 0 sem casas viraria "0" no JSON.
            cast(func.coalesce(func.sum(movimentos.c.valor), 0), Numeric(20, 2)).label("saldo"),
        )
        .join(User, User.id == GroupMember.user_id)
        .outerjoin(movimentos, movimentos.c.user_id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
        .group_by(GroupMember.user_id, User.nome)
        .order_by(GroupMember.user_id)
    )
    return (await self.db.execute(stmt)).all()
```

**`union_all`: os movimentos.** A ideia central é a tabela da conta à mão, virada de lado. Cada despesa vira uma linha `(quem pagou, +valor)`. Cada parte vira uma linha `(quem consumiu, −valor)`. O `UNION ALL` empilha os dois resultados num só. O `ALL` diz para não tirar repetidas: duas pizzas de R$ 30 pagas pelo Bruno são duas linhas iguais, e as duas contam. O `UNION` sem `ALL` jogaria uma fora.

**`cte`: dar nome.** CTE é *common table expression*: uma subconsulta com nome, escrita no começo, no `WITH`. Ela deixa a consulta de baixo falar de `movimentos` como se fosse uma tabela.

**`outerjoin`: o Davi.** A consulta parte de `group_members`, a lista de quem está no grupo, e cola os movimentos de cada um. Com um `join` comum, só sobra quem tem movimento. Troquei temporariamente o `outerjoin` por `join` e rodei os testes:

```console
$ uv run pytest -q tests/test_despesas.py -k "saldos_conferidos or sem_despesa"
E       AssertionError: assert [] == ['0.00', '0.00']
...
E       AssertionError: assert [(1, '51.66')...(3, '-33.33')] == [(1, '51.66')..., (4, '0.00')]
E         
E         Right contains one more item: (4, '0.00')
...
2 failed, 15 deselected in 0.52s
```

O Davi sumiu da lista. E no grupo sem despesa nenhuma, sumiu todo mundo: a resposta é `[]`. O `LEFT OUTER JOIN` mantém toda linha da esquerda (os membros), mesmo sem par à direita. Onde não tem par, as colunas de `movimentos` vêm `NULL`.

**`coalesce`: o NULL vira zero.** O `SUM` de nada é `NULL`, não zero. Sem o `coalesce`, o `NULL` chega ao `BalanceOut` como `None`:

```console
E       pydantic_core._pydantic_core.ValidationError: 1 validation error for BalanceOut
E       saldo
E         Decimal input should be an integer, float, string or Decimal object [type=decimal_type, input_value=None, input_type=NoneType]
```

O `COALESCE(x, 0)` devolve o primeiro valor que não é `NULL`.

**`cast`: o `"0"` × `"0.00"`.** Com o `coalesce` e sem o `cast`, os testes ainda falham:

```console
E       AssertionError: assert ['0', '0'] == ['0.00', '0.00']
E         
E         At index 0 diff: '0' != '0.00'
```

O `0` do `coalesce` é um inteiro, sem casas decimais. Ele vira `Decimal('0')`, e o Pydantic escreve `"0"` no JSON. A lição 06 prometeu dinheiro sempre com duas casas. O `CAST(... AS NUMERIC(20, 2))` cumpre a promessa no banco: `0` vira `0.00`, como qualquer outro saldo.

**Por que 20, e não o 12 da coluna?** Porque saldo não é valor: é soma de valores. A lição 06 disse que `Numeric(12, 2)` "dá e sobra" para uma despesa, e dá. Para a soma de várias, não. A primeira versão desta consulta usava `NUMERIC(12, 2)`, copiado da coluna, e o `test_saldos_somam_alem_do_teto_de_uma_despesa` pegou: três despesas de `9999999999.99`, cada uma válida, deixam a Ana com quase quinze bilhões a receber. Com o 12, o `GET` dá 500:

```console
$ uv run pytest -q tests/test_despesas.py -k teto
E   asyncpg.exceptions.NumericValueOutOfRangeError: numeric field overflow
E   DETAIL:  A field with precision 12, scale 2 must round to an absolute value less than 10^10.
...
1 failed, 16 deselected in 1.33s
```

E não era só o saldo que morria. Despesa não se apaga (lição 12), então o grupo ficaria com o saldo quebrado para sempre. Com 20 dígitos, o teto do saldo é 10^18: seriam precisos cem milhões de despesas no valor máximo para estourar. O `Numeric` do Postgres aceita até 1000 dígitos; 20 é um número escolhido, não um limite do banco. Moral: **o tipo do resultado de uma conta não é o tipo das parcelas.**

O SQL que o SQLAlchemy gera, com o `group_id` 1 escrito no lugar dos parâmetros. Colei no `psql` do banco de dev, onde o grupo 1 ainda não tem despesa:

```console
fairfare=# WITH movimentos AS
(SELECT expenses.paid_by AS user_id, expenses.valor AS valor
FROM expenses
WHERE expenses.group_id = 1 UNION ALL SELECT expense_shares.user_id AS user_id, -expense_shares.valor AS valor
FROM expense_shares JOIN expenses ON expenses.id = expense_shares.expense_id
WHERE expenses.group_id = 1)
 SELECT group_members.user_id, users.nome, CAST(coalesce(sum(movimentos.valor), 0) AS NUMERIC(20, 2)) AS saldo
FROM group_members JOIN users ON users.id = group_members.user_id LEFT OUTER JOIN movimentos ON movimentos.user_id = group_members.user_id
WHERE group_members.group_id = 1 GROUP BY group_members.user_id, users.nome ORDER BY group_members.user_id;
 user_id | nome  | saldo
---------+-------+-------
       2 | Ana   |  0.00
       3 | Bruno |  0.00
       4 | Carla |  0.00
(3 rows)
```

Os ids são os do meu banco de dev. Os seus vão ser outros.

O `GroupService.balances` confere se o grupo existe e transforma as linhas em `BalanceOut`. Ele é leitura pura, então fica sem `begin()`, como o `get` (lição 08). Grupo inexistente dá `404`.

## O guardião

Na lição 03, um teste passou a contar as consultas do `GET /bookings`. Os saldos ganham o seu:

```python
async def test_saldos_nao_crescem_com_o_numero_de_despesas(client, engine_de_teste):
    g = await grupo_com(client, 3)
    for _ in range(5):
        await cria_despesa(client, g, paid_by=1, valor="10.00")
    with conta_consultas(engine_de_teste) as contagem:
        await client.get(f"/groups/{g}/balances")
    assert contagem["n"] == 2  # o grupo existe? + os saldos
```

Duas consultas: o `exists` do service e a dos saldos. Com 5 despesas ou com 5000. A bancada conta 1 no (c) porque chama o repository direto, sem o service. Se alguém trocar a consulta por um laço em Python, o número cresce e o teste quebra.

## O que fica declarado

- **O saldo é recalculado a cada request.** Correto, e caro num grupo com muitas despesas. É o candidato a cache do capítulo 7.
- **As quitações ainda não existem.** O saldo de hoje é só pago menos consumido. A lição 11 traz as quitações, e a consulta ganha mais duas fontes no `UNION ALL`.
- **Esta forma, em Core, não é a final.** Na lição 10, a mesma consulta é reescrita em SQL puro, e o diff entre as duas é a própria lição.

## O que você deve conseguir fazer agora

- Calcular à mão os saldos de um grupo a partir das despesas e das partes, e conferir que somam zero.
- Explicar por que a consulta usa `outerjoin`, e o que acontece com quem não gastou nada se ele vira `join`.
- Dizer por que o `coalesce` e o `cast` estão lá, e o que o cliente receberia sem cada um.
- Olhar uma tela e decidir onde somar: se ela mostra cada linha, carregue as linhas; se mostra um resumo, peça o resumo ao banco.
