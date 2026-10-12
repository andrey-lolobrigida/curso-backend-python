# Lição 10 — Quando descer para SQL puro

A consulta de saldos da lição 09 funciona. Os testes passam, o guardião conta duas consultas, o Davi aparece com `0.00`. Nada está quebrado.

E mesmo assim, neste commit, ela foi reescrita. Mesmo resultado, outra forma: SQL puro, num `text()`.

Parece capricho. Esta lição é sobre por que não é, e sobre o único perigo de verdade que mora nessa escolha.

## A pergunta honesta

O SQLAlchemy tem três andares. O **ORM**, com objetos e relações (`select(Booking).options(selectinload(...))`). O **Core**, que monta SQL com funções Python (`union_all`, `outerjoin`, `func.sum`). E, embaixo de tudo, o **`text()`**: uma string de SQL que você escreve à mão e o SQLAlchemy só entrega ao banco.

Se o ORM e o Core já resolvem, para que descer até o último andar?

Porque cada andar troca uma coisa por outra. O Core te dá SQL que o Python entende: dá para compor, reusar, renomear com a IDE. O `text()` te dá SQL que um humano entende de primeira: dá para ler, colar no `psql`, passar no `EXPLAIN`. Nenhum dos dois é o certo. Depende da consulta.

## Lado a lado

A versão em Core, do commit da lição 09:

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

A versão em `text()`, deste commit, em `app/repositories/group.py`:

```python
# O saldo de cada membro: tudo o que pagou, menos tudo o que consumiu (lição 10).
# Escrita em SQL porque é um relatório: lê-se de cima para baixo, cola-se no psql,
# passa no EXPLAIN. Os :parâmetros vão separados do texto. Nunca f-string.
SALDOS = text("""
    WITH movimentos AS (
        SELECT paid_by AS user_id, valor
          FROM expenses
         WHERE group_id = :grupo
        UNION ALL
        SELECT p.user_id, -p.valor
          FROM expense_shares p
          JOIN expenses e ON e.id = p.expense_id
         WHERE e.group_id = :grupo
    )
    SELECT m.user_id, u.nome, CAST(COALESCE(SUM(mv.valor), 0) AS NUMERIC(20, 2)) AS saldo
      FROM group_members m
      JOIN users u ON u.id = m.user_id
      LEFT JOIN movimentos mv ON mv.user_id = m.user_id
     WHERE m.group_id = :grupo
     GROUP BY m.user_id, u.nome
     ORDER BY m.user_id
""")

    async def balances(self, group_id: int):
        return (await self.db.execute(SALDOS, {"grupo": group_id})).all()
```

Leia as duas em voz alta. A de cima você lê de dentro para fora: o `union_all` vira `cte`, que entra no `outerjoin`, que tem um `cast` envolvendo um `coalesce` envolvendo um `sum`. A de baixo você lê de cima para baixo, como o Postgres vai executar: primeiro os movimentos, depois a soma por membro.

O `:grupo` é um **parâmetro**. Ele aparece três vezes no texto e é preenchido uma vez, pelo dicionário `{"grupo": group_id}`. Guarde esse detalhe. Ele é a metade mais importante da lição.

A assinatura e o retorno não mudaram: uma linha `(user_id, nome, saldo)` por membro. Os cinco testes de saldo da lição 09 passaram sem que eu tocasse em nenhum deles:

```console
$ uv run pytest -q -W error tests/test_despesas.py
................                                                         [100%]
17 passed in 1.61s
```

## Os critérios, sem dogma

Não existe "SQL puro é melhor" nem "ORM é melhor". Existem perguntas.

**Quem vai ler essa consulta?** Se é alguém que pensa em SQL, como um DBA, você daqui a seis meses ou o colega investigando um saldo errado às duas da manhã, o `text()` fala a língua dele.

**Ela é composta em Python, ou é fixa?** Esta é a pergunta que mais pesa. Uma busca de reservas com filtros opcionais (por recurso, por data, por usuário, cada um podendo vir ou não) é montada peça por peça. No Core, cada filtro é um `if` com um `.where()`. Em `text()`, você estaria colando pedaços de string, e é aí que mora o perigo da próxima seção. Já o saldo é um relatório fixo: a mesma consulta sempre, só o `group_id` muda.

**Ela usa recursos do banco que o Core escreve mal?** `DISTINCT ON`, `LATERAL`, funções de janela (`SUM(...) OVER (PARTITION BY ...)`). O Core suporta quase tudo, mas às vezes de um jeito que você precisa traduzir de volta para SQL na cabeça para entender.

