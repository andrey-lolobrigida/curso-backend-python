async def _cria_usuario(client, email="ana@example.com"):
    resp = await client.post("/users", json={"nome": "Ana", "email": email})
    assert resp.status_code == 201
    return resp.json()


async def _cria_recurso(client):
    resp = await client.post("/resources", json={"nome": "Quadra 1", "tipo": "quadra"})
    assert resp.status_code == 201
    return resp.json()


async def _cria_reserva(client, user_id, resource_id, starts_at, ends_at):
    return await client.post(
        "/bookings",
        json={
            "user_id": user_id,
            "resource_id": resource_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
        },
    )


async def test_cria_e_busca_usuario(client):
    user = await _cria_usuario(client)
    resp = await client.get(f"/users/{user['id']}")
    assert resp.status_code == 200
    assert resp.json()["nome"] == "Ana"


async def test_email_invalido_e_422(client):
    resp = await client.post("/users", json={"nome": "Ana", "email": "sem-arroba"})
    assert resp.status_code == 422


async def test_email_duplicado_e_409(client):
    await _cria_usuario(client)
    resp = await client.post("/users", json={"nome": "Outra Ana", "email": "ana@example.com"})
    assert resp.status_code == 409


async def test_usuario_inexistente_e_404(client):
    resp = await client.get("/users/999")
    assert resp.status_code == 404


async def test_cria_e_lista_recurso(client):
    await _cria_recurso(client)
    resp = await client.get("/resources")
    assert resp.status_code == 200
    assert resp.json()[0]["tipo"] == "quadra"


async def test_cria_reserva(client):
    user = await _cria_usuario(client)
    resource = await _cria_recurso(client)
    resp = await _cria_reserva(
        client, user["id"], resource["id"], "2026-08-01T10:00:00", "2026-08-01T12:00:00"
    )
    assert resp.status_code == 201
    assert resp.json()["user_nome"] == "Ana"
    assert resp.json()["resource_nome"] == "Quadra 1"


async def test_reserva_conflitante_e_409(client):
    user = await _cria_usuario(client)
    resource = await _cria_recurso(client)
    await _cria_reserva(
        client, user["id"], resource["id"], "2026-08-01T10:00:00", "2026-08-01T12:00:00"
    )
    resp = await _cria_reserva(
        client, user["id"], resource["id"], "2026-08-01T11:00:00", "2026-08-01T13:00:00"
    )
    assert resp.status_code == 409


async def test_reservas_encostadas_nao_conflitam(client):
    user = await _cria_usuario(client)
    resource = await _cria_recurso(client)
    await _cria_reserva(
        client, user["id"], resource["id"], "2026-08-01T10:00:00", "2026-08-01T12:00:00"
    )
    resp = await _cria_reserva(
        client, user["id"], resource["id"], "2026-08-01T12:00:00", "2026-08-01T14:00:00"
    )
    assert resp.status_code == 201


async def test_reserva_com_fim_antes_do_inicio_e_422(client):
    user = await _cria_usuario(client)
    resource = await _cria_recurso(client)
    resp = await _cria_reserva(
        client, user["id"], resource["id"], "2026-08-01T12:00:00", "2026-08-01T10:00:00"
    )
    assert resp.status_code == 422


async def test_reserva_com_usuario_fantasma_e_404(client):
    resource = await _cria_recurso(client)
    resp = await _cria_reserva(
        client, 999, resource["id"], "2026-08-01T10:00:00", "2026-08-01T12:00:00"
    )
    assert resp.status_code == 404


async def test_cancela_reserva_futura(client):
    user = await _cria_usuario(client)
    resource = await _cria_recurso(client)
    resposta = await _cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T10:00:00", "2030-01-01T12:00:00"
    )
    booking = resposta.json()
    resp = await client.delete(f"/bookings/{booking['id']}")
    assert resp.status_code == 204
    listagem = await client.get("/bookings")
    assert listagem.json() == []


async def test_nao_cancela_reserva_passada(client):
    user = await _cria_usuario(client)
    resource = await _cria_recurso(client)
    resposta = await _cria_reserva(
        client, user["id"], resource["id"], "2020-01-01T10:00:00", "2020-01-01T12:00:00"
    )
    booking = resposta.json()
    resp = await client.delete(f"/bookings/{booking['id']}")
    assert resp.status_code == 409


async def test_cancelar_reserva_inexistente_e_404(client):
    resp = await client.delete("/bookings/999")
    assert resp.status_code == 404
