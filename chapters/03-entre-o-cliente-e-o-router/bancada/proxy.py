"""Bancada: um proxy reverso em cinquenta linhas.

Escuta na 8080. O que chega em /api/... vai para o FairFare (8000), sem o prefixo.
Todo o resto é a página em pagina/, servida como arquivo estático.

Imprime cada request que atravessa — inclusive o corpo. Isso é DE PROPÓSITO:
quem está no meio lê tudo, e a lição 09 é sobre isso.

Sobe com:
  uv run uvicorn proxy:app --port 8080 --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
"""

from pathlib import Path

import httpx2
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

UPSTREAM = "http://127.0.0.1:8000"
PAGINA = Path(__file__).with_name("pagina")

# Headers que pertencem a UMA conexão, não à mensagem. Não atravessam proxies.
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade"}

upstream = httpx2.AsyncClient(base_url=UPSTREAM, timeout=30)


def headers_para_o_upstream(request: Request) -> dict[str, str]:
    # "host" sai: o httpx põe o do upstream. O resto passa como veio.
    return {
        nome: valor
        for nome, valor in request.headers.items()
        if nome.lower() not in HOP_BY_HOP and nome.lower() != "host"
    }


async def repassar(request: Request) -> Response:
    caminho = "/" + request.path_params["caminho"]
    corpo = await request.body()
    print(f"→ {request.method} {caminho}  corpo={corpo!r}")

    resposta = await upstream.request(
        request.method,
        caminho,
        params=request.url.query,
        headers=headers_para_o_upstream(request),
        content=corpo,
    )
    print(f"← {resposta.status_code}")

    # content-length e content-encoding saem: o httpx já descomprimiu, e o Starlette recalcula.
    headers_de_volta = {
        nome: valor
        for nome, valor in resposta.headers.items()
        if nome.lower() not in HOP_BY_HOP | {"content-length", "content-encoding"}
    }
    return Response(resposta.content, status_code=resposta.status_code, headers=headers_de_volta)


app = Starlette(
    routes=[
        Route(
            "/api/{caminho:path}",
            repassar,
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        ),
        Mount("/", StaticFiles(directory=PAGINA, html=True)),
    ]
)
