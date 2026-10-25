from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import GroupRepository, SettlementRepository
from app.schemas import SettlementCreate, SettlementOut
from app.services.expense import NotAMemberError
from app.services.group import GroupNotFoundError


class SettlementExceedsDebtError(Exception):
    pass


class SettlementToSelfError(Exception):
    pass


class SettlementService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.groups = GroupRepository(db)
        self.settlements = SettlementRepository(db)

    async def create(self, group_id: int, data: SettlementCreate, user: User) -> SettlementOut:
        # Quem lança é quem RECEBE. A mentira que dá prejuízo é o devedor dizendo "paguei":
        # então o pagamento só entra pela mão de quem o recebeu (lição 12 do cap. 6).
        async with self.db.begin():
            # Quem pede é membro? Antes de qualquer cadeado, e antes de qualquer outra resposta.
            if not await self.groups.is_member(group_id, user.id):
                raise GroupNotFoundError
            # "Recebi de mim mesmo": é no que vira o devedor dizendo "paguei", agora que o
            # para_user_id vem do token. Antes do cadeado: com os dois ids iguais, o
            # lock_members tranca uma linha só, e o erro sairia como "não é membro".
            if data.de_user_id == user.id:
                raise SettlementToSelfError
            # Os dois cadeados ANTES de ler os saldos: quem chegar depois espera aqui,
            # e lê os saldos já com a quitação de quem chegou antes (READ COMMITTED:
            # cada comando vê o que já foi comitado, como na lição 10 do capítulo 4).
            trancados = await self.groups.lock_members(group_id, [data.de_user_id, user.id])
            if len(trancados) != 2:
                raise NotAMemberError
            saldo = {b.user_id: b.saldo for b in await self.groups.balances(group_id)}
            # A regra dos dois lados: quem paga deve pelo menos V, quem recebe tem pelo menos V.
            if saldo[data.de_user_id] > -data.valor or saldo[user.id] < data.valor:
                raise SettlementExceedsDebtError
            settlement = await self.settlements.create(
                group_id, data.de_user_id, user.id, data.valor
            )
        return SettlementOut.model_validate(settlement, from_attributes=True)
