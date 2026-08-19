from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, nome: str, email: str) -> User:
        user = User(nome=nome, email=email)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)

    async def list_all(self) -> list[User]:
        resultado = await self.db.scalars(select(User))
        return list(resultado)
