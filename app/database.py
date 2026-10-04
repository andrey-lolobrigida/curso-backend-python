from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# O mesmo servidor, dois drivers: asyncpg para o app (async até o osso) e psycopg para
# o Alembic, que continua síncrono. É a promessa da lição 08 do capítulo 2.
DATABASE_URL = "postgresql+asyncpg://fairfare:fairfare@localhost:5432/fairfare"
SYNC_DATABASE_URL = "postgresql+psycopg://fairfare:fairfare@localhost:5432/fairfare"

engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,  # conexões mantidas abertas
    max_overflow=10,  # extras sob pico, descartadas depois
    pool_timeout=30,  # segundos esperando uma conexão livre antes de estourar
)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as db:
        yield db
