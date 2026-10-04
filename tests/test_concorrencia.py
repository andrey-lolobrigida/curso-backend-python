"""Várias requests idênticas ao mesmo tempo: exatamente uma reserva passa."""

import asyncio

from tests.apoio import cria_recurso, cria_reserva, cria_usuario


async def test_reservas_simultaneas_so_uma_passa(client):
    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    respostas = await asyncio.gather(
        *(
            cria_reserva(
                client, user["id"], resource["id"], "2030-01-01T10:00:00Z", "2030-01-01T12:00:00Z"
            )
            for _ in range(10)
        )
    )
    assert sorted(r.status_code for r in respostas) == [201] + [409] * 9
