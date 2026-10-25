from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import LoginIn, TokenOut
from app.services import AuthService, InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, db: AsyncSession = Depends(get_db)):
    try:
        token = await AuthService(db).login(data.email, data.senha)
    except InvalidCredentialsError:
        # A mesma resposta para email inexistente, senha errada e conta sem senha.
        # Todo 401 diz como se apresentar: o WWW-Authenticate da lição 01.
        raise HTTPException(
            status_code=401,
            detail="email ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(access_token=token)
