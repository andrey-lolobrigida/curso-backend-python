# Soluções — capítulo 4

Leia depois de tentar. Uma solução lida antes da tentativa vira informação; depois da tentativa, vira entendimento.

Cada item tem o código consertado, **por que aquele conserto e não outro**, e como você poderia ter chegado nele sozinho.

Todas as mensagens e todos os números daqui saíram da máquina do autor. Os seus vão ser parecidos, não iguais. Os números de processo e de transação, esses, mudam a cada execução.

---

## Bloco 1 — A migração que mudou o passado

### Como localizar, antes de consertar

Olhe a primeira falha com calma:

```
E       AssertionError: assert datetime.datetime(2030, 1, 1, 10, 0, tzinfo=zoneinfo.ZoneInfo(key='Etc/UTC')) == datetime.datetime(2030, 1, 1, 13, 0, tzinfo=datetime.timezone.utc)
```

Saiu 10h, era para sair 13h. A diferença é de **exatamente três horas**. Três horas é o fuso de São Paulo. Quando um horário erra por um número redondo de horas, o defeito quase nunca é aritmética: é alguém lendo o relógio no fuso errado.

E o único lugar da migração que fala de fuso é o `USING`:

```sql
USING inicio AT TIME ZONE 'UTC'
```

Essa linha veio da lição 04. Lá, ela vinha acompanhada de um comentário: *"SUPOSIÇÃO EXPLÍCITA: os horários gravados até aqui, sem fuso, estavam em UTC."* No FairFare, essa era a melhor aposta disponível. No banco do clube, ela é falsa: o enunciado diz que o sistema antigo gravava **no horário de parede de São Paulo**. A migração copiou a expressão e deixou a suposição para trás.

### O conserto

```python
def upgrade(conn: Connection) -> None:
    conn.execute(
        text(
            "ALTER TABLE reservas_do_clube "
            "ALTER COLUMN inicio TYPE timestamptz USING inicio AT TIME ZONE 'America/Sao_Paulo'"
        )
    )
```

`inicio AT TIME ZONE 'America/Sao_Paulo'` quer dizer: "leia este horário de parede como se fosse um relógio de São Paulo, e me dê o instante". Os dois testes passam.

### Por que não `'-03:00'`

Este é o conserto que parece certo. São Paulo é "menos três", então `AT TIME ZONE '-03:00'`. Rodei. **Os dois testes falham**, e falham para o lado errado:

```
E       AssertionError: assert datetime.datetime(2030, 1, 1, 7, 0, tzinfo=zoneinfo.ZoneInfo(key='Etc/UTC')) == datetime.datetime(2030, 1, 1, 13, 0, ...)
E       AssertionError: assert datetime.datetime(2018, 12, 1, 7, 0, tzinfo=zoneinfo.ZoneInfo(key='Etc/UTC')) == datetime.datetime(2018, 12, 1, 12, 0, ...)
```

Sete da manhã. Ele andou três horas, sim, só que **para trás**.

São duas armadilhas empilhadas. Para enxergar as duas de uma vez, pus as variantes lado a lado num `psql`, sobre os mesmos dois horários de parede:

```
          t          |         menos3         |         mais3          |       intervalo        |         utcm3          |           sp
---------------------+------------------------+------------------------+------------------------+------------------------+------------------------
 2030-01-01 10:00:00 | 2030-01-01 07:00:00+00 | 2030-01-01 13:00:00+00 | 2030-01-01 13:00:00+00 | 2030-01-01 07:00:00+00 | 2030-01-01 13:00:00+00
 2018-12-01 10:00:00 | 2018-12-01 07:00:00+00 | 2018-12-01 13:00:00+00 | 2018-12-01 13:00:00+00 | 2018-12-01 07:00:00+00 | 2018-12-01 12:00:00+00
```

As colunas são, na ordem: `'-03:00'`, `'+03:00'`, `INTERVAL '-03:00'`, `'UTC-3'` e `'America/Sao_Paulo'`.

