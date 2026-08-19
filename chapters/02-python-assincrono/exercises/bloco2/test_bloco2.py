import time

from httpx2 import ASGITransport, AsyncClient

from rotas import app


async def test_painel_devolve_as_duas_partes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60) as client:
        resposta = await client.get("/painel")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert set(corpo) == {"reservas", "recursos"}


async def test_painel_faz_as_duas_consultas_ao_mesmo_tempo():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60) as client:
        comeco = time.perf_counter()
        await client.get("/painel")
        total = time.perf_counter() - comeco
    assert total < 0.6, f"levou {total:.2f}s — as duas consultas ainda estão em série"
