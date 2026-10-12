"""Bancada da lição 09: quem soma os saldos, o Python ou o banco?

O QUE O SCRIPT FAZ NO BANCO DE DESENVOLVIMENTO (o fairfare do compose):

  cria   10 usuários (saldos01@bancada-l09.fairfare.dev ... saldos10@...),
         o grupo "bancada/saldos.py (lição 09)" com os 10 como membros,
         N despesas (padrão 2000), cada uma dividida em partes iguais entre os 10;
  apaga  tudo isso no fim, em ordem de chave estrangeira (partes, despesas, membros,
         grupo, usuários).

A limpeza só mira o que o script cria: grupos com esse nome cujos membros são TODOS
usuários da bancada, e usuários da bancada que nada mais referencia. Se uma rodada
anterior morreu no meio, a próxima apaga a sobra antes de começar.

As sequências de id NÃO voltam: os ids gastos aqui ficam como buracos (users, groups,
expenses). Sequência não é transacional, e devolvê-la à mão poderia fazer um insert
concorrente reusar um id já em uso.

  docker compose up -d --wait
  uv run python chapters/05-relacoes-e-dinheiro/bancada/saldos.py
  uv run python chapters/05-relacoes-e-dinheiro/bancada/saldos.py --despesas 20000

Três jeitos de calcular o mesmo saldo, cada um medido 3 vezes (consultas e tempo):
  (a) Python ingênuo: duas consultas por membro (o que pagou, o que consumiu).
  (b) Python carregando tudo: as despesas com selectinload(Expense.partes), soma no laço.
  (c) O banco soma: GroupRepository.balances, a consulta do app.
"""

import argparse
import asyncio
import sys
import time
from decimal import Decimal
from pathlib import Path

# A raiz do projeto no sys.path: o projeto não é instalado (ver conta_consultas.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.models import Expense, ExpenseShare, GroupMember  # noqa: E402
from app.repositories import GroupRepository  # noqa: E402
from tests.apoio import conta_consultas  # noqa: E402  (o mesmo contador do guardião)

MEMBROS = 10
EMAILS = [f"saldos{i:02d}@bancada-l09.fairfare.dev" for i in range(1, MEMBROS + 1)]
GRUPO = "bancada/saldos.py (lição 09)"


async def apaga_sobras(db) -> None:
    """Apaga o que o script criou, e só isso, em ordem de chave estrangeira."""
    # Só os grupos com o nome da bancada em que TODO membro é usuário da bancada.
    # Os ids são lidos uma vez, antes de apagar: depois que os membros somem, a
    # condição "todo membro é da bancada" valeria para qualquer grupo vazio.
    ids = list(
        await db.scalars(
            text(
                """
                SELECT g.id FROM groups g
                WHERE g.nome = :grupo
                  AND NOT EXISTS (
                    SELECT 1 FROM group_members m JOIN users u ON u.id = m.user_id
                    WHERE m.group_id = g.id AND u.email <> ALL(CAST(:emails AS text[]))
                  )
                """
            ),
            {"grupo": GRUPO, "emails": EMAILS},
        )
    )
    alvo = {"ids": ids}
    await db.execute(
        text(
            """
            DELETE FROM expense_shares
            WHERE expense_id IN (SELECT id FROM expenses WHERE group_id = ANY(CAST(:ids AS int[])))
            """
        ),
        alvo,
    )
    await db.execute(text("DELETE FROM expenses WHERE group_id = ANY(CAST(:ids AS int[]))"), alvo)
    await db.execute(
        text("DELETE FROM group_members WHERE group_id = ANY(CAST(:ids AS int[]))"), alvo
    )
    await db.execute(text("DELETE FROM groups WHERE id = ANY(CAST(:ids AS int[]))"), alvo)
    # Usuários da bancada que nada mais referencia. Se algum ficou preso a outro dado,
    # ele fica: melhor uma sobra do que um DELETE que estoura na chave estrangeira.
    await db.execute(
        text(
            """
            DELETE FROM users u
            WHERE u.email = ANY(CAST(:emails AS text[]))
              AND NOT EXISTS (SELECT 1 FROM group_members m WHERE m.user_id = u.id)
              AND NOT EXISTS (SELECT 1 FROM expenses e WHERE e.paid_by = u.id)
              AND NOT EXISTS (SELECT 1 FROM expense_shares p WHERE p.user_id = u.id)
              AND NOT EXISTS (SELECT 1 FROM bookings b WHERE b.user_id = u.id)
            """
        ),
        {"emails": EMAILS},
    )


