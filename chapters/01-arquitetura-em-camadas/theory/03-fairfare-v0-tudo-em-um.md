# Lição 03 — Nasce o FairFare: v0, tudo-em-um

## O produto, enfim

Chega de servidor de quadras genérico. A partir de agora, todo código deste curso pertence a um único app: o **FairFare**.

A ideia: grupos de amigos reservam recursos compartilhados — a quadra do condomínio, o chalé da serra, a sala de ensaio — e racham os custos entre os membros. Reserva + divisão justa da conta. *Fair fare.*

Essa é a visão completa. O que nasce **hoje** é bem menos que isso: um cadastro de usuários. Três rotas. Nem banco de dados tem. E é assim de propósito: cada capítulo adiciona ao FairFare apenas o que precisa para ensinar a sua lição. O app cresce porque você está aprendendo, não apesar disso.

## O código inteiro (sim, inteiro)

Este é o `app/main.py` deste commit — o FairFare v0, completo:

```python
from fastapi import FastAPI, HTTPException

app = FastAPI(title="FairFare")

users: dict[int, dict] = {}
_next_id = 1


@app.post("/users", status_code=201)
def create_user(user: dict):
    global _next_id
    user = {"id": _next_id, **user}
    users[_next_id] = user
    _next_id += 1
    return user


@app.get("/users")
def list_users():
    return list(users.values())


@app.get("/users/{user_id}")
def get_user(user_id: int):
    if user_id not in users:
        raise HTTPException(status_code=404, detail="usuário não existe")
    return users[user_id]
```

Suba-o (e deixe rodando durante a lição):

```bash
uv run uvicorn app.main:app --reload
```

O **uvicorn** é o servidor que fica escutando a porta e entregando requests ao nosso app — o papel que o `http.server` fazia no capítulo 0. O `--reload` reinicia o servidor a cada arquivo salvo: conveniência de desenvolvimento. E `app.main:app` significa "no módulo `app/main.py`, use a variável `app`".

## Tour linha a linha

**`app = FastAPI(title="FairFare")`** — cria a aplicação. Tudo o mais se pendura nela.

**`@app.post("/users", ...)` e `@app.get("/users")`** — os decorators de rota. Lembra da cadeia de `if/else` do `server.py` do capítulo 0, decidindo o que fazer para cada caminho e método? É isso que eles substituem. Cada decorator registra na tabela de rotas: "quando chegar um POST em `/users`, chame esta função". O framework faz o despacho; você escreve só o miolo.

**`def get_user(user_id: int)`** — olhe o caminho da rota: `/users/{user_id}`. O pedaço entre chaves é um **path parameter**, e ele chega à função como argumento. O type hint `int` não é decoração: peça `GET /users/abc` e o FastAPI responde `422` sozinho, porque `abc` não vira `int`. Primeiro sinal dos tipos trabalhando.

**`raise HTTPException(status_code=404, ...)`** — o 404 do capítulo 0, agora visto do outro lado do balcão. Lá você *recebia* o status code; aqui você *decide* quando devolvê-lo. Levantar a exceção interrompe a função e vira uma response de erro com o corpo JSON `{"detail": "..."}`.

**`status_code=201`** — POST que cria algo responde `201 Created`, não `200` (lição 05 do capítulo 0). O FastAPI devolve `200` por padrão; aqui declaramos a intenção correta.

## `/docs` de graça

Com o servidor no ar, abra [http://localhost:8000/docs](http://localhost:8000/docs).

Isso é documentação interativa da sua API — cada rota, seus parâmetros, e um botão "Try it out" que dispara requests de verdade. Você não escreveu uma linha dela: o FastAPI gerou tudo a partir das rotas e dos tipos declarados (o formato por trás chama-se OpenAPI, um padrão da indústria). É o primeiro pagamento concreto dos type hints — e ainda está magro, porque nossos tipos ainda dizem pouco. Repare como a documentação do corpo do POST está vaga. Guarde essa observação.

## Os dois experimentos que doem

Não leia esta seção — **execute-a**. A dor é o material da próxima lição.

**Experimento 1: o servidor aceita qualquer coisa.** Crie um usuário legítimo e depois um absurdo:

```console
$ curl -s -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{"nome": "Ana", "email": "ana@example.com"}'
{"id":1,"nome":"Ana","email":"ana@example.com"}
$ curl -s -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{"nome": 42}'
{"id":2,"nome":42}
```

`201 Created`. Nome numérico, sem email, e o FairFare disse "bem-vindo". O culpado está na assinatura: `user: dict`. Um `dict` como corpo de request é uma promessa vazia — diz "me mande JSON" sem dizer *qual* JSON. O servidor engole qualquer coisa e o problema explode depois, longe daqui, quando algum código tentar usar `user["email"]` de um usuário que nunca teve email.

**Experimento 2: o servidor tem amnésia.** Derrube o servidor (Ctrl+C), suba de novo, e liste:

```console
$ curl -s localhost:8000/users
[]
```

Ana morreu com o processo. Óbvio em retrospecto — `users` é um dicionário na memória do processo — mas sinta o tamanho do problema: *qualquer* deploy, *qualquer* crash, *qualquer* reinício apaga o cadastro inteiro.

Duas dores, duas curas: a lição 04 resolve a porta escancarada; a lição 05, a amnésia.

## O que você deve conseguir fazer agora

- Subir o FairFare com `uv run uvicorn app.main:app --reload`.
- Criar, listar e buscar usuários pelo `curl` **e** pelo `/docs`.
- Apontar, no código, quem substitui o `if/else` de rotas do capítulo 0.
- Explicar por que `user: dict` é uma promessa vazia — e qual das duas dores ela causa.
