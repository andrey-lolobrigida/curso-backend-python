# Lição 02 — O lazy load que explode no async

A lição 01 terminou com uma pergunta. O objeto `Booking` sai do banco só com as colunas de `bookings`. O nome do usuário mora em outra tabela. Então, quando o Python lê `booking.user`, quem vai ao banco buscar o usuário? E quando?

A resposta curta: o SQLAlchemy vai, sozinho, na hora em que você lê o atributo. Isso tem nome: **lazy load**, carregamento preguiçoso. O ORM só busca o vizinho quando alguém pede por ele.

A resposta longa é esta lição. E ela começa com um experimento que dá errado.

## O experimento

A relação existe desde a lição 01. O `_to_out` ainda busca os nomes pelos repositories, com dois `SELECT` por reserva. Parece óbvio o que fazer: trocar as duas buscas pela relação.

```diff
     async def _to_out(self, booking: Booking) -> BookingOut:
-        user = await self.users.get(booking.user_id)
-        resource = await self.resources.get(booking.resource_id)
         return BookingOut(
             id=booking.id,
             user_id=booking.user_id,
             resource_id=booking.resource_id,
             starts_at=booking.starts_at,
             ends_at=booking.ends_at,
-            user_nome=user.nome,
-            resource_nome=resource.nome,
+            user_nome=booking.user.nome,
+            resource_nome=booking.resource.nome,
         )
```

**Essa troca não está no repositório.** Ela é o experimento desta lição. Fiz a mudança, rodei, e desfiz com `git checkout app/services/booking.py`. Se quiser ver com os seus olhos, faça o mesmo.

Com a troca no lugar, subi o uvicorn contra o banco de dev e criei uma reserva:

```console
$ curl -i -s -X POST localhost:8000/bookings -H 'Content-Type: application/json' \
    -d '{"user_id": 1, "resource_id": 1, "starts_at": "2035-01-01T10:00:00Z", "ends_at": "2035-01-01T12:00:00Z"}'
HTTP/1.1 201 Created
date: Mon, 12 Oct 2026 00:46:26 GMT
server: uvicorn
content-length: 159
content-type: application/json

{"id":1000673,"user_id":1,"resource_id":1,"starts_at":"2035-01-01T10:00:00Z","ends_at":"2035-01-01T12:00:00Z","user_nome":"Semente","resource_nome":"Quadra 1"}
```

**201.** Com `user_nome` e `resource_nome` preenchidos. A troca funcionou. *(O id é o do meu banco de dev. O seu vai ser outro. A reserva fica lá, e tudo bem: a lição 03 refaz o seed e ela some.)*

Agora, a lista. Com o banco de um milhão de reservas do capítulo 4, o 500 demora uns segundos para chegar: o repository carrega a lista inteira antes de o `_to_out` explodir na primeira.

```console
$ curl -i -s localhost:8000/bookings
HTTP/1.1 500 Internal Server Error
date: Mon, 12 Oct 2026 00:46:26 GMT
server: uvicorn
content-length: 21
content-type: text/plain; charset=utf-8

Internal Server Error
```

**500.** O mesmo `booking.user.nome`, no mesmo `_to_out`. Num endpoint funcionou, no outro explodiu.

O terminal do uvicorn conta o resto. Cortei o miolo do FastAPI e do Starlette e deixei o que importa, literal:

```console
INFO:     127.0.0.1:41414 - "POST /bookings HTTP/1.1" 201 Created
INFO:     127.0.0.1:41416 - "GET /bookings HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
(...)
  File "/home/andrey/PycharmProjects/python-backend-course/app/routers/bookings.py", line 29, in list_bookings
    return await BookingService(db).list_all()
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/andrey/PycharmProjects/python-backend-course/app/services/booking.py", line 66, in list_all
    return [await self._to_out(b) for b in await self.bookings.list_all()]
            ^^^^^^^^^^^^^^^^^^^^^
  File "/home/andrey/PycharmProjects/python-backend-course/app/services/booking.py", line 75, in _to_out
    user_nome=booking.user.nome,
              ^^^^^^^^^^^^
(...)
  File "/home/andrey/PycharmProjects/python-backend-course/.venv/lib/python3.12/site-packages/sqlalchemy/orm/strategies.py", line 1079, in _emit_lazyload
    return loading.load_on_pk_identity(
(...)
  File "/home/andrey/PycharmProjects/python-backend-course/.venv/lib/python3.12/site-packages/sqlalchemy/orm/loading.py", line 695, in load_on_pk_identity
    session.execute(
(...)
  File "/home/andrey/PycharmProjects/python-backend-course/.venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py", line 585, in execute
    self._adapt_connection.await_(
  File "/home/andrey/PycharmProjects/python-backend-course/.venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py", line 123, in await_only
    raise exc.MissingGreenlet(
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here. Was IO attempted in an unexpected place? (Background on this error at: https://sqlalche.me/e/20/xd2s)
```