async def semeia(db, despesas: int) -> int:
    users = []
    for i, email in enumerate(EMAILS, start=1):
        users.append(
            await db.scalar(
                text("INSERT INTO users (nome, email) VALUES (:nome, :email) RETURNING id"),
                {"nome": f"Bancada {i:02d}", "email": email},
            )
        )
    group_id = await db.scalar(
        text("INSERT INTO groups (nome) VALUES (:grupo) RETURNING id"), {"grupo": GRUPO}
    )
    await db.execute(
        text(
            "INSERT INTO group_members (group_id, user_id) SELECT :g, unnest(CAST(:users AS int[]))"
        ),
        {"g": group_id, "users": users},
    )
    # Valor múltiplo de 10.00: a parte de cada um (valor / 10) fecha sem centavo sobrando.
    # Quem paga gira entre os 10, para os saldos não serem todos iguais.
    await db.execute(
        text(
            """
            INSERT INTO expenses (group_id, paid_by, descricao, valor)
            SELECT :g, (CAST(:users AS int[]))[1 + (s * 7) % 10], 'Despesa ' || s, ((s % 50) + 1) * 10.00
            FROM generate_series(1, :n) AS s
            """
        ),
        {"g": group_id, "users": users, "n": despesas},
    )
    await db.execute(
        text(
            """
            INSERT INTO expense_shares (expense_id, user_id, valor)
            SELECT e.id, m.user_id, e.valor / 10
            FROM expenses e JOIN group_members m ON m.group_id = e.group_id
            WHERE e.group_id = :g
            """
        ),
        {"g": group_id},
    )
    return group_id


async def ingenuo(db, group_id: int) -> tuple[dict[int, Decimal], int]:
    """(a) Para cada membro, uma consulta do que ele pagou e uma das partes dele."""
    membros = list(
        await db.scalars(select(GroupMember.user_id).where(GroupMember.group_id == group_id))
    )
    saldos, linhas = {}, len(membros)
    for user_id in membros:
        pagos = list(
            await db.scalars(
                select(Expense.valor).where(
                    Expense.group_id == group_id, Expense.paid_by == user_id
                )
            )
        )
        partes = list(
            await db.scalars(
                select(ExpenseShare.valor)
                .join(Expense, Expense.id == ExpenseShare.expense_id)
                .where(Expense.group_id == group_id, ExpenseShare.user_id == user_id)
            )
        )
        linhas += len(pagos) + len(partes)
        saldos[user_id] = sum(pagos, Decimal("0")) - sum(partes, Decimal("0"))
    return saldos, linhas


async def carrega_tudo(db, group_id: int) -> tuple[dict[int, Decimal], int]:
    """(b) Todas as despesas e todas as partes vêm para o Python, e o laço soma.

    Repare: quem não pagou nem consumiu nada não aparece no dicionário. Para listá-lo
    com 0.00, faltaria buscar os membros também. É o mesmo buraco do join sem outer.
    """
    stmt = select(Expense).where(Expense.group_id == group_id).options(selectinload(Expense.partes))
    despesas = list(await db.scalars(stmt))
    saldos: dict[int, Decimal] = {}
    linhas = len(despesas)
    for despesa in despesas:
        saldos[despesa.paid_by] = saldos.get(despesa.paid_by, Decimal("0")) + despesa.valor
        for parte in despesa.partes:
            saldos[parte.user_id] = saldos.get(parte.user_id, Decimal("0")) - parte.valor
            linhas += 1
    return saldos, linhas


async def no_banco(db, group_id: int) -> tuple[dict[int, Decimal], int]:
    """(c) A consulta do app: o banco soma e devolve uma linha por membro."""
    resultado = await GroupRepository(db).balances(group_id)
    return {user_id: saldo for user_id, _, saldo in resultado}, len(resultado)


async def mede(nome: str, funcao, group_id: int) -> dict[int, Decimal]:
    resultados = []
    for rodada in range(1, 4):
        # Sessão nova a cada rodada: o identity map da anterior não pode ajudar (lição 03).
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))  # aquecimento: fora do cronômetro
            with conta_consultas(engine) as contagem:
                inicio = time.perf_counter()
                saldos, linhas = await funcao(db, group_id)
                ms = (time.perf_counter() - inicio) * 1000
        resultados.append(saldos)
        print(f"{nome} rodada {rodada}: consultas={contagem['n']} linhas={linhas} tempo={ms:.0f}ms")
    return resultados[0]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--despesas", type=int, default=2000)
    args = parser.parse_args()

    async with SessionLocal() as db:
        banco = await db.scalar(text("SELECT current_database()"))
    print(f"banco={banco} membros={MEMBROS} despesas={args.despesas}")

    try:
        async with SessionLocal() as db, db.begin():
            await apaga_sobras(db)
            group_id = await semeia(db, args.despesas)
        # Estatísticas em dia antes de medir. Sem isso, o planner ainda acha que o grupo
        # recém-criado tem meia dúzia de despesas e escolhe um plano ruim.
        async with SessionLocal() as db, db.begin():
            await db.execute(text("ANALYZE expenses, expense_shares, group_members, users"))

        a = await mede("(a) python ingênuo     ", ingenuo, group_id)
        b = await mede("(b) python carrega tudo", carrega_tudo, group_id)
        c = await mede("(c) o banco soma       ", no_banco, group_id)

        if not (a == b == c):
            raise SystemExit(f"Os três discordam!\n(a) {a}\n(b) {b}\n(c) {c}")
        print(f"os três concordam; soma dos saldos = {sum(c.values())}")
    finally:
        async with SessionLocal() as db, db.begin():
            await apaga_sobras(db)
        await engine.dispose()
    print("dados da bancada apagados")


asyncio.run(main())
