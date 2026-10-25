from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class LoginIn(BaseModel):
    # A mesma régua do cadastro: o EmailStr baixa o domínio aqui também, senão quem
    # digita igual nas duas telas não entra. O teto da senha também é o mesmo (lição 03).
    # Sem min_length: o login só confere a senha que chegou.
    email: EmailStr
    senha: str = Field(max_length=128)


class TokenOut(BaseModel):
    access_token: str
    # "bearer" = "portador": quem mostrar o token, entra. Por isso ele não pode vazar.
    token_type: Literal["bearer"] = "bearer"
