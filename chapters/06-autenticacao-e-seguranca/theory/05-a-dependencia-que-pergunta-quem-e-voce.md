# Lição 05 — A dependência que pergunta quem é você

A lição 04 entregou o crachá, mas nenhuma rota pedia por ele. Esta lição põe o porteiro para trabalhar. Todas as rotas passam a perguntar "quem é você?", exceto as duas que existem para quem ainda não tem crachá: o cadastro e o login.

## Uma pergunta, um lugar

São quinze rotas protegidas. Escrever em cada uma "leia o header, calcule o hash, busque a sessão, responda 401 se não achar" seria pedir para esquecer em alguma.

O FastAPI já tem o lugar certo para isso, e você conhece ele desde a lição 06 do capítulo 1: a **dependência**. Lá, cada rota declarava `db: Session = Depends(get_db)` (o `AsyncSession` veio no capítulo 2) e o FastAPI providenciava a sessão. Aqui é igual. Uma função, declarada uma vez, pedida por quem precisa. Ela mora num arquivo novo, `app/dependencies.py`:

```python
# Lê o "Authorization: Bearer <token>" e confere o formato. Sem header, ou com outro
# esquema, responde 401 "Not authenticated" sozinho. Se o token vale, não é com ele.
bearer = HTTPBearer()


async def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    # A dependência e o service dividem a mesma sessão. Sem este begin(), a consulta abriria
    # a transação sozinha (autobegin), e o begin() do service estouraria logo depois.
    # Assim ela abre e fecha a própria transação de leitura, e o service segue dono da dele.
    # O User continua legível depois do commit: expire_on_commit=False.
    async with db.begin():
        user = await SessionRepository(db).user_by_token_hash(hash_token(cred.credentials))
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="token inválido ou vencido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
```

Repare: uma dependência pode ter dependências. O `get_current_user` pede o `bearer` e o `get_db`, e o FastAPI resolve a árvore antes de chamar a rota.

E como a rota pede? Em `resources`, `bookings` e `groups`, o router inteiro pede. O do `resources.py`:

```python
# Login exigido no router inteiro: rota nova que nascer aqui já nasce protegida.
router = APIRouter(
    prefix="/resources", tags=["resources"], dependencies=[Depends(get_current_user)]
)
```

O ganho é o padrão seguro: quem criar uma rota nova nesse arquivo não precisa lembrar de nada. No `users.py` não dá para fazer isso, porque o `POST /users` é público. Lá ela vai rota a rota, no decorador: `@router.get("", ..., dependencies=[Depends(get_current_user)])`.

A rota que precisa do usuário pede também como parâmetro: `user: User = Depends(get_current_user)`. Pedir duas vezes não consulta duas vezes: o FastAPI guarda o resultado de cada dependência durante a request (o **cache de dependências**). Conferi no `POST /bookings`: uma consulta à tabela `sessions`.

## O `HTTPBearer`, e os dois 401

O `HTTPBearer`, do FastAPI, faz uma coisa só: lê o header `Authorization` e confere se ele tem a forma `Bearer <alguma coisa>`. Se não tiver, ele mesmo responde. Pelo uvicorn, no banco de dev:

```console
$ curl -i localhost:8000/bookings
HTTP/1.1 401 Unauthorized
date: Sun, 25 Oct 2026 02:19:12 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 30
content-type: application/json

{"detail":"Not authenticated"}
```

O que o `HTTPBearer` **não** faz é saber se o token vale. Para ele, `Bearer lixo` tem a forma certa. Quem descobre que é lixo é o `get_current_user`, ao não achar sessão nenhuma:

```console
$ curl -i localhost:8000/bookings -H 'Authorization: Bearer lixo'
HTTP/1.1 401 Unauthorized
date: Sun, 25 Oct 2026 02:19:12 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 39
content-type: application/json

{"detail":"token inválido ou vencido"}
```

Dois 401, duas mensagens. O primeiro é "você não mostrou crachá". O segundo é "esse crachá é falso, ou venceu". Os dois levam o `www-authenticate: Bearer`, pela regra da lição 01: todo 401 diz como se apresentar.

