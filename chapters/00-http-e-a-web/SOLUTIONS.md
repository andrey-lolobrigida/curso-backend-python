# Soluções do capítulo 0

Leia isto só depois de tentar. Não por moralismo — por eficiência: o entendimento se forma no atrito, e a resposta lida sem luta evapora em uma semana. Empacou 20 minutos numa pergunta? Aí sim, este arquivo paga o aluguel.

Cada solução traz o comando, a saída relevante e **o raciocínio** — o que a pergunta queria que você percebesse.

## Exercício 1 — Caça ao tesouro

### T1 — status e Content-Type de GET /quadras

```console
$ curl -i localhost:8000/quadras
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
...
```

Status `200`, corpo em JSON. O ponto da pergunta: acostumar o olho a ler a status line e os headers *antes* do corpo — a ordem em que um cliente de verdade lê.

### T2 — quantas quadras de tênis?

```bash
curl "localhost:8000/quadras?esporte=tenis"
```

Duas: Quadra Central e Saibro do Fundo. A peneira foi a **query string** `?esporte=tenis` — o recurso continua sendo `/quadras`; a query só refina (lição 07). E as aspas na URL protegem o `?` do seu shell.

### T3 — o segredo

Batendo sem credencial:

```console
$ curl -i localhost:8000/segredo
HTTP/1.1 401 Unauthorized
X-Dica: a senha e clube-do-backend
```

A chave estava na recusa: o header `X-Dica`. Quem só olha o corpo do erro não a vê — a pergunta existe para você criar o hábito de ler headers de resposta. Com a credencial:

```console
$ curl -H "X-Senha: clube-do-backend" localhost:8000/segredo
{
  "segredo": "voce leu os headers. e exatamente assim que se faz."
}
```

### T4 — a rota que se mudou

```console
$ curl -i localhost:8000/antigo
HTTP/1.1 301 Moved Permanently
Location: /quadras
```

Status `301`, novo endereço no header `Location`. O curl, por padrão, **não segue** o bilhete — ele te mostra o 301 e pronto. Com `-L`, ele lê o `Location` e refaz a request no novo caminho, devolvendo as quadras. Navegadores fazem esse `-L` sozinhos a vida inteira sem você notar.

### T5 — criando a reserva

```console
$ curl -i -X POST localhost:8000/reservas \
    -H "Content-Type: application/json" \
    -d '{"quadra_id": 1, "quem": "SEU-NOME"}'
HTTP/1.1 201 Created
Location: /reservas/1
```

`201 Created` confirma; `Location` diz onde a criatura mora. Se você levou um `415` no caminho, foi porque o `-d` sozinho anuncia o corpo como formulário (`application/x-www-form-urlencoded`) — o `-H` com o `Content-Type` certo resolve (lição 08).

### T6 — PUT /quadras

```console
$ curl -i -X PUT localhost:8000/quadras
HTTP/1.1 405 Method Not Allowed
Allow: GET
```

`405` = a rota existe, o método não. E o header `Allow` entrega o cardápio: ali, só GET. Um servidor bem educado recusa ensinando.

### T7 — a mesma request, duas vezes

```console
$ curl localhost:8000/reservas
[ { "id": 1, ... }, { "id": 2, ... } ]
```

**Duas reservas.** Requests idênticas, efeitos acumulados: POST não é idempotente (lição 06). Agora imagine que cada reserva custa R$80 e a segunda request foi uma retentativa automática depois de um timeout... É exatamente assim que se cobra alguém duas vezes, e é por isso que idempotência deixará de ser trivia e virará projeto de engenharia nos capítulos 7 e 8.

### T8 — o café recusado

```console
$ curl -i localhost:8000/cha
HTTP/1.1 418 I'm a Teapot
```

O código 418 vem da RFC 2324 (1º de abril de 1998), que especifica o *Hyper Text Coffee Pot Control Protocol*. Um bule de chá, coerentemente, recusa-se a passar café. Zero utilidade, cem por cento tradição — e uma boa desculpa para você descobrir que RFCs são legíveis e às vezes engraçadas.

## Exercício 2 — A request crua

### R1 — GET na unha

Conteúdo de `request-quadras.txt` (a última linha em branco faz parte):

```http
GET /quadras HTTP/1.1
Host: localhost:8000
Connection: close

```

```console
$ nc localhost 8000 < request-quadras.txt
HTTP/1.1 200 OK
...
```

Cada linha com seu papel: a request line pede; o `Host` é obrigatório no HTTP/1.1; o `Connection: close` avisa "depois desta, pode desligar" (sem ele, o servidor mantém a conexão aberta esperando a próxima request, e o `nc` fica pendurado); a linha em branco diz "acabaram os headers". Faltou ela? O servidor segue esperando headers para sempre — e o terminal fica mudo.

### R2 — POST na unha

O corpo escolhido: `{"quadra_id": 2, "quem": "voce"}`. Contando os bytes (todo caractere aqui é ASCII, 1 byte cada — contando na mão ou com `printf '%s' '...' | wc -c`): **32**.

Conteúdo de `request-reserva.txt`:

```http
POST /reservas HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Content-Length: 32
Connection: close

{"quadra_id": 2, "quem": "voce"}
```

```console
$ nc localhost 8000 < request-reserva.txt
HTTP/1.1 201 Created
Location: /reservas/1
...
```

O `Content-Length` é o combinado de quantos bytes de corpo o servidor deve ler após a linha em branco. Minta para menos e ele lê seu JSON pela metade (400); minta para mais e ele fica esperando bytes que não virão. É o mesmo header que você viu nas responses — o contrato vale nos dois sentidos.

