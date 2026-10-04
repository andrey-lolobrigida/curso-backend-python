"""Bloco 2.2 — o vazamento. (QUEBRADO DE PROPÓSITO)

Um app mínimo com o mesmo pool do FairFare (5 + 10), só que com pool_timeout curto,
para o problema aparecer em segundos e não em meio minuto.
"""

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

URL = "postgresql+asyncpg://fairfare:fairfare@localhost:5432/fairfare_test"

engine = create_async_engine(URL, pool_size=5, max_overflow=10, pool_timeout=2)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

app = FastAPI()


async def get_db():
    db = SessionLocal()
    yield db


@app.get("/agora")
async def agora(db: AsyncSession = Depends(get_db)):
    return {"agora": str(await db.scalar(text("SELECT now()")))}
