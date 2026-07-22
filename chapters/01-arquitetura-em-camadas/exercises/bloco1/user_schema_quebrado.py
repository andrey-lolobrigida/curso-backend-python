from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    nome: str
    email: EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    internal_note: str
