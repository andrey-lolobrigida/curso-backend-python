# Lição 11 — A regra mora no banco

A lição 10 fechou a corrida com um cadeado na quadra. E terminou com uma ressalva: a prancheta funciona enquanto **todo mundo combina de usá-la**.

Esta lição tira a regra do combinado. "Uma quadra não tem duas reservas no mesmo horário" deixa de ser um `if` no service e vira uma regra **do banco**. Aí não importa por onde a reserva chega.

## O buraco que o cadeado deixa

A lição 10 mediu: um `INSERT` feito à mão no `psql` espera o cadeado e depois grava sem perguntar nada. Não tem `find_overlapping` num `INSERT`.

Dá para escrever esse buraco como teste. Em `tests/test_concorrencia.py`:

```python
async def test_sem_a_verificacao_previa_o_banco_ainda_recusa(client, monkeypatch):
    # Simula quem perdeu a corrida: passou pela verificação (que não viu nada) e foi gravar.
    async def nada_sobrepoe(self, resource_id, starts_at, ends_at):
        return []

    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    primeira = await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T10:00:00Z", "2030-01-01T12:00:00Z"
    )
    assert primeira.status_code == 201
    monkeypatch.setattr(BookingRepository, "find_overlapping", nada_sobrepoe)
    segunda = await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T11:00:00Z", "2030-01-01T13:00:00Z"
    )
    assert segunda.status_code == 409
```

O `monkeypatch` é uma fixture do pytest que troca um atributo durante um teste e desfaz a troca no fim. Aqui ele troca o `find_overlapping` por uma função que sempre responde "nada sobrepõe". É exatamente o que vê quem perde a corrida: olhou a agenda antes da outra gravar.

Com o cadeado da lição 10 ainda no lugar:

```console
$ uv run pytest tests/test_concorrencia.py -v
...
>       assert segunda.status_code == 409
E       assert 201 == 409
E        +  where 201 = <Response [201 Created]>.status_code
...
========================= 1 failed, 1 passed in 0.34s ==========================
```

`201`. Das 11h às 13h, por cima de uma reserva das 10h às 12h. O cadeado não ajudou em nada, porque cadeado organiza **quem olha**. Se o olhar falha, ninguém mais confere.

## A regra na porta

Pense num clube com uma regra: "uma quadra, uma reserva por horário". Hoje ela está no bolso de um funcionário, o `BookingService`. Quem passa pelo balcão é barrado. Quem entra pela porta dos fundos, não.

A alternativa é escrever a regra **na porta da agenda**. Não importa quem chega, nem por onde: a agenda recusa.

O PostgreSQL tem isso pronto. Chama **exclusion constraint**:

```sql
EXCLUDE USING gist (resource_id WITH =, tstzrange(starts_at, ends_at) WITH &&)
```

Lida em voz alta: "não pode haver duas linhas com o **mesmo** `resource_id` **e** intervalos que **se sobrepõem**". Para cada par de linhas, o banco aplica os operadores. Se **todos** derem verdadeiro, o par é proibido.

Você já conhece um caso especial disso: o `UNIQUE`. Ele é um `EXCLUDE` em que todos os operadores são `=`. O `EXCLUDE` deixa escolher o operador de cada coluna. Aqui, `=` no recurso e `&&` no horário.

### `tstzrange` e o `[)`

`tstzrange(início, fim)` monta um **intervalo** de `timestamptz` (a lição 04). E `&&` é o operador "se sobrepõe a":

```console
fairfare=# SELECT tstzrange('2031-01-01 10:00+00', '2031-01-01 12:00+00');
                      tstzrange                      
-----------------------------------------------------
 ["2031-01-01 10:00:00+00","2031-01-01 12:00:00+00")
(1 row)

fairfare=# SELECT tstzrange('2031-01-01 10:00+00', '2031-01-01 12:00+00') && tstzrange('2031-01-01 12:00+00', '2031-01-01 14:00+00') AS encostadas,
       tstzrange('2031-01-01 10:00+00', '2031-01-01 12:00+00') && tstzrange('2031-01-01 11:59+00', '2031-01-01 14:00+00') AS um_minuto;
 encostadas | um_minuto 
------------+-----------
 f          | t
(1 row)
```

