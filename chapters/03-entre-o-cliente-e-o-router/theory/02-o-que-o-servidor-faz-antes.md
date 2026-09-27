# Lição 02 — O que o servidor faz antes do seu app

A lição 01 terminou com uma lista de quatro itens e uma confissão: *"estou nomeando, não explicando"*.

Os quatro eram estes. Escutar uma porta e aceitar uma conexão TCP. Ler os bytes que chegaram. Entender HTTP/1.1 naqueles bytes. Montar o `scope` e chamar a sua corrotina.

Agora a explicação. E ela vai desembocar num lugar prático: **o servidor pode dizer não à sua request antes de o seu código existir** — e você tem duas manoplas para regular isso.

## Os quatro passos, um por vez

### 1. Aceitar a conexão

O uvicorn abre um socket, avisa o sistema operacional que quer escutar na porta 8000 e fica esperando. Quando um cliente conecta, o kernel faz o **handshake de três vias** do TCP — "podemos falar?" / "podemos" / "beleza" — e só então o uvicorn recebe uma conexão pronta para uso.

Esse handshake você já conhece. O capítulo 0 mostrou a conta e deixou a fatura em aberto:

> Um detalhe que vai importar mais tarde: antes de transportar qualquer coisa, o TCP faz um aperto de mão (*handshake*) — uma ida e volta de "podemos falar?" / "podemos". Isso custa tempo. Guarde essa fatura; no capítulo 3, ela explica por que conexões são reaproveitadas em vez de abertas a cada request.

É este capítulo. É esta lição. A fatura vence daqui a duas seções.

### 2. Ler bytes

Aceita a conexão, o uvicorn lê dela. E aqui mora a primeira surpresa de quem nunca mexeu com socket: **TCP não entrega mensagens. Entrega um fluxo de bytes.**

A analogia: TCP é uma mangueira, não um carteiro. O carteiro te entrega envelopes fechados, um de cada vez, e você sabe onde cada carta começa e termina. A mangueira só jorra. Se dois baldes de água entraram de um lado, sai água — não saem dois baldes.

Tecnicamente: uma leitura do socket devolve o que estiver disponível naquele instante. Pode ser meia request. Podem ser duas requests grudadas. Pode ser a linha `GET /users HTTP/1.1` sem os headers ainda, porque o resto está a caminho. O TCP garante que os bytes chegam **na ordem** e **sem buracos**. Não garante mais nada — e, em particular, não faz ideia de onde uma request termina.

Quem tem que descobrir isso é o passo 3.

### 3. Entender HTTP/1.1

Ficou uma pergunta pendurada no fim da lição 01: *o uvicorn escreveu esse parser de HTTP à mão?*

Não. Ele delega:

```bash
$ uv run python -c "
from uvicorn.config import Config
c = Config('app.main:app'); c.load()
print(c.http_protocol_class)
"
<class 'uvicorn.protocols.http.h11_impl.H11Protocol'>
```

Quem lê o HTTP nesta máquina é o **h11**, uma biblioteca que faz exatamente uma coisa: recebe bytes, devolve eventos ("começou uma request", "chegou um pedaço de corpo", "acabou"). O h11 não abre socket nenhum — esse é o estilo *sans-IO*, "sem entrada e saída": a máquina de estados do protocolo separada de quem move os bytes. Dá para testar o parser sem rede, e dá para plugá-lo em qualquer servidor.

O uvicorn aceita um segundo motor, o `httptools` (um embrulho do parser em C do Node.js, mais rápido). Ele escolhe sozinho: usa o `httptools` se estiver instalado, senão cai no h11. Aqui não está instalado, então é h11 — e é por isso que a linha acima diz `h11_impl`. Se a sua disser `httptools_impl`, é só isso: você tem a dependência extra.

