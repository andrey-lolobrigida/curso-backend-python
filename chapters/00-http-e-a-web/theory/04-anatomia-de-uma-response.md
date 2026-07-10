# Lição 04 — Anatomia de uma response

A response é o espelho da request: também é texto, também tem uma primeira linha especial, headers, linha em branco e corpo. Se você entendeu a lição 03, esta vai parecer um déjà vu — e é exatamente essa a graça do HTTP: **um formato só, nos dois sentidos**.

Com o servidor no ar, rode:

```console
$ curl -i localhost:8000/quadras
HTTP/1.1 200 OK
Server: MiniServidorCap00/0.1 Python/3.11.14
Date: Fri, 10 Jul 2026 15:48:23 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 296

[
  {
    "id": 1,
    "nome": "Quadra Central",
    ...
```

(`-i` mostra os headers da response junto com o corpo — é o `-v` sem o lado do cliente. A data, claro, será a sua.)

## A status line

A primeira linha da response responde a pergunta que todo cliente faz primeiro: *deu certo?*

```
HTTP/1.1 200 OK
   |      |   |
versão  código frase-razão
```

- A **versão**, como na request.
- O **código de status**: um número de três dígitos com a resposta oficial. É a informação mais importante da response inteira — tanto que a próxima lição é só sobre ele.
- A **frase-razão** (`OK`, `Not Found`...): uma legenda para humanos. É decorativa — clientes decidem pelo número, nunca pela frase. O servidor poderia escrever `200 Beleza` e nada quebraria.

## Headers de response que você já vai usar

**`Content-Type`** — o que é esse corpo que estou te devolvendo. `application/json; charset=utf-8` está dizendo: "interprete esses bytes como JSON, em UTF-8". Sem ele, o corpo é só uma sopa de bytes; o header é a promessa de como lê-la.

**`Content-Length`** — quantos bytes de corpo vêm aí. É assim que o cliente sabe onde a response termina (e como conexões conseguem ser reaproveitadas para a próxima request sem confusão).

**`Location`** — "o que você procura está *ali*". Aparece em dois momentos clássicos. O primeiro: redirects. Nosso servidor tem uma rota `/antigo` que se mudou:

```console
$ curl -i localhost:8000/antigo
HTTP/1.1 301 Moved Permanently
Server: MiniServidorCap00/0.1 Python/3.11.14
Date: Fri, 10 Jul 2026 15:48:23 GMT
Location: /quadras
Content-Length: 0
```

O servidor não devolveu as quadras — devolveu um bilhete dizendo onde elas moram agora. Seguir ou não o bilhete é decisão do cliente (navegadores seguem sozinhos; curl só se você pedir com `-L`). O segundo momento clássico do `Location` você verá no exercício: quando algo é **criado**, o servidor conta onde a criatura mora.

## Nem toda response tem corpo

Repare no `Content-Length: 0` do redirect acima: response sem corpo, e está tudo bem. O exemplo mais famoso é a resposta de uma deleção bem-sucedida:

```console
$ curl -i -X DELETE localhost:8000/reservas/1
HTTP/1.1 204 No Content
Server: MiniServidorCap00/0.1 Python/3.11.14
Date: Fri, 10 Jul 2026 15:48:23 GMT
Content-Length: 0
```

`204 No Content` é o servidor dizendo "feito, e não tenho nada a acrescentar". A informação inteira está na status line. Elegante, não?

(Para rodar esse DELETE você precisa de uma reserva existente — crie uma antes com o POST da lição 03, ou anote e volte depois do exercício 1.)

## O quadro completo

A conversa inteira, lado a lado:

```
REQUEST  (o que você manda)          RESPONSE  (o que volta)
--------------------------------     --------------------------------
POST /reservas HTTP/1.1              HTTP/1.1 201 Created
Host: localhost:8000                 Content-Type: application/json; ...
Content-Type: application/json       Content-Length: 48
Content-Length: 31                   Location: /reservas/1
                                     
{"quadra_id": 1, "quem": "ana"}      { "id": 1, "quadra_id": 1, ... }
```

Método + caminho de um lado; status do outro. Headers dos dois lados. Linha em branco dos dois lados. Corpo opcional dos dois lados. Um idioma só.

## O que você deve conseguir fazer agora

- Rodar `curl -i` em qualquer rota e apontar: status line (e suas três partes), headers, corpo.
- Explicar o que `Content-Type` e `Content-Length` prometem ao cliente.
- Explicar o que um `301` com `Location` está pedindo que o cliente faça — e o que a flag `-L` do curl muda nisso.
- Dar um exemplo de response que não tem corpo e por que isso não é um erro.