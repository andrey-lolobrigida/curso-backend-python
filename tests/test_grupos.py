from tests.apoio import adiciona_membro, conta_consultas, cria_grupo, cria_usuario


async def test_cria_grupo_vazio(client):
    grupo = await cria_grupo(client)
    assert grupo == {"id": 1, "nome": "Viagem", "membros": []}


async def test_adiciona_membros_e_busca_grupo(client):
    ana = await cria_usuario(client)
    bruno = await cria_usuario(client, email="bruno@example.com")
    grupo = await cria_grupo(client)
    assert (await adiciona_membro(client, grupo["id"], bruno["id"])).status_code == 201
    assert (await adiciona_membro(client, grupo["id"], ana["id"])).status_code == 201
    resp = await client.get(f"/groups/{grupo['id']}")
    assert resp.status_code == 200
    # Em ordem de user_id, não de chegada.
    assert [m["user_id"] for m in resp.json()["membros"]] == [ana["id"], bruno["id"]]


async def test_membro_repetido_e_409(client):
    ana = await cria_usuario(client)
    grupo = await cria_grupo(client)
    await adiciona_membro(client, grupo["id"], ana["id"])
    assert (await adiciona_membro(client, grupo["id"], ana["id"])).status_code == 409


async def test_grupo_ou_usuario_inexistente_e_404(client):
    ana = await cria_usuario(client)
    grupo = await cria_grupo(client)
    assert (await client.get("/groups/999")).status_code == 404
    assert (await adiciona_membro(client, 999, ana["id"])).status_code == 404
    assert (await adiciona_membro(client, grupo["id"], 999)).status_code == 404


async def test_buscar_grupo_nao_cresce_com_o_numero_de_membros(client, engine_de_teste):
    grupo = await cria_grupo(client)
    for i in range(5):
        user = await cria_usuario(client, email=f"m{i}@example.com")
        await adiciona_membro(client, grupo["id"], user["id"])
    with conta_consultas(engine_de_teste) as contagem:
        resp = await client.get(f"/groups/{grupo['id']}")
    assert len(resp.json()["membros"]) == 5
    assert contagem["n"] == 3  # grupo, membros, usuários
