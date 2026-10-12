from pydantic import BaseModel


class GroupCreate(BaseModel):
    nome: str


class MemberAdd(BaseModel):
    user_id: int


class MemberOut(BaseModel):
    user_id: int
    nome: str


class GroupOut(BaseModel):
    id: int
    nome: str
    membros: list[MemberOut]
