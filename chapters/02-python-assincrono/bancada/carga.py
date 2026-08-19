"""Bancada: dispara N requests ao mesmo tempo e cronometra o total.

Uso: uv run python chapters/02-python-assincrono/bancada/carga.py <url> [n]
"""

import asyncio
import sys
import time

import httpx2


async def uma(client: httpx2.AsyncClient, url: str) -> int:
    resposta = await client.get(url)
    return resposta.status_code


async def main() -> None:
    url = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    async with httpx2.AsyncClient(timeout=120) as client:
        comeco = time.perf_counter()
        codigos = await asyncio.gather(*(uma(client, url) for _ in range(n)))
        total = time.perf_counter() - comeco

    print(f"{n} requests em {total:.2f}s  (status: {set(codigos)})")


asyncio.run(main())
