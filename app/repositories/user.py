from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome: str, email: str) -> User:
        user = User(nome=nome, email=email)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def list_all(self) -> list[User]:
        return list(self.db.scalars(select(User)))
