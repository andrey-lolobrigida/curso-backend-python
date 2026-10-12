# Lição 04 — Grupos e membros, o muitos-para-muitos

As três primeiras lições pagaram uma dívida. Esta começa o domínio novo: a divisão de despesas. E toda divisão começa com uma pergunta simples. Dividir **entre quem**?

Entre os membros de um grupo. A Ana viaja com o Bruno para um chalé. A mesma Ana joga bola com outra turma às quintas. O Bruno também está na turma da bola. Grupos de amigos se cruzam o tempo todo.

## O problema: ninguém tem uma coluna só

Um usuário está em vários grupos. Um grupo tem vários usuários. Isso tem nome: relação **muitos-para-muitos**.

Até aqui, toda relação do FairFare era de muitos-para-um. Cada reserva tem **um** usuário, então a reserva guarda um `user_id`, e pronto. Tente o mesmo truque aqui. *(As tabelas abaixo são ilustração. Não estão no repositório.)*

Primeira tentativa: o usuário guarda o grupo dele.

| users.id | users.nome | users.group_id |
|---|---|---|
| 2 | Ana | 1 |
| 3 | Bruno | 1 |

E a turma da bola, onde a Ana também está? A coluna `group_id` cabe **um** número. Ou a Ana sai do chalé, ou a turma da bola fica sem ela.

Segunda tentativa: o grupo guarda o usuário.

| groups.id | groups.nome | groups.user_id |
|---|---|---|
| 1 | Chalé | 2 |
| 1 | Chalé | 3 |

Agora o grupo 1 aparece duas vezes, com o nome repetido. Renomear o chalé vira renomear N linhas. E o `id` deixou de identificar o grupo, que era o único trabalho dele.

O defeito é o mesmo nas duas. O fato "a Ana é do Chalé" não pertence à Ana nem ao Chalé. Pertence ao **par**.

## A tabela de associação

Pense na lista de chamada de uma escola. O cadastro de alunos não diz em que turma cada um está. O cadastro de turmas não lista os alunos. A lista de chamada tem uma linha por fato: "fulano está nesta turma". Aluno em três turmas? Três linhas. Turma com trinta alunos? Trinta linhas.

No banco, isso é uma **tabela de associação**: uma tabela cujas linhas são pares. O FairFare ganha duas tabelas. A `groups` guarda o grupo, uma linha por grupo. A `group_members` guarda os pares:

```python
class GroupMember(Base):
    """Quem é de qual grupo. Uma classe, e não uma Table solta: a lição 11 tranca linhas dela."""

    __tablename__ = "group_members"

    # Chave composta: o par (grupo, usuário) é a identidade da linha, e não se repete.
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)

    user: Mapped[User] = relationship(lazy="raise")
```

Repare que não há coluna `id`. As **duas** colunas têm `primary_key=True`. Isso é uma **chave primária composta**: a identidade da linha é o par `(group_id, user_id)`, e não um número qualquer.

O efeito é direto. A chave primária não se repete, então o mesmo par não entra duas vezes. "A Ana está duas vezes no Chalé" deixa de ser um estado que o banco aceita guardar. No `psql`:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare -c 'INSERT INTO group_members (group_id, user_id) VALUES (1, 2);'
ERROR:  duplicate key value violates unique constraint "group_members_pkey"
DETAIL:  Key (group_id, user_id)=(1, 2) already exists.
```

*(Rodei isso depois de a Ana já ser membro do grupo 1. Está mais abaixo.)*

É o mesmo jogo da `EXCLUDE` do capítulo 4. A regra mora no banco. O código não verifica antes "ela já é membro?". Ele tenta inserir, e o banco diz não. Uma verificação no código teria a mesma janela de corrida que a reserva dupla teve: duas requests checam ao mesmo tempo, as duas ouvem "não é membro", as duas inserem. A chave primária fecha essa janela de graça.

O caminho até o `409`, de baixo para cima:

1. O Postgres recusa: `duplicate key value violates unique constraint "group_members_pkey"`.
2. O `commit()` do repository levanta `IntegrityError`. O repository desfaz a transação e levanta `MemberAlreadyExistsError`.
3. O service traduz para a exceção de domínio dele, `AlreadyMemberError`.
4. O router responde `409`.

Uma diferença em relação às reservas. Lá, o repository conferia o `sqlstate` (`23P01`) antes de concluir "é sobreposição". Aqui, ele trata qualquer `IntegrityError` como membro repetido. Funciona porque o service confere, **antes**, se o grupo e o usuário existem. Com as duas chaves estrangeiras já atendidas, a única violação que sobra é a da chave primária.

## Classe ou `Table`?

O SQLAlchemy tem um atalho para muitos-para-muitos. Você declara a associação como uma `Table` solta, sem classe, e liga os dois lados com `secondary=`. Ficaria mais ou menos assim *(pseudocódigo: não é o código do FairFare)*:

```python
# PSEUDOCÓDIGO — não está no repositório.
group_members = Table(
    "group_members",
    Base.metadata,
    Column("group_id", ForeignKey("groups.id"), primary_key=True),
    Column("user_id", ForeignKey("users.id"), primary_key=True),
)

