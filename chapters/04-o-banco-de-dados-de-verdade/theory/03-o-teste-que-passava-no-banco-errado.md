# Lição 03 — O teste que passava no banco errado

A lição 02 terminou com uma pergunta incômoda. O app dá 500 para um pedido comum, e o `pytest` não avisou. Esta lição é sobre esse silêncio. A pergunta dela: **o que um teste verde garante, e onde?**

## O par que não fecha

Rode as duas coisas, uma atrás da outra, no código da lição 02:

```console
$ uv run pytest -q
......................                                                   [100%]
22 passed in 0.19s
```

```console
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/bookings -H 'content-type: application/json' -d '{"user_id":1,"resource_id":1,"starts_at":"2030-01-03T10:00:00-03:00","ends_at":"2030-01-03T12:00:00-03:00"}'
Internal Server Error
500
```

Vinte e dois testes verdes. E, no mesmo minuto, o app real quebrando. No terminal do uvicorn, o mesmo erro da lição 02, no mesmo lugar:

```console
asyncpg.exceptions.DataError: invalid input for query argument $2: datetime.datetime(2030, 1, 3, 12, 0, tzi... (can't subtract offset-naive and offset-aware datetimes)
```

Os dois não podem estar certos ao mesmo tempo. E não estão. Abra o `tests/conftest.py` da lição 02:

```python
engine = create_async_engine("sqlite+aiosqlite://")
```

A suíte inteira roda num SQLite em memória. O app, desde a lição 02, roda no PostgreSQL. **Os testes estão testando um banco que o app não usa mais.**

É como uma banda que ensaia com um violão emprestado e faz o show com uma guitarra. O ensaio foi ótimo. Só que o ensaio não diz nada sobre a guitarra. Se ela estiver desafinada, você descobre no palco.

No capítulo 1, lição 11, a gente comemorou que trocar o banco dos testes custava uma linha. Continua custando. O que ninguém disse é o que essa linha esconde quando os dois bancos são **produtos diferentes**.

## O que o SQLite escondia

Escrevi um teste que diz o que o FairFare **deveria** fazer, em `tests/test_fuso.py`:

```python
async def test_mesmo_instante_em_fusos_diferentes_conflita(client):
    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    primeira = await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T10:00:00-03:00", "2030-01-01T12:00:00-03:00"
    )
    assert primeira.status_code == 201
    # 13:00 em UTC é 10:00 em São Paulo: o mesmo instante, a mesma quadra.
    segunda = await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T13:00:00Z", "2030-01-01T15:00:00Z"
    )
    assert segunda.status_code == 409
```

Duas reservas para a mesma quadra. A primeira às 10h de Brasília. A segunda às 13h em UTC (o `Z` no fim quer dizer UTC). São **o mesmo instante**, escritos de dois jeitos. A segunda tem que dar `409`, conflito.

*(O código acima é o teste sem a marca que ele vai ganhar daqui a pouco. Ele não ficou assim no repositório.)*

Rodei esse teste contra o conftest antigo, o do SQLite:

```console
$ uv run pytest -q tests/test_fuso.py
(...)
>       assert segunda.status_code == 409
E       assert 201 == 409
E        +  where 201 = <Response [201 Created]>.status_code

tests/test_fuso.py:17: AssertionError
(...)
1 failed in 0.07s
```

**201 e 201.** O SQLite aceitou a reserva dupla: guardou os horários sem fuso, comparou `10:00` com `13:00` e não viu sobreposição. O porquê exato é a lição 04.

No SQLite, o app erra **em silêncio**. No PostgreSQL, ele grita. Mesmo código, dois comportamentos, e os testes só viam um.

Daí a frase desta lição:

> **Um teste só garante alguma coisa no banco onde ele roda.**

E o fuso é só o primeiro caso. O SQLite não tem `SELECT ... FOR UPDATE` (o "tranca essa linha para mim"), e o SQLAlchemy, falando com ele, simplesmente tira a cláusula da consulta, sem avisar. Não tem `EXCLUDE` (uma regra que o próprio banco impõe, como "reservas da mesma quadra não se sobrepõem"). E serializa as escritas, uma de cada vez. Os três são assunto deste capítulo, e nenhum teste no SQLite enxerga nenhum deles.

Então a suíte vai para o PostgreSQL.

## O `fairfare_test`

Em **qual** PostgreSQL? Não no `fairfare`, onde moram os dados do seu `curl`: um teste que apaga tudo antes de rodar não pode morar lá.

A lição 02 disse que um servidor guarda vários bancos. É hora do segundo: o `fairfare_test`.

