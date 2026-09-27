# Lição 08 — Atrás do proxy, em quem confiar

A lição 07 terminou com um incômodo guardado. Todas as requests chegavam ao FairFare vindas de `127.0.0.1`, porque quem conectava era o proxy. E o rate limiter da lição 05 usa exatamente esse valor como chave do balde.

Esta lição é sobre uma pergunta só: **atrás de um proxy, quem é o cliente?**

A resposta curta é que o app não sabe. Alguém precisa contar para ele. E aí a pergunta vira outra, pior: **em quem ele acredita?**

## O espelho

Para responder isso a gente precisa de um instrumento que só faça uma coisa: dizer o que o servidor achou. `chapters/03-entre-o-cliente-e-o-router/bancada/eco.py`:

```python
"""Bancada: o espelho. Devolve quem o servidor ACHA que é o cliente e por qual esquema chegou.

Sobe com (no lugar do FairFare, na 8000, para ficar atrás do proxy):
  uv run uvicorn eco:app --port 8000 --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
"""

import json

from asgi_cru import acompanhar_lifespan


async def app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        await acompanhar_lifespan(receive, send)
        return

    # Duas ressalvas de espelho: headers do HTTP são latin-1, e este dict guarda a ÚLTIMA
    # ocorrência de um header repetido — o uvicorn junta todos os x-forwarded-for com ", ".
    headers = {nome.decode("latin-1"): valor.decode("latin-1") for nome, valor in scope["headers"]}
    espelho = {
        "cliente": scope["client"],
        "esquema": scope["scheme"],
        "path": scope["path"],
        "x-forwarded-for": headers.get("x-forwarded-for"),
        "x-forwarded-proto": headers.get("x-forwarded-proto"),
    }
    corpo = json.dumps(espelho, indent=2, ensure_ascii=False).encode()

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": corpo})
```

*(Versão do commit desta lição. A lição 11 acrescenta um `/lento` aqui, que dorme cinco segundos de propósito.)*

É o `asgi_cru.py` da lição 01 com um JSON no lugar do texto. Ele reaproveita até o `acompanhar_lifespan` de lá. Duas abas: o espelho na 8000, no lugar do FairFare, e o proxy da lição 06 na 8080.

