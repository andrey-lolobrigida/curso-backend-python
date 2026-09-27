# Soluções — capítulo 3

Leia depois de tentar. Uma solução lida antes da tentativa vira informação; depois da tentativa, vira entendimento.

Cada item tem o código consertado, **por que aquele conserto e não outro**, e como você poderia ter chegado nele sozinho.

Os três blocos são pequenos de propósito, mas as decisões deles são grandes: uma delas é a mesma que você vai tomar em todo app que tiver mais de um middleware.

---

## Bloco 1 — Depurar: bloqueia demais e bloqueia de menos

São dois defeitos. Eles ficam a quarenta linhas de distância um do outro, e é só isso que têm em comum.

### Como localizar, antes de consertar

O enunciado já entrega a primeira pista: **a segunda rodada do `carga.py`, três segundos depois, dá `429: 10`.** Um balde de capacidade 5 que recarrega a uma ficha por segundo deveria ter três fichas ali. Não tem nenhuma. E o servidor ainda manda `Retry-After: 1`, ou seja, ele *acha* que vai liberar em um segundo — está errado, e nem sabe.

Repare no que essa medição já elimina. O balde não está travado em "sem ficha": ele nunca recarrega. As duas fórmulas da lição 05 são

```
fichas = min(capacidade, fichas_de_antes + tempo_passado × recarga)
espera = (1 − fichas) / recarga
```

A segunda está claramente funcionando — o `Retry-After: 1` sai dela. Logo o problema é a primeira. Você chegou na linha certa sem ter aberto o arquivo.

O segundo defeito não aparece no `carga.py`, porque o `carga.py` não é um browser. Ele aparece no teste — e o motivo de ele aparecer só ali é metade da lição.

### Defeito 1 — a recarga que nunca acontece

O código entregue:

```python
if agora < ultimo:  # "só recarrega se o tempo andou"
    fichas = min(self.capacidade, fichas + (agora - ultimo) * self.recarga_por_segundo)
```

O conserto é **apagar o `if`**:

```python
def _consumir_ficha(self, cliente: str) -> float:
    agora = self.relogio()
    fichas, ultimo = self.baldes.get(cliente, (float(self.capacidade), agora))
    fichas = min(self.capacidade, fichas + (agora - ultimo) * self.recarga_por_segundo)
    if fichas >= 1:
        self.baldes[cliente] = (fichas - 1, agora)
        return 0.0
    self.baldes[cliente] = (fichas, agora)
    return (1 - fichas) / self.recarga_por_segundo
```

**Por que ele nunca rodava.** `ultimo` é uma leitura anterior do mesmo relógio. O relógio é `time.monotonic`, e a lição 05 disse por que ele foi escolhido: *ele nunca anda para trás*. Então `agora < ultimo` é uma condição que, por construção, nunca é verdade. O comentário ao lado (`"só recarrega se o tempo andou"`) descreve a intenção certa e o código faz o contrário dela — é o tipo de linha que passa em revisão porque a gente lê o comentário e acredita.

**Por que apagar, e não inverter o sinal.** `if agora > ultimo:` também deixa os três testes verdes. Eu rodei; passa. E mesmo assim está pior, por um motivo que não é gosto: **a guarda não protege de nada.** Olhe o caso que ela existiria para tratar, `agora == ultimo`:

```
fichas + (agora - ultimo) * recarga  →  fichas + 0 * recarga  →  fichas
```

A fórmula já devolve a resposta certa para tempo zero. A guarda é um `if` que só sabe decidir entre "a fórmula" e "o resultado que a fórmula daria". Um caso especial a menos é uma linha a menos para ler, um ramo a menos para testar, e um lugar a menos onde um sinal pode estar trocado — que é literalmente o defeito que você acabou de consertar.

A regra por trás: **quando um caso especial e o caso geral dão a mesma resposta, o caso especial é ruído.** Guarde-a, porque ela aparece muito mais em código de negócio do que em código de rate limit.

### Defeito 2 — a ordem da pilha

O código entregue registrava assim:

```python
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:8080"], allow_methods=["GET", "POST"]
)
app.add_middleware(RateLimitMiddleware)
```

O conserto é trocar as duas de lugar:

