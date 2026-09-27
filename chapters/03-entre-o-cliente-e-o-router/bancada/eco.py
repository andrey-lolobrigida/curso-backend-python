"""Bancada: o espelho. Devolve quem o servidor ACHA que é o cliente e por qual esquema chegou.

Sobe com (no lugar do FairFare, na 8000, para ficar atrás do proxy):
  uv run uvicorn eco:app --port 8000 --app-dir chapters/03-entre-o-cliente-e-o-router/bancada

`/lento` demora 5s de propósito (lição 11).
"""

import asyncio
import json

from asgi_cru import acompanhar_lifespan


async def app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        await acompanhar_lifespan(receive, send)
        return

    if scope["path"] == "/lento":
        await asyncio.sleep(5)  # uma request em voo, para a demonstração de shutdown gracioso

    # Duas ressalvas de espelho: headers do HTTP são latin-1, e este dict guarda a ÚLTIMA
    # ocorrência de um header repetido — o uvicorn junta todos os x-forwarded-for com ", ".
    headers = {nome.decode("latin-1"): valor.decode("latin-1") for nome, valor in scope["headers"]}
    espelho = {
        "cliente": scope["client"],
        "esquema": scope["scheme"],
        "path": scope["path"],
        "x-forwarded-for": headers.get("x-forwarded-for"),
        "x-forwarded-proto": headers.get("x-forwarded-proto"),
    }
    corpo = json.dumps(espelho, indent=2, ensure_ascii=False).encode()

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": corpo})
