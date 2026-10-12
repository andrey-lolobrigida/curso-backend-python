"""A regra do centavo (lição 07)."""

from decimal import Decimal

import pytest

from app.services.divisao import dividir


def test_cem_entre_tres():
    assert dividir(Decimal("100.00"), [3, 1, 2]) == {
        1: Decimal("33.34"),
        2: Decimal("33.33"),
        3: Decimal("33.33"),
    }


def test_um_centavo_entre_tres():
    assert dividir(Decimal("0.01"), [1, 2, 3]) == {
        1: Decimal("0.01"),
        2: Decimal("0.00"),
        3: Decimal("0.00"),
    }


def test_divisao_exata_nao_inventa_centavo():
    assert dividir(Decimal("90.00"), [1, 2, 3]) == {u: Decimal("30.00") for u in (1, 2, 3)}


def test_a_soma_sempre_fecha():
    # Centenas de totais × tamanhos de grupo. Sem hypothesis: um laço basta.
    for centavos in range(1, 1001, 7):
        total = Decimal(centavos) / 100
        for n in range(1, 13):
            partes = dividir(total, list(range(1, n + 1)))
            assert sum(partes.values()) == total
            assert max(partes.values()) - min(partes.values()) <= Decimal("0.01")
            assert all(p.as_tuple().exponent == -2 for p in partes.values())


@pytest.mark.parametrize("participantes", [[], [1, 1]])
def test_participantes_invalidos(participantes):
    with pytest.raises(ValueError):
        dividir(Decimal("10.00"), participantes)