O novo `tests/conftest.py`, inteiro:

```python
import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  (registra as tabelas no metadata)
from app.database import Base, get_db
from app.main import app as fastapi_app

# O mesmo servidor do compose.yaml, outro banco: o pytest nunca toca no fairfare.
ADMIN_URL = "postgresql+psycopg://fairfare:fairfare@localhost:5432/postgres"
TEST_DB = "fairfare_test"
SYNC_TEST_URL = f"postgresql+psycopg://fairfare:fairfare@localhost:5432/{TEST_DB}"
TEST_URL = f"postgresql+asyncpg://fairfare:fairfare@localhost:5432/{TEST_DB}"


@pytest.fixture(scope="session", autouse=True)
def banco_de_testes():
    """Uma vez por rodada do pytest: o fairfare_test existe e tem as tabelas dos models."""
    # CREATE DATABASE não roda dentro de transação; daí o AUTOCOMMIT.
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            existe = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :nome"), {"nome": TEST_DB}
            )
            if not existe:
                conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    except OperationalError:
        pytest.exit(
            "Não achei o PostgreSQL em localhost:5432. Suba o banco: docker compose up -d --wait",
            returncode=1,
        )
    finally:
        admin.dispose()

    engine = create_engine(SYNC_TEST_URL)
    with engine.begin() as conn:
        # Do zero a cada rodada: se um model mudou, o banco de testes muda junto.
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
    engine.dispose()


@pytest.fixture()
async def client():
    # Uma engine por teste: conexões do asyncpg pertencem ao event loop que as criou,
    # e o pytest-asyncio dá um loop novo a cada teste.
    engine = create_async_engine(TEST_URL)
    async with engine.begin() as conn:
        # Limpa ANTES, não depois: se um teste falhar, o estado dele fica no banco
        # para você olhar com o psql.
        await conn.execute(text("TRUNCATE users, resources, bookings RESTART IDENTITY CASCADE"))
    TestingSession = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def override_get_db():
        async with TestingSession() as db:
            yield db

    fastapi_app.dependency_overrides[get_db] = override_get_db

    # O rate limiter guarda os baldes em memória — no processo do pytest também.
    # (...) o mesmo comentário e a mesma linha do capítulo 3
    fastapi_app.middleware_stack = None

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
    await engine.dispose()
```

*(Cortei o comentário do rate limiter com `(...)`. Ele é o mesmo de antes, palavra por palavra.)*

Primeiro, a fixture `banco_de_testes`. A `client` vem nas próximas seções.

**Três URLs.** `TEST_URL` (`asyncpg`) para os testes, `SYNC_TEST_URL` (`psycopg`) para o trabalho síncrono. A `ADMIN_URL` aponta para o banco `postgres`, que vem vazio de fábrica em todo servidor justamente para isto: você não consegue se conectar no `fairfare_test` para criar o `fairfare_test`.

**`scope="session", autouse=True`.** Roda uma vez por rodada do `pytest`, antes do primeiro teste, sem nenhum teste pedir.

**Por que o conftest cria o banco.** O jeito "Docker" seria um `CREATE DATABASE` num script em `/docker-entrypoint-initdb.d/`. Só que esse script **só roda com o volume vazio**. O seu volume tem dados desde a lição 01: o script nunca rodaria para você, e nada avisaria. O conftest pergunta ao servidor (`pg_database` é a lista de bancos dele) e cria se faltar. Funciona para quem clonou hoje e para quem vinha acompanhando.

**`AUTOCOMMIT`.** O SQLAlchemy abre uma transação antes de cada comando, e o PostgreSQL se recusa a rodar `CREATE DATABASE` dentro de uma. Com `AUTOCOMMIT`, cada comando vale sozinho. Transação de verdade é a lição 08.

**`drop_all` + `create_all`.** Uma vez por rodada, as tabelas renascem dos models. Mudou um model, o banco de testes acompanha. Sem migração, pelo motivo da lição 11 do capítulo 1: banco de teste não tem dados a preservar.

## Limpar entre testes

Antes, cada teste ganhava um SQLite novo em memória. Agora o banco é um só e sobrevive entre os testes. Sem limpeza, a `ana@example.com` do primeiro teste ainda estaria lá no segundo.

A limpeza é uma linha:

```sql
TRUNCATE users, resources, bookings RESTART IDENTITY CASCADE
```

- **`TRUNCATE`** esvazia as tabelas de uma vez, em vez de apagar linha por linha como um `DELETE`.
- **`RESTART IDENTITY`** zera os contadores de `id`, para os testes que esperam `id` 1.
- **`CASCADE`** leva junto o que depende dessas tabelas por chave estrangeira.

