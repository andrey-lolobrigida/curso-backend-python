# Lição 03 — O N+1 morre

A lição 02 terminou com a cura anunciada: em vez de deixar o ORM adivinhar, na hora, o que buscar, você diz o que carregar junto com a consulta principal. Esta lição aplica a cura. Mas, antes de consertar, vamos medir. Conserto sem medição é palpite.

## O antes, medido pelo endpoint

A bancada deste capítulo ganhou um script, `bancada/conta_consultas.py`. Ele sobe o FairFare **dentro do próprio processo**, sem uvicorn: o `httpx2` fala com o app pelo `ASGITransport`, o mesmo truque do `client` dos testes. Por estar no mesmo processo, o script consegue pendurar um contador na engine do app e contar cada comando SQL que passa por ela durante um `GET /bookings`.

O contador mora em `tests/apoio.py`, e é curto:

```python
@contextmanager
def conta_consultas(engine):
    """Conta os comandos SQL que passam pela engine dentro do bloco (lição 03)."""
    contagem = {"n": 0}

    def conta(*args):
        contagem["n"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", conta)
    try:
        yield contagem
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", conta)
```

O `event.listen` é um gancho do SQLAlchemy: "antes de mandar qualquer comando ao driver, chame esta função". A função soma um. O `with` liga o gancho na entrada e desliga na saída.

Para ter volume, rodei o `seed.sql` do capítulo 4 com 2000 reservas. Ele **apaga** os dados do banco de dev, e o `bancada/README.md` avisa isso. Depois, o script, três vezes, no código da lição 02.

**Para ver o "antes" na sua máquina:** o script nasce neste commit, então ele não existe no checkout da lição 02. Traga de volta só os três arquivos do app que esta lição conserta, rode, e devolva-os depois:

```console
$ git checkout v-cap05-licao02 -- app/models/booking.py app/repositories/booking.py app/services/booking.py
$ # ... rode o script e o teste ...
$ git checkout HEAD -- app/
```

Com os três arquivos da lição 02 no lugar:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare -v linhas=2000 \
    < chapters/04-o-banco-de-dados-de-verdade/bancada/seed.sql
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py
reservas=2000 consultas=4001 tempo=999ms
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py
reservas=2000 consultas=4001 tempo=997ms
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py
reservas=2000 consultas=4001 tempo=1017ms
```

**4001.** Uma para a lista, duas por reserva. É o 2N+1, exato. (A lição 01 citou 4005 porque o banco do capítulo 4 tinha 2002 reservas; o seed daqui tem 2000.) Um segundo para devolver uma lista.

Espera aí. O seed tem **um** usuário só. A lição 02 mostrou o identity map: a sessão guarda o `User` de id 1 e devolve o mesmo objeto da memória, sem SQL. Por que, então, 2000 buscas pelo mesmo usuário?

Porque o identity map guarda referências **fracas**. Ele lembra do objeto enquanto alguém, fora dele, ainda segura esse objeto. O `_to_out` buscava o usuário numa variável local, montava o `BookingOut` e retornava. No `return`, a variável morria, ninguém mais segurava o `User`, e o Python o recolhia. A próxima reserva perguntava pelo id 1, o mapa não tinha mais nada, e lá ia outro `SELECT`.

Testei num script de rascunho, fora do repositório, com as mesmas 2000 reservas e um laço de `db.get` por reserva. Reatribuindo a mesma variável a cada volta, deu **2001**: o usuário anterior ainda estava vivo durante o `get` seguinte, e o mapa o achou. Os recursos mudam a cada reserva, e esses sempre iam ao banco. Guardando cada objeto numa lista, deu **51**. E no endpoint, onde nada sobrevive ao `return` do `_to_out`, **4001**. Três números, três jeitos de segurar referência.

É também o "por acaso" da lição 02. No `POST`, o `create` ainda segurava `user` e `resource` em variáveis locais quando chamou o `_to_out`. Por isso o mapa os tinha. O mapa funciona quando alguém segura os objetos. Contar com isso é contar com sorte. A contagem do N+1 depende de quem segura referência a quê, e por isso esta lição mede pelo endpoint, e não por um script que imita o endpoint.

## Duas formas de dizer o que carregar

O SQLAlchemy chama isso de **eager loading**, carregamento antecipado: você avisa, na consulta, quais relações vêm junto. As duas formas mais usadas são `selectinload` e `joinedload`. Capturei o SQL de cada uma num script de rascunho com `echo=True`, que imprime todo comando enviado ao banco. As linhas de log foram aparadas, e o `(...)` marca o corte.

Com `selectinload(Booking.user), selectinload(Booking.resource)`:

```sql
SELECT bookings.id, bookings.user_id, bookings.resource_id, bookings.starts_at, bookings.ends_at
FROM bookings

