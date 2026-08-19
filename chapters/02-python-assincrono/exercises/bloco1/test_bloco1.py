import asyncio
import time

import pytest
from httpx2 import ASGITransport, AsyncClient

from rotas import app


async def tempo_de_n_requests(caminho: str, n: int = 5) -> float:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60) as client:
        comeco = time.perf_counter()
        await asyncio.gather(*(client.get(caminho) for _ in range(n)))
        return time.perf_counter() - comeco


@pytest.mark.parametrize("caminho", ["/rapida", "/lenta", "/misteriosa"])
async def test_rota_nao_serializa(caminho):
    total = await tempo_de_n_requests(caminho, n=5)
    assert total < 1.5, (
        f"{caminho} levou {total:.2f}s para 5 requests de ~0.3s — está bloqueando o loop"
    )