Olhe os colchetes: `[` no começo, `)` no fim. O início **pertence** ao intervalo; o fim, **não**. Às 12h em ponto, a reserva das 10h às 12h já acabou. Por isso uma reserva que termina às 12h e outra que começa às 12h **não** se sobrepõem. É a mesma regra do `find_overlapping` desde o capítulo 1, e o teste das reservas encostadas da lição 04 continua verde.

### E a reserva de duração zero?

O `[)` tem um caso de canto. Um intervalo que começa e termina no mesmo instante não contém instante nenhum. O PostgreSQL o chama de **vazio**, e um vazio não se sobrepõe a nada:

```console
fairfare=# SELECT tstzrange('2031-01-01 10:00+00', '2031-01-01 10:00+00') AS zero,
       tstzrange('2031-01-01 10:00+00', '2031-01-01 10:00+00') && tstzrange('2031-01-01 09:00+00', '2031-01-01 12:00+00') AS sobrepoe;
 zero  | sobrepoe 
-------+----------
 empty | f
(1 row)
```

Ou seja: uma "reserva" das 10h às 10h passaria pela constraint, até no meio de uma reserva das 9h às 12h. A API não deixa ela chegar: o schema exige `ends_at` depois de `starts_at` desde o capítulo 1. Mas esta lição inteira é sobre não depender do balcão. Pelo `psql`, ela entraria.

O caso invertido, fim antes do começo, o próprio `tstzrange` já recusa:

```console
fairfare=# SELECT tstzrange('2031-01-01 12:00+00', '2031-01-01 10:00+00');
ERROR:  range lower bound must be less than or equal to range upper bound
```

Para fechar os dois de uma vez, entra uma segunda regra, bem mais simples. Um **check constraint**: uma condição que toda linha da tabela tem que cumprir.

```sql
CHECK (ends_at > starts_at)
```

### `gist` e `btree_gist`

Uma regra dessas precisa de um índice: a cada `INSERT`, o banco procura no índice alguma linha que colida. O btree da lição 06 não serve. Ele sabe **ordenar**, e "se sobrepõe" não é uma ordem. Quem sabe responder "quem se sobrepõe a este intervalo?" é outro tipo de índice, o **gist**.

Só que o gist, sozinho, não sabe comparar inteiros com `=`. Tentei criar a constraint num banco sem ajuda:

```console
ERROR:  data type integer has no default operator class for access method "gist"
HINT:  You must specify an operator class for the index or define a default operator class for the data type.
```

A ajuda é uma extensão que já vem com o PostgreSQL, a `btree_gist`. Ela ensina o gist a fazer o que o btree faz com tipos comuns, como o `=` do `resource_id`. Basta um `CREATE EXTENSION btree_gist` no banco.

## O model e a migração, à mão

No model, o índice da lição 06 sai e a constraint entra:

```python
class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        # "Um recurso não tem duas reservas no mesmo horário" — regra do banco, não do código
        # (lição 11). O autogenerate do Alembic não enxerga isto: a migração foi escrita à mão.
        ExcludeConstraint(
            ("resource_id", "="),
            (func.tstzrange(column("starts_at"), column("ends_at")), "&&"),
            name="bookings_sem_sobreposicao",
            using="gist",
        ),
        # Sem isto, uma reserva de duração zero vira um intervalo vazio, que não sobrepõe
        # nada, e escapa da regra de cima (lição 11).
        CheckConstraint("ends_at > starts_at", name="bookings_fim_depois_do_inicio"),
    )
```

Pedi a migração ao autogenerate, como na lição 06. Ele achou isto:

```console
INFO  [alembic.autogenerate.compare.constraints] Detected removed index 'ix_bookings_resource_id_starts_at' on 'bookings'
```

Viu o índice sumir. As duas regras novas, **não**. O autogenerate não compara `ExcludeConstraint`, nem `CheckConstraint`. *(Ele também quis apagar a tabela `bancada_reservas`, que as lições 08 e 09 criaram no banco de dev sem model nenhum. Joguei o arquivo fora.)*

Então a migração é escrita à mão:

```python
def upgrade() -> None:
    """Upgrade schema."""
    # btree_gist ensina o gist a comparar inteiros com "=" (o resource_id).
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # Escrita à mão: o autogenerate não enxerga ExcludeConstraint.
    op.create_exclude_constraint(
        "bookings_sem_sobreposicao",
        "bookings",
        ("resource_id", "="),
        (sa.func.tstzrange(sa.column("starts_at"), sa.column("ends_at")), "&&"),
        using="gist",
    )
    # Fecha a brecha do intervalo vazio: começo e fim iguais não sobrepõem nada.
    op.create_check_constraint("bookings_fim_depois_do_inicio", "bookings", "ends_at > starts_at")
    # O índice da constraint responde a pergunta do find_overlapping melhor que o btree
    # da lição 06 — desde que a consulta use &&. Dois índices para uma pergunta é desperdício.
    op.drop_index("ix_bookings_resource_id_starts_at", table_name="bookings")
```

O `downgrade` faz o caminho de volta: recria o btree e apaga as duas regras. A extensão fica, porque outro objeto do banco pode ter passado a depender dela.

Por que `func.tstzrange(column(...))` e não o SQL como texto, `text("tstzrange(starts_at, ends_at)")`? Porque o texto funciona no model e quebra na migração:

```console
sqlalchemy.exc.ArgumentError: Column must be constructed with a non-blank name or assign a non-blank .name before adding to a Table.
```

Se a migração é que cria a constraint, para que ela no model? Por dois motivos. Quem abre o model vê a regra ali, junto das colunas. E os testes não rodam migração: o `conftest.py` monta o `fairfare_test` com `create_all`, a partir dos models (lição 03). Sem a constraint no model, a suíte testaria um banco sem a regra. Por isso o `conftest.py` ganhou uma linha, antes do `create_all`:

```python
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
```

## A migração falha

```console
$ time uv run alembic upgrade head
...
sqlalchemy.exc.IntegrityError: (psycopg.errors.ExclusionViolation) could not create exclusion constraint "bookings_sem_sobreposicao"
DETAIL:  Key (resource_id, tstzrange(starts_at, ends_at))=(51, ["2030-06-01 10:00:00+00","2030-06-01 12:00:00+00")) conflicts with key (resource_id, tstzrange(starts_at, ends_at))=(51, ["2030-06-01 10:00:00+00","2030-06-01 12:00:00+00")).
[SQL: ALTER TABLE bookings ADD CONSTRAINT bookings_sem_sobreposicao EXCLUDE USING gist (resource_id WITH =, tstzrange(starts_at, ends_at) WITH &&)]

real	0m54.389s
```

Quadra 51, 1º de junho de 2030, 10h às 12h. Duas vezes. É a corrida da lição 07, que deixou duplicatas nas quadras 51 a 70 e que a lição 07 mandou não apagar. O banco se recusa a prometer uma regra que os dados de hoje já quebram.

E repare: nada mudou. O Alembic roda a migração numa transação, e a falha desfez tudo, a extensão inclusive.

### Achar as sobreposições

O `DETAIL` mostra só a primeira. Para ver todas, `bancada/sobreposicoes.sql`:

```sql
SELECT id, resource_id, user_id, starts_at, ends_at
FROM (
    SELECT *,
           max(ends_at) OVER (
               PARTITION BY resource_id ORDER BY starts_at, id
               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
           ) AS fim_das_anteriores
    FROM bookings
) b
WHERE fim_das_anteriores > starts_at
ORDER BY resource_id, starts_at;
```

