"""O rate limiter não sabe que o FairFare existe. Por isso dá para testá-lo sem banco:
um app ASGI de brinquedo, um relógio falso, zero sleep."""

from httpx2 import ASGITransport, AsyncClient

from app.middleware.rate_limit import RateLimitMiddleware


class RelogioFalso:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


async def app_de_brinquedo(scope, receive, send) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def montar(capacidade: int = 3, recarga: float = 1.0):
    relogio = RelogioFalso()
    middleware = RateLimitMiddleware(
        app_de_brinquedo, capacidade=capacidade, recarga_por_segundo=recarga, relogio=relogio
    )
    return middleware, relogio


def cliente(middleware, ip: str = "10.0.0.1") -> AsyncClient:
    transport = ASGITransport(app=middleware, client=(ip, 1234))
    return AsyncClient(transport=transport, base_url="http://test")


async def test_n_requests_passam_e_a_seguinte_leva_429():
    middleware, _ = montar(capacidade=3)
    async with cliente(middleware) as c:
        codigos = [(await c.get("/")).status_code for _ in range(3)]
        quarta = await c.get("/")
    assert codigos == [200, 200, 200]
    assert quarta.status_code == 429
    assert quarta.headers["retry-after"] == "1"  # 1 ficha a 1 ficha/s, arredondado para cima
    assert quarta.json()["detail"]


async def test_avancar_o_relogio_libera():
    middleware, relogio = montar(capacidade=1, recarga=1.0)
    async with cliente(middleware) as c:
        assert (await c.get("/")).status_code == 200
        assert (await c.get("/")).status_code == 429
        relogio.avancar(1.0)
        assert (await c.get("/")).status_code == 200


async def test_retry_after_arredonda_para_cima():
    middleware, _ = montar(capacidade=1, recarga=0.4)  # 1 ficha leva 2,5s
    async with cliente(middleware) as c:
        await c.get("/")
        resp = await c.get("/")
    assert resp.status_code == 429
    assert resp.headers["retry-after"] == "3"


async def test_clientes_diferentes_tem_baldes_diferentes():
    middleware, _ = montar(capacidade=1)
    async with cliente(middleware, ip="10.0.0.1") as a, cliente(middleware, ip="10.0.0.2") as b:
        assert (await a.get("/")).status_code == 200
        assert (await a.get("/")).status_code == 429
        assert (await b.get("/")).status_code == 200  # o balde do outro está cheio


async def test_429_atravessa_o_cors(client):
    """Integração com o FairFare: o CORS é a camada de fora, então o 429 sai com os headers.
    Sem isso o browser mostraria 'erro de CORS' em vez do 429 de verdade."""
    origem = "http://localhost:8080"
    respostas = [await client.get("/users", headers={"Origin": origem}) for _ in range(40)]
    recusadas = [r for r in respostas if r.status_code == 429]
    assert recusadas, "40 requests seguidas e nenhum 429: o rate limiter não está na pilha"
    for r in recusadas:
        assert r.headers["access-control-allow-origin"] == origem
