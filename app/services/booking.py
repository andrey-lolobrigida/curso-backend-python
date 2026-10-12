from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking
from app.repositories import (
    BookingOverlapError,
    BookingRepository,
    ResourceRepository,
    UserRepository,
)
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
    def __init__(self, db: AsyncSession):
        self.db = db
        self.bookings = BookingRepository(db)
        self.users = UserRepository(db)
        self.resources = ResourceRepository(db)

    async def create(self, data: BookingCreate) -> BookingOut:
        # A transação é do service: commit na saída normal, rollback em qualquer exceção.
        async with self.db.begin():
            user = await self.users.get(data.user_id)
            resource = await self.resources.get(data.resource_id)
            if user is None or resource is None:
                raise RelatedNotFoundError
            overlapping = await self.bookings.find_overlapping(
                data.resource_id, data.starts_at, data.ends_at
            )
            if overlapping:
                raise BookingConflictError
            try:
                booking = await self.bookings.create(
                    data.user_id, data.resource_id, data.starts_at, data.ends_at
                )
            except BookingOverlapError:
                # A verificação acima é o caminho rápido e educado; a garantia é do banco.
                # Quem perdeu a corrida passou pela verificação e foi barrado aqui.
                # A exceção atravessa o begin(), que desfaz a transação.
                raise BookingConflictError
        return self._to_out(booking)

    async def cancel(self, booking_id: int) -> None:
        async with self.db.begin():
            booking = await self.bookings.get(booking_id)
            if booking is None:
                raise BookingNotFoundError
            if booking.starts_at <= datetime.now(UTC):
                raise BookingInPastError
            await self.bookings.delete(booking)

    async def list_all(self) -> list[BookingOut]:
        return [self._to_out(b) for b in await self.bookings.list_all()]

    def _to_out(self, booking: Booking) -> BookingOut:
        return BookingOut(
            id=booking.id,
            user_id=booking.user_id,
            resource_id=booking.resource_id,
            starts_at=booking.starts_at,
            ends_at=booking.ends_at,
            user_nome=booking.user.nome,
            resource_nome=booking.resource.nome,
        )