O `OVER (...)` é uma **window function**: para cada linha, calcula algo sobre um grupo de linhas vizinhas, sem juntar tudo numa linha só como o `GROUP BY` faria. Aqui, para cada reserva, olha as anteriores **da mesma quadra** (`PARTITION BY resource_id`), em ordem de início, e pega o maior fim entre elas. Se esse fim passa do início da reserva atual, ela se sobrepõe a alguma anterior.

```console
$ B=chapters/04-o-banco-de-dados-de-verdade/bancada
$ docker compose exec -T postgres psql -U fairfare -d fairfare < $B/sobreposicoes.sql
   id    | resource_id | user_id |       starts_at        |        ends_at         
---------+-------------+---------+------------------------+------------------------
 1000002 |          51 |       2 | 2030-06-01 10:00:00+00 | 2030-06-01 12:00:00+00
 1000004 |          52 |       3 | 2030-06-01 10:00:00+00 | 2030-06-01 12:00:00+00
...
 1000067 |          70 |      21 | 2030-06-01 10:00:00+00 | 2030-06-01 12:00:00+00
(47 rows)
```

Quarenta e sete. Uma a mais em cada quadra de 51 a 61, quatro a mais em cada uma de 62 a 70. Bate com a lição 07.

### Quem fica é decisão sua

A consulta lista as reservas que sobrepõem uma **anterior**. Quem é "anterior" ela decide pelo início e, no empate, pelo `id`. Mas isso é só o critério da consulta. O banco não sabe qual das duas pessoas chegou primeiro **de verdade**. Talvez uma já tenha pagado. Talvez a outra tenha avisado os amigos. A migração não tem como saber, e por isso ela não tenta: ela para e devolve a decisão.

Aqui a decisão foi minha, e simples. São dados de teste, cada grupo tem o mesmo usuário e o mesmo horário. **Fica o menor `id` de cada quadra**, o primeiro a chegar ao `INSERT`. São justamente as 47 que a consulta lista:

```console
$ docker compose exec postgres psql -U fairfare -c "DELETE FROM bookings WHERE id IN (SELECT id FROM (SELECT id, starts_at, max(ends_at) OVER (PARTITION BY resource_id ORDER BY starts_at, id ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS fim_das_anteriores FROM bookings) b WHERE fim_das_anteriores > starts_at);"
DELETE 47
```

Num banco de produção, essa linha seria uma conversa com as pessoas, não um `DELETE`. De novo:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare < $B/sobreposicoes.sql
 id | resource_id | user_id | starts_at | ends_at 
----+-------------+---------+-----------+---------
(0 rows)

$ time uv run alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade 735b317a52e9 -> 257143851bec, reserva nao sobrepoe

real	0m51.008s

$ docker compose exec postgres psql -U fairfare -c '\d bookings'
...
Indexes:
    "bookings_pkey" PRIMARY KEY, btree (id)
    "bookings_sem_sobreposicao" EXCLUDE USING gist (resource_id WITH =, tstzrange(starts_at, ends_at) WITH &&)
Check constraints:
    "bookings_fim_depois_do_inicio" CHECK (ends_at > starts_at)
