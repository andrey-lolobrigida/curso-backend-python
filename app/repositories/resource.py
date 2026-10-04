from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Resource


class ResourceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, nome: str, tipo: str) -> Resource:
        resource = Resource(nome=nome, tipo=tipo)
        self.db.add(resource)
        await self.db.commit()
        await self.db.refresh(resource)
        return resource

    async def get(self, resource_id: int) -> Resource | None:
        return await self.db.get(Resource, resource_id)

    async def list_all(self) -> list[Resource]:
        resultado = await self.db.scalars(select(Resource))
        return list(resultado)
