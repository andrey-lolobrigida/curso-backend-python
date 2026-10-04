# Lição 08 — Transação não é cadeado

A lição 07 terminou com dez de dez rodadas de reserva dupla. Mostre isso para qualquer pessoa que já mexeu com banco de dados, e a primeira resposta vai ser quase sempre a mesma:

> "Põe numa transação."

É uma boa resposta. Parece certa, soa técnica, e transação existe exatamente para "coisas que precisam acontecer juntas". Esta lição testa essa resposta. Com o banco de verdade, contando.

Spoiler do título: não basta. Mas o *porquê* é o que importa, e ele vai guiar as próximas três lições.

## O que é uma transação

Pense num carrinho de compras. Você põe um livro, um fone, uma camiseta. Tira o fone. Põe outro. Nada disso é um pedido ainda. O pedido só existe quando você clica em "finalizar". E se a internet cair no meio, você não recebe metade das coisas: ou o pedido inteiro existe, ou nenhum.

Transação é isso, num banco de dados. Um bloco de comandos que começa com `BEGIN` e termina de um de dois jeitos:

- `COMMIT`: "finalizar". Tudo o que o bloco fez passa a valer, de uma vez.
- `ROLLBACK`: "esvaziar o carrinho". Tudo o que o bloco fez some, como se nunca tivesse acontecido.

Ela promete duas coisas que interessam aqui. (Há mais duas letras numa sigla famosa, ACID, mas elas não mudam a história desta lição.)

**Atomicidade.** Tudo ou nada. Se a transação faz três `INSERT` e o terceiro falha, os dois primeiros não ficam no banco. Você já viu isso duas vezes neste capítulo: o `transactional DDL` do Alembic, na lição 02, e o `ROLLBACK` que desfez o teste do fuso, na lição 04.

**Isolamento.** O que as **outras** conexões veem enquanto a sua transação ainda não terminou. No carrinho, ninguém mais vê o que está no seu carrinho. O estoque só muda para os outros quando você finaliza. No banco, o que a sua transação gravou e ainda não comitou fica invisível para as outras.

Guarde essa segunda promessa. Ela é a lição inteira.

## No FairFare, já existe uma

Aqui vem a surpresa: o `BookingService.create` **já roda dentro de uma transação**. Sempre rodou. Ninguém escreveu `BEGIN` em lugar nenhum, e mesmo assim ela está lá.

Quem abre é o SQLAlchemy. A `AsyncSession` tem um comportamento chamado **autobegin**: no primeiro comando que vai ao banco, ela abre uma transação sozinha, e a mantém aberta até alguém chamar `commit()` ou `rollback()`.

Para ver isso, liguei o log do SQLAlchemy. É um parâmetro do `create_async_engine` em `app/database.py`:

```python
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # TEMPORÁRIO: imprime cada comando SQL
    pool_size=5,
    ...
)
```

*(Essa linha não está no repositório. Liguei, medi e desfiz com `git checkout app/database.py`.)*

Com o app de pé, um `POST /bookings` com uma reserva livre:

```console
$ curl -s -X POST localhost:8000/bookings -H 'content-type: application/json' \
    -d '{"user_id":1,"resource_id":1,"starts_at":"2040-01-01T10:00:00Z","ends_at":"2040-01-01T12:00:00Z"}'
{"id":1000068,"user_id":1,"resource_id":1,"starts_at":"2040-01-01T10:00:00Z","ends_at":"2040-01-01T12:00:00Z","user_nome":"Semente","resource_nome":"Quadra 1"}
```

E o que o SQLAlchemy mandou ao PostgreSQL:

```console
BEGIN (implicit)
SELECT users.id AS users_id, users.nome AS users_nome, users.email AS users_email
FROM users
WHERE users.id = $1::INTEGER
SELECT resources.id AS resources_id, resources.nome AS resources_nome, resources.tipo AS resources_tipo
FROM resources
WHERE resources.id = $1::INTEGER
SELECT bookings.id, bookings.user_id, bookings.resource_id, bookings.starts_at, bookings.ends_at
FROM bookings
WHERE bookings.resource_id = $1::INTEGER AND bookings.starts_at < $2::TIMESTAMP WITH TIME ZONE AND bookings.ends_at > $3::TIMESTAMP WITH TIME ZONE
INSERT INTO bookings (user_id, resource_id, starts_at, ends_at) VALUES ($1::INTEGER, $2::INTEGER, $3::TIMESTAMP WITH TIME ZONE, $4::TIMESTAMP WITH TIME ZONE) RETURNING bookings.id
COMMIT
BEGIN (implicit)
SELECT bookings.id, bookings.user_id, bookings.resource_id, bookings.starts_at, bookings.ends_at
FROM bookings
WHERE bookings.id = $1::INTEGER
ROLLBACK
```

