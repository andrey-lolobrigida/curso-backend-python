from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserSession
from app.security import VALIDADE_DA_SESSAO


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, token_hash: str, agora: datetime) -> UserSession:
        # criada_em e expira_em saem do mesmo relógio: a validade é exata, 24 h cravadas.
        sessao = UserSession(
            user_id=user_id,
            token_hash=token_hash,
            criada_em=agora,
            expira_em=agora + VALIDADE_DA_SESSAO,
        )
        self.db.add(sessao)
        await self.db.flush()
        return sessao

    async def user_by_token_hash(self, token_hash: str) -> User | None:
        # Uma ida ao banco: o usuário dono de uma sessão com esse hash e ainda na validade.
        # O "agora" é o now() do banco, não o relógio do Python: um relógio só decide.
        stmt = (
            select(User)
            .join(UserSession, UserSession.user_id == User.id)
            .where(UserSession.token_hash == token_hash, UserSession.expira_em > func.now())
        )
        return await self.db.scalar(stmt)

    async def delete_by_token_hash(self, token_hash: str) -> None:
        # Logout é isto: apagar a linha. Sem flush(): um DELETE como este vai direto ao banco,
        # não passa pela fila do add() (lição 07).
        await self.db.execute(delete(UserSession).where(UserSession.token_hash == token_hash))
