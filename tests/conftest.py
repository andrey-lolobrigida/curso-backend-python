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
        # A constraint de não-sobreposição (lição 11) precisa da extensão btree_gist.
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
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
    # O Starlette monta a pilha de middlewares na primeira chamada ao app (sob o uvicorn
    # é o lifespan; aqui, sem lifespan, é a primeira request) e a guarda aqui;
    # zerar força uma pilha nova (e um limitador de balde cheio) para cada teste.
    fastapi_app.middleware_stack = None

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
    await engine.dispose()