```python
# Ordem invertida: o ÚLTIMO add_middleware é a camada de FORA (lição 03).
# Rate limiter por dentro, CORS por fora — preflight não gasta ficha, e o 429 sai carimbado.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:8080"], allow_methods=["GET", "POST"]
)
```

Nada dentro das classes mudou. Duas linhas mudaram de ordem.

**Por quê**, com a regra da lição 03 na mão — *`add_middleware` empilha: o último registrado é a camada de fora*. No código quebrado, o rate limiter era a camada de fora. Duas consequências, e as duas estão no teste:

- **O preflight gastava ficha.** O `OPTIONS` batia primeiro no balde. Um preflight é burocracia do browser, não é o cliente pedindo dados — e a lição 04 lembrou que *praticamente toda API JSON leva preflight*. Cobrar ficha por ele é cobrar do usuário do browser uma request que ele não pediu. Pior: com o balde vazio, o preflight leva `429`, o browser conclui que a origem não é permitida, e o `POST` que viria depois nunca sai.
- **O `429` saía sem CORS.** O rate limiter, por fora, respondia sozinho e nunca chamava o CORS — então a resposta ia embora sem `Access-Control-Allow-Origin`. O browser olha, não acha o carimbo e **esconde a resposta inteira**, status incluído. No console aparece "erro de CORS". Você passa a tarde investigando CORS, e o problema era rate limit.

Depois do conserto, com o balde no chão de propósito:

```console
$ curl -s -i localhost:8200/users -H 'Origin: http://localhost:8080'
HTTP/1.1 429 Too Many Requests
server: uvicorn
content-type: application/json
content-length: 28
retry-after: 1
access-control-allow-origin: http://localhost:8080
vary: Origin

$ curl -s -o /dev/null -w "preflight → %{http_code}\n" -X OPTIONS localhost:8200/users \
    -H 'Origin: http://localhost:8080' -H 'Access-Control-Request-Method: POST'
preflight → 200
```

Um `429` que o browser consegue ler, e um preflight que atravessa mesmo com o balde vazio.

### A medição depois, que é a prova do defeito 1

Mesmas duas rodadas do enunciado, mesmo intervalo de três segundos:

```console
$ uv run python $C http://localhost:8200/users 10
10 requests em 0.01s  status → 200: 5  429: 5  (Retry-After: 1s)
$ sleep 3
$ uv run python $C http://localhost:8200/users 10
10 requests em 0.01s  status → 200: 3  429: 7  (Retry-After: 1s)
```

Três segundos, uma ficha por segundo, **três passaram**. O `Retry-After` deixou de ser mentira.

### A frase que fecha o bloco

Um conserto é **aritmética de tempo**: uma comparação invertida dentro de uma função de dez linhas. O outro é **topologia da pilha**: quem embrulha quem, decidido fora de qualquer classe.

Eles são independentes **de verdade**, e dá para provar. Consertei um de cada vez, em cópias separadas:

```
### SÓ o defeito 1 consertado (apaguei o if)
FAILED test_preflight_nao_gasta_ficha_e_429_sai_com_cors
1 failed, 2 passed

### SÓ o defeito 2 consertado (troquei a ordem)
FAILED test_o_balde_recarrega_com_o_tempo
1 failed, 2 passed
```

Cada conserto move exatamente o seu teste e não encosta no do outro. Isso é raro e é bom notar quando acontece, porque o padrão mais comum — o do capítulo 2 — é o contrário: um conserto que revela o próximo.

O que **é** confuso aqui é outra coisa, e é a lição de método do bloco: **os dois defeitos aparecem na tela como `429`.** Um é `429` demais (o balde que nunca solta). O outro é `429` de menos, no sentido de informação: o status até sai, mas sem o carimbo de CORS, e aí o browser esconde a resposta inteira e escreve "erro de CORS" no console. Mesmo número, duas histórias, e uma delas nem chega a ser lida por quem precisava lê-la.

É por isso que o `carga.py` sozinho não fecha o diagnóstico. Ele mostra o defeito 1 na primeira olhada e é **cego** para o defeito 2 — porque ele não é um browser, e nada no `httpx2` se importa com `Access-Control-Allow-Origin`. Um ferramental que só mede um lado te dá um relatório limpo de um problema pela metade.

