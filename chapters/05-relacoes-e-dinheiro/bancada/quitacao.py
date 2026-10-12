"""Bancada da lição 11: o Bruno clica em "quitar" N vezes no mesmo segundo.

Irmão do corrida.py do capítulo 4, com dinheiro no lugar da quadra. Suba o FairFare e rode:
  uv run uvicorn app.main:app --port 8000
  uv run python chapters/05-relacoes-e-dinheiro/bancada/quitacao.py --n 5 --rodadas 10

Cada rodada monta um grupo novo pela API: Ana, Bruno e Carla, e uma despesa de 100.00 paga
pela Ana e dividida entre os três (Ana +66.66, Bruno -33.33, Carla -33.33). Depois dispara
N quitações iguais ao mesmo tempo: Bruno paga 30.00 à Ana. Pela regra, só uma cabe na
dívida. A rodada imprime os status e o saldo final do Bruno.

Cada request leva um X-Forwarded-For diferente: é o truque da lição 08 do cap. 3
(o uvicorn confia no loopback), para o rate limiter ver N clientes e não atrapalhar.

O QUE O SCRIPT FAZ NO BANCO DE DESENVOLVIMENTO (o fairfare do compose):

  cria   por rodada, 3 usuários (e-mails em @bancada-l11.fairfare.dev), o grupo
         "bancada/quitacao.py (lição 11)", os 3 membros, 1 despesa e as quitações;
  apaga  tudo isso no começo e no fim, em ordem de chave estrangeira (quitações, partes,
         despesas, membros, grupos, usuários).

A limpeza só mira o que o script cria: grupos com esse nome cujos membros são TODOS
usuários da bancada, e usuários da bancada que nada mais referencia. As sequências de id
NÃO voltam (mesmo motivo do saldos.py da lição 09).
"""

import argparse
import asyncio
import itertools
import sys
import uuid
from collections import Counter
from pathlib import Path

# A raiz do projeto no sys.path: o projeto não é instalado (ver conta_consultas.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import httpx2  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402

GRUPO = "bancada/quitacao.py (lição 11)"
DOMINIO = "%@bancada-l11.fairfare.dev"  # padrão do LIKE: todo e-mail que a bancada cria
_ips = itertools.count(1)


def cliente_novo() -> dict[str, str]:
    k = next(_ips)
    return {"X-Forwarded-For": f"10.1.{k // 250}.{k % 250 + 1}"}


async def apaga_sobras() -> None:
    """Apaga o que o script criou, e só isso, em ordem de chave estrangeira."""
    async with SessionLocal() as db, db.begin():
        # Os ids são lidos uma vez, antes de apagar: depois que os membros somem, a
        # condição "todo membro é da bancada" valeria para qualquer grupo vazio.
        ids = list(
            await db.scalars(
                text(
                    """
                    SELECT g.id FROM groups g
                    WHERE g.nome = :grupo
                      AND NOT EXISTS (
                        SELECT 1 FROM group_members m JOIN users u ON u.id = m.user_id
                        WHERE m.group_id = g.id AND u.email NOT LIKE :dominio
                      )
                    """
                ),
                {"grupo": GRUPO, "dominio": DOMINIO},
            )
        )
        alvo = {"ids": ids}
        await db.execute(
            text("DELETE FROM settlements WHERE group_id = ANY(CAST(:ids AS int[]))"), alvo
        )
        await db.execute(
            text(
                """
                DELETE FROM expense_shares
                WHERE expense_id IN (
                    SELECT id FROM expenses WHERE group_id = ANY(CAST(:ids AS int[]))
                )
                """
            ),
            alvo,
        )
        await db.execute(
            text("DELETE FROM expenses WHERE group_id = ANY(CAST(:ids AS int[]))"), alvo
        )
        await db.execute(
            text("DELETE FROM group_members WHERE group_id = ANY(CAST(:ids AS int[]))"), alvo
        )
        await db.execute(text("DELETE FROM groups WHERE id = ANY(CAST(:ids AS int[]))"), alvo)
        # Usuários da bancada que nada mais referencia. Se algum ficou preso a outro dado,
        # ele fica: melhor uma sobra do que um DELETE que estoura na chave estrangeira.
        await db.execute(
            text(
                """
                DELETE FROM users u
                WHERE u.email LIKE :dominio
                  AND NOT EXISTS (SELECT 1 FROM group_members m WHERE m.user_id = u.id)
                  AND NOT EXISTS (SELECT 1 FROM expenses e WHERE e.paid_by = u.id)
                  AND NOT EXISTS (SELECT 1 FROM expense_shares p WHERE p.user_id = u.id)
                  AND NOT EXISTS (
                    SELECT 1 FROM settlements s
                    WHERE s.de_user_id = u.id OR s.para_user_id = u.id
                  )
                  AND NOT EXISTS (SELECT 1 FROM bookings b WHERE b.user_id = u.id)
                """
            ),
            {"dominio": DOMINIO},
        )


async def post(http: httpx2.AsyncClient, url: str, corpo: dict) -> dict:
    resp = await http.post(url, json=corpo, headers=cliente_novo())
    if resp.status_code != 201:
        raise SystemExit(f"POST {url} devolveu {resp.status_code}: {resp.text}")
    return resp.json()


async def monta_grupo(http: httpx2.AsyncClient) -> tuple[int, int, int]:
    """Ana pagou 100.00 entre os três. Devolve (grupo, ana, bruno)."""
    sufixo = uuid.uuid4().hex[:8]
    ids = []
    for nome in ["Ana", "Bruno", "Carla"]:
        email = f"{nome.lower()}-{sufixo}@bancada-l11.fairfare.dev"
        ids.append((await post(http, "/users", {"nome": nome, "email": email}))["id"])
    grupo = (await post(http, "/groups", {"nome": GRUPO}))["id"]
    for user_id in ids:
        await post(http, f"/groups/{grupo}/members", {"user_id": user_id})
    corpo = {"paid_by": ids[0], "descricao": "Chalé", "valor": "100.00"}
    await post(http, f"/groups/{grupo}/expenses", corpo)
    return grupo, ids[0], ids[1]


async def rodada(http: httpx2.AsyncClient, n: int) -> tuple[Counter, str]:
    grupo, ana, bruno = await monta_grupo(http)
    corpo = {"de_user_id": bruno, "para_user_id": ana, "valor": "30.00"}
    respostas = await asyncio.gather(
        *(
            http.post(f"/groups/{grupo}/settlements", json=corpo, headers=cliente_novo())
            for _ in range(n)
        )
    )
    saldos = (await http.get(f"/groups/{grupo}/balances", headers=cliente_novo())).json()
    saldo_bruno = next(s["saldo"] for s in saldos if s["user_id"] == bruno)
    return Counter(r.status_code for r in respostas), saldo_bruno


async def main(n: int, rodadas: int, url: str) -> None:
    alem = 0
    await apaga_sobras()
    try:
        async with httpx2.AsyncClient(base_url=url, timeout=120) as http:
            for i in range(1, rodadas + 1):
                codigos, saldo_bruno = await rodada(http, n)
                if codigos.get(201, 0) > 1:
                    alem += 1
                resumo = "  ".join(f"{status}×{q}" for status, q in sorted(codigos.items()))
                print(f"rodada {i:2}: {resumo}  saldo do Bruno: {saldo_bruno}")
        print(f"\nrodadas em que o Bruno pagou além da dívida: {alem}/{rodadas}")
    finally:
        await apaga_sobras()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--rodadas", type=int, default=10)
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(main(args.n, args.rodadas, args.url))
