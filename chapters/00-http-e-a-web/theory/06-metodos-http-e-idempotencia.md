# Lição 06 — Métodos HTTP e idempotência

Toda request começa com um verbo. Até agora usamos GET e POST meio no instinto; hora de conhecer o elenco completo e — mais importante — as duas propriedades que separam os métodos em castas: **segurança** e **idempotência**. A segunda vai perseguir você pelo curso inteiro, então vamos com calma.

## Os cinco verbos do dia a dia

| Método | Tradução | Tem corpo? | Exemplo no nosso servidor |
|--------|----------|------------|---------------------------|
| **GET** | "me mostre" | não | `GET /quadras` |
| **POST** | "crie" | sim | `POST /reservas` |
| **PUT** | "substitua por isto" | sim | (ainda não temos) |
| **PATCH** | "ajuste este pedaço" | sim | (ainda não temos) |
| **DELETE** | "remova" | não | `DELETE /reservas/1` |

PUT e PATCH fazem parentesco: os dois alteram algo que existe. PUT entrega o recurso **inteiro** de novo ("substitua a reserva pela versão que estou mandando"); PATCH entrega **só o que muda** ("troque apenas o horário"). Nosso mini-servidor ainda não sabe alterar nada:

```console
$ curl -i -X PATCH localhost:8000/reservas/1
HTTP/1.1 405 Method Not Allowed
Allow: GET, POST
```

O que ilustra um ponto que passa batido: **o método é um pedido, não uma ordem**. O cliente pode mandar o verbo que quiser; o servidor decide o que aceita — e um 405 com `Allow` é a recusa educada.

## Segurança: métodos que só olham

Um método é **seguro** quando não muda nada no servidor. GET é o exemplo canônico: você pode fazer mil GETs em `/quadras` e o mundo continua igual. É leitura pura.

Esse contrato é o que permite metade da infraestrutura da web existir: caches guardam respostas de GET, navegadores refazem GETs sem perguntar, robôs de busca disparam GETs a rodo — tudo porque *o combinado* é que GET não tem efeito colateral. (Se você um dia criar um endpoint `GET /deletar-tudo`, o protocolo não vai te impedir. Mas você terá quebrado um juramento, e a web vai te punir de formas criativas.)

## Idempotência: repetir não piora

Aqui, a estrela da lição. Analogia: o botão do elevador. Apertar cinco vezes não chama cinco elevadores — o estado final é o mesmo de apertar uma vez. Agora compare com o botão "comprar" de um site: clicar cinco vezes *pode* gerar cinco cobranças.

A definição precisa: um método é **idempotente** quando N requests idênticas deixam o servidor no mesmo estado que 1. Repare: é sobre o **estado do servidor**, não sobre as respostas serem iguais.

- **GET** — idempotente (nem toca no estado).
- **PUT** — idempotente: substituir pela mesma coisa duas vezes dá... a mesma coisa.
- **DELETE** — idempotente: deletado uma vez, deletado para sempre.
- **POST** — **NÃO**: cada POST cria de novo.

## Não acredite em mim: rode

O experimento 1 — POST duas vezes, o mesmo corpo:

```console
$ curl -s -X POST localhost:8000/reservas -H "Content-Type: application/json" \
    -d '{"quadra_id": 1, "quem": "ana"}'
{ "id": 1, "quadra_id": 1, "quem": "ana" }

$ curl -s -X POST localhost:8000/reservas -H "Content-Type: application/json" \
    -d '{"quadra_id": 1, "quem": "ana"}'
{ "id": 2, "quadra_id": 1, "quem": "ana" }
```

Duas reservas. A Ana vai pagar a quadra duas vezes. Requests idênticas, estado diferente a cada repetição — POST não é idempotente.

O experimento 2 — DELETE duas vezes, o mesmo id:

```console
$ curl -i -X DELETE localhost:8000/reservas/1
HTTP/1.1 204 No Content

$ curl -i -X DELETE localhost:8000/reservas/1
HTTP/1.1 404 Not Found
```

As *respostas* mudaram (204, depois 404) — mas o **estado** é o mesmo nos dois casos: reserva 1 não existe. Idempotente. Este exemplo derruba o mal-entendido mais comum sobre idempotência; se você entendeu por que o 404 não quebra a propriedade, entendeu a propriedade.

## Por que isso vai importar MUITO

Redes falham. Você manda uma request, a resposta não volta... e agora? A request se perdeu no caminho, ou *chegou, foi executada, e só a resposta se perdeu*? **Você não tem como saber.**

Se a request era um GET ou um DELETE — reenvie sem medo, é idempotente, o pior que acontece é um 404. Se era um POST... reenviar pode criar a coisa duas vezes. É exatamente o caso da Ana pagando a quadra em dobro.

Este fantasma tem capítulo marcado: quando formos construir retentativas automáticas e jobs em segundo plano (capítulos 8 e 9), idempotência deixa de ser trivia de protocolo e vira questão de dinheiro. O app de reservas que vamos construir vai sofrer disso na pele — de propósito.

## O que você deve conseguir fazer agora

- Classificar cada um dos cinco métodos: seguro? idempotente? nenhum dos dois?
- Explicar por que reenviar um DELETE perdido é tranquilo e reenviar um POST perdido é perigoso.
- Explicar por que o par 204/404 do experimento 2 **não** contraria a idempotência do DELETE.
- Dizer a diferença de intenção entre PUT e PATCH.