"""Bancada: o FairFare de verdade, embrulhado num middleware de sete linhas que imprime o scope.

Precisa da raiz do projeto no sys.path (importa app.main), e o --app-dir do uvicorn
tira a raiz do path. Por isso o -m:
  uv run python -m uvicorn espiao:app --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
"""

from app.main import app as fairfare

CHAVES = ("type", "http_version", "method", "scheme", "path", "query_string", "client", "server")


async def app(scope, receive, send) -> None:
    if scope["type"] == "http":
        print({chave: scope[chave] for chave in CHAVES})
        print("headers:", [(nome.decode(), valor.decode()) for nome, valor in scope["headers"]])
    await fairfare(scope, receive, send)