```

As duas regras estão lá, e o btree da lição 06 não.

### Cinquenta segundos de porta fechada

Por que 51 s, se o índice da lição 06 levou 7? Criar o gist em si é rápido: o mesmo índice, sem a regra, saiu em 2,6 s. O resto é a **conferência**. Para cada uma do milhão de linhas, o banco procura no índice outra que colida.

E, enquanto confere, a tabela fica fechada. Rodei a migração de novo e, no meio dela, um `SELECT` de uma linha:

```console
Time: 46222.798 ms (00:46.223)
```

Quarenta e seis segundos para ler **uma** reserva. O `ALTER TABLE ... ADD CONSTRAINT` pega o cadeado mais forte que existe, o `AccessExclusiveLock`, que barra até leitura. Num banco de dev, tudo bem. Em produção, seria quase um minuto de FairFare fora do ar. Migrações sem parar o app são assunto do capítulo 11.

## A tradução

Agora o banco recusa. Pelo app, a recusa chega no `commit()` do repository. Peguei a exceção com a sessão do próprio app, tentando gravar uma reserva por cima de outra:

```console
type(erro): IntegrityError
erro.orig.sqlstate: 23P01
str(erro) primeira linha: (sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) <class 'asyncpg.exceptions.ExclusionViolationError'>: conflicting key value violates exclusion constraint "bookings_sem_sobreposicao"
```

O `IntegrityError` do SQLAlchemy é genérico: chave estrangeira quebrada, `NOT NULL` violado, tudo vira ele. O que diz **qual** regra foi quebrada é o **SQLSTATE**, um código de cinco caracteres que o PostgreSQL manda junto com todo erro. `23P01` é "violou uma exclusion constraint". O SQLAlchemy guarda o erro do driver em `erro.orig`.

O repository traduz:

```python
# SQLSTATE do Postgres para "violou uma exclusion constraint".
EXCLUSION_VIOLATION = "23P01"


class BookingOverlapError(Exception):
    """O banco recusou a reserva: ela sobrepõe outra no mesmo recurso."""
```

```python
        self.db.add(booking)
        try:
            await self.db.commit()
        except IntegrityError as erro:
            await self.db.rollback()
            if getattr(erro.orig, "sqlstate", None) == EXCLUSION_VIOLATION:
                raise BookingOverlapError from erro
            raise
```

Depois de um `commit()` que falhou, a sessão fica num estado quebrado até alguém chamar `rollback()`. Por isso ele vem antes de tudo. E qualquer outro `IntegrityError` sobe como veio: o repository só traduz o que entende.

O service traduz de novo:

```python
        try:
            booking = await self.bookings.create(
                data.user_id, data.resource_id, data.starts_at, data.ends_at
            )
        except BookingOverlapError:
            # A verificação acima é o caminho rápido e educado; a garantia é do banco.
            # Quem perdeu a corrida passou pela verificação e foi barrado aqui.
            raise BookingConflictError
```

E o router não muda nada: `BookingConflictError` já virava `409` desde o capítulo 1.

O caminho inteiro:

```
asyncpg ExclusionViolationError
  → IntegrityError, sqlstate 23P01   (SQLAlchemy)
  → BookingOverlapError              (repository)
  → BookingConflictError             (service)
  → 409                              (router)
```

Por que duas exceções, e não o repository levantando `BookingConflictError` direto? A lição 09 do capítulo 1 já respondeu: cada camada fala a própria língua. O service não deve conhecer SQLSTATE nem driver. E o repository não pode importar uma exceção do service: o service importa o repository, e o import ficaria circular. Então o repository diz "o banco recusou" na língua dele, e o service decide o que isso significa para uma reserva.

## O cadeado sai

O diff desta lição **apaga** código. O `get_for_update` some do `ResourceRepository`, e o service volta ao `get` comum:

```python
        resource = await self.resources.get(data.resource_id)
