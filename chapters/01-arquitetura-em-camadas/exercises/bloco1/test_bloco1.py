def test_saida_de_usuario_nao_vaza_campos_internos(client):
    resp = client.post("/users", json={"nome": "Ana", "email": "ana@example.com"})
    assert resp.status_code == 201
    assert "internal_note" not in resp.json()


def test_recurso_inexistente_e_404(client):
    assert client.get("/resources/999").status_code == 404


def test_recurso_sem_tipo_e_422(client):
    resp = client.post("/resources", json={"nome": "Quadra sem tipo"})
    assert resp.status_code == 422
