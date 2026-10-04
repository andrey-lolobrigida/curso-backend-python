"""Bloco 2.3 — o índice que o planner ignora. (QUEBRADO DE PROPÓSITO: o resultado está
certo, mas o banco lê a tabela inteira para chegar nele)
"""

from datetime import date

from sqlalchemy import Column, DateTime, Integer, MetaData, Select, Table, func, select

metadata = MetaData()
agenda = Table(
    "bloco2_agenda",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("starts_at", DateTime(timezone=True), nullable=False, index=True),
)


def reservas_do_dia(dia: date) -> Select:
    """As reservas que começam em `dia` (um dia em UTC)."""
    return select(agenda).where(func.date(agenda.c.starts_at) == dia)
