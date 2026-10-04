# Lição 06 — O proxy reverso

Esta lição põe uma peça nova na frente do app: o proxy reverso. Ele não existe para resolver CORS — isso é um efeito colateral simpático, e fica para a lição 07. Ele existe por outros motivos, e é melhor conhecer os motivos antes do código.

## Por que pôr alguma coisa na frente do app

Até agora o mapa é curto: o cliente fala com o uvicorn, o uvicorn fala com o FairFare. Uma máquina, uma porta, um processo. Funciona, e é ótimo para aprender.

Agora quatro perguntas que esse arranjo não responde bem.

**1. Onde mora o TLS?** Todo tráfego de verdade é `https`. Isso significa certificado, chave privada, renovação, e um handshake criptográfico antes de cada conexão. Se cada app cuidar do próprio, você tem N lugares para renovar certificado e N chances de esquecer. (A lição 09 mostra o handshake acontecendo.)

**2. E se houver mais de um app?** Uma máquina tem uma porta 443. Você tem o FairFare, um painel de admin, talvez um serviço de relatórios. Todos querem ser `https://…:443`. Alguém precisa olhar o caminho ou o domínio e decidir para quem vai.

**3. Quem serve os arquivos estáticos?** Um `.js` de 200 KB não precisa de sessão de banco, nem de validação Pydantic, nem de event loop. Fazer o Python entregar bytes de disco é gastar o recurso caro no trabalho barato.

**4. O app deveria estar exposto na internet?** Um processo Python, escrito por você, com a sua lógica de negócio dentro, aceitando conexões TCP de qualquer lugar do mundo. Dá para fazer melhor: o app escuta só em `127.0.0.1`, e quem conversa com o mundo é um programa cuja única função é conversar com o mundo.

As quatro respostas são a mesma peça: **um proxy reverso**.

A analogia é a recepção de um prédio. Ninguém entra e sai batendo na porta de cada escritório. Você fala com a recepção, diz para quem veio, e a recepção resolve: sobe, avisa, entrega. Os escritórios lá em cima nem sabem que a rua existe.

Agora a afirmação técnica, que é mais estranha do que a analogia deixa parecer: **um proxy reverso é um servidor HTTP que, ao receber uma request, faz ele mesmo outra request para um segundo servidor, e devolve a resposta ao cliente**. Ele é servidor de um lado e cliente do outro. As duas coisas ao mesmo tempo, na mesma função.

O "reverso" é só para distinguir do outro tipo. Um proxy comum ("forward proxy") fica do lado do **cliente** — a empresa põe um para filtrar o que os funcionários acessam. Um proxy reverso fica do lado do **servidor**, e o cliente nem sabe que ele existe: para o browser, ele *é* o site.

## Cinquenta linhas

A melhor forma de acreditar na frase "servidor de um lado, cliente do outro" é escrever uma. São cinquenta linhas de código, e você já conhece as duas metades: um app ASGI (lição 01) e o `httpx2.AsyncClient` do `carga.py` (lição 02).

`chapters/03-entre-o-cliente-e-o-router/bancada/proxy.py`:

```python
"""Bancada: um proxy reverso em cinquenta linhas.

Escuta na 8080. O que chega em /api/... vai para o FairFare (8000), sem o prefixo.
Todo o resto é a página em pagina/, servida como arquivo estático.

Imprime cada request que atravessa — inclusive o corpo. Isso é DE PROPÓSITO:
quem está no meio lê tudo, e a lição 09 é sobre isso.

Sobe com:
  uv run uvicorn proxy:app --port 8080 --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
"""

from pathlib import Path

import httpx2
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

UPSTREAM = "http://127.0.0.1:8000"
PAGINA = Path(__file__).with_name("pagina")

# Headers que pertencem a UMA conexão, não à mensagem. Não atravessam proxies.
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade"}

upstream = httpx2.AsyncClient(base_url=UPSTREAM, timeout=30)


def headers_para_o_upstream(request: Request) -> dict[str, str]:
    # "host" sai: o httpx põe o do upstream. O resto passa como veio.
    return {
        nome: valor
        for nome, valor in request.headers.items()
        if nome.lower() not in HOP_BY_HOP and nome.lower() != "host"
    }


async def repassar(request: Request) -> Response:
    caminho = "/" + request.path_params["caminho"]
    corpo = await request.body()
    print(f"→ {request.method} {caminho}  corpo={corpo!r}")

    resposta = await upstream.request(
        request.method,
        caminho,
        params=request.url.query,
        headers=headers_para_o_upstream(request),
        content=corpo,
    )
    print(f"← {resposta.status_code}")

    # content-length e content-encoding saem: o httpx já descomprimiu, e o Starlette recalcula.
    headers_de_volta = {
        nome: valor
        for nome, valor in resposta.headers.items()
        if nome.lower() not in HOP_BY_HOP | {"content-length", "content-encoding"}
    }
    return Response(resposta.content, status_code=resposta.status_code, headers=headers_de_volta)


app = Starlette(
    routes=[
        Route(
            "/api/{caminho:path}",
            repassar,
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        ),
        Mount("/", StaticFiles(directory=PAGINA, html=True)),
    ]
)
```

