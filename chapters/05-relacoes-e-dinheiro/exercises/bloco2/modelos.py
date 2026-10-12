"""Bloco 2 — os modelos. (ESTES ESTÃO CERTOS: o defeito mora em listagem.py)

Uma Base própria, separada da do FairFare: estas tabelas vivem só no fairfare_test,
e o teste as cria e as apaga.
"""

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Bloco2Grupo(Base):
    __tablename__ = "bloco2_grupos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    # lazy="select" é o padrão do SQLAlchemy, escrito aqui de propósito: sem o
    # lazy="raise" do FairFare, nada impede você de escrever o N+1.
    membros: Mapped[list["Bloco2Membro"]] = relationship(lazy="select", order_by="Bloco2Membro.id")


class Bloco2Membro(Base):
    __tablename__ = "bloco2_membros"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(ForeignKey("bloco2_grupos.id"))
    nome: Mapped[str] = mapped_column(String(100))


class Bloco2Despesa(Base):
    __tablename__ = "bloco2_despesas"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(ForeignKey("bloco2_grupos.id"))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
