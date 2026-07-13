import sqlite3

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

DB_PATH = "fairfare.db"

app = FastAPI(title="FairFare")


class UserCreate(BaseModel):
    nome: str
    email: EmailStr


class UserOut(BaseModel):
    id: int
    nome: str
    email: str


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables() -> None:
    conn = get_conn()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "nome TEXT NOT NULL, "
        "email TEXT NOT NULL UNIQUE)"
    )
    conn.commit()
    conn.close()


ensure_tables()


@app.post("/users", status_code=201, response_model=UserOut)
def create_user(user: UserCreate):
    conn = get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO users (nome, email) VALUES (?, ?)",
            (user.nome, user.email),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="email já cadastrado")
    row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    conn.close()
    return dict(row)


@app.get("/users", response_model=list[UserOut])
def list_users():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="usuário não existe")
    return dict(row)