```

A regra mudou de casa. O cadeado existia para impedir duas reservas sobrepostas, e isso agora é trabalho do banco, para **todo** caminho. Manter os dois seria pagar o custo da lição 10 (a fila por quadra, mesmo para horários que nem se tocam) sem ganhar garantia nenhuma.

## A verificação prévia fica

Se o banco garante, por que o `find_overlapping` continua no service?

Porque ele é o caminho **educado**. No caso comum, uma pessoa por vez, a verificação vê a reserva que já existe e responde `409` sem tentar gravar nada: sem exceção do driver, sem `rollback`. A constraint é a rede de segurança para quem passou pela verificação sem ver nada, que é exatamente quem perde uma corrida.

Dá para ver as duas trabalhando. O PostgreSQL registra cada violação no log dele. Depois de rodar a corrida da lição 07 (resultados na seção "A prova"), contei as violações de cada quadra:

| corrida | `409` no total | `409` vindos da constraint |
|---|---|---|
| N=10, 10 rodadas | 90 | 49 |
| N=5, 10 rodadas | 40 | 40 |

Com dez pessoas, a verificação barrou 41 e a constraint, 49. Com cinco, **todas** as perdedoras passaram pela verificação e foram barradas no `INSERT`. Sozinha, a verificação prévia não segura corrida nenhuma. Ela nunca segurou: é a lição 07.

## O índice que só serve à consulta escrita na forma dele

Volte à lição 06. O btree `(resource_id, starts_at)` lia **8772 entradas para achar 2**, em 3,3 ms, porque não sabia usar o `ends_at`. E ela prometeu um índice que entende intervalos. É o gist da constraint.

Antes de mexer no código, criei esse mesmo gist à mão, num índice temporário, e rodei o `explain.sql` da lição 06, com a consulta como o `find_overlapping` a escrevia:

```console
 Bitmap Heap Scan on bookings  (cost=602.81..8315.42 rows=5031 width=28) (actual time=5.075..8.795 rows=2.00 loops=1)
   Recheck Cond: (resource_id = 7)
   Filter: ((starts_at < '2031-01-01 12:00:00+00'::timestamp with time zone) AND (ends_at > '2031-01-01 10:00:00+00'::timestamp with time zone))
   Rows Removed by Filter: 19998
   Heap Blocks: exact=7353
   ->  Bitmap Index Scan on tmp_gist  (cost=0.00..601.55 rows=20435 width=0) (actual time=1.435..1.436 rows=20000.00 loops=1)
         Index Cond: (resource_id = 7)
 Execution Time: 9.114 ms
```

**Pior** que o btree. O `Index Cond` só tem o `resource_id`: o índice entregou as 20 000 reservas da quadra 7 inteira, e o filtro jogou 19 998 fora. Nove milissegundos.

O motivo: o gist guarda `tstzrange(starts_at, ends_at)`, uma **expressão**. O planejador só usa um índice de expressão quando a consulta contém **a mesma expressão**. `starts_at < 12h AND ends_at > 10h` quer dizer o mesmo que o `&&`, mas o planejador não faz essa conta. Para ele, são perguntas diferentes.

Então o `find_overlapping` muda de forma, para falar a língua do índice:

```python
        # Escrita na forma do índice da constraint (tstzrange &&): só assim o Postgres
        # consegue usá-lo de verdade. Mesma pergunta, outra forma (lição 11).
        stmt = select(Booking).where(
            Booking.resource_id == resource_id,
            func.tstzrange(Booking.starts_at, Booking.ends_at).op("&&")(
                func.tstzrange(starts_at, ends_at)
            ),
        )
```

O `.op("&&")` é como o SQLAlchemy escreve um operador que ele não conhece por nome. O SQL que sai:

```sql
WHERE bookings.resource_id = $1::INTEGER AND (tstzrange(bookings.starts_at, bookings.ends_at) && tstzrange($2::TIMESTAMP WITH TIME ZONE, $3::TIMESTAMP WITH TIME ZONE))
```

O `explain.sql` ganhou essa forma, ao lado da antiga. Antes de rodar, um `ANALYZE bookings;` no `psql`. O índice da constraint é sobre uma **expressão**, o `tstzrange(starts_at, ends_at)`, e o Postgres só tem estatísticas de uma expressão indexada depois de um `ANALYZE`. Sem elas, o planner chuta: escolhe um `Bitmap Heap Scan` estimando 194 linhas, e o plano sai diferente do de baixo (a conclusão é a mesma). Com a constraint criada e as estatísticas em dia, as duas formas, na mesma sessão:

```console
 Bitmap Heap Scan on bookings  (cost=586.76..8290.03 rows=4889 width=28) (actual time=5.256..8.762 rows=2.00 loops=1)
   ...
   ->  Bitmap Index Scan on bookings_sem_sobreposicao  (cost=0.00..585.54 rows=19901 width=0) (actual time=1.662..1.663 rows=20000.00 loops=1)
         Index Cond: (resource_id = 7)
 Execution Time: 9.071 ms

 Index Scan using bookings_sem_sobreposicao on bookings  (cost=0.29..16.35 rows=3 width=28) (actual time=0.038..0.060 rows=2.00 loops=1)
   Index Cond: ((resource_id = 7) AND (tstzrange(starts_at, ends_at) && '["2031-01-01 10:00:00+00","2031-01-01 12:00:00+00")'::tstzrange))
   Buffers: shared hit=7
 Execution Time: 0.066 ms
