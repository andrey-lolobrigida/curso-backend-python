from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    BalanceOut,
    ExpenseCreate,
    ExpenseOut,
    GroupCreate,
    GroupOut,
    MemberAdd,
    MemberOut,
)
from app.services import (
    AlreadyMemberError,
    ExpenseService,
    GroupNotFoundError,
    GroupService,
    NotAMemberError,
    UserNotFoundError,
)

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("", status_code=201, response_model=GroupOut)
async def create_group(data: GroupCreate, db: AsyncSession = Depends(get_db)):
    return await GroupService(db).create(data)


@router.get("/{group_id}", response_model=GroupOut)
async def get_group(group_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await GroupService(db).get(group_id)
    except GroupNotFoundError:
        raise HTTPException(status_code=404, detail="grupo não existe")


@router.get("/{group_id}/balances", response_model=list[BalanceOut])
async def get_balances(group_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await GroupService(db).balances(group_id)
    except GroupNotFoundError:
        raise HTTPException(status_code=404, detail="grupo não existe")


@router.post("/{group_id}/members", status_code=201, response_model=MemberOut)
async def add_member(group_id: int, data: MemberAdd, db: AsyncSession = Depends(get_db)):
    try:
        return await GroupService(db).add_member(group_id, data)
    except GroupNotFoundError:
        raise HTTPException(status_code=404, detail="grupo não existe")
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="usuário não existe")
    except AlreadyMemberError:
        raise HTTPException(status_code=409, detail="usuário já é membro do grupo")


@router.post("/{group_id}/expenses", status_code=201, response_model=ExpenseOut)
async def create_expense(group_id: int, data: ExpenseCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await ExpenseService(db).create(group_id, data)
    except GroupNotFoundError:
        raise HTTPException(status_code=404, detail="grupo não existe")
    except NotAMemberError:
        raise HTTPException(status_code=422, detail="pagador e participantes precisam ser membros")