Você já viu essa mensagem. Foi na lição 05 do capítulo 2, rodando o `bancada/lazy_load.py`. Ela chegou ao FairFare.

Leia a pilha de cima para baixo. A linha do nosso código é `user_nome=booking.user.nome`, e o `^^^^` aponta para `booking.user`. Um ponto. Logo abaixo, dentro do SQLAlchemy: `_emit_lazyload`, depois `session.execute`, depois `execute` no driver do asyncpg. O ponto virou um `SELECT`. É o lazy load trabalhando. E, no fim, o `await_only` recusa.

Duas perguntas. Por que o `GET` explode? E, mais estranho: por que o `POST` não explodiu?

## Por que o `POST` passou

Comece pela mais estranha.

Olhe o `create` do `BookingService`. Antes de gravar, ele confere se o usuário e o recurso existem:

```python
user = await self.users.get(data.user_id)
resource = await self.resources.get(data.resource_id)
```

Esses dois objetos não somem depois do uso. Eles ficam guardados na sessão.

Toda `Session` do SQLAlchemy tem um **identity map** (mapa de identidade). Pense num chaveiro de porteiro: cada chave tem uma etiqueta com o número do apartamento, e cada apartamento tem uma chave só. O rigor: é um dicionário, dentro da sessão, de "classe + chave primária" para "o objeto já carregado". Enquanto a sessão estiver viva, o `User` de id 1 é **um** objeto Python, sempre o mesmo, não importa quantas vezes você o busque.

Quando o `_to_out` leu `booking.user`, o lazy load fez a pergunta certa: "preciso do `User` de id `booking.user_id`". Antes de ir ao banco, ele olhou o mapa. O `User` de id 1 estava lá, deixado pelo `users.get` do `create`. Ele o entregou da memória. Nenhum SQL.

Como eu sei que não houve SQL? Pela própria resposta. Se o lazy load tivesse ido ao banco, teria batido no mesmo `await_only` e explodido com o mesmo `MissingGreenlet` do `GET`. Ele devolveu 201. Logo, não foi.

Tem um detalhe que segura isso de pé: o `expire_on_commit=False` do `SessionLocal`, da lição 07 do capítulo 2. Sem ele, o `commit` do `create` marcaria o `User` como expirado, e ler o `.nome` dele dispararia uma ida ao banco. O mesmo `MissingGreenlet`, por outro caminho.

Agora o `GET`. O `list_all` não busca usuário nenhum. Ele carrega as reservas, e só. O mapa só tem `Booking`. Quando o `_to_out` lê `booking.user`, não há nada na memória, e o lazy load precisa ir ao banco de verdade.

É isso que torna esse bug traiçoeiro. Ele passa justamente pelo caminho em que você mais testa, que é criar. E morre no caminho que você testa menos.

## Por que o `GET` explode

O lazy load é I/O escondido atrás de um acesso a atributo. `booking.user` parece ler um campo. Na verdade, pode disparar um `SELECT`.

No código síncrono, isso funciona. O Python para na linha, a consulta vai e volta, e a linha continua. É lento, mas funciona.

No async, não dá. Volte à lição 03 do capítulo 2: todo I/O precisa de um `await`, porque é o `await` que devolve o controle ao event loop enquanto o banco pensa. E um `.user` não tem onde pôr o `await`. Não existe `booking.await user`. Um acesso a atributo é uma chamada síncrona, ponto.

O SQLAlchemy tinha duas saídas. A primeira: fazer a consulta mesmo assim, travando o event loop até o banco responder. Isso congelaria todas as outras requisições do processo, exatamente o desastre da lição 04 do capítulo 2. A segunda: recusar. Ele recusa. É o `MissingGreenlet`.

E o nome esquisito? O SQLAlchemy async usa, por baixo, uma biblioteca chamada **greenlet**. Ela permite pausar uma função síncrona no meio e voltar ao event loop. Mas só funciona dentro de um contexto que o próprio SQLAlchemy abre, com o `greenlet_spawn`. Quando você chama `await db.scalars(...)`, ele abre esse contexto, roda o código síncrono do ORM lá dentro, e o I/O tem por onde voltar ao loop. Quando você lê `booking.user` direto, no meio do seu `async def`, ninguém abriu contexto nenhum. Daí a mensagem: `greenlet_spawn has not been called`. O I/O foi tentado num lugar inesperado.

Isso responde à pergunta que a lição 01 deixou pendurada. O script do porteiro rodava a leitura dentro de `db.run_sync(vizinhos)`. O `run_sync` é justamente o jeito de pedir ao SQLAlchemy: "abra o contexto e rode esta função síncrona lá dentro". Lá dentro, o lazy load tem para onde voltar, e funciona. Fora dele, explode.

A lição 05 do capítulo 2 terminava com uma promessa: quando as relações chegassem ao FairFare, a mensagem ia aparecer. A promessa era esta.

