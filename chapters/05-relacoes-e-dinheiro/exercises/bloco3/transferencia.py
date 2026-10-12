"""Bloco 3.2 — a transferência entre contas. (QUEBRADA DE PROPÓSITO)

Os cadeados estão lá, em ordem de id, como na lição 11. Mesmo assim, duas
transferências ao mesmo tempo gastam o mesmo saldo duas vezes.
"""

from collections.abc import Awaitable, Callable
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

LE_SALDO = text("SELECT saldo FROM bloco3_contas WHERE id = :id")
TRANCA = text("SELECT id FROM bloco3_contas WHERE id IN (:de, :para) ORDER BY id FOR UPDATE")
DEBITA = text("UPDATE bloco3_contas SET saldo = saldo - :valor WHERE id = :id")
CREDITA = text("UPDATE bloco3_contas SET saldo = saldo + :valor WHERE id = :id")


class SaldoInsuficiente(Exception):
    pass


async def transferir(
    engine: AsyncEngine,
    de: int,
    para: int,
    valor: Decimal,
    depois_de_ler: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """Passa `valor` da conta `de` para a conta `para`, se `de` tiver saldo.

    `depois_de_ler` é um gancho do teste: ele roda logo depois da leitura do saldo.

    EXERCÍCIO 3.2: esta função tem um defeito de propósito. O teste mostra qual.
    """
    async with engine.begin() as conn:
        saldo = await conn.scalar(LE_SALDO, {"id": de})
        if depois_de_ler is not None:
            await depois_de_ler()
        # Os dois cadeados num comando só, em ordem de id: sem ciclo, sem deadlock.
        await conn.execute(TRANCA, {"de": de, "para": para})
        if saldo < valor:
            raise SaldoInsuficiente(f"a conta {de} tem {saldo}, e a transferência é de {valor}")
        await conn.execute(DEBITA, {"valor": valor, "id": de})
        await conn.execute(CREDITA, {"valor": valor, "id": para})