E o crachá mal escrito? `Basic abc`, `Token xyz`, `Bearer` sozinho, `Bearer ` com um espaço e nada depois. Todos caem no primeiro caso: 401, `Not authenticated`, com o header. O espaço do `Bearer ` chega intacto, e o servidor recusa igual. O `test_authorization_mal_formado_e_401` trava os quatro: nunca 500, nunca 422. Já `bearer` com minúscula funciona: o nome do esquema não diferencia maiúsculas (RFC 9110).

Agora com crachá. Cadastrei a Gabi, usuária nova desta demo, e fiz o login dela como na lição 04. Com o token dela, a rota nova `GET /users/me` responde quem você é:

```console
$ curl -s localhost:8000/users/me -H 'Authorization: Bearer SDYh0yoD3AyNVjvhquHc6ltxc6MvZDQDL6kz2_5QDFU'
{"id":270,"nome":"Gabi","email":"gabi.cap06@example.com"}
```

É o `UserMeOut` da lição 03, o único schema que mostra o email. A rota é declarada **antes** de `GET /users/{user_id}`. As rotas casam na ordem em que foram declaradas, e na ordem contrária o `"me"` viraria um `user_id` que não é inteiro: 422.

## A consulta

O token chega, o `hash_token` calcula o sha256 dele, e o `SessionRepository` ganha um método:

```python
    async def user_by_token_hash(self, token_hash: str) -> User | None:
        # Uma ida ao banco: o usuário dono de uma sessão com esse hash e ainda na validade.
        # O "agora" é o now() do banco, não o relógio do Python: um relógio só decide.
        stmt = (
            select(User)
            .join(UserSession, UserSession.user_id == User.id)
            .where(UserSession.token_hash == token_hash, UserSession.expira_em > func.now())
        )
        return await self.db.scalar(stmt)
```

O SQL que sai dali, capturado no caminho para o banco:

```sql
SELECT users.id, users.nome, users.email, users.senha_hash
FROM users JOIN sessions ON sessions.user_id = users.id
WHERE sessions.token_hash = $1::VARCHAR AND sessions.expira_em > now()
```

Uma ida ao banco, e não duas ("ache a sessão" e depois "ache o usuário"). O `token_hash` usa o índice da constraint `unique` da lição 04. E o vencimento já entra aqui, no `WHERE`. Sessão vencida não é achada, e cai no mesmo "token inválido ou vencido".

Por que o `now()` do banco, e não `datetime.now(UTC)`? Com o app em várias máquinas (a lição 11 do capítulo 3 subiu vários processos, e um deploy de verdade os espalha por máquinas), cada máquina tem o seu relógio, e eles nunca batem cravado. O banco é um só. Mas o `expira_em` saiu do relógio do app que fez o login (lição 04): se esse relógio e o do banco discordam, a janela se desloca pela diferença. O `now()` do banco garante outra coisa: todos os processos decidem igual.

## O autobegin, de novo

A primeira versão da dependência não tinha o `async with db.begin():`. Rodei o teste da reserva, e o primeiro a estourar foi o `POST /resources`, que cria a quadra do teste: o `begin()` do router (`app/routers/resources.py:18`). Com a quadra já no banco, o `POST /bookings` estoura no `begin()` do service:

```console
app/routers/bookings.py:28: in create_booking
    return await BookingService(db).create(data, user)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/services/booking.py:34: in create
    async with self.db.begin():
               ^^^^^^^^^^^^^^^
...
E   sqlalchemy.exc.InvalidRequestError: A transaction is already begun on this Session.
```

É a pegadinha da lição 08 do capítulo 5. A dependência e o service pedem `Depends(get_db)`, e o FastAPI entrega **a mesma** sessão para os dois: é o cache de dependências, que guarda o resultado do `get_db` durante a request. A consulta da dependência foi a primeira a ir ao banco, e o autobegin abriu uma transação sozinho. Quando o `begin()` do service chegou, a sessão se recusou a abrir outra por cima.

O conserto é uma linha: a dependência abre e fecha a **própria** transação de leitura. Ela termina antes de a rota começar. O service chega numa sessão sem transação, e continua dono da dele, como a lição 08 do capítulo 5 decidiu. O `User` que a dependência devolveu continua legível depois do commit, graças ao `expire_on_commit=False`.

