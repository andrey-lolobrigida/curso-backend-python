from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.dinheiro import Dinheiro


class ExpenseCreate(BaseModel):
    # Sem paid_by: quem paga é quem lança, e quem lança vem do token (lição 12 do cap. 6).
    # Um paid_by no corpo é descartado, como todo campo que o schema não declara.
    descricao: str
    valor: Dinheiro
    # Sem a lista: o grupo todo participa.
    participantes: list[int] | None = Field(default=None, min_length=1)

    @field_validator("participantes")
    @classmethod
    def sem_repeticao(cls, valor: list[int] | None) -> list[int] | None:
        if valor is not None and len(set(valor)) != len(valor):
            raise ValueError("participantes não pode ter ids repetidos")
        return valor


class ShareOut(BaseModel):
    user_id: int
    valor: Decimal


class ExpenseOut(BaseModel):
    id: int
    group_id: int
    paid_by: int
    descricao: str
    valor: Decimal
    criada_em: datetime
    partes: list[ShareOut]
