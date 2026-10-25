from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.repositories import ResourceRepository
from app.schemas import ResourceCreate, ResourceOut

# Login exigido no router inteiro: rota nova que nascer aqui já nasce protegida.
router = APIRouter(
    prefix="/resources", tags=["resources"], dependencies=[Depends(get_current_user)]
)


@router.post("", status_code=201, response_model=ResourceOut)
async def create_resource(resource: ResourceCreate, db: AsyncSession = Depends(get_db)):
    # Sem service, quem diz o que é "uma operação" é o router (lição 08).
    async with db.begin():
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
