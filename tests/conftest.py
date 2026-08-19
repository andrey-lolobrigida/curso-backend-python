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
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
    await engine.dispose()
