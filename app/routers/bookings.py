from fastapi import APIRouter, Depends, HTTPException
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
