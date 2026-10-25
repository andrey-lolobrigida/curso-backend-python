from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Group, User
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

    async def create(self, data: GroupCreate, user: User) -> GroupOut:
        # Quem cria entra como membro, na mesma transação: grupo sem o criador não existe nem
        # por um instante. Sem isso, o criador não poderia nem ler o grupo que acabou de criar.
        async with self.db.begin():
            group = await self.groups.create(data.nome)
            await self.groups.add_member(group.id, user.id)
        return GroupOut(
            id=group.id, nome=group.nome, membros=[MemberOut(user_id=user.id, nome=user.nome)]
        )

    async def get(self, group_id: int, user: User) -> GroupOut:
        group = await self.groups.get_with_members(group_id)
        # Os membros já vieram carregados: conferir quem pede não custa consulta nenhuma.
        # Grupo de que você não é membro responde igual ao que não existe (lição 12 do cap. 6).
        if group is None or user.id not in {m.user_id for m in group.membros}:
            raise GroupNotFoundError
        return self._to_out(group)

    async def balances(self, group_id: int, user: User) -> list[BalanceOut]:
        # Leitura pura: sem begin(), como o get. O is_member ocupa o lugar do "o grupo existe?":
        # mesma consulta a menos, mesma contagem de antes.
        if not await self.groups.is_member(group_id, user.id):
            raise GroupNotFoundError
        linhas = await self.groups.balances(group_id)
        return [BalanceOut(user_id=u, nome=nome, saldo=saldo) for u, nome, saldo in linhas]

    async def add_member(self, group_id: int, data: MemberAdd, user: User) -> MemberOut:
        async with self.db.begin():
            # Quem pede primeiro, o alvo depois: quem é de fora não ouve nenhuma outra resposta
            # sobre o grupo. Primeiro "é seu?", depois o resto (lição 11 do cap. 6).
            if not await self.groups.is_member(group_id, user.id):
                raise GroupNotFoundError
            novo = await self.users.get(data.user_id)
            if novo is None:
                raise UserNotFoundError
            try:
                await self.groups.add_member(group_id, data.user_id)
            except MemberAlreadyExistsError:
                raise AlreadyMemberError
        return MemberOut(user_id=novo.id, nome=novo.nome)

    def _to_out(self, group: Group) -> GroupOut:
        return GroupOut(
            id=group.id,
            nome=group.nome,
            membros=[MemberOut(user_id=m.user_id, nome=m.user.nome) for m in group.membros],
        )
