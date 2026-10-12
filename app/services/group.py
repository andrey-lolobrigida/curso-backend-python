from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Group
from app.repositories import GroupRepository, MemberAlreadyExistsError, UserRepository
from app.schemas import BalanceOut, GroupCreate, GroupOut, MemberAdd, MemberOut


class GroupNotFoundError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class AlreadyMemberError(Exception):
    pass


class GroupService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.groups = GroupRepository(db)
        self.users = UserRepository(db)

    async def create(self, data: GroupCreate) -> GroupOut:
        async with self.db.begin():
            group = await self.groups.create(data.nome)
        return GroupOut(id=group.id, nome=group.nome, membros=[])

    async def get(self, group_id: int) -> GroupOut:
        group = await self.groups.get_with_members(group_id)
        if group is None:
            raise GroupNotFoundError
        return self._to_out(group)

    async def balances(self, group_id: int) -> list[BalanceOut]:
        # Leitura pura: sem begin(), como o get.
        if not await self.groups.exists(group_id):
            raise GroupNotFoundError
        linhas = await self.groups.balances(group_id)
        return [BalanceOut(user_id=u, nome=nome, saldo=saldo) for u, nome, saldo in linhas]

    async def add_member(self, group_id: int, data: MemberAdd) -> MemberOut:
        async with self.db.begin():
            if not await self.groups.exists(group_id):
                raise GroupNotFoundError
            user = await self.users.get(data.user_id)
            if user is None:
                raise UserNotFoundError
            try:
                await self.groups.add_member(group_id, data.user_id)
            except MemberAlreadyExistsError:
                raise AlreadyMemberError
        return MemberOut(user_id=user.id, nome=user.nome)

    def _to_out(self, group: Group) -> GroupOut:
        return GroupOut(
            id=group.id,
            nome=group.nome,
            membros=[MemberOut(user_id=m.user_id, nome=m.user.nome) for m in group.membros],
        )
