from sqlalchemy import text

from tests.apoio import SENHA_DE_TESTE, cria_usuario


async def test_cadastro_nao_devolve_a_senha_nem_o_hash(client):
    resp = await client.post(
        "/users", json={"nome": "Ana", "email": "ana@example.com", "senha": "segredo123"}
    )
    assert resp.status_code == 201
    assert set(resp.json()) == {"id", "nome", "email"}


async def test_senha_e_guardada_como_argon2id(client, engine_de_teste):
    await cria_usuario(client)  # senha = SENHA_DE_TESTE
    async with engine_de_teste.connect() as conn:
        guardado = await conn.scalar(text("SELECT senha_hash FROM users"))
    assert guardado.startswith("$argon2id$")
    assert SENHA_DE_TESTE not in guardado


async def test_mesma_senha_hashes_diferentes(client, engine_de_teste):
    # Duas contas, mesma senha: o sal faz os dois hashes saírem diferentes (lição 02).
    await cria_usuario(client, email="ana@example.com")
    await cria_usuario(client, email="bruno@example.com")
    async with engine_de_teste.connect() as conn:
        hashes = list(await conn.scalars(text("SELECT senha_hash FROM users")))
    assert len(hashes) == 2
    assert hashes[0] != hashes[1]


async def test_senha_curta_e_422(client):
    resp = await client.post(
        "/users", json={"nome": "Ana", "email": "ana@example.com", "senha": "1234567"}
    )
    assert resp.status_code == 422


async def test_senha_longa_demais_e_422(client):
    # Nenhuma senha de gente passa de 128: o que passa disso leva 422 antes do argon2.
    resp = await client.post(
        "/users", json={"nome": "Ana", "email": "ana@example.com", "senha": "x" * 10_000}
    )
    assert resp.status_code == 422


async def test_listagem_de_usuarios_nao_mostra_email(client):
    user = await cria_usuario(client)
    lista = await client.get("/users")
    assert [set(u) for u in lista.json()] == [{"id", "nome"}]
    um = await client.get(f"/users/{user['id']}")
    assert set(um.json()) == {"id", "nome"}