**Armadilha 1: o sinal.** Quando você passa um fuso como texto (`'-03:00'`, `'UTC-3'`), o PostgreSQL o lê no padrão **POSIX**. E no POSIX o sinal é ao contrário do que todo mundo usa: positivo é **a oeste** de Greenwich. `'-03:00'` vira "três horas a leste", o fuso de Moscou. Daí o 7h. O `INTERVAL '-03:00'` não sofre disso, porque um intervalo usa o sinal de sempre (o da ISO 8601). E o `'+03:00'`, que parece o sinal errado, é justamente o que o POSIX lê como três horas a oeste: o −3 de São Paulo.

**Armadilha 2: o horário de verão.** Repare nas colunas `mais3` e `intervalo`. Acertam 2030 (13h) e erram 2018 (13h, quando devia ser 12h). Com qualquer uma delas, o primeiro teste passa e o segundo falha:

```
E       AssertionError: assert datetime.datetime(2018, 12, 1, 13, 0, tzinfo=zoneinfo.ZoneInfo(key='Etc/UTC')) == datetime.datetime(2018, 12, 1, 12, 0, tzinfo=datetime.timezone.utc)
```

É o conserto que o README chamou de "passa só no primeiro teste". Em dezembro de 2018, São Paulo estava no horário de verão: o relógio estava adiantado uma hora, e o fuso era **UTC−2**. 10h lá eram 12h em UTC, e não 13h. O Brasil só aboliu o horário de verão em 2019.

### Por que o nome do fuso resolve as duas

`'-03:00'` é um **offset**: um número fixo de horas. Ele não sabe nada sobre datas.

`'America/Sao_Paulo'` é o nome de uma entrada no **tz database** (o banco de fusos que o PostgreSQL, o Python e quase todo sistema operacional usam). Essa entrada guarda a **história** das regras: em que anos teve horário de verão, de que dia a que dia, e quando acabou. O PostgreSQL olha a data de cada linha e aplica a regra que valia naquela data. Para 2030, −3. Para dezembro de 2018, −2.

Um offset é uma foto de uma regra. Um nome de fuso é o arquivo de todas elas. Quando os dados atravessam anos, só o segundo serve.

Uma última sutileza, só para você saber que existe: para datas **futuras**, como 2030, o tz database aplica as regras de hoje. Se o Brasil voltar com o horário de verão, o arquivo muda, e a conta para 2030 muda junto. Para o passado, a história já está escrita.

### A moral

A migração rodou sem erro, sem aviso, e mudou o horário de todas as reservas. É o pior tipo de defeito: o que não faz barulho. A lição 04 não errou ao escolher UTC. Ela **escreveu a escolha**. O erro foi copiar a expressão sem copiar a pergunta: "em que fuso estavam os horários antigos?". Essa pergunta é refeita a cada banco, e a resposta nunca vem do código. Vem de quem conhece os dados.

---

## Bloco 2 — O banco sob carga

### 2.1 — O `count()`

O conserto, em `repositorio.py` (importando `func` do `sqlalchemy`):

```python
    async def count(self) -> int:
        return await self.conn.scalar(select(func.count()).select_from(reservas))
```

O SQL que sai é `SELECT count(*) FROM bloco2_reservas`. O banco conta, e devolve **um** número. `scalar` pega a primeira coluna da primeira linha, que é esse número.

Os tempos, com `-s`, na máquina do autor:

| versão | tempo do `count()` |
|---|---|
| `len(resultado.all())` | 0,192 s, 0,193 s, 0,221 s |
| `select(func.count())` | 0,010 s, 0,009 s, 0,009 s, 0,009 s, 0,009 s |

Uns vinte vezes mais rápido. E a diferença cresce com a tabela.

**Por que o caminho antigo é tão caro.** Ele pede ao banco "me manda tudo". São 200 mil linhas serializadas pelo PostgreSQL, atravessando a rede (aqui, só até o container, que é o caso mais barato possível), desempacotadas pelo `asyncpg`, viradas em objetos `Row` pelo SQLAlchemy e guardadas numa lista. Tudo isso para o `len` olhar o tamanho da lista e jogar a lista fora. O `count(*)` faz a contagem onde os dados já estão.

