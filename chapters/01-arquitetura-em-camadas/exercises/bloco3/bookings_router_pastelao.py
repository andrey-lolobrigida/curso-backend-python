from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import BookingCreate, BookingOut
from app.services import BookingConflictError, BookingService, RelatedNotFoundError

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", status_code=201, response_model=BookingOut)
def create_booking(data: BookingCreate, db: Session = Depends(get_db)):
    try:
        return BookingService(db).create(data)
    except RelatedNotFoundError:
        raise HTTPException(status_code=404, detail="usuário ou recurso não existe")
    except BookingConflictError:
        raise HTTPException(status_code=409, detail="o recurso já está reservado nesse horário")


@router.get("", response_model=list[BookingOut])
def list_bookings(db: Session = Depends(get_db)):
    return BookingService(db).list_all()


@router.delete("/{booking_id}", status_code=204)
def cancel_booking(booking_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT starts_at FROM bookings WHERE id = :id"), {"id": booking_id}
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="reserva não existe")
    starts_at = datetime.fromisoformat(str(row[0]))
    if starts_at <= datetime.now():
        raise HTTPException(status_code=409, detail="só reservas futuras podem ser canceladas")
    db.execute(text("DELETE FROM bookings WHERE id = :id"), {"id": booking_id})
    db.commit()