---

## Bloco 2 — Estender: um proxy que serve duas apps

### O código

```python
def criar_proxy(upstreams: dict[str, httpx2.AsyncClient]) -> Starlette:
    # Prefixo mais longo primeiro: se houvesse /reservas e /reservas/premium, o segundo
    # tem que ser testado antes, senão o primeiro engole tudo.
    rotas = sorted(upstreams.items(), key=lambda par: len(par[0]), reverse=True)

    async def repassar(request: Request) -> Response:
        for prefixo, upstream in rotas:
            if request.url.path.startswith(prefixo):
                break
        else:
            return Response("nenhum upstream para este caminho", status_code=404)

        caminho = request.url.path.removeprefix(prefixo) or "/"
        ...  # daqui para baixo, nada mudou
```

Seis linhas novas. O resto do arquivo ficou intacto — e isso é parte do exercício: **refatoração que muda o contrato do proxy não é refatoração, é bug.** O teste que já estava verde é quem segura isso.

### As três decisões dentro dessas seis linhas

**1. Prefixo mais longo primeiro.** Um dicionário Python preserva a ordem de inserção, então "iterar `upstreams`" já daria os dois testes verdes com o dicionário do teste. E estaria errado por sorte. Se um dia entrasse `{"/reservas": a, "/reservas/premium": b}`, `/reservas/premium/x` casaria com `/reservas` e o `/reservas/premium` nunca seria alcançado — um upstream inteiro inacessível, e nenhum erro em lugar nenhum. Ordenar por tamanho decrescente custa uma linha e tira a rota da mão da sorte.

Isso não é invenção nossa: é a regra do nginx. Entre os `location` de prefixo, vence o que casa o trecho **mais longo** — não o que aparece primeiro no arquivo. Você está reimplementando uma regra que já existe porque ela é a única que não surpreende.

**2. `404`, e não "o primeiro que aparecer".** Um proxy que não sabe para onde mandar tem exatamente duas saídas honestas: dizer que não sabe, ou ter um upstream padrão declarado. Despejar no primeiro do dicionário não é nenhuma das duas — é um roteamento que depende da ordem de um `dict` que ninguém escreveu pensando em ser rota padrão. O `for/else` do Python diz isso bem: o `else` é o "acabou a lista sem `break`".

Vale notar que este `404` é do **proxy**, não do upstream. São coisas diferentes e um dia isso vai te custar meia hora: `/reservas/nao-existe` dá 404 vindo lá de dentro, `/outra/coisa` dá 404 sem nenhum upstream ter sido consultado. O corpo diferente é o que te diz qual dos dois foi.

**3. `removeprefix`, e o `or "/"`.** `"/reservas".removeprefix("/reservas")` é `""`, e string vazia não é caminho. O `or "/"` já estava no código entregue e continua fazendo falta.

### O `Host`, e por que aqui ele atravessa

O `Host` original chega ao upstream, e isso não é descuido — é o teste que já estava verde:

```python
assert corpo["host"] == "proxy.test"  # Host preservado
```

Ele atravessa porque o filtro de headers só tira hop-by-hop, e `host` não é hop-by-hop. Se você copiou o `!= "host"` do `proxy.py` da bancada por reflexo, o teste te avisou na hora:

```
E       AssertionError: assert 'reservas' == 'proxy.test'
```

`'reservas'` é o host do `base_url` do cliente httpx — ou seja, o upstream passou a ver o nome *dele mesmo* no lugar do nome pelo qual o mundo o chamou.

**As duas escolhas são legítimas, e a diferença é o que o upstream precisa saber.**

- **Tirar o `Host`** (bancada, `bancada/proxy.py`: *"host sai: o httpx põe o do upstream"*) é o mais simples e serve quando o app de dentro não liga para o nome pelo qual foi chamado. Ele passa a ver `127.0.0.1:8000`, que é a verdade da conexão que ele recebeu.
- **Preservar o `Host`** (nginx, `bancada/nginx.conf` e lição 07: `proxy_set_header Host $host;`) é o que se usa quando o app precisa do nome público — para montar URLs absolutas que voltam para o cliente (um `Location:` de redirect, um link em e-mail), para servir domínios diferentes do mesmo processo, ou para qualquer log que precise dizer *por qual porta de entrada* aquilo veio.