## O buraco nos testes

Rodei a suíte com a troca no lugar. Primeiro, só os dois testes que interessam aqui:

```console
$ uv run pytest -q tests/test_smoke.py::test_cria_reserva tests/test_smoke.py::test_lista_reservas_com_nomes 2>&1 | grep -E "MissingGreenlet|passed|failed"
>           raise exc.MissingGreenlet(
E           sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here. Was IO attempted in an unexpected place? (Background on this error at: https://sqlalche.me/e/20/xd2s)
.venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:123: MissingGreenlet
1 failed, 1 passed in 0.52s
```

O `test_cria_reserva` passa. O identity map salva o `POST` no teste também. Quem falha é o `test_lista_reservas_com_nomes`.

Esse teste é novo. Ele entra nesta lição. Antes dele, **nenhum teste listava uma reserva**. A suíte criava reservas, cancelava reservas, recusava reservas. O único `GET /bookings` da suíte, no `test_cancela_reserva_futura`, lista a tabela já vazia, depois do cancelamento. E lista vazia não toca em relação nenhuma: não há `booking` para ler o `.user`.

E a suíte inteira, com a troca no lugar:

```console
$ uv run pytest -q 2>&1 | grep -E "^FAILED|passed|failed"
FAILED tests/test_concorrencia.py::test_reservas_simultaneas_so_uma_passa - sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here. Was IO attempted in an unexpected place? (Background on this error at: ht...
FAILED tests/test_smoke.py::test_lista_reservas_com_nomes - sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here. Was IO attempted in an unexpected place? (Background on this error at: https://sqlalche.m...
2 failed, 29 passed in 1.92s
```

Dois. O teste novo e o `test_reservas_simultaneas_so_uma_passa`, do capítulo 4. Esse falha porque, no fim, ele chama `GET /bookings` para conferir que só uma reserva ficou. Sem o teste novo, ele seria o único a pegar o bug, de carona, num teste que existe para outra coisa.

Aqui está o teste, no fim do `tests/test_smoke.py`:

```python
async def test_lista_reservas_com_nomes(client):
    # Nenhum teste listava reservas: o bug da lição 02 passava pelo create e só morria aqui.
    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    await cria_reserva(
        client, user["id"], resource["id"], "2030-01-01T10:00:00Z", "2030-01-01T12:00:00Z"
    )
    resp = await client.get("/bookings")
    assert resp.status_code == 200
    [reserva] = resp.json()
    assert reserva["user_nome"] == "Ana"
    assert reserva["resource_nome"] == "Quadra 1"
```

O `[reserva] = resp.json()` desempacota a lista e, de quebra, confere que ela tem exatamente um item. Se vier vazia ou com dois, o Python reclama.

A lição de testes cabe numa frase: **o caminho que nenhum teste percorre é onde o bug mora.**

Sem a troca, que é o estado do repositório, a suíte fica assim:

```console
$ uv run pytest -q -W error
...............................                                          [100%]
31 passed in 1.25s
```

Trinta e um. Os trinta de antes, e o novo.

## "Então o lazy load é ruim?"

Depende de onde você está.

No código síncrono, ele funciona. E esconde o N+1. Cada `booking.user` e cada `booking.resource` é uma consulta silenciosa. Uma lista de 2000 reservas vira umas 4000 consultas sem que nenhuma linha do seu código pareça ir ao banco. É o 2N+1 do capítulo 4, só que invisível.

No async, ele nem funciona. Explode na primeira leitura que precisa de I/O.

Os dois problemas têm a mesma cura. Em vez de deixar o ORM adivinhar, na hora, o que buscar, **você diz o que carregar**, junto com a consulta principal. A consulta das reservas já leva o pedido dos usuários e dos recursos delas: uma consulta por relação, pedida de antemão, em vez de uma por reserva. Quando o `_to_out` ler `booking.user`, o objeto já está no identity map, de propósito, e não por sorte.

Isso é a lição 03.

## O que fica declarado

- **A troca no `_to_out` não está no repositório.** Foi o experimento desta lição, desfeito com `git checkout`. O `_to_out` continua buscando os nomes pelos repositories.
- **O `GET /bookings` continua com 2N+1 consultas.** Nada mudou no app. Morre na lição 03.
- **Só a suíte mudou:** ganhou o `test_lista_reservas_com_nomes`, e agora são 31 testes.

## O que você deve conseguir fazer agora

- Explicar por que o mesmo `booking.user` funciona no `POST /bookings` e explode no `GET /bookings`.
- Dizer o que é o identity map, e por que ele salvou o `POST`.
- Explicar por que o async proíbe o lazy load: onde ficaria o `await`, e o que o SQLAlchemy faz em vez de travar o event loop.
- Ler uma pilha de `MissingGreenlet` e achar a linha do seu código que tocou na relação.
