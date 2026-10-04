from datetime import UTC, datetime

from pydantic import BaseModel, field_validator, model_validator


class BookingCreate(BaseModel):
    user_id: int
    resource_id: int
    starts_at: datetime
    ends_at: datetime

    @field_validator("starts_at", "ends_at")
    @classmethod
    def sem_fuso_e_utc(cls, valor: datetime) -> datetime:
        # Horário sem fuso é ambíguo: 10h de onde? Decisão declarada (lição 04):
        # quem não diz o fuso está falando em UTC. Escrita aqui, e não deixada para o
        # driver do banco, que resolveria pelo relógio da máquina onde o app roda.
        if valor.tzinfo is None:
            return valor.replace(tzinfo=UTC)
        return valor

    @model_validator(mode="after")
    def fim_depois_do_inicio(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at deve ser depois de starts_at")
        return self


class BookingOut(BaseModel):
    id: int
    user_id: int
    resource_id: int
    starts_at: datetime
    ends_at: datetime
    user_nome: str
    resource_nome: str
