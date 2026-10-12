"""Guardiões do N+1: o número de consultas não pode crescer com o número de linhas (lição 03)."""

from tests.apoio import conta_consultas, cria_recurso, cria_reserva, cria_usuario


async def test_listar_reservas_nao_cresce_com_o_numero_de_reservas(client, engine_de_teste):
    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    for dia in range(1, 6):
        resp = await cria_reserva(
            client,
            user["id"],
            resource["id"],
            f"2030-01-0{dia}T10:00:00Z",
            f"2030-01-0{dia}T12:00:00Z",
        )
        assert resp.status_code == 201

    with conta_consultas(engine_de_teste) as contagem:
        resp = await client.get("/bookings")

    assert resp.status_code == 200
    assert len(resp.json()) == 5
    # Uma para as reservas, uma para os usuários, uma para os recursos. Com 5 ou 5000.
    assert contagem["n"] == 3
