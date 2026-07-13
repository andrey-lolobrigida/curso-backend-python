from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

app = FastAPI(title="FairFare")


class UserCreate(BaseModel):
    nome: str
    email: EmailStr


class UserOut(BaseModel):
    id: int
    nome: str
    email: str


users: dict[int, dict] = {}
_next_id = 1


@app.post("/users", status_code=201, response_model=UserOut)
def create_user(user: UserCreate):
    global _next_id
    new_user = {"id": _next_id, "nome": user.nome, "email": user.email}
    users[_next_id] = new_user
    _next_id += 1
    return new_user


@app.get("/users", response_model=list[UserOut])
def list_users():
    return list(users.values())


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    if user_id not in users:
        raise HTTPException(status_code=404, detail="usuário não existe")
    return users[user_id]
