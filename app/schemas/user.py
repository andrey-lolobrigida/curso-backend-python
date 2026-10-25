from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    nome: str
    email: EmailStr
    # Teto folgado: nenhuma senha de gente passa de 128, e a norma permite um máximo (lição 03).
    senha: str = Field(min_length=8, max_length=128)


# O que qualquer um vê de um usuário. Sem email: o email é de quem é dono dele.
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str


# O que só o próprio usuário vê. O senha_hash não sai em schema de resposta nenhum.
class UserMeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
