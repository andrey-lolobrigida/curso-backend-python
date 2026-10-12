"""Bloco 3.1 — o extrato pela metade. (QUEBRADO DE PROPÓSITO)

Lança um extrato inteiro: várias linhas que só fazem sentido juntas.
"""

from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Lancamento(Base):
    __tablename__ = "bloco3_extrato"

    id: Mapped[int] = mapped_column(primary_key=True)
    descricao: Mapped[str] = mapped_column(String(100))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))


async def lancar_extrato(
    engine: AsyncEngine, linhas: list[tuple[str, Decimal]], falhar_na: int | None = None
) -> None:
    """Grava todas as linhas do extrato, ou nenhuma.

    `falhar_na` é o índice de uma linha em que o teste força uma falha, no papel da
    conexão que cai ou do processo que morre no meio do caminho.

    EXERCÍCIO 3.1: esta função tem um defeito de propósito. O teste mostra qual.
    """
    async with AsyncSession(engine) as db:
        for i, (descricao, valor) in enumerate(linhas):
            if i == falhar_na:
                raise RuntimeError(f"falha simulada na linha {i}")
            db.add(Lancamento(descricao=descricao, valor=valor))
            await db.commit()
