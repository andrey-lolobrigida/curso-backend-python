from decimal import Decimal
from typing import Annotated

from pydantic import Field

# Dinheiro que entra pela API: Decimal, positivo, no máximo 2 casas e 12 dígitos
# (o mesmo Numeric(12, 2) do banco). Sai como string no JSON: o JSON não tem decimal (lição 06).
Dinheiro = Annotated[Decimal, Field(max_digits=12, decimal_places=2, gt=0)]