```bash
uv run uvicorn eco:app --port 8000 --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
uv run uvicorn proxy:app --port 8080 --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

**Antes do primeiro `curl`, abra o `proxy.py` e comente as duas linhas que começam com `headers["x-forwarded-`** — são as duas logo antes do `return` do `headers_para_o_upstream`. Suba o proxy exatamente com o comando acima, sem flag nenhuma. Vamos descomentar as duas daqui a pouco, e você vai ver por quê. (É o `proxy.py` como ele era no fim da lição 06.)

```console
$ curl -s localhost:8080/api/
{
  "cliente": [
    "127.0.0.1",
    35596
  ],
  "esquema": "http",
  "path": "/",
  "x-forwarded-for": null,
  "x-forwarded-proto": null
}
```

`cliente` é o proxy. `esquema` é `http`, e seria `http` mesmo que o cliente lá fora tivesse falado `https` com o proxy — porque a conexão que o espelho enxerga é a segunda, a que o proxy abriu. Aquela linha `cliente = scope["client"]` da lição 01 nunca mentiu: ela sempre disse "quem abriu esta conexão TCP". Só que quem abre a conexão deixou de ser o cliente.

**Uma ressalva de bancada, antes que ela te engane.** Numa máquina só, o proxy *e* você são `127.0.0.1`. Esse primeiro output não prova nada sozinho — ele seria igual sem proxy nenhum. A diferença começa a aparecer no próximo passo.

## Os headers que resolvem isso

A convenção é velha e é simples: **o proxy conta ao app o que viu**, em dois headers.

- `X-Forwarded-For: <ip do cliente>` — quem conectou comigo.
- `X-Forwarded-Proto: https` — por qual esquema ele falou comigo.

(O `X-` é herança de quando headers não-padronizados levavam esse prefixo. Existe um substituto padronizado, o header `Forwarded` do RFC 7239, com sintaxe mais rica. Na prática o mundo continua usando os `X-Forwarded-*`, e é o que o uvicorn lê.)

O detalhe que pega quase todo mundo de surpresa: **o uvicorn já lê esses dois headers, sem você pedir**. A opção `--proxy-headers` vem ligada por padrão, e o que ela liga é um middleware ASGI do próprio uvicorn (`ProxyHeadersMiddleware`) — exatamente o "mexer no `scope` antes do app de dentro ver" da lição 03. Quando ele aceita o header, ele **troca** o `scope["client"]` e o `scope["scheme"]` antes do seu app ver qualquer coisa. Ou seja: o valor que o seu rate limiter usa como chave pode ter vindo de um header.

Ele não aceita de qualquer um. Quem decide é a opção `--forwarded-allow-ips` (ou a variável de ambiente `FORWARDED_ALLOW_IPS`). O padrão é **`127.0.0.1`**: só se a conexão TCP vier desse endereço é que os headers são levados a sério. Guarde esse padrão. Ele é o motivo de tudo que vem a seguir.

E quando aceita, a regra de qual endereço extrair da lista tem um nome: **o primeiro host não confiável, lendo da direita para a esquerda**. A ideia é que cada proxy da cadeia *acrescenta* o endereço de quem falou com ele no fim da lista — então o fim da lista é a parte que você mesmo escreveu, e o começo é a parte que veio de fora. Andando de trás para frente, o primeiro endereço que não está na sua lista de confiáveis é o cliente real; tudo à direita dele é infraestrutura sua.

Medido no espelho, batendo **direto** na 8000 (uvicorn com os padrões, portanto confiando em `127.0.0.1`):

| `X-Forwarded-For` enviado | `scope["client"]` que o app viu |
|---|---|
| `10.0.0.7` | `['10.0.0.7', 0]` |
| `10.0.0.7, 127.0.0.1` | `['10.0.0.7', 0]` |
| `8.8.8.8, 10.0.0.7, 127.0.0.1` | `['10.0.0.7', 0]` |
| `127.0.0.1, 127.0.0.1` | `['127.0.0.1', 0]` |

A terceira linha é a regra funcionando: `127.0.0.1` é confiável, `10.0.0.7` não é, e a busca para ali — o `8.8.8.8` à esquerda é ignorado **justamente porque qualquer um pode tê-lo escrito**. Quem chegou até a sua cadeia foi `10.0.0.7`, e tudo à esquerda dele é texto que `10.0.0.7` mandou junto. Palavra de estranho, mais uma vez.

A quarta linha é o caso degenerado: quando a lista inteira é confiável, ele devolve o primeiro.

E aquele `0` no lugar da porta é literal: o header quase sempre carrega só o endereço, e para um endereço sem porta o uvicorn põe zero. (Ele *sabe* ler `host:porta` e `[ipv6]:porta`; nenhum valor da tabela tem porta, então o zero é o que sobra.)

O `X-Forwarded-Proto` é mais direto. Um `curl -H 'X-Forwarded-Proto: https' localhost:8000/` no espelho devolve `"esquema": "https"`, tendo o espelho recebido uma conexão em texto puro. O que mudou foi o `scope["scheme"]` — e é dele que sai o esquema de qualquer URL que o app monte a partir da request. É assim que uma aplicação atrás de um proxy com TLS descobre que o mundo lá fora é `https`. A lição 10 volta nisso com o certificado na mão.

Agora repita o `curl` de antes pelo proxy da lição 06, inventando um header:

```console
$ curl -s -H 'X-Forwarded-For: 8.8.8.8' localhost:8080/api/
{
  "cliente": [
    "8.8.8.8",
    0
  ],
  "esquema": "http",
  "path": "/",
  "x-forwarded-for": "8.8.8.8",
  "x-forwarded-proto": null
}
```

Eu digitei `8.8.8.8` no terminal e o app acreditou. O proxy da lição 06 não escreve `X-Forwarded-For` nenhum — ele só **repassa os headers que chegaram**, e esse veio de mim. Do outro lado, o uvicorn viu uma conexão vinda de `127.0.0.1`, que é confiável por padrão, leu o header e trocou o `scope["client"]`.

## A frase da lição 05, desmentida com número

No fim da lição 05 ficou uma frase para guardar:

> o rate limit protege o app de um cliente abusado.

Vamos medir. Mate o espelho e suba o FairFare de verdade na 8000, com os padrões de sempre, e pegue o `carga.py`:

```console
$ C=chapters/03-entre-o-cliente-e-o-router/bancada/carga.py
$ uv run python $C http://localhost:8000/users 100
100 requests em 0.12s  status → 200: 20  429: 80  (Retry-After: 1s)
```

Vinte passam, oitenta levam `429`. É o balde da lição 05 funcionando exatamente como projetado. Agora a mesma carga, com um header a mais — o `{i}` do `carga.py` vira o número da request, então cada uma alega um IP diferente:

```console
$ uv run python $C http://localhost:8000/users 100 --header 'X-Forwarded-For: 10.0.0.{i}'
100 requests em 0.17s  status → 200: 100
```

**Cem de cem.** Um header de texto, escrito à mão, derrubou a proteção inteira. Cada request "veio" de um endereço diferente, cada uma abriu um balde novo e cheio, e nenhuma esbarrou em nada.

Por quê: nesta máquina eu sou `127.0.0.1`, `127.0.0.1` é confiável por padrão, e o uvicorn portanto acredita em qualquer `X-Forwarded-For` que eu mandar. Não há proxy nenhum nessa cadeia. Só eu, mentindo, e um servidor configurado para acreditar em proxies que não existem.

A frase da lição 05 estava incompleta. A versão correta é:

> o rate limit protege o app de um cliente abusado — se a chave do balde vier de uma fonte confiável.

## A fronteira de confiança tem duas camadas

Consertar isso não é uma linha. São duas, em lugares diferentes, e as duas precisam existir.

### Camada 1 — o proxy sobrescreve o que veio de fora

Com as duas linhas comentadas, o `headers_para_o_upstream` é isto:

```python
def headers_para_o_upstream(request: Request) -> dict[str, str]:
    # "host" sai: o httpx põe o do upstream. O resto passa como veio...
    headers = {
        nome: valor
        for nome, valor in request.headers.items()
        if nome.lower() not in HOP_BY_HOP and nome.lower() != "host"
    }
    # ...menos estes dois, que o proxy SOBRESCREVE. Quem está na frente é quem sabe
    # quem conectou e por qual esquema; o que veio de fora nesses headers é palavra de estranho.
    # headers["x-forwarded-for"] = request.client.host
    # headers["x-forwarded-proto"] = request.url.scheme
    return headers
```

Descomente as duas linhas e suba o proxy de novo. A função inteira fica assim, e é o que está no repositório:

```python
def headers_para_o_upstream(request: Request) -> dict[str, str]:
    # "host" sai: o httpx põe o do upstream. O resto passa como veio...
    headers = {
        nome: valor
        for nome, valor in request.headers.items()
        if nome.lower() not in HOP_BY_HOP and nome.lower() != "host"
    }
    # ...menos estes dois, que o proxy SOBRESCREVE. Quem está na frente é quem sabe
    # quem conectou e por qual esquema; o que veio de fora nesses headers é palavra de estranho.
    headers["x-forwarded-for"] = request.client.host
    headers["x-forwarded-proto"] = request.url.scheme
    return headers
```

Duas atribuições. E repare no verbo: **sobrescreve**. Existe uma versão tentadora, que parece mais educada e que é um buraco:

```python
# NÃO é isto que está commitado. É o buraco.
headers.setdefault("x-forwarded-for", request.client.host)
```

"Se já veio um, respeita." Respeitar o quê? Quem mandou aquele valor foi o cliente — a pessoa de quem você está tentando se defender. Um proxy de borda é a **primeira** coisa que a request encontra: por definição, não existe proxy anterior legítimo para ter escrito aquele header. O que estiver ali é palavra de estranho, e a única coisa certa a fazer com palavra de estranho nesse campo é jogar fora.

Em `nginx.conf` a mesma escolha aparece como duas variáveis:

```nginx
proxy_set_header X-Forwarded-For $remote_addr;                # sobrescreve
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;  # acrescenta
```

`$remote_addr` é o endereço de quem abriu a conexão TCP, e nada mais — usar só ele **descarta** o que veio de fora. `$proxy_add_x_forwarded_for` é o valor recebido, mais uma vírgula, mais o `$remote_addr`: ele **acrescenta**, preservando a cadeia. A regra é: **na borda, `$remote_addr`; num proxy interno que já está atrás de uma borda confiável, `$proxy_add_x_forwarded_for`**, porque aí a cadeia que chegou foi escrita por infraestrutura sua e vale a pena manter. *(Este arquivo continua sendo lido, nunca executado, como a lição 07 avisou — esta é a documentação do nginx, não uma medição minha.)*

### Camada 2 — o servidor de baixo só ouve o proxy

Sobrescrever no proxy não basta, e a razão é a carga lá de cima: **o atacante não precisa passar pelo proxy**. Se o uvicorn do FairFare estiver alcançável direto, ele continua aceitando `X-Forwarded-For` de qualquer um que esteja num endereço confiável.

A configuração correta tem duas metades que só funcionam juntas:

1. o app escuta **só** onde o proxy alcança (é o `--host 127.0.0.1`, que é o padrão do uvicorn, ou uma rede interna);
2. o app confia **só** no endereço do proxy: `--forwarded-allow-ips <ip-do-proxy>`.

Dá para ver a flag funcionando por exclusão. Suba o FairFare declarando confiança num endereço que não é o seu e repita o mesmo header inventado (*spoof*, no jargão):

```console
$ uv run uvicorn app.main:app --port 8000 --forwarded-allow-ips 10.20.30.40
$ uv run python $C http://localhost:8000/users 100 --header 'X-Forwarded-For: 10.0.0.{i}'
100 requests em 0.11s  status → 200: 20  429: 80  (Retry-After: 1s)
```

O `429` voltou. `127.0.0.1` deixou de ser confiável, o uvicorn ignorou o header, o `scope["client"]` continuou sendo o endereço real, e as cem requests dividiram um balde só.

### E a reviravolta: a camada 2 também vale para o proxy

Agora o teste que interessa. Proxy com as duas linhas descomentadas na 8080; FairFare de volta aos padrões na 8000 (mate o da flag e suba de novo sem ela); e o mesmo spoof — mas pelo proxy:

```console
$ uv run python $C http://localhost:8080/api/users 100 --header 'X-Forwarded-For: 10.0.0.{i}'
100 requests em 0.22s  status → 200: 100
```

Cem de cem. **De novo.** O proxy sobrescreveu o header, e o spoof passou assim mesmo.

O motivo é bonito e vale mais que a correção: o proxy sobrescreveu com `request.client.host` — e `request.client.host`, dentro do proxy, **já estava adulterado**. O `proxy.py` também roda sob um uvicorn. Esse uvicorn também tem `--proxy-headers` ligado por padrão. Ele também viu uma conexão vinda de `127.0.0.1`, também achou confiável, também leu o `X-Forwarded-For` que eu inventei e também trocou o `scope["client"]` — antes do `repassar()` ser chamado. O proxy copiou fielmente uma mentira que ele mesmo tinha acabado de acreditar.

A correção é dizer ao uvicorn da **borda** que ele não deve ouvir ninguém:

```bash
uv run uvicorn proxy:app --port 8080 --no-proxy-headers --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

```console
$ uv run python $C http://localhost:8080/api/users 100 --header 'X-Forwarded-For: 10.0.0.{i}'
100 requests em 0.19s  status → 200: 20  429: 80  (Retry-After: 1s)
$ uv run python $C http://localhost:8080/api/users 100
100 requests em 0.20s  status → 200: 20  429: 80  (Retry-After: 1s)
```

Com header inventado ou sem, o mesmo `20 / 80`. O `request.client.host` do proxy voltou a ser o endereço TCP de verdade, o proxy escreveu esse endereço no `X-Forwarded-For`, e o FairFare viu um cliente só.

*(As seis cargas desta lição — as duas diretas, as três pelo proxy e a do `--forwarded-allow-ips` — saíram todas de uma sessão só, na mesma máquina, na ordem em que aparecem.)*

Daí a regra, que cabe em uma frase e é a lição inteira:

**Cada camada só pode acreditar em `X-Forwarded-*` vindo da camada de dentro. Quem está na borda não acredita em ninguém.**

A diferença entre os dois programas é o padrão. No nginx, `$remote_addr` é quem abriu a conexão TCP e ponto; existe um módulo (`ngx_http_realip_module`) que o substitui pelo que um header disser, mas ele **só age nas fontes que você listar** em `set_real_ip_from` — que é o `--forwarded-allow-ips` com outro nome, e vem desligado. O uvicorn já vem ligado, acreditando em `127.0.0.1`. Isso é ótimo no arranjo comum (proxy e app na mesma máquina) e é exatamente o que te morde quando ele fica exposto.

## O que fica declarado

Como sempre, o que este código **não** resolve, dito na cara:

- **A configuração de produção não foi demonstrada aqui, e não tem como ser.** Numa máquina só, o proxy e o atacante têm o mesmo endereço: `127.0.0.1`. Não existe `--forwarded-allow-ips` que aceite um e recuse o outro. O que foi medido é a flag funcionando por **exclusão** (`10.20.30.40`, que não é ninguém). Confiar só no IP do proxy é configuração escrita, não rodada — e o capítulo 10, com Docker e endereços reais, é onde ela roda.
- **O `proxy.py` sobrescreve, nunca acrescenta.** É o comportamento certo para uma borda, que é o papel dele aqui. Se algum dia ele virasse o segundo proxy de uma cadeia, ele apagaria o endereço do cliente real — e aí o certo seria o equivalente ao `$proxy_add_x_forwarded_for`.
- **O rate limiter do FairFare não mudou nesta lição.** Ele continua usando `scope["client"]` como chave, e continua certo em fazer isso: quem tem que garantir que esse valor é confiável é a configuração do servidor, não o middleware. As outras limitações dele (baldes por processo, dicionário que nunca esquece) continuam de pé e são assunto do capítulo 6.
- **Nesta bancada o FairFare continua enganável na 8000.** O proxy protege o caminho que passa por ele — e só. O uvicorn de baixo segue com os padrões, escutando em `127.0.0.1:8000`, e quem bater lá direto continua fazendo o que a carga com `X-Forwarded-For: 10.0.0.{i}` fez lá em cima: cem de cem. É o arranjo de laboratório, de propósito, porque as duas cargas precisam existir lado a lado. Num servidor real a camada 2 fecha isso, e é a configuração que só o capítulo 10 consegue rodar.
- **O `Caddyfile` não tem nenhuma linha de `X-Forwarded-*`, e não é esquecimento.** O `reverse_proxy` do Caddy já escreve os três headers sozinho e, por padrão, ignora os que vierem de fora — o `trusted_proxies` começa vazio. Ele nasce fazendo o que esta lição levou uma lição inteira para explicar: o oposto do padrão do uvicorn. (Leitura da documentação do Caddy, como sempre; o `Caddyfile` da bancada ganhou dois comentários dizendo isso.)
- **`--no-proxy-headers` no proxy é a configuração da bancada a partir de agora.** O `README.md` da bancada e o docstring do `proxy.py` trazem a versão com a flag.

## O que você deve conseguir fazer agora

- Explicar por que, atrás de um proxy, `scope["client"]` deixa de responder "quem é o cliente" — e qual pergunta ele responde de verdade.
- Dizer o que um proxy de borda deve fazer com um `X-Forwarded-For` que já veio de fora, e por que `setdefault` é a resposta errada.
- Apontar as duas camadas da fronteira de confiança e dizer qual delas o `--forwarded-allow-ips` implementa.
