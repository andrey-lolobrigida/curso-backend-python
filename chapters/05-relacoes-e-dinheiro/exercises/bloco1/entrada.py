"""Bloco 1.2 — o valor que chega como número. (QUEBRADO DE PROPÓSITO)"""

import json
from decimal import Decimal


def valor_do_pedido(corpo: str) -> Decimal:
    """Lê o campo "valor" de um JSON vindo de um cliente que manda número, não string.

    EXERCÍCIO 1.2: esta função tem um defeito de propósito. Os testes mostram qual.
    """
    return Decimal(json.loads(corpo)["valor"])
