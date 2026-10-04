"""Bancada da lição 07: N pessoas clicam em "reservar" no mesmo segundo.

Suba o FairFare e rode:
  uv run uvicorn app.main:app --port 8000
  uv run python chapters/04-o-banco-de-dados-de-verdade/bancada/corrida.py --n 5 --rodadas 10

Cada rodada cria um usuário e uma quadra novos e dispara N reservas idênticas ao mesmo
tempo. Cada request leva um X-Forwarded-For diferente: é o truque da lição 08 do cap. 3
(o uvicorn confia no loopback), para o rate limiter ver N clientes e não atrapalhar.
"""

import argparse
import asyncio
import itertools
import uuid
from collections import Counter

import httpx2

INICIO, FIM = "2030-06-01T10:00:00Z", "2030-06-01T12:00:00Z"
_ips = itertools.count(1)


def cliente_novo() -> dict[str, str]:
    k = next(_ips)
    return {"X-Forwarded-For": f"10.0.{k // 250}.{k % 250 + 1}"}


async def rodada(http: httpx2.AsyncClient, n: int) -> Counter:
    email = f"corrida-{uuid.uuid4().hex[:8]}@example.com"
    user = (
        await http.post("/users", json={"nome": "Corrida", "email": email}, headers=cliente_novo())
    ).json()
    quadra = (
        await http.post(
            "/resources",
            json={"nome": "Quadra da corrida", "tipo": "quadra"},
            headers=cliente_novo(),
        )
    ).json()
    corpo = {
        "user_id": user["id"],
        "resource_id": quadra["id"],
        "starts_at": INICIO,
        "ends_at": FIM,
    }
    respostas = await asyncio.gather(
        *(http.post("/bookings", json=corpo, headers=cliente_novo()) for _ in range(n))
    )
    return Counter(r.status_code for r in respostas)


async def main(n: int, rodadas: int, url: str) -> None:
    duplas = 0
    # Folgado de propósito: uma rodada que cai em deadlock leva quase meio minuto (lição 11).
    async with httpx2.AsyncClient(base_url=url, timeout=120) as http:
        for i in range(1, rodadas + 1):
            codigos = await rodada(http, n)
            if codigos.get(201, 0) > 1:
                duplas += 1
            resumo = "  ".join(f"{status}×{q}" for status, q in sorted(codigos.items()))
            print(f"rodada {i:2}: {resumo}")
    print(f"\nrodadas com mais de uma reserva criada: {duplas}/{rodadas}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--rodadas", type=int, default=10)
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(main(args.n, args.rodadas, args.url))
