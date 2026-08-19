"""Bloco 2 — estender. Este arquivo não está quebrado: está lento.

A rota /painel precisa de duas consultas que não dependem uma da outra, e as
faz em série. Faça as duas acontecerem ao mesmo tempo, sem mudar nada do que
a rota devolve.
"""

import asyncio

from fastapi import FastAPI

app = FastAPI(title="bloco 2")


async def buscar_reservas() -> list[dict]:
    await asyncio.sleep(0.4)  # finge uma consulta ao banco
    return [{"id": 1, "recurso": "Quadra 1"}, {"id": 2, "recurso": "Chalé"}]


async def buscar_recursos() -> list[dict]:
    await asyncio.sleep(0.4)  # e esta não depende do resultado da outra
    return [{"id": 1, "nome": "Quadra 1"}, {"id": 2, "nome": "Chalé"}]


@app.get("/painel")
async def painel():
    reservas = await buscar_reservas()
    recursos = await buscar_recursos()
    return {"reservas": reservas, "recursos": recursos}
