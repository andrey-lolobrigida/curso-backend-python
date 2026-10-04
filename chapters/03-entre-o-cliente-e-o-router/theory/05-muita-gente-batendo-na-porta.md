# Lição 05 — Muita gente batendo na porta

A lição 03 prometeu duas camadas no FairFare. A lição 04 entregou a primeira. Esta é a segunda — e ela é a camada que a lição 02 deixou faltando.

## A dor, medida

Suba o FairFare como sempre e dispare cem requests de uma vez, com o `carga.py` da bancada:

```console
$ uv run uvicorn app.main:app --port 8000
$ uv run python chapters/03-entre-o-cliente-e-o-router/bancada/carga.py http://localhost:8000/users 100
100 requests em 0.12s  status → 200: 100
```

Cem requests, cem `200`, em pouco mais de um décimo de segundo. Cada uma abriu sessão no banco, rodou a query e voltou com JSON.

E é **um cliente só**. Um script, uma máquina, um IP. O FairFare atendeu todos os cem pedidos dele com o mesmo carinho com que atenderia cem pessoas diferentes — porque ele não faz ideia de que é a mesma pessoa cem vezes.

O freio da lição 02 não resolve isso. O `--limit-concurrency` conta **conexões simultâneas**, não clientes: ele recusaria a centésima por ser a centésima, e recusaria igual se as cem viessem de cem pessoas legítimas. Fusível, não segurança. Lembra?

O que falta é contar **por cliente**. E contar por cliente exige responder a uma pergunta chata: contar o quê, exatamente?

## O balde de fichas

A resposta ingênua é "N requests por minuto". Ela tem um defeito que aparece na borda: com uma janela fixa de 60 por minuto, alguém manda 60 às 12:00:59 e mais 60 às 12:01:00. São 120 requests em um segundo, e nenhuma das duas janelas foi violada. A janela fixa é justa no papel e injusta no relógio.

O padrão que a indústria usa em vez disso é o **token bucket**, o balde de fichas.

Imagine um balde com 20 fichas. Ele goteja: cinco fichas novas por segundo, até encher de novo — nunca passa de 20. Toda request pega uma ficha. Tem ficha, entra. Balde vazio, espera.

Repare no que a analogia compra. Um cliente parado juntou fichas, então ele pode chegar e mandar **vinte de uma vez** — a rajada é permitida, e rajada é o comportamento normal de uma página que carrega várias coisas ao abrir. Mas a média sustentada dele nunca passa de cinco por segundo, porque é isso que goteja. Rajada curta: sim. Torneira aberta: não.

Agora o rigor, que são duas fórmulas e nada mais.

**Quantas fichas há agora**, dado o tempo passado desde a última vez que olhamos:

```
fichas = min(capacidade, fichas_de_antes + tempo_passado × recarga)
```

**Quanto falta esperar**, quando não deu ficha:

```
espera = (1 − fichas) / recarga
```

A segunda fórmula é a que vira o header `Retry-After`. Se sobrou 0,2 de ficha e a recarga é 5/s, falta `(1 − 0,2) / 5 = 0,16s`. Arredondando para cima, `Retry-After: 1`.

Note o que o balde **não** guarda: um histórico de requests. Nada de lista de timestamps, nada de janela deslizante para varrer. Dois números por cliente — quantas fichas e quando foi a última vez — e as fórmulas reconstroem o resto. É por isso que ele cabe em memória sem virar problema.

## O código

`app/middleware/rate_limit.py`, inteiro:

```python
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
```

É a forma da lição 03, com o passe livre para o que não é `http` e tudo. Três decisões merecem nome.

**ASGI puro, e não `BaseHTTPMiddleware`.** Olhe o `_recusar`: dois `send` e acabou. Nenhum `await self.app(...)`. O router nunca soube que essa request existiu — nenhuma sessão de banco aberta, nenhuma validação, nenhuma query. É a regra da lição 03 aplicada: *se você só quer olhar, o fácil serve; se precisa controlar, ASGI puro.* Recusar é controlar. E é o mesmo motivo pelo qual o `CORSMiddleware` responde o preflight sozinho.

**A chave é `scope["client"][0]`**, o IP que o servidor colocou no `scope`. Anote a ressalva, e ela é grande: **a lição 08 vai desmontar essa linha.** Assim que existir um proxy reverso na frente do app, `scope["client"]` passa a ser o IP do proxy — e o balde vira um balde só, para o mundo inteiro. A correção tem nome e tem armadilha; é lá.

