from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.dinheiro import Dinheiro


class SettlementCreate(BaseModel):
    # Sem para_user_id: quem recebe é quem lança, e quem lança vem do token (lição 12 do
    # cap. 6). O "de diferente de para" saiu daqui para o service: o schema não sabe quem pede.
    de_user_id: int
    valor: Dinheiro


class SettlementOut(BaseModel):
    id: int
    group_id: int
    de_user_id: int
    para_user_id: int
    valor: Decimal
    criada_em: datetime
