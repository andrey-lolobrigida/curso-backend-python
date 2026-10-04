"""Bloco 3.2 — o deadlock das duas quadras. (QUEBRADO DE PROPÓSITO)

Operação de bancada: reservar duas quadras juntas, para um torneio que usa as duas.
Ela tranca as duas linhas com FOR UPDATE, na ordem em que o cliente mandou.
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

TRANCA = text("SELECT id FROM bloco3_quadras WHERE id = :id FOR UPDATE")


async def reservar_par(engine: AsyncEngine, quadras: tuple[int, int]) -> None:
    async with engine.begin() as conn:
        for quadra in quadras:
            await conn.execute(TRANCA, {"id": quadra})
            await asyncio.sleep(0.01)  # o tempo de olhar a agenda de cada quadra
        # (aqui entrariam a verificação e os inserts; o que importa neste bloco são os locks)