**O relógio é injetado.** `relogio: Relogio = time.monotonic` — em produção é o relógio de verdade; no teste é um objeto que você manda avançar. Duas coisas de graça nisso. Primeiro, `time.monotonic` (e não `time.time`) porque ele nunca anda para trás: um ajuste de NTP no meio do dia não pode fazer o seu balde recarregar dez minutos de uma vez. Segundo, o teste não dorme — e é a próxima seção.

## Os testes que não dormem

Um teste de rate limit é o candidato natural a `sleep`. "Estoura o balde, dorme um segundo, tenta de novo." Funciona, e apodrece: a suíte fica lenta, e fica instável na máquina lenta do CI.

Com o relógio injetado, o teste manda no tempo:

```python
class RelogioFalso:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


async def test_avancar_o_relogio_libera():
    middleware, relogio = montar(capacidade=1, recarga=1.0)
    async with cliente(middleware) as c:
        assert (await c.get("/")).status_code == 200
        assert (await c.get("/")).status_code == 429
        relogio.avancar(1.0)
        assert (await c.get("/")).status_code == 200
```

Um segundo de tempo simulado, zero segundo de tempo real. (Essa ideia volta no capítulo 8, quando tarefas em segundo plano precisarem de "daqui a cinco minutos" sem esperar cinco minutos.)

E tem outra coisa aí, que vale dizer em voz alta: **o rate limiter não sabe que o FairFare existe.** Ele não importa router, não importa modelo, não toca no banco. É um app ASGI que embrulha outro app ASGI — e por isso o teste embrulha um app de brinquedo de quatro linhas:

```python
async def app_de_brinquedo(scope, receive, send) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})
```

Sem banco, sem fixture de sessão, sem migração. Quando um componente não conhece o resto do sistema, o teste dele também não precisa conhecer. Isso não é sorte: é o que a fronteira ASGI compra.

Falta fingir que somos dois clientes diferentes. O `httpx2` deixa dizer qual `client` vai no `scope`:

```python
def cliente(middleware, ip: str = "10.0.0.1") -> AsyncClient:
    transport = ASGITransport(app=middleware, client=(ip, 1234))
    return AsyncClient(transport=transport, base_url="http://test")


async def test_clientes_diferentes_tem_baldes_diferentes():
    middleware, _ = montar(capacidade=1)
    async with cliente(middleware, ip="10.0.0.1") as a, cliente(middleware, ip="10.0.0.2") as b:
        assert (await a.get("/")).status_code == 200
        assert (await a.get("/")).status_code == 429
        assert (await b.get("/")).status_code == 200  # o balde do outro está cheio
```

Esse teste é a diferença entre esta lição e a 02 em três asserções: um cliente estourado, o outro intacto.

## A ordem com o CORS

Agora o `app/main.py`. E aqui a lição 03 cobra o que ensinou.

```diff
 from fastapi import FastAPI
 from fastapi.middleware.cors import CORSMiddleware

+from app.middleware.rate_limit import RateLimitMiddleware
 from app.routers import bookings, resources, users

 app = FastAPI(title="FairFare")

+# Ordem importa, e é invertida: o ÚLTIMO add_middleware é a camada de FORA.
+# Rate limiter por dentro, CORS por fora. Assim o preflight (OPTIONS) é respondido
+# pelo CORS sem gastar ficha, e um 429 atravessa o CORS e sai com os headers —
+# senão o browser mostra "erro de CORS" e esconde o 429 de verdade.
+app.add_middleware(RateLimitMiddleware, capacidade=20, recarga_por_segundo=5.0)
+
 # A página da bancada mora em http://localhost:8080. Origem explícita: nada de "*".
```

Rate limiter registrado **antes** do CORS, logo **por dentro** dele. Duas consequências, e as duas são o motivo.

**O preflight não gasta ficha.** O `OPTIONS` é respondido pelo `CORSMiddleware`, que está por fora — a request nunca chega ao balde. Faz sentido: o preflight é burocracia do browser, não é o cliente pedindo dados. Cobrar ficha por ele seria cobrar do usuário do browser uma request que ele não pediu — e só dele, porque o `curl` nunca manda preflight.

**O 429 sai carimbado.** Como o CORS é a camada de fora, a resposta de recusa passa por ele na saída e ganha o `Access-Control-Allow-Origin`. Inverta a ordem e veja o estrago: o rate limiter, por fora, responde 429 sem nunca chamar o CORS; a resposta sai sem o header; o browser da lição 04 olha, não acha o carimbo e esconde tudo. Você vê "erro de CORS" no console e passa a tarde investigando CORS, e o problema era rate limit.

Um teste segura essa decisão no lugar:

