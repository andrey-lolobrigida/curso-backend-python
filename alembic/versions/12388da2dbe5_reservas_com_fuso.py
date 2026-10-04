"""reservas com fuso

Revision ID: 12388da2dbe5
Revises: 4b1f163d18ea
Create Date: 2026-10-04 00:44:37.124788

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "12388da2dbe5"
down_revision: Union[str, Sequence[str], None] = "4b1f163d18ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SUPOSIÇÃO EXPLÍCITA: os horários gravados até aqui, sem fuso, estavam em UTC.
    # Sem o USING, o Postgres converteria pelo TimeZone da sessão — que hoje é UTC
    # no container, mas é configuração, não decisão. Aqui a decisão fica escrita.
    for coluna in ("starts_at", "ends_at"):
        op.alter_column(
            "bookings",
            coluna,
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=f"{coluna} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    """Downgrade schema."""
    for coluna in ("starts_at", "ends_at"):
        op.alter_column(
            "bookings",
            coluna,
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
            postgresql_using=f"{coluna} AT TIME ZONE 'UTC'",
        )
