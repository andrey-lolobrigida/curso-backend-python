# Lição 05 — Status codes: as famílias e os que importam

O código de status é a primeira coisa que qualquer cliente olha numa response — o "sim/não/depende" oficial da conversa. Um cliente bem escrito decide o que fazer *antes* de olhar o corpo: comemorar, redirecionar, corrigir a própria request ou desistir educadamente.

A boa notícia: você não precisa decorar dezenas de códigos. Precisa entender **quatro famílias** e conhecer **uns dez códigos** de nome.

## As famílias: o primeiro dígito conta a história

| Família | Tradução honesta | Quem age em seguida |
|---------|------------------|---------------------|
| **2xx** | "Funcionou." | Ninguém — siga a vida |
| **3xx** | "O que você quer está em outro lugar." | O cliente, indo até lá |
| **4xx** | "Tem algo errado — **e o erro é seu**." | O cliente, corrigindo a request |
| **5xx** | "Tem algo errado — **e o erro é meu**." | O servidor (e quem o mantém) |

A divisão que mais importa na vida real é **4xx vs 5xx**, porque ela aponta o culpado. Um 4xx diz: sua request veio torta, consertá-la resolve. Um 5xx diz: sua request pode estar perfeita, quem quebrou foi o outro lado. Quando seu backend estiver no ar, essa distinção decide quem é acordado de madrugada.

(Existe também a família 1xx, de respostas provisórias durante a conversa. Você pode viver anos sem encontrá-la; fica registrado que existe.)

## O elenco principal

Cada um destes você pode provocar no mini-servidor — e deve. Comandos e respostas reais:

**200 OK** — funcionou, e aqui está o que você pediu.

```console
$ curl -i localhost:8000/quadras
HTTP/1.1 200 OK
```

**201 Created** — funcionou *e algo novo passou a existir*. Vem com o header `Location` apontando onde:

```console
$ curl -i -X POST localhost:8000/reservas \
    -H "Content-Type: application/json" -d '{"quadra_id": 1, "quem": "ana"}'
HTTP/1.1 201 Created
Location: /reservas/1
```

**204 No Content** — funcionou, e não há nada a dizer. O finale típico de um DELETE (viu na lição 04).

**301 Moved Permanently** — mudou de endereço para sempre; o novo está no `Location`. É o `/antigo` do nosso servidor.

**400 Bad Request** — sua request está malformada. O 4xx genérico, o "não entendi o que você disse":

```console
$ curl -i -X POST localhost:8000/reservas \
    -H "Content-Type: application/json" -d 'isso nao e json'
HTTP/1.1 400 Bad Request
```

**401 Unauthorized** — você não se identificou (ou se identificou mal). Nosso `/segredo` devolve isso para quem chega sem credencial. Detalhe de nomenclatura mal resolvida do protocolo: apesar do nome, 401 é sobre **identificação**, não autorização. O código para "sei quem você é, mas você não pode" é o **403 Forbidden**. Essa distinção rende conversa no capítulo 5.

**404 Not Found** — o recurso não existe:

```console
$ curl -i localhost:8000/quadras/99
HTTP/1.1 404 Not Found
```

**405 Method Not Allowed** — a rota existe, mas não aceita esse método. Repare no header `Allow`, que lista o que a rota aceita — o servidor recusa e ainda ensina:

```console
$ curl -i -X PUT localhost:8000/quadras
HTTP/1.1 405 Method Not Allowed
Allow: GET
```

**415 Unsupported Media Type** — você mandou um corpo num formato que o servidor não aceita (ou esqueceu de dizer o formato). Guarde este; ele vai morder no exercício 3.

**500 Internal Server Error** — o servidor quebrou processando sua request: uma exceção não tratada, um bug, um banco fora do ar. O nosso mini-servidor é simples demais para provocar um 500 honesto — mas prometo que, a partir do capítulo 1, você vai gerar muitos. Todo backend real gera. A diferença entre amador e profissional é o que acontece *depois* (capítulo 8).

## Uma curiosidade que é quase um aperto de mão secreto

Existe um código 418 — **I'm a teapot** — criado numa RFC de 1º de abril de 1998 para bules de chá que se recusam a fazer café. Virou tradição da comunidade e teste de carinho de quem constrói APIs. O nosso servidor tem um bule escondido; a caça é sua (exercício 1).

## O que você deve conseguir fazer agora

- Dado um cenário, dizer a família e o código provável:
  - "o cliente pediu uma reserva que não existe" → ?
  - "o servidor lançou uma exceção não tratada" → ?
  - "faltou a credencial na request" → ?
  - "criei o recurso que você pediu" → ?
- Explicar por que a divisão 4xx/5xx é a mais importante do protocolo.
- Explicar a pegadinha do 401 vs 403 em uma frase cada.