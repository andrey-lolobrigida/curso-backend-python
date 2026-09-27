# Lição 01 — Abrindo a caixa do uvicorn

Você digita este comando desde o capítulo 1:

```bash
uv run uvicorn app.main:app --reload
```

E nunca perguntou o que é o `uvicorn`.

O capítulo 2 chegou perto. A lição 06 disse, quando descobrimos que um cliente async conversa sem reclamar com rotas `def`:

> **ASGI é a fronteira.** É o protocolo entre servidor e aplicação em Python — a mesma fronteira que o uvicorn atravessa em produção, e o capítulo 3 vai abrir essa caixa por completo. […]

E o README do capítulo fechou com a dívida escrita em voz alta: *"quem é esse `uvicorn` que a gente digita desde o capítulo 1 e nunca abriu?"*

Chegou a hora. E a resposta é menor do que você imagina: **o uvicorn não faz ideia do que é o FastAPI.** Ele conhece uma função com três argumentos.

## Duas funções sem framework

Antes de abrir o FairFare, vamos escrever a coisa mais simples que o uvicorn aceita rodar. Sem FastAPI, sem Starlette, sem `import` nenhum.

`chapters/03-entre-o-cliente-e-o-router/bancada/asgi_cru.py`:

```python
async def acompanhar_lifespan(receive, send) -> None:
    """O servidor avisa quando nasce e quando morre. A gente só responde 'ok'."""
    while True:
        mensagem = await receive()
        if mensagem["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif mensagem["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


async def app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        await acompanhar_lifespan(receive, send)
        return

    # A partir daqui, scope["type"] == "http": uma request chegou.
    # (ip, porta) de quem conectou — guarde essa linha; a lição 08 volta nela
    cliente = scope["client"]
    corpo = f"{scope['method']} {scope['path']} — você é {cliente}\n".encode()

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send({"type": "http.response.body", "body": corpo})
```

Repare no que **não** tem aí: nenhuma dependência. Nenhum decorator. Nenhum `@app.get`. É um arquivo Python com duas funções.

Suba com o **mesmo** comando de sempre:

```bash
uv run uvicorn asgi_cru:app --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

E bata nele — pelo `curl` ou abrindo `http://localhost:8000/qualquer/coisa` no browser:

```
$ curl -s localhost:8000/qualquer/coisa
GET /qualquer/coisa — você é ('127.0.0.1', 35444)
```

O uvicorn subiu, atendeu e respondeu texto. Ele não reclamou de não ter framework porque **framework nunca foi requisito**. O requisito é a assinatura: uma corrotina que recebe três argumentos.

Isso é ASGI. E o nome importa menos que a ideia: **ASGI é uma especificação de interface, não uma biblioteca.** Não existe `pip install asgi`. É um documento que diz "servidor, chame o app assim; app, responda assim" — e qualquer servidor e qualquer framework que sigam o documento se encaixam. É por isso que o mesmo `uvicorn` roda FastAPI, Starlette, Django assíncrono, Litestar e as nossas duas funções: nenhum deles conhece os outros; todos conhecem o contrato.

## Os três argumentos, um por vez

A analogia: o servidor é a recepção do prédio. Alguém chega, a recepção anota numa ficha quem é, de onde veio e o que quer, e te entrega a ficha. Se a pessoa trouxe uma encomenda pesada, a recepção não sobe com ela — te dá um jeito de pedir a encomenda aos poucos. E quando você tem uma resposta, você não desce: você manda a resposta pela recepção, em partes.

Ficha, jeito de pedir, jeito de mandar. `scope`, `receive`, `send`.

### `scope` — a ficha

Um dicionário comum, montado pelo servidor **antes** de qualquer corpo chegar. É tudo que o servidor já sabe sobre a request só de ter lido o começo dela: o método, o caminho, os headers, quem conectou, se é `http` ou `https`.

Não é objeto. Não tem método. É `dict`, e você lê com colchetes: `scope["method"]`, `scope["path"]`.

Duas chaves merecem atenção agora:

- **`headers`** é uma lista de pares de **bytes**, não um dicionário de strings: `[(b"host", b"localhost:8000"), ...]`. Bytes porque é literalmente o que veio pelo fio, sem ninguém ter decidido ainda qual encoding usar. Lista de pares porque HTTP permite o mesmo header repetido.
- **`client`** é a tupla `(ip, porta)` de quem abriu a conexão TCP. Guarde essa linha do `asgi_cru.py`. Quando um proxy reverso entrar na frente do seu app, esse `client` vai passar a responder outra pergunta — quem **conectou**, não quem **pediu** — e a lição 08 é inteira sobre isso.

