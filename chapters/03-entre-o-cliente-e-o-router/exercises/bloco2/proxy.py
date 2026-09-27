"""Bloco 2 — estender. Este arquivo NÃO está quebrado: só sabe repassar para UM upstream.

criar_proxy recebe {prefixo: cliente httpx2} e devolve um app Starlette. Hoje ele
ignora todos menos o primeiro. Estenda para rotear por prefixo — tirando o prefixo,
preservando query string, Host e o X-Forwarded-For já sobrescrito — sem quebrar o
teste que já passa.

Uma diferença de propósito em relação ao proxy da bancada (lições 06 e 08): lá o
`Host` é retirado e o httpx põe o do upstream; aqui ele **atravessa**, como faz o
`proxy_set_header Host $host` do nginx.conf da lição 07. As duas escolhas são
legítimas — esta é a que o teste cobra, então não copie o `!= "host"` da bancada.
"""

import httpx2
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade"}


def criar_proxy(upstreams: dict[str, httpx2.AsyncClient]) -> Starlette:
    prefixo, upstream = next(iter(upstreams.items()))  # <- só o primeiro. É aqui que você entra.

    async def repassar(request: Request) -> Response:
        caminho = request.url.path.removeprefix(prefixo) or "/"
        headers = {
            nome: valor for nome, valor in request.headers.items() if nome.lower() not in HOP_BY_HOP
        }
        headers["x-forwarded-for"] = request.client.host  # sobrescreve, como a lição 08 manda
        resposta = await upstream.request(
            request.method,
            caminho,
            params=request.url.query,
            headers=headers,
            content=await request.body(),
        )
        headers_de_volta = {
            nome: valor
            for nome, valor in resposta.headers.items()
            if nome.lower() not in HOP_BY_HOP | {"content-length", "content-encoding"}
        }
        return Response(
            resposta.content, status_code=resposta.status_code, headers=headers_de_volta
        )

    return Starlette(routes=[Route("/{caminho:path}", repassar, methods=["GET", "POST", "DELETE"])])
