"""Bancada: o event loop, em quatro cenas.

Rode: uv run python chapters/02-python-assincrono/bancada/loop.py
"""

import asyncio
import time


async def tarefa(nome: str, segundos: float) -> str:
    print(f"  [{nome}] comecei")
    await asyncio.sleep(segundos)
    print(f"  [{nome}] terminei")
    return nome


async def cena_1_uma_corrotina_nao_e_paralela() -> None:
    print("cena 1: dois await em sequência")
    comeco = time.perf_counter()
    await tarefa("a", 1)
    await tarefa("b", 1)
    print(f"  total: {time.perf_counter() - comeco:.2f}s  <- 2s: await espera mesmo\n")


async def cena_2_gather_e_que_concorre() -> None:
    print("cena 2: os mesmos dois, com gather")
    comeco = time.perf_counter()
    await asyncio.gather(tarefa("a", 1), tarefa("b", 1))
    print(f"  total: {time.perf_counter() - comeco:.2f}s  <- 1s: agora sim\n")


async def cena_3_o_sleep_errado() -> None:
    print("cena 3: gather, mas com time.sleep no lugar do asyncio.sleep")

    async def bloqueia(nome: str) -> None:
        print(f"  [{nome}] comecei")
        time.sleep(1)  # não devolve o controle ao loop
        print(f"  [{nome}] terminei")

    comeco = time.perf_counter()
    await asyncio.gather(bloqueia("a"), bloqueia("b"))
    print(f"  total: {time.perf_counter() - comeco:.2f}s  <- 2s: o gather não salva ninguém\n")


async def cena_4_corrotina_sem_await_nao_roda() -> None:
    print("cena 4: chamar uma corrotina sem await")
    coro = tarefa("fantasma", 0)
    print(f"  o que voltou: {coro!r}")
    print("  nada foi executado. o await é quem entrega ao loop.")
    coro.close()


async def main() -> None:
    await cena_1_uma_corrotina_nao_e_paralela()
    await cena_2_gather_e_que_concorre()
    await cena_3_o_sleep_errado()
    await cena_4_corrotina_sem_await_nao_roda()


asyncio.run(main())
