def _setup_reserva(client, starts_at, ends_at):
    user = client.post("/users", json={"nome": "Ana", "email": "ana@example.com"}).json()
    resource = client.post("/resources", json={"nome": "Quadra 1", "tipo": "quadra"}).json()
    resp = client.post(
        "/bookings",
        json={
            "user_id": user["id"],
            "resource_id": resource["id"],
            "starts_at": starts_at,
            "ends_at": ends_at,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_cancela_reserva_futura(client):
    booking = _setup_reserva(client, "2030-01-01T10:00:00", "2030-01-01T12:00:00")
    resp = client.delete(f"/bookings/{booking['id']}")
    assert resp.status_code == 204
    assert client.get("/bookings").json() == []


def test_nao_cancela_reserva_passada(client):
    booking = _setup_reserva(client, "2020-01-01T10:00:00", "2020-01-01T12:00:00")
    resp = client.delete(f"/bookings/{booking['id']}")
    assert resp.status_code == 409


def test_cancelar_reserva_inexistente_e_404(client):
    assert client.delete("/bookings/999").status_code == 404