SELECT users.id AS users_id, users.nome AS users_nome, users.email AS users_email
FROM users
WHERE users.id IN ($1::INTEGER)

SELECT resources.id AS resources_id, resources.nome AS resources_nome, resources.tipo AS resources_tipo
FROM resources
WHERE resources.id IN ($1::INTEGER, $2::INTEGER, $3::INTEGER, (...) $50::INTEGER)
```

Três consultas. A primeira busca as reservas. Depois o SQLAlchemy olha os `user_id` que vieram, tira as repetições (2000 reservas, um id só) e busca todos os usuários de uma vez, com `WHERE id IN (...)`. Faz o mesmo com os 50 recursos. É o N+1 virado do avesso: em vez de uma consulta por reserva, uma consulta por **relação**.

Com `joinedload(Booking.user), joinedload(Booking.resource)`:

```sql
SELECT bookings.id, bookings.user_id, bookings.resource_id, bookings.starts_at, bookings.ends_at,
       users_1.id AS id_1, users_1.nome, users_1.email,
       resources_1.id AS id_2, resources_1.nome AS nome_1, resources_1.tipo
FROM bookings
LEFT OUTER JOIN users AS users_1 ON users_1.id = bookings.user_id
LEFT OUTER JOIN resources AS resources_1 ON resources_1.id = bookings.resource_id
```

*(Quebrei as linhas para caber. O SQL é o mesmo.)*

Uma consulta só. Um `JOIN` costura cada reserva ao usuário e ao recurso dela, e cada linha do resultado já vem completa.

## Por que `selectinload` aqui

Uma consulta parece melhor que três. Olhe o que trafega.

O `joinedload` devolve 2000 linhas de 11 colunas. Em **todas** as 2000, lá estão o nome e o e-mail do mesmo usuário. Cada quadra se repete 40 vezes. O banco manda a mesma informação de novo e de novo, e o SQLAlchemy desduplica tudo do lado de cá.

O `selectinload` devolve 2000 linhas de 5 colunas, mais 1 linha de usuário, mais 50 de recursos. Cada dado viaja uma vez.

Aqui, nesta relação, a repetição é barata. Onde ela morde é nas **coleções**: quando o lado carregado tem **muitos** itens por linha, como um grupo e os seus membros. Um `JOIN` aí multiplica as linhas, uma por combinação, e é preciso desfazer a multiplicação depois. O bloco 2 dos exercícios deste capítulo põe a mão nisso.

O critério, então:

- **Coleção** (um-para-muitos, muitos-para-muitos): `selectinload`.
- **Muitos-para-um pequeno** (cada reserva tem um usuário, um recurso): os dois funcionam. Escolha um e **meça**.

É critério, não dogma. O FairFare usa `selectinload` nas duas relações do `Booking`. Funciona, e é a mesma ferramenta que as coleções vão pedir nas próximas lições.

O conserto mora no repository:

```python
async def list_all(self) -> list[Booking]:
    # Uma consulta para as reservas, mais uma por relação: 3, com 5 ou 5000 reservas.
    stmt = select(Booking).options(selectinload(Booking.user), selectinload(Booking.resource))
    resultado = await self.db.scalars(stmt)
    return list(resultado)
```

E o `_to_out`, no service, deixa de ir ao banco. Ele perde o `async` e as duas buscas, e lê as relações:

```python
def _to_out(self, booking: Booking) -> BookingOut:
    return BookingOut(
        ...
        user_nome=booking.user.nome,
        resource_nome=booking.resource.nome,
    )
