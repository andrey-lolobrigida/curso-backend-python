from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import ResourceRepository
from app.schemas import ResourceCreate, ResourceOut

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("", status_code=201, response_model=ResourceOut)
def create_resource(resource: ResourceCreate, db: Session = Depends(get_db)):
    return ResourceRepository(db).create(nome=resource.nome, tipo=resource.tipo)


@router.get("", response_model=list[ResourceOut])
def list_resources(db: Session = Depends(get_db)):
    return ResourceRepository(db).list_all()


@router.get("/{resource_id}", response_model=ResourceOut)
def get_resource(resource_id: int, db: Session = Depends(get_db)):
    resource = ResourceRepository(db).get(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="recurso não existe")
    return resource
