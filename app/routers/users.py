from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import UserRepository
from app.schemas import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", status_code=201, response_model=UserOut)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    try:
        return UserRepository(db).create(nome=user.nome, email=user.email)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="email já cadastrado")


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return UserRepository(db).list_all()


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = UserRepository(db).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="usuário não existe")
    return user