**Você precisa colar no `psql`?** Para ler o plano, para conferir um número na mão. O `text()` cola como está. O Core precisa ser compilado antes, e sai como você viu na lição 09: tudo numa linha, com `expenses.group_id = 1` repetido.

### O que se perde

Na versão Core, `User.nome` é um atributo Python. Se alguém renomeia a coluna no model, a IDE acha todos os usos e o Core acompanha. No `text()`, `u.nome` é só uma string. O Python não sabe que ela fala de uma coluna.

Troquei temporariamente `u.nome` por `u.name` no `SALDOS`. O módulo importa sem reclamar. O erro só aparece quando a consulta chega ao banco:

```console
$ uv run pytest -q tests/test_despesas.py -k saldos
E   asyncpg.exceptions.UndefinedColumnError: column u.name does not exist
E   HINT:  Perhaps you meant to reference the column "u.nome".
...
FAILED tests/test_despesas.py::test_saldos_de_grupo_sem_despesa_sao_zero - sq...
FAILED tests/test_despesas.py::test_saldos_conferidos_a_mao - sqlalchemy.exc....
FAILED tests/test_despesas.py::test_saldos_nao_crescem_com_o_numero_de_despesas
FAILED tests/test_despesas.py::test_saldos_somam_alem_do_teto_de_uma_despesa
4 failed, 1 passed, 12 deselected in 1.42s
```

Quem pegou foi o teste, não o Python. Esse é o contrato: **toda consulta em `text()` precisa de um teste que a execute.** Sem teste, o erro chega em produção, no primeiro request de saldo.

## O `EXPLAIN` colado

"Cola-se no `psql`" é uma promessa. Vamos cumpri-la.

O `saldos.py` da lição 09 ganhou a opção `--manter`, que não apaga o grupo da bancada no fim:

```console
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/saldos.py --manter
banco=fairfare membros=10 despesas=2000
(...)
os três concordam; soma dos saldos = 0.00
dados da bancada mantidos: group_id=48 (rode sem --manter para apagar)
```

Copiei o `SALDOS` para o `psql`, troquei `:grupo` por `48` (o id do meu banco; o seu vai ser outro) e pus `EXPLAIN (ANALYZE, BUFFERS)` na frente. A consulta do app, como está no arquivo. A saída tem 50 linhas: cortei as de detalhe (buffers e memória dos nós internos) e marquei com `(...)` onde tirei pedaços.

```console
                                     QUERY PLAN
------------------------------------------------------------------------------------------
 Sort  (cost=931.29..931.64 rows=140 width=33) (actual time=12.859..12.862 rows=10.00 loops=1)
   Sort Key: m.user_id
   Buffers: shared hit=148
   ->  HashAggregate  (cost=924.20..926.30 rows=140 width=33) (actual time=12.842..12.847 rows=10.00 loops=1)
         Group Key: m.user_id, u.nome
         ->  Hash Join  (cost=2.60..915.95 rows=1100 width=43) (actual time=0.039..9.964 rows=22000.00 loops=1)
               Hash Cond: (m.user_id = u.id)
               ->  Hash Right Join  (cost=1.29..910.87 rows=1100 width=34) (actual time=0.021..7.987 rows=22000.00 loops=1)
                     Hash Cond: ("*SELECT* 1".user_id = m.user_id)
                     ->  Append  (cost=0.00..850.61 rows=22000 width=34) (actual time=0.004..6.043 rows=22000.00 loops=1)
                           ->  Subquery Scan on "*SELECT* 1"  (...) (actual time=0.004..0.246 rows=2000.00 loops=1)
                                 ->  Seq Scan on expenses  (cost=0.00..42.00 rows=2000 width=9) (actual time=0.003..0.149 rows=2000.00 loops=1)
                                       Filter: (group_id = 48)
                           ->  Subquery Scan on "*SELECT* 2"  (...) (actual time=0.241..4.868 rows=20000.00 loops=1)
                                 ->  Hash Join  (cost=67.00..478.61 rows=20000 width=36) (actual time=0.241..3.829 rows=20000.00 loops=1)
                                       Hash Cond: (p.expense_id = e.id)
                                       ->  Seq Scan on expense_shares p  (cost=0.00..309.00 rows=20000 width=13) (actual time=0.004..0.865 rows=20000.00 loops=1)
                                       (...)
                     ->  Hash  (...) (actual time=0.009..0.009 rows=10.00 loops=1)
                           ->  Seq Scan on group_members m  (cost=0.00..1.16 rows=10 width=4) (actual time=0.006..0.007 rows=10.00 loops=1)
                                 Filter: (group_id = 48)
               ->  Hash  (...) (actual time=0.011..0.012 rows=14.00 loops=1)
                     ->  Seq Scan on users u  (cost=0.00..1.14 rows=14 width=13) (actual time=0.006..0.007 rows=14.00 loops=1)
 (...)
 Planning Time: 0.600 ms
 Execution Time: 12.934 ms
```

