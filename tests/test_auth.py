import hashlib
import re
import statistics
import time
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.main import app as fastapi_app
from tests.apoio import SENHA_DE_TESTE, cria_recurso, cria_reserva, cria_usuario, faz_login


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


async def test_listagem_de_usuarios_nao_mostra_email(pessoa):
    ana = await pessoa("Ana")
    lista = await ana.client.get("/users")
    assert [set(u) for u in lista.json()] == [{"id", "nome"}]
    um = await ana.client.get(f"/users/{ana.id}")
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


async def cronometra_logins(client, email_sem_hash):
    """7 logins com um email sem hash para conferir × 7 de senha errada, intercalados.

    Devolve as duas medianas. O ruído da máquina cai nos dois grupos por igual.
    1 cadastro + 7 + 7 logins = 15 requests, do mesmo IP: cabe nas 20 fichas do balde."""
    await cria_usuario(client, email="ana@example.com")
    sem_hash, senha_errada = [], []
    for _ in range(7):
        for tempos, email in ((sem_hash, email_sem_hash), (senha_errada, "ana@example.com")):
            comeco = time.perf_counter()
            resp = await client.post("/auth/login", json={"email": email, "senha": "outra-senha"})
            tempos.append(time.perf_counter() - comeco)
            assert resp.status_code == 401
    return statistics.median(sem_hash), statistics.median(senha_errada)


async def test_login_de_email_inexistente_demora_como_senha_errada(client):
    # A mensagem igual não basta: o cronômetro também não pode denunciar quem tem conta.
    inexistente, senha_errada = await cronometra_logins(client, "ninguem@example.com")
    # Folga de 2x: o argon2 dos dois lados oscila. Sem o hash fantasma, a razão dá ~0,03.
    assert inexistente >= 0.5 * senha_errada


async def test_login_de_conta_sem_senha_demora_como_senha_errada(client, engine_de_teste):
    # A conta de antes da lição 03 também não tem hash para conferir. Nem ela pode sair rápido.
    async with engine_de_teste.begin() as conn:
        await conn.execute(
            text("INSERT INTO users (nome, email) VALUES ('Velho', 'velho@example.com')")
        )
    sem_senha, senha_errada = await cronometra_logins(client, "velho@example.com")
    assert sem_senha >= 0.5 * senha_errada


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


async def test_rota_sem_token_e_401(client):
    resp = await client.get("/bookings")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Not authenticated"}
    assert resp.headers["www-authenticate"] == "Bearer"


async def test_token_desconhecido_e_401(client):
    resp = await client.get("/bookings", headers={"Authorization": "Bearer lixo"})
    assert (resp.status_code, resp.json()["detail"]) == (401, "token inválido ou vencido")
    assert resp.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer ", "Token xyz"])
async def test_authorization_mal_formado_e_401(client, header):
    # Crachá mal escrito é crachá ausente: 401 com o header, nunca 500 nem 422.
    resp = await client.get("/bookings", headers={"Authorization": header})
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


async def test_bearer_minusculo_funciona(pessoa):
    # O nome do esquema não diferencia maiúsculas (RFC 9110): "bearer" vale.
    ana = await pessoa("Ana")
    token = ana.client.headers["Authorization"].removeprefix("Bearer ")
    resp = await ana.client.get("/users/me", headers={"Authorization": f"bearer {token}"})
    assert resp.status_code == 200


async def test_eu(pessoa):
    ana = await pessoa("Ana")
    resp = await ana.client.get("/users/me")
    assert resp.json() == {"id": ana.id, "nome": "Ana", "email": "ana@example.com"}


async def test_cadastro_e_login_continuam_publicos(client):
    # Sem header nenhum: quem ainda não tem crachá precisa conseguir pedir um.
    cadastro = await client.post(
        "/users", json={"nome": "Ana", "email": "ana@example.com", "senha": SENHA_DE_TESTE}
    )
    assert cadastro.status_code == 201
    login = await client.post(
        "/auth/login", json={"email": "ana@example.com", "senha": SENHA_DE_TESTE}
    )
    assert login.status_code == 200


async def test_reserva_e_de_quem_esta_logado(pessoa):
    await pessoa("Bruno")  # o Bruno vem antes: a Ana não é o usuário 1 por acaso
    ana = await pessoa("Ana")
    resource = await cria_recurso(ana.client)
    resp = await cria_reserva(
        ana.client, resource["id"], "2030-01-01T10:00:00Z", "2030-01-01T12:00:00Z"
    )
    assert resp.status_code == 201
    assert (resp.json()["user_id"], resp.json()["user_nome"]) == (ana.id, "Ana")


async def test_user_id_no_corpo_e_ignorado(pessoa):
    # Um cliente antigo, ou malandro, manda o user_id do Bruno. O corpo não diz quem é você.
    bruno = await pessoa("Bruno")
    ana = await pessoa("Ana")
    resource = await cria_recurso(ana.client)
    resp = await ana.client.post(
        "/bookings",
        json={
            "user_id": bruno.id,
            "resource_id": resource["id"],
            "starts_at": "2030-01-01T10:00:00Z",
            "ends_at": "2030-01-01T12:00:00Z",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["user_id"] == ana.id


# As únicas portas abertas de propósito: quem ainda não tem crachá precisa conseguir pedir um.
ROTAS_PUBLICAS = {("POST", "/users"), ("POST", "/auth/login")}


def todas_as_rotas():
    """Todo par (método, caminho) do app, lido do esquema OpenAPI: a lista pública de rotas,
    a mesma que o Swagger mostra. /docs e /openapi.json não entram nela. Uma rota com
    include_in_schema=False também não entraria: o FairFare não tem nenhuma."""
    return {
        (metodo.upper(), caminho)
        for caminho, operacoes in fastapi_app.openapi()["paths"].items()
        for metodo in operacoes
    }


async def test_toda_rota_exige_login_menos_as_publicas(client):
    # O guardião de rotas: esquecer o dependencies= numa rota nova deixa este teste vermelho.
    rotas = todas_as_rotas()
    # Travas contra o laço vazio: a lista tem as públicas, e tem mais do que elas.
    assert ROTAS_PUBLICAS <= rotas
    assert len(rotas) > 2
    abertas = []
    for metodo, caminho in sorted(rotas - ROTAS_PUBLICAS):
        url = re.sub(r"\{[^}]+\}", "1", caminho)  # /groups/{group_id} -> /groups/1
        # Sem corpo: o 401 vem antes da validação do corpo.
        resp = await client.request(metodo, url)
        if resp.status_code != 401 or resp.headers.get("www-authenticate") != "Bearer":
            abertas.append((metodo, caminho, resp.status_code))
    assert abertas == []
