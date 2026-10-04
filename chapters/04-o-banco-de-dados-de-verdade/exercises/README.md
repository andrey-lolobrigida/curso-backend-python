# Exercícios do capítulo 4

**Aviso, porque isto importa: todo código desta pasta está quebrado de propósito.**

O FairFare, em `app/`, não tem defeito escondido: o que ele ainda não resolve está declarado na lição 12. O que você encontrar de errado lá fora disso vale um issue. O que está *aqui* foi escrito errado de caso pensado, para você consertar. Só um item foge um pouco da regra: o 2.1 não está quebrado, ele **funciona, mas do jeito caro**. A resposta sai certa. O preço é que está errado.

Cada bloco tem testes que você mesmo roda. O teste é a definição de "pronto": enquanto ele estiver vermelho, o exercício não acabou.

Nenhum destes testes é coletado pelo `uv run pytest` do projeto (o `testpaths` do `pyproject.toml` cuida disso). Você roda cada bloco apontando o caminho.

Os blocos são **autocontidos**: nenhum deles importa `app/`. Cada um cria as próprias tabelas no `fairfare_test`, o banco do pytest (`reservas_do_clube`, `bloco2_*`, `bloco3_*`), e as apaga no fim. O banco de desenvolvimento do FairFare não é tocado. As fixtures que todos usam moram em `exercises/conftest.py`.

Todos precisam do Postgres de pé:

```bash
docker compose up -d --wait
```

---

## Bloco 1 — A migração que mudou o passado

**Arquivo:** `bloco1/migracao.py` — **quebrado de propósito.**

O sistema antigo de um clube gravava o início de cada reserva em `timestamp`, sem fuso, no horário de parede de São Paulo. A migração converte a coluna para `timestamptz`. Ela foi copiada da lição 04 e roda sem erro nenhum. Nenhuma linha some, nenhum aviso aparece. E todas as reservas mudam de horário.

```bash
uv run pytest chapters/04-o-banco-de-dados-de-verdade/exercises/bloco1 -v
```

Estado inicial: **2 falharam**. Na máquina do autor, saiu isto:

```
E       AssertionError: assert datetime.datetime(2030, 1, 1, 10, 0, tzinfo=zoneinfo.ZoneInfo(key='Etc/UTC')) == datetime.datetime(2030, 1, 1, 13, 0, tzinfo=datetime.timezone.utc)
E       AssertionError: assert datetime.datetime(2018, 12, 1, 10, 0, tzinfo=zoneinfo.ZoneInfo(key='Etc/UTC')) == datetime.datetime(2018, 12, 1, 12, 0, tzinfo=datetime.timezone.utc)
```

As duas reservas eram às 10h em São Paulo. Depois da migração, as duas viraram 10h em UTC: horas antes do que quem marcou combinou.

A dica: a migração foi copiada da lição 04. O que a lição 04 *supôs* sobre os horários que já estavam gravados? Essa suposição vale para o banco do clube?

**Pronto quando:** os dois testes de `test_bloco1.py` passam. E um aviso, que vale ouro: **um conserto que passa só no primeiro teste ainda está errado.** O segundo teste existe exatamente para pegar o conserto que parece certo. Se o seu passou num e não no outro, pergunte o que aconteceu com o relógio de São Paulo em dezembro de 2018.

---

## Bloco 2 — O banco sob carga

Três itens independentes, num arquivo de teste só. Você pode rodar um de cada vez com `-k`, ou todos juntos:

```bash
uv run pytest chapters/04-o-banco-de-dados-de-verdade/exercises/bloco2 -v -s
```

O `-s` deixa aparecer o tempo que o teste da 2.1 imprime.

Estado inicial: **1 passou, 3 falharam.** O que passa é o `test_resultado_do_dia_esta_certo`, e isso é parte do exercício (veja a 2.3).

### 2.1 — Aquecimento: o `count()`

**Arquivo:** `bloco2/repositorio.py` — **funciona, mas do jeito caro.**

É o `count()` da lição 08 do capítulo 1, aquele do "`len` da lista serve por enquanto". Com 50 linhas, servia. Aqui a tabela tem 200 mil.

O teste confere duas coisas: que o total dá 200 000 (dá) e que o SQL enviado ao banco tem um `count(` dentro (não tem). Na máquina do autor:

