from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("valor > 0", name="expenses_valor_positivo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    paid_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    descricao: Mapped[str]
    # Numeric(12, 2): exato, em base 10, com duas casas. Nunca Float (lição 06).
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    partes: Mapped[list["ExpenseShare"]] = relationship(
        lazy="raise", order_by="ExpenseShare.user_id"
    )


class ExpenseShare(Base):
    """A parte de cada um, gravada: se a regra de divisão mudar, a despesa de ontem não muda."""

    __tablename__ = "expense_shares"
    # Zero é permitido: R$ 0,01 entre três dá 0,01 + 0,00 + 0,00 (lição 07).
    __table_args__ = (CheckConstraint("valor >= 0", name="expense_shares_valor_nao_negativo"),)

    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
