"""Bancada da lição 05: o pool encontra o teto.

Dois experimentos, cada um segurando conexões com pg_sleep para que elas não voltem logo:

  # 1. O pool estoura: um processo, o pool do app (5 + 10), mais tarefas que conexões.
  uv run python chapters/04-o-banco-de-dados-de-verdade/bancada/pool.py pool --tarefas 20

  # 2. O servidor estoura: vários pools (um por "processo"), somando mais que max_connections.
  uv run python chapters/04-o-banco-de-dados-de-verdade/bancada/pool.py servidor --processos 4 --por-processo 30

No experimento 2, cada engine faz o papel do pool de um worker do uvicorn. Para o
Postgres não há diferença: ele só conta conexões, não sabe de onde elas vêm.
"""

import argparse
import asyncio
from collections import Counter

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

URL = "postgresql+asyncpg://fairfare:fairfare@localhost:5432/fairfare"  # a do app/database.py
SEGURA = 3  # segundos que cada tarefa segura a conexão


async def segurar(engine: AsyncEngine) -> str:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT pg_sleep(:s)"), {"s": SEGURA})
        return "ok"
    except Exception as erro:  # noqa: BLE001 — a bancada quer ver qualquer erro
        return f"{type(erro).__name__}: {erro}".splitlines()[0]


def relatorio(resultados: list[str]) -> None:
    for resultado, quantas in Counter(resultados).most_common():
        print(f"{quantas:4} × {resultado}")


async def experimento_pool(tarefas: int) -> None:
    # Os mesmos números do app/database.py, com timeout curto para não esperar 30s.
    engine = create_async_engine(URL, pool_size=5, max_overflow=10, pool_timeout=2)
    relatorio(await asyncio.gather(*(segurar(engine) for _ in range(tarefas))))
    await engine.dispose()


async def experimento_servidor(processos: int, por_processo: int) -> None:
    engines = [
        create_async_engine(URL, pool_size=por_processo, max_overflow=0, pool_timeout=10)
        for _ in range(processos)
    ]
    tarefas = [segurar(e) for e in engines for _ in range(por_processo)]
    print(f"{processos} processos × {por_processo} conexões = {len(tarefas)} pedidas")
    relatorio(await asyncio.gather(*tarefas))
    for e in engines:
        await e.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="experimento", required=True)
    p = sub.add_parser("pool")
    p.add_argument("--tarefas", type=int, default=20)
    s = sub.add_parser("servidor")
    s.add_argument("--processos", type=int, default=4)
    s.add_argument("--por-processo", type=int, default=30)
    args = parser.parse_args()
    if args.experimento == "pool":
        asyncio.run(experimento_pool(args.tarefas))
    else:
        asyncio.run(experimento_servidor(args.processos, args.por_processo))


if __name__ == "__main__":
    main()
