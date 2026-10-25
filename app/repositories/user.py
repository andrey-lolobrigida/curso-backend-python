from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, nome: str, email: str, senha_hash: str) -> User:
        user = User(nome=nome, email=email, senha_hash=senha_hash)
        self.db.add(user)
        # flush: manda o INSERT dentro da transação de quem chamou. Quem comita é o service
        # (ou o router, quando não há service). Lição 08.
        await self.db.flush()
        return user

    async def get(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)

    async def list_all(self) -> list[User]:
        resultado = await self.db.scalars(select(User))
        return list(resultado)
