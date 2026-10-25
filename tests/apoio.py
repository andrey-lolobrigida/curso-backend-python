"""Atalhos para montar o cenário dos testes pela API, como um cliente faria.

Uma pessoa = um cliente = um IP: cada pessoa do teste tem o próprio AsyncClient, com o
próprio crachá no header e o próprio balde no rate limiter, como gente de verdade em
máquinas diferentes (lição 05 do cap. 6)."""

from contextlib import contextmanager
from dataclasses import dataclass

from httpx2 import AsyncClient
from sqlalchemy import event

SENHA_DE_TESTE = "senha-de-teste"


@dataclass
class Pessoa:
    """Alguém cadastrado e logado. O client já manda o Authorization dela em toda request."""

    id: int
    nome: str
    email: str
    client: AsyncClient


async def cria_usuario(client, email="ana@example.com", nome="Ana", senha=SENHA_DE_TESTE):
    resp = await client.post("/users", json={"nome": nome, "email": email, "senha": senha})
    assert resp.status_code == 201
    return resp.json()


async def faz_login(client, email, senha=SENHA_DE_TESTE) -> str:
    resp = await client.post("/auth/login", json={"email": email, "senha": senha})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def cria_recurso(client):
    resp = await client.post("/resources", json={"nome": "Quadra 1", "tipo": "quadra"})
    assert resp.status_code == 201
    return resp.json()


async def cria_reserva(client, resource_id, starts_at, ends_at):
    # Sem user_id: a reserva é de quem está logado no client (lição 05 do cap. 6).
    return await client.post(
        "/bookings",
        json={
            "resource_id": resource_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
        },
    )


@contextmanager
def conta_consultas(engine):
    """Conta os comandos SQL que passam pela engine dentro do bloco (lição 03)."""
    contagem = {"n": 0}

    def conta(*args):
        contagem["n"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", conta)
    try:
        yield contagem
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", conta)


async def cria_grupo(client, nome="Viagem"):
    resp = await client.post("/groups", json={"nome": nome})
    assert resp.status_code == 201
    return resp.json()


async def adiciona_membro(client, group_id, user_id):
    return await client.post(f"/groups/{group_id}/members", json={"user_id": user_id})


async def cria_despesa(client, group_id, valor, participantes=None, descricao="Jantar"):
    # Sem paid_by: quem paga é quem lança, a pessoa do client (lição 12 do cap. 6).
    corpo = {"descricao": descricao, "valor": valor}
    if participantes is not None:
        corpo["participantes"] = participantes
    return await client.post(f"/groups/{group_id}/expenses", json=corpo)


async def quita(client, group_id, de, valor):
    # Sem para_user_id: quem recebe é quem lança, a pessoa do client (lição 12 do cap. 6).
    return await client.post(
        f"/groups/{group_id}/settlements", json={"de_user_id": de, "valor": valor}
    )
