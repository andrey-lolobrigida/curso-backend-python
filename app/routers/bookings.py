from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import BookingCreate, BookingOut
from app.services import (
    BookingConflictError,
    BookingInPastError,
    BookingNotFoundError,
    BookingService,
    RelatedNotFoundError,
)

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", status_code=201, response_model=BookingOut)
async def create_booking(data: BookingCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await BookingService(db).create(data)
    except RelatedNotFoundError:
        raise HTTPException(status_code=404, detail="usuário ou recurso não existe")
    except BookingConflictError:
        raise HTTPException(status_code=409, detail="o recurso já está reservado nesse horário")


@router.get("", response_model=list[BookingOut])
async def list_bookings(db: AsyncSession = Depends(get_db)):
    return await BookingService(db).list_all()


@router.delete("/{booking_id}", status_code=204)
async def cancel_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
    try:
        await BookingService(db).cancel(booking_id)
    except BookingNotFoundError:
        raise HTTPException(status_code=404, detail="reserva não existe")
    except BookingInPastError:
        raise HTTPException(status_code=409, detail="só reservas futuras podem ser canceladas")
