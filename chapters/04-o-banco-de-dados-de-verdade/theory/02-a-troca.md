# Lição 02 — A troca

A lição 01 deixou um PostgreSQL de pé, vazio, esperando. O FairFare continuou falando com o `fairfare.db`, como se nada tivesse acontecido.

Nesta lição o app muda de banco. E a mudança, no código, cabe num punhado de linhas. A pergunta da lição: **o que precisa mudar para o mesmo app falar com um banco completamente diferente, e por que é tão pouco?**

## Duas URLs, como prometido

No capítulo 2, lição 08, o Alembic ficou síncrono de propósito, e o preço foi declarado ali mesmo:

> Quando o FairFare for para o PostgreSQL no capítulo 4, você não vai mexer numa string — vai mexer em duas, e elas precisam apontar para o mesmo banco (`postgresql+asyncpg://...` e `postgresql+psycopg://...`).

Chegou a hora de pagar. Mas antes de trocar as strings, vale entender o que é cada pedaço delas. Começando por uma palavra que até agora passou quieta: **driver**.

### O que é um driver

Pense num tradutor de embaixada. O diplomata (o SQLAlchemy) sabe o que quer dizer: "me traga as reservas da quadra 1". Mas ele não fala a língua do país. Quem fala é o tradutor. Troque de país, troque de tradutor. O diplomata continua o mesmo.

O rigor: o **SQLAlchemy não fala com banco nenhum sozinho**. Ele monta o SQL, cuida das sessões, transforma linhas em objetos. A conversa de verdade, os bytes indo e voltando, é de outra biblioteca: o **driver**. Cada banco tem o seu protocolo, e cada driver sabe um.

Você já usou dois sem prestar muita atenção:

- O `sqlite3`, que vem com o Python, e era o driver do capítulo 1.
- O `aiosqlite`, que entrou no capítulo 2. A lição 05 de lá contou o segredo dele: é o `sqlite3` de sempre rodando numa **thread de fundo**, com uma fachada `await`-ável. E a lição 10 completou: é uma solução legítima, só que "não é a mesma coisa que um driver de rede assíncrono".

Agora o FairFare ganha um driver de rede assíncrono de verdade. Dois, na verdade.

### Os dois drivers novos

**`asyncpg`**, para o app. Ele implementa o protocolo do PostgreSQL direto, sobre o próprio event loop do `asyncio`. Não tem thread escondida, não tem fachada. Quando o app espera o banco, a espera é um `await` numa conexão de rede, e o event loop fica livre para atender outra request. É o "async até o osso" que o capítulo 2 queria e o SQLite não podia dar.

**`psycopg`** (versão 3), para o Alembic. É o driver de PostgreSQL mais tradicional do Python, e ele fala síncrono, que é exatamente o que o Alembic quer. O `[binary]` no nome do pacote traz junto a `libpq` (a biblioteca oficial de cliente do PostgreSQL) já compilada. Sem ele, você precisaria ter a `libpq` instalada na máquina.

Instalando os dois:

```console
$ uv add asyncpg "psycopg[binary]"
(...)
 + asyncpg==0.31.0
 + psycopg==3.3.6
 + psycopg-binary==3.3.6
```

As aspas em volta de `psycopg[binary]` são para o shell não tentar interpretar os colchetes. O `pyproject.toml` ganha duas linhas:

```diff
 dependencies = [
     "aiosqlite>=0.22.1",
     "alembic>=1.18.5",
+    "asyncpg>=0.31.0",
     "email-validator>=2.3.0",
     "fastapi>=0.139.0",
+    "psycopg[binary]>=3.3.6",
     "sqlalchemy>=2.0.51",
     "uvicorn>=0.51.0",
 ]
```

Repare que o `aiosqlite` **fica**. O app não usa mais, mas os testes ainda usam: o `tests/conftest.py` sobe um SQLite em memória para cada teste. Isso tem consequência, e a consequência é a lição 03.

### Por que não um driver só?

Pergunta justa, e a resposta honesta é: daria. O `psycopg` 3 também tem um modo assíncrono, sem thread escondida. Com ele, a mesma URL `postgresql+psycopg://...` serviria para o app e para o Alembic, e a duplicação da lição 08 do capítulo 2 sumiria.

O curso fica com o `asyncpg` no app porque ele nasceu async, é o par mais comum do SQLAlchemy async, e todas as mensagens de erro deste capítulo foram medidas com ele. É uma escolha, não uma lei. O preço dela continua sendo o mesmo de antes, e continua declarado: duas strings que precisam apontar para o mesmo banco.

### A URL, pedaço por pedaço