**Por que antes, e não depois?** Se um teste falha, o estado dele fica no banco para você olhar com o `psql`. Limpar no fim apagaria a cena do crime. E não importa como a rodada anterior terminou: o teste sempre começa do zero.

E o custo? A alternativa óbvia é `drop_all` + `create_all` por teste. Medi as duas, oito rodadas de cada, intercaladas (com a máquina sob carga variável, rodadas isoladas não se comparavam):

| Estratégia por teste | Suíte inteira (mediana) | Preparação de cada teste (mediana) |
|---|---|---|
| `TRUNCATE` | ~1,25 s | ~20 ms |
| `drop_all` + `create_all` | ~1,47 s | ~30 ms |

A diferença é pequena com três tabelas, e tende a crescer com mais tabelas (isso eu não medi). O `TRUNCATE` é a ferramenta feita para isto: o esquema fica, só o conteúdo vai embora.

Há uma estratégia mais fina, com cada teste dentro de uma transação desfeita no fim. Ela fica para o capítulo 10, sobre estratégia de testes.

## Uma engine por teste

A `create_async_engine(TEST_URL)` mora **dentro** da fixture `client`: cada teste cria a sua e a descarta no fim. Por que não uma só, no topo do módulo?

Eu tentei:

```console
$ uv run pytest -q
.EEEx....EEEEEEEEEEEEEE                                                  [100%]
(...)
E   RuntimeError: Task <Task pending name='Task-8' coro=<...>> got Future <Future pending cb=[BaseProtocol._on_waiter_completed()]> attached to a different loop
(...)
E   asyncpg.exceptions._base.InterfaceError: cannot perform operation: another operation is in progress
(...)
5 passed, 1 xfailed, 17 errors in 2.88s
```

*(Esse conftest com engine única foi um experimento meu. Ele não está no repositório. Na saída, encurtei com `<...>` a descrição da tarefa, que tem caminhos da minha máquina.)*

O primeiro teste passou. O segundo morreu com `attached to a different loop`. Daí em diante, quase todos com `another operation is in progress`.

Uma conexão do `asyncpg` é uma conversa de rede que **pertence ao event loop que a abriu**: é nele que ela espera as respostas do servidor. E o `pytest-asyncio` dá um loop novo a cada teste. O primeiro teste abriu conexões no loop 1 e as devolveu ao pool. O segundo, no loop 2, pegou uma delas e tentou conversar por um loop que já não existia: `different loop`. E a conexão, quebrada no meio de uma operação, voltou ao pool e envenenou quase todo teste que a pegou depois.

Com uma engine por teste, o pool nasce e morre com o loop, e a suíte final não mostra nenhum desses erros. Nem precisei do `NullPool` (um pool que não guarda conexões), meu plano B.

## O teste que falha de propósito

Agora, o teste do fuso. Com a suíte no PostgreSQL, rodei ele de novo, sem marca nenhuma:

```console
$ uv run pytest -q tests/test_fuso.py
(...)
E   sqlalchemy.exc.DBAPIError: (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'asyncpg.exceptions.DataError'>: invalid input for query argument $2: datetime.datetime(2030, 1, 1, 12, 0, tzi... (can't subtract offset-naive and offset-aware datetimes)
E   [SQL: SELECT bookings.id, bookings.user_id, bookings.resource_id, bookings.starts_at, bookings.ends_at
E   FROM bookings
E   WHERE bookings.resource_id = $1::INTEGER AND bookings.starts_at < $2::TIMESTAMP WITHOUT TIME ZONE AND bookings.ends_at > $3::TIMESTAMP WITHOUT TIME ZONE]
(...)
1 failed in 0.49s
```

*(Tirei a indentação das linhas `E`. O resto é literal.)*

É o `DataError` da lição 02, no mesmo `find_overlapping`, no mesmo `$2`, e agora já na **primeira** reserva, a do `-03:00`. O teste não recebe um `500`: o `ASGITransport` repassa a ele a exceção que escapou do app.

O teste está certo, o app está errado, e o conserto é a lição 04. O que fazer com um teste vermelho até lá? Apagar é perder a informação. Deixar vermelho é treinar todo mundo a ignorar vermelho. O pytest tem uma terceira opção:

```python
@pytest.mark.xfail(
    strict=True,
    reason="o fuso ainda é descartado; no Postgres vira 500 (conserto: lição 04)",
)
async def test_mesmo_instante_em_fusos_diferentes_conflita(client):
    ...
```

