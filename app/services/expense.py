from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense, User
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

    async def create(self, group_id: int, data: ExpenseCreate, user: User) -> ExpenseOut:
        # Uma despesa são várias gravações: a despesa e uma parte por participante.
        # Ou entram todas, ou nenhuma. O begin() abraça o método INTEIRO, leituras
        # incluídas: a sessão já abre a transação na primeira consulta (lição 08).
        async with self.db.begin():
            membros = await self.groups.member_ids(group_id)
            # Quem lança precisa ser membro. Grupo que não existe não tem membros, e cai aqui
            # também: o mesmo 404 para os dois (lição 12 do cap. 6).
            if user.id not in membros:
                raise GroupNotFoundError
            participantes = data.participantes or sorted(membros)
            if not set(participantes) <= membros:
                raise NotAMemberError
            # Quem paga é quem lança: ninguém lança gasto em nome de outro.
            expense = await self.expenses.create(group_id, user.id, data.descricao, data.valor)
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
