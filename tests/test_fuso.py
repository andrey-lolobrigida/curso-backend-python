"""Horário com fuso: o mesmo instante, escrito de jeitos diferentes, é o mesmo instante."""

import pytest

from tests.apoio import cria_recurso, cria_reserva, cria_usuario


@pytest.mark.xfail(
    strict=True,
    reason="o fuso ainda é descartado; no Postgres vira 500 (conserto: lição 04)",
)
async def test_mesmo_instante_em_fusos_diferentes_conflita(client):
    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    primeira = await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T10:00:00-03:00", "2030-01-01T12:00:00-03:00"
    )
    assert primeira.status_code == 201
    # 13:00 em UTC é 10:00 em São Paulo: o mesmo instante, a mesma quadra.
    segunda = await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T13:00:00Z", "2030-01-01T15:00:00Z"
    )
    assert segunda.status_code == 409