Duas saídas que parecem mais simples, e não servem:

- **Ler e dar `rollback()`.** Fecha a transação, mas o rollback expira os objetos da sessão, e o `expire_on_commit=False` só vale para commit. Testei: o `user.id` no service foi ao banco por fora do `await` e estourou o `MissingGreenlet` da lição 02 do capítulo 5.
- **Uma sessão só para a dependência**, aberta com o `SessionLocal`. Fugiria do `dependency_overrides[get_db]` dos testes, e a autenticação cairia no banco de dev, o erro da lição 03 do capítulo 4.

## O `user_id` saiu do corpo

Antes, o cliente dizia quem estava reservando. Agora quem diz é o token:

```diff
 class BookingCreate(BaseModel):
-    user_id: int
+    # Sem user_id: quem reserva é quem está logado (lição 05 do cap. 6). Um user_id que
+    # ainda chegue no corpo é descartado, como todo campo que o schema não declara.
     resource_id: int
```

O `BookingService.create(data, user)` recebe o usuário pronto e não precisa mais procurá-lo. O `RelatedNotFoundError` passa a querer dizer só "recurso não existe", e é essa a mensagem do 404.

E o cliente antigo, que ainda manda `user_id`? Ele não leva 422. O Pydantic descarta o campo que o schema não declara, e a identidade vem do token. Mandei como a Gabi, dizendo ser o usuário 1:

```console
$ curl -s -X POST localhost:8000/bookings -H 'Authorization: Bearer SDYh0yoD3AyNVjvhquHc6ltxc6MvZDQDL6kz2_5QDFU' -H 'Content-Type: application/json' -d '{"user_id": 1, "resource_id": 51, "starts_at": "2030-03-01T10:00:00Z", "ends_at": "2030-03-01T12:00:00Z"}'
{"id":2001,"user_id":270,"resource_id":51,"starts_at":"2030-03-01T10:00:00Z","ends_at":"2030-03-01T12:00:00Z","user_nome":"Gabi","resource_nome":"Quadra da Gabi"}
```

A reserva é da Gabi (270). Ignorar, e não recusar, é escolha: o cliente desatualizado continua funcionando, e o campo perdeu todo o poder. O `test_user_id_no_corpo_e_ignorado` trava isso. Antes desta lição, ele falhava com `assert 1 == 2`: a reserva ia para o Bruno.

## O Swagger aprende a mostrar o crachá

Abra `localhost:8000/docs`. Apareceu um botão **Authorize** no topo, e um cadeado em cada rota protegida. O `HTTPBearer` se anuncia no OpenAPI como `{'HTTPBearer': {'type': 'http', 'scheme': 'bearer'}}`, e o Swagger lê isso. No `openapi.json`, quinze rotas pedem `HTTPBearer`; só `POST /users` e `POST /auth/login`, nada.

Para testar à mão: faça o login pelo próprio Swagger, copie o `access_token`, clique em Authorize e cole só o token, sem a palavra `Bearer`. Daí em diante, o Swagger põe o header em toda request.

## O diff dos testes

O maior diff do capítulo: `12 files changed, 422 insertions(+), 237 deletions(-)` só em `tests/`. Quase todo teste fazia request anônima.

O `tests/conftest.py` ganhou uma fábrica de pessoas:

```python
    async def nova(nome: str = "Ana", email: str | None = None) -> Pessoa:
        email = email or f"{nome.lower()}@example.com"
        ip = f"10.0.0.{len(clientes) + 1}"
        transport = ASGITransport(app=fastapi_app, client=(ip, 123))
        cliente = AsyncClient(transport=transport, base_url="http://test")
        clientes.append(cliente)
        dados = await cria_usuario(cliente, email=email, nome=nome)
        token = await faz_login(cliente, email)
        cliente.headers["Authorization"] = f"Bearer {token}"
        return Pessoa(id=dados["id"], nome=dados["nome"], email=dados["email"], client=cliente)
```

O teste escreve `ana = await pessoa("Ana")` e recebe alguém cadastrado, logado, com o crachá já no header. Os helpers do `tests/apoio.py` passam a receber o client de quem age: `cria_reserva(ana.client, ...)`.

