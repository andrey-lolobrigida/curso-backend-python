from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense
from app.repositories import ExpenseRepository, GroupRepository
from app.schemas import ExpenseCreate, ExpenseOut, ShareOut
from app.services.divisao import dividir
from app.services.group import GroupNotFoundError


class NotAMemberError(Exception):
    pass


class ExpenseService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.expenses = ExpenseRepository(db)
        self.groups = GroupRepository(db)

    async def create(self, group_id: int, data: ExpenseCreate) -> ExpenseOut:
        # Uma despesa são várias gravações: a despesa e uma parte por participante.
        # Ou entram todas, ou nenhuma. O begin() abraça o método INTEIRO, leituras
        # incluídas: a sessão já abre a transação na primeira consulta (lição 08).
        async with self.db.begin():
            if not await self.groups.exists(group_id):
                raise GroupNotFoundError
            membros = await self.groups.member_ids(group_id)
            participantes = data.participantes or sorted(membros)
            if data.paid_by not in membros or not set(participantes) <= membros:
                raise NotAMemberError
            expense = await self.expenses.create(group_id, data.paid_by, data.descricao, data.valor)
            for user_id, valor in dividir(data.valor, participantes).items():
                await self.expenses.add_share(expense.id, user_id, valor)
            expense = await self.expenses.get_with_shares(expense.id)
        return self._to_out(expense)

    def _to_out(self, expense: Expense) -> ExpenseOut:
        return ExpenseOut(
            id=expense.id,
            group_id=expense.group_id,
            paid_by=expense.paid_by,
            descricao=expense.descricao,
            valor=expense.valor,
            criada_em=expense.criada_em,
            partes=[ShareOut(user_id=p.user_id, valor=p.valor) for p in expense.partes],
        )
