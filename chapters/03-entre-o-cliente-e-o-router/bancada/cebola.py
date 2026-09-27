"""Bancada: três middlewares que imprimem quando entram e quando saem.

Dois são ASGI puro (a forma que o FairFare vai usar); um é BaseHTTPMiddleware
(a forma fácil). Registre em uma ordem, veja executar na ordem inversa.

Sobe com:
  uv run uvicorn cebola:app --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
"""

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware


class CamadaASGI:
    """Middleware ASGI puro: recebe o app de dentro e vira ele mesmo um app."""

    def __init__(self, app, nome: str) -> None:
        self.app = app
        self.nome = nome

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        print(f"→ entrei em {self.nome}")

        async def send_espiao(mensagem) -> None:
            if mensagem["type"] == "http.response.start":
                print(f"← saindo de {self.nome} (status {mensagem['status']})")
            await send(mensagem)

        await self.app(scope, receive, send_espiao)


class CamadaFacil(BaseHTTPMiddleware):
    """A forma fácil: você vê Request e Response, não scope/receive/send."""

    def __init__(self, app, nome: str) -> None:
        super().__init__(app)
        self.nome = nome

    async def dispatch(self, request, call_next):
        print(f"→ entrei em {self.nome}")
        resposta = await call_next(request)
        print(f"← saindo de {self.nome} (status {resposta.status_code})")
        return resposta


app = FastAPI(title="cebola")


@app.get("/")
async def centro():
    print("   · o router, no centro da cebola")
    return {"ok": True}


app.add_middleware(CamadaASGI, nome="A (registrado primeiro)")
app.add_middleware(CamadaASGI, nome="B (registrado depois)")
app.add_middleware(CamadaFacil, nome="C (registrado por último, BaseHTTPMiddleware)")