**`xfail`** quer dizer *expected to fail*. O teste roda. Se falhar, conta como `xfailed`, e a suíte segue verde. O `reason` é a nota para quem vier depois.

E o **`strict=True`** é o que torna isso honesto. Sem ele, se um dia o teste começar a passar, o pytest só comenta (`xpassed`) e segue. Com ele, um teste marcado que **passa** vira uma falha da suíte. Testei num arquivo descartável, com o mesmo `reason`, e um teste que sempre passa:

```console
FAILED test_xp.py::test_x - [XPASS(strict)] o fuso ainda é descartado; no Pos...
1 failed in 0.00s
```

Na lição 04, quando o fuso for consertado, este teste vai passar, e a suíte vai **ficar vermelha** até alguém remover a marca. Ela não tem como ficar esquecida, mentindo que o defeito existe. É a política de limitações declaradas, escrita dentro do próprio código, com o pytest vigiando.

Um detalhe: o `xfail` aceita **qualquer** falha. No SQLite seria o `assert`, no PostgreSQL é a exceção, e os dois contam como `xfailed`. O que importa aqui é o dia em que o teste passar, e isso o `strict=True` pega.

A suíte, no PostgreSQL, com `-W error` (que transforma qualquer aviso em erro, para nada passar escondido):

```console
$ uv run pytest -q -W error
....x..................                                                  [100%]
22 passed, 1 xfailed in 1.58s
```

*(Uma rodada isolada varia: nesta máquina vi de ~1,1 s a ~1,6 s. A tabela da limpeza usa medianas.)*

Aquele `x` no meio dos pontos é o teste do fuso. Vinte e dois verdes, agora no banco certo, e um vermelho declarado.

## Sem o banco de pé

A suíte agora depende de um servidor. Esqueça de subir o compose:

```console
$ docker compose stop
$ uv run pytest -q

no tests ran in 0.37s
! _pytest.outcomes.Exit: Não achei o PostgreSQL em localhost:5432. Suba o banco: docker compose up -d --wait !
```

Uma linha, que diz o que fazer, sem traceback do driver. É o `except OperationalError` da fixture de sessão: `OperationalError` é a exceção do SQLAlchemy para problema de operação (servidor fora do ar, conexão recusada), não do seu SQL. O `pytest.exit` encerra a rodada com código 1, para um script ou CI saberem que deu errado.

Para voltar:

```bash
docker compose up -d --wait
```

## O `aiosqlite` foi para o `dev`

O app não usa mais o `aiosqlite`, mas a bancada do capítulo 2 (`bancada/lazy_load.py`) ainda usa. Ele sai das dependências do app e vai para o grupo `dev`, o que o `uv` instala para quem desenvolve, mas o app não precisa para rodar:

```bash
uv remove aiosqlite && uv add --dev aiosqlite
```

A lição 02 disse que esta lição "tira" o `aiosqlite`. Tira do app, não do projeto.

Uma arrumação, que você vai ver no diff: os atalhos `_cria_usuario`, `_cria_recurso` e `_cria_reserva` saíram do topo de `test_smoke.py` para `tests/apoio.py`, sem o `_`, porque o `test_fuso.py` também usa. Nenhum teste mudou de comportamento.

## O que fica declarado

- **O fuso continua quebrado.** O app dá 500 para horário com fuso, e o teste do fuso está marcado `xfail(strict=True)`. Conserto: lição 04.
- **A suíte precisa do compose de pé.** Sem ele, nenhum teste roda.
- **O banco de testes é recriado com `create_all`, não com as migrações.** Se uma migração divergir dos models, os testes não percebem. Hoje elas batem; é uma limitação a lembrar.
- **As URLs do banco de testes também estão escritas no código.** Configuração por variável de ambiente: capítulo 11.
- **Limpeza por `TRUNCATE`, não por transação.** A estratégia mais fina fica para o capítulo 10.

## O que você deve conseguir fazer agora

- Explicar por que um teste verde no SQLite não diz nada sobre o PostgreSQL, usando o teste do fuso (201 e 201 num, `DataError` no outro).
- Rodar a suíte contra o `fairfare_test` com o compose de pé, e reconhecer a mensagem de quando ele não está.
- Explicar por que o conftest cria o `fairfare_test` em vez de um script no `docker-entrypoint-initdb.d`, e por que precisa de `AUTOCOMMIT`.
- Explicar por que a limpeza acontece antes de cada teste, e o que o `RESTART IDENTITY` evita.
- Explicar por que cada teste tem a sua engine.
- Dizer o que `strict=True` faz num `xfail`, e o que vai acontecer com este teste na lição 04.