A pergunta que decide: **o app de dentro alguma vez precisa escrever a própria URL pública?** Se sim, preserve. Se não, tanto faz — e aí o mais simples ganha.

Repare que o `X-Forwarded-For` na linha seguinte segue a regra oposta, e de propósito: ele é **sobrescrito**, porque o que veio de fora nesse header é palavra de estranho (lição 08). `Host` você repassa, `X-Forwarded-*` você declara. A diferença é quem tem a informação: só o cliente sabe por qual nome ele chamou; só o proxy sabe quem realmente conectou.

### Uma sutileza que o teste não cobra

`startswith(prefixo)` casa `/reservasx/y` com `/reservas`. O `caminho` viraria `x/y` — sem a barra da frente — e o upstream receberia uma request torta. O conserto é exigir a fronteira:

```python
def casa(caminho: str, prefixo: str) -> bool:
    return caminho == prefixo or caminho.startswith(prefixo + "/")
```

Não coloquei isso na solução principal porque o enunciado não pediu e nenhum teste cobra. Mas é o tipo de coisa que um proxy de verdade trata, e agora você sabe que existe. (No nginx é a mesma pegadinha: `location /reservas` casa `/reservasx` também. Quem quer a fronteira escreve `location /reservas/`, com a barra. Mesmo problema, outra língua.)

### O bônus: o `Retry-After` do upstream

**Ele atravessa intacto, e é isso que a gente quer.**

Por quê: `Retry-After` **não é hop-by-hop**. Hop-by-hop são os headers que descrevem *uma conexão* e não a mensagem — `Connection`, `Keep-Alive`, `Transfer-Encoding`, `TE`, `Trailer`, `Upgrade` — e são justamente os do conjunto `HOP_BY_HOP` do arquivo. O `Retry-After` descreve a **mensagem**: é uma informação do serviço para o cliente final. Ele passa pelo filtro sem ser tocado.

Montei um upstream de brinquedo que devolve `429` com `Retry-After: 30` e um `Connection: close` junto, para ver os dois caminhos ao mesmo tempo:

```
status: 429
retry-after: 30
connection: None
```

O `Retry-After` chegou; o `Connection` foi barrado. E foi o **seu** filtro que barrou: conferi o que o `httpx2` entrega ao proxy e o `connection: close` está lá, inteiro, antes do dicionário de `headers_de_volta` ser montado.

E é o comportamento certo: **quem contou as fichas é o upstream, e o número é dele.** O proxy não tem informação melhor. A tentação — que um proxy real aprende a resistir — é *acrescentar* segundos: somar o tempo que ele mesmo levou, arredondar "para garantir", inventar um valor mais conservador. Nada disso é medição; é um número inventado com cara de medição, e o cliente não tem como saber a diferença. Se o próprio proxy tiver um limite dele, a resposta certa é ele emitir o **próprio** `429` com o **próprio** `Retry-After`, não editar o do vizinho.

---

## Bloco 3 — Refatorar: o middleware que faz tudo

Este é o bloco onde os testes de comportamento já estavam verdes e mesmo assim havia trabalho. Vale nomear o que estava errado antes de mostrar o certo: o `FazTudo` tem **três razões para mudar**. Um dia alguém troca a política de CORS, e precisa entender rate limit para fazer isso com segurança. Não é um bug — é um custo, cobrado toda vez que alguém encostar no arquivo.

### O que vira o quê

Três peças, três decisões diferentes.

#### 1. O CORS vira `CORSMiddleware` do Starlette

```python
from fastapi.middleware.cors import CORSMiddleware
```

E as vinte linhas de preflight na mão somem.

O enunciado pediu para você abrir o fonte e achar pelo menos uma coisa que o pronto faz e o seu não. Abrindo `starlette/middleware/cors.py` (Starlette 1.3.1 aqui), no método `preflight_response`, são pelo menos três:

**Ele confere se o método pedido é permitido.**

```python
requested_method = request_headers["access-control-request-method"]
...
if requested_method not in self.allow_methods:
    failures.append("method")
```