class Group(Base):
    ...
    membros: Mapped[list[User]] = relationship(secondary=group_members)
```

Mais curto. `group.membros` já seria uma lista de `User`, sem degrau no meio. Por que o FairFare não usa?

Porque a linha de associação vai ganhar vida própria. Na lição 11, a quitação de dívidas vai **trancar linhas** de `group_members`, com `FOR UPDATE`, para que duas quitações não se atropelem. Com `secondary`, a linha de associação não existe como objeto no Python. Não há o que consultar, nem o que trancar, sem descer para SQL na mão. Com uma classe, `GroupMember` é uma entidade como qualquer outra.

A regra prática: se a associação é só "liga A a B", `secondary` serve. Se ela vai ter colunas próprias, ou ser consultada e trancada por conta própria, é classe.

O preço da classe é o degrau. `group.membros` é uma lista de `GroupMember`, e o nome do usuário está um passo adiante: `membro.user.nome`.

## A relação encadeada

Esse degrau tem consequência no carregamento. O `GET /groups/{id}` precisa do grupo, dos membros e do usuário de cada membro. São duas relações em sequência: `Group.membros`, e depois `GroupMember.user`.

As duas são `lazy="raise"`, como as do `Booking` desde a lição 03. Nada é carregado sem pedir. Então o repository pede as duas, encadeadas:

```python
async def get_with_members(self, group_id: int) -> Group | None:
    # Grupo, membros e usuários: três consultas, qualquer que seja o tamanho do grupo.
    stmt = (
        select(Group)
        .where(Group.id == group_id)
        .options(selectinload(Group.membros).selectinload(GroupMember.user))
    )
    return await self.db.scalar(stmt)
```

Leia o `.options(...)` como um caminho: "carregue os membros do grupo e, **a partir deles**, o usuário de cada um". O segundo `selectinload` é pendurado no primeiro, não colocado ao lado.

E se você esquecer o segundo degrau? Apaguei, temporariamente, o `.selectinload(GroupMember.user)`, deixando só `selectinload(Group.membros)`, e rodei o guardião desta lição:

```console
$ uv run pytest -q tests/test_grupos.py::test_buscar_grupo_nao_cresce_com_o_numero_de_membros 2>&1 | grep -E "Error|passed|failed"
>       raise sa_exc.InvalidRequestError(
E       sqlalchemy.exc.InvalidRequestError: 'GroupMember.user' is not available due to lazy='raise'
.venv/lib/python3.12/site-packages/sqlalchemy/orm/strategies.py:867: InvalidRequestError
1 failed in 0.44s
```

Os membros vieram. O usuário de cada um, não. Sem o `lazy="raise"`, o lazy load iria buscar cada usuário na hora: no async, um `MissingGreenlet`; num código síncrono, um N+1 silencioso. Com ele, é um erro que diz o nome da relação esquecida.

Com o caminho completo, capturei o SQL num script de rascunho com `echo=True`, no grupo de dois membros que você vai ver logo abaixo (linhas de log aparadas):

```sql
SELECT groups.id, groups.nome
FROM groups
WHERE groups.id = $1::INTEGER

SELECT group_members.group_id AS group_members_group_id, group_members.user_id AS group_members_user_id
FROM group_members
WHERE group_members.group_id IN ($1::INTEGER) ORDER BY group_members.user_id

SELECT users.id AS users_id, users.nome AS users_nome, users.email AS users_email
FROM users
WHERE users.id IN ($1::INTEGER, $2::INTEGER)
```

Três consultas: uma por nível do caminho. O `ORDER BY` da segunda vem do model, `relationship(lazy="raise", order_by="GroupMember.user_id")`. Os membros saem em ordem de `user_id`, e não na ordem em que entraram. A ordem é estável, a mesma a cada request. A regra do centavo da lição 07 fala justamente em "menores `user_id`".

O guardião é o mesmo da lição 03, agora para grupos:

```python
async def test_buscar_grupo_nao_cresce_com_o_numero_de_membros(client, engine_de_teste):
    grupo = await cria_grupo(client)
    for i in range(5):
        user = await cria_usuario(client, email=f"m{i}@example.com")
        await adiciona_membro(client, grupo["id"], user["id"])
    with conta_consultas(engine_de_teste) as contagem:
        resp = await client.get(f"/groups/{grupo['id']}")
    assert len(resp.json()["membros"]) == 5
    assert contagem["n"] == 3  # grupo, membros, usuários
```

Cinco membros, três consultas. Quinhentos membros, três consultas.

## O diff, camada por camada

Como no capítulo 1, cada camada ganha o seu pedaço.

**Model** (`app/models/group.py`). O `GroupMember` está lá em cima. O `Group` é curto:

```python
class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]

    # Um-para-muitos: um grupo, várias linhas de associação.
    membros: Mapped[list["GroupMember"]] = relationship(
        lazy="raise", order_by="GroupMember.user_id"
    )
