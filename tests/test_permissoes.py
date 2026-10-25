"""O que cada um pode (lições 11 e 12 do cap. 6).

A autenticação diz quem pede. Aqui mora a outra pergunta: esta pessoa pode mexer
neste objeto? Recurso alheio é 404, não 403: responde igual ao que não existe. É o
contrato da API, e ele não depende do que as listagens mostram."""

import pytest

from tests.apoio import adiciona_membro, cria_despesa, cria_grupo, cria_recurso, cria_reserva, quita


async def test_cancelar_reserva_alheia_e_404(pessoa):
    ana = await pessoa("Ana")
    bruno = await pessoa("Bruno")
    recurso = await cria_recurso(ana.client)
    reserva = (
        await cria_reserva(
            ana.client, recurso["id"], "2030-01-01T10:00:00Z", "2030-01-01T12:00:00Z"
        )
    ).json()

    resp = await bruno.client.delete(f"/bookings/{reserva['id']}")

    assert resp.status_code == 404
    assert resp.json() == {"detail": "reserva não existe"}
    # E a reserva continua lá, para a dona.
    listagem = await ana.client.get("/bookings")
    assert [r["id"] for r in listagem.json()] == [reserva["id"]]


async def test_404_alheio_e_igual_ao_inexistente(pessoa):
    # O contrato: a reserva alheia e a inexistente respondem igual, em tudo. Qualquer
    # diferença viraria um jeito de saber que o id existe.
    ana = await pessoa("Ana")
    bruno = await pessoa("Bruno")
    recurso = await cria_recurso(ana.client)
    reserva = (
        await cria_reserva(
            ana.client, recurso["id"], "2030-01-01T10:00:00Z", "2030-01-01T12:00:00Z"
        )
    ).json()

    alheia = await bruno.client.delete(f"/bookings/{reserva['id']}")
    inexistente = await bruno.client.delete("/bookings/999")

    assert alheia.status_code == inexistente.status_code == 404
    assert alheia.json() == inexistente.json()


async def test_reserva_alheia_passada_tambem_e_404(pessoa):
    # Não 409: o dono vem antes do "já começou". Um 409 seria uma resposta diferente da do
    # inexistente, e quebraria o contrato do 404.
    ana = await pessoa("Ana")
    bruno = await pessoa("Bruno")
    recurso = await cria_recurso(ana.client)
    reserva = (
        await cria_reserva(
            ana.client, recurso["id"], "2020-01-01T10:00:00Z", "2020-01-01T12:00:00Z"
        )
    ).json()

    resp = await bruno.client.delete(f"/bookings/{reserva['id']}")

    assert resp.status_code == 404
    assert resp.json() == {"detail": "reserva não existe"}


# --- Lição 12: ser membro é a regra em todas as rotas de grupo. ---


async def test_quem_cria_o_grupo_e_membro(pessoa):
    ana = await pessoa("Ana")
    grupo = await cria_grupo(ana.client)
    assert grupo["membros"] == [{"user_id": ana.id, "nome": "Ana"}]
    # E não é só a resposta: a linha está no banco, e a Ana lê o grupo dela.
    resp = await ana.client.get(f"/groups/{grupo['id']}")
    assert resp.status_code == 200
    assert resp.json()["membros"] == [{"user_id": ana.id, "nome": "Ana"}]


@pytest.mark.parametrize(
    "metodo, caminho, corpo",
    [
        ("get", "/groups/{g}", None),
        ("get", "/groups/{g}/balances", None),
        ("post", "/groups/{g}/members", {"user_id": "{carla}"}),
        ("post", "/groups/{g}/expenses", {"descricao": "x", "valor": "10.00"}),
        ("post", "/groups/{g}/settlements", {"de_user_id": "{ana}", "valor": "1.00"}),
    ],
)
async def test_quem_nao_e_membro_recebe_404(pessoa, metodo, caminho, corpo):
    # A Carla, de fora, pede no grupo da Ana. A resposta tem de ser idêntica à de um grupo
    # que não existe: qualquer diferença contaria à Carla que o grupo existe (lição 11).
    ana = await pessoa("Ana")
    carla = await pessoa("Carla")
    grupo = await cria_grupo(ana.client)
    ids = {"{ana}": ana.id, "{carla}": carla.id}
    if corpo is not None:
        # Os ids entram como int: uma string "{ana}" levaria 422 no schema, antes do service.
        corpo = {campo: ids.get(valor, valor) for campo, valor in corpo.items()}

    do_grupo = await carla.client.request(metodo, caminho.format(g=grupo["id"]), json=corpo)
    inexistente = await carla.client.request(metodo, caminho.format(g=999), json=corpo)

    assert do_grupo.status_code == inexistente.status_code == 404
    assert do_grupo.json() == inexistente.json() == {"detail": "grupo não existe"}


