from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import ResourceRepository
from app.schemas import ResourceOut

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("", status_code=201)
def create_resource(resource: dict, db: Session = Depends(get_db)):
    created = ResourceRepository(db).create(nome=resource["nome"], tipo=resource["tipo"])
    return created


@router.get("", response_model=list[ResourceOut])
def list_resources(db: Session = Depends(get_db)):
    return ResourceRepository(db).list_all()


@router.get("/{resource_id}")
def get_resource(resource_id: int, db: Session = Depends(get_db)):
    return ResourceRepository(db).get(resource_id)