Seja qual for o motor, o trabalho é o mesmo: achar a linha de request, achar os headers, achar onde o cabeçalho acaba (uma linha em branco) e decidir onde o corpo termina — pelo `Content-Length` ou pelo `Transfer-Encoding: chunked`. Aquela frase solta da lição 04 do capítulo 0, sobre o `Content-Length` ser "como conexões conseguem ser reaproveitadas para a próxima request sem confusão", é literalmente o algoritmo deste passo.

### 4. Montar o `scope`

Com os eventos do h11 na mão, o uvicorn monta o dicionário que a lição 01 imprimiu com o espião: método, path, query crua, headers como pares de bytes, `client`, `server`, `scheme`. Depois chama `app(scope, receive, send)`.

Repare no que ele **não** fez. Não validou nada. Não olhou a sua tabela de rotas — ele não tem uma. Não decidiu se `/users` existe. O uvicorn atravessa a fronteira ASGI com uma ficha fiel do que veio pelo fio, e o resto é problema seu.

## A fatura do handshake: keep-alive

Passo 1 custa uma ida e volta na rede antes de qualquer byte útil. Fazer isso a cada request seria burrice — então o HTTP/1.1 já nasce com a conexão **persistente** por padrão: respondeu, a conexão fica aberta esperando a próxima request. É o **keep-alive**.

Dá para ver o `curl` reaproveitando. Suba o FairFare numa aba:

```bash
uv run uvicorn app.main:app --port 8000
```

E peça duas coisas de uma vez, na outra:

```bash
$ curl -sv -o /dev/null localhost:8000/users localhost:8000/users 2>&1 | grep -iE 'connected to|re-using|left intact'
* Connected to localhost (127.0.0.1) port 8000
* Connection #0 to host localhost left intact
* Re-using existing connection with host localhost
* Connection #0 to host localhost left intact
```

Conectou uma vez. Deixou intacta. Reusou.

Agora medindo. A bancada ganhou um aparelho novo nesta lição, o `carga.py` — o do capítulo 2 crescido. Ele conta os status um a um, aceita headers extras e sabe jogar a conexão fora depois de cada request. Duzentas requests, uma de cada vez, com e sem reaproveitamento:

```bash
C=chapters/03-entre-o-cliente-e-o-router/bancada/carga.py
```

```
$ uv run python $C http://localhost:8000/users 200 --em-serie
200 requests em 0.21s  status → 200: 200

$ uv run python $C http://localhost:8000/users 200 --em-serie --nova-conexao
200 requests em 0.38s  status → 200: 200
```

Mesmo servidor, mesma rota, mesmas duzentas requests. **1,8× mais lento** só por abrir e fechar uma conexão a cada uma. E `--em-serie` está aí de propósito: em rajada, o tempo mede o paralelismo, não o handshake.

**Agora o aviso honesto, porque esse 1,8× é o menor número que essa conta pode dar.** Isso é loopback: cliente e servidor na mesma máquina, e o handshake nem chega à placa de rede. Compare quanto custa uma ida e volta nos dois mundos — o `ping` mede exatamente isso:

```
$ ping -c 5 127.0.0.1 | tail -1
rtt min/avg/max/mdev = 0.053/0.058/0.064/0.004 ms
$ ping -c 5 1.1.1.1 | tail -1
rtt min/avg/max/mdev = 5.652/5.889/6.209/0.182 ms
```

Cem vezes mais caro. E o `1.1.1.1` ainda é um destino **perto** — um servidor do outro lado de um oceano cobra bem mais que isso; rode o `ping` contra um e veja. É essa ida e volta que o keep-alive economiza a cada request, e nenhum truque de código a encurta. Com TLS por cima (lição 09), são duas idas e voltas antes do primeiro byte de HTTP. É a mesma fatura, cobrada duas vezes.

### Conexão aberta não é conexão eterna

Se o servidor guardasse toda conexão ociosa para sempre, ele acumularia sockets de clientes que foram embora. Então existe um prazo: `--timeout-keep-alive`, **5 segundos** por padrão.

Dá para cronometrar. Uma conexão crua, uma request, e depois esperar sentado até o servidor desistir:

```bash
uv run python - <<'PY'
import socket, time
s = socket.create_connection(("localhost", 8000))
s.sendall(b"GET /users HTTP/1.1\r\nHost: localhost\r\n\r\n")
print("primeira linha:", s.recv(4096).split(b"\r\n")[0].decode())
comeco = time.perf_counter()
s.recv(4096)  # bloqueia até o servidor fechar a conexão
print(f"servidor fechou a conexão ociosa depois de {time.perf_counter() - comeco:.1f}s")
PY
```

Contra o servidor que já está no ar:

```
primeira linha: HTTP/1.1 200 OK
servidor fechou a conexão ociosa depois de 5.0s
```

E contra um subido com `uv run uvicorn app.main:app --port 8000 --timeout-keep-alive 2`:

```
primeira linha: HTTP/1.1 200 OK
servidor fechou a conexão ociosa depois de 2.0s
```

De quebra, esse scriptzinho é o passo 2 e o passo 3 acontecendo à vista: você mandou bytes escritos à mão, com `\r\n` e tudo, e voltou HTTP.

## Os freios brutos

Keep-alive é economia. Agora as duas manoplas que são **recusa**.

### `--limit-concurrency`: o servidor diz não

Suba o FairFare com um teto de dez:

```bash
uv run uvicorn app.main:app --port 8000 --limit-concurrency 10
```

E vá aumentando a rajada. O `carga.py` sem `--em-serie` dispara tudo junto:

```
$ uv run python $C http://localhost:8000/users 8
8 requests em 0.01s  status → 200: 8

$ uv run python $C http://localhost:8000/users 10
10 requests em 0.02s  status → 200: 5  503: 5

$ uv run python $C http://localhost:8000/users 100
100 requests em 0.08s  status → 503: 100
```

Oito passam limpo. Dez viram uma mistura. Cem viram **cem 503**, sem um único 200.

Esse último número costuma surpreender, e a explicação é boa. O uvicorn conta **conexões**, e conta a partir do instante em que a conexão TCP é aceita — antes de ler um byte de request. A checagem acontece quando o uvicorn termina de ler a linha de request e os headers; o `carga.py` em rajada abre as cem conexões praticamente ao mesmo tempo, e nesse instante o contador já passou de dez fazia tempo. Resultado: todas caem no `503`, inclusive as dez que "caberiam".

Não é determinístico. Em cinco rodadas aqui, quatro deram `503: 100` cravado; numa escaparam sete `200`. Depende de quais conexões o kernel estabeleceu antes de o loop do uvicorn respirar. Com dez requests, a mistura varia entre 5/5 e 7/3.

A prova de que o limite é sobre **simultaneidade**, e não sobre volume: as mesmas cem requests, uma de cada vez, passam inteiras.

```
$ uv run python $C http://localhost:8000/users 100 --em-serie
100 requests em 0.11s  status → 200: 100
```

Cem requests, zero recusas, no servidor com teto de dez. Nunca houve mais de uma conexão viva ao mesmo tempo.

E o ponto que importa para o capítulo: **esse 503 sai sem o seu código rodar.** Nenhum router, nenhuma dependência, nenhuma query. O uvicorn viu o contador estourado, escreveu a resposta e fechou.

### `--backlog`: a fila antes do `accept`

A outra manopla é mais sutil. Entre "o kernel completou o handshake" e "o uvicorn chamou `accept()`" existe uma fila — as conexões prontas, esperando o processo pegá-las. O tamanho dela é o `--backlog` (2048 por padrão).

Encolhi para 1 e mandei as mesmas cem simultâneas. Servidor normal: `100 requests em 0.14s  status → 200: 100`. Com `--backlog 1`: `100 requests em 2.77s  status → 200: 100`.

Repare no que **não** aconteceu: nenhum erro. Nenhuma conexão recusada. Todas as cem responderam 200. O que mudou foi o relógio — vinte vezes mais lento.

