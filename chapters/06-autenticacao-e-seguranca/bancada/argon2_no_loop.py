"""Bancada da lição 03: o argon2 e o event loop.

Oito logins chegam juntos. Cada um confere uma senha com argon2
(~55 ms de relógio; o ato 0 mede).
Ao mesmo tempo, uma corrotina "batimento" dorme 10 ms, acorda, e anota quanto
atrasou para acordar. Atraso alto = o loop estava ocupado e ninguém mais andou.

  uv run python chapters/06-autenticacao-e-seguranca/bancada/argon2_no_loop.py

Ato 0: quanto custa um hash e um verify, em relógio (perf_counter) e em CPU
(process_time). CPU maior que relógio = a conta usou mais de um núcleo.
Ato 1: o verify chamado direto, dentro da corrotina (no loop).
Ato 2: o mesmo verify, via asyncio.to_thread (numa thread).
Ato 3: o GIL. 20 verify em sequência × os mesmos 20 espalhados em 4 threads.

Só Python e argon2-cffi: nada aqui fala com o app nem com o banco.
"""

import asyncio
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from argon2 import PasswordHasher

ph = PasswordHasher()  # os parâmetros padrão, os mesmos do app/security.py
SENHA = "segredo123"
HASH = ph.hash(SENHA)
LOGINS = 8


def ms(segundos: float) -> str:
    """Milissegundos no jeito brasileiro: ms(0.0123) -> '12,3 ms'."""
    return f"{segundos * 1000:.1f} ms".replace(".", ",")


async def batimento(parar: asyncio.Event, atrasos: list[float]) -> None:
    while not parar.is_set():
        antes = time.perf_counter()
        await asyncio.sleep(0.01)
        atrasos.append(time.perf_counter() - antes - 0.01)


async def login_no_loop() -> None:
    ph.verify(HASH, SENHA)  # CPU pura, sem await: o loop fica parado aqui


async def login_na_thread() -> None:
    await asyncio.to_thread(ph.verify, HASH, SENHA)  # o loop segue girando


async def mede(login) -> None:
    parar = asyncio.Event()
    atrasos: list[float] = []
    pulso = asyncio.create_task(batimento(parar, atrasos))
    await asyncio.sleep(0.05)  # o batimento pega o ritmo antes de os logins chegarem
    comeco = time.perf_counter()
    await asyncio.gather(*(login() for _ in range(LOGINS)))
    total = time.perf_counter() - comeco
    parar.set()
    await pulso
    print(f"{LOGINS} verify: {ms(total)} no total")
    print(f"maior atraso do batimento: {ms(max(atrasos))}")


def ato_0() -> None:
    n = 15
    hashes, relogio, cpu = [], [], []
    for _ in range(n):
        comeco = time.perf_counter()
        ph.hash(SENHA)
        hashes.append(time.perf_counter() - comeco)
    for _ in range(n):
        comeco, comeco_cpu = time.perf_counter(), time.process_time()
        ph.verify(HASH, SENHA)
        relogio.append(time.perf_counter() - comeco)
        cpu.append(time.process_time() - comeco_cpu)
    print(f"hash: {ms(statistics.median(hashes))} (mediana de {n})")
    print(
        f"verify: {ms(statistics.median(relogio))} de relógio, "
        f"{ms(statistics.median(cpu))} de CPU (mediana de {n})"
    )


def ato_3() -> None:
    n = 20
    comeco = time.perf_counter()
    for _ in range(n):
        ph.verify(HASH, SENHA)
    serie = time.perf_counter() - comeco

    comeco = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: ph.verify(HASH, SENHA), range(n)))
    threads = time.perf_counter() - comeco

    print(f"{n} verify em sequência: {ms(serie)}")
    print(f"{n} verify em 4 threads: {ms(threads)}")


async def main() -> None:
    print("== Ato 0: quanto custa um ==")
    ato_0()
    print()
    print("== Ato 1: o verify no loop ==")
    await mede(login_no_loop)
    print()
    print("== Ato 2: o verify numa thread (asyncio.to_thread) ==")
    await mede(login_na_thread)
    print()
    print("== Ato 3: o GIL ==")
    ato_3()


if __name__ == "__main__":
    asyncio.run(main())