### `receive` — o jeito de pedir

Uma corrotina. Você dá `await receive()` e recebe uma mensagem — um dicionário. Para uma request HTTP com corpo (um `POST`, um `PUT`), as mensagens vêm `{"type": "http.request", "body": b"...", "more_body": True}` até acabar.

Por que em pedaços, e não tudo de uma vez? Porque o corpo pode ser um upload de 2 GB, e ninguém quer 2 GB de RAM antes da primeira linha do seu código rodar. O `asgi_cru.py` nunca chama `receive` para requests HTTP: ele responde sem ler o corpo, o que é permitido.

### `send` — o jeito de mandar

Também uma corrotina, e a resposta sai em **duas ou mais** mensagens:

1. `{"type": "http.response.start", "status": 200, "headers": [...]}` — a linha de status e os headers.
2. `{"type": "http.response.body", "body": b"..."}` — os bytes. Pode repetir, com `more_body`, para transmitir um arquivo grande aos poucos.

Depois do `response.start`, os headers já foram pelo fio. Não dá para mudar de ideia sobre o status code. Essa ordem não é burocracia do protocolo: é a ordem em que o HTTP realmente sai na conexão, e você vai reencontrá-la na lição 02.

## `lifespan`: nascer e morrer

Repare que o `scope["type"]` do nosso app pode não ser `"http"`. O uvicorn usa a mesmíssima função para uma segunda conversa, e ela acontece antes de qualquer request: o **lifespan**.

Assim que sobe, o servidor chama o app com `scope["type"] == "lifespan"` e manda `lifespan.startup`. O app faz o que precisa fazer para nascer e responde `lifespan.startup.complete`. Só então o uvicorn começa a aceitar conexões. Na hora de morrer, `lifespan.shutdown` e a resposta simétrica.

É o handshake que você já viu mil vezes no terminal sem saber que era isso:

```
INFO:     Started server process [9730]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

`Waiting for application startup` é o uvicorn esperando o `startup.complete` que a nossa `acompanhar_lifespan` manda. Já `Application shutdown complete`, no `Ctrl+C`, é a outra ponta.

Não acredite em mim, quebre. Troque aquele primeiro `await send(...)` por um `pass` e suba de novo:

```
INFO:     Started server process [9823]
INFO:     Waiting for application startup.
```

E acabou. Fica ali, parado, para sempre — a porta 8000 nem chega a ser aberta. O uvicorn não vai atender ninguém enquanto o app não disser que nasceu.

E para que serve, num app de verdade? Para tudo que precisa existir **uma vez por processo**, não uma vez por request: abrir um pool de conexões com o banco, carregar um modelo pesado na memória, iniciar um cliente HTTP compartilhado. É o gancho onde o pool da lição 09 do capítulo 2 nasceria — o FairFare ainda não usa lifespan porque o pool do SQLAlchemy é preguiçoso, cria conexão na primeira que precisar. Quando isso deixar de bastar — um pool que precise nascer antes da primeira request, um cliente HTTP que precise morrer com o processo —, o lugar é aqui. Nenhum capítulo tem data marcada para isso; o gancho fica registrado.

## O FastAPI é isso

Agora a virada. Aquele `app` que você importa há dois capítulos:

```bash
$ uv run python -c "from app.main import app; from starlette.applications import Starlette; print(callable(app), isinstance(app, Starlette))"
True True
```

`callable(app)` é `True`. E o objeto `FastAPI` é um `Starlette` — é lá que mora o `__call__` com os três argumentos. Chamar `app(scope, receive, send)` funciona exatamente como chamar as nossas duas funções. **Para o uvicorn, o FairFare inteiro — routers, dependências, Pydantic, SQLAlchemy — é uma corrotina de três argumentos.** Todo o resto acontece depois que ele já entregou a ficha e foi embora.

Dá para ver a ficha chegando. `bancada/espiao.py` embrulha o FairFare de verdade num middleware de sete linhas que imprime o `scope` antes de repassar:

```python
from app.main import app as fairfare

CHAVES = ("type", "http_version", "method", "scheme", "path", "query_string", "client", "server")


