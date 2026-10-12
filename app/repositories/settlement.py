from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Settlement


class SettlementRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, group_id: int, de_user_id: int, para_user_id: int, valor: Decimal
    ) -> Settlement:
        settlement = Settlement(
            group_id=group_id, de_user_id=de_user_id, para_user_id=para_user_id, valor=valor
        )
        self.db.add(settlement)
        await self.db.flush()
        await self.db.refresh(settlement)  # o criada_em vem do banco
        return settlement
