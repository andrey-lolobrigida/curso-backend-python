from decimal import Decimal

import pytest
from listagem import grupos_com_membros, resumo_dos_grupos
from modelos import Base, Bloco2Despesa, Bloco2Grupo, Bloco2Membro
from sqlalchemy.ext.asyncio import AsyncSession

GRUPOS = 20


def total_esperado(i: int) -> Decimal:
    # As 4 despesas do grupo i valem i.01, i.02, i.03 e i.04: somam 4·i + 0.10.
    return Decimal(4 * i) + Decimal("0.10")


@pytest.fixture()
async def grupos(engine_async):
    async with engine_async.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine_async) as db, db.begin():
        for i in range(1, GRUPOS + 1):
            db.add(Bloco2Grupo(id=i, nome=f"Grupo {i:02d}"))
        await db.flush()
        for i in range(1, GRUPOS + 1):
            for j in range(1, 4):
                db.add(Bloco2Membro(grupo_id=i, nome=f"Membro {i}-{j}"))
            for j in range(1, 5):
                db.add(Bloco2Despesa(grupo_id=i, valor=Decimal(f"{i}.{j:02d}")))
    yield engine_async
    async with engine_async.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_resumo_correto(grupos):
    async with AsyncSession(grupos) as db:
        resumo = await resumo_dos_grupos(db)
    assert resumo == [
        {
            "nome": f"Grupo {i:02d}",
            "membros": [f"Membro {i}-{j}" for j in range(1, 4)],
            "total": total_esperado(i),
        }
        for i in range(1, GRUPOS + 1)
    ]


async def test_resumo_sem_n_mais_1(grupos, conta_consultas):
    async with AsyncSession(grupos) as db:
        with conta_consultas(grupos) as contagem:
            await resumo_dos_grupos(db)
    assert contagem["n"] <= 3, f"{contagem['n']} consultas para {GRUPOS} grupos"


async def test_grupos_com_membros(grupos):
    async with AsyncSession(grupos) as db:
        lista = await grupos_com_membros(db)
        assert len(lista) == GRUPOS
        assert all(len(g.membros) == 3 for g in lista)
