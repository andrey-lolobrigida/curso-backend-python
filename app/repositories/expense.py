from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Expense, ExpenseShare


class ExpenseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, group_id: int, paid_by: int, descricao: str, valor: Decimal) -> Expense:
        expense = Expense(group_id=group_id, paid_by=paid_by, descricao=descricao, valor=valor)
        self.db.add(expense)
        await self.db.flush()
        await self.db.refresh(expense)  # criada_em vem do servidor
        return expense

    async def add_share(self, expense_id: int, user_id: int, valor: Decimal) -> ExpenseShare:
        share = ExpenseShare(expense_id=expense_id, user_id=user_id, valor=valor)
        self.db.add(share)
        await self.db.flush()
        return share

    async def get_with_shares(self, expense_id: int) -> Expense:
        stmt = select(Expense).where(Expense.id == expense_id).options(selectinload(Expense.partes))
        return await self.db.scalar(stmt)
