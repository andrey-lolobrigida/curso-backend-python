"""O que cada um pode (lições 11 e 12 do cap. 6).

A autenticação diz quem pede. Aqui mora a outra pergunta: esta pessoa pode mexer
neste objeto? Recurso alheio é 404, não 403: responde igual ao que não existe. É o
contrato da API, e ele não depende do que as listagens mostram."""

from tests.apoio import cria_recurso, cria_reserva


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
