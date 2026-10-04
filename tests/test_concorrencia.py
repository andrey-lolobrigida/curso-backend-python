"""Várias requests idênticas ao mesmo tempo: exatamente uma reserva passa."""

import asyncio

from sqlalchemy.exc import DBAPIError

from app.repositories import BookingRepository
from tests.apoio import cria_recurso, cria_reserva, cria_usuario

# SQLSTATE do Postgres para "deadlock detectado" (lição 11).
DEADLOCK = "40P01"


async def test_reservas_simultaneas_so_uma_passa(client):
    # Sem o cadeado, um empate pode virar deadlock, e as perdedoras saem com 500 em vez de 409
    # (lição 11). Isso é raro, mas acontece: o teste exige o que a regra garante, e só isso.
    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    respostas = await asyncio.gather(
        *(
            cria_reserva(
                client, user["id"], resource["id"], "2030-01-01T10:00:00Z", "2030-01-01T12:00:00Z"
            )
            for _ in range(10)
        ),
        return_exceptions=True,
    )

    criadas = [r for r in respostas if not isinstance(r, Exception) and r.status_code == 201]
    assert len(criadas) == 1
    for r in respostas:
        if isinstance(r, Exception):
            # Sob o pytest, o 500 chega como a própria exceção do app.
            assert isinstance(r, DBAPIError) and r.orig.sqlstate == DEADLOCK
        else:
            assert r.status_code in (201, 409)
    reservas = await client.get("/bookings")
    assert len(reservas.json()) == 1


async def test_sem_a_verificacao_previa_o_banco_ainda_recusa(client, monkeypatch):
    # Simula quem perdeu a corrida: passou pela verificação (que não viu nada) e foi gravar.
    async def nada_sobrepoe(self, resource_id, starts_at, ends_at):
        return []

    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    primeira = await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T10:00:00Z", "2030-01-01T12:00:00Z"
    )
    assert primeira.status_code == 201
    monkeypatch.setattr(BookingRepository, "find_overlapping", nada_sobrepoe)
    segunda = await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T11:00:00Z", "2030-01-01T13:00:00Z"
    )
    assert segunda.status_code == 409
