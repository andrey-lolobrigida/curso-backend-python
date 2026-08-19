import asyncio
import inspect
import time

import servico


async def test_operacoes_de_io_nao_serializam():
    comeco = time.perf_counter()
    await asyncio.gather(*(servico.buscar(i) for i in range(5)))
    total = time.perf_counter() - comeco
    assert total < 0.6, f"{total:.2f}s para 5 buscas de ~0.3s — ainda bloqueando"


def test_carregar_config_continua_sincrona():
    assert not inspect.iscoroutinefunction(servico.carregar_config), (
        "carregar_config roda uma vez, na inicialização, sem ninguém na fila: "
        "async aqui só adiciona cerimônia"
    )
    assert servico.carregar_config()["nome"] == "FairFare"


async def test_resumo_pesado_nao_trava_o_loop():
    # O prazo é calculado AQUI, antes de a tarefa começar — de propósito.
    # Se o resumo travar o loop, a batida só acorda com o prazo já vencido.
    fim = time.perf_counter() + 0.5

    async def batida() -> int:
        marcas = 0
        while time.perf_counter() < fim:
            await asyncio.sleep(0.01)
            marcas += 1
        return marcas

    tarefa = asyncio.create_task(batida())
    await servico.resumo_pesado()
    marcas = await tarefa

    assert marcas >= 30, (
        f"o loop bateu só {marcas} vezes em 0,5s (o normal é ~50) — "
        "resumo_pesado travou o event loop; use asyncio.to_thread"
    )
