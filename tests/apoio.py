"""Atalhos para montar o cenário dos testes pela API, como um cliente faria."""

from contextlib import contextmanager

from sqlalchemy import event


async def cria_usuario(client, email="ana@example.com"):
    resp = await client.post("/users", json={"nome": "Ana", "email": email})
    assert resp.status_code == 201
    return resp.json()


async def cria_recurso(client):
    resp = await client.post("/resources", json={"nome": "Quadra 1", "tipo": "quadra"})
    assert resp.status_code == 201
    return resp.json()


async def cria_reserva(client, user_id, resource_id, starts_at, ends_at):
    return await client.post(
        "/bookings",
        json={
            "user_id": user_id,
            "resource_id": resource_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
        },
    )


@contextmanager
def conta_consultas(engine):
    """Conta os comandos SQL que passam pela engine dentro do bloco (lição 03)."""
    contagem = {"n": 0}

    def conta(*args):
        contagem["n"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", conta)
    try:
        yield contagem
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", conta)


async def cria_grupo(client, nome="Viagem"):
    resp = await client.post("/groups", json={"nome": nome})
    assert resp.status_code == 201
    return resp.json()


async def adiciona_membro(client, group_id, user_id):
    return await client.post(f"/groups/{group_id}/members", json={"user_id": user_id})


async def cria_despesa(client, group_id, paid_by, valor, participantes=None, descricao="Jantar"):
    corpo = {"paid_by": paid_by, "descricao": descricao, "valor": valor}
    if participantes is not None:
        corpo["participantes"] = participantes
    return await client.post(f"/groups/{group_id}/expenses", json=corpo)


async def quita(client, group_id, de, para, valor):
    return await client.post(
        f"/groups/{group_id}/settlements",
        json={"de_user_id": de, "para_user_id": para, "valor": valor},
    )
