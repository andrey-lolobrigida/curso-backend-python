from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking

# SQLSTATE do Postgres para "violou uma exclusion constraint".
EXCLUSION_VIOLATION = "23P01"


class BookingOverlapError(Exception):
    """O banco recusou a reserva: ela sobrepõe outra no mesmo recurso."""


class BookingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, user_id: int, resource_id: int, starts_at: datetime, ends_at: datetime
    ) -> Booking:
        booking = Booking(
            user_id=user_id, resource_id=resource_id, starts_at=starts_at, ends_at=ends_at
        )
        self.db.add(booking)
        try:
            await self.db.commit()
        except IntegrityError as erro:
            await self.db.rollback()
            if getattr(erro.orig, "sqlstate", None) == EXCLUSION_VIOLATION:
                raise BookingOverlapError from erro
            raise
        await self.db.refresh(booking)
        return booking

    async def get(self, booking_id: int) -> Booking | None:
        return await self.db.get(Booking, booking_id)

    async def delete(self, booking: Booking) -> None:
        await self.db.delete(booking)
        await self.db.commit()

    async def list_all(self) -> list[Booking]:
        resultado = await self.db.scalars(select(Booking))
        return list(resultado)

    async def find_overlapping(
        self, resource_id: int, starts_at: datetime, ends_at: datetime
    ) -> list[Booking]:
        # Escrita na forma do índice da constraint (tstzrange &&): só assim o Postgres
        # consegue usá-lo de verdade. Mesma pergunta, outra forma (lição 11).
        stmt = select(Booking).where(
            Booking.resource_id == resource_id,
            func.tstzrange(Booking.starts_at, Booking.ends_at).op("&&")(
                func.tstzrange(starts_at, ends_at)
            ),
        )
        resultado = await self.db.scalars(stmt)
        return list(resultado)
