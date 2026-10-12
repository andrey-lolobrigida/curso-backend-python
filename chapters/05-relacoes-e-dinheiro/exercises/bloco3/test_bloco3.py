import asyncio
from decimal import Decimal

import pytest
from lancamento import lancar_extrato
from sqlalchemy import text
from transferencia import SaldoInsuficiente, transferir

EXTRATO = [
    ("Aluguel da quadra", Decimal("120.00")),
    ("Bolas novas", Decimal("89.90")),
    ("Coletes", Decimal("45.50")),
    ("Água", Decimal("18.00")),
]


@pytest.fixture()
def tabelas(autocommit):
    # Tabelas reais (não temporárias): várias conexões precisam enxergá-las.
    autocommit.execute(text("DROP TABLE IF EXISTS bloco3_extrato, bloco3_contas"))
    autocommit.execute(
        text(
            "CREATE TABLE bloco3_extrato (id serial PRIMARY KEY, "
            "descricao varchar(100) NOT NULL, valor numeric(12, 2) NOT NULL)"
        )
    )
    autocommit.execute(
        text("CREATE TABLE bloco3_contas (id int PRIMARY KEY, saldo numeric(12, 2) NOT NULL)")
    )
    autocommit.execute(text("INSERT INTO bloco3_contas VALUES (1, 100.00), (2, 0.00)"))
    yield autocommit
    autocommit.execute(text("DROP TABLE bloco3_extrato, bloco3_contas"))


# ---------- 3.1 ----------


async def test_extrato_nunca_fica_pela_metade(tabelas, engine_async):
    with pytest.raises(RuntimeError):
        await lancar_extrato(engine_async, EXTRATO, falhar_na=2)
    linhas = tabelas.scalar(text("SELECT count(*) FROM bloco3_extrato"))
    assert linhas == 0, f"o extrato ficou pela metade: {linhas} de {len(EXTRATO)} linhas"


# ---------- 3.2 ----------


async def test_duas_transferencias_nao_estouram_o_saldo(tabelas, engine_async):
    # O gancho faz cada transferência esperar a outra chegar ao mesmo ponto, por no
    # máximo 0,5 s. Com timeout, e nunca uma barreira sem fim: se a outra estiver
    # parada num cadeado, a espera acaba e a vida segue.
    chegaram = 0
    as_duas = asyncio.Event()

    async def depois_de_ler():
        nonlocal chegaram
        chegaram += 1
        if chegaram == 2:
            as_duas.set()
        try:
            await asyncio.wait_for(as_duas.wait(), timeout=0.5)
        except TimeoutError:
            pass

    resultados = await asyncio.gather(
        transferir(engine_async, 1, 2, Decimal("80.00"), depois_de_ler),
        transferir(engine_async, 1, 2, Decimal("80.00"), depois_de_ler),
        return_exceptions=True,
    )
    for r in resultados:
        if isinstance(r, Exception) and not isinstance(r, SaldoInsuficiente):
            raise r
    passaram = sum(r is None for r in resultados)
    saldo = tabelas.scalar(text("SELECT saldo FROM bloco3_contas WHERE id = 1"))
    assert (passaram, saldo) == (1, Decimal("20.00"))