*(Cortei o carimbo de hora e o prefixo `INFO sqlalchemy.engine.Engine` de cada linha, as linhas com os valores dos parâmetros, e as três consultas que o SQLAlchemy faz uma vez só, quando abre a primeira conexão. O resto está na ordem em que saiu.)*

Leia de cima para baixo, com o service do lado:

1. `BEGIN (implicit)` aparece logo antes do primeiro `SELECT`, o do `self.users.get`. O "implicit" é o autobegin: ninguém pediu, a sessão abriu.
2. Os três `SELECT`: o usuário, o recurso, e o `find_overlapping`. A **verificação**.
3. O `INSERT`. A **ação**.
4. O `COMMIT`. Ele vem do `await self.db.commit()` dentro do `BookingRepository.create`.

A verificação e a ação estão **na mesma transação**. O "põe numa transação" já está feito, e a corrida da lição 07 aconteceu com ele.

Depois do `COMMIT` vem um bônus: uma segunda transação, curtinha. O `refresh(booking)` do repository relê a linha recém-gravada, e o autobegin abre outra. Ela só lê, e termina em `ROLLBACK` quando o `get_db` fecha a sessão no fim da request. Um `ROLLBACK` de quem não escreveu nada não desfaz nada. É só a sessão devolvendo a conexão limpa ao pool.

### Quem chama o `commit()`

Repare onde o `commit()` mora: no repository, não no service. Isso tem uma consequência. Se um dia o service precisar gravar duas coisas que só fazem sentido juntas, cada repository vai comitar a sua, e a atomicidade some no meio.

Neste capítulo, o `commit()` **fica onde está**. Hoje cada operação grava uma coisa só, e o problema não aparece. Quem deve comitar é uma pergunta do capítulo 5, quando as despesas chegarem e uma operação passar a mexer em várias tabelas de uma vez.

## O experimento

O log mostra que a transação existe. Falta mostrar que ela não basta, e de um jeito que dê para repetir, sem uvicorn, sem HTTP, sem nada no caminho. Para isso, a bancada tem `bancada/transacao.py`.

Ele faz o mesmo check-then-act do `BookingService.create`, em SQL puro, numa tabela própria, a `bancada_reservas`. A tabela é recriada a cada execução, com dez mil reservas em outros horários, um índice e `ANALYZE`, para ter cara de banco de verdade sem mexer nas tabelas do app. (A tabela fica no banco de dev; a lição 12 conta o efeito colateral.) O coração dele:

```python
async def tentar(
    engine: AsyncEngine, nivel: str, recurso: int, barreira: asyncio.Barrier | None
) -> str:
    params = {"r": recurso, "inicio": INICIO, "fim": FIM}
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level=nivel)
        try:
            async with conn.begin():
                ocupado = await conn.scalar(VERIFICA, params)
                if barreira is not None:
                    await barreira.wait()  # as duas já olharam; agora as duas agem
                if ocupado:
                    return "409"
                await conn.execute(INSERE, params)
            return "201"
        except DBAPIError as erro:
            if getattr(erro.orig, "sqlstate", None) == "40001":  # serialization_failure
                return "abortada"
            raise
```

Tudo dentro de `async with conn.begin()`: `BEGIN` na entrada, `COMMIT` na saída, `ROLLBACK` se uma exceção escapar. O `VERIFICA` é o `find_overlapping` (um `count(*)` com a mesma condição de sobreposição). O `INSERE` é o `create`. O `nivel` aqui é sempre `READ COMMITTED`, o padrão do PostgreSQL, e o `except` do `40001` nunca dispara. Os dois são para a lição 09.

Cada rodada dispara duas chamadas de `tentar` ao mesmo tempo, para a mesma quadra e o mesmo horário, com `asyncio.gather`.

### A barreira

A linha diferente é a do `barreira.wait()`. Um `asyncio.Barrier(2)` é um ponto de encontro: quem chega primeiro espera ali até o segundo chegar, e aí os dois seguem. Com a barreira entre a verificação e o insert, a ordem fica garantida: **as duas olham, e só depois as duas agem**. É o pior encaixe possível da linha do tempo da lição 07, em toda rodada, sem depender de sorte.

Sem a barreira, a sorte quase sempre ajuda o defeito do mesmo jeito. Medi com um script descartável (no scratchpad, fora do repositório), chamando o mesmo `tentar` com `barreira=None`, cem rodadas, três vezes:

```console
sem barreira, 100 rodadas: {'201 + 409': 1, '201 + 201': 99}
sem barreira, 100 rodadas: {'201 + 201': 100}
sem barreira, 100 rodadas: {'201 + 409': 1, '201 + 201': 99}
```

Noventa e nove por cento sem ajuda nenhuma. A barreira não cria a corrida. Ela só tira o "quase" do resultado, para que a lição 09 possa comparar níveis de isolamento sem que a sorte entre na conta.