É assim que o Linux se comporta: fila cheia não vira "não", vira silêncio. O kernel descarta o pacote do handshake sem avisar, e quem ficou sem resposta tenta de novo mais tarde — a primeira espera é da ordem de um segundo, e cada nova tentativa espera o dobro. É essa espera, medida em segundos e não em milissegundos, que apareceu no relógio. Por isso este flag entra aqui como nota de rodapé, não como manchete: **você não vai ver `--backlog` num incidente como erro. Vai ver como lentidão.**

## O 503 do servidor e o 500 do pool

Volte à lição 09 do capítulo 2. Cem clientes simultâneos no FairFare síncrono davam isto:

> **60,16s — 80 requests com erro 500**

Oitenta pessoas esperaram um minuto para receber um erro. E o erro era o `QueuePool limit of size 5 overflow 10 reached` — o pool de conexões estourando **dentro** do app. Cada uma dessas requests já tinha atravessado router, service e repository, e sentado trinta segundos na fila do pool.

Compare com o `503` desta lição. Mesmo tipo de problema — mais gente do que o processo aguenta —, resposta completamente diferente:

| | 500 do pool (cap. 2) | 503 do servidor (aqui) |
|---|---|---|
| Onde nasce | dentro do app, na camada de dados | no servidor, antes do ASGI |
| Quando o cliente sabe | depois de 30s de espera | na hora |
| Custo por request recusada | router + service + pool + timeout | um contador e uma resposta |
| O que o cliente entende | "quebrou algo aí dentro" | "estou sobrecarregado, volte depois" |

Dizer não cedo é mais barato e mais previsível. E o código diz a verdade: o capítulo 0 apresentou o **500** como "o servidor quebrou processando sua request". Não foi o caso aqui — nada quebrou. O **503**, *Service Unavailable*, é o 5xx que diz "não consigo agora", que é uma informação diferente e mais útil, principalmente para um cliente que sabe tentar de novo.

Não é que o freio do servidor substitua o dimensionamento do pool — o capítulo 4 vai dimensionar o pool de verdade. É que ele te dá um teto **antes** do teto, com falha barata em vez de falha cara.

## Mas ele diz não para todo mundo igual

Agora o defeito, e ele é grande.

O `--limit-concurrency` não sabe quem está do outro lado. Um script maluco abrindo cem conexões e cem pessoas legítimas reservando ao mesmo tempo são, para ele, exatamente a mesma coisa: cem. Ele recusa a centésima porque é a centésima, não porque ela é suspeita.

É um fusível, não um segurança. Fusível protege a instalação; ele não escolhe quem fica sem luz.

Distinguir cliente de cliente — "este IP fez 300 requests em dez segundos, aquele fez 3" — exige contar por cliente, e isso é trabalho para dentro do processo. É a lição 05, o rate limiting.

Só que "dentro do processo" ainda é um endereço vago demais. Entre a fronteira ASGI e a sua função de rota existe uma pilha de coisas rodando em ordem, e é preciso saber exatamente onde um contador desses se encaixa — e por que ele não pode ir no lugar óbvio. Esse é o assunto da lição 03.

## O que você deve conseguir fazer agora

- Listar os quatro passos entre o socket e o `scope`, e dizer o que cada um resolve.
- Explicar por que TCP entregar "um fluxo de bytes" obriga alguém a parsear HTTP, e dizer quem faz isso no seu uvicorn.
- Explicar o que é keep-alive e mostrar a diferença medida entre reaproveitar e reabrir conexão — e por que o número no loopback é o piso, não o teto.
- Descobrir, com uma conexão crua, em quantos segundos o seu servidor fecha uma conexão ociosa.
- Subir o app com `--limit-concurrency` e produzir um `503` de propósito, sabendo dizer por que a rajada inteira cai mesmo quando o limite "caberia".
- Dizer em uma frase o que o `503` do servidor tem de diferente do `500` do pool do capítulo 2.
- Explicar por que `--backlog` aparece como lentidão, e não como erro.