```

Agora o `Index Cond` tem as **duas** partes, e não existe mais `Filter`. O índice vai direto às 2 linhas: 7 páginas lidas no total, índice e tabela somados. Lado a lado:

| índice e forma da consulta | o índice entrega | tempo |
|---|---|---|
| btree, forma antiga (lição 06) | 8 772 | 3,3 ms |
| gist, forma antiga | 20 000 | 9,1 ms |
| gist, forma `&&` | 2 | 0,066 ms |

*(O btree mediu 3,6 ms nesta sessão, antes da migração. A lição 06 mediu 3,3.)*

E por isso o btree sai. Ele custava 30 MB, mais uma entrada a cada `INSERT`, para responder uma pergunta que o índice da constraint agora responde melhor. O gist ocupa 43 MB, e esse custo não é opcional: a regra precisa dele.

## A prova

```console
$ uv run pytest -q -W error
..............................                                           [100%]
30 passed in 2.80s
```

O teste do `monkeypatch` está verde, sem cadeado nenhum. As encostadas da lição 04 também.

E o teste de concorrência da lição 10, que precisou mudar. Sem o cadeado, um empate raro pode virar deadlock (o item do empate, em "O que fica declarado"), e aí as perdedoras saem com `500`, não com `409`. A versão da lição 10 exigia nove `409` exatos. Ela ia ficar vermelha de vez em quando, sem ninguém ter mexido em nada. E um teste assim ensina a ignorar o vermelho.

A versão nova exige o que a regra garante, e só isso:

```python
    criadas = [r for r in respostas if not isinstance(r, Exception) and r.status_code == 201]
    assert len(criadas) == 1
    for r in respostas:
        if isinstance(r, Exception):
            # Sob o pytest, o 500 chega como a própria exceção do app.
            assert isinstance(r, DBAPIError) and r.orig.sqlstate == DEADLOCK
        else:
            assert r.status_code in (201, 409)
    reservas = await client.get("/bookings")
    assert len(reservas.json()) == 1
```

Exatamente um `201`, exatamente uma reserva no banco, e toda perdedora recusada: por `409` ou por deadlock (SQLSTATE `40P01`). O `gather` ganhou um `return_exceptions=True`, porque sob o pytest o `500` não chega como resposta. Chega como a própria exceção do app, e sem isso ela derrubaria o teste antes da conferência. O `500` continua feio e continua declarado. O teste só não finge que ele não existe.

Em vinte execuções seguidas:

```console
$ for i in $(seq 1 20); do uv run pytest tests/test_concorrencia.py -q | tail -1; done | sed 's/ in .*//' | sort | uniq -c
     20 2 passed
```

No `fairfare_test`, a constraint veio do model, pelo `create_all`:

```console
$ docker compose exec postgres psql -U fairfare -d fairfare_test -c '\d bookings'
...
    "bookings_sem_sobreposicao" EXCLUDE USING gist (resource_id WITH =, tstzrange(starts_at, ends_at) WITH &&)
Check constraints:
    "bookings_fim_depois_do_inicio" CHECK (ends_at > starts_at)