### O resultado

```console
$ uv run python chapters/04-o-banco-de-dados-de-verdade/bancada/transacao.py
rodada  1: 201 + 201
rodada  2: 201 + 201
rodada  3: 201 + 201
rodada  4: 201 + 201
rodada  5: 201 + 201
rodada  6: 201 + 201
rodada  7: 201 + 201
rodada  8: 201 + 201
rodada  9: 201 + 201
rodada 10: 201 + 201

READ COMMITTED, mesma quadra: duas reservas em 10/10 rodadas
```

Dez de dez. Duas transações, cada uma com começo, meio e fim, cada uma atômica. E duas reservas para a mesma quadra no mesmo horário.

## Por quê

O `READ COMMITTED` no fim da saída é o **nível de isolamento**: a regra que diz o que uma transação enxerga das outras. É o padrão do PostgreSQL, e o do container também:

```console
$ docker compose exec -T postgres psql -U fairfare -c "SHOW default_transaction_isolation;"
 default_transaction_isolation
-------------------------------
 read committed
(1 row)
```

O nome já diz a regra: **lê o que foi comitado**. Mais preciso: em `READ COMMITTED`, cada comando vê o banco como ele estava no instante em que **aquele comando** começou, contando só o que já tinha sido comitado.

Agora reconte a rodada, com a barreira no meio:

```
tempo ──────────────────────────────────────────────────────────────►

T1: BEGIN  SELECT count(*) → 0  │ espera │  INSERT  COMMIT
T2: BEGIN  SELECT count(*) → 0  │ espera │  INSERT  COMMIT
                                ▲
                                └── barreira: as duas já olharam
```

Quando o `SELECT` da T1 rodou, a T2 não tinha gravado nada. Quando o `SELECT` da T2 rodou, a T1 também não. Nenhuma das duas **podia** ver a outra: o isolamento escondeu justamente o que importava. Cada `count(*)` deu `0`, e cada `0` era verdade no instante em que foi lido.

Aí as duas gravaram. E o `INSERT` não pergunta nada a ninguém. Não existe regra no banco dizendo "duas reservas não podem se sobrepor". Para o PostgreSQL, são duas linhas diferentes numa tabela, e ele as aceita.

A transação cumpriu tudo o que prometeu. Deu atomicidade: cada uma gravou tudo ou nada. Deu isolamento: nenhuma viu o trabalho pela metade da outra. O que ela **não** prometeu foi exclusividade. Ela não impede outra transação de fazer a mesma pergunta, ao mesmo tempo, e chegar à mesma resposta.

Na agenda de papel da lição 07, a transação é cada um rascunhar a anotação num papel à parte e só passá-la para a agenda quando terminar. Ninguém vê anotação pela metade. Mas Ana e Bruno continuam olhando a agenda ao mesmo tempo: os dois veem o horário livre, os dois passam a limpo. O que resolveria é um cadeado na agenda: quem pega primeiro olha e anota, e o outro espera.

**Transação não é cadeado.**

## E agora?

Duas saídas aparecem quando você olha a linha do tempo acima.

A primeira: e se a transação fosse **mais desconfiada**? Se o banco percebesse que as duas leram a mesma coisa e depois agiram com base nisso, e recusasse uma delas? Isso existe, e é para isso que o `nivel` e o `"abortada"` do script estão lá. São os **níveis de isolamento**, e a lição 09 os testa, um por um, nesta mesma bancada.

A segunda: e se alguém **pusesse o cadeado** de verdade? Isso também existe, e é a lição 10.

## O que fica declarado

- **A corrida continua aberta no app.** Esta lição só mostrou que a transação que ele já tem não a fecha.
- **O `echo=True` foi temporário.** O log acima veio de uma execução com ele ligado, e o `app/database.py` do repositório não tem essa linha.
- **A reserva do log (id `1000068`) foi apagada** depois da medição, para não deixar lixo no banco de dev.
- **A medição sem barreira** foi um script descartável, rodado três vezes e jogado fora. O `transacao.py` sempre usa a barreira.
- **O `commit()` continua no repository.** Quem deve comitar é uma pergunta do capítulo 5.

## O que você deve conseguir fazer agora

- Dizer onde a transação de um `POST /bookings` começa e onde ela termina, e quem abre e quem fecha cada uma.
- Ligar o `echo=True` e ler o `BEGIN (implicit)` e o `COMMIT` no log.
- Explicar o que a barreira do `transacao.py` garante, e por que ela não "cria" a corrida.
- Explicar por que duas transações em `READ COMMITTED` gravam as duas: o que cada `SELECT` vê, e o que o `INSERT` não verifica.
- Dizer o que uma transação promete (atomicidade, isolamento) e o que ela não promete (exclusividade).
