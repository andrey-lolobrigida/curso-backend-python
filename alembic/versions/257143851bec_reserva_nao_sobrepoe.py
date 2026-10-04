"""reserva nao sobrepoe

Revision ID: 257143851bec
Revises: 735b317a52e9
Create Date: 2026-10-04 01:32:57.097159

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "257143851bec"
down_revision: Union[str, Sequence[str], None] = "735b317a52e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # btree_gist ensina o gist a comparar inteiros com "=" (o resource_id).
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # Escrita à mão: o autogenerate não enxerga ExcludeConstraint.
    op.create_exclude_constraint(
        "bookings_sem_sobreposicao",
        "bookings",
        ("resource_id", "="),
        (sa.func.tstzrange(sa.column("starts_at"), sa.column("ends_at")), "&&"),
        using="gist",
    )
    # Fecha a brecha do intervalo vazio: começo e fim iguais não sobrepõem nada.
    op.create_check_constraint("bookings_fim_depois_do_inicio", "bookings", "ends_at > starts_at")
    # O índice da constraint responde a pergunta do find_overlapping melhor que o btree
    # da lição 06 — desde que a consulta use &&. Dois índices para uma pergunta é desperdício.
    op.drop_index("ix_bookings_resource_id_starts_at", table_name="bookings")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_index("ix_bookings_resource_id_starts_at", "bookings", ["resource_id", "starts_at"])
    op.drop_constraint("bookings_fim_depois_do_inicio", "bookings")
    op.drop_constraint("bookings_sem_sobreposicao", "bookings")
    # A extensão fica: outro objeto pode ter passado a depender dela.