```
postgresql+asyncpg://fairfare:fairfare@localhost:5432/fairfare
└───┬────┘ └──┬──┘   └──┬───┘ └──┬───┘ └───┬───┘ └┬─┘ └──┬───┘
 dialeto   driver    usuário   senha     host   porta  banco
```

- **`postgresql`** é o **dialeto**: o sabor de SQL que o SQLAlchemy deve gerar. Cada banco tem os seus detalhes, e o dialeto cuida deles.
- **`+asyncpg`** é o driver. É aqui, e só aqui, que as duas URLs diferem.
- **`fairfare:fairfare`** é usuário e senha. São os do `environment:` do `compose.yaml`. O cartório pedindo documento, lembra?
- **`localhost:5432`** é onde o servidor está. A porta é a do `ports:` do compose. Se você trocou para `5433` na lição 01, é aqui que troca também, **nas duas URLs**.
- **`/fairfare`** é o nome do banco, dentro do servidor. Um servidor PostgreSQL guarda vários bancos. Na lição 03 vai aparecer um segundo.

Compare com a URL antiga, `sqlite+aiosqlite:///fairfare.db`. Lá não tinha usuário, senha, host nem porta. Tinha um caminho de arquivo. É a lição 01 inteira numa linha: um arquivo não pergunta quem você é, e não mora do outro lado de rede nenhuma.

## O diff de `database.py`

Esta é a mudança no app. Inteira:

```diff
-DATABASE_URL = "sqlite+aiosqlite:///fairfare.db"
-
-# O Alembic continua síncrono, e por isso precisa da sua própria URL. A lição 08 explica.
-SYNC_DATABASE_URL = "sqlite:///fairfare.db"
+# O mesmo servidor, dois drivers: asyncpg para o app (async até o osso) e psycopg para
+# o Alembic, que continua síncrono. É a promessa da lição 08 do capítulo 2.
+DATABASE_URL = "postgresql+asyncpg://fairfare:fairfare@localhost:5432/fairfare"
+SYNC_DATABASE_URL = "postgresql+psycopg://fairfare:fairfare@localhost:5432/fairfare"
```

Duas strings e um comentário. O pool (`pool_size=5`, `max_overflow=10`, `pool_timeout=30`) ficou igual. O `alembic/env.py` também não mudou: ele já lia o `SYNC_DATABASE_URL` desde o capítulo 2, e continua lendo.

E o resto? Nenhum router, nenhum service, nenhum repository, nenhum model, nenhum schema. Lembra da lição 08 do capítulo 1, quando os repositories nasceram e pareciam burocracia? A justificativa veio em parcelas datadas, e uma delas era esta:

> **Capítulo 4:** SQLite dá lugar ao Postgres, e queries espertas (índices, locks) entram — tudo atrás do mesmo balcão.

A parcela foi paga com sobra. Desta vez nem o balcão precisou mudar. A troca aconteceu numa camada **abaixo** dele: o repository fala SQLAlchemy, e o SQLAlchemy fala com o driver que a URL mandar. O resto do app nem ficou sabendo.

## As três migrações num banco vazio

Banco novo, tabela nenhuma:

```console
$ docker compose exec postgres psql -U fairfare -c '\dt'
Did not find any tables.
```

O `\dt` é um comando do `psql` que lista as tabelas. Agora as migrações, as mesmas três de sempre:

```console
$ uv run alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 92b6a0b6e69f, usuarios e recursos
INFO  [alembic.runtime.migration] Running upgrade 92b6a0b6e69f -> 0d2bacd9919e, recurso ganha tipo
INFO  [alembic.runtime.migration] Running upgrade 0d2bacd9919e -> 4b1f163d18ea, reservas
```

Leia as duas primeiras linhas. `PostgresqlImpl`: o Alembic percebeu, pela URL, que agora está falando com um PostgreSQL. `transactional DDL`: no PostgreSQL, criar e alterar tabelas acontece dentro de uma transação. Se uma migração falhar no meio, nada dela fica pela metade. Transação é assunto da lição 08. Guarde só que o banco novo oferece isso até para mudanças de estrutura.

As três migrações foram escritas no capítulo 1, geradas pelo autogenerate contra um SQLite. E rodaram aqui **sem mudar uma vírgula**. Elas não têm SQL dentro: têm `op.create_table(...)`, `op.add_column(...)`, e cada dialeto traduz isso para o SQL do seu banco. É o Alembic fazendo, nas migrações, o mesmo trabalho que o SQLAlchemy faz nas queries.

Agora olhe o que ele criou:

```console
$ docker compose exec postgres psql -U fairfare -c '\d bookings'
                                         Table "public.bookings"
   Column    |            Type             | Collation | Nullable |               Default
-------------+-----------------------------+-----------+----------+--------------------------------------
 id          | integer                     |           | not null | nextval('bookings_id_seq'::regclass)
 user_id     | integer                     |           | not null |
 resource_id | integer                     |           | not null |
 starts_at   | timestamp without time zone |           | not null |
 ends_at     | timestamp without time zone |           | not null |
Indexes:
    "bookings_pkey" PRIMARY KEY, btree (id)
Foreign-key constraints:
    "bookings_resource_id_fkey" FOREIGN KEY (resource_id) REFERENCES resources(id)
    "bookings_user_id_fkey" FOREIGN KEY (user_id) REFERENCES users(id)
```

O `\d` descreve uma tabela. Quase tudo é o que você esperaria do model `Booking`: um `id` que se autonumera, as duas chaves estrangeiras, nada nulo.

E duas colunas com um tipo de nome comprido: **`timestamp without time zone`**. Horário **sem fuso**. Guarde esse nome. Ele vai aparecer de novo no fim desta lição, e ele é a lição 04 inteira.

## O `fairfare.db` virou peça de museu

O arquivo `fairfare.db` ainda está na raiz do projeto. O app não abre mais ele: nenhuma das duas URLs aponta para lá. Pode apagar.

```bash
rm fairfare.db
```

Ele nunca entrou no Git (o `.gitignore` tem uma linha `*.db` desde o capítulo 1), então apagar não deixa rastro no `git status`. Os dados que estavam lá dentro não vêm junto para o PostgreSQL. Eram dados de teste dos capítulos anteriores, e o banco novo começa limpo.

## O app sobe e funciona

Com o compose de pé (`docker compose up -d --wait`), suba o FairFare como sempre:

```bash
uv run uvicorn app.main:app --port 8000
```

E, em outro terminal, um usuário, um recurso e uma reserva:

```console
$ curl -s -X POST localhost:8000/users -H 'content-type: application/json' -d '{"nome":"Ana","email":"ana@example.com"}'
{"id":1,"nome":"Ana","email":"ana@example.com"}
$ curl -s -X POST localhost:8000/resources -H 'content-type: application/json' -d '{"nome":"Quadra 1","tipo":"quadra"}'
{"id":1,"nome":"Quadra 1","tipo":"quadra"}
$ curl -s -X POST localhost:8000/bookings -H 'content-type: application/json' -d '{"user_id":1,"resource_id":1,"starts_at":"2030-01-01T10:00:00","ends_at":"2030-01-01T12:00:00"}'
{"id":1,"user_id":1,"resource_id":1,"starts_at":"2030-01-01T10:00:00","ends_at":"2030-01-01T12:00:00","user_nome":"Ana","resource_nome":"Quadra 1"}
```

Três `201`. Mesmos corpos, mesmo formato, mesmos ids começando do 1. Do lado de fora, nada denuncia que o banco mudou. É isso que "o resto do app nem ficou sabendo" quer dizer na prática.

## O banco que grita

Agora a mesma reserva, um dia depois, só que dizendo o fuso. `-03:00` é o horário de Brasília:

```console
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/bookings -H 'content-type: application/json' -d '{"user_id":1,"resource_id":1,"starts_at":"2030-01-02T10:00:00-03:00","ends_at":"2030-01-02T12:00:00-03:00"}'
Internal Server Error
500
```

**500.** O `-w` do `curl` imprime o status depois do corpo, e o corpo é só a frase genérica, porque o FastAPI não conta detalhes de erro interno para o cliente. Os detalhes estão no terminal do uvicorn. O traceback real tem 173 linhas, quase todas de dentro do FastAPI, do Starlette e do SQLAlchemy. Cortei esses miolos e deixei as pontas, literais:

```console
INFO:     127.0.0.1:58006 - "POST /bookings HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "asyncpg/protocol/prepared_stmt.pyx", line 175, in asyncpg.protocol.protocol.PreparedStatementState._encode_bind_msg
  File "asyncpg/protocol/codecs/base.pyx", line 251, in asyncpg.protocol.protocol.Codec.encode
  File "asyncpg/protocol/codecs/base.pyx", line 153, in asyncpg.protocol.protocol.Codec.encode_scalar
  File "asyncpg/pgproto/codecs/datetime.pyx", line 152, in asyncpg.pgproto.pgproto.timestamp_encode
TypeError: can't subtract offset-naive and offset-aware datetimes

The above exception was the direct cause of the following exception:

(...)
asyncpg.exceptions.DataError: invalid input for query argument $2: datetime.datetime(2030, 1, 2, 12, 0, tzi... (can't subtract offset-naive and offset-aware datetimes)

(...)
  File "/home/andrey/PycharmProjects/python-backend-course/app/routers/bookings.py", line 20, in create_booking
    return await BookingService(db).create(data)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/andrey/PycharmProjects/python-backend-course/app/services/booking.py", line 37, in create
    overlapping = await self.bookings.find_overlapping(
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/andrey/PycharmProjects/python-backend-course/app/repositories/booking.py", line 43, in find_overlapping
    resultado = await self.db.scalars(stmt)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^
(...)
sqlalchemy.exc.DBAPIError: (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'asyncpg.exceptions.DataError'>: invalid input for query argument $2: datetime.datetime(2030, 1, 2, 12, 0, tzi... (can't subtract offset-naive and offset-aware datetimes)
[SQL: SELECT bookings.id, bookings.user_id, bookings.resource_id, bookings.starts_at, bookings.ends_at 
FROM bookings 
WHERE bookings.resource_id = $1::INTEGER AND bookings.starts_at < $2::TIMESTAMP WITHOUT TIME ZONE AND bookings.ends_at > $3::TIMESTAMP WITHOUT TIME ZONE]
[parameters: (1, datetime.datetime(2030, 1, 2, 12, 0, tzinfo=TzInfo(-10800)), datetime.datetime(2030, 1, 2, 10, 0, tzinfo=TzInfo(-10800)))]
(Background on this error at: https://sqlalche.me/e/20/dbapi)
```

Leia de baixo para cima, que é onde mora a história.

- **Onde quebrou.** No `find_overlapping`, o `SELECT` que procura reserva sobreposta antes de gravar. A reserva nem chegou a ser inserida. Um `GET /bookings` confirma: só a reserva `1` está lá.
- **Quem reclamou.** O `asyncpg`, antes mesmo de mandar a consulta para o servidor. Ele não conseguiu converter o argumento `$2` (o `ends_at`, `12:00` com `tzinfo=TzInfo(-10800)`, que é `-03:00` em segundos) para o tipo que a consulta pede.
- **Que tipo é esse.** Está escrito no SQL: `$2::TIMESTAMP WITHOUT TIME ZONE`. O nome que eu pedi para você guardar.

Não vou explicar ainda o que está acontecendo. Só quero que você repare numa coisa. Eu rodei o mesmo `curl`, com o mesmo corpo, contra o FairFare de ontem, o do SQLite (o commit da lição 01):

```console
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/bookings -H 'content-type: application/json' -d '{"user_id":1,"resource_id":1,"starts_at":"2030-01-02T10:00:00-03:00","ends_at":"2030-01-02T12:00:00-03:00"}'
{"id":2,"user_id":1,"resource_id":1,"starts_at":"2030-01-02T10:00:00","ends_at":"2030-01-02T12:00:00","user_nome":"Ana","resource_nome":"Quadra 1"}
201
```

**No SQLite isso dava 201.** No PostgreSQL dá 500. O código do app é o mesmo. O pedido é o mesmo. Só o banco mudou.

Então, qual dos dois está certo?

A resposta parece óbvia ("o que não quebra, ué"), e é exatamente aí que ela engana. Antes de responder, duas perguntas para você levar para as próximas lições:

1. Se o app quebra com um pedido tão comum, por que os testes não avisaram? Rode `uv run pytest -q` agora. Ele passa, verde, os 22. A lição 03 é sobre esse verde.
2. Compare as duas respostas do SQLite e do PostgreSQL com calma. O que o SQLite **fez** com o `-03:00` que você mandou? A lição 04 é sobre isso.

## O que fica declarado

- **O app dá 500 para horário com fuso.** É um defeito real do código desta lição, e não fica escondido: a lição 04 conserta.
- **Os testes ainda rodam no SQLite**, e por isso o `aiosqlite` continua nas dependências. A lição 03 move a suíte para o PostgreSQL e tira ele.
- **As URLs estão escritas no código**, com usuário e senha. Configuração por variável de ambiente e segredos de verdade são do capítulo 11.
- **Duas URLs, dois lugares para trocar**, como o capítulo 2 avisou. Se divergirem, o Alembic migra um banco e o app fala com outro.

## O que você deve conseguir fazer agora

- Explicar o que é um driver e por que o SQLAlchemy precisa de um.
- Explicar por que o FairFare tem duas URLs, uma com `asyncpg` e outra com `psycopg`, e dizer o que muda se uma delas apontar para outro banco.
- Ler uma URL de banco pedaço por pedaço: dialeto, driver, usuário, senha, host, porta, banco.
- Migrar um PostgreSQL vazio com `uv run alembic upgrade head` e conferir o resultado com `\dt` e `\d bookings`.
- Reproduzir o 500 com o `-03:00` e achar, no traceback, a linha do repository e o tipo `timestamp without time zone`.
