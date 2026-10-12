from decimal import Decimal

import pytest
from entrada import valor_do_pedido
from taxa import taxa_de_servico


@pytest.mark.parametrize(
    "conta, taxa",
    [("10.00", "1.00"), ("0.25", "0.03"), ("0.35", "0.04"), ("10.05", "1.01"), ("80.15", "8.02")],
)
def test_taxa_meio_centavo_para_cima(conta, taxa):
    assert taxa_de_servico(Decimal(conta)) == Decimal(taxa)


@pytest.mark.parametrize(
    "bruto, esperado", [("80.10", "80.10"), ("0.1", "0.1"), ("19.99", "19.99")]
)
def test_valor_do_pedido_exato(bruto, esperado):
    assert valor_do_pedido(f'{{"valor": {bruto}}}') == Decimal(esperado)
