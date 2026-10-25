"""Guardiões do N+1: o número de consultas não pode crescer com o número de linhas (lição 03)."""

from tests.apoio import conta_consultas, cria_recurso, cria_reserva


async def test_listar_reservas_nao_cresce_com_o_numero_de_reservas(pessoa, engine_de_teste):
    ana = await pessoa("Ana")
    resource = await cria_recurso(ana.client)
    for dia in range(1, 6):
        resp = await cria_reserva(
            ana.client,
            resource["id"],
            f"2030-01-0{dia}T10:00:00Z",
            f"2030-01-0{dia}T12:00:00Z",
        )
        assert resp.status_code == 201

    with conta_consultas(engine_de_teste) as contagem:
        resp = await ana.client.get("/bookings")

    assert resp.status_code == 200
    assert len(resp.json()) == 5
    # Uma para as reservas, uma para os usuários, uma para os recursos. Com 5 ou 5000.
    # +1: a consulta que pergunta quem é você (lição 05 do cap. 6).
    assert contagem["n"] == 4
