"""Bancada da lição 09: o mesmo check-then-act da lição 08, em cada nível de isolamento.

B=chapters/04-o-banco-de-dados-de-verdade/bancada
uv run python $B/isolamento.py --nivel read-committed
uv run python $B/isolamento.py --nivel repeatable-read
uv run python $B/isolamento.py --nivel serializable
uv run python $B/isolamento.py --nivel serializable --recursos diferentes
uv run python $B/isolamento.py --nivel serializable --retry
"""

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from transacao import INICIO, URL, preparar, rodada, tentar

NIVEIS = {
    "read-committed": "READ COMMITTED",
    "repeatable-read": "REPEATABLE READ",
    "serializable": "SERIALIZABLE",
}


async def tentar_com_retry(
    engine: AsyncEngine, nivel: str, recurso: int, barreira: asyncio.Barrier
) -> str:
    # O retry obrigatório do SERIALIZABLE: quando o banco aborta, a transação morreu.
    # Tentar de novo é começar OUTRA, do zero — verificar de novo, decidir de novo.
    resultado = await tentar(engine, nivel, recurso, barreira)
    tentativa = 1
    while resultado == "abortada" and tentativa < 5:
        tentativa += 1
        resultado = await tentar(engine, nivel, recurso, None)
    return resultado if tentativa == 1 else f"{resultado} (tentativa {tentativa})"


async def rodada_com_retry(engine: AsyncEngine, nivel: str, recursos: tuple[int, int]) -> list[str]:
    barreira = asyncio.Barrier(2)
    resultados = await asyncio.gather(
        *(tentar_com_retry(engine, nivel, r, barreira) for r in recursos)
    )
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM bancada_reservas WHERE starts_at = :i"), {"i": INICIO})
    return list(resultados)


async def main(nivel: str, recursos: tuple[int, int], retry: bool) -> None:
    engine = create_async_engine(URL)
    await preparar(engine)
    executar = rodada_com_retry if retry else rodada
    duplas = abortadas = 0
    for i in range(1, 11):
        resultado = await executar(engine, nivel, recursos)
        duplas += sum(r.startswith("201") for r in resultado) == 2
        abortadas += any(r.startswith("abortada") for r in resultado)
        print(f"rodada {i:2}: {' + '.join(resultado)}")
    print(
        f"\n{nivel}, recursos {recursos}: duas reservas em {duplas}/10, abortou em {abortadas}/10"
    )
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nivel", choices=NIVEIS, default="read-committed")
    parser.add_argument("--recursos", choices=["mesmo", "diferentes"], default="mesmo")
    parser.add_argument("--retry", action="store_true")
    args = parser.parse_args()
    recursos = (1, 1) if args.recursos == "mesmo" else (1, 2)
    asyncio.run(main(NIVEIS[args.nivel], recursos, args.retry))