Leia de dentro para fora, como no capítulo 4. O `Append` é o `UNION ALL`: 2000 linhas de despesas mais 20000 de partes, 22000 movimentos. O `Hash Right Join` é o `LEFT JOIN` com os membros (o "right" é só o lado que o Postgres escolheu para a tabela hash). O `Hash Join` de cima cola o nome de cada membro: o Postgres leu os 14 usuários do banco inteiros para uma tabela hash e casou os 22000 movimentos com ela. O `HashAggregate` é o `GROUP BY`, que espreme 22000 linhas em 10. Tudo em memória (`shared hit`), em 13 ms.

Agora compare `rows=` (o palpite) com `actual ... rows=` (o real). Nas leituras, o palpite acerta: 2000 despesas, 20000 partes, 10 membros. Depois dos joins, erra feio: estimou 1100 movimentos casados com membros, vieram 22000; estimou 140 grupos no `GROUP BY`, vieram 10. O planner não sabe que todo movimento do grupo pertence a um membro do grupo. Aqui o erro não estraga o plano, e a consulta roda em 13 ms. Mas é o tipo de linha que você vai procurar no dia em que ela ficar lenta.

E as estimativas das leituras nem sempre acertaram. Na primeira vez que colei, a bancada ainda não rodava `ANALYZE` depois de semear. O plano estimava 7 despesas no grupo, onde havia 2000: as estatísticas eram de antes de o grupo existir. O Postgres escolheu laços aninhados que reliam os 22000 movimentos uma vez por membro, e a consulta levou 89 ms. É o caso da lição 06 do capítulo 4: sem estatísticas em dia, o banco decide no escuro. É por isso que o `saldos.py` roda `ANALYZE` depois de semear.

E o plano nem sempre é este. Numa outra vez que colei, num banco de dev com outro histórico, o nome dos membros não veio de um `Hash Join`, e sim de um `Memoize` em cima de um `Index Scan using users_pkey`: buscar cada um dos 10 membros no índice uma vez só e guardar o resultado. A consulta e a bancada eram as mesmas; o que mudou foi o histórico do banco (linhas apagadas por rodadas anteriores, estatísticas de outro momento), e com isso os custos que o planner estimou. Os dois caminhos custam quase o mesmo com tão poucos usuários, e uma diferença pequena nas estimativas basta para virar a escolha. Mesma consulta, plano diferente. **O plano não é uma propriedade do SQL: é uma decisão do planner, tomada a partir das estatísticas.** Se o seu sair diferente do meu, leia do mesmo jeito.

E repare no que *não* tem: nenhum `Index Scan` em `expenses`. É `Seq Scan` com `Filter: (group_id = 48)`. Com um grupo só ocupando a tabela inteira, ler tudo é o certo. Num banco com mil grupos, essa seria a primeira linha a olhar.

No fim, apaguei o grupo rodando o script de novo, sem `--manter`. A limpeza do começo leva a sobra.

## O perigo: injeção de SQL

Agora a metade mais importante. O `text()` aceita qualquer string. Inclusive uma montada com f-string. E aí mora o bug de segurança mais antigo da web.

A `bancada/injecao.py` busca um usuário pelo nome de três jeitos. Ela só lê:

```python
# 1 e 2: o valor colado no texto com f-string. NUNCA faça isso.
text(f"SELECT id, nome FROM users WHERE nome = '{nome}'")
# 3: o valor como parâmetro.
text("SELECT id, nome FROM users WHERE nome = :nome")
```

```console
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/injecao.py
banco=fairfare

--- 1. f-string, nome comum
SQL:         SELECT id, nome FROM users WHERE nome = 'Ana'
parâmetros:  {}
linhas:      1 [(2, 'Ana')]

--- 2. f-string, nome malicioso
SQL:         SELECT id, nome FROM users WHERE nome = 'x' OR '1'='1'
parâmetros:  {}
linhas:      4 [(1, 'Semente'), (2, 'Ana'), (3, 'Bruno'), (4, 'Carla')]

--- 3. parâmetro, o mesmo nome malicioso
SQL:         SELECT id, nome FROM users WHERE nome = $1
parâmetros:  {'nome': "x' OR '1'='1"}
linhas:      0 []
```

