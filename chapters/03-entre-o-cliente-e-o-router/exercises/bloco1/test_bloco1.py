"""Cada teste usa um IP diferente: baldes independentes, ordem dos testes não importa."""

from httpx2 import ASGITransport, AsyncClient

from servidor import RELOGIO, app

ORIGEM = "http://localhost:8080"


def cliente(ip: str) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app, client=(ip, 1)), base_url="http://test")


async def test_cinco_passam_e_a_sexta_leva_429():
    async with cliente("10.0.0.1") as c:
        codigos = [(await c.get("/users")).status_code for _ in range(6)]
    assert codigos == [200, 200, 200, 200, 200, 429]


async def test_o_balde_recarrega_com_o_tempo():
    async with cliente("10.0.0.2") as c:
        for _ in range(5):
            await c.get("/users")
        assert (await c.get("/users")).status_code == 429
        RELOGIO.avancar(10)
        resp = await c.get("/users")
    assert resp.status_code == 200, "10s depois o balde deveria estar cheio de novo"


async def test_preflight_nao_gasta_ficha_e_429_sai_com_cors():
    async with cliente("10.0.0.3") as c:
        for _ in range(5):
            await c.get("/users", headers={"Origin": ORIGEM})
        preflight = await c.options(
            "/users", headers={"Origin": ORIGEM, "Access-Control-Request-Method": "POST"}
        )
        recusada = await c.get("/users", headers={"Origin": ORIGEM})
    assert preflight.status_code == 200, "preflight é assunto do CORS, não do rate limiter"
    assert recusada.status_code == 429
    assert recusada.headers.get("access-control-allow-origin") == ORIGEM, (
        "o 429 saiu sem CORS: o browser vai mostrar 'erro de CORS' em vez do 429"
    )
