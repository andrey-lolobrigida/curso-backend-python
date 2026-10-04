"""Bancada da lição 08: transação não é cadeado.

Duas transações fazem o check-then-act do BookingService.create ao mesmo tempo, com uma
barreira entre a verificação e o insert: as duas olham, e só depois as duas agem.
Roda numa tabela própria (bancada_reservas), recriada a cada execução, sem mexer nas
tabelas do app.

  uv run python chapters/04-o-banco-de-dados-de-verdade/bancada/transacao.py
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

URL = "postgresql+asyncpg://fairfare:fairfare@localhost:5432/fairfare"  # a do app/database.py
INICIO = datetime(2030, 6, 1, 10, 0, tzinfo=UTC)
FIM = datetime(2030, 6, 1, 12, 0, tzinfo=UTC)

PREPARO = [
    "DROP TABLE IF EXISTS bancada_reservas",
    """CREATE TABLE bancada_reservas (
           id serial PRIMARY KEY,
           resource_id int NOT NULL,
           starts_at timestamptz NOT NULL,
           ends_at timestamptz NOT NULL)""",
    # Dez mil reservas em outros horários, um índice e estatísticas: cara de banco de verdade.
    """INSERT INTO bancada_reservas (resource_id, starts_at, ends_at)
       SELECT i % 50 + 1,
              timestamptz '2031-01-01 00:00+00' + (i / 50) * interval '1 hour',
              timestamptz '2031-01-01 00:00+00' + (i / 50 + 1) * interval '1 hour'
       FROM generate_series(0, 9999) i""",
    "CREATE INDEX ON bancada_reservas (resource_id, starts_at)",
    "ANALYZE bancada_reservas",
]

VERIFICA = text(
    "SELECT count(*) FROM bancada_reservas "
    "WHERE resource_id = :r AND starts_at < :fim AND ends_at > :inicio"
)
INSERE = text(
    "INSERT INTO bancada_reservas (resource_id, starts_at, ends_at) VALUES (:r, :inicio, :fim)"
)


async def preparar(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for sql in PREPARO:
            await conn.execute(text(sql))


async def tentar(
    engine: AsyncEngine, nivel: str, recurso: int, barreira: asyncio.Barrier | None
) -> str:
    params = {"r": recurso, "inicio": INICIO, "fim": FIM}
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level=nivel)
        try:
            async with conn.begin():
                ocupado = await conn.scalar(VERIFICA, params)
                if barreira is not None:
                    await barreira.wait()  # as duas já olharam; agora as duas agem
                if ocupado:
                    return "409"
                await conn.execute(INSERE, params)
            return "201"
        except DBAPIError as erro:
            if getattr(erro.orig, "sqlstate", None) == "40001":  # serialization_failure
                return "abortada"
            raise


async def rodada(engine: AsyncEngine, nivel: str, recursos: tuple[int, int]) -> list[str]:
    barreira = asyncio.Barrier(2)
    resultados = await asyncio.gather(*(tentar(engine, nivel, r, barreira) for r in recursos))
    async with engine.begin() as conn:  # apaga o que a rodada gravou: a próxima começa limpa
        await conn.execute(text("DELETE FROM bancada_reservas WHERE starts_at = :i"), {"i": INICIO})
    return list(resultados)


async def main() -> None:
    engine = create_async_engine(URL)
    await preparar(engine)
    duplas = 0
    for i in range(1, 11):
        resultado = await rodada(engine, "READ COMMITTED", (1, 1))
        duplas += resultado.count("201") == 2
        print(f"rodada {i:2}: {' + '.join(resultado)}")
    print(f"\nREAD COMMITTED, mesma quadra: duas reservas em {duplas}/10 rodadas")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
