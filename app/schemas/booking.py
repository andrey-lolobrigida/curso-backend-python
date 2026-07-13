from datetime import datetime

from pydantic import BaseModel, model_validator


class BookingCreate(BaseModel):
    user_id: int
    resource_id: int
    starts_at: datetime
    ends_at: datetime

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