```

Repare no que sumiu: o `async def`. Uma função síncrona não tem como esperar o banco. O `_to_out` agora **não pode** fazer consulta. Quem chama perde o `await`, e quem lê o código sabe que montar a resposta é só montar a resposta.

## `lazy="raise"`: a regra que o código faz cumprir

Sobrou um buraco. A lição 02 mostrou que o `POST` funcionava lendo `booking.user` pelo identity map, sem que ninguém tivesse pedido a relação. Funcionava por acaso. Se amanhã alguém escrever um endpoint novo e esquecer o `selectinload`, o lazy load volta: um `MissingGreenlet` no async, ou um N+1 silencioso num código síncrono.

A saída é proibir o lazy load. No model:

```python
# lazy="raise": acesso a relação não carregada é erro na hora, nunca I/O escondido (lição 03).
user: Mapped[User] = relationship(lazy="raise")
resource: Mapped[Resource] = relationship(lazy="raise")
```

Agora, ler uma relação que ninguém carregou é erro, sempre. Mesmo que o objeto esteja no identity map. Para ver, apaguei temporariamente o `.options(...)` do `list_all` e rodei o teste da lição 02:

```console
$ uv run pytest -q tests/test_smoke.py::test_lista_reservas_com_nomes 2>&1 | grep -E "Error|passed|failed"
>       raise sa_exc.InvalidRequestError(
E       sqlalchemy.exc.InvalidRequestError: 'Booking.user' is not available due to lazy='raise'
.venv/lib/python3.12/site-packages/sqlalchemy/orm/strategies.py:867: InvalidRequestError
1 failed in 0.36s
```

Compare com o `MissingGreenlet` da lição 02: `greenlet_spawn has not been called`. Aquela mensagem fala do mecanismo, e você precisava descer pela pilha para achar a relação culpada. Esta diz o nome: `'Booking.user'`. E diz o motivo: ninguém carregou. Na hora, no primeiro teste que passar por ali.

O carregamento explícito deixa de ser disciplina. Vira regra.

## A armadilha do `refresh`

O `lazy="raise"` também cobra do `POST`. O `create` do repository gravava a reserva e fazia um `refresh(booking)`, que relê as colunas do banco. Relações não vêm num refresh de colunas. Testei, temporariamente, o `create` só com esse refresh: **14 failed, 18 passed**. Quase todos com o mesmo `'Booking.user' is not available due to lazy='raise'`, e todos são testes que criam reserva. O identity map não salva mais ninguém.

O `refresh` aceita uma lista de atributos. Parecia bastar trocar o refresh por `refresh(booking, ["user", "resource"])`. Fiz isso, temporariamente, e rodei os testes de fuso do capítulo 4:

```console
$ uv run pytest -q tests/test_fuso.py
(...)
>       assert resp.json()["starts_at"] == "2030-01-01T13:00:00Z"
E       AssertionError: assert '2030-01-01T10:00:00-03:00' == '2030-01-01T13:00:00Z'
(...)
FAILED tests/test_fuso.py::test_horario_volta_em_utc - AssertionError: assert...
1 failed, 5 passed in 0.38s
```

O `refresh` com lista recarrega **só** o que está na lista. O `starts_at` não é relido do banco, e fica como estava no objeto Python: com o fuso que o cliente mandou, `-03:00`. O instante é o mesmo, mas a lição 04 do capítulo 4 prometeu que a resposta volta como o banco guardou, em UTC. A promessa quebrou, e o teste pegou.

Por isso, dois:

```python
await self.db.refresh(booking)
# As relações não vêm no refresh de colunas: pedidas por nome, explicitamente.
# (Só o segundo refresh recarregaria SÓ user e resource, e o starts_at ficaria
# com o fuso de entrada em vez do instante gravado. Lição 03.)
await self.db.refresh(booking, ["user", "resource"])
```

O primeiro relê as colunas. O segundo carrega as relações.

## O guardião

Consertar não basta. O N+1 é o bug que volta: alguém acrescenta uma relação, lê ela no `_to_out`, e o teste de smoke passa, porque o teste lista uma reserva e duas consultas a mais ninguém sente.

Então a contagem vira teste, em `tests/test_consultas.py`:

```python
async def test_listar_reservas_nao_cresce_com_o_numero_de_reservas(client, engine_de_teste):
    user = await cria_usuario(client)
    resource = await cria_recurso(client)
    for dia in range(1, 6):
        resp = await cria_reserva(
            client,
            user["id"],
            resource["id"],
            f"2030-01-0{dia}T10:00:00Z",
            f"2030-01-0{dia}T12:00:00Z",
        )
        assert resp.status_code == 201

    with conta_consultas(engine_de_teste) as contagem:
        resp = await client.get("/bookings")

    assert resp.status_code == 200
    assert len(resp.json()) == 5
    # Uma para as reservas, uma para os usuários, uma para os recursos. Com 5 ou 5000.
    assert contagem["n"] == 3
```

Para contar, o teste precisa da engine que o app usa. Por isso o `tests/conftest.py` ganhou uma fixture, `engine_de_teste`: a engine do `fairfare_test`, com as tabelas já limpas. O `client` passou a depender dela, em vez de criar a própria.

Escrevi o teste antes do conserto. No código da lição 02 (os mesmos três arquivos trazidos de volta), ele falhou assim:

```console
$ uv run pytest -q tests/test_consultas.py
(...)
>       assert contagem["n"] == 3
E       assert 11 == 3
(...)
1 failed in 0.19s
```

Onze: 2×5+1. Depois do conserto:

```console
$ uv run pytest -q tests/test_consultas.py
.                                                                        [100%]
1 passed in 0.18s
```

Três com 5 reservas. Três com 5000. O teste não mede tempo, que varia de máquina para máquina. Mede a **forma**: o número de consultas não pode crescer com o número de linhas.

## O depois, medido

O mesmo script, no mesmo banco, com o conserto:

```console
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py
reservas=2000 consultas=3 tempo=29ms
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py
reservas=2000 consultas=3 tempo=29ms
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py
reservas=2000 consultas=3 tempo=29ms
```

| | consultas | tempo |
|---|---|---|
| antes (2N+1) | 4001 | ~1000 ms |
| depois (`selectinload`) | 3 | 29 ms |

Umas trinta e cinco vezes mais rápido. E o `joinedload`, pela opção do script:

```console
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py --joinedload
reservas=2000 consultas=1 tempo=15ms (joinedload)
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py --joinedload
reservas=2000 consultas=1 tempo=15ms (joinedload)
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py --joinedload
reservas=2000 consultas=1 tempo=15ms (joinedload)
```

Uma consulta. Mas não compare esses 15 ms com os 29 ms. A opção `--joinedload` vai direto ao ORM, sem HTTP, sem Pydantic, sem JSON. É outra medida. O que ela prova é a contagem, e não que o `joinedload` ganhe.

## A dívida mais antiga do curso, paga

O 2N+1 nasceu no capítulo 1. Ficou escrito na ERRATA, entrada 2, item 2, com o endereço "capítulo 5". A lição 11 do capítulo 2 explicou o mecanismo. As lições 12 dos capítulos 3 e 4 o carregaram no inventário do que ainda não estava resolvido. No capítulo 4, ele esgotou um pool.

O endereço era este. Três consultas, e um teste para que ele não volte.

## O que fica declarado

- **Os três experimentos não estão no repositório:** o `list_all` sem `.options(...)`, o `create` só com o primeiro `refresh` e o `create` só com o segundo. Todos foram desfeitos.
- **O script de rascunho do identity map (as 51 consultas) e o do `echo=True` também não.** Os números deles estão aqui, e só aqui.
- **O tempo do `--joinedload` não é comparável ao do endpoint.** A bancada mede caminhos diferentes.

## O que você deve conseguir fazer agora

- Escolher entre `selectinload` e `joinedload` para uma relação dada, e justificar: coleção ou muitos-para-um, e quanto se repete.
- Explicar o que o `lazy="raise"` impede, e por que a mensagem dele é melhor que o `MissingGreenlet`.
- Explicar por que o `create` faz dois `refresh`, e o que quebra com um só.
- Escrever um teste que conta consultas com `event.listen`, e dizer por que ele mede a forma, e não o tempo.
