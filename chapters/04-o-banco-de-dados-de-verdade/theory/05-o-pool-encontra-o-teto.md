# Lição 05 — O pool encontra o teto

No capítulo 2, a lição 09 terminou com uma confissão:

> Repare que esta lição inteira foi sobre um gargalo de **quinze conexões** — e a gente nem discutiu se quinze é um bom número.

Não dava para discutir. Com SQLite, conexão era um arquivo aberto, e não havia teto do outro lado. Agora há. A lição 01 mostrou o número: **`max_connections = 100`**, para o servidor inteiro. Esta lição põe os dois números para brigar: o pool de cada processo, e o teto do servidor.

## Uma lista que demora

Para esgotar um pool, cada request precisa **segurar** a conexão por um tempo. O `GET /bookings` faz isso sozinho, se houver reservas suficientes. Criei 2000 à mão, direto no `psql`:

```bash
docker compose exec -T postgres psql -U fairfare -d fairfare -c "
INSERT INTO bookings (user_id, resource_id, starts_at, ends_at)
SELECT (SELECT min(id) FROM users), (SELECT min(id) FROM resources),
       '2040-01-01 00:00+00'::timestamptz + g * interval '2 hours',
       '2040-01-01 01:00+00'::timestamptz + g * interval '2 hours'
FROM generate_series(1, 2000) g;"
```

*(Um usuário e um recurso precisam existir antes. As datas começam em 2040 para não encostar nas reservas das lições anteriores. É um atalho de bancada: a lição 06 traz um seed de verdade e começa limpando a tabela.)*

Uma request sozinha, com 2002 reservas no banco:

```console
$ curl -s -o /dev/null -w '%{http_code} %{time_total}\n' localhost:8000/bookings
200 0.974191
```

Quase um segundo. O motivo tem nome e endereço: para cada reserva, o `_to_out` busca o usuário e o recurso, uma consulta de cada vez. São 4005 consultas numa request (duas por reserva, mais a lista), e a conexão fica presa a ela do começo ao fim. É uma limitação declarada, e ela morre no capítulo 5. Hoje ela é útil: é exatamente o tipo de request que esgota um pool.

## O pool estoura

O FairFare com quatro workers, como na lição 11 do capítulo 3, e duzentas requests de uma vez:

```bash
uv run uvicorn app.main:app --port 8000 --workers 4
```

```bash
C=chapters/03-entre-o-cliente-e-o-router/bancada/carga.py
uv run python $C http://localhost:8000/bookings 200 --nova-conexao --header 'X-Forwarded-For: 10.0.0.{i}'
```

Duas flags do `carga.py` merecem uma palavra. O `X-Forwarded-For` dá um IP diferente a cada request. Sem ele, o rate limiter do capítulo 3 barraria quase tudo com `429`, e a gente mediria o limitador, não o pool. Funciona porque o uvicorn confia no loopback (lição 08 do capítulo 3). Já o `--nova-conexao` abre uma conexão TCP por request. Sem ele, a primeira tentativa morreu no próprio cliente com `httpx2.ReadError`, ao reaproveitar uma conexão que o servidor já tinha fechado. Um problema do cliente, não do que a gente quer medir.

O resultado:

```console
200 requests em 32.54s  status → 200: 120  500: 80
```

E no log do uvicorn, oitenta vezes:

```console
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00 (Background on this error at: https://sqlalche.me/e/20/3o7r)
```

É a mensagem do capítulo 2, letra por letra. Vale ler cada número:

- **`size 5`**: o `pool_size`, as conexões que o pool mantém abertas o tempo todo.
- **`overflow 10`**: o `max_overflow`, as extras que ele abre sob pico e fecha depois.
- **`timeout 30.00`**: o `pool_timeout`, quantos segundos uma request espera na fila do pool antes de desistir.

Cada worker tem um pool de 15. A décima sexta request de um worker não falha na hora: ela **espera**. Se em 30 segundos nenhuma das quinze voltar, ela desiste e vira `500`. Os 32 segundos da carga são isso: trinta de espera e um pouco de troco.

### A versão controlada

Um experimento com uvicorn, `curl` e duzentas requests tem peças demais. A bancada tem uma versão em que só o pool aparece: `bancada/pool.py`. Ele cria um engine com os números do app e dispara tarefas que seguram a conexão com `SELECT pg_sleep(3)`, três segundos parados. Para não esperar meio minuto, o `pool_timeout` aqui é 2:

```bash
B=chapters/04-o-banco-de-dados-de-verdade/bancada
uv run python $B/pool.py pool --tarefas 20
```

```console
  15 × ok
   5 × TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 2.00 (Background on this error at: https://sqlalche.me/e/20/3o7r)
```

Quinze pegam conexão. As outras cinco esperam dois segundos, ninguém devolve (as quinze estão dormindo por três), e elas desistem. Com `--tarefas 15`, dá `15 × ok`. O funil tem quinze de largura, nem uma a mais.