async def ana_e_bruno(pessoa):
    """Um grupo da Ana, com o Bruno. Devolve o id do grupo e as duas pessoas."""
    ana = await pessoa("Ana")
    bruno = await pessoa("Bruno")
    grupo = await cria_grupo(ana.client)
    assert (await adiciona_membro(ana.client, grupo["id"], bruno.id)).status_code == 201
    return grupo["id"], ana, bruno


async def test_paid_by_e_quem_lanca(pessoa):
    g, _, bruno = await ana_e_bruno(pessoa)
    resp = await cria_despesa(bruno.client, g, valor="10.00")
    assert resp.status_code == 201
    assert resp.json()["paid_by"] == bruno.id


async def test_paid_by_no_corpo_e_ignorado(pessoa):
    # Um cliente antigo, ou mal-intencionado, ainda manda o paid_by. O app não obedece:
    # o campo é descartado, e quem pagou é quem está no token.
    g, ana, bruno = await ana_e_bruno(pessoa)
    resp = await bruno.client.post(
        f"/groups/{g}/expenses",
        json={"paid_by": ana.id, "descricao": "Jantar que a Ana não pagou", "valor": "500.00"},
    )
    assert resp.status_code == 201
    assert resp.json()["paid_by"] == bruno.id


async def ana_bruno_carla(pessoa):
    """Ana pagou 100 entre os três: Ana +66.66, Bruno −33.33, Carla −33.33."""
    g, ana, bruno = await ana_e_bruno(pessoa)
    carla = await pessoa("Carla")
    assert (await adiciona_membro(ana.client, g, carla.id)).status_code == 201
    assert (await cria_despesa(ana.client, g, valor="100.00")).status_code == 201
    return g, ana, bruno, carla


async def saldos(client, g):
    return [b["saldo"] for b in (await client.get(f"/groups/{g}/balances")).json()]


async def test_quitacao_e_lancada_por_quem_recebe(pessoa):
    g, ana, bruno, _ = await ana_bruno_carla(pessoa)
    resp = await quita(ana.client, g, de=bruno.id, valor="33.33")
    assert resp.status_code == 201
    assert (resp.json()["de_user_id"], resp.json()["para_user_id"]) == (bruno.id, ana.id)


async def test_para_user_id_no_corpo_e_ignorado(pessoa):
    # A Ana manda a quitação do Bruno "para a Carla". O campo é descartado: quem recebe
    # é quem lança, e a quitação sai para a Ana.
    g, ana, bruno, carla = await ana_bruno_carla(pessoa)
    resp = await ana.client.post(
        f"/groups/{g}/settlements",
        json={"de_user_id": bruno.id, "para_user_id": carla.id, "valor": "10.00"},
    )
    assert resp.status_code == 201
    assert resp.json()["para_user_id"] == ana.id


async def test_devedor_nao_registra_o_proprio_pagamento(pessoa):
    # A mentira que dá prejuízo: o devedor dizendo "paguei". O Bruno deve 33.33 à Ana.
    g, ana, bruno, carla = await ana_bruno_carla(pessoa)

    # O ataque de antes: "eu, Bruno, paguei a Ana". O para_user_id cai, quem recebe é
    # quem lança, e o pedido vira "o Bruno pagou o Bruno". Barrado no service.
    resp = await bruno.client.post(
        f"/groups/{g}/settlements",
        json={"de_user_id": bruno.id, "para_user_id": ana.id, "valor": "33.33"},
    )
    assert (resp.status_code, resp.json()) == (
        422,
        {"detail": "ninguém quita uma dívida consigo mesmo"},
    )

    # E não existe outra forma: tudo o que o Bruno lança é "o Bruno recebeu", e receber
    # nunca diminui a dívida dele. A Ana não deve nada; o Bruno não tem nada a receber.
    for de in (ana.id, carla.id):
        assert (await quita(bruno.client, g, de=de, valor="33.33")).status_code == 409
    assert await saldos(ana.client, g) == ["66.66", "-33.33", "-33.33"]
