from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Group, GroupMember


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