*(Versão do commit desta lição. A lição 08 muda duas linhas aqui — `git show v-cap03-licao06:chapters/03-entre-o-cliente-e-o-router/bancada/proxy.py` mostra exatamente esta. O README do capítulo explica a convenção.)*

Três coisas para reparar.

**O `repassar` é a definição inteira.** Ele recebe uma `Request` (é servidor), monta uma request nova para `127.0.0.1:8000` — o **upstream**, que é como proxies chamam o servidor de trás: rio acima, para onde a request sobe — (é cliente), e devolve uma `Response` com o corpo e o status que voltaram. O resto do arquivo é higiene de headers.

**O prefixo some no caminho.** O `{caminho:path}` captura tudo depois de `/api/`, e a request para o upstream é montada com `"/" + caminho`. Quem chega em `/api/users` vira `/users` lá dentro. O FairFare não sabe que existe um `/api`.

**Os headers hop-by-hop.** Alguns headers do HTTP descrevem a **mensagem** (`content-type`, `authorization`) e outros descrevem a **conexão** em que ela viajou (`connection`, `keep-alive`, `transfer-encoding`). Um proxy termina uma conexão e abre outra — então os da segunda categoria não têm sentido do outro lado, e repassá-los produz desde bobagem até resposta corrompida. Por isso o `HOP_BY_HOP` sai nas duas direções.

O `Mount("/", StaticFiles(...))` é a resposta à pergunta 3 lá de cima, em uma linha: qualquer caminho que não comece com `/api/` é procurado em `pagina/`. O `html=True` faz `/` virar `index.html`.

### Rodando

Duas abas. O FairFare, como sempre:

```bash
uv run uvicorn app.main:app --port 8000
```

E o proxy:

```bash
uv run uvicorn proxy:app --port 8080 --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

*(A lição 08 acrescenta `--no-proxy-headers` a este comando e explica por quê. Aqui ainda não, de propósito.)*

Agora bata **só** na 8080:

```console
$ curl -si localhost:8080/api/users | head -8
HTTP/1.1 200 OK
date: Mon, 07 Sep 2026 15:36:22 GMT
server: uvicorn
date: Mon, 07 Sep 2026 15:36:23 GMT
server: uvicorn
content-type: application/json
content-length: 147

