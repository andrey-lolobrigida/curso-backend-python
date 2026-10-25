from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserSession
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
