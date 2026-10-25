from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserSession(Base):
    """Um login que deu certo. UserSession, e não Session, para não confundir com a AsyncSession."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # O sha256 do token, nunca o token: se a tabela vazar, os crachás não vazam (lição 04).
    token_hash: Mapped[str] = mapped_column(unique=True)
    # O repository grava o criada_em; o server_default é só rede de segurança.
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
