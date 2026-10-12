from decimal import ROUND_DOWN, Decimal

CENTAVO = Decimal("0.01")


def dividir(total: Decimal, participantes: list[int]) -> dict[int, Decimal]:
    """Divide `total` em partes iguais, ao centavo, sem perder nenhum (lição 07).

    Cada um recebe o piso da divisão. Os centavos que sobram vão, um a um,
    aos menores user_id: uma regra arbitrária, mas escrita e sempre a mesma.
    """
    if not participantes or len(set(participantes)) != len(participantes):
        raise ValueError("participantes precisa ter ids distintos e não pode ser vazio")
    ordem = sorted(participantes)
    base = (total / len(ordem)).quantize(CENTAVO, rounding=ROUND_DOWN)
    sobra = int((total - base * len(ordem)) / CENTAVO)
    return {user_id: base + (CENTAVO if i < sobra else 0) for i, user_id in enumerate(ordem)}
