from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, column, func
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        # "Um recurso não tem duas reservas no mesmo horário" — regra do banco, não do código
        # (lição 11). O autogenerate do Alembic não enxerga isto: a migração foi escrita à mão.
        ExcludeConstraint(
            ("resource_id", "="),
            (func.tstzrange(column("starts_at"), column("ends_at")), "&&"),
            name="bookings_sem_sobreposicao",
            using="gist",
        ),
        # Sem isto, uma reserva de duração zero vira um intervalo vazio, que não sobrepõe
        # nada, e escapa da regra de cima (lição 11).
        CheckConstraint("ends_at > starts_at", name="bookings_fim_depois_do_inicio"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    # timestamptz: um instante na linha do tempo, não um horário de parede (lição 04).
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
