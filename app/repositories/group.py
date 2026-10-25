from sqlalchemy import exists, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Group, GroupMember

# O saldo de cada membro: tudo o que pagou, menos tudo o que consumiu (lição 10),
# mais as quitações que fez, menos as que recebeu (lição 11).
# Escrita em SQL porque é um relatório: lê-se de cima para baixo, cola-se no psql,
# passa no EXPLAIN. Os :parâmetros vão separados do texto. Nunca f-string.
SALDOS = text("""
    WITH movimentos AS (
        SELECT paid_by AS user_id, valor
          FROM expenses
         WHERE group_id = :grupo
        UNION ALL
        SELECT p.user_id, -p.valor
          FROM expense_shares p
          JOIN expenses e ON e.id = p.expense_id
         WHERE e.group_id = :grupo
        UNION ALL
        SELECT de_user_id, valor FROM settlements WHERE group_id = :grupo
        UNION ALL
        SELECT para_user_id, -valor FROM settlements WHERE group_id = :grupo
    )
    SELECT m.user_id, u.nome, CAST(COALESCE(SUM(mv.valor), 0) AS NUMERIC(20, 2)) AS saldo
      FROM group_members m
      JOIN users u ON u.id = m.user_id
      LEFT JOIN movimentos mv ON mv.user_id = m.user_id
     WHERE m.group_id = :grupo
     GROUP BY m.user_id, u.nome
     ORDER BY m.user_id
""")


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

    async def is_member(self, group_id: int, user_id: int) -> bool:
        # Uma consulta. Grupo que não existe não tem membro nenhum: False, como o de fora.
        return await self.db.scalar(
            select(exists().where(GroupMember.group_id == group_id, GroupMember.user_id == user_id))
        )

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
        return (await self.db.execute(SALDOS, {"grupo": group_id})).all()

    async def lock_members(self, group_id: int, user_ids: list[int]) -> list[GroupMember]:
        # Tranca as linhas de quem paga e de quem recebe até o fim da transação.
        # SEMPRE em ordem de user_id: quem tranca na mesma ordem nunca forma um ciclo,
        # e sem ciclo não há deadlock (lição 11; capítulo 4, SOLUTIONS do bloco 3).
        stmt = (
            select(GroupMember)
            .where(GroupMember.group_id == group_id, GroupMember.user_id.in_(user_ids))
            .order_by(GroupMember.user_id)
            .with_for_update()
        )
        return list(await self.db.scalars(stmt))
