from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import ResourceRepository, UserRepository
from app.schemas import (
    BookingCreate,
    BookingOut,
    ResourceCreate,
    ResourceOut,
    UserCreate,
    UserOut,
)
from app.services import BookingConflictError, BookingService, RelatedNotFoundError

app = FastAPI(title="FairFare")


@app.post("/users", status_code=201, response_model=UserOut)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    try:
        return UserRepository(db).create(nome=user.nome, email=user.email)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="email já cadastrado")


@app.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return UserRepository(db).list_all()


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = UserRepository(db).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="usuário não existe")
    return user


@app.post("/resources", status_code=201, response_model=ResourceOut)
def create_resource(resource: ResourceCreate, db: Session = Depends(get_db)):
    return ResourceRepository(db).create(nome=resource.nome, tipo=resource.tipo)


@app.get("/resources", response_model=list[ResourceOut])
def list_resources(db: Session = Depends(get_db)):
    return ResourceRepository(db).list_all()


@app.get("/resources/{resource_id}", response_model=ResourceOut)
def get_resource(resource_id: int, db: Session = Depends(get_db)):
    resource = ResourceRepository(db).get(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="recurso não existe")
    return resource


@app.post("/bookings", status_code=201, response_model=BookingOut)
def create_booking(data: BookingCreate, db: Session = Depends(get_db)):
    try:
        return BookingService(db).create(data)
    except RelatedNotFoundError:
        raise HTTPException(status_code=404, detail="usuário ou recurso não existe")
    except BookingConflictError:
        raise HTTPException(status_code=409, detail="o recurso já está reservado nesse horário")


@app.get("/bookings", response_model=list[BookingOut])
def list_bookings(db: Session = Depends(get_db)):
    return BookingService(db).list_all()
