from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Resource


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