## Exercício 3 — Scripts quebrados

O padrão dos três consertos, antes dos detalhes: **nenhum exigia adivinhar**. O servidor disse `405 Method Not Allowed`, disse `415` com "mande Content-Type", disse `301` com o novo endereço. O protocolo foi desenhado para que as respostas carreguem o diagnóstico — ler o que o servidor responde é metade do ofício de backend (a outra metade é escrever servidores que respondem assim de claros).

### 3.1 — método errado

**Sintoma:** `RuntimeError: o servidor respondeu 405 Method Not Allowed`.

**Diagnóstico:** o script usava `POST` para *ler* `/quadras` — verbo de criação em pedido de leitura. O 405 diz exatamente isso; um `curl -i -X POST localhost:8000/quadras` mostraria até o `Allow: GET` com a resposta certa.

**Conserto** — uma palavra:

```python
    conexao.request("GET", "/quadras")
```

Arquivo completo consertado:

```python
"""Exercício 3.1 — este script deveria listar as quadras, mas alguém o quebrou.
...
"""

import json
from http.client import HTTPConnection


def busca_quadras():
    conexao = HTTPConnection("localhost", 8000)
    conexao.request("GET", "/quadras")
    resposta = conexao.getresponse()
    if resposta.status != 200:
        raise RuntimeError(f"o servidor respondeu {resposta.status} {resposta.reason}")
    return json.loads(resposta.read())


def exibe(quadras):
    for q in quadras:
        print(f"{q['nome']} ({q['esporte']}) - R${q['preco_hora']}/h")


if __name__ == "__main__":
    exibe(busca_quadras())
```

### 3.2 — a etiqueta e o dialeto

**Sintoma 1:** `o servidor respondeu 415: mande Content-Type: application/json`. O script mandava o corpo sem anunciar o formato. Conserto: passar o header na request.

**Sintoma 2 (depois do primeiro conserto):** `o servidor respondeu 400: o corpo nao e JSON valido`. O erro **mudou** — progresso! Agora o servidor aceita o pacote, mas não entende o conteúdo: `str(dicionario)` produz `{'quadra_id': 1, 'quem': 'voce'}`, com **aspas simples** — sintaxe de Python, não JSON (lição 08). Conserto: `json.dumps`.

Arquivo completo consertado:

```python
"""Exercício 3.2 — este script deveria criar uma reserva, mas ele tem DOIS bugs.
...
"""

import json
from http.client import HTTPConnection


def cria_reserva(quadra_id, quem):
    conexao = HTTPConnection("localhost", 8000)
    corpo = json.dumps({"quadra_id": quadra_id, "quem": quem})
    conexao.request(
        "POST",
        "/reservas",
        body=corpo,
        headers={"Content-Type": "application/json"},
    )
    resposta = conexao.getresponse()
    if resposta.status != 201:
        detalhe = resposta.read().decode()
        raise RuntimeError(f"o servidor respondeu {resposta.status}: {detalhe}")
    return resposta.getheader("Location")


if __name__ == "__main__":
    endereco = cria_reserva(quadra_id=1, quem="voce")
    print(f"Reserva criada! Ela mora em: {endereco}")
```

A moral do exercício: dois bugs empilhados se revelam **um de cada vez**, e cada resposta de erro aponta o próximo passo. Consertar-observar-consertar é o loop; quem tenta consertar tudo às cegas de uma vez fica sem o mapa.

### 3.3 — o script crédulo

**Sintoma:** `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`.

**Diagnóstico:** repare que o erro nem menciona HTTP — ele estoura no `json.loads`. O script pediu `/antigo`, recebeu um `301` com corpo **vazio** (`char 0`: não havia nem um byte para ler) e tentou interpretar o nada como JSON. O bug de verdade não é o endereço velho — é a **credulidade**: o script nunca olhou o status antes de usar o corpo.

**Conserto:** reagir ao que o servidor disse — se veio 301, ler o `Location` e refazer a request no novo caminho; e nunca mais tocar num corpo sem conferir o status:

```python
"""Exercício 3.3 — este script usa um endereço antigo do servidor e confia demais.
...
"""

import json
from http.client import HTTPConnection


def conta_quadras():
    conexao = HTTPConnection("localhost", 8000)
    conexao.request("GET", "/antigo")
    resposta = conexao.getresponse()
    if resposta.status == 301:
        novo_caminho = resposta.getheader("Location")
        resposta.read()  # esvazia esta resposta para reusar a conexão
        conexao.request("GET", novo_caminho)
        resposta = conexao.getresponse()
    if resposta.status != 200:
        raise RuntimeError(f"o servidor respondeu {resposta.status} {resposta.reason}")
    dados = json.loads(resposta.read())
    return len(dados)


if __name__ == "__main__":
    print(f"O servidor conhece {conta_quadras()} quadras.")
```

"Mas era só trocar `/antigo` por `/quadras` no código!" — era, e por isso o enunciado proibiu. No mundo real, o endereço velho vem de um config, de um cliente antigo, de um link publicado — coisas que você não controla. O 301 existe justamente para que servidores possam se mudar sem quebrar quem ficou para trás. Um cliente que sabe *reagir a status codes* sobrevive a mudanças; um que só conhece o caminho feliz quebra na primeira esquina. (É o que o `-L` do curl e o seu navegador fazem por você o tempo todo — agora você já fez na mão.)