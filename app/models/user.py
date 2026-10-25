from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    # Anulável de propósito: os usuários de antes da lição 03 não têm senha, e não
    # existe senha para inventar para eles. Sem senha, não logam (lição 03).
    senha_hash: Mapped[str | None]