```
count() em 0.192s
...
E       AssertionError: o count ainda traz as linhas para o Python
```

Duzentas mil linhas atravessaram a rede, viraram objetos Python e foram contadas uma por uma. Para devolver um número.

**Pronto quando:** `test_count_conta_no_banco` passa. Rode com `-s` antes e depois e compare o tempo impresso. A diferença é o tamanho do desperdício.

### 2.2 — O vazamento

**Arquivo:** `bloco2/vazamento.py` — **quebrado de propósito.**

Um app mínimo com o mesmo pool do FairFare (5 + 10) e uma rota só, `/agora`. O teste faz 100 requests seguidas. Cada uma pega uma sessão. Repare em quem devolve a conexão dela ao pool.

Estado inicial: falha logo na **primeira** request:

```
E               AssertionError: a conexão da request 1 só voltou porque o coletor de lixo foi buscar
```

E, nos logs capturados, o SQLAlchemy reclamando:

```
ERROR    sqlalchemy.pool.impl.AsyncAdaptedQueuePool:base.py:1031 The garbage collector is trying to clean up non-checked-in connection <AdaptedConnection <asyncpg.connection.Connection object at 0x73f07ff0f200>>, which will be terminated.  Please ensure that SQLAlchemy pooled connections are returned to the pool explicitly, either by calling ``close()`` or by using appropriate context managers to manage their lifecycle.
```

Leia com calma, porque o sintoma é traiçoeiro. Ninguém devolve a conexão. Quem acaba resolvendo é o **coletor de lixo** do Python (o *garbage collector*, a parte do interpretador que recolhe objetos que ninguém mais usa). Ele acha a sessão abandonada e encerra a conexão dela. O pool ganha a vaga de volta, e o app segue respondendo. Às vezes.

