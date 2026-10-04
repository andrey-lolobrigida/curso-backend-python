# Lição 04 — Que horas são?

Duas lições atrás, o FairFare passou a dar 500 para um horário com fuso. Na lição 03, um teste passou a dizer o que ele deveria fazer, marcado `xfail` até hoje. Esta lição conserta o defeito e tira a marca. A pergunta dela: **o que um horário precisa dizer para ser um instante, e quem decide quando ele não diz?**

## Dois bancos, dois jeitos de falhar

Recapitulando os sintomas, porque eles são o mesmo defeito.

**No SQLite** (capítulos 1 a 3), a reserva das 10h de Brasília (`-03:00`) e a das 13h em UTC (`Z`) recebiam **201 e 201**. Você viu isso na lição 03. O `-03:00` era jogado fora na gravação, e para o banco sobravam dois números, 10:00 e 13:00, que não se sobrepõem. Uma reserva dupla, sem nenhuma corrida envolvida. Está registrado na entrada 3 do `ERRATA.md`.

**No PostgreSQL** (lição 02), o mesmo pedido dava **500**. O `asyncpg` se recusou a converter um horário com fuso para uma coluna `timestamp without time zone`.

Mesmo código. Dois bancos. Um engolia o erro e dava uma resposta errada com cara de certa. O outro gritou.

O grito é melhor. Um 500 aparece no log, alguém olha, alguém conserta. Um 201 errado vira uma quadra com dois grupos dentro, num sábado de manhã. **Um erro barulhento é um favor.**

## Horário de parede × instante

Imagine um bilhete na geladeira: "a gente se encontra ao meio-dia". Que meio-dia? Se quem escreveu estava em Tóquio e quem leu está em São Paulo, a diferença é de doze horas. O bilhete tem um horário, mas não tem um **instante**. Falta a cidade.

Esse é o **horário de parede**: o número que o relógio da parede mostra, sem dizer qual parede.

O rigor, no PostgreSQL:

- **`timestamp without time zone`** guarda o bilhete. Ele guarda `2030-01-01 10:00:00` e mais nada. Se o horário chegar com fuso, o fuso não tem onde morar.
- **`timestamp with time zone`**, apelidado de **`timestamptz`**, guarda o **instante**: um ponto na linha do tempo, igual para o mundo todo. Por dentro, ele guarda o instante em UTC.

E aqui mora a pegadinha do nome. O `timestamptz` **não guarda o fuso de quem mandou**. Mandou `10:00-03:00`? Ele converte para `13:00` UTC, guarda isso, e esquece o `-03:00`. Na hora de mostrar, ele converte de volta usando o fuso **da sessão** (a configuração `TimeZone` da conexão que está lendo).

Dá para ver isso no `psql`, com a reserva que você vai criar mais adiante nesta lição (10h de Brasília, no dia 1º de fevereiro):

```console
$ docker compose exec postgres psql -U fairfare -c "SELECT starts_at FROM bookings ORDER BY id DESC LIMIT 1;"
       starts_at
------------------------
 2030-02-01 13:00:00+00
(1 row)

$ docker compose exec postgres psql -U fairfare -c "SET TIME ZONE 'America/Sao_Paulo'; SELECT starts_at FROM bookings ORDER BY id DESC LIMIT 1;"
SET
       starts_at
------------------------
 2030-02-01 10:00:00-03
(1 row)
```

A mesma linha, o mesmo valor guardado. A primeira sessão está no fuso padrão do container, `Etc/UTC` (você viu na lição 01), e mostra `13:00+00`. A segunda pediu São Paulo e vê `10:00-03`. Nada foi regravado. **Mudou só a exibição.**

O FairFare precisa do instante. Uma quadra não fica ocupada "às 10h de algum lugar". Ela fica ocupada num intervalo da linha do tempo.

## O diff do model