Regra geral, e ela vai voltar: **mande a pergunta para onde os dados moram, e traga só a resposta.** Contar, somar, filtrar, ordenar: o banco faz isso melhor e sem gastar rede.

Uma curiosidade, sem aprofundar: mesmo no banco, `count(*)` não é instantâneo no PostgreSQL. Ele não guarda o total pronto, porque cada transação pode estar vendo uma versão diferente da tabela (é o **MVCC**, o mecanismo que dá um retrato próprio para cada transação, e que você viu em ação na lição 09). Para contar, ele precisa conferir quais linhas aquela transação enxerga. Os 9 ms são isso.

**Como chegar nele sozinho.** O teste te deu a pista sem rodeio: o SQL enviado não tem `count(`. A pergunta seguinte é "como se escreve `count(*)` no SQLAlchemy?", e a resposta é `func.count()`. O `func` você já viu na lição 11, no `func.tstzrange`: qualquer função do SQL sai dele.

### 2.2 — O vazamento

O conserto, em `vazamento.py`:

```python
async def get_db():
    async with SessionLocal() as db:
        yield db
```

Uma linha virou um `async with`, e o resto entrou nele. É o mesmo corpo do `get_db` do `app/database.py` do FairFare.

**O que estava errado.** O código quebrado criava a sessão e entregava, e ninguém a fechava. Quando a request termina, o FastAPI continua o gerador depois do `yield`. No código quebrado, depois do `yield` não tem nada. A sessão fica com a conexão na mão, e ninguém a devolve ao pool.

Com o `async with`, a saída do bloco chama `close()` na sessão. E o `close()` devolve a conexão ao pool. Sempre: com resposta 200, com exceção, com o que for.

**E por que o app ainda funcionava às vezes.** É a parte traiçoeira, e vale entender o mecanismo, porque ele vai te enganar em produção.

A sessão abandonada vira lixo. Mas ela não é recolhida na hora: o fato de o pool secar sem o `gc.collect()` mostra que a contagem de referências do Python, sozinha, não a solta. Quem a recolhe é o **coletor de lixo** de ciclos, quando ele resolver passar. E ele não devolve a conexão ao pool. Leia o que o SQLAlchemy escreve no log:

```
The garbage collector is trying to clean up non-checked-in connection <AdaptedConnection <asyncpg.connection.Connection object at 0x73f07ff0f200>>, which will be terminated.
```

*"Which will be terminated."* A conexão é **encerrada**, não devolvida. O pool percebe que ela sumiu, desconta, e a vaga reabre. A próxima request que precisar paga o preço de abrir uma conexão nova do zero (handshake, autenticação: o que a lição 09 do capítulo 2 disse que o pool existe para evitar).

