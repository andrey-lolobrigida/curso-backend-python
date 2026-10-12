"""O tipo Dinheiro: o que entra pela API (lição 06)."""

from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas import Dinheiro


class Conta(BaseModel):
    valor: Dinheiro


def test_string_entra_exata():
    assert Conta.model_validate_json('{"valor": "80.10"}').valor == Decimal("80.10")


def test_numero_json_entra_como_decimal():
    assert Conta.model_validate_json('{"valor": 80.10}').valor == Decimal("80.10")


def test_sai_como_string():
    assert Conta(valor=Decimal("80.10")).model_dump_json() == '{"valor":"80.10"}'


@pytest.mark.parametrize(
    "bruto",
    ['"80.105"', "80.105", '"-1"', '"0"', '"NaN"', "0.30000000000000004", '"1234567890123.45"'],
)
def test_valores_invalidos_sao_recusados(bruto):
    with pytest.raises(ValidationError):
        Conta.model_validate_json(f'{{"valor": {bruto}}}')
