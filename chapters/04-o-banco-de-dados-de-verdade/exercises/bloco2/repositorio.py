"""Bloco 2.1 — aquecimento. (FUNCIONA, MAS DO JEITO CARO)

O count() da lição 08 do capítulo 1 ("len da lista serve por enquanto") numa tabela grande.
"""

from sqlalchemy import Column, Integer, MetaData, Table, select
from sqlalchemy.ext.asyncio import AsyncConnection

metadata = MetaData()
reservas = Table(
    "bloco2_reservas",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("resource_id", Integer, nullable=False),
)


class ReservaRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def count(self) -> int:
        resultado = await self.conn.execute(select(reservas))
        return len(resultado.all())
