"""Bancada da lição 10: injeção de SQL ao vivo, e o parâmetro que a impede.

SÓ LEITURA no banco de desenvolvimento (o fairfare do compose): três SELECTs em users,
nenhuma escrita. Precisa de um usuário chamado "Ana" no banco (o da lição 04).

  docker compose up -d --wait
  uv run python chapters/05-relacoes-e-dinheiro/bancada/injecao.py

Busca um usuário pelo nome de três jeitos:
  1. f-string, com um nome comum            -> uma linha.
  2. a mesma f-string, com um nome malicioso -> TODAS as linhas.
  3. parâmetro (:nome), com o mesmo nome malicioso -> zero linhas.

Para cada um, imprime o SQL que vai ao driver, os parâmetros e as linhas que voltaram.
A f-string aqui é o exemplo do que NUNCA fazer. Ela existe para ser vista quebrando.
"""

import asyncio
import sys
from pathlib import Path

# A raiz do projeto no sys.path: o projeto não é instalado (ver conta_consultas.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402

MALICIOSO = "x' OR '1'='1"


async def busca(db, titulo: str, stmt, parametros: dict) -> None:
    linhas = (await db.execute(stmt, parametros)).all()
    print(f"--- {titulo}")
    # O texto que o driver (asyncpg) recebe: o SQLAlchemy troca :nome por $1, e o valor
    # vai à parte, numa mensagem separada do protocolo do Postgres.
    print(f"SQL:         {stmt.compile(dialect=engine.dialect)}")
    print(f"parâmetros:  {parametros}")
    print(f"linhas:      {len(linhas)} {[tuple(linha) for linha in linhas]}")
    print()


async def main() -> None:
    async with SessionLocal() as db:
        banco = await db.scalar(text("SELECT current_database()"))
        print(f"banco={banco}\n")

        nome = "Ana"
        await busca(
            db,
            "1. f-string, nome comum",
            text(f"SELECT id, nome FROM users WHERE nome = '{nome}'"),
            {},
        )

        nome = MALICIOSO
        await busca(
            db,
            "2. f-string, nome malicioso",
            text(f"SELECT id, nome FROM users WHERE nome = '{nome}'"),
            {},
        )

        await busca(
            db,
            "3. parâmetro, o mesmo nome malicioso",
            text("SELECT id, nome FROM users WHERE nome = :nome"),
            {"nome": nome},
        )
    await engine.dispose()


asyncio.run(main())
