from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking


class BookingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, user_id: int, resource_id: int, starts_at: datetime, ends_at: datetime
    ) -> Booking:
        booking = Booking(
            user_id=user_id, resource_id=resource_id, starts_at=starts_at, ends_at=ends_at
        )
        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def get(self, booking_id: int) -> Booking | None:
        return self.db.get(Booking, booking_id)

    def delete(self, booking: Booking) -> None:
        self.db.delete(booking)
        self.db.commit()

    def list_all(self) -> list[Booking]:
        return list(self.db.scalars(select(Booking)))

    def find_overlapping(
        self, resource_id: int, starts_at: datetime, ends_at: datetime
    ) -> list[Booking]:
        stmt = select(Booking).where(
            Booking.resource_id == resource_id,
            Booking.starts_at < ends_at,
            Booking.ends_at > starts_at,
        )
        return list(self.db.scalars(stmt))
