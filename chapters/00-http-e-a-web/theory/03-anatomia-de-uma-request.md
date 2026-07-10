# Lição 03 — Anatomia de uma request

Hora da revelação central deste capítulo: **uma request HTTP é texto**. Não é um formato binário misterioso, não é mágica de framework. É uma carta, escrita num formato combinado, que qualquer pessoa consegue ler — e, com um pouco de prática, escrever à mão.

Olhe uma inteira:

```http
POST /reservas HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Content-Length: 31

{"quadra_id": 1, "quem": "ana"}
```

É isso. Isso é tudo que o cliente manda. Vamos dissecar.

## As quatro partes

**1. A request line** — a primeira linha diz o essencial: `POST /reservas HTTP/1.1`.

- `POST` é o **método**: o tipo de ação que estou pedindo (a lição 06 é toda sobre eles).
- `/reservas` é o **caminho**: em qual recurso estou interessado.
- `HTTP/1.1` é a **versão** do protocolo que estou falando.

**2. Os headers** — pares `Nome: valor`, um por linha. São os metadados da carta: quem envia, o que tem dentro, o que aceito de volta. O `Host` merece destaque: é **obrigatório** no HTTP/1.1. Parece redundante ("eu já me conectei a você, por que dizer seu nome?"), mas uma mesma máquina pode hospedar vários sites — o `Host` diz *qual deles* você quer. É o "aos cuidados de" do envelope.

**3. A linha em branco** — a parte mais fácil de esquecer e a mais importante: uma linha vazia separa os headers do corpo. É como o servidor sabe que os metadados acabaram. Sem ela, a request é inválida. (No exercício 2 você vai escrever uma request na mão e sentir isso na pele.)

**4. O corpo** — opcional. GETs normalmente não têm; POSTs quase sempre têm. É a carga útil: os dados que você está mandando, no formato anunciado pelo `Content-Type`.

## Chega de teoria: curl

Escrever essas cartas na mão toda vez seria tortura. O **curl** é a ferramenta de linha de comando que escreve por você — onipresente, disponível em qualquer servidor que você acessar na vida. Vale a intimidade.

Suba o mini-servidor do capítulo (está em `exercises/`, instruções no [README dos exercícios](../exercises/README.md) — deixe rodando num terminal e use outro para brincar):

```console
$ cd chapters/00-http-e-a-web/exercises
$ python3 server.py
Mini-servidor no ar em http://localhost:8000 — Ctrl+C para parar.
```

Aproveitando essa primeira caixa: a convenção de todo o curso. Caixas **sem** `$` são comandos prontos para copiar e colar. Caixas **com** `$` são transcrições de uma sessão — as linhas com `$` são o que você digitou (sem o `$`), e as demais são o que o terminal respondeu.

**Rode os comandos desta lição.** Ler curl é como ler partitura: não substitui tocar.

O básico:

```bash
curl localhost:8000/quadras
```

Isso faz um GET e imprime o corpo da resposta. Bonito, mas esconde a carta. A flag `-v` (*verbose*) mostra a conversa inteira:

```console
$ curl -v localhost:8000/quadras
*   Trying 127.0.0.1:8000...
* Connected to localhost (127.0.0.1) port 8000
> GET /quadras HTTP/1.1
> Host: localhost:8000
> User-Agent: curl/8.5.0
> Accept: */*
>
< HTTP/1.1 200 OK
< Server: MiniServidorCap00/0.1 Python/3.11.14
< Content-Type: application/json; charset=utf-8
< Content-Length: 296
<
[ ... o JSON das quadras ... ]
```

Aprenda a ler esses símbolos, porque eles voltam o curso inteiro:

- Linhas com `>` — o que o **cliente enviou**. Olhe: é exatamente a anatomia que descrevemos. Request line, headers, linha em branco.
- Linhas com `<` — o que o **servidor respondeu** (assunto da próxima lição).
- Linhas com `*` — comentários do próprio curl sobre a conexão (repare o DNS e o TCP da lição 02 acontecendo em tempo real).

Repare também no que você **não** escreveu: curl inventou o `Host`, o `User-Agent` e o `Accept` por conta própria. Ferramentas educadas preenchem o envelope por você.

> **📦 Box: "Connection refused"?! Calma, está tudo bem.**
>
> No seu terminal, as linhas `*` provavelmente incluem algo assim antes da conexão:
>
> ```
> *   Trying [::1]:8000...
> * connect to ::1 port 8000 from ::1 port 59768 failed: Connection refused
> *   Trying 127.0.0.1:8000...
> * Connected to localhost (127.0.0.1) port 8000
> ```
>
> Uma conexão *recusada*? Sim — e nenhum problema. Três coisas estão acontecendo:
>
> 1. **`localhost` tem dois endereços**: `::1` (o loopback do IPv6) e `127.0.0.1` (o do IPv4). O curl tenta o IPv6 primeiro. Nosso servidor escuta só no IPv4 — então a primeira batida encontra a porta 8000 *daquele endereço* vazia, e o sistema recusa na hora. O curl dá de ombros e tenta o endereço IPv4, onde o servidor está. Repare: a porta de destino foi 8000 nas duas tentativas; o que mudou foi o "prédio", não o "apartamento" (lição 02).
> 2. **`Connection refused` não é uma conexão que caiu** — é "não há ninguém escutando neste endereço:porta", antes de qualquer conversa começar.
> 3. **E esse `port 59768`?** Leia a frase inteira: `from ::1 port 59768`. É a porta de **origem**, do lado do curl. Toda conexão TCP tem porta nas duas pontas: a do servidor é fixa e conhecida (8000); a do cliente é sorteada pelo sistema só para aquela conexão — é por ela que a resposta acha o caminho de volta. Na sua máquina, o número será outro.

## As quatro flags que valem o capítulo

**`-X` escolhe o método** (sem ela, curl faz GET):

```bash
curl -X DELETE localhost:8000/reservas/1
```

**`-H` adiciona um header**:

```bash
curl -H "X-Senha: tentei-adivinhar" localhost:8000/segredo
```

**`-d` manda um corpo** (e, de brinde, muda o método para POST — cuidado com essa gentileza):

```bash
curl -d '{"quadra_id": 1, "quem": "ana"}' localhost:8000/reservas
```

**E combinando as três** — um POST completo, com corpo JSON devidamente anunciado:

```bash
curl -v -X POST localhost:8000/reservas \
    -H "Content-Type: application/json" \
    -d '{"quadra_id": 1, "quem": "ana"}'
```

Rode essa última com `-v` e compare as linhas `>` com a carta do início da lição. São a mesma coisa. Sempre foram.

## O que você deve conseguir fazer agora

- Escrever de cabeça, num papel, uma request GET crua válida (request line, `Host`, linha em branco).
- Rodar `curl -v localhost:8000/quadras` e apontar no output: o método, o caminho, a versão e dois headers que o curl adicionou sozinho.
- Dizer o que `-v`, `-X`, `-H` e `-d` fazem, sem consultar.
- Explicar para que serve a linha em branco entre headers e corpo.