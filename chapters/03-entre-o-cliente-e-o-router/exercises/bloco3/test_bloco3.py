"""Os testes de comportamento já passam — e têm que continuar passando depois da refatoração.
O último é estrutural: ele é quem começa vermelho."""

from httpx2 import ASGITransport, AsyncClient

from main import CARIMBO, RELOGIO, app

ORIGEM = "http://localhost:8080"


def cliente(ip: str) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app, client=(ip, 1)), base_url="http://test")


async def test_preflight_de_origem_permitida():
    async with cliente("10.0.3.1") as c:
        resp = await c.options(
            "/users", headers={"Origin": ORIGEM, "Access-Control-Request-Method": "POST"}
        )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGEM
    assert resp.headers["x-servido-por"] == CARIMBO


async def test_origem_desconhecida_nao_ganha_header():
    async with cliente("10.0.3.2") as c:
        resp = await c.get("/users", headers={"Origin": "http://malandro.example"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers
    assert resp.headers["x-servido-por"] == CARIMBO


async def test_429_depois_de_cinco_com_cors_e_carimbo():
    async with cliente("10.0.3.3") as c:
        for _ in range(5):
            assert (await c.get("/users", headers={"Origin": ORIGEM})).status_code == 200
        resp = await c.get("/users", headers={"Origin": ORIGEM})
    assert resp.status_code == 429
    assert resp.headers["retry-after"] == "1"
    assert resp.headers["access-control-allow-origin"] == ORIGEM
    assert resp.headers["x-servido-por"] == CARIMBO


async def test_o_balde_recarrega():
    async with cliente("10.0.3.4") as c:
        for _ in range(6):
            await c.get("/users")
        RELOGIO.avancar(10)
        assert (await c.get("/users")).status_code == 200


def test_o_faz_tudo_foi_desmontado():
    nomes = [m.cls.__name__ for m in app.user_middleware]
    assert "FazTudo" not in nomes, "ainda é um middleware só"
    assert len(nomes) >= 3, f"esperava pelo menos três camadas de propósito único, achei {nomes}"