Isso é um resgate eventual, e não dá para contar com ele. Sem o `gc.collect()` forçado, o autor rodou o teste oito vezes. O coletor salvou as primeiras dezenas de requests em todas, e mesmo assim o pool secou em todas: uma vez na request 87, sete vezes na 98.

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 2.00 (Background on this error at: https://sqlalche.me/e/20/3o7r)
```

O número da request não diz nada sobre o seu código. Depende de quando o coletor resolveu passar, e isso depende de quanto lixo o resto do processo produziu. Em outra máquina, com outro tráfego, é outro número. Por isso o teste chama `gc.collect()` depois de cada request e **reprova** se o coletor precisou recolher alguma conexão: ele não aceita o resgate como conserto.

Agora leve isso para o FairFare de verdade, com `pool_timeout=30`. Quando o coletor atrasa e as quinze vagas estão presas, a próxima request não falha na hora. Ela **espera** trinta segundos na fila do pool (lição 05) e só então vira `500`. O usuário vê meio minuto de nada, e depois um erro. Num gráfico, aparece como "o app às vezes trava", sem padrão. O mais difícil de depurar é justamente isto: o defeito está em toda request, mas o sintoma só aparece de vez em quando.

A regra é a do capítulo 2, lição 09: o pool **empresta** conexões, e quem pega emprestado devolve. Devolver não pode depender de ninguém lembrar, e muito menos do coletor de lixo. O `async with` é a forma de escrever "devolve sempre" que o Python garante.

**Como chegar nele sozinho.** O enunciado disse: "repare em quem devolve a conexão". Leia o `get_db` procurando quem fecha a sessão. Não tem ninguém. Depois compare com o `get_db` do `app/database.py`, que você usa desde o capítulo 1. A diferença é o conserto. E a mensagem do log, de novo, entrega o resto: *"Please ensure that SQLAlchemy pooled connections are returned to the pool explicitly, either by calling ``close()`` or by using appropriate context managers"*. *Context manager* é o nome do que o `async with` usa.

### 2.3 — O índice que o planner ignora

O conserto, em `consulta.py`:

```python
from datetime import UTC, date, datetime, time, timedelta

...

def reservas_do_dia(dia: date) -> Select:
    """As reservas que começam em `dia` (um dia em UTC)."""
    inicio = datetime.combine(dia, time(0, 0), tzinfo=UTC)
    fim = inicio + timedelta(days=1)
    return select(agenda).where(agenda.c.starts_at >= inicio, agenda.c.starts_at < fim)
```

O `func` sai do import, porque ninguém mais o usa. Os dois testes passam: o resultado continua 1440 linhas, e o plano mudou.

**Por que o índice não servia.** Volte à lição 06. Um btree guarda os valores **em ordem**. O índice de `bloco2_agenda` guarda os `starts_at` em ordem. Ele sabe responder perguntas sobre `starts_at`: "qual é igual a X", "quais estão entre X e Y".

A consulta quebrada não perguntava sobre `starts_at`. Ela perguntava sobre `date(starts_at)`, que é **outro valor**, calculado a partir do primeiro. O índice não tem esse valor guardado. O único jeito de responder é calcular `date()` em cada uma das cem mil linhas e comparar. É o `Seq Scan` com `Filter`:

```
 Seq Scan on bloco2_agenda  (cost=0.00..2041.00 rows=500 width=12) (actual time=0.119..5.519 rows=1440.00 loops=1)
   Filter: (date(starts_at) = '2030-01-02'::date)
   Rows Removed by Filter: 98560
 Execution Time: 5.555 ms
```

O conserto faz **a mesma pergunta em outra forma**. "Começa no dia 2" é o mesmo que "começa a partir da meia-noite do dia 2 e antes da meia-noite do dia 3". E essa forma fala de `starts_at` puro, um intervalo, exatamente o que o btree sabe percorrer:

```
 Index Scan using ix_bloco2_agenda_starts_at on bloco2_agenda  (cost=0.29..60.57 rows=1464 width=12) (actual time=0.005..0.116 rows=1440.00 loops=1)
   Index Cond: ((starts_at >= '2030-01-02 00:00:00+00'::timestamp with time zone) AND (starts_at < '2030-01-03 00:00:00+00'::timestamp with time zone))
 Execution Time: 0.152 ms
```

De 5,6 ms para 0,15 ms. Repare que o `Filter` virou `Index Cond`: a condição agora é resolvida dentro do índice. E repare no `<`, e não `<=`, na ponta de cima. Com `<=`, a reserva da meia-noite do dia 3 entraria no dia 2 também.

É a mesma ideia da seção "O índice que só serve à consulta escrita na forma dele", da lição 11. Lá, o gist só ajudou quando a consulta passou a usar o `&&` sobre o `tstzrange`. Aqui, o btree só ajuda quando a consulta para de embrulhar a coluna numa função. Mesma pergunta, outra forma, e o planejador não faz essa tradução por você.

**Bônus 1: por que não um índice em `date(starts_at)`?** O enunciado proibiu, mas vale saber que nem daria. Tentei:

```
CREATE INDEX ix_dia ON bloco2_agenda (date(starts_at));
ERROR:  functions in index expression must be marked IMMUTABLE
```

*Immutable* é a promessa de que a função devolve sempre a mesma saída para a mesma entrada. `date()` de um `timestamptz` não cumpre. Lembre da lição 04: o `timestamptz` guarda o instante, e mostra no fuso **da sessão**. `date()` faz a mesma coisa: ele pega o dia no fuso da sessão. Medi. Com `SET LOCAL TimeZone = 'America/Sao_Paulo'`, o `WHERE date(starts_at) = '2030-01-02'` devolve 1440 linhas de `2030-01-02 03:00` a `2030-01-03 02:59` UTC. A mesma linha cai em dias diferentes conforme quem pergunta. Um índice não pode guardar uma resposta que muda com a sessão.

Isso quer dizer que a consulta quebrada tinha um segundo defeito, escondido: o resultado dela dependia do `TimeZone` da conexão. O teste passava porque o container está em UTC. A consertada não depende de nada disso. A meia-noite está escrita nela, em UTC.

**Bônus 2: o dia de quem?** "Reservas do dia 2" é uma pergunta sem resposta até alguém dizer **em que fuso** é o dia. Aqui, a docstring decide: UTC. É a mesma filosofia da lição 04. A suposição existe de qualquer jeito, então que ela fique escrita.

**Como chegar nele sozinho.** O `Filter` do plano diz `date(starts_at) = ...`. O índice se chama `ix_bloco2_agenda_starts_at`. Ponha os dois lado a lado: o que está indexado é `starts_at`, e o que está sendo perguntado é `date(starts_at)`. A partir daí a pergunta é só: "como escrevo 'é do dia 2' falando só de `starts_at`?".

---

## Bloco 3 — A concorrência

### 3.1 — O retry no cadáver

O conserto, em `retry.py`:

```python
import asyncio
import random
from datetime import datetime

...

async def reservar(engine: AsyncEngine, recurso: int, inicio: datetime, fim: datetime) -> str:
    """Devolve "criada" ou "conflito"."""
    params = {"r": recurso, "inicio": inicio, "fim": fim}
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="SERIALIZABLE")
        for tentativa in range(1, 6):
            try:
                if await conn.scalar(VERIFICA, params):
                    await conn.rollback()
                    return "conflito"
                await conn.execute(INSERE, params)
                await conn.commit()
                return "criada"
            except DBAPIError as erro:
                if _abortada(erro):
                    await conn.rollback()  # a transação morreu: enterre-a antes de tentar de novo
                    # espere o vencedor terminar o COMMIT: 20, 40, 80, 160 ms, com sorteio de ±50%
                    await asyncio.sleep(0.01 * 2**tentativa * random.uniform(0.5, 1.5))
                    continue  # tenta de novo
                raise
    raise RuntimeError("cinco tentativas e nada")
