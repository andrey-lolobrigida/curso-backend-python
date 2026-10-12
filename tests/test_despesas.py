"""Despesas: divisão, validação e a transação que não deixa nada pela metade (lição 08)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense, ExpenseShare
from app.repositories import ExpenseRepository
from tests.apoio import adiciona_membro, cria_despesa, cria_grupo, cria_usuario


async def grupo_com(client, n):
    """Um grupo com n membros (user_id 1..n). Devolve o id do grupo."""
    grupo = await cria_grupo(client)
    for i in range(1, n + 1):
        user = await cria_usuario(client, email=f"u{i}@example.com")
        await adiciona_membro(client, grupo["id"], user["id"])
    return grupo["id"]


async def test_despesa_dividida_entre_o_grupo_todo(client):
    g = await grupo_com(client, 3)
    resp = await cria_despesa(client, g, paid_by=1, valor="100.00")
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["valor"] == "100.00"
    assert corpo["partes"] == [
        {"user_id": 1, "valor": "33.34"},
        {"user_id": 2, "valor": "33.33"},
        {"user_id": 3, "valor": "33.33"},
    ]


async def test_despesa_entre_alguns_participantes(client):
    g = await grupo_com(client, 3)
    resp = await cria_despesa(client, g, paid_by=1, valor="50.00", participantes=[2, 3])
    assert [p["user_id"] for p in resp.json()["partes"]] == [2, 3]


async def test_despesa_de_um_centavo_entre_tres(client):
    g = await grupo_com(client, 3)
    resp = await cria_despesa(client, g, paid_by=1, valor="0.01")
    assert resp.status_code == 201
    assert [p["valor"] for p in resp.json()["partes"]] == ["0.01", "0.00", "0.00"]


async def test_valor_em_notacao_cientifica_volta_com_duas_casas(client):
    g = await grupo_com(client, 2)
    resp = await cria_despesa(client, g, paid_by=1, valor="1e2")
    assert resp.status_code == 201
    assert resp.json()["valor"] == "100.00"


@pytest.mark.parametrize("valor", ["80.105", "-5", "0", "abc"])
async def test_valor_invalido_e_422(client, valor):
    g = await grupo_com(client, 2)
    assert (await cria_despesa(client, g, paid_by=1, valor=valor)).status_code == 422


async def test_participante_repetido_e_422(client):
    g = await grupo_com(client, 2)
    resp = await cria_despesa(client, g, paid_by=1, valor="10.00", participantes=[2, 2])
    assert resp.status_code == 422


async def test_participante_de_fora_do_grupo_e_422(client):
    g = await grupo_com(client, 2)
    await cria_usuario(client, email="fora@example.com")  # user 3, sem grupo
    assert (
        await cria_despesa(client, g, paid_by=1, valor="10.00", participantes=[3])
    ).status_code == 422
    assert (await cria_despesa(client, g, paid_by=3, valor="10.00")).status_code == 422


async def test_despesa_em_grupo_inexistente_e_404(client):
    await cria_usuario(client)
    assert (await cria_despesa(client, 999, paid_by=1, valor="10.00")).status_code == 404


async def test_despesa_nunca_fica_pela_metade(client, engine_de_teste, monkeypatch):
    g = await grupo_com(client, 4)
    original = ExpenseRepository.add_share
    chamadas = {"n": 0}

    async def falha_na_terceira(self, expense_id, user_id, valor):
        chamadas["n"] += 1
        if chamadas["n"] == 3:
            raise RuntimeError("o banco caiu no meio da despesa")
        return await original(self, expense_id, user_id, valor)

    monkeypatch.setattr(ExpenseRepository, "add_share", falha_na_terceira)
    with pytest.raises(RuntimeError):
        await cria_despesa(client, g, paid_by=1, valor="100.00")

    async with AsyncSession(engine_de_teste) as db:
        assert await db.scalar(select(func.count()).select_from(Expense)) == 0
        assert await db.scalar(select(func.count()).select_from(ExpenseShare)) == 0
