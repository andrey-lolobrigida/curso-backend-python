import gc
import json
import logging
import time
from datetime import date

import pytest
from consulta import agenda, reservas_do_dia
from httpx2 import ASGITransport, AsyncClient
from repositorio import ReservaRepository, metadata
from sqlalchemy import event, text

# ---------- 2.1 ----------


@pytest.fixture()
async def tabela_de_reservas(engine_async):
    async with engine_async.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)
        await conn.execute(
            text(
                "INSERT INTO bloco2_reservas (resource_id) "
                "SELECT i % 50 FROM generate_series(1, 200000) i"
            )
        )
    yield engine_async
    async with engine_async.begin() as conn:
        await conn.run_sync(metadata.drop_all)


async def test_count_conta_no_banco(tabela_de_reservas):
    comandos = []
    event.listen(
        tabela_de_reservas.sync_engine,
        "before_cursor_execute",
        lambda conn, cursor, sql, *args: comandos.append(sql.lower()),
    )
    async with tabela_de_reservas.connect() as conn:
        inicio = time.perf_counter()
        total = await ReservaRepository(conn).count()
        print(f"\ncount() em {time.perf_counter() - inicio:.3f}s")
    assert total == 200_000
    assert any("count(" in sql for sql in comandos), "o count ainda traz as linhas para o Python"


# ---------- 2.2 ----------


async def test_cem_requests_seguidas(caplog):
    from vazamento import app, engine

    # Quando o coletor de lixo acha uma conexão que ninguém devolveu, o SQLAlchemy
    # reclama no logger do pool. É esse aviso que o teste procura.
    caplog.set_level(logging.ERROR, logger="sqlalchemy.pool")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        for i in range(100):
            resp = await c.get("/agora")
            assert resp.status_code == 200, f"a request {i + 1} falhou"
            gc.collect()  # o coletor passa agora, e não quando ele quiser
            assert not any(
                "garbage collector is trying" in r.getMessage() for r in caplog.records
            ), f"a conexão da request {i + 1} só voltou porque o coletor de lixo foi buscar"
    assert engine.pool.checkedout() == 0, "terminou com conexões fora do pool"
    await engine.dispose()


# ---------- 2.3 ----------


@pytest.fixture()
def agenda_cheia(conexao):
    agenda.create(conexao)
    # Uma reserva por minuto a partir de 2030-01-01 00:00 UTC: ~69 dias.
    conexao.execute(
        text(
            "INSERT INTO bloco2_agenda (starts_at) "
            "SELECT timestamptz '2030-01-01 00:00+00' + i * interval '1 minute' "
            "FROM generate_series(0, 99999) i"
        )
    )
    conexao.execute(text("ANALYZE bloco2_agenda"))
    return conexao


def test_resultado_do_dia_esta_certo(agenda_cheia):
    linhas = agenda_cheia.execute(reservas_do_dia(date(2030, 1, 2))).all()
    assert (
        len(linhas) == 1440
    )  # um dia, um por minuto: começa à 00:00, para antes da 00:00 seguinte


def test_a_consulta_usa_o_indice(agenda_cheia):
    stmt = reservas_do_dia(date(2030, 1, 2)).compile(dialect=agenda_cheia.dialect)
    plano = agenda_cheia.exec_driver_sql("EXPLAIN (FORMAT JSON) " + str(stmt), stmt.params).scalar()
    assert "Seq Scan" not in json.dumps(plano), "o planner está lendo a tabela inteira"
