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
