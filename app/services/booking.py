from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Booking
from app.repositories import BookingRepository, ResourceRepository, UserRepository
from app.schemas import BookingCreate, BookingOut


class RelatedNotFoundError(Exception):
    pass


class BookingConflictError(Exception):
    pass


class BookingNotFoundError(Exception):
    pass


class BookingInPastError(Exception):
    pass


class BookingService:
    def __init__(self, db: Session):
        self.bookings = BookingRepository(db)
        self.users = UserRepository(db)
        self.resources = ResourceRepository(db)

    def create(self, data: BookingCreate) -> BookingOut:
        user = self.users.get(data.user_id)
        resource = self.resources.get(data.resource_id)
        if user is None or resource is None:
            raise RelatedNotFoundError
        overlapping = self.bookings.find_overlapping(data.resource_id, data.starts_at, data.ends_at)
        if overlapping:
            raise BookingConflictError
        booking = self.bookings.create(data.user_id, data.resource_id, data.starts_at, data.ends_at)
        return self._to_out(booking)

    def cancel(self, booking_id: int) -> None:
        booking = self.bookings.get(booking_id)
        if booking is None:
            raise BookingNotFoundError
        if booking.starts_at <= datetime.now():
            raise BookingInPastError
        self.bookings.delete(booking)

    def list_all(self) -> list[BookingOut]:
        return [self._to_out(b) for b in self.bookings.list_all()]

    def _to_out(self, booking: Booking) -> BookingOut:
        user = self.users.get(booking.user_id)
        resource = self.resources.get(booking.resource_id)
        return BookingOut(
            id=booking.id,
            user_id=booking.user_id,
            resource_id=booking.resource_id,
            starts_at=booking.starts_at,
            ends_at=booking.ends_at,
            user_nome=user.nome,
            resource_nome=resource.nome,
        )