O teste chama `gc.collect()` depois de cada request para o coletor passar *naquela hora*, e não quando ele quiser. Sem isso, o resultado vira loteria. O autor tirou o `gc.collect()` e rodou oito vezes: o coletor salvou as primeiras dezenas de requests, e mesmo assim o pool secou em todas. Uma vez na request 87, sete vezes na 98, sempre com:

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 2.00
```

Na sua máquina o número vai ser outro. É esse o problema: um app que funciona enquanto o coletor de lixo tem tempo de passar funciona por sorte.

**Pronto quando:** `test_cem_requests_seguidas` passa. Ou seja: as 100 requests respondem `200`, o coletor de lixo não precisa recolher conexão nenhuma, e no fim `engine.pool.checkedout()` dá `0`. O conserto não mexe no pool, nem no `pool_timeout`, nem no teste.

### 2.3 — O índice que o planner ignora

**Arquivo:** `bloco2/consulta.py` — **quebrado de propósito**, do jeito mais sutil do capítulo: o resultado está certo.

`reservas_do_dia(dia)` devolve as reservas que começam num dia (em UTC). A tabela `bloco2_agenda` tem 100 mil linhas, uma por minuto, e um índice em `starts_at`. A consulta devolve exatamente as 1440 linhas do dia, e o `test_resultado_do_dia_esta_certo` passa. O outro teste pede o plano ao banco:

```
E       AssertionError: o planner está lendo a tabela inteira
E       assert 'Seq Scan' not in '[{"Plan": {...'::date)"}}]'
...
E           [{"Plan": {"Node Type": "Seq Scan", "Parallel Aware": false, "Async Capable": false, "Relation Name": "bloco2_agenda", "Alias": "bloco2_agenda", "Startup Cost": 0.0, "Total Cost": 2041.0, "Plan Rows": 500, "Plan Width": 12, "Disabled": false, "Filter": "(date(starts_at) = '2030-01-02'::date)"}}]
```

O índice está lá. O planner simplesmente não consegue usá-lo para essa pergunta. A lição 06 mostrou o que um índice btree sabe responder. Olhe o `Filter` e pergunte: o que está indexado é `starts_at`, ou é outra coisa?

**Pronto quando:** `test_a_consulta_usa_o_indice` passa **e** `test_resultado_do_dia_esta_certo` continua passando. Mude a consulta sem mudar a resposta. Um índice novo não vale: o conserto mora em `reservas_do_dia`.

---

## Bloco 3 — A concorrência

Dois itens, o mesmo arquivo de teste. Estas tabelas são reais (não temporárias), porque várias conexões precisam enxergá-las ao mesmo tempo. O teste as cria e as apaga.

```bash
uv run pytest chapters/04-o-banco-de-dados-de-verdade/exercises/bloco3 -v
```

Estado inicial: **2 falharam.**

### 3.1 — O retry no cadáver

**Arquivo:** `bloco3/retry.py` — **quebrado de propósito.**

É a reserva com `SERIALIZABLE` da lição 09: verifica se o horário está livre, insere, faz commit. Quando o banco aborta a transação com `40001` (*serialization failure*), o código tenta de novo, até cinco vezes. A ideia está certa. O problema é **onde** ele tenta de novo.

O teste dispara 5 reservas iguais ao mesmo tempo, 10 rodadas seguidas. Em cada rodada, exatamente uma tem que sair `criada` e quatro `conflito`.

A exceção que escapa depende de onde o `40001` nasceu. Se ele veio no `COMMIT`, sai esta (foi a mais comum na máquina do autor: 14 de 15 execuções do teste):

```
E       sqlalchemy.exc.PendingRollbackError: Can't reconnect until invalid transaction is rolled back.  Please rollback() fully before proceeding (Background on this error at: https://sqlalche.me/e/20/8s2b)
```

Se veio no `INSERT`, sai esta outra:

```
E                   sqlalchemy.exc.DBAPIError: (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'asyncpg.exceptions.InFailedSQLTransactionError'>: current transaction is aborted, commands ignored until end of transaction block
E                   [SQL: SELECT count(*) FROM bloco3_reservas WHERE resource_id = $1 AND starts_at < $2 AND ends_at > $3]
```

Repare no `[SQL: ...]` da segunda: quem falhou não foi o `INSERT`. Foi o `SELECT` da tentativa **seguinte**. As duas mensagens dizem a mesma coisa com palavras diferentes. Leia as duas devagar.

Depois do primeiro conserto, rode o teste umas dez vezes seguidas. Se aparecer `RuntimeError: cinco tentativas e nada`, você não voltou à estaca zero: avançou um passo. O retry agora funciona, só que rápido demais. A lição 09 mediu quanto tempo o `COMMIT` do vencedor pode levar, e quanto tempo leva uma tentativa do perdedor. Compare os dois números. Cinco tentativas de meio milissegundo cabem dentro de um `COMMIT` lento. A lição 09 também testou uma pausa fixa de 10 ms entre as tentativas, e contou por que ela não bastou. Leve isso em conta quando decidir quanto esperar, e se a espera deve ser sempre a mesma.

**Pronto quando:** `test_corrida_serializable_termina_com_uma_reserva` passa, com 10 rodadas de exatamente 1 `criada` e 4 `conflito`, e continua passando quando você roda o teste dez vezes seguidas. Sem mudar o teste, e sem subir o número de tentativas. Uma falha rara, com a máquina ocupada, não reprova o conserto: um retry com limite pode estourar o limite, e é por isso que ele tem um (o capítulo 9 volta a isso). Falha frequente, sim.

### 3.2 — O deadlock das duas quadras

**Arquivo:** `bloco3/deadlock.py` — **quebrado de propósito.**

Uma operação de bancada: reservar duas quadras juntas, para um torneio que usa as duas. Ela tranca as duas linhas com `FOR UPDATE`, na ordem em que o cliente mandou. O teste faz 50 rodadas com dois clientes ao mesmo tempo: um pede `(1, 2)`, o outro pede `(2, 1)`.

Estado inicial: o Postgres desiste e mata uma das duas transações. Na máquina do autor:

```
E   asyncpg.exceptions.DeadlockDetectedError: deadlock detected
E   DETAIL:  Process 296293 waits for ShareLock on transaction 17950; blocked by process 296294.
E   Process 296294 waits for ShareLock on transaction 17949; blocked by process 296293.
E   HINT:  See server log for query details.
```

Leia o `DETAIL` como uma história: cada processo espera o outro, e nenhum dos dois vai soltar. Os números de processo e de transação mudam a cada execução. O desenho, não.

**Pronto quando:** `test_cinquenta_rodadas_sem_deadlock` passa. O conserto não tira o `FOR UPDATE`, não tira o `asyncio.sleep` e não troca nenhum dos dois locks por outra coisa. Os dois clientes continuam pedindo as duas quadras, cada um na ordem que quiser.
