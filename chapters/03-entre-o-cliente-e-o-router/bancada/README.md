# A bancada

Isto é **instrumento, não produto**.

Vale a mesma regra do capítulo 2: o curso vive numa única base de código que cresce, o FairFare, em `app/`. Esta pasta é a exceção declarada. São aparelhos — servidores de mentira, um espião que imprime o que chega, um proxy escrito à mão — que existem só para fazer aparecer na tela o que normalmente é invisível entre o cliente e a primeira linha do seu router.

Regras da bancada:

- **Nada daqui entra no FairFare.** Se um trecho parecer útil no app, ele volta pelo caminho normal: uma lição que o motive.
- **Nada daqui é exemplo de produção.** O proxy desta pasta imprime corpos de request no terminal — de propósito, porque é isso que a gente veio ver. Num servidor de verdade isso é um vazamento de dados, não um recurso.
- **Tudo que é Python aqui roda.** As saídas que aparecem nas lições saíram destes arquivos, na máquina do autor. Rode você também: as suas vão ser parecidas, não idênticas (a porta do cliente muda a cada conexão), e a lição sempre diz o que importa olhar.

## Os aparelhos

| Arquivo | O que é | Nasce na lição |
|---|---|---|
| `asgi_cru.py` | Um app ASGI sem framework nenhum: três argumentos, duas mensagens, uma resposta de texto | 01 |
| `espiao.py` | O FairFare de verdade embrulhado num middleware que imprime o `scope` de cada request | 01 |
| `carga.py` | Dispara N requests, conta os status um a um, aceita headers extras (com `{i}` virando o número da request) e sabe abrir uma conexão nova a cada uma | 02 |
| `cebola.py` | Três middlewares que imprimem quando entram e quando saem, para ver a ordem invertida do `add_middleware` | 03 |
| `pagina/index.html` | Uma página estática que lista e cria usuários do FairFare via `fetch` — na lição 04 de outra origem; na 07, da mesma | 04 |
| `proxy.py` | Um proxy reverso em cinquenta linhas: repassa `/api/...` para o FairFare e serve a página como estático, imprimindo tudo o que atravessa | 06 |
| `Caddyfile` | A mesma configuração do `proxy.py`, escrita para o Caddy. **Lido, nunca executado** | 07 |
| `nginx.conf` | A mesma configuração do `proxy.py`, escrita para o nginx. **Lido, nunca executado** | 07 |
| `eco.py` | Um espelho: devolve em JSON quem o servidor **acha** que é o cliente, por qual esquema a request chegou e os `X-Forwarded-*` que ele recebeu | 08 |

*(A tabela cresce junto com o capítulo.)*

## As portas

O capítulo inteiro respeita este mapa. Quando uma lição pedir duas ou três abas de terminal ao mesmo tempo — e várias vão pedir —, cada aba ocupa uma porta diferente:

| Porta | Quem mora ali |
|---|---|
| 8000 | O FairFare (ou um servidor da bancada no lugar dele) |
| 8080 | A página estática / o proxy reverso |
| 8443 | O proxy reverso com TLS |

Se uma porta estiver ocupada, o uvicorn morre na subida com um erro claro (`address already in use`). Mate o servidor da aba anterior antes de subir o próximo.

## Como usar

O app ASGI cru, numa aba:

```bash
uv run uvicorn asgi_cru:app --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

Em outra, bata nele:

```bash
curl -s localhost:8000/qualquer/coisa
```

O espião — o FairFare de verdade, com o `scope` impresso no terminal do servidor:

```bash
uv run python -m uvicorn espiao:app --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

O `python -m` não é enfeite: com `--app-dir`, o uvicorn põe a bancada no `sys.path` **no lugar** do diretório atual, e o espião importa `app.main`. Com o `-m`, o próprio Python já pôs a raiz lá antes. Sem ele, o import falha. A lição 01 explica.

A carga, contra o FairFare de sempre. O mesmo par de comandos da lição 02 — o segundo joga fora a conexão depois de cada request:

```bash
C=chapters/03-entre-o-cliente-e-o-router/bancada/carga.py
uv run python $C http://localhost:8000/users 200 --em-serie
uv run python $C http://localhost:8000/users 200 --em-serie --nova-conexao
```

Sem `--em-serie`, ela dispara tudo de uma vez — é assim que a lição 02 arranca um `503` de um servidor com `--limit-concurrency`.

A cebola — três camadas em volta de um router de uma linha:

```bash
uv run uvicorn cebola:app --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

Bata nela com `curl -s localhost:8000/` e leia o terminal **do servidor**: os middlewares imprimem lá, não na resposta. A ordem que aparece é o assunto da lição 03.

A página, que precisa de **duas** abas: o FairFare de verdade numa porta e alguém servindo a página na outra. Ela lista e cria usuários, então o banco precisa estar migrado: rode `uv run alembic upgrade head` antes.

O app, sempre na primeira aba:

```bash
uv run uvicorn app.main:app --port 8000
```

Na segunda aba, o proxy reverso da lição 06 — que serve a página **e** repassa `/api/...` para o FairFare:

```bash
uv run uvicorn proxy:app --port 8080 --no-proxy-headers \
    --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

O `--no-proxy-headers` entrou na lição 08 e não é enfeite: sem ele, o uvicorn que serve o
proxy acredita no `X-Forwarded-For` que o cliente mandar, e o proxy repassa a mentira adiante.
Quem está na borda não acredita em ninguém. (As lições 06 e 07 sobem o proxy sem a flag, porque
lá o assunto ainda não existia.)

Abra `http://localhost:8080` **com o console do browser aberto**. Leia também o terminal do proxy: ele imprime toda request que atravessa, corpo incluído. Para bater só na API, sem browser: `curl -s localhost:8080/api/users`.

O espelho da lição 08, que troca de lugar com o FairFare para mostrar o que o servidor
acha que sabe sobre o cliente — ele fica na 8000, com o proxy na 8080 na frente:

```bash
uv run uvicorn eco:app --port 8000 --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

```bash
curl -s localhost:8080/api/
curl -s -H 'X-Forwarded-For: 8.8.8.8' localhost:8080/api/
```

O segundo comando é o ponto da lição 08. Com o proxy subido do jeito acima — **com**
`--no-proxy-headers` — o espelho responde `"cliente": ["127.0.0.1", 0]` nos dois casos: o header
inventado morre na borda. Tire a flag, suba o proxy de novo e repita o segundo comando: agora o
espelho responde `"cliente": ["8.8.8.8", 0]`. É a diferença inteira, em um `curl`.

**Para refazer a lição 04**, que é o arranjo anterior — página numa origem, API em outra —, troque as duas coisas juntas: a segunda aba vira

```bash
python3 -m http.server 8080 --directory chapters/03-entre-o-cliente-e-o-router/bancada/pagina
```

e em `pagina/index.html` a constante volta a ser `const API = "http://localhost:8000"`. As duas mudanças andam em par: com o `http.server`, `/api` não existe e o `fetch` toma 404 em vez de esbarrar no CORS. E tem uma terceira, sem a qual não há cena: o `app/main.py` de hoje já traz o conserto da lição 04, então comente o bloco do `CORSMiddleware` e reinicie o FairFare. Descomente quando terminar.
