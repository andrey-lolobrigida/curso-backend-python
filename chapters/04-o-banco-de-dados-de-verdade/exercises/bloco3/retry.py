"""Bloco 3.1 — o retry no cadáver. (QUEBRADO DE PROPÓSITO)

Reserva com SERIALIZABLE, como na lição 09. Quando o banco aborta a transação, o código
tenta de novo. O problema é ONDE ele tenta de novo.
"""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

VERIFICA = text(
    "SELECT count(*) FROM bloco3_reservas "
    "WHERE resource_id = :r AND starts_at < :fim AND ends_at > :inicio"
)
INSERE = text(
    "INSERT INTO bloco3_reservas (resource_id, starts_at, ends_at) VALUES (:r, :inicio, :fim)"
)


def _abortada(erro: DBAPIError) -> bool:
    return getattr(erro.orig, "sqlstate", None) == "40001"  # serialization_failure


async def reservar(engine: AsyncEngine, recurso: int, inicio: datetime, fim: datetime) -> str:
    """Devolve "criada" ou "conflito"."""
    params = {"r": recurso, "inicio": inicio, "fim": fim}
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="SERIALIZABLE")
        for _ in range(5):
            try:
                if await conn.scalar(VERIFICA, params):
                    await conn.rollback()
                    return "conflito"
                await conn.execute(INSERE, params)
                await conn.commit()
                return "criada"
            except DBAPIError as erro:
                if _abortada(erro):
                    continue  # tenta de novo
                raise
    raise RuntimeError("cinco tentativas e nada")
