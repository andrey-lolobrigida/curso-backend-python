from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import GroupRepository, SettlementRepository
from app.schemas import SettlementCreate, SettlementOut
from app.services.expense import NotAMemberError
from app.services.group import GroupNotFoundError


class SettlementExceedsDebtError(Exception):
    pass


class SettlementService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.groups = GroupRepository(db)
        self.settlements = SettlementRepository(db)

    async def create(self, group_id: int, data: SettlementCreate) -> SettlementOut:
        async with self.db.begin():
            if not await self.groups.exists(group_id):
                raise GroupNotFoundError
            # Os dois cadeados ANTES de ler os saldos: quem chegar depois espera aqui,
            # e lê os saldos já com a quitação de quem chegou antes (READ COMMITTED:
            # cada comando vê o que já foi comitado, como na lição 10 do capítulo 4).
            trancados = await self.groups.lock_members(
                group_id, [data.de_user_id, data.para_user_id]
            )
            if len(trancados) != 2:
                raise NotAMemberError
            saldo = {b.user_id: b.saldo for b in await self.groups.balances(group_id)}
            # A regra dos dois lados: quem paga deve pelo menos V, quem recebe tem pelo menos V.
            if saldo[data.de_user_id] > -data.valor or saldo[data.para_user_id] < data.valor:
                raise SettlementExceedsDebtError
            settlement = await self.settlements.create(
                group_id, data.de_user_id, data.para_user_id, data.valor
            )
        return SettlementOut.model_validate(settlement, from_attributes=True)