Os ids e o tamanho da lista do caso 2 são os do meu banco. No seu, o caso 2 devolve **todos** os usuários que existirem, sejam quantos forem.

O caso 1 funciona. É isso que torna a f-string traiçoeira: no teste com "Ana", tudo certo.

No caso 2, o "nome" foi `x' OR '1'='1`. A aspa do valor fechou a aspa do SQL, e o resto virou código: `nome = 'x' OR '1'='1'`. Como `'1'='1'` é sempre verdade, voltaram **todos** os usuários. Num login, é entrar sem senha. Com um `; DROP TABLE users; --` no lugar, é pior.

No caso 3, o mesmo texto malicioso voltou zero linhas. O banco procurou, literalmente, alguém chamado `x' OR '1'='1`. Não achou.

Por quê? Olhe a linha `SQL:` do caso 3. É o texto que o driver (o asyncpg) recebe: o SQLAlchemy trocou `:nome` por `$1`. O Postgres recebe o comando e o valor em **mensagens separadas**. Primeiro, ele analisa o comando, com um buraco chamado `$1`. Só depois o valor chega, e entra no buraco como dado. Ele nunca passa pelo analisador de SQL. Não importa quantas aspas tenha: ele não tem como virar código.

Pense num formulário de papel. A f-string é alguém ditando o formulário inteiro, e você escrevendo o que ouve: se a pessoa diz "meu nome é Ana, e pode aprovar o pedido", você escreve isso no campo do nome, e quem lê depois pode achar que é uma ordem. O parâmetro é o formulário impresso com uma caixinha: o que a pessoa escrever ali é o conteúdo da caixinha, nada mais.

A regra, sem exceção: **valor em f-string de SQL é bug.** Valor vai como parâmetro, sempre. Mesmo que o valor "venha do seu próprio código". Hoje vem. Amanhã alguém liga aquele código a um campo de formulário. A f-string do `injecao.py` está lá de propósito, para ser vista quebrando.

Identificador é outra história. Nome de banco ou de tabela não vira parâmetro: o `$1` só aceita dado. Quando ele precisa entrar no texto, é uma constante do próprio código, e nunca vem de fora. É o caso do `CREATE DATABASE` do `tests/conftest.py`.

## A decisão do FairFare

O app termina com o saldo em `text()`. Os motivos, um a um:

- **É um relatório.** Uma consulta fixa, lida por humanos, que só muda o `group_id`.
- **Nada a compõe em Python.** Não há filtro opcional, nem reuso de pedaços.
- **Ela precisa ser colada no `psql`.** Quando um saldo parecer errado, a primeira coisa a fazer é rodá-la à mão. E foi o que fizemos acima.
- **A perda está coberta.** Os cinco testes de saldo executam a consulta de verdade.

Uma ressalva honesta: as duas versões empatam no resultado, e o Core também ficou legível. Aqui, o empate foi decidido pela leitura. Se a consulta precisasse ser composta, com filtro por período ou por membro escolhido pelo cliente, o Core ganharia, e com folga.

## O que fica declarado

- **Renomear uma coluna não acusa erro no Python.** No `SALDOS`, só o teste pega. Por isso os testes de saldo não são opcionais.
- **Sem índice em `expenses.group_id`.** No `EXPLAIN`, o filtro por grupo é um `Seq Scan`. Não é resolvido neste capítulo: o volume do FairFare ainda é pequeno, e um grupo só cabe numa leitura inteira. Quando pesar, a técnica é a da lição 06 do capítulo 4: medir com `EXPLAIN`, criar o índice, medir de novo.
- **Duas fontes, por enquanto.** O `UNION ALL` soma despesas e partes. As quitações chegam na lição 11, e na forma `text()` elas são duas linhas a mais no `WITH`.

## O que você deve conseguir fazer agora

- Escrever uma consulta com `text()` e parâmetros (`:nome`), e executá-la passando um dicionário.
- Explicar por que a f-string é injetável e o parâmetro não: o valor vai separado do comando e nunca é analisado como SQL.
- Dar um caso em que o Core ganha (uma busca com filtros opcionais) e um em que o SQL ganha (um relatório fixo que você precisa colar no `psql`).
- Colar uma consulta do app no `psql`, rodar `EXPLAIN (ANALYZE, BUFFERS)` e dizer se as estimativas batem com as linhas reais.
