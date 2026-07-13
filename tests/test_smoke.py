def _cria_usuario(client, email="ana@example.com"):
    resp = client.post("/users", json={"nome": "Ana", "email": email})
    assert resp.status_code == 201
    return resp.json()


def _cria_recurso(client):
    resp = client.post("/resources", json={"nome": "Quadra 1", "tipo": "quadra"})
    assert resp.status_code == 201
    return resp.json()


def _cria_reserva(client, user_id, resource_id, starts_at, ends_at):
    return client.post(
        "/bookings",
        json={
            "user_id": user_id,
            "resource_id": resource_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
        },
    )


def test_cria_e_busca_usuario(client):
    user = _cria_usuario(client)
    resp = client.get(f"/users/{user['id']}")
    assert resp.status_code == 200
    assert resp.json()["nome"] == "Ana"


def test_email_invalido_e_422(client):
    resp = client.post("/users", json={"nome": "Ana", "email": "sem-arroba"})
    assert resp.status_code == 422


def test_email_duplicado_e_409(client):
    _cria_usuario(client)
    resp = client.post("/users", json={"nome": "Outra Ana", "email": "ana@example.com"})
    assert resp.status_code == 409


def test_usuario_inexistente_e_404(client):
    assert client.get("/users/999").status_code == 404


def test_cria_e_lista_recurso(client):
    _cria_recurso(client)
    resp = client.get("/resources")
    assert resp.status_code == 200
    assert resp.json()[0]["tipo"] == "quadra"


def test_cria_reserva(client):
    user = _cria_usuario(client)
    resource = _cria_recurso(client)
    resp = _cria_reserva(
        client, user["id"], resource["id"], "2026-08-01T10:00:00", "2026-08-01T12:00:00"
    )
    assert resp.status_code == 201
    assert resp.json()["user_nome"] == "Ana"
    assert resp.json()["resource_nome"] == "Quadra 1"


def test_reserva_conflitante_e_409(client):
    user = _cria_usuario(client)
    resource = _cria_recurso(client)
    _cria_reserva(client, user["id"], resource["id"], "2026-08-01T10:00:00", "2026-08-01T12:00:00")
    resp = _cria_reserva(
        client, user["id"], resource["id"], "2026-08-01T11:00:00", "2026-08-01T13:00:00"
    )
    assert resp.status_code == 409


def test_reservas_encostadas_nao_conflitam(client):
    user = _cria_usuario(client)
    resource = _cria_recurso(client)
    _cria_reserva(client, user["id"], resource["id"], "2026-08-01T10:00:00", "2026-08-01T12:00:00")
    resp = _cria_reserva(
        client, user["id"], resource["id"], "2026-08-01T12:00:00", "2026-08-01T14:00:00"
    )
    assert resp.status_code == 201


def test_reserva_com_fim_antes_do_inicio_e_422(client):
    user = _cria_usuario(client)
    resource = _cria_recurso(client)
    resp = _cria_reserva(
        client, user["id"], resource["id"], "2026-08-01T12:00:00", "2026-08-01T10:00:00"
    )
    assert resp.status_code == 422


def test_reserva_com_usuario_fantasma_e_404(client):
    resource = _cria_recurso(client)
    resp = _cria_reserva(client, 999, resource["id"], "2026-08-01T10:00:00", "2026-08-01T12:00:00")
    assert resp.status_code == 404
