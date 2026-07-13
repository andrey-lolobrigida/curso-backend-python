from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, model_validator


class UserCreate(BaseModel):
    nome: str
    email: EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str


class ResourceCreate(BaseModel):
    nome: str
    tipo: str


class ResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    tipo: str


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
