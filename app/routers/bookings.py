from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import BookingCreate, BookingOut
from app.services import (
    BookingConflictError,
    BookingInPastError,
    BookingNotFoundError,
    BookingService,
    RelatedNotFoundError,
)

# Login exigido no router inteiro: rota nova que nascer aqui já nasce protegida.
router = APIRouter(prefix="/bookings", tags=["bookings"], dependencies=[Depends(get_current_user)])


@router.post("", status_code=201, response_model=BookingOut)
async def create_booking(
    data: BookingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # A mesma dependência do router: o FastAPI guarda o resultado, e a consulta roda uma vez.
    try:
        return await BookingService(db).create(data, user)
    except RelatedNotFoundError:
        raise HTTPException(status_code=404, detail="recurso não existe")
    except BookingConflictError:
        raise HTTPException(status_code=409, detail="o recurso já está reservado nesse horário")


@router.get("", response_model=list[BookingOut])
async def list_bookings(db: AsyncSession = Depends(get_db)):
    return await BookingService(db).list_all()


@router.delete("/{booking_id}", status_code=204)
async def cancel_booking(
    booking_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await BookingService(db).cancel(booking_id, user)
    except BookingNotFoundError:
        raise HTTPException(status_code=404, detail="reserva não existe")
    except BookingInPastError:
        raise HTTPException(status_code=409, detail="só reservas futuras podem ser canceladas")
