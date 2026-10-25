import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.apoio import SENHA_DE_TESTE, cria_usuario, faz_login


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


async def test_login_devolve_token_bearer(client):
    await cria_usuario(client)
    resp = await client.post(
        "/auth/login", json={"email": "ana@example.com", "senha": SENHA_DE_TESTE}
    )
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert len(resp.json()["access_token"]) >= 43  # 32 bytes em base64url


async def test_banco_guarda_o_sha256_do_token_e_nao_o_token(client, engine_de_teste):
    await cria_usuario(client)
    token = await faz_login(client, "ana@example.com")
    async with engine_de_teste.connect() as conn:
        linhas = (await conn.execute(text("SELECT * FROM sessions"))).all()
    assert len(linhas) == 1
    assert linhas[0].token_hash == hashlib.sha256(token.encode()).hexdigest()
    # O token puro não aparece em coluna nenhuma da linha.
    assert all(token not in str(valor) for valor in linhas[0])


async def test_sessao_vale_24_horas(client, engine_de_teste):
    await cria_usuario(client)
    await faz_login(client, "ana@example.com")
    async with engine_de_teste.connect() as conn:
        validade = await conn.scalar(text("SELECT expira_em - criada_em FROM sessions"))
    # Exato, sem microssegundo sobrando: os dois vêm do mesmo "agora".
    assert validade == timedelta(hours=24)


@pytest.mark.parametrize("caso", ["email_inexistente", "senha_errada", "conta_sem_senha"])
async def test_login_recusado_e_sempre_igual(client, engine_de_teste, caso):
    await cria_usuario(client, email="ana@example.com")
    if caso == "conta_sem_senha":
        # Um usuário de antes da lição 03: a linha existe, o senha_hash é NULL.
        async with engine_de_teste.begin() as conn:
            await conn.execute(
                text("INSERT INTO users (nome, email) VALUES ('Velho', 'velho@example.com')")
            )
    corpo = {
        "email_inexistente": {"email": "ninguem@example.com", "senha": SENHA_DE_TESTE},
        "senha_errada": {"email": "ana@example.com", "senha": "outra-senha"},
        "conta_sem_senha": {"email": "velho@example.com", "senha": SENHA_DE_TESTE},
    }[caso]
    resp = await client.post("/auth/login", json=corpo)
    assert resp.status_code == 401
    assert resp.json() == {"detail": "email ou senha inválidos"}
    assert resp.headers["WWW-Authenticate"] == "Bearer"


async def test_dois_logins_duas_sessoes(client, engine_de_teste):
    await cria_usuario(client)
    primeiro = await faz_login(client, "ana@example.com")
    segundo = await faz_login(client, "ana@example.com")
    assert primeiro != segundo
    async with engine_de_teste.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM sessions")) == 2


async def test_senha_com_acento_e_emoji_loga(client):
    await cria_usuario(client, senha="pão de açúcar 🍞")
    token = await faz_login(client, "ana@example.com", senha="pão de açúcar 🍞")
    assert token


async def test_login_aceita_o_email_digitado_como_no_cadastro(client):
    # O cadastro baixa o domínio (EmailStr). O login passa pela mesma régua,
    # senão quem digita igual nas duas telas não entra.
    await cria_usuario(client, email="Fe.Cap06@Example.COM")
    token = await faz_login(client, "Fe.Cap06@Example.COM")
    assert token


async def test_login_com_senha_longa_demais_e_422(client):
    # O mesmo teto do cadastro: senha de 10 000 caracteres não chega ao argon2.
    resp = await client.post(
        "/auth/login", json={"email": "ana@example.com", "senha": "x" * 10_000}
    )
    assert resp.status_code == 422
