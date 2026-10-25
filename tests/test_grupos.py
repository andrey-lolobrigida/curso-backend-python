from tests.apoio import adiciona_membro, conta_consultas, cria_grupo


async def test_grupo_novo_so_com_o_criador(pessoa):
    # Quem cria entra como membro (lição 12 do cap. 6): grupo vazio não existe mais.
    ana = await pessoa("Ana")
    grupo = await cria_grupo(ana.client)
    assert grupo == {"id": 1, "nome": "Viagem", "membros": [{"user_id": ana.id, "nome": "Ana"}]}


async def test_adiciona_membros_e_busca_grupo(pessoa):
    ana = await pessoa("Ana")
    bruno = await pessoa("Bruno")
    # O Bruno cria (entra primeiro) e adiciona a Ana (entra depois, com o id menor).
    grupo = await cria_grupo(bruno.client)
    assert (await adiciona_membro(bruno.client, grupo["id"], ana.id)).status_code == 201
    resp = await bruno.client.get(f"/groups/{grupo['id']}")
    assert resp.status_code == 200
    # Em ordem de user_id, não de chegada.
    assert [m["user_id"] for m in resp.json()["membros"]] == [ana.id, bruno.id]


async def test_membro_repetido_e_409(pessoa):
    ana = await pessoa("Ana")
    bruno = await pessoa("Bruno")
    grupo = await cria_grupo(ana.client)
    await adiciona_membro(ana.client, grupo["id"], bruno.id)
    assert (await adiciona_membro(ana.client, grupo["id"], bruno.id)).status_code == 409


async def test_grupo_ou_usuario_inexistente_e_404(pessoa):
    ana = await pessoa("Ana")
    grupo = await cria_grupo(ana.client)
    assert (await ana.client.get("/groups/999")).status_code == 404
    assert (await adiciona_membro(ana.client, 999, ana.id)).status_code == 404
    assert (await adiciona_membro(ana.client, grupo["id"], 999)).status_code == 404


async def test_buscar_grupo_nao_cresce_com_o_numero_de_membros(pessoa, engine_de_teste):
    membros = [await pessoa(nome) for nome in ["Ana", "Bruno", "Carla", "Davi", "Eva"]]
    ana = membros[0]
    grupo = await cria_grupo(ana.client)
    for membro in membros[1:]:  # a Ana já entrou ao criar
        await adiciona_membro(ana.client, grupo["id"], membro.id)
    with conta_consultas(engine_de_teste) as contagem:
        resp = await ana.client.get(f"/groups/{grupo['id']}")
    assert len(resp.json()["membros"]) == 5
    # +1: a consulta que pergunta quem é você (lição 05 do cap. 6). O "é membro?" (lição 12)
    # não soma: ele olha os membros que já vieram carregados.
    assert contagem["n"] == 4  # quem é você, grupo, membros, usuários
