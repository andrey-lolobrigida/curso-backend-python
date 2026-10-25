from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.repositories import UserRepository
from app.schemas import UserCreate, UserMeOut, UserOut
from app.security import hash_senha

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", status_code=201, response_model=UserMeOut)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # O hash vem antes do begin(): ~55 ms de conta sem segurar uma conexão do pool.
    senha_hash = await hash_senha(user.senha)
    # Sem service, quem diz o que é "uma operação" é o router (cap. 5, lição 08).
    try:
        async with db.begin():
            return await UserRepository(db).create(
                nome=user.nome, email=user.email, senha_hash=senha_hash
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail="email já cadastrado")


# Daqui para baixo, login exigido rota a rota: o POST /users lá em cima é público.
@router.get("", response_model=list[UserOut], dependencies=[Depends(get_current_user)])
async def list_users(db: AsyncSession = Depends(get_db)):
    return await UserRepository(db).list_all()


# Antes do /{user_id}: as rotas casam na ordem em que foram declaradas, e "me" viraria
# um user_id que não é inteiro (422).
@router.get("/me", response_model=UserMeOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(get_current_user)])
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await UserRepository(db).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="usuário não existe")
    return user
