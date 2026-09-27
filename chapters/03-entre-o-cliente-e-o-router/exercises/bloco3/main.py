"""Bloco 3 — refatorar. ATENÇÃO: este arquivo está FUNCIONANDO ERRADO de propósito.

Um único BaseHTTPMiddleware faz CORS na mão, rate limit e um carimbo de header,
tudo entrelaçado. Os testes de comportamento passam. Separe em middlewares de
propósito único, na ordem certa, e mantenha-os verdes — o teste estrutural cobra.
"""

import math
import time

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

ORIGENS = {"http://localhost:8080"}
CARIMBO = "fairfare-bloco3"
CAPACIDADE = 5
RECARGA_POR_SEGUNDO = 1.0


class RelogioFalso:
    """Segue o time.monotonic até alguém mandar o tempo andar; daí em diante, só anda quando mandam."""

    def __init__(self) -> None:
        self.agora: float | None = None

    def __call__(self) -> float:
        return time.monotonic() if self.agora is None else self.agora

    def avancar(self, segundos: float) -> None:
        self.agora = self() + segundos


RELOGIO = RelogioFalso()


class FazTudo(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.baldes: dict[str, tuple[float, float]] = {}

    async def dispatch(self, request, call_next):
        origem = request.headers.get("origin")
        origem_ok = origem in ORIGENS

        # 1. Preflight, na mão.
        if request.method == "OPTIONS" and "access-control-request-method" in request.headers:
            if not origem_ok:
                return Response(
                    "origem não permitida", status_code=400, headers={"x-servido-por": CARIMBO}
                )
            return Response(
                status_code=200,
                headers={
                    "access-control-allow-origin": origem,
                    "access-control-allow-methods": "GET, POST",
                    "access-control-allow-headers": "content-type",
                    "x-servido-por": CARIMBO,
                },
            )

        # 2. Rate limit.
        agora = RELOGIO()
        fichas, ultimo = self.baldes.get(request.client.host, (float(CAPACIDADE), agora))
        fichas = min(CAPACIDADE, fichas + (agora - ultimo) * RECARGA_POR_SEGUNDO)
        if fichas >= 1:
            self.baldes[request.client.host] = (fichas - 1, agora)
            resposta = await call_next(request)
        else:
            self.baldes[request.client.host] = (fichas, agora)
            espera = (1 - fichas) / RECARGA_POR_SEGUNDO
            resposta = JSONResponse(
                {"detail": "muitas requests"},
                status_code=429,
                headers={"retry-after": str(math.ceil(espera))},
            )

        # 3. CORS nas respostas normais, e o carimbo em tudo.
        if origem_ok:
            resposta.headers["access-control-allow-origin"] = origem
            resposta.headers["vary"] = "Origin"
        resposta.headers["x-servido-por"] = CARIMBO
        return resposta


app = FastAPI(title="bloco 3")


@app.get("/users")
async def listar():
    return [{"id": 1, "nome": "Ana"}]


app.add_middleware(FazTudo)
