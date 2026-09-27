"""O proxy inteiro roda em processo: os upstreams são apps ASGI de brinquedo ligados
por ASGITransport. Nenhuma porta é aberta."""

import json

import pytest
from httpx2 import ASGITransport, AsyncClient

from proxy import criar_proxy


def app_de_brinquedo(nome: str):
    async def app(scope, receive, send) -> None:
        headers = {k.decode(): v.decode() for k, v in scope["headers"]}
        corpo = json.dumps(
            {
                "app": nome,
                "path": scope["path"],
                "query": scope["query_string"].decode(),
                "host": headers.get("host"),
                "x-forwarded-for": headers.get("x-forwarded-for"),
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"x-servido-por", nome.encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": corpo})

    return app


@pytest.fixture()
async def proxy():
    upstreams = {
        "/reservas": AsyncClient(
            transport=ASGITransport(app=app_de_brinquedo("reservas")), base_url="http://reservas"
        ),
        "/despesas": AsyncClient(
            transport=ASGITransport(app=app_de_brinquedo("despesas")), base_url="http://despesas"
        ),
    }
    app = criar_proxy(upstreams)
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("203.0.113.9", 4321)), base_url="http://proxy.test"
    ) as c:
        yield c
    for cliente in upstreams.values():
        await cliente.aclose()


async def test_formato_preservado(proxy):
    """Já passa. Continuar passando é metade da tarefa."""
    resp = await proxy.get(
        "/reservas/quadras?dia=2026-09-05", headers={"X-Forwarded-For": "1.2.3.4"}
    )
    assert resp.status_code == 200
    assert resp.headers["x-servido-por"] == "reservas"
    corpo = resp.json()
    assert corpo["path"] == "/quadras"  # prefixo removido
    assert corpo["query"] == "dia=2026-09-05"  # query string preservada
    assert corpo["host"] == "proxy.test"  # Host preservado
    assert corpo["x-forwarded-for"] == "203.0.113.9"  # o de fora (1.2.3.4) foi sobrescrito


async def test_roteia_por_prefixo(proxy):
    resp = await proxy.get("/despesas/saldos")
    assert resp.status_code == 200
    assert resp.json()["app"] == "despesas"
    assert resp.json()["path"] == "/saldos"


async def test_prefixo_desconhecido_e_404(proxy):
    resp = await proxy.get("/outra/coisa")
    assert resp.status_code == 404, (
        "nenhum prefixo casa com /outra: o proxy tem que dizer 404, e não despejar a request "
        "no primeiro upstream que encontrar"
    )