```

São dois consertos, e eles chegam em ordem. Um é de lógica. O outro é de tempo.

#### Primeiro conserto: o `rollback()`

**Onde o `40001` nasce.** Na lição 09 ele saía às vezes no `COMMIT`, às vezes no `INSERT`. Contei, com uma tentativa só por reserva, 20 rodadas de 5: das 80 perdedoras, 36 levaram o `40001` no `COMMIT` e 44 no `INSERT`. Os dois lugares, com frequência parecida.

**Por que escapam duas exceções diferentes.** Nos dois casos o `except` pega o `40001`, o `_abortada` diz que sim, e o laço dá `continue`. E aí a próxima volta manda o `SELECT` numa transação que já morreu. Quem reclama depende de quem percebeu a morte primeiro:

- **`40001` no `COMMIT`.** O SQLAlchemy viu o `COMMIT` falhar e marcou a conexão como "transação inválida". Ele mesmo recusa o `SELECT` seguinte, sem nem mandar ao banco:

  ```
  E       sqlalchemy.exc.PendingRollbackError: Can't reconnect until invalid transaction is rolled back.  Please rollback() fully before proceeding (Background on this error at: https://sqlalche.me/e/20/8s2b)
  ```

  O `PendingRollbackError` não é um `DBAPIError`, então o `except` nem o pega. Ele escapa direto.

- **`40001` no `INSERT`.** Aqui quem sabe da morte é o PostgreSQL. O `SELECT` vai até ele, e ele responde com outro código, `25P02`:

  ```
  E                   sqlalchemy.exc.DBAPIError: (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'asyncpg.exceptions.InFailedSQLTransactionError'>: current transaction is aborted, commands ignored until end of transaction block
  E                   [SQL: SELECT count(*) FROM bloco3_reservas WHERE resource_id = $1 AND starts_at < $2 AND ends_at > $3]
  ```

  Esse é um `DBAPIError`, mas o `sqlstate` não é `40001`. O `_abortada` diz que não, e o `raise` o deixa sair.

No teste inteiro, a primeira a escapar foi a `PendingRollbackError` em 14 de 15 execuções, e a `InFailedSQLTransactionError` em 1. As duas dizem a mesma frase: **a transação está morta, e nada roda nela até você enterrá-la.** O PostgreSQL diz "commands ignored until end of transaction block". O SQLAlchemy diz "please rollback() fully". A segunda mensagem até te dá o conserto por escrito.

Volte à frase da lição 09: **tentar de novo é começar outra transação do zero.** O código quebrado tentava de novo **dentro** da transação morta. O `rollback()` encerra a morta, e o próximo comando abre uma nova automaticamente (o `connect()` do SQLAlchemy abre transação no primeiro comando, sozinho). O nível `SERIALIZABLE` continua valendo, porque ele foi posto na conexão, e não na transação. A nova tentativa faz o `SELECT` com um retrato novo, vê (ou não) a reserva da vencedora, e decide de novo.

#### Segundo conserto: esperar, e esperar diferente

Só com o `rollback()`, o teste fica verde na maioria das vezes. Rodei 30 vezes: **7 falharam**, todas com:

```
RuntimeError: cinco tentativas e nada
```

Como o README avisou, isso é um passo adiante. O retry agora funciona. Ele só é rápido demais.

A lição 09 já tinha o diagnóstico. A vencedora manda o `COMMIT` e espera o disco confirmar: uns 3 ms em geral, às vezes mais de 80 ms. A perdedora faz uma tentativa inteira em menos de 1 ms. Num log de uma rodada ruim, com o tempo em milissegundos, a vencedora mandou o `INSERT` em ~6587 e o `COMMIT` só confirmou em 6666,8. Oitenta milissegundos. Nesse meio-tempo, uma perdedora gastou as cinco tentativas e desistiu, em 6654. Cinco tentativas inteiras dentro de um `COMMIT` lento. Em cada uma, ela olhava, via a quadra ainda livre, tentava inserir e levava outro `40001`.

A saída é **esperar entre as tentativas**. Esperar quanto é a pergunta difícil, e eu testei algumas respostas, cada uma em levas de 25 a 60 execuções do teste:

| pausa depois do `rollback()` | resultado |
|---|---|
| nenhuma | 7 de 30 falharam |
| `random.uniform(0, 0.01)` | 19 de 30 falharam (pior que nenhuma!) |
| `random.uniform(0, 0.05)` | 0 de 30 falharam numa leva; 4 de 40 e 7 de 30 noutras |
| `random.uniform(0, 0.01 * 2**tentativa)` | 40 de 40 passaram numa leva; 9 de 60 falharam noutra |
| `0.01 * 2**tentativa * random.uniform(0.5, 1.5)` | 25 de 25 passaram no pytest; 500 de 500 rodadas no script avulso |

A última linha é o conserto. Ela junta três ideias:

- **Crescer a cada tentativa** (`2**tentativa`): 20, 40, 80, 160 ms. Se a primeira espera não bastou, o problema provavelmente é maior do que você achou, então espere mais. Isso tem nome: **backoff exponencial**.
- **Sortear** (`random.uniform(...)`): se as quatro perdedoras esperarem exatamente o mesmo tempo, elas voltam juntas e colidem de novo. O sorteio espalha as voltas. Isso também tem nome: **jitter**.
- **Ter um piso** (`0.5` a `1.5`, e não `0` a `1`): a espera nunca é quase nada. Somando as quatro primeiras pausas, são pelo menos 150 ms antes da quinta tentativa. Cobre o `COMMIT` lento de 80 ms com folga.

Esses números são de uma máquina tranquila. Com a máquina ocupada, tudo piora, porque tempo é justamente o que a carga rouba. Medi de novo com a máquina ocupada, com outros quatro PostgreSQL rodando ao lado: só o `rollback()` falhou 14 de 20 vezes, e o conserto de referência falhou 5 de 50 numa leva e 1 de 50 noutra. Por isso o "pronto" do README aceita uma falha rara.

A tabela mostra por que o piso importa. As variantes que sorteiam a partir de zero podem tirar quatro pausas quase nulas seguidas, e aí é como não ter pausa. A de 0 a 10 ms ficou até **pior** que nenhuma. Não sei explicar isso com certeza, e não fui atrás: fica como dado medido, e como aviso de que intuição sobre espera engana.

Com o conserto, a distribuição de tentativas em 5 levas de 100 rodadas ficou assim, em formato (tentativa, quantas terminaram nela): `[(1, 100), (2, 372), (3, 7), (4, 21)]`, `[(1, 100), (2, 368), (3, 6), (4, 26)]`, `[(1, 100), (2, 356), (3, 24), (4, 19), (5, 1)]`, `[(1, 100), (2, 396), (3, 4)]`, `[(1, 100), (2, 400)]`. A primeira tentativa são as 100 vencedoras. Quase todo o resto resolve na segunda. Uma única vez em 500 chamadas precisou da quinta.

Agora a honestidade obrigatória: **este teste mede uma probabilidade.** Ele não tem como provar que o conserto está certo. Ele mostra que, nesta máquina, a chance de falhar ficou muito pequena. Num disco bem mais lento, com `COMMIT` de 500 ms, até o conserto correto pode ficar vermelho de vez em quando. Esse é o preço de um retry com número fixo de tentativas, e não tem como fugir dele. O que dá é escolher o número e a espera sabendo o que se está medindo.

Um detalhe pequeno que o conserto de referência deixou passar: na quinta falha, ele ainda dorme (uns 320 ms) antes de desistir. Uma espera que não serve para nada. Um `if tentativa < 5:` antes do `sleep` resolve. Não muda o teste.

O backoff aqui é uma prévia. Tempo, espera e quantas vezes insistir são o assunto do capítulo 9, de falhas e observabilidade, com a conversa completa: limite de tentativas, teto de espera, e quando não tentar de novo de jeito nenhum.

**Como chegar nele sozinho.** O primeiro conserto está escrito na própria mensagem: *"Please rollback() fully before proceeding"*. E o `[SQL: SELECT count(*) ...]` da outra mensagem mostra que quem falhou foi o `SELECT` da tentativa **seguinte**, e não o `INSERT`: o erro estava no recomeço, e não no meio. Para o segundo, o caminho é a aritmética que o README sugeriu: uma tentativa custa menos de 1 ms, um `COMMIT` pode custar 80. Cinco vezes menos de 1 é menos de 5. Para cobrir 80, alguém tem que esperar.

### 3.2 — O deadlock das duas quadras

O conserto, em `deadlock.py`:

```python
async def reservar_par(engine: AsyncEngine, quadras: tuple[int, int]) -> None:
    async with engine.begin() as conn:
        for quadra in sorted(quadras):  # todo mundo tranca na mesma ordem: menor id primeiro
            await conn.execute(TRANCA, {"id": quadra})
            await asyncio.sleep(0.01)  # o tempo de olhar a agenda de cada quadra
        # (aqui entrariam a verificação e os inserts; o que importa neste bloco são os locks)
```

Uma palavra: `sorted`. O `FOR UPDATE` continua, o `sleep` continua, os dois clientes continuam pedindo na ordem que quiserem.

**O que é um deadlock.** Leia o `DETAIL` como uma história:

```
E   asyncpg.exceptions.DeadlockDetectedError: deadlock detected
E   DETAIL:  Process 296293 waits for ShareLock on transaction 17950; blocked by process 296294.
E   Process 296294 waits for ShareLock on transaction 17949; blocked by process 296293.
E   HINT:  See server log for query details.
```

Um dos processos é o cliente `(1, 2)`: trancou a quadra 1 e foi pedir a 2. O outro é o cliente `(2, 1)`: trancou a 2 e foi pedir a 1. Cada um segura o que o outro quer, e cada um só solta quando terminar. Nenhum vai terminar.

A analogia é a de dois carros numa ponte de uma pista só, entrando um de cada lado. Cada um espera o outro dar ré. Nenhum dá.

O nome técnico é **ciclo de esperas**: A espera B, B espera A. Com três transações, o ciclo pode ser A → B → C → A, e a ideia é a mesma.

Um detalhe do `DETAIL` que confunde na primeira leitura: ele diz "waits for ShareLock on **transaction** 17950", e não "na linha da quadra 2". É assim que o PostgreSQL implementa a espera por uma linha trancada: quem quer a linha espera **a transação que a trancou** terminar. Na prática, dá no mesmo. 17950 é a transação do outro cliente.

**Quem desfaz o nó.** Ninguém, por um tempo. O PostgreSQL não procura ciclos a cada espera, porque isso seria caro e quase sempre inútil: a maioria das esperas termina sozinha. Ele espera um tempo, o `deadlock_timeout`, e só então olha se a espera faz parte de um ciclo:

```console
$ docker compose exec postgres psql -U fairfare -c "SHOW deadlock_timeout"
 deadlock_timeout 
------------------
 1s
(1 row)
```

Um segundo. Achou o ciclo, ele escolhe uma das transações e a mata com `deadlock detected`. A outra segue. Para o usuário da vítima, é um erro depois de um segundo de espera parado.

**Por que a ordem resolve.** Um ciclo precisa de alguém trancando "1 depois 2" e alguém trancando "2 depois 1". Se **todo mundo** tranca na mesma ordem global, o menor id primeiro, o ciclo não tem como se formar. Os dois clientes vão atrás da quadra 1 primeiro. Um ganha, o outro espera **antes de trancar qualquer coisa**. Quem espera não segura nada, então não bloqueia ninguém. O vencedor tranca a 2, termina, solta as duas, e o segundo segue.

Repare que o conserto não diminuiu a espera: o segundo cliente continua esperando o primeiro. Ele transformou uma espera que **nunca acaba** (e que o banco resolve na marra, matando alguém) numa espera que **acaba sozinha**. Fila, e não nó.

Esse princípio não é do PostgreSQL. Vale para qualquer sistema com mais de um cadeado: threads com mais de um `Lock`, arquivos trancados, mutexes no sistema operacional. **Se você precisa de mais de um cadeado ao mesmo tempo, combine uma ordem e respeite-a sempre.** Ordenar pelo id é a ordem mais fácil de combinar, porque todo mundo já tem o id na mão.

E vai voltar. No capítulo 5, as **quitações** entre membros de um grupo mexem em dois lados ao mesmo tempo: quem paga e quem recebe. É um `FOR UPDATE` em duas linhas, com dois pedidos chegando em direções opostas. Exatamente este bloco, com dinheiro no lugar das quadras.

**Como chegar nele sozinho.** O teste já mostra o padrão: um cliente pede `(1, 2)`, o outro pede `(2, 1)`. A mesma dupla, ordens opostas. O `DETAIL` confirma que é um ciclo. E a regra do enunciado ("cada um na ordem que quiser") diz que você não pode mexer em quem pede. Só sobra mexer em **como** o pedido é atendido: a função recebe a ordem do cliente e tranca na ordem dela.

---

## O fio que costura os três blocos

Olhe o que cada conserto mudou. No bloco 1, a leitura de um relógio. No 2.2, quando uma conexão volta. No 3.1, quanto esperar antes de insistir. No 3.2, a ordem em que se pede.

Quase nenhum dos defeitos era lógica errada no sentido de sempre. A conta da migração estava certa para o fuso errado. O retry estava certo e rápido demais. Os dois clientes do deadlock faziam, cada um sozinho, exatamente o que deviam. O que quebrou foi **tempo**: fuso, ordem, espera, e quem chega primeiro.

E quase nenhum fez barulho na primeira vez. A migração rodou limpa. O vazamento funcionou dezenas de vezes antes de secar o pool. O retry sem o backoff passa na maioria das execuções, numa máquina tranquila. Um banco de verdade, com mais de uma pessoa usando ao mesmo tempo, é onde "funcionou aqui" para de ser prova de qualquer coisa. A prova passa a ser o teste que mede, e a mensagem de erro lida até o fim.
