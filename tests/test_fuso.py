"""Horário com fuso: o mesmo instante, escrito de jeitos diferentes, é o mesmo instante."""

import time

from tests.apoio import cria_recurso, cria_reserva, cria_usuario


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


async def test_horario_volta_em_utc(client):
    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    resp = await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T10:00:00-03:00", "2030-01-01T12:00:00-03:00"
    )
    assert resp.status_code == 201
    # timestamptz guarda o instante, não o fuso de quem mandou: volta em UTC.
    assert resp.json()["starts_at"] == "2030-01-01T13:00:00Z"


async def test_horario_sem_fuso_e_lido_como_utc(client):
    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    resp = await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T10:00:00", "2030-01-01T12:00:00"
    )
    assert resp.status_code == 201
    assert resp.json()["starts_at"] == "2030-01-01T10:00:00Z"


async def test_sem_fuso_e_utc_mesmo_com_o_servidor_em_outro_fuso(client, monkeypatch):
    # A decisão "sem fuso é UTC" não pode depender do relógio da máquina onde o app roda.
    monkeypatch.setenv("TZ", "America/Sao_Paulo")
    time.tzset()
    try:
        user = await cria_usuario(client)
        resource = await cria_recurso(client)
        resp = await cria_reserva(
            client, user["id"], resource["id"], "2030-01-01T10:00:00", "2030-01-01T12:00:00"
        )
    finally:
        monkeypatch.undo()
        time.tzset()
    assert resp.status_code == 201
    assert resp.json()["starts_at"] == "2030-01-01T10:00:00Z"


async def test_fusos_misturados_sao_422_nao_500(client):
    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    # 10:00 em São Paulo = 13:00 UTC; o fim, sem fuso, é 12:00 UTC: termina antes de começar.
    resp = await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T10:00:00-03:00", "2030-01-01T12:00:00"
    )
    assert resp.status_code == 422


async def test_encostadas_em_fusos_diferentes_nao_conflitam(client):
    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T10:00:00-03:00", "2030-01-01T12:00:00-03:00"
    )
    # 15:00 UTC é 12:00 em São Paulo: começa exatamente quando a outra termina.
    resp = await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T15:00:00Z", "2030-01-01T17:00:00Z"
    )
    assert resp.status_code == 201
