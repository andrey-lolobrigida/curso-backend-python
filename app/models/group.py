from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import User


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]

    # Um-para-muitos: um grupo, várias linhas de associação.
    membros: Mapped[list["GroupMember"]] = relationship(
        lazy="raise", order_by="GroupMember.user_id"
    )


class GroupMember(Base):
    """Quem é de qual grupo. Uma classe, e não uma Table solta: a lição 11 tranca linhas dela."""

    __tablename__ = "group_members"

    # Chave composta: o par (grupo, usuário) é a identidade da linha, e não se repete.
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)

    user: Mapped[User] = relationship(lazy="raise")
