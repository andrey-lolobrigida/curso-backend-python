from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    tipo: Mapped[str] = mapped_column(server_default="quadra")
