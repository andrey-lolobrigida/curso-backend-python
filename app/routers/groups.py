from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import (
    BalanceOut,
    ExpenseCreate,
    ExpenseOut,
    GroupCreate,
    GroupOut,
    MemberAdd,
    MemberOut,
    SettlementCreate,
    SettlementOut,
)
from app.services import (
    AlreadyMemberError,
    ExpenseService,
    GroupNotFoundError,
    GroupService,
    NotAMemberError,
    SettlementExceedsDebtError,
    SettlementService,
    SettlementToSelfError,
    UserNotFoundError,
)

# Login exigido no router inteiro: rota nova que nascer aqui já nasce protegida. Ser membro
# é a outra metade, e ela mora no service, ao lado do grupo, dos membros e da transação
# (lição 12 do cap. 6). Grupo de que você não é membro responde igual ao que não existe.
router = APIRouter(prefix="/groups", tags=["groups"], dependencies=[Depends(get_current_user)])


# Cada rota pede o user de novo: o FastAPI guarda o resultado da dependência do router,
# e a consulta da sessão roda uma vez só (lição 05 do cap. 6).
@router.post("", status_code=201, response_model=GroupOut)
async def create_group(
    data: GroupCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await GroupService(db).create(data, user)


@router.get("/{group_id}", response_model=GroupOut)
async def get_group(
    group_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await GroupService(db).get(group_id, user)
    except GroupNotFoundError:
        raise HTTPException(status_code=404, detail="grupo não existe")


@router.get("/{group_id}/balances", response_model=list[BalanceOut])
async def get_balances(
    group_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await GroupService(db).balances(group_id, user)
    except GroupNotFoundError:
        raise HTTPException(status_code=404, detail="grupo não existe")


@router.post("/{group_id}/members", status_code=201, response_model=MemberOut)
async def add_member(
    group_id: int,
    data: MemberAdd,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await GroupService(db).add_member(group_id, data, user)
    except GroupNotFoundError:
        raise HTTPException(status_code=404, detail="grupo não existe")
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="usuário não existe")
    except AlreadyMemberError:
        raise HTTPException(status_code=409, detail="usuário já é membro do grupo")


@router.post("/{group_id}/expenses", status_code=201, response_model=ExpenseOut)
async def create_expense(
    group_id: int,
    data: ExpenseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await ExpenseService(db).create(group_id, data, user)
    except GroupNotFoundError:
        raise HTTPException(status_code=404, detail="grupo não existe")
    except NotAMemberError:
        raise HTTPException(status_code=422, detail="os participantes precisam ser membros")


@router.post("/{group_id}/settlements", status_code=201, response_model=SettlementOut)
async def create_settlement(
    group_id: int,
    data: SettlementCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await SettlementService(db).create(group_id, data, user)
    except GroupNotFoundError:
        raise HTTPException(status_code=404, detail="grupo não existe")
    except SettlementToSelfError:
        raise HTTPException(status_code=422, detail="ninguém quita uma dívida consigo mesmo")
    except NotAMemberError:
        raise HTTPException(status_code=422, detail="quem paga precisa ser membro")
    except SettlementExceedsDebtError:
        raise HTTPException(status_code=409, detail="a quitação passa do que se deve")
