from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
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


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    return await UserRepository(db).list_all()


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await UserRepository(db).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="usuário não existe")
    return user
