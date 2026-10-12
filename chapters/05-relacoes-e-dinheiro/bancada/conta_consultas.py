"""Bancada da lição 03: quantas consultas custa um GET /bookings?

ATENÇÃO: o seed APAGA users, resources e bookings do banco de desenvolvimento
(e, via CASCADE, tudo o que depender deles). Suba o banco e semeie 2000 reservas:

  docker compose up -d --wait
  docker compose exec -T postgres psql -U fairfare -d fairfare -v linhas=2000 \\
    < chapters/04-o-banco-de-dados-de-verdade/bancada/seed.sql

Depois:

  # O endpoint de verdade, em processo, contando o que passa pela engine do app.
  uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py

  # A mesma listagem direto pelo ORM, com joinedload nas duas relações.
  uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py --joinedload

Nenhum uvicorn: o httpx2 fala com o app pelo ASGITransport, dentro deste processo.
É isso que deixa o script pendurar o contador na mesma engine que o app usa.
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

# A raiz do projeto no sys.path: sem isso, `import app` não acha o pacote,
# porque o Python põe no path a pasta do script, não a pasta de onde você rodou.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from httpx2 import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import joinedload  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Booking  # noqa: E402
from tests.apoio import conta_consultas  # noqa: E402  (o mesmo contador do guardião)


async def pelo_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://bancada") as http:
        # Aquecimento: abrir a primeira conexão do pool (socket, autenticação) custa
        # tempo que não é do GET /bookings. Fica fora do cronômetro.
        await http.get("/users")

        with conta_consultas(engine) as contagem:
            inicio = time.perf_counter()
            resp = await http.get("/bookings")
            ms = (time.perf_counter() - inicio) * 1000

    resp.raise_for_status()
    print(f"reservas={len(resp.json())} consultas={contagem['n']} tempo={ms:.0f}ms")


async def com_joinedload() -> None:
    async with SessionLocal() as db:
        await db.scalars(select(Booking).limit(1))  # aquecimento, como acima

        with conta_consultas(engine) as contagem:
            inicio = time.perf_counter()
            stmt = select(Booking).options(joinedload(Booking.user), joinedload(Booking.resource))
            reservas = list(await db.scalars(stmt))
            nomes = [(b.user.nome, b.resource.nome) for b in reservas]
            ms = (time.perf_counter() - inicio) * 1000

    print(f"reservas={len(nomes)} consultas={contagem['n']} tempo={ms:.0f}ms (joinedload)")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--joinedload", action="store_true")
    args = parser.parse_args()
    try:
        await (com_joinedload() if args.joinedload else pelo_endpoint())
    finally:
        await engine.dispose()


asyncio.run(main())