```diff
 from datetime import datetime

-from sqlalchemy import ForeignKey
+from sqlalchemy import DateTime, ForeignKey
 from sqlalchemy.orm import Mapped, mapped_column
 (...)
     resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
-    starts_at: Mapped[datetime]
-    ends_at: Mapped[datetime]
+    # timestamptz: um instante na linha do tempo, não um horário de parede (lição 04).
+    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
+    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

Até aqui, o SQLAlchemy deduzia o tipo da anotação `Mapped[datetime]`, e o padrão dele é `DateTime()`, sem fuso. Agora o tipo é dito por extenso: `DateTime(timezone=True)`, que no PostgreSQL vira `timestamptz`.

## A migração

O model mudou. O banco de dev, não. Quem leva a mudança até lá é uma migração.

Antes de mexer no model, rodei o autogenerate uma vez, só para conferir que o banco estava em dia com o código:

```console
$ uv run alembic revision --autogenerate -m "reservas com fuso"
(...)
Generating /home/andrey/PycharmProjects/python-backend-course/alembic/versions/f87706f8de2a_reservas_com_fuso.py ...  done
```

O arquivo saiu com `upgrade` e `downgrade` vazios, só um `pass` em cada. Ótimo: nada pendente. Apaguei e mudei o model. Na segunda vez:

```console
$ uv run alembic revision --autogenerate -m "reservas com fuso"
(...)
INFO  [alembic.autogenerate.compare.types] Detected type change from TIMESTAMP() to DateTime(timezone=True) on 'bookings.starts_at'
INFO  [alembic.autogenerate.compare.types] Detected type change from TIMESTAMP() to DateTime(timezone=True) on 'bookings.ends_at'
Generating /home/andrey/PycharmProjects/python-backend-course/alembic/versions/12388da2dbe5_reservas_com_fuso.py ...  done
```

Ele percebeu a troca. O que ele gerou, para cada coluna:

```python
    op.alter_column('bookings', 'starts_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=False)
```

*(Esse é o arquivo como o autogenerate o deixou. Ele não ficou assim no repositório.)*

Parece pronto. Não está. Falta uma pergunta que o autogenerate não sabe fazer: **os horários que já estão no banco estão em qual fuso?**

### Sem o `USING`, quem decide é a sessão

Converter `timestamp` para `timestamptz` exige um fuso. O valor antigo é um bilhete (`10:00`), e o novo é um instante. Para ir de um ao outro, alguém tem que dizer "10:00 **de onde**". Se a migração não diz, o PostgreSQL usa o `TimeZone` da sessão que está rodando o `ALTER`.

Testei isso no banco de dev, dentro de uma transação desfeita no fim (o `ROLLBACK` devolve tudo como estava). A reserva `1`, a da lição 02, foi gravada como `10:00`:

```console
$ docker compose exec -T postgres psql -U fairfare <<'EOF'
BEGIN;
SET TIME ZONE 'America/Sao_Paulo';
ALTER TABLE bookings ALTER COLUMN starts_at TYPE timestamptz;
SET TIME ZONE 'UTC';
SELECT id, starts_at FROM bookings ORDER BY id;
ROLLBACK;
EOF
BEGIN
SET
ALTER TABLE
SET
 id |       starts_at
----+------------------------
  1 | 2030-01-01 13:00:00+00
(1 row)

ROLLBACK
```

Uma sessão em São Paulo leu `10:00` como "10h de São Paulo" e gravou `13:00` UTC. A reserva andou três horas, sem erro e sem aviso.

Hoje, o container está em `Etc/UTC`, e o `ALTER` sem `USING` daria o resultado certo. Mas daria **por acaso**. É configuração, não decisão. Rode a mesma migração num servidor configurado em outro fuso, e os horários andam.

### A suposição, escrita

O `upgrade` e o `downgrade` finais:

```python
def upgrade() -> None:
    """Upgrade schema."""
    # SUPOSIÇÃO EXPLÍCITA: os horários gravados até aqui, sem fuso, estavam em UTC.
    # Sem o USING, o Postgres converteria pelo TimeZone da sessão — que hoje é UTC
    # no container, mas é configuração, não decisão. Aqui a decisão fica escrita.
    for coluna in ("starts_at", "ends_at"):
        op.alter_column(
            "bookings",
            coluna,
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=f"{coluna} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    """Downgrade schema."""
    for coluna in ("starts_at", "ends_at"):
        op.alter_column(
            "bookings",
            coluna,
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
            postgresql_using=f"{coluna} AT TIME ZONE 'UTC'",
        )
```

O `postgresql_using` vira um `USING` no `ALTER TABLE`: a expressão que calcula o valor novo a partir do antigo. `starts_at AT TIME ZONE 'UTC'` quer dizer "leia este horário de parede como UTC". No `downgrade`, a mesma expressão faz o caminho inverso: pega o instante e devolve o horário de parede em UTC. Troquei também o `postgresql.TIMESTAMP()` gerado por `sa.DateTime()`, que é o mesmo tipo, e o `import` do `postgresql` saiu.

Agora, a parte honesta. **Os horários antigos estavam mesmo em UTC?** Ninguém sabe. Nos capítulos 1 a 3, quem mandou sem fuso gravou o número que mandou. Quem mandou com fuso perdeu o fuso: o `10:00-03:00` virou `10:00`. Olhando para uma linha antiga, não há como saber o que ela queria dizer.

A migração não resolve isso, porque não dá para resolver. Ela **escolhe** UTC, e **escreve a escolha** no lugar onde quem vier depois vai procurar. Se a escolha estiver errada, pelo menos ela está à vista. Um dos exercícios deste capítulo (bloco 1) mostra o que acontece quando ela está errada.

### Rodando

```console
$ uv run alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 4b1f163d18ea -> 12388da2dbe5, reservas com fuso
$ docker compose exec postgres psql -U fairfare -c '\d bookings'
(...)
 starts_at   | timestamp with time zone |           | not null |
 ends_at     | timestamp with time zone |           | not null |
(...)
$ docker compose exec postgres psql -U fairfare -c "SELECT id, starts_at FROM bookings ORDER BY id;"
 id |       starts_at
----+------------------------
  1 | 2030-01-01 10:00:00+00
(1 row)
```

A reserva da lição 02 virou `10:00+00`: 10h em UTC, como a suposição manda. E a volta também funciona. Um `uv run alembic downgrade -1` devolveu `2030-01-01 10:00:00`, sem fuso, e um novo `upgrade head` trouxe o `+00` de volta. O `uv run alembic check` confirma que model e banco batem: `No new upgrade operations detected.`

## E quem manda sem fuso?

O banco agora guarda instantes. Mas a API continua aceitando `"2030-01-01T10:00:00"`, sem fuso. Os testes do `test_smoke.py` mandam assim, e o seu `curl` da lição 02 também. O que fazer com um bilhete?

Três saídas.

**Recusar com 422.** É a mais purista. Só que muda o contrato da API: todo cliente que funciona hoje passaria a receber erro. E este capítulo não muda contrato.

**Deixar o driver decidir.** Não escrever nada, e o `asyncpg` converte o horário sem fuso de algum jeito. Que jeito? Medi, com um script de três linhas que manda `datetime(2030, 1, 1, 10, 0)`, sem fuso, para um `SELECT $1::timestamptz` (o script é um experimento meu, fora do repositório):

```console
$ TZ=UTC uv run python sem_fuso.py
UTC 2030-01-01 10:00:00+00:00
$ TZ=America/Sao_Paulo uv run python sem_fuso.py
America/Sao_Paulo 2030-01-01 13:00:00+00:00
$ TZ=Asia/Tokyo uv run python sem_fuso.py
Asia/Tokyo 2030-01-01 01:00:00+00:00
```

`TZ` é a variável de ambiente que diz ao processo em que fuso a máquina está. O `asyncpg` lê o horário sem fuso **no fuso da máquina onde o app roda**. O mesmo POST grava 10:00, 13:00 ou 01:00 UTC, dependendo do servidor. Mude o app de máquina, e as reservas novas andam. Inaceitável.

**Decidir no app, por escrito.** É a escolha. Um `field_validator` em `BookingCreate`:

```python
    @field_validator("starts_at", "ends_at")
    @classmethod
    def sem_fuso_e_utc(cls, valor: datetime) -> datetime:
        # Horário sem fuso é ambíguo: 10h de onde? Decisão declarada (lição 04):
        # quem não diz o fuso está falando em UTC. Escrita aqui, e não deixada para o
        # driver do banco, que resolveria pelo relógio da máquina onde o app roda.
        if valor.tzinfo is None:
            return valor.replace(tzinfo=UTC)
        return valor
```

Um **`field_validator`** é o primo do `model_validator` que você conhece desde o capítulo 1: ele roda para um campo de cada vez, logo depois de o Pydantic converter o texto em `datetime`, e o que ele devolve vira o valor do campo. `tzinfo` é o fuso de um `datetime`. Se ele é `None`, o horário é um bilhete, e o validator escreve "UTC" nele. Se já tem fuso, passa intacto.

É a mesma filosofia da migração: a suposição existe de qualquer jeito, então que ela fique **escrita**, num lugar só, e não espalhada pela configuração de cada servidor.

E tem teste para isso, com o servidor fingindo estar em São Paulo:

```python
async def test_sem_fuso_e_utc_mesmo_com_o_servidor_em_outro_fuso(client, monkeypatch):
    # A decisão "sem fuso é UTC" não pode depender do relógio da máquina onde o app roda.
    monkeypatch.setenv("TZ", "America/Sao_Paulo")
    time.tzset()
    try:
        user = await cria_usuario(client)
        resource = await cria_recurso(client)
        resp = await cria_reserva(
            client, user["id"], resource["id"], "2030-01-01T10:00:00", "2030-01-01T12:00:00"
        )
    finally:
        monkeypatch.undo()
        time.tzset()
    assert resp.status_code == 201
    assert resp.json()["starts_at"] == "2030-01-01T10:00:00Z"
```

O `monkeypatch.setenv` troca a variável `TZ` só durante o teste. O `time.tzset()` faz o processo reler a `TZ`: sem ele, mudar a variável não muda nada. No `finally`, os dois desfazem a troca, para o fuso falso não vazar para os outros testes.

Um teste desses só vale se ele **falha** sem o conserto. Comentei o `@field_validator` (temporariamente, isso não entrou no commit) e rodei com a máquina em UTC:

```console
$ TZ=UTC uv run pytest tests/test_fuso.py -q
(...)
E       AssertionError: assert '2030-01-01T13:00:00Z' == '2030-01-01T10:00:00Z'
(...)
FAILED tests/test_fuso.py::test_sem_fuso_e_utc_mesmo_com_o_servidor_em_outro_fuso
FAILED tests/test_fuso.py::test_fusos_misturados_sao_422_nao_500 - TypeError:...
2 failed, 4 passed in 0.54s
```

Com a máquina em UTC, o teste "sem fuso é UTC" comum passa mesmo sem o validator, por sorte. O teste com São Paulo pega o `13:00`. É ele que protege a decisão.

## O `cancel`

Uma linha do service muda junto:

```diff
-        if booking.starts_at <= datetime.now():
+        if booking.starts_at <= datetime.now(UTC):
```

`datetime.now()` devolve um horário de parede, o da máquina, sem fuso. `datetime.now(UTC)` devolve o instante, com fuso. E o `starts_at` agora volta do banco **com** fuso. Esqueça de trocar, e os dois testes de cancelamento estouram:

```console
$ uv run pytest -q tests/test_smoke.py
(...)
>       if booking.starts_at <= datetime.now():
E       TypeError: can't compare offset-naive and offset-aware datetimes

app/services/booking.py:51: TypeError
(...)
FAILED tests/test_smoke.py::test_cancela_reserva_futura - TypeError: can't co...
FAILED tests/test_smoke.py::test_nao_cancela_reserva_passada - TypeError: can...
2 failed, 11 passed in 0.89s
```

*(Desfiz a troca só para medir isso. No commit, o `cancel` usa `now(UTC)`.)*

O Python se recusa a comparar um horário com fuso e um sem. E ele tem razão: "é antes ou depois?" não tem resposta se um dos lados é um bilhete.

Repare que o código antigo também estava errado, só que calado. Ele comparava o horário gravado com o relógio **local** da máquina. Numa máquina em `-03:00`, uma reserva gravada para as 10h UTC ainda contava como "futura" por três horas depois de começar.

## De brinde, os fusos misturados

A entrada 3 do `ERRATA.md` cita um terceiro sintoma: `starts_at` com fuso e `ends_at` sem fuso derrubavam a request. Antes do conserto, o teste novo mostrava onde:

```console
    def fim_depois_do_inicio(self):
>       if self.ends_at <= self.starts_at:
E       TypeError: can't compare offset-naive and offset-aware datetimes

app/schemas/booking.py:14: TypeError
```

É o mesmo `TypeError` do `cancel`, agora no `model_validator` do schema. Agora:

```console
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/bookings -H 'content-type: application/json' -d '{"user_id":1,"resource_id":1,"starts_at":"2030-02-02T10:00:00-03:00","ends_at":"2030-02-02T12:00:00"}'
{"detail":[{"type":"value_error","loc":["body"],"msg":"Value error, ends_at deve ser depois de starts_at","input":{"user_id":1,"resource_id":1,"starts_at":"2030-02-02T10:00:00-03:00","ends_at":"2030-02-02T12:00:00"},"ctx":{"error":{}}}]}
422
```

Um 422, com motivo. Ninguém escreveu código para isso. Os `field_validator` rodam **antes** do `model_validator(mode="after")`: quando o schema compara as duas pontas, as duas já têm fuso. E aí a comparação é verdadeira: 10h em São Paulo são 13h UTC, e o fim, lido como UTC, é 12h. Termina antes de começar.

## O `xfail` caiu

A lição 03 prometeu: quando o fuso fosse consertado, o teste marcado ia passar, e o `strict=True` ia deixar a suíte vermelha até alguém tirar a marca. Rodei o `test_fuso.py` da lição 03, com a marca, contra o código novo:

```console
$ uv run pytest -q tests/test_fuso.py
(...)
[XPASS(strict)] o fuso ainda é descartado; no Postgres vira 500 (conserto: lição 04)
1 failed in 0.28s
```

Promessa cumprida. A marca sai:

```diff
-import pytest
+import time

 from tests.apoio import cria_recurso, cria_reserva, cria_usuario


-@pytest.mark.xfail(
-    strict=True,
-    reason="o fuso ainda é descartado; no Postgres vira 500 (conserto: lição 04)",
-)
 async def test_mesmo_instante_em_fusos_diferentes_conflita(client):
```

E cinco testes entram com ela. Além do de São Paulo, que você já viu:

- `test_horario_volta_em_utc`: manda `10:00-03:00`, recebe `13:00:00Z`.
- `test_horario_sem_fuso_e_lido_como_utc`: manda `10:00`, recebe `10:00:00Z`.
- `test_fusos_misturados_sao_422_nao_500`: o caso da seção anterior.
- `test_encostadas_em_fusos_diferentes_nao_conflitam`: uma reserva até 12h em São Paulo e outra começando às 15h UTC, que é o mesmo instante. Encostar não é sobrepor, e os fusos não podem mudar isso.

```console
$ uv run pytest -q -W error
............................                                             [100%]
28 passed in 0.97s
```

Vinte e dois de antes, o do fuso, que era `x` e agora passa, e os cinco novos. Sem `x`. Rodei também com `TZ=UTC` e com `TZ=Asia/Tokyo`: 28 passed nas duas.

E o par de reservas que abriu esta lição, agora contra o app de verdade:

```console
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/bookings -H 'content-type: application/json' -d '{"user_id":1,"resource_id":1,"starts_at":"2030-02-01T10:00:00-03:00","ends_at":"2030-02-01T12:00:00-03:00"}'
{"id":2,"user_id":1,"resource_id":1,"starts_at":"2030-02-01T13:00:00Z","ends_at":"2030-02-01T15:00:00Z","user_nome":"Ana","resource_nome":"Quadra 1"}
201
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/bookings -H 'content-type: application/json' -d '{"user_id":1,"resource_id":1,"starts_at":"2030-02-01T13:00:00Z","ends_at":"2030-02-01T15:00:00Z"}'
{"detail":"o recurso já está reservado nesse horário"}
409
```

**201, depois 409.** O mesmo instante, escrito de dois jeitos, agora é o mesmo instante.

## O que mudou para quem usa a API

Olhe de novo a resposta acima. Você mandou `10:00:00-03:00` e recebeu `13:00:00Z`. O `-03:00` não voltou.

Isso é o `timestamptz` fazendo o que a seção do bilhete disse: ele guarda o instante, não o fuso de quem mandou. O `asyncpg` devolve o instante em UTC, e o Pydantic escreve UTC com um `Z` no fim. A reserva antiga também mudou de cara:

```console
$ curl -s localhost:8000/bookings
[{"id":1,"user_id":1,"resource_id":1,"starts_at":"2030-01-01T10:00:00Z","ends_at":"2030-01-01T12:00:00Z",(...)},(...)]
```

Antes, `"2030-01-01T10:00:00"`. Agora, `"2030-01-01T10:00:00Z"`.

Não é mudança de contrato: o campo continua sendo um `datetime` em ISO 8601, e qualquer cliente que lê ISO 8601 entende o `Z`. Mas é uma mudança **visível**. Um cliente que comparava texto, ou que mostrava o horário cru na tela, vai notar. Fica dito aqui. Mostrar o horário no fuso de quem está olhando é trabalho do cliente, que sabe onde ele está. O servidor fala em instantes.

## O que fica declarado

- **Horário sem fuso é lido como UTC.** Um cliente que manda `10:00` querendo dizer "10h em São Paulo" grava o instante errado, e a API não tem como perceber. É uma decisão, escrita no schema, e não uma garantia.
- **A migração supôs que os horários antigos estavam em UTC.** Linhas gravadas nos capítulos 1 a 3 com outro fuso em mente andaram. Não há como saber quais.
- **As respostas vêm sempre em UTC**, com `Z`, não no fuso que o cliente mandou.
- **A reserva dupla por corrida continua aberta.** Esta lição fechou o caminho do fuso. O de duas requests ao mesmo tempo é das lições 07 a 11.

## O que você deve conseguir fazer agora

- Explicar a diferença entre `timestamp` e `timestamptz`, e por que o `timestamptz` não guarda o fuso de quem mandou.
- Mostrar, com `SET TIME ZONE` no `psql`, o mesmo valor exibido em dois fusos.
- Dizer que suposição a migração `reservas com fuso` fez, onde ela está escrita, e o que o `ALTER` faria sem o `USING`.
- Explicar por que o FairFare decide o fuso de um horário sem fuso no schema, em vez de deixar o driver decidir, e por que não recusa com 422.
- Explicar por que `datetime.now()` virou `datetime.now(UTC)` no `cancel`.
- Explicar por que os fusos misturados viraram 422 sem nenhuma linha nova para isso.
