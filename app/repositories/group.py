from sqlalchemy import Numeric, cast, func, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Expense, ExpenseShare, Group, GroupMember, User


class MemberAlreadyExistsError(Exception):
    """O banco recusou: o usuário já é membro do grupo (chave composta repetida)."""


class GroupRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, nome: str) -> Group:
        group = Group(nome=nome)
        self.db.add(group)
        await self.db.flush()
        await self.db.refresh(group)
        return group

    async def exists(self, group_id: int) -> bool:
        return await self.db.get(Group, group_id) is not None

    async def get_with_members(self, group_id: int) -> Group | None:
        # Grupo, membros e usuários: três consultas, qualquer que seja o tamanho do grupo.
        stmt = (
            select(Group)
            .where(Group.id == group_id)
            .options(selectinload(Group.membros).selectinload(GroupMember.user))
        )
        return await self.db.scalar(stmt)

    async def add_member(self, group_id: int, user_id: int) -> GroupMember:
        member = GroupMember(group_id=group_id, user_id=user_id)
        self.db.add(member)
        try:
            await self.db.flush()
        except IntegrityError as erro:
            # Sem rollback aqui: quem desfaz a transação é o begin() do service.
            raise MemberAlreadyExistsError from erro
        return member

    async def member_ids(self, group_id: int) -> set[int]:
        resultado = await self.db.scalars(
            select(GroupMember.user_id).where(GroupMember.group_id == group_id)
        )
        return set(resultado)

    async def balances(self, group_id: int):
        # Cada movimento de dinheiro vira uma linha (user_id, valor): quem pagou ganha,
        # quem consumiu perde. O saldo é a soma por membro (lição 09).
        movimentos = union_all(
            select(Expense.paid_by.label("user_id"), Expense.valor).where(
                Expense.group_id == group_id
            ),
            select(ExpenseShare.user_id, (-ExpenseShare.valor).label("valor"))
            .join(Expense, Expense.id == ExpenseShare.expense_id)
            .where(Expense.group_id == group_id),
        ).cte("movimentos")
        stmt = (
            select(
                GroupMember.user_id,
                User.nome,
                # Membro sem movimento: o SUM dá NULL, e o 0 sem casas viraria "0" no JSON.
                cast(func.coalesce(func.sum(movimentos.c.valor), 0), Numeric(20, 2)).label("saldo"),
            )
            .join(User, User.id == GroupMember.user_id)
            .outerjoin(movimentos, movimentos.c.user_id == GroupMember.user_id)
            .where(GroupMember.group_id == group_id)
            .group_by(GroupMember.user_id, User.nome)
            .order_by(GroupMember.user_id)
        )
        return (await self.db.execute(stmt)).all()
