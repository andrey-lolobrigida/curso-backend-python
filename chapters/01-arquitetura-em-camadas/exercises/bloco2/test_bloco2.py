def test_recurso_pode_ter_capacidade(client):
    resp = client.post(
        "/resources", json={"nome": "Chalé da Serra", "tipo": "chalé", "capacity": 8}
    )
    assert resp.status_code == 201
    assert resp.json()["capacity"] == 8


def test_capacidade_e_opcional(client):
    resp = client.post("/resources", json={"nome": "Quadra 1", "tipo": "quadra"})
    assert resp.status_code == 201
    assert resp.json()["capacity"] is None