Por que cada pessoa tem o **próprio** cliente, com IP próprio? Por causa do rate limiter da lição 05 do capítulo 3. Antes, todo teste usava um cliente só, no `127.0.0.1`. Agora cada pessoa gasta duas fichas só para existir (cadastro e login). O teste das quitações em direções opostas, com três pessoas, faz 21 requests. O balde tem 20.

Rodei esse teste com todas as pessoas num IP só, e ele passou: sobrou 1,52 ficha no balde. Cada cadastro e cada login gastam uns 55 ms de argon2, e nesse tempo o balde goteja de volta. Num ensaio antes do capítulo, o mesmo tipo de teste levou 429. É o pior tipo de teste: passa ou falha conforme a CPU.

Subir o limite só nos testes seria gambiarra. Criar a sessão direto no banco fugiria do "como um cliente faria". Um IP por pessoa é o que acontece na vida real: gente diferente, máquina diferente, balde diferente. Uma pessoa, um cliente, um IP.

O `client` anônimo continua lá, para o que é anônimo de verdade: os testes de 401, o cadastro, o login. E o `test_429_atravessa_o_cors` continua anônimo de propósito. As primeiras 20 requests dele agora levam 401, e as outras, 429. O limitador fica antes da rota e gasta a ficha mesmo assim. Crachá ausente não poupa balde.

E um guardião novo, de rotas. O `test_toda_rota_exige_login_menos_as_publicas` percorre todas as rotas do esquema OpenAPI (o do Swagger) e exige 401 com `WWW-Authenticate: Bearer` de cada uma, sem token, menos as duas públicas, numa lista explícita. Tirei o `dependencies=` do `GET /users/{user_id}` para ver se ele morde: vermelho, com `('GET', '/users/{user_id}', 404)`. A rota respondia a qualquer um.

E três testes ficaram vermelhos por um bom motivo. Os guardiões de consultas do capítulo 5:

```diff
     # Uma para as reservas, uma para os usuários, uma para os recursos. Com 5 ou 5000.
-    assert contagem["n"] == 3
+    # +1: a consulta que pergunta quem é você (lição 05 do cap. 6).
+    assert contagem["n"] == 4
```

`GET /bookings` foi de 3 para 4. `GET /groups/{id}`, de 3 para 4. Os saldos, de 2 para 3. A mudança é a boa: subiu **um**, constante, sem depender de quantas reservas ou membros existem. Um N+1 cresceria com o N. Este é só o porteiro.

A suíte foi de 93 para 105 testes, e os de concorrência passaram 10 de 10 rodadas com a autenticação na frente.

## O que fica declarado

- **O app agora é autenticado, mas não autorizado.** Ele sabe quem você é. Ainda não pergunta o que você pode. Qualquer pessoa logada lança uma despesa "paga" por outra (o `paid_by` ainda vem do corpo), lança uma quitação em nome de outra (o `para_user_id` também), adiciona quem quiser a qualquer grupo e cancela a reserva de outra pessoa. É a distinção da lição 01 vista no código. A reserva alheia é a lição 11. Os grupos, a lição 12.
- **Ainda não há logout, e a expiração não foi provada.** O `expira_em` já é conferido na consulta, mas só a lição 07 prova isso com um teste, e traz o logout.
- **As bancadas antigas que chamam a API quebraram.** Elas fazem requests sem crachá e agora levam 401. Não foram reescritas: cada uma roda na tag do capítulo dela. A ERRATA explica, no fim do capítulo.

## O que você deve conseguir fazer agora

- Escrever uma rota nova protegida, e dizer por que, num router com `dependencies=[Depends(get_current_user)]`, ela já nasce protegida.
- Explicar os dois 401: quem responde cada um, o que cada mensagem quer dizer e por que os dois levam `WWW-Authenticate: Bearer`.
- Explicar por que a dependência abre a própria transação, e por que ler e dar `rollback()` não serve no lugar.
- Dizer por que o vencimento da sessão é conferido pelo `now()` do banco.
- Explicar por que cada pessoa dos testes tem o próprio cliente, com IP próprio.
