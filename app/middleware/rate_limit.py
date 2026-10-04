"""Limitação de taxa por cliente: um balde de fichas por endereço IP, em memória.

Middleware ASGI puro. Não sabe que o FairFare existe — só conhece scope, receive, send.

Limitações declaradas (lição 12 do capítulo 3):
- o dicionário de baldes vive neste processo; com vários workers, cada um tem o seu (cap. 7);
- a chave é scope["client"], que atrás de um proxy é o que o servidor confiou (lição 08);
- o dicionário nunca esquece um cliente: cada IP novo vira uma entrada permanente, e quem
  decide quantos IPs aparecem é o próprio tráfego que o limitador deveria conter (cap. 7, via TTL).
"""

import math
import time
from collections.abc import Callable

Relogio = Callable[[], float]


class RateLimitMiddleware:
    def __init__(
        self,
        app,
        capacidade: int = 20,
        recarga_por_segundo: float = 5.0,
        relogio: Relogio = time.monotonic,
    ) -> None:
        self.app = app
        self.capacidade = capacidade
        self.recarga_por_segundo = recarga_por_segundo
        self.relogio = relogio
        # ip -> (fichas disponíveis, instante da última atualização)
        self.baldes: dict[str, tuple[float, float]] = {}

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        cliente = scope["client"][0] if scope.get("client") else "desconhecido"
        espera = self._consumir_ficha(cliente)
        if espera > 0:
            await self._recusar(send, espera)
            return

        await self.app(scope, receive, send)

    def _consumir_ficha(self, cliente: str) -> float:
        """Devolve 0 se havia ficha (e consome uma), ou os segundos até a próxima."""
        agora = self.relogio()
        fichas, ultimo = self.baldes.get(cliente, (float(self.capacidade), agora))

        # O balde goteja: recarrega proporcional ao tempo passado, até o teto.
        fichas = min(self.capacidade, fichas + (agora - ultimo) * self.recarga_por_segundo)

        if fichas >= 1:
            self.baldes[cliente] = (fichas - 1, agora)
            return 0.0

        self.baldes[cliente] = (fichas, agora)
        return (1 - fichas) / self.recarga_por_segundo

    async def _recusar(self, send, espera: float) -> None:
        corpo = b'{"detail":"muitas requests deste cliente; tente de novo em alguns segundos"}'
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(corpo)).encode()),
                    (b"retry-after", str(math.ceil(espera)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": corpo})
