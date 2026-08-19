"""Bancada: trabalho de CPU em série, em threads e em processos.

Rode: uv run python chapters/02-python-assincrono/bancada/cpu.py
"""

import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


def trabalho(n: int) -> int:
    """Puro CPU: nenhuma espera, nenhum I/O."""
    return sum(i * i for i in range(n))


N = 8_000_000
TAREFAS = 4


def cronometrar(rotulo: str, fn) -> None:
    comeco = time.perf_counter()
    fn()
    print(f"{rotulo:<28} {time.perf_counter() - comeco:.2f}s")


def em_serie() -> None:
    for _ in range(TAREFAS):
        trabalho(N)


def em_threads() -> None:
    with ThreadPoolExecutor(max_workers=TAREFAS) as pool:
        list(pool.map(trabalho, [N] * TAREFAS))


def em_processos() -> None:
    with ProcessPoolExecutor(max_workers=TAREFAS) as pool:
        list(pool.map(trabalho, [N] * TAREFAS))


if __name__ == "__main__":
    cronometrar("em série", em_serie)
    cronometrar("em 4 threads", em_threads)
    cronometrar("em 4 processos", em_processos)
