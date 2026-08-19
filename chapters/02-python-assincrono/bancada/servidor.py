"""Bancada: dois endpoints idênticos, uma diferença de três letras.

Instrumento de medição do capítulo 2. Não faz parte do FairFare.
"""

import time

from fastapi import FastAPI

app = FastAPI(title="bancada")


@app.get("/sync")
def rota_sync():
    time.sleep(1)  # finge um I/O lento: banco, rede, disco
    return {"ok": "sync"}


@app.get("/async-bloqueante")
async def rota_async_bloqueante():
    time.sleep(1)  # o MESMO sleep — e é aqui que o mundo para
    return {"ok": "async-bloqueante"}