O `FazTudo` lê `access-control-request-method` só para saber que aquilo *é* um preflight, e depois responde `Access-Control-Allow-Methods: GET, POST` para qualquer coisa. Ele diz "pode GET e POST" sem nunca ter olhado o que foi pedido.

Mandei **o mesmo preflight** para os dois, no mesmo processo — `Access-Control-Request-Method: DELETE`, `Access-Control-Request-Headers: authorization`. O `FazTudo`:

```
--- FazTudo (exercises/bloco3) ---
status: 200
allow-methods: GET, POST
allow-headers: content-type
vary: None
max-age: None
corpo:
```

O Starlette, na mesma request:

```
--- Starlette (refatorado) ---
status: 400
allow-methods: GET, POST
allow-headers: Accept, Accept-Language, Content-Language, Content-Type
vary: Origin
max-age: 600
corpo: Disallowed CORS method, headers
```

Seis linhas, cinco diferenças — e elas cobrem as três coisas desta seção de uma vez.

Comece pelo `200` contra o `400`, e desfaça a leitura errada que ele convida: o `FazTudo` **não** autorizou o `DELETE`. Ele respondeu `200` com `Access-Control-Allow-Methods: GET, POST`, e é essa lista que o browser lê — `DELETE` não está nela, então o browser barra do mesmo jeito. **Quem faz cumprir a política de CORS é o browser, sempre.** Com o `200` do `FazTudo`, o servidor diz "tudo certo": o access log mostra `200`, o `curl` mostra `200`, e a recusa só existe dentro do browser. Com o `400`, a recusa aparece do lado do servidor — `400` no log e na coluna de status da aba de rede, e o corpo `Disallowed CORS method, headers` no `curl` das onze da noite. O próprio Starlette diz que o `400` é informação, não bloqueio, em comentário, três linhas antes de escolhê-lo (`cors.py:143-145`):

> *"We don't strictly need to use 400 responses here, since its up to the browser to enforce the CORS policy, but its more informative if we do."*

E repare no corpo dessa resposta: `method, headers`, no plural. **São duas reclamações, não uma** — e a segunda é a próxima subseção.

**Ele confere os headers pedidos.**

```python
elif requested_headers is not None:
    for header in [h.lower() for h in requested_headers.split(",")]:
        if header.strip() not in self.allow_headers:
            failures.append("headers")
            break
```

É o `headers` do `Disallowed CORS method, headers`: eu pedi `authorization`, o Starlette olhou a lista dele, não achou, e reclamou.

Agora compare com a linha `allow-headers: content-type` do `FazTudo`. Ele também não permite `authorization` — mas ele nunca olhou o que foi pedido. Respondeu `content-type` porque `content-type` é o que está escrito no arquivo dele, e responderia `content-type` para qualquer coisa. O browser barra os dois; só um dos dois te diz por quê.

Isso é uma bomba-relógio com data marcada — o capítulo 5 traz `Authorization`, o browser vai pedir, e o preflight vai falhar por um motivo que não aparece em lugar nenhum do seu código.

**Ele manda `Access-Control-Max-Age`.**

```python
preflight_headers.update(
    {
        "Access-Control-Allow-Methods": ", ".join(allow_methods),
        "Access-Control-Max-Age": str(max_age),
    }
)
```

Com `max_age=600` no padrão. É o header que faz o browser guardar o preflight por dez minutos (lição 04). Na medição acima ele aparece dos dois lados: `600` no Starlette, `None` no `FazTudo`. Sem ele, **todo** `POST` da sua API vira duas viagens de rede em vez de uma — o `FazTudo` está funcionando e cobrando o dobro de idas e voltas de todo mundo, silenciosamente.

E tem uma quarta, de brinde, também visível na medição: o `vary: None`. O Starlette põe `Vary: Origin` **também** na resposta de preflight (com origens explícitas, como aqui — com `["*"]` sem credenciais ele não põe); o `FazTudo` só põe nas respostas normais. `Vary` é o que impede um cache no meio do caminho de servir a resposta de uma origem para outra.

**A moral:** CORS parece um `if` e é uma especificação. Escrever à mão a parte que você entendeu produz código que passa nos seus testes e conversa mal com o browser em tudo que você não pensou — sem `Vary`, sem `Max-Age`, e sem nunca ler o que foi perguntado. Nada disso quebra hoje. Tudo isso vira uma tarde perdida algum dia. Esta é a peça a **não** escrever.

