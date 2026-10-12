"""Bloco 2 — a listagem dos grupos. (QUEBRADA DE PROPÓSITO)

As duas funções devolvem a resposta certa, ou deveriam. O defeito está em COMO elas
pedem os dados ao banco.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from modelos import Bloco2Despesa, Bloco2Grupo, Bloco2Membro


async def resumo_dos_grupos(db: AsyncSession) -> list[dict]:
    """Nome, membros e total gasto de cada grupo, em ordem de id.

    EXERCÍCIO 2.1: a resposta sai certa. O número de consultas, não.
    """
    grupos = (await db.scalars(select(Bloco2Grupo).order_by(Bloco2Grupo.id))).all()
    resumo = []
    for grupo in grupos:
        nomes = await db.scalars(
            select(Bloco2Membro.nome)
            .where(Bloco2Membro.grupo_id == grupo.id)
            .order_by(Bloco2Membro.id)
        )
        total = await db.scalar(
            select(func.sum(Bloco2Despesa.valor)).where(Bloco2Despesa.grupo_id == grupo.id)
        )
        resumo.append({"nome": grupo.nome, "membros": list(nomes), "total": total})
    return resumo


async def grupos_com_membros(db: AsyncSession) -> list[Bloco2Grupo]:
    """Os grupos, cada um com a coleção `membros` já carregada, numa consulta só.

    EXERCÍCIO 2.2: esta função tem um defeito de propósito. O teste mostra qual.
    """
    stmt = select(Bloco2Grupo).options(joinedload(Bloco2Grupo.membros)).order_by(Bloco2Grupo.id)
    return list((await db.scalars(stmt)).all())
