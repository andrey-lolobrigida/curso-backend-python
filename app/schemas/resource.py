from pydantic import BaseModel, ConfigDict


class ResourceCreate(BaseModel):
    nome: str
    tipo: str


class ResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    tipo: str
