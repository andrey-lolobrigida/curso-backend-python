"""Bancada: o erro que espera todo mundo que usa relações no SQLAlchemy async.

Este script FALHA de propósito. O objetivo é você reconhecer a mensagem —
no capítulo 5, quando as relações chegarem ao FairFare, ela vai aparecer.

Rode: uv run python chapters/02-python-assincrono/bancada/lazy_load.py
"""

import asyncio

from sqlalchemy import ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Dono(Base):
    __tablename__ = "donos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]


class Coisa(Base):
    __tablename__ = "coisas"

    id: Mapped[int] = mapped_column(primary_key=True)
    dono_id: Mapped[int] = mapped_column(ForeignKey("donos.id"))
    dono: Mapped[Dono] = relationship()


async def main() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as db:
        db.add(Coisa(dono=Dono(nome="Ana")))
        await db.commit()

        coisa = (await db.scalars(select(Coisa))).first()
        print("carreguei a coisa. agora vou tocar em coisa.dono, que não foi carregado:")
        print(coisa.dono.nome)  # <- estoura aqui


asyncio.run(main())