## O conserto ingênuo

O pool estourou. A reação de quase todo mundo, numa madrugada de plantão, é a mesma: **aumenta o pool**. Trinta em vez de quinze.

Num processo só, funciona. O subcomando `servidor` do `pool.py` cria um engine por "processo", cada um com `pool_size` igual a `--por-processo` e sem overflow:

```console
$ uv run python $B/pool.py servidor --processos 1 --por-processo 30
1 processos × 30 conexões = 30 pedidas
  30 × ok
```

Trinta conexões, trinta ok. Problema resolvido, certo?

## × 4 workers

A lição 11 do capítulo 3 já tinha avisado:

> Cinco mais dez são quinze conexões — **por processo**. Com `--workers 4`, o app pode abrir 60.

E também:

> Vai doer no capítulo 4, quando o FairFare for para o PostgreSQL — que tem um limite próprio de conexões, para o servidor inteiro, e não se importa nem um pouco com quantos workers você achou que podia subir.

Chegou a hora de doer. Mudei o `app/database.py` **temporariamente**, só nesta máquina, para o pool de cada processo ir a 30. Essa mudança **não está no repositório**, e você vai ver por quê:

```python
    pool_size=20,  # conexões mantidas abertas
    max_overflow=10,  # extras sob pico, descartadas depois
```

Mesmo uvicorn, mesmos quatro workers, mesma carga:

```console
200 requests em 33.40s  status → 200: 120  500: 80
```

E no log, dois erros diferentes:

```console
     60 sqlalchemy.exc.TimeoutError: QueuePool limit of size 20 overflow 10 reached, connection timed out, timeout 30.00 (Background on this error at: https://sqlalche.me/e/20/3o7r)
     20 asyncpg.exceptions.TooManyConnectionsError: sorry, too many clients already
```

*(Contei as linhas do log com `sort | uniq -c`.)*

O segundo erro é novo, e ele não vem do SQLAlchemy. Vem do **PostgreSQL**: "desculpe, clientes demais". Quatro processos, cada um achando que podia abrir trinta. São **4 × 30 = 120** pedidas, contra um teto de **100**. Vinte ficaram do lado de fora.

E não foi só o app. Enquanto a carga rodava, eu tinha um `psql` consultando o `pg_stat_activity` a cada segundo. Em 29 das amostras, ele levou isto:

```console
psql: error: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed: FATAL:  sorry, too many clients already
```

O banco estava tão cheio que **nem o administrador entrava** para ver o que estava acontecendo. Imagine isso às três da manhã.

A bancada mostra a mesma coisa sem o uvicorn. **Derrube o uvicorn antes** (Ctrl+C) e desfaça a mudança do pool (`git checkout app/database.py`). Parados, os workers ainda seguram as conexões ociosas do pool deles, e elas contam contra os mesmos 100. Com o uvicorn de pé, o `pool.py` abaixo dá 80 ok, não 100.

Cada engine faz o papel do pool de um worker. Para o Postgres não há diferença: ele só conta conexões, não sabe de que processo elas vêm.

```console
$ uv run python $B/pool.py servidor --processos 4 --por-processo 15
4 processos × 15 conexões = 60 pedidas
  60 × ok
$ uv run python $B/pool.py servidor --processos 4 --por-processo 30
4 processos × 30 conexões = 120 pedidas
 100 × ok
  20 × TooManyConnectionsError: sorry, too many clients already
```

Com 15 por processo, 60 cabem. Com 30, o servidor corta em 100. **O conserto de um problema causou o seguinte.**

E tem um detalhe pior. Compare as duas linhas do `carga.py`: **120 ok, nas duas**. Dobrar o pool não fez o FairFare atender nem uma request a mais. Numa terceira rodada, igual à segunda (`200 requests em 33.51s  status → 200: 120  500: 80`), olhei o `top` no meio da carga: os quatro workers Python entre 90% e 100% de CPU cada, e cada processo do Postgres perto de 9%. O gargalo desta carga é o Python montando milhares de consultas, não a falta de conexões. Mais conexões só deram mais gente esperando, e um erro novo.

## As três vagas que não salvaram ninguém

Cem é o teto, mas não é bem cem para todo mundo. O Postgres guarda algumas vagas para emergência:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare -c "SELECT name, setting FROM pg_settings WHERE name IN ('max_connections','superuser_reserved_connections','reserved_connections');"
              name              | setting
--------------------------------+---------
 max_connections                | 100
 reserved_connections           | 0
 superuser_reserved_connections | 3
