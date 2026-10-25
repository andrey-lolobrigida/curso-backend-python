from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import bearer, get_current_user
from app.models import User
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


# O login é público; o logout, não. Por isso o get_current_user vem aqui, por parâmetro,
# e não no router inteiro.
@router.post("/logout", status_code=204)
async def logout(
    # O eu não é usado no corpo. Ele está aqui para a dependência rodar: token vencido ou
    # desconhecido leva 401 antes de chegar ao DELETE.
    eu: User = Depends(get_current_user),
    # O mesmo bearer do get_current_user: o FastAPI o resolve uma vez só por request.
    cred: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    await AuthService(db).logout(cred.credentials)