$ curl -s localhost:8080/ | head -3
<!doctype html>
<html lang="pt-br">
<head>
```

Uma porta, duas coisas diferentes: JSON do FairFare e HTML do disco.

E o `date`/`server` duplicado? É o seu proxy sendo de brinquedo, na cara dura. O `headers_de_volta` repassa o `date` e o `server` que vieram do uvicorn de baixo, e o uvicorn de cima acrescenta os dele. Um proxy de verdade normaliza isso. O nosso não — e é melhor você ver a falha aqui do que descobri-la depois.

Faça mais três, todas pela 8080: um `POST` criando a Bia, um `GET` com query string e um `GET` num id que não existe.

```bash
curl -s -X POST localhost:8080/api/users -H 'content-type: application/json' -d '{"nome":"Bia","email":"bia2@exemplo.com"}'
curl -s 'localhost:8080/api/users?limit=1'
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/api/users/999999
```

Agora olhe o terminal do **FairFare**:

```
INFO:     127.0.0.1:46532 - "GET /users HTTP/1.1" 200 OK
INFO:     127.0.0.1:46532 - "POST /users HTTP/1.1" 201 Created
INFO:     127.0.0.1:46532 - "GET /users?limit=1 HTTP/1.1" 200 OK
INFO:     127.0.0.1:46532 - "GET /users/999999 HTTP/1.1" 404 Not Found
```

Quatro requests, e três detalhes de uma vez. Os caminhos chegam **sem** o `/api`. A query string atravessou (`?limit=1` — o FairFare não tem esse parâmetro e o ignora; o ponto é só que ela chegou). E a porta de origem é a **mesma nas quatro**: `46532`. É o keep-alive da lição 02 do outro lado da mesa — o `AsyncClient` do proxy mantém uma conexão aberta com o upstream e reaproveita.

Repare também no endereço: `127.0.0.1`. **Todas** as requests chegam ao FairFare vindas do proxy, então é sempre esse. O rate limiter da lição 05 usa `scope["client"]` como chave do balde. Guarde o incômodo; a lição 08 é sobre exatamente isso.

## O que este proxy ainda não faz

Ele é um instrumento de bancada, não um produto. As limitações são estas, todas conhecidas:

- **Não manda `X-Forwarded-*`.** O FairFare não tem como saber quem é o cliente de verdade nem se a conexão original era `https`. É a lição 08.
- **`HOP_BY_HOP` é uma lista fixa, não a definição real.** O RFC 7230 diz que hop-by-hop é o que o header `Connection:` de cada request citar — um proxy correto lê esse valor e amplia a lista pedido a pedido. O nosso conjunto é fechado: um header citado dentro de `Connection:` mas ausente do `HOP_BY_HOP` atravessa sem querer, e faltam `proxy-authenticate`/`proxy-authorization`.
- **Headers repetidos da resposta viram um só, com vírgula.** O `resposta.headers.items()` do httpx já entrega os repetidos fundidos com `, ` (é o `multi_items()` que os separa), e o proxy repassa assim. Inofensivo hoje, porque o FairFare não manda `set-cookie` — errado assim que o capítulo 6 trouxer login por cookie e este arquivo for reaproveitado.
- **Não faz TLS.** Escuta em `http`. A lição 10 sobe o mesmo arquivo com certificado, na 8443.
- **Duplica `date` e `server`** na resposta, como você viu acima.
- **Segura o corpo inteiro na memória** (`await request.body()` e `resposta.content`) em vez de repassar em streaming. Para um upload grande isso é ruim; para a bancada é o que torna o código legível.
- **Cria o `AsyncClient` no import e nunca o fecha.** Num app de produção isso vai para o `lifespan`.
- **Imprime o corpo de toda request no terminal.** Esse não é um descuido — é o ponto da lição 09.

## Uma última olhada no terminal do proxy

Antes de fechar, role o terminal onde o `proxy.py` está rodando:

```
→ GET /users  corpo=b''
← 200
→ POST /users  corpo=b'{"nome":"Bia","email":"bia2@exemplo.com"}'
← 201
```

Olhe bem a terceira linha. O nome e o e-mail que você mandou pelo `curl` estão ali, em texto puro, no terminal de um programa que não é o cliente nem é o servidor.

Ele não invadiu nada. Ele está no caminho — e quem está no caminho lê tudo. Foi assim o capítulo inteiro, aliás: o `espiao.py` da lição 01 leu o `scope`, o middleware da lição 03 leu a resposta, e agora o proxy lê o corpo.

Fica a pergunta para a lição 09: se qualquer coisa no meio do caminho lê tudo, como é que alguém manda uma senha pela internet?

## O que você deve conseguir fazer agora

- Explicar em uma frase o que um proxy reverso é: um servidor HTTP que faz requests a outro servidor em nome do cliente — servidor de um lado, cliente do outro.
- Dar dois motivos para pôr um na frente do app que não tenham nada a ver com CORS.
- Dizer o que são headers hop-by-hop e por que um proxy não os repassa.
- Listar três coisas que este proxy de bancada ainda não faz, e dizer qual delas é o gancho da lição 09.
