from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking


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
        await self.db.commit()
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
        stmt = select(Booking).where(
            Booking.resource_id == resource_id,
            Booking.starts_at < ends_at,
            Booking.ends_at > starts_at,
        )
        resultado = await self.db.scalars(stmt)
        return list(resultado)
