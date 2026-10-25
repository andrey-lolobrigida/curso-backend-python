"""Quitações: a regra dos dois lados e os cadeados (lição 11)."""

import asyncio

from tests.apoio import adiciona_membro, cria_despesa, cria_grupo, quita


async def ana_bruno_carla(pessoa):
    """Ana pagou 100 entre os três: Ana +66.66, Bruno −33.33, Carla −33.33.
    Devolve o grupo e as três pessoas."""
    ana, bruno, carla = [await pessoa(nome) for nome in ["Ana", "Bruno", "Carla"]]
    grupo = await cria_grupo(ana.client)
    for membro in (bruno, carla):  # a Ana já entrou ao criar
        await adiciona_membro(ana.client, grupo["id"], membro.id)
    await cria_despesa(ana.client, grupo["id"], valor="100.00")
    return grupo["id"], ana, bruno, carla


async def saldos(client, g):
    return [b["saldo"] for b in (await client.get(f"/groups/{g}/balances")).json()]


# Cada quitação sai do client de quem recebe: quem lança é o `para` (lição 12 do cap. 6).
# O corpo leva só o de_user_id, quem pagou.


async def test_quitacao_zera_a_divida(pessoa):
    g, ana, bruno, _ = await ana_bruno_carla(pessoa)
    resp = await quita(ana.client, g, de=bruno.id, valor="33.33")
    assert resp.status_code == 201
    assert resp.json()["valor"] == "33.33"
    assert await saldos(ana.client, g) == ["33.33", "0.00", "-33.33"]


async def test_quitar_alem_do_que_deve_e_409(pessoa):
    g, ana, bruno, _ = await ana_bruno_carla(pessoa)
    assert (await quita(ana.client, g, de=bruno.id, valor="40.00")).status_code == 409


async def test_receber_alem_do_que_tem_a_receber_e_409(pessoa):
    g, _, bruno, carla = await ana_bruno_carla(pessoa)
    # Carla deve 33.33, mas Bruno não tem nada a receber.
    resp = await quita(bruno.client, g, de=carla.id, valor="10.00")
    assert resp.status_code == 409


async def test_quitar_para_si_mesmo_e_422(pessoa):
    # De quem pede para quem pede. Barrado no service, que é quem sabe quem pede.
    g, _, bruno, _ = await ana_bruno_carla(pessoa)
    resp = await quita(bruno.client, g, de=bruno.id, valor="1.00")
    assert (resp.status_code, resp.json()) == (
        422,
        {"detail": "ninguém quita uma dívida consigo mesmo"},
    )


async def test_quitar_com_quem_nao_e_membro_e_422(pessoa):
    g, ana, _, _ = await ana_bruno_carla(pessoa)
    davi = await pessoa("Davi")  # fora do grupo
    # O Davi como quem pagou: 422. (O Davi como quem pede é 404: tests/test_permissoes.py.)
    assert (await quita(ana.client, g, de=davi.id, valor="1.00")).status_code == 422


async def test_quitacoes_simultaneas_nao_pagam_a_mesma_divida_duas_vezes(pessoa):
    g, ana, bruno, _ = await ana_bruno_carla(pessoa)
    respostas = await asyncio.gather(
        *(quita(ana.client, g, de=bruno.id, valor="30.00") for _ in range(8))
    )
    assert sorted(r.status_code for r in respostas) == [201] + [409] * 7
    assert await saldos(ana.client, g) == ["36.66", "-3.33", "-33.33"]


async def test_quitacoes_em_direcoes_opostas_nao_dao_deadlock(pessoa):
    g, ana, _, carla = await ana_bruno_carla(pessoa)
    # A Ana recebendo da Carla é válida (5 × 5 = 25 ≤ 33.33). A Carla "recebendo" da Ana
    # nunca é (a Ana não deve). As duas trancam as mesmas duas linhas, a da Ana e a da Carla,
    # pedidas em ordens opostas: [de, quem pede]. Trancadas nessa ordem, seria deadlock. O
    # lock_members tranca em ordem de user_id, e o ciclo não se forma.
    pedidos = [quita(ana.client, g, de=carla.id, valor="5.00") for _ in range(5)]
    pedidos += [quita(carla.client, g, de=ana.id, valor="5.00") for _ in range(5)]
    respostas = await asyncio.gather(*pedidos)
    assert sorted(r.status_code for r in respostas) == [201] * 5 + [409] * 5
