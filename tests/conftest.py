import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  (registra as tabelas no metadata)
from app.database import Base, get_db
from app.main import app as fastapi_app


@pytest.fixture()
async def client():
    engine = create_async_engine("sqlite+aiosqlite://")
    TestingSession = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
