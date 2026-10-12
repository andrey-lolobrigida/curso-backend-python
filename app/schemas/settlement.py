from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, model_validator

from app.schemas.dinheiro import Dinheiro


class SettlementCreate(BaseModel):
    de_user_id: int
    para_user_id: int
    valor: Dinheiro

    @model_validator(mode="after")
    def de_diferente_de_para(self):
        if self.de_user_id == self.para_user_id:
            raise ValueError("ninguém quita uma dívida consigo mesmo")
        return self


class SettlementOut(BaseModel):
    id: int
    group_id: int
    de_user_id: int
    para_user_id: int
    valor: Decimal
    criada_em: datetime
