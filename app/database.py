from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///fairfare.db"

# O Alembic continua síncrono, e por isso precisa da sua própria URL. A lição 08 explica.
SYNC_DATABASE_URL = "sqlite:///fairfare.db"

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