```

Repare no comentário. Do ponto de vista do `Group`, `membros` é um-para-muitos: um grupo, várias linhas de `group_members`. O muitos-para-muitos é a soma de dois desses, um de cada lado da tabela do meio.

**Migração** (`alembic revision --autogenerate -m "grupos e membros"`). Desta vez o autogenerate acertou tudo sozinho: duas tabelas, as duas chaves estrangeiras e a chave composta.

```python
op.create_table(
    "group_members",
    sa.Column("group_id", sa.Integer(), nullable=False),
    sa.Column("user_id", sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(
        ["group_id"],
        ["groups.id"],
    ),
    sa.ForeignKeyConstraint(
        ["user_id"],
        ["users.id"],
    ),
    sa.PrimaryKeyConstraint("group_id", "user_id"),
)
```

`upgrade head`, `downgrade -1` e `upgrade head` de novo, no banco de dev, e depois `uv run alembic check`: `No new upgrade operations detected.`

**Schemas** (`app/schemas/group.py`): `GroupCreate(nome)`, `MemberAdd(user_id)`, `MemberOut(user_id, nome)` e `GroupOut(id, nome, membros: list[MemberOut])`. A resposta achata o degrau: o cliente vê `user_id` e `nome`, e nunca fica sabendo que existe um `GroupMember`.

**Repository** (`app/repositories/group.py`): `create`, `exists`, `get_with_members`, `add_member` e `member_ids`. O `member_ids` ainda não tem quem o chame. Ele espera a lição 08, que vai conferir se os participantes de uma despesa são do grupo. Como os outros repositories, este ainda comita sozinho. A lição 08 muda isso.

**Service** (`app/services/group.py`): confere grupo e usuário, chama o repository e traduz as exceções. Um detalhe no `create`:

```python
async def create(self, data: GroupCreate) -> GroupOut:
    group = await self.groups.create(data.nome)
    return GroupOut(id=group.id, nome=group.nome, membros=[])
```

Por que `membros=[]` escrito à mão, se o grupo acabou de nascer vazio? Porque o repository faz `refresh(group)` depois do commit, e o `refresh` relê **colunas**. É a armadilha da lição 03, do outro lado. Testei num script de rascunho: ler `group.membros` logo depois do `create` dá `'Group.membros' is not available due to lazy='raise'`. Um grupo recém-criado não tem membros, e o service sabe disso sem perguntar ao banco.

**Router** (`app/routers/groups.py`): três rotas. `POST /groups` (201), `GET /groups/{group_id}` (200 ou 404) e `POST /groups/{group_id}/members` (201, 404 para grupo ou usuário que não existe, 409 para membro repetido). O `app/main.py` ganha o `include_router(groups.router)`.

**Testes** (`tests/test_grupos.py`): cinco testes. Com eles, a suíte vai a **37 passed**. O `TRUNCATE` do `conftest.py` ganhou `groups` e `group_members`.

## Pelo uvicorn

No banco de dev, com o FairFare de pé. Os ids de usuário são 2 e 3 porque o seed da lição 03 já tinha criado o usuário 1. Os seus podem ser outros.

```console
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/users -H 'content-type: application/json' -d '{"nome": "Ana", "email": "ana@fairfare.dev"}'
{"id":2,"nome":"Ana","email":"ana@fairfare.dev"}
201
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/users -H 'content-type: application/json' -d '{"nome": "Bruno", "email": "bruno@fairfare.dev"}'
{"id":3,"nome":"Bruno","email":"bruno@fairfare.dev"}
201
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/groups -H 'content-type: application/json' -d '{"nome": "Chalé em Monte Verde"}'
{"id":1,"nome":"Chalé em Monte Verde","membros":[]}
201
```

O Bruno entra primeiro, a Ana depois. E a Ana tenta entrar de novo:

```console
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/groups/1/members -H 'content-type: application/json' -d '{"user_id":3}'
{"user_id":3,"nome":"Bruno"}
201
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/groups/1/members -H 'content-type: application/json' -d '{"user_id":2}'
{"user_id":2,"nome":"Ana"}
201
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/groups/1/members -H 'content-type: application/json' -d '{"user_id":2}'
{"detail":"usuário já é membro do grupo"}
409
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/groups/1/members -H 'content-type: application/json' -d '{"user_id":999}'
{"detail":"usuário não existe"}
404
$ curl -s -w '\n%{http_code}\n' localhost:8000/groups/1
{"id":1,"nome":"Chalé em Monte Verde","membros":[{"user_id":2,"nome":"Ana"},{"user_id":3,"nome":"Bruno"}]}
200
```

A Ana vem antes do Bruno, mesmo tendo chegado depois. No banco, a ordem é a de chegada:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare -c 'SELECT * FROM group_members;'
 group_id | user_id 
----------+---------
        1 |       3
        1 |       2
(2 rows)
```

Uma tabela não tem ordem garantida. Quem ordena é o `ORDER BY`, e quem pede o `ORDER BY` é o `order_by` do model.

E a tabela, descrita pelo próprio Postgres:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare -c '\d group_members'
            Table "public.group_members"
  Column  |  Type   | Collation | Nullable | Default 
----------+---------+-----------+----------+---------
 group_id | integer |           | not null | 
 user_id  | integer |           | not null | 
Indexes:
    "group_members_pkey" PRIMARY KEY, btree (group_id, user_id)
Foreign-key constraints:
    "group_members_group_id_fkey" FOREIGN KEY (group_id) REFERENCES groups(id)
    "group_members_user_id_fkey" FOREIGN KEY (user_id) REFERENCES users(id)
```

Lá está: `PRIMARY KEY, btree (group_id, user_id)`. É o índice que disse não ao segundo `POST` da Ana.

## O que fica declarado

- **Qualquer um adiciona qualquer um a qualquer grupo.** Não há login, então não há como perguntar "quem está pedindo, e ele é do grupo?". Permissões chegam no capítulo 6.
- **Ninguém sai do grupo.** Não existe `DELETE /groups/{id}/members/{user_id}`. É escolha, não esquecimento: sair de um grupo com dívida em aberto é um problema de domínio que este capítulo não precisa resolver para ensinar o que ensina.
- **`GET /groups`, sem id, não existe.** Nenhuma lição precisa listar todos os grupos.
- **O experimento do `selectinload` sem o segundo degrau não está no repositório.** Foi desfeito. Os scripts de rascunho do `refresh` e do `echo=True` também não.
- **O banco de dev ficou com a Ana (2), o Bruno (3) e o grupo 1.** Se você seguiu junto, o seu também.

## O que você deve conseguir fazer agora

- Modelar um muitos-para-muitos com uma tabela de associação e chave primária composta, e explicar por que nem `users.group_id` nem `groups.user_id` resolvem.
- Dizer de onde vem o `409` do membro repetido, camada por camada, começando no Postgres.
- Escolher entre uma classe de associação e uma `Table` com `secondary=`, e justificar.
- Carregar uma relação encadeada com `selectinload(...).selectinload(...)`, sem N+1, e provar isso com um teste que conta consultas.