```python
async def test_429_atravessa_o_cors(client):
    origem = "http://localhost:8080"
    respostas = [await client.get("/users", headers={"Origin": origem}) for _ in range(40)]
    recusadas = [r for r in respostas if r.status_code == 429]
    assert recusadas, "40 requests seguidas e nenhum 429: o rate limiter não está na pilha"
    for r in recusadas:
        assert r.headers["access-control-allow-origin"] == origem
```

Isto é uma **decisão**, não uma lei da natureza. Ela pode ser tomada errado — e o bloco 1 dos exercícios chega com ela tomada errado, para você consertar.

## A linha estranha no `conftest.py`

O commit traz uma linha que não parece ter nada a ver:

```python
    # O rate limiter guarda os baldes em memória — no processo do pytest também.
    # O Starlette monta a pilha de middlewares na primeira chamada ao app (sob o uvicorn
    # é o lifespan; aqui, sem lifespan, é a primeira request) e a guarda aqui;
    # zerar força uma pilha nova (e um limitador de balde cheio) para cada teste.
    fastapi_app.middleware_stack = None
```

Ela existe porque **estado em memória é estado do processo — inclusive do processo do pytest**. A suíte inteira roda num app só, como um cliente só (`127.0.0.1`), num balde só. O `test_429_atravessa_o_cors` dispara 40 requests de propósito e deixa o balde no chão. Quem vier depois herda o balde vazio.

Comentando a linha, aqui:

```
13 failed, 9 passed in 0.14s
FAILED tests/test_smoke.py::test_cria_e_busca_usuario - assert 429 == 201
FAILED tests/test_smoke.py::test_email_invalido_e_422 - assert 429 == 422
...
```

Treze testes. O `test_smoke.py` inteiro, do capítulo 1, quebrado por um middleware que ele nem sabe que existe — e quebrado com a mensagem mais desnorteante possível: `assert 429 == 201`.

Essa cena é um ensaio. Estado guardado em memória de processo é confortável e traiçoeiro: funciona sozinho, some quando o processo reinicia, e não existe para o processo vizinho. Com dois workers de uvicorn, são dois baldes — e o cliente ganha **até** o dobro do limite. E o dicionário nunca esquece um IP: cada cliente novo vira uma entrada permanente, e quem decide quantos IPs aparecem é justamente o tráfego que o limitador deveria conter. São duas limitações declaradas deste código, escritas no topo do módulo, e o capítulo 7 resolve as duas tirando o balde da memória e colocando no Redis — onde cada entrada carrega um TTL e expira sozinha.

## A medição depois

Mesmo `carga.py`, mesmas cem requests, mesmo cliente:

```console
$ uv run python $C http://localhost:8000/users 100
100 requests em 0.11s  status → 200: 20  429: 80  (Retry-After: 1s)

$ sleep 5
$ uv run python $C http://localhost:8000/users 100
100 requests em 0.10s  status → 200: 20  429: 80  (Retry-After: 1s)
```

Vinte passam, oitenta levam 429. Exatamente a capacidade do balde — e a segunda rajada dá o mesmo, porque cinco segundos parado a 5 fichas/s reenchem o balde de 20 com folga.

Um `curl` logo depois, ainda dentro da janela do estouro:

```console
$ curl -s -i localhost:8000/users
HTTP/1.1 429 Too Many Requests
server: uvicorn
content-type: application/json
content-length: 76
retry-after: 1

{"detail":"muitas requests deste cliente; tente de novo em alguns segundos"}
```

E cinco segundos depois, `200`.

O `429 Too Many Requests` é a resposta certa, e o `Retry-After` é a metade educada dela: em vez de "não", ele diz "não, e tente de novo em 1 segundo". Um cliente bem-feito lê esse número e para de martelar. Compare com o `503` da lição 02 — que também dizia não, mas dizia para todo mundo igual, e sem prazo.

Essa é a diferença que este commit comprou: o app agora sabe que os cem pedidos vieram da mesma pessoa.

Guarde a frase abaixo do jeito que ela está. A lição 08 volta para desmontá-la:

> o rate limit protege o app de um cliente abusado.

## O que você deve conseguir fazer agora

- Explicar o token bucket com as duas fórmulas: `min(capacidade, fichas + tempo × recarga)` e `(1 − fichas) / recarga` — e dizer por que ele permite rajada onde a janela fixa é injusta na borda.
- Dizer por que o relógio é injetado no middleware, e o que isso faz com o `sleep` do teste.
- Justificar a ordem entre CORS e rate limiter com o cenário concreto do preflight e o do 429 sem carimbo.
- Explicar por que dá para testar o rate limiter com um app de brinquedo e nenhum banco.
- Dizer o que acontece com os baldes quando o app sobe com dois workers.