(3 rows)
```

Três vagas reservadas para **superusuário**. A ideia é boa: o app lota 97, e o admin ainda entra pelas três de sobra para apagar o incêndio.

Só que o usuário `fairfare` **é** superusuário. A imagem do Postgres cria o `POSTGRES_USER` do `compose.yaml` (lição 01) como superusuário. Então o app passou pela porta dos fundos também: pegou as 100 vagas, inclusive as três de emergência. Foi por isso que o `pool.py` conseguiu 100, e não 97. E foi por isso que o `psql` ficou trancado do lado de fora.

Para ver a reserva funcionando, criei um papel sem superpoder, chamado `comum`, e rodei o mesmo experimento com ele. Foi um teste de uma vez só: o papel e o script ficaram fora do repositório, e apaguei o papel no fim.

```console
4 processos × 30 conexões = 120 pedidas
  97 × ok
  20 × TooManyConnectionsError: sorry, too many clients already
   3 × TooManyConnectionsError: remaining connection slots are reserved for roles with the SUPERUSER attribute
```

Noventa e sete. As três últimas tentativas levaram uma mensagem diferente: "as vagas que sobram são de quem tem o atributo SUPERUSER". E, no pico, o `psql` do admin entrou normalmente.

A lição: **a reserva do Postgres só protege o admin se o app não for superusuário.** O FairFare conecta como superusuário. Fica declarado como limitação. O conserto é um usuário do banco só para o app, sem superpoder, e ele mora no capítulo 11, junto com as credenciais que hoje estão fixas no código.

## Dimensionar

Agora dá para responder à pergunta do capítulo 2. A conta é uma desigualdade:

```
workers × (pool_size + max_overflow)  ≤  max_connections − reserva
```

Do lado esquerdo, o **pior caso** do app: todos os workers com o pool cheio, overflow incluído. Do lado direito, o teto do servidor menos uma **reserva** para quem não é o app: o Alembic rodando uma migração, o seu `psql`, uma ferramenta de admin, um script da bancada. E o servidor é um só para todos os bancos dele: o `pytest`, que usa o `fairfare_test`, também conta contra os mesmos 100.

A reserva não é uma fórmula. É uma decisão. Uma dezena de vagas é folga para um projeto deste tamanho.

E por que não pôr um pool enorme e um `max_connections` enorme, e acabar com o assunto? Porque um pool maior **não é** mais rápido. Você acabou de ver isso no 120 = 120. E há um motivo do lado do banco também: no Postgres, cada conexão é um processo (lição 01). Quando há mais conexões trabalhando ao mesmo tempo do que núcleos na máquina, esses processos disputam a CPU entre si, e cada consulta fica mais lenta. O pool é um funil de propósito. Ele protege o banco do seu entusiasmo.

Quando um sistema precisa mesmo de mais conexões do lado do app do que o banco aguenta, existem os *poolers*, como o PgBouncer: um intermediário que recebe muitas conexões e repassa poucas ao Postgres. Eles não entram neste curso agora.

## O FairFare hoje

Com os números do `app/database.py` e os quatro workers do capítulo 3:

```
4 × (5 + 10) = 60  ≤  100 − 10 = 90
```

Sobram 40 vagas além do pior caso do app, e a reserva de dez está folgada. Com a mesma conta, cabem até 6 workers (6 × 15 = 90). O sétimo já passa do teto.

Por isso o `app/database.py` **não muda** nesta lição. Os números de lá já cabem. E os 80 `500` da primeira carga não eram um pool pequeno demais: eram duzentas requests de um segundo caindo de uma vez em quatro processos. A rodada com pool 30 provou isso: o dobro de conexões, o mesmo 120, e os workers sem CPU livre. Aumentar o pool não ajudou. A causa é o endpoint lento, e ela morre no capítulo 5. Até lá, o freio do servidor (o `--limit-concurrency` da lição 02 do capítulo 3) troca esse `500` caro por um `503` barato.

O que muda é que agora os números têm uma conta por trás. Antes eles eram o padrão do SQLAlchemy. Agora são **15 por processo, 60 no pior caso, 100 no servidor**, e você sabe dizer o que acontece se alguém mexer em qualquer um dos três.

## O que fica declarado

- **Os números são desta máquina, nesta sessão.** Doze núcleos, loopback, 2002 reservas. O 120 ok vai dançar na sua máquina. O 100 do `pool.py`, não: é o teto do servidor, desde que nada mais esteja conectado. Um uvicorn ou um `psql` de pé ocupam vagas, e o 100 cai junto.
- **A mudança para pool 30 foi temporária** e nunca entrou no repositório. Se você repetir o experimento, desfaça com `git checkout app/database.py`.
- **O papel `comum` e o script dele foram descartáveis**, fora do repositório.
- **O app conecta como superusuário**, e a reserva do Postgres não o protege de si mesmo. Morre no capítulo 11.
- **O `GET /bookings` faz duas consultas por reserva.** Morre no capítulo 5.

## O que você deve conseguir fazer agora

- Ler `QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00` e dizer o que cada número significa e o que acontece com a décima sexta request.
- Fazer a conta para N workers e dizer com quantos o FairFare passa do teto.
- Explicar por que dobrar o pool pode derrubar o banco, e por que ele nem sempre deixa o app mais rápido.
- Explicar por que o `pool.py` conseguiu 100 conexões, e não 97.
