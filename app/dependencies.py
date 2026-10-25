from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.repositories import SessionRepository
from app.security import hash_token

# Lê o "Authorization: Bearer <token>" e confere o formato. Sem header, ou com outro
# esquema, responde 401 "Not authenticated" sozinho. Se o token vale, não é com ele.
bearer = HTTPBearer()


async def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    # A dependência e o service dividem a mesma sessão. Sem este begin(), a consulta abriria
    # a transação sozinha (autobegin), e o begin() do service estouraria logo depois.
    # Assim ela abre e fecha a própria transação de leitura, e o service segue dono da dele.
    # O User continua legível depois do commit: expire_on_commit=False.
    async with db.begin():
        user = await SessionRepository(db).user_by_token_hash(hash_token(cred.credentials))
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="token inválido ou vencido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
