from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Resource, User


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


class ResourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome: str, tipo: str) -> Resource:
        resource = Resource(nome=nome, tipo=tipo)
        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)
        return resource

    def get(self, resource_id: int) -> Resource | None:
        return self.db.get(Resource, resource_id)

    def list_all(self) -> list[Resource]:
        return list(self.db.scalars(select(Resource)))