async def app(scope, receive, send) -> None:
    if scope["type"] == "http":
        print({chave: scope[chave] for chave in CHAVES})
        print("headers:", [(nome.decode(), valor.decode()) for nome, valor in scope["headers"]])
    await fairfare(scope, receive, send)
```

Isso é um middleware ASGI, e é o middleware mais honesto que existe: uma função com a assinatura do app, que chama o app de verdade no fim. Nada de `@app.middleware`, nada de classe base. Só a assinatura.

Suba numa aba:

```bash
uv run python -m uvicorn espiao:app --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

Em outra, uma request qualquer ao FairFare:

```bash
curl -s 'localhost:8000/users?limite=3' -H 'accept: application/json'
```

E o terminal do servidor mostra:

```
{'type': 'http', 'http_version': '1.1', 'method': 'GET', 'scheme': 'http', 'path': '/users', 'query_string': b'limite=3', 'client': ('127.0.0.1', 45376), 'server': ('127.0.0.1', 8000)}
headers: [('host', 'localhost:8000'), ('user-agent', 'curl/8.5.0'), ('accept', 'application/json')]
INFO:     127.0.0.1:45376 - "GET /users?limite=3 HTTP/1.1" 200 OK
```

Leia esse dicionário devagar, porque ele é o capítulo inteiro em uma linha.

`path` é `'/users'` — só o caminho, sem a query. A query vive separada em `query_string`, e vive como **bytes crus**: `b'limite=3'`. Ninguém parseou. Ninguém validou. O `limite=3` inclusive não existe na rota `GET /users` do FairFare, e ele veio assim mesmo, intacto. O servidor não tem opinião sobre a sua API — quem descarta um parâmetro desconhecido é o FastAPI, mais tarde. `client` é a máquina que conectou; `server`, o par `(host, porta)` onde o uvicorn está escutando. E `scheme` é `'http'`, o que vai ficar interessante quando a lição 10 colocar TLS na frente.

### Sobre aquele `python -m`

Duas frases, porque isso morde. O `--app-dir` do uvicorn tem um padrão: o diretório atual. Passar outra pasta **substitui** esse padrão — a raiz do projeto não é tirada do `sys.path`, ela simplesmente deixa de entrar. E o espião importa `app.main`. Rodar como `python -m uvicorn` resolve porque o próprio Python já pôs a raiz no path antes de o uvicorn abrir a boca, então as duas pastas convivem; sem o `-m`, o import falha:

```
File ".../bancada/espiao.py", line 8, in <module>
    from app.main import app as fairfare
ModuleNotFoundError: No module named 'app'
```

## O que o uvicorn fez antes de te chamar

Volte àquele dicionário e faça a pergunta certa: de onde ele veio? Ninguém manda um `dict` pela internet. O que chega pelo fio são bytes.

Entre o cliente digitar o endereço e a sua função ser chamada, o uvicorn fez pelo menos isto:

1. **Escutou uma porta** e aceitou uma conexão **TCP** — um canal de bytes entre duas máquinas.
2. **Leu os bytes** que chegaram, sem saber ainda quantos são nem onde a request termina.
3. **Entendeu HTTP/1.1** naqueles bytes: a linha de request, os headers, onde acaba o cabeçalho e começa o corpo.
4. **Montou o `scope`** com o que entendeu e chamou a sua corrotina.

Estou nomeando, não explicando. Cada um desses passos tem uma decisão de projeto atrás, e é o assunto da lição 02 — inclusive a pergunta que sobrou: o uvicorn escreveu esse parser de HTTP à mão?

O que fica desta lição é a fronteira. De um lado, bytes, sockets e protocolo. Do outro, um dicionário e duas corrotinas. O FastAPI mora do lado direito, e sempre morou.

## O que você deve conseguir fazer agora

- Escrever, do zero e sem framework, um app ASGI que responde texto para qualquer caminho.
- Dizer o que são `scope`, `receive` e `send`, e por que a resposta sai em pelo menos duas mensagens.
- Apontar, no `scope` de uma request real, o método, o path, a query crua e quem é o cliente.
- Explicar o que é o `lifespan` e por que `Waiting for application startup` aparece no seu terminal.
- Responder em uma frase o que o FastAPI é para o uvicorn: uma corrotina de três argumentos, como qualquer outra.
- Listar os quatro passos que o servidor deu antes de chamar a sua função.