#### 2. O rate limit vira um `RateLimitMiddleware` ASGI puro

É o da lição 05, com o relógio injetado apontando para o `RELOGIO` do módulo. **O trecho abaixo é um esqueleto, não é copiável como está:** os `...` marcam o corpo do `__init__`, e `_consumir_ficha` e `_recusar` não aparecem aqui. Cole os três da lição 05 (ou do `app/middleware/rate_limit.py` do FairFare) e troque só os defaults — capacidade, recarga e o relógio:

```python
class RateLimitMiddleware:
    def __init__(
        self,
        app,
        capacidade: int = CAPACIDADE,
        recarga_por_segundo: float = RECARGA_POR_SEGUNDO,
        relogio=RELOGIO,
    ) -> None:
        ...

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
```

ASGI puro **porque ele precisa recusar**. O `_recusar` são dois `send` e acabou: nenhum `await self.app(...)`, nenhum router, nenhuma sessão de banco. É a regra da lição 03 — *se você só quer olhar, o fácil serve; se precisa controlar, ASGI puro* — e recusar é controlar.

Duas coisas que vieram de graça na conversão e não estavam no `FazTudo`:

- **O passe livre para `scope["type"] != "http"`.** O `BaseHTTPMiddleware` esconde isso de você; escrevendo ASGI puro, a guarda é sua responsabilidade e está lá.
- **A guarda do `scope.get("client")`.** `scope["client"]` pode ser `None` — num transporte que não é TCP, por exemplo. O `FazTudo` fazia `request.client.host` direto, que é um `AttributeError` esperando a hora certa. A linha é a mesma da lição 05.

#### 3. O carimbo vira um `CarimboMiddleware` ASGI puro

```python
from starlette.datastructures import MutableHeaders


class CarimboMiddleware:
    """Só olha e escreve um header: ASGI puro, send embrulhado."""

    def __init__(self, app, carimbo: str = CARIMBO) -> None:
        self.app = app
        self.carimbo = carimbo

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_carimbado(mensagem) -> None:
            if mensagem["type"] == "http.response.start":
                mensagem.setdefault("headers", [])
                MutableHeaders(scope=mensagem)["x-servido-por"] = self.carimbo
            await send(mensagem)

        await self.app(scope, receive, send_carimbado)
```

É o `send` embrulhado da lição 03, ponto. Você não recebe a resposta pronta em lugar nenhum: você troca o `send` por uma função sua e intercepta o `http.response.start`, que é a primeira mensagem a sair e a que carrega os headers.

O `MutableHeaders` (do `starlette.datastructures`, o mesmo que o `CORSMiddleware` usa) em vez de um `mensagem["headers"].append(...)` na unha: com `append`, se alguém de dentro já tiver escrito `x-servido-por`, você fica com o header duplicado em vez de substituído. Aqui ninguém escreve — mas o dia em que alguém escrever, ninguém vai lembrar deste detalhe.

### A ordem, que é a parte que ensina

```python
# add_middleware empilha de dentro para fora: o ÚLTIMO registrado é a camada de FORA.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=sorted(ORIGENS), allow_methods=["GET", "POST"])
app.add_middleware(CarimboMiddleware)
```

De fora para dentro: **carimbo → CORS → rate limiter → router.**

Cada camada está onde está por um motivo que um teste cobra:

- **O carimbo por fora de tudo**, porque ele tem que aparecer em respostas que as camadas de dentro produzem **sozinhas**. O preflight quem responde é o CORS; o `429` quem responde é o rate limiter. Nenhuma das duas chega ao router. Só quem está por fora das duas vê as duas saírem.
- **O CORS por fora do rate limiter**, pelos dois motivos da lição 05: o preflight não gasta ficha, e o `429` sai carimbado de CORS. Se não sair, o browser esconde o `429` e mostra "erro de CORS".
- **O rate limiter no centro**, porque a única coisa que ele precisa ver é tráfego de verdade — e porque é dele o direito de não deixar a request seguir.

Isso deixa **uma** ordem de pé. Eu testei as duas trocas mais tentadoras.

