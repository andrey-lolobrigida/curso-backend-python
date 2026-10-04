import asyncio
from collections import Counter
from datetime import UTC, datetime

import pytest
from deadlock import reservar_par
from retry import reservar
from sqlalchemy import text

INICIO = datetime(2030, 6, 1, 10, 0, tzinfo=UTC)
FIM = datetime(2030, 6, 1, 12, 0, tzinfo=UTC)


@pytest.fixture()
def tabelas(autocommit):
    autocommit.execute(text("DROP TABLE IF EXISTS bloco3_reservas, bloco3_quadras"))
    autocommit.execute(
        text(
            "CREATE TABLE bloco3_reservas (id serial PRIMARY KEY, resource_id int NOT NULL, "
            "starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL)"
        )
    )
    autocommit.execute(text("CREATE TABLE bloco3_quadras (id int PRIMARY KEY)"))
    autocommit.execute(text("INSERT INTO bloco3_quadras VALUES (1), (2)"))
    yield autocommit
    autocommit.execute(text("DROP TABLE bloco3_reservas, bloco3_quadras"))


async def test_corrida_serializable_termina_com_uma_reserva(tabelas, engine_async):
    for rodada in range(10):
        tabelas.execute(text("DELETE FROM bloco3_reservas"))
        resultados = await asyncio.gather(
            *(reservar(engine_async, 1, INICIO, FIM) for _ in range(5))
        )
        assert Counter(resultados) == {"criada": 1, "conflito": 4}, f"rodada {rodada + 1}"


async def test_cinquenta_rodadas_sem_deadlock(tabelas, engine_async):
    for _ in range(50):
        await asyncio.gather(
            reservar_par(engine_async, (1, 2)),
            reservar_par(engine_async, (2, 1)),
        )
