"""Bloco 1.1 — a taxa de serviço. (QUEBRADA DE PROPÓSITO)"""

from decimal import Decimal

CENTAVO = Decimal("0.01")


def taxa_de_servico(conta: Decimal) -> Decimal:
    """Os 10% do garçom, ao centavo. Regra da casa: meio centavo arredonda PARA CIMA.

    EXERCÍCIO 1.1: esta função tem um defeito de propósito. Os testes mostram qual.
    """
    return (conta * Decimal("0.10")).quantize(CENTAVO)
