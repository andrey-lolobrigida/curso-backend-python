import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  (registra as tabelas no metadata)
from app.database import Base, get_db
from app.main import app as fastapi_app
from tests.apoio import Pessoa, cria_usuario, faz_login

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
        # A constraint de não-sobreposição (lição 11) precisa da extensão btree_gist.
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        # Do zero a cada rodada: se um model mudou, o banco de testes muda junto.
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
    engine.dispose()


@pytest.fixture()
async def engine_de_teste():
    # Uma engine por teste: conexões do asyncpg pertencem ao event loop que as criou,
    # e o pytest-asyncio dá um loop novo a cada teste.
    engine = create_async_engine(TEST_URL)
    async with engine.begin() as conn:
        # Limpa ANTES, não depois: se um teste falhar, o estado dele fica no banco
        # para você olhar com o psql.
        await conn.execute(
            text(
                "TRUNCATE users, resources, bookings, groups, group_members, expenses, expense_shares, settlements, sessions RESTART IDENTITY CASCADE"
            )
        )
    yield engine
    await engine.dispose()


@pytest.fixture()
async def client(engine_de_teste):
    TestingSession = async_sessionmaker(bind=engine_de_teste, expire_on_commit=False)

    async def override_get_db():
        async with TestingSession() as db:
            yield db

    fastapi_app.dependency_overrides[get_db] = override_get_db

    # O rate limiter guarda os baldes em memória — no processo do pytest também.
    # O Starlette monta a pilha de middlewares na primeira chamada ao app (sob o uvicorn
    # é o lifespan; aqui, sem lifespan, é a primeira request) e a guarda aqui;
    # zerar força uma pilha nova (e um limitador de balde cheio) para cada teste.
    fastapi_app.middleware_stack = None

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
async def pessoa(client):
    """Fábrica de pessoas logadas: `ana = await pessoa("Ana")`.

    Depende do `client` para os dependency_overrides e o limitador zerado já estarem montados.
    Cada pessoa ganha um AsyncClient próprio, com IP próprio (10.0.0.1, 10.0.0.2, ...): o
    próprio balde no rate limiter. Com um IP só, cadastro + login de cada pessoa somados às
    requests do teste podem passar das 20 fichas (no ensaio do spike, um teste levou 429;
    lição 05 do cap. 6). Nenhuma pessoa usa o 127.0.0.1 do `client` anônimo.
    """
    clientes = []

    async def nova(nome: str = "Ana", email: str | None = None) -> Pessoa:
        email = email or f"{nome.lower()}@example.com"
        ip = f"10.0.0.{len(clientes) + 1}"
        transport = ASGITransport(app=fastapi_app, client=(ip, 123))
        cliente = AsyncClient(transport=transport, base_url="http://test")
        clientes.append(cliente)
        dados = await cria_usuario(cliente, email=email, nome=nome)
        token = await faz_login(cliente, email)
        cliente.headers["Authorization"] = f"Bearer {token}"
        return Pessoa(id=dados["id"], nome=dados["nome"], email=dados["email"], client=cliente)

    yield nova
    for cliente in clientes:
        await cliente.aclose()
