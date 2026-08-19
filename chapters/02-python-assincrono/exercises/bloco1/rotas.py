"""Bloco 1 — depurar. ATENÇÃO: este arquivo tem código quebrado DE PROPÓSITO.

Três rotas que deveriam atender várias pessoas ao mesmo tempo. Uma consegue.
Rode os testes, descubra quais rotas bloqueiam o event loop e conserte.

Antes de consertar, veja o número ruim com os seus próprios olhos:
    uv run uvicorn rotas:app --port 8200 --app-dir chapters/02-python-assincrono/exercises/bloco1
    uv run python chapters/02-python-assincrono/bancada/carga.py http://localhost:8200/lenta 5
"""

import asyncio
import time

from fastapi import FastAPI

app = FastAPI(title="bloco 1")

# Calibrado para ~0,1s na máquina do autor. Se aí o número for muito diferente,
# ajuste: o exercício quer um trecho de CPU de aproximadamente um décimo de segundo.
VOLTAS_DE_CPU = 3_000_000


@app.get("/rapida")
async def rapida():
    await asyncio.sleep(0.3)
    return {"rota": "rapida"}


@app.get("/lenta")
async def lenta():
    time.sleep(0.3)
    return {"rota": "lenta"}


@app.get("/misteriosa")
async def misteriosa():
    total = sum(i * i for i in range(VOLTAS_DE_CPU))
    time.sleep(0.3)
    return {"rota": "misteriosa", "total": total}
