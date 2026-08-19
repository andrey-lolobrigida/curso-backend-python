from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import ResourceRepository
from app.schemas import ResourceCreate, ResourceOut

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("", status_code=201, response_model=ResourceOut)
async def create_resource(resource: ResourceCreate, db: AsyncSession = Depends(get_db)):
    return await ResourceRepository(db).create(nome=resource.nome, tipo=resource.tipo)


@router.get("", response_model=list[ResourceOut])
async def list_resources(db: AsyncSession = Depends(get_db)):
    return await ResourceRepository(db).list_all()


@router.get("/{resource_id}", response_model=ResourceOut)
async def get_resource(resource_id: int, db: AsyncSession = Depends(get_db)):
    resource = await ResourceRepository(db).get(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="recurso não existe")
    return resource
