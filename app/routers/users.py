from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import UserRepository
from app.schemas import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", status_code=201, response_model=UserOut)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await UserRepository(db).create(nome=user.nome, email=user.email)
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
