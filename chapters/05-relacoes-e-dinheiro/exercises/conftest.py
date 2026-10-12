"""Fixtures dos exercícios do capítulo 5. Os blocos 2 e 3 falam com o fairfare_test, o banco
do pytest. O bloco 1 não usa banco nenhum.

Suba o banco antes: docker compose up -d --wait
"""

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

ADMIN = "postgresql+psycopg://fairfare:fairfare@localhost:5432/postgres"
SINCRONA = "postgresql+psycopg://fairfare:fairfare@localhost:5432/fairfare_test"
ASSINCRONA = "postgresql+asyncpg://fairfare:fairfare@localhost:5432/fairfare_test"


@pytest.fixture(scope="session")
def _banco_de_testes():
    # O mesmo que o tests/conftest.py faz: garantir que o fairfare_test existe.
    # Não é autouse: o bloco 1 roda sem banco, e só quem pede uma conexão precisa dele.
    admin = create_engine(ADMIN, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = 'fairfare_test'")):
                conn.execute(text("CREATE DATABASE fairfare_test"))
    except OperationalError:
        pytest.exit(
            "Não achei o PostgreSQL. Suba o banco: docker compose up -d --wait", returncode=1
        )
    finally:
        admin.dispose()


@pytest.fixture()
def conexao(_banco_de_testes):
    """Uma conexão síncrona dentro de uma transação que é desfeita no fim do teste."""
    engine = create_engine(SINCRONA)
    with engine.connect() as conn:
        transacao = conn.begin()
        yield conn
        transacao.rollback()
    engine.dispose()


@pytest.fixture()
def autocommit(_banco_de_testes):
    """Uma conexão em que cada comando vale na hora (para tabelas que outras conexões veem)."""
    engine = create_engine(SINCRONA, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        yield conn
    engine.dispose()


@pytest.fixture()
async def engine_async(_banco_de_testes):
    engine = create_async_engine(ASSINCRONA, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture()
def conta_consultas():
    """O contador de consultas da lição 03 (o mesmo do tests/apoio.py).

    Uso: `with conta_consultas(engine) as contagem: ...`, e depois `contagem["n"]`.
    """

    @contextmanager
    def contador(engine):
        contagem = {"n": 0}

        def conta(*args):
            contagem["n"] += 1

        event.listen(engine.sync_engine, "before_cursor_execute", conta)
        try:
            yield contagem
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", conta)

    return contador
