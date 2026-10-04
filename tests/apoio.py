"""Atalhos para montar o cenário dos testes pela API, como um cliente faria."""


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
