import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registra as tabelas no metadata)
from app.database import Base, get_db
from app.main import app as fastapi_app


@pytest.fixture()
async def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
