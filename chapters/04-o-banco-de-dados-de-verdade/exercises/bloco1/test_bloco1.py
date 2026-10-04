from datetime import UTC, datetime

import pytest
from migracao import upgrade
from sqlalchemy import text


@pytest.fixture()
def clube(conexao):
    conexao.execute(
        text("CREATE TEMP TABLE reservas_do_clube (id int PRIMARY KEY, inicio timestamp NOT NULL)")
    )
    conexao.execute(
        text(
            "INSERT INTO reservas_do_clube VALUES (1, '2030-01-01 10:00'), (2, '2018-12-01 10:00')"
        )
    )
    return conexao


def _inicio(conexao, id_):
    return conexao.scalar(text("SELECT inicio FROM reservas_do_clube WHERE id = :id"), {"id": id_})


def test_a_reserva_continua_no_mesmo_instante(clube):
    upgrade(clube)
    # 10h em São Paulo, em 2030, é 13h em UTC.
    assert _inicio(clube, 1) == datetime(2030, 1, 1, 13, 0, tzinfo=UTC)


def test_a_reserva_do_horario_de_verao_tambem(clube):
    upgrade(clube)
    # Em dezembro de 2018 São Paulo estava no horário de verão.
    assert _inicio(clube, 2) == datetime(2018, 12, 1, 12, 0, tzinfo=UTC)
