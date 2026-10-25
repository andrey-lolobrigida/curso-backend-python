"""Despesas: divisão, validação e a transação que não deixa nada pela metade (lição 08)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense, ExpenseShare
from app.repositories import ExpenseRepository
from tests.apoio import adiciona_membro, conta_consultas, cria_despesa, cria_grupo

NOMES = ["Ana", "Bruno", "Carla", "Davi"]


async def grupo_com(pessoa, n):
    """Um grupo com n membros (Ana, Bruno, ...; user_id 1..n), criado pela Ana.
    Devolve o id do grupo e as pessoas."""
    membros = [await pessoa(nome) for nome in NOMES[:n]]
    ana = membros[0]
    grupo = await cria_grupo(ana.client)
    for membro in membros[1:]:  # a Ana já entrou ao criar
        await adiciona_membro(ana.client, grupo["id"], membro.id)
    return grupo["id"], membros


async def test_despesa_dividida_entre_o_grupo_todo(pessoa):
    g, (ana, _, _) = await grupo_com(pessoa, 3)
    resp = await cria_despesa(ana.client, g, valor="100.00")
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["valor"] == "100.00"
    assert corpo["partes"] == [
        {"user_id": 1, "valor": "33.34"},
        {"user_id": 2, "valor": "33.33"},
        {"user_id": 3, "valor": "33.33"},
    ]


async def test_despesa_entre_alguns_participantes(pessoa):
    g, (ana, bruno, carla) = await grupo_com(pessoa, 3)
    resp = await cria_despesa(ana.client, g, valor="50.00", participantes=[bruno.id, carla.id])
    assert [p["user_id"] for p in resp.json()["partes"]] == [2, 3]


async def test_despesa_de_um_centavo_entre_tres(pessoa):
    g, (ana, _, _) = await grupo_com(pessoa, 3)
    resp = await cria_despesa(ana.client, g, valor="0.01")
    assert resp.status_code == 201
    assert [p["valor"] for p in resp.json()["partes"]] == ["0.01", "0.00", "0.00"]


async def test_valor_em_notacao_cientifica_volta_com_duas_casas(pessoa):
    g, (ana, _) = await grupo_com(pessoa, 2)
    resp = await cria_despesa(ana.client, g, valor="1e2")
    assert resp.status_code == 201
    assert resp.json()["valor"] == "100.00"


@pytest.mark.parametrize("valor", ["80.105", "-5", "0", "abc"])
async def test_valor_invalido_e_422(pessoa, valor):
    g, (ana, _) = await grupo_com(pessoa, 2)
    assert (await cria_despesa(ana.client, g, valor=valor)).status_code == 422


async def test_participante_repetido_e_422(pessoa):
    g, (ana, bruno) = await grupo_com(pessoa, 2)
    resp = await cria_despesa(ana.client, g, valor="10.00", participantes=[bruno.id, bruno.id])
    assert resp.status_code == 422


async def test_participante_de_fora_do_grupo_e_422(pessoa):
    g, (ana, _) = await grupo_com(pessoa, 2)
    eva = await pessoa("Eva")  # sem grupo
    # Participante de fora é 422. (A Eva lançando, de fora, é 404: tests/test_permissoes.py.)
    assert (
        await cria_despesa(ana.client, g, valor="10.00", participantes=[eva.id])
    ).status_code == 422


async def test_despesa_em_grupo_inexistente_e_404(pessoa):
    ana = await pessoa("Ana")
    assert (await cria_despesa(ana.client, 999, valor="10.00")).status_code == 404


async def test_despesa_nunca_fica_pela_metade(pessoa, engine_de_teste, monkeypatch):
    g, (ana, *_) = await grupo_com(pessoa, 4)
    original = ExpenseRepository.add_share
    chamadas = {"n": 0}

    async def falha_na_terceira(self, expense_id, user_id, valor):
        chamadas["n"] += 1
        if chamadas["n"] == 3:
            raise RuntimeError("o banco caiu no meio da despesa")
        return await original(self, expense_id, user_id, valor)

    monkeypatch.setattr(ExpenseRepository, "add_share", falha_na_terceira)
    with pytest.raises(RuntimeError):
        await cria_despesa(ana.client, g, valor="100.00")

    async with AsyncSession(engine_de_teste) as db:
        assert await db.scalar(select(func.count()).select_from(Expense)) == 0
        assert await db.scalar(select(func.count()).select_from(ExpenseShare)) == 0


async def test_saldos_de_grupo_sem_despesa_sao_zero(pessoa):
    g, (ana, _) = await grupo_com(pessoa, 2)
    resp = await ana.client.get(f"/groups/{g}/balances")
    assert resp.status_code == 200
    assert [b["saldo"] for b in resp.json()] == ["0.00", "0.00"]


async def test_saldos_conferidos_a_mao(pessoa):
    g, (ana, bruno, carla, _) = await grupo_com(pessoa, 4)
    await cria_despesa(ana.client, g, valor="100.00", participantes=[ana.id, bruno.id, carla.id])
    await cria_despesa(bruno.client, g, valor="30.00", participantes=[ana.id, bruno.id])
    resp = await ana.client.get(f"/groups/{g}/balances")
    # Ana: pagou 100, consumiu 33.34 + 15 → +51.66
    # Bruno: pagou 30, consumiu 33.33 + 15 → −18.33
    # Carla: consumiu 33.33 → −33.33.   Davi: nada → 0.00.   Soma: zero.
    assert [(b["user_id"], b["saldo"]) for b in resp.json()] == [
        (1, "51.66"),
        (2, "-18.33"),
        (3, "-33.33"),
        (4, "0.00"),
    ]


async def test_saldos_de_grupo_inexistente_e_404(pessoa):
    ana = await pessoa("Ana")
    assert (await ana.client.get("/groups/999/balances")).status_code == 404


async def test_saldos_nao_crescem_com_o_numero_de_despesas(pessoa, engine_de_teste):
    g, (ana, _, _) = await grupo_com(pessoa, 3)
    for _ in range(5):
        await cria_despesa(ana.client, g, valor="10.00")
    with conta_consultas(engine_de_teste) as contagem:
        await ana.client.get(f"/groups/{g}/balances")
    # +1: a consulta que pergunta quem é você (lição 05 do cap. 6).
    # O "é membro?" (lição 12 do cap. 6) ocupa o lugar do "o grupo existe?": a conta não sobe.
    assert contagem["n"] == 3  # quem é você? + é membro? + os saldos


async def test_saldos_somam_alem_do_teto_de_uma_despesa(pessoa):
    # Cada despesa cabe no Numeric(12, 2). A soma de três, não: o saldo precisa de mais dígitos.
    g, (ana, _) = await grupo_com(pessoa, 2)
    for _ in range(3):
        resp = await cria_despesa(ana.client, g, valor="9999999999.99")
        assert resp.status_code == 201
    resp = await ana.client.get(f"/groups/{g}/balances")
    assert resp.status_code == 200
    assert [b["saldo"] for b in resp.json()] == ["14999999999.97", "-14999999999.97"]
