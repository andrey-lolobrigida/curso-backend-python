from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Settlement(Base):
    """X paga V a Y, dentro de um grupo: o pagador sobe V, o recebedor desce V (lição 11)."""

    __tablename__ = "settlements"
    __table_args__ = (
        CheckConstraint("valor > 0", name="settlements_valor_positivo"),
        CheckConstraint("de_user_id <> para_user_id", name="settlements_de_diferente_de_para"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    de_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    para_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
