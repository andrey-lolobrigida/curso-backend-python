"""Quitações: a regra dos dois lados e os cadeados (lição 11)."""

import asyncio

from tests.apoio import adiciona_membro, cria_despesa, cria_grupo, cria_usuario, quita


async def ana_bruno_carla(client):
    """Ana pagou 100 entre os três: Ana +66.66, Bruno −33.33, Carla −33.33. Devolve o grupo."""
    grupo = await cria_grupo(client)
    for i, nome in enumerate(["ana", "bruno", "carla"], start=1):
        await cria_usuario(client, email=f"{nome}@example.com")
        await adiciona_membro(client, grupo["id"], i)
    await cria_despesa(client, grupo["id"], paid_by=1, valor="100.00")
    return grupo["id"]


async def saldos(client, g):
    return [b["saldo"] for b in (await client.get(f"/groups/{g}/balances")).json()]


async def test_quitacao_zera_a_divida(client):
    g = await ana_bruno_carla(client)
    resp = await quita(client, g, de=2, para=1, valor="33.33")
    assert resp.status_code == 201
    assert resp.json()["valor"] == "33.33"
    assert await saldos(client, g) == ["33.33", "0.00", "-33.33"]


async def test_quitar_alem_do_que_deve_e_409(client):
    g = await ana_bruno_carla(client)
    assert (await quita(client, g, de=2, para=1, valor="40.00")).status_code == 409


async def test_receber_alem_do_que_tem_a_receber_e_409(client):
    g = await ana_bruno_carla(client)
    # Carla deve 33.33, mas Bruno não tem nada a receber.
    assert (await quita(client, g, de=3, para=2, valor="10.00")).status_code == 409


async def test_quitar_para_si_mesmo_e_422(client):
    g = await ana_bruno_carla(client)
    assert (await quita(client, g, de=2, para=2, valor="1.00")).status_code == 422


async def test_quitar_com_quem_nao_e_membro_e_422(client):
    g = await ana_bruno_carla(client)
    await cria_usuario(client, email="davi@example.com")  # user 4, fora do grupo
    assert (await quita(client, g, de=4, para=1, valor="1.00")).status_code == 422
    assert (await quita(client, g, de=2, para=4, valor="1.00")).status_code == 422


async def test_quitacoes_simultaneas_nao_pagam_a_mesma_divida_duas_vezes(client):
    g = await ana_bruno_carla(client)
    respostas = await asyncio.gather(
        *(quita(client, g, de=2, para=1, valor="30.00") for _ in range(8))
    )
    assert sorted(r.status_code for r in respostas) == [201] + [409] * 7
    assert await saldos(client, g) == ["36.66", "-3.33", "-33.33"]


async def test_quitacoes_em_direcoes_opostas_nao_dao_deadlock(client):
    g = await ana_bruno_carla(client)
    # Bruno→Ana é válida (5 × 5 = 25 ≤ 33.33). Ana→Bruno nunca é (Ana não deve).
    # As duas trancam as mesmas duas linhas. Em ordens opostas, seria deadlock.
    pedidos = [quita(client, g, de=2, para=1, valor="5.00") for _ in range(5)]
    pedidos += [quita(client, g, de=1, para=2, valor="5.00") for _ in range(5)]
    respostas = await asyncio.gather(*pedidos)
    assert sorted(r.status_code for r in respostas) == [201] * 5 + [409] * 5