```

E a reserva das 10h às 10h, agora pelo `psql`, que não passa pelo schema da API:

```console
ERROR:  new row for relation "bookings" violates check constraint "bookings_fim_depois_do_inicio"
DETAIL:  Failing row contains (1, 1, 1, 2031-01-01 10:00:00+00, 2031-01-01 10:00:00+00).
```

E a corrida, pelo uvicorn de verdade:

```console
$ uv run python $B/corrida.py --n 10 --rodadas 10
rodada  1: 201×1  409×9
rodada  2: 201×1  409×9
...
rodada 10: 201×1  409×9

rodadas com mais de uma reserva criada: 0/10
```

*(Cortei as rodadas do meio: todas iguais. Com `--n 5`, também 0/10.)* No log do uvicorn, as duas corridas somaram 150 `POST /bookings`: 20 `201`, 130 `409`, **nenhum** `500`. Nessas duas corridas, as 89 recusas da constraint viraram `409` pela tradução. Com mais gente ao mesmo tempo, não é sempre assim: veja o item do empate, em "O que fica declarado".

## O que fica declarado

- **A migração tranca a tabela** por quase um minuto, inclusive para leitura, num milhão de linhas. Migração sem parar o app: capítulo 11.
- **A limpeza das 47 duplicatas foi decisão minha**: fica o menor `id`. Num banco real, essa decisão é de gente, não de SQL.
- **O autogenerate não enxerga a constraint.** Quem mudar a `ExcludeConstraint` no model tem que escrever a migração à mão. Ele também tenta apagar a `bancada_reservas` do banco de dev: confira sempre o arquivo gerado.
- **Cada `409` vindo da constraint vira uma linha `ERROR` no log do PostgreSQL.** É o banco fazendo o trabalho dele, mas suja o log. Logs e o que merece alarme: capítulo 9.
- **Um empate de verdade pode terminar em `500`, e não em `409`.** Sem o cadeado, duas transações que gravam horários sobrepostos ao mesmo tempo podem ficar esperando **uma pela outra**. O PostgreSQL percebe o ciclo (um *deadlock*) e aborta uma delas com `deadlock detected`, SQLSTATE `40P01`. Isso não é `IntegrityError`, então o repository não traduz e o app responde `500`. Reproduzi. Com `--n 10` não apareceu, nem em 30 rodadas. Com `--n 30`, 2 de 10 rodadas terminaram em `201×1  500×29`. Repare: não foi uma perdedora, foram **todas** as daquela rodada. E a rodada levou quase meio minuto, contra uns 0,2 s das normais. O banco só procura o ciclo depois de um segundo de espera (o `deadlock_timeout`), e nessas rodadas as vítimas saíram uma a uma, mais ou menos uma por segundo. Atirando `INSERT`s direto no banco, 10 por vez em 200 rodadas, 108 de 2 000 deram deadlock. A regra continuou valendo: zero reservas duplicadas, em todas as rodadas. O que falha é a resposta. Tratar falha transitória com retry é assunto do capítulo 9.
- **A extensão `btree_gist` fica no banco** depois de um `downgrade`.
- **Os números são desta máquina, nesta sessão.** O índice temporário `tmp_gist` foi criado e apagado à mão; ele não está no repositório.

## O que você deve conseguir fazer agora

- Ler a constraint `bookings_sem_sobreposicao` em voz alta e explicar cada pedaço: `gist`, `=`, `tstzrange`, `&&`, `btree_gist`.
- Explicar por que reservas encostadas passam (o `[)`), e por que uma reserva de duração zero passaria, se não fosse o `CHECK`.
- Dizer por que uma migração dessas pode falhar num banco com dados, e por que a limpeza é decisão humana.
- Descrever o caminho de uma violação, do driver até o `409`, e dizer por que existem duas exceções no meio.
- Explicar por que o cadeado saiu e a verificação prévia ficou.
- Explicar por que o `find_overlapping` precisou mudar de forma para o índice servir.
