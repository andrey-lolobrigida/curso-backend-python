"""Bloco 1 — depurar. ATENÇÃO: este arquivo tem código quebrado DE PROPÓSITO.

Um FairFare de brinquedo com CORS e rate limit. Dois defeitos, de naturezas
diferentes. Os testes dizem quais. Antes de abrir o código, veja a dor:

    uv run uvicorn servidor:app --port 8200 --app-dir chapters/03-entre-o-cliente-e-o-router/exercises/bloco1
    uv run python chapters/03-entre-o-cliente-e-o-router/bancada/carga.py http://localhost:8200/users 10
    sleep 3
    uv run python chapters/03-entre-o-cliente-e-o-router/bancada/carga.py http://localhost:8200/users 10
"""

import math
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


class RelogioFalso:
    """Segue o time.monotonic até alguém mandar o tempo andar; daí em diante, só anda quando mandam.

    (Parte do monotonic real, e não de zero, para o tempo fingido nunca ficar ATRÁS do
    instante em que um balde foi criado — senão a recarga sairia negativa.)
    """

    def __init__(self) -> None:
        self.agora: float | None = None

    def __call__(self) -> float:
        return time.monotonic() if self.agora is None else self.agora

    def avancar(self, segundos: float) -> None:
        self.agora = self() + segundos


RELOGIO = RelogioFalso()


class RateLimitMiddleware:
    def __init__(
        self, app, capacidade: int = 5, recarga_por_segundo: float = 1.0, relogio=RELOGIO
    ) -> None:
        self.app = app
        self.capacidade = capacidade
        self.recarga_por_segundo = recarga_por_segundo
        self.relogio = relogio
        self.baldes: dict[str, tuple[float, float]] = {}

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        cliente = scope["client"][0] if scope.get("client") else "desconhecido"
        espera = self._consumir_ficha(cliente)
        if espera > 0:
            await self._recusar(send, espera)
            return
        await self.app(scope, receive, send)

    def _consumir_ficha(self, cliente: str) -> float:
        agora = self.relogio()
        fichas, ultimo = self.baldes.get(cliente, (float(self.capacidade), agora))
        if agora < ultimo:  # "só recarrega se o tempo andou"
            fichas = min(self.capacidade, fichas + (agora - ultimo) * self.recarga_por_segundo)
        if fichas >= 1:
            self.baldes[cliente] = (fichas - 1, agora)
            return 0.0
        self.baldes[cliente] = (fichas, agora)
        return (1 - fichas) / self.recarga_por_segundo

    async def _recusar(self, send, espera: float) -> None:
        corpo = b'{"detail":"muitas requests"}'
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(corpo)).encode()),
                    (b"retry-after", str(math.ceil(espera)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": corpo})


app = FastAPI(title="bloco 1")


@app.get("/users")
async def listar():
    return [{"id": 1, "nome": "Ana"}]


@app.get("/health")
async def health():
    return {"ok": True}


app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:8080"], allow_methods=["GET", "POST"]
)
app.add_middleware(RateLimitMiddleware)
