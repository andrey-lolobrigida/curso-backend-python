import pytest
from bloco2.app import app
from httpx2 import ASGITransport, AsyncClient


@pytest.fixture()
async def cliente():
    transport = ASGITransport(app=app, client=("10.0.0.1", 123))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def cracha(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_membro_ve_saldo_de_outro_membro(cliente):
    # A Ana e o Bruno são do grupo 10: um vê o saldo do outro.
    resp = await cliente.get("/grupos/10/saldos/2", headers=cracha("tk-ana"))
    assert resp.status_code == 200
    assert resp.json() == {"user_id": 2, "saldo": "-50.00"}


@pytest.mark.parametrize("alvo", [1, 99], ids=["saldo da ana", "alvo inexistente"])
async def test_quem_nao_e_membro_recebe_404(cliente, alvo):
    # A Carla tem crachá, e não é do grupo 10. Para ela, o grupo não existe, seja qual for
    # o alvo. Qualquer outra frase contaria a ela que o grupo 10 existe.
    resp = await cliente.get(f"/grupos/10/saldos/{alvo}", headers=cracha("tk-carla"))
    assert resp.status_code == 404
    assert resp.json() == {"detail": "grupo não existe"}


async def test_grupo_inexistente_e_404(cliente):
    resp = await cliente.get("/grupos/999/saldos/1", headers=cracha("tk-ana"))
    assert resp.status_code == 404
    assert resp.json() == {"detail": "grupo não existe"}


async def test_sem_token_e_401(cliente):
    resp = await cliente.get("/grupos/10/saldos/1")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"
