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
| `pagina/index.html` | Uma página estática que lista e cria usuários do FairFare via `fetch` — de outra porta, ou seja, de outra origem | 04 |
| `proxy.py` | Um proxy reverso em cinquenta linhas: repassa `/api/...` para o FairFare e serve a página como estático, imprimindo tudo o que atravessa | 06 |

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

A página, que precisa de **duas** abas: o FairFare de verdade numa porta e a página estática na outra. Primeiro o app:

```bash
uv run uvicorn app.main:app --port 8000
```

Depois a página:

```bash
python3 -m http.server 8080 --directory chapters/03-entre-o-cliente-e-o-router/bancada/pagina
```

Abra `http://localhost:8080` **com o console do browser aberto** — é lá que a lição 04 acontece. A página lista e cria usuários, então o banco precisa estar migrado: rode `uv run alembic upgrade head` antes.

O proxy também mora na 8080, então ele entra no lugar do `http.server`, com o FairFare de pé na primeira aba. Na segunda aba, o proxy reverso da lição 06 — que repassa `/api/...` para o FairFare e serve a página como estático (a página só passa a usá-lo na lição 07):

```bash
uv run uvicorn proxy:app --port 8080 --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

Bata nele com `curl -s localhost:8080/api/users` e leia o terminal do proxy: ele imprime toda request que atravessa, corpo incluído.

