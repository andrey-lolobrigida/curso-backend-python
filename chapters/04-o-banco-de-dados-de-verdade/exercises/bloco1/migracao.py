"""Bloco 1 — a migração que mudou o passado. (QUEBRADA DE PROPÓSITO)

O sistema antigo do clube gravava o início de cada reserva em `timestamp`, sem fuso,
no horário de parede de São Paulo. Esta migração converte a coluna para `timestamptz`.
Ela foi copiada da lição 04 e roda sem erro nenhum.
"""

from sqlalchemy import Connection, text


def upgrade(conn: Connection) -> None:
    conn.execute(
        text(
            "ALTER TABLE reservas_do_clube "
            "ALTER COLUMN inicio TYPE timestamptz USING inicio AT TIME ZONE 'UTC'"
        )
    )
