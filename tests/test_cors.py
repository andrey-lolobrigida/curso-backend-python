"""CORS: o browser é quem aplica a regra; o servidor só anuncia o que permite."""

ORIGEM_PERMITIDA = "http://localhost:8080"


async def test_preflight_de_origem_permitida_e_respondido(client):
    resp = await client.options(
        "/users",
        headers={
            "Origin": ORIGEM_PERMITIDA,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA
    assert "POST" in resp.headers["access-control-allow-methods"]


# Os três abaixo fazem GET /users, que agora pede login: quem pergunta é uma pessoa logada
# (lição 05 do cap. 6). O preflight acima não muda: o CORS responde antes da rota.


async def test_request_simples_de_origem_permitida_ganha_o_header(pessoa):
    ana = await pessoa("Ana")
    resp = await ana.client.get("/users", headers={"Origin": ORIGEM_PERMITIDA})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA


async def test_origem_desconhecida_nao_ganha_header_nenhum(pessoa):
    ana = await pessoa("Ana")
    resp = await ana.client.get("/users", headers={"Origin": "http://malandro.example"})
    assert resp.status_code == 200  # o servidor responde normalmente...
    assert "access-control-allow-origin" not in resp.headers  # ...e o browser vai esconder


async def test_sem_origin_passa_intacta(pessoa):
    # O curl de sempre não manda Origin. CORS é regra de browser, não de servidor.
    ana = await pessoa("Ana")
    resp = await ana.client.get("/users")
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


# Lição 10 do cap. 6: o crachá vai no header Authorization, que não está na lista segura.
# O preflight não leva credencial nenhuma, então quem pergunta é o cliente anônimo.


async def test_preflight_com_authorization_e_permitido(client):
    resp = await client.options(
        "/bookings",
        headers={
            "Origin": ORIGEM_PERMITIDA,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert resp.status_code == 200
    assert "authorization" in resp.headers["access-control-allow-headers"].lower()


async def test_sem_allow_credentials(client):
    # O crachá é um header que o JS põe à mão. Não é cookie: o CORS não precisa liberar credenciais.
    resp = await client.options(
        "/bookings",
        headers={
            "Origin": ORIGEM_PERMITIDA,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert resp.status_code == 200
    assert "access-control-allow-credentials" not in resp.headers


async def test_401_atravessa_o_cors(client):
    # Anônimo de propósito: sem o carimbo, a página veria "erro de CORS" em vez de "faça login".
    resp = await client.get("/bookings", headers={"Origin": ORIGEM_PERMITIDA})
    assert resp.status_code == 401
    assert resp.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA
