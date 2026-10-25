"""Quitações: a regra dos dois lados e os cadeados (lição 11)."""

import asyncio

from tests.apoio import adiciona_membro, cria_despesa, cria_grupo, quita


async def ana_bruno_carla(pessoa):
    """Ana pagou 100 entre os três: Ana +66.66, Bruno −33.33, Carla −33.33.
    Devolve o grupo e as três pessoas."""
    ana, bruno, carla = [await pessoa(nome) for nome in ["Ana", "Bruno", "Carla"]]
    grupo = await cria_grupo(ana.client)
    for membro in (ana, bruno, carla):
        await adiciona_membro(ana.client, grupo["id"], membro.id)
    await cria_despesa(ana.client, grupo["id"], paid_by=ana.id, valor="100.00")
    return grupo["id"], ana, bruno, carla


async def saldos(client, g):
    return [b["saldo"] for b in (await client.get(f"/groups/{g}/balances")).json()]


# Cada quitação sai do client de quem recebe (`para`): é a regra da lição 12 do cap. 6.
# Até lá, o de_user_id e o para_user_id ainda vêm no corpo, e o app não confere quem lança.


async def test_quitacao_zera_a_divida(pessoa):
    g, ana, bruno, _ = await ana_bruno_carla(pessoa)
    resp = await quita(ana.client, g, de=bruno.id, para=ana.id, valor="33.33")
    assert resp.status_code == 201
    assert resp.json()["valor"] == "33.33"
    assert await saldos(ana.client, g) == ["33.33", "0.00", "-33.33"]


async def test_quitar_alem_do_que_deve_e_409(pessoa):
    g, ana, bruno, _ = await ana_bruno_carla(pessoa)
    assert (await quita(ana.client, g, de=bruno.id, para=ana.id, valor="40.00")).status_code == 409


async def test_receber_alem_do_que_tem_a_receber_e_409(pessoa):
    g, _, bruno, carla = await ana_bruno_carla(pessoa)
    # Carla deve 33.33, mas Bruno não tem nada a receber.
    resp = await quita(bruno.client, g, de=carla.id, para=bruno.id, valor="10.00")
    assert resp.status_code == 409


async def test_quitar_para_si_mesmo_e_422(pessoa):
    g, _, bruno, _ = await ana_bruno_carla(pessoa)
    resp = await quita(bruno.client, g, de=bruno.id, para=bruno.id, valor="1.00")
    assert resp.status_code == 422


async def test_quitar_com_quem_nao_e_membro_e_422(pessoa):
    g, ana, bruno, _ = await ana_bruno_carla(pessoa)
    davi = await pessoa("Davi")  # fora do grupo
    assert (await quita(ana.client, g, de=davi.id, para=ana.id, valor="1.00")).status_code == 422
    assert (await quita(davi.client, g, de=bruno.id, para=davi.id, valor="1.00")).status_code == 422


async def test_quitacoes_simultaneas_nao_pagam_a_mesma_divida_duas_vezes(pessoa):
    g, ana, bruno, _ = await ana_bruno_carla(pessoa)
    respostas = await asyncio.gather(
        *(quita(ana.client, g, de=bruno.id, para=ana.id, valor="30.00") for _ in range(8))
    )
    assert sorted(r.status_code for r in respostas) == [201] + [409] * 7
    assert await saldos(ana.client, g) == ["36.66", "-3.33", "-33.33"]


async def test_quitacoes_em_direcoes_opostas_nao_dao_deadlock(pessoa):
    g, ana, bruno, _ = await ana_bruno_carla(pessoa)
    # Bruno→Ana é válida (5 × 5 = 25 ≤ 33.33). Ana→Bruno nunca é (Ana não deve).
    # As duas trancam as mesmas duas linhas. Em ordens opostas, seria deadlock.
    pedidos = [quita(ana.client, g, de=bruno.id, para=ana.id, valor="5.00") for _ in range(5)]
    pedidos += [quita(bruno.client, g, de=ana.id, para=bruno.id, valor="5.00") for _ in range(5)]
    respostas = await asyncio.gather(*pedidos)
    assert sorted(r.status_code for r in respostas) == [201] * 5 + [409] * 5