**Ordem errada 1 — o carimbo por dentro.** É a mais tentadora, porque parece que o carimbo é um detalhe de acabamento que fica perto do app:

```python
app.add_middleware(CarimboMiddleware)     # mais por dentro
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CORSMiddleware, ...)   # mais por fora
```

```
______________________ test_preflight_de_origem_permitida ______________________
E       KeyError: 'x-servido-por'
_________________ test_429_depois_de_cinco_com_cors_e_carimbo __________________
E       KeyError: 'x-servido-por'
2 failed, 3 passed
```

Dois testes, e eles falham exatamente nas duas respostas que nunca chegam ao centro. `test_origem_desconhecida_nao_ganha_header` continua verde — porque aquela request atravessa a cebola inteira, e o carimbo a alcança de qualquer jeito. **É o teste que continua passando que te diria "está tudo bem" se os outros dois não existissem.**

**Ordem errada 2 — o rate limiter por fora do CORS.** É o defeito do bloco 1, de novo:

```
_________________ test_429_depois_de_cinco_com_cors_e_carimbo __________________
E       KeyError: 'access-control-allow-origin'
1 failed, 4 passed
```

Um teste só. E repare que o preflight **continua verde** aqui, mesmo gastando ficha — cada teste do arquivo usa um IP diferente, então o balde daquele cliente estava cheio e uma ficha a menos não fez diferença. A ordem errada está lá e o teste do preflight não a vê. Foi preciso o `test_429` para pegá-la — e note que ele é o único dos cinco que cobra CORS **e** rate limit na mesma resposta. Cruzamento de duas camadas é onde os testes de uma camada só são cegos.

### "E se eu tivesse usado `BaseHTTPMiddleware` no carimbo?"

Passa. Eu rodei:

```python
class CarimboMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resposta = await call_next(request)
        resposta.headers["x-servido-por"] = CARIMBO
        return resposta
```

`5 passed`. Quatro linhas no lugar de uma classe de dezoito, e pela regra da lição 03 ele até se qualifica: escrever um header de saída é quase só olhar.

Escolhi ASGI puro mesmo assim, por dois motivos — e nenhum deles é "porque é melhor":

1. **Coerência com o app.** O FairFare decidiu, na lição 03, usar a forma pura nas duas camadas dele. Um app com dois estilos de middleware é um app onde a próxima pessoa tem que descobrir qual estilo usar, toda vez.
2. **O custo que a lição 03 descreveu.** Para te entregar `Request` e `Response`, o `BaseHTTPMiddleware` roda o app de dentro numa task separada e passa a resposta por um canal em memória. Isso custa por request, atravessa no caminho de respostas transmitidas aos poucos, e tem histórico de esquisitice com `contextvars` e background tasks. Para um header, é caro demais para o que entrega — e ele estaria na camada de **fora**, ou seja, no caminho de 100% do tráfego.

Se o seu carimbo tivesse ficado como `BaseHTTPMiddleware`, você não errou o exercício. Você tomou outra decisão, e agora sabe qual é o preço dela.

---

## O fio que costura os três blocos

Os três exercícios são a mesma pergunta feita de três jeitos: **quem está no caminho, e em que ordem?**

- No bloco 1, um defeito era aritmética dentro de uma camada e o outro era a ordem entre duas camadas — e os dois saíram na tela como `429`, um deles disfarçado de erro de CORS que não era de CORS.
- No bloco 2, o proxy é uma camada a mais no caminho, e cada header que ele toca é uma decisão sobre *quem tem a informação*: `Host` vem do cliente, `X-Forwarded-For` vem do proxy, `Retry-After` vem do upstream. Ninguém inventa o dado do outro.
- No bloco 3, a ordem virou a tarefa inteira — e a única forma de justificá-la foi apontar, para cada camada, qual teste cai se ela mudar de lugar.

E fica uma coisa dita em voz alta, porque ela é o capítulo inteiro em uma frase: **entre o cliente e o seu router existe uma pilha, e ela tem ordem.** O seu código pode estar perfeito e a resposta chegar errada no browser porque duas linhas de `add_middleware` estavam trocadas. Depurar isso exige saber que a pilha existe — e agora você sabe.
