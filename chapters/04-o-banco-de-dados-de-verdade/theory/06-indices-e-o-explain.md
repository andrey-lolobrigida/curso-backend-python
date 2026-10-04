# Lição 06 — Índices e o `EXPLAIN`

Toda vez que alguém tenta reservar uma quadra, o FairFare pergunta ao banco: "já tem alguém nesse horário?". Com as poucas reservas do seu banco de dev, a resposta vem antes de você piscar. Com qualquer número de reservas que caiba na sua cabeça, também.

Esta lição pergunta o que acontece com **um milhão**. E, mais importante, ensina a perguntar isso ao próprio banco, em vez de chutar.

## A consulta que roda em toda reserva

Ela mora no repository, desde o capítulo 1:

```python
    async def find_overlapping(
        self, resource_id: int, starts_at: datetime, ends_at: datetime
    ) -> list[Booking]:
        stmt = select(Booking).where(
            Booking.resource_id == resource_id,
            Booking.starts_at < ends_at,
            Booking.ends_at > starts_at,
        )
        resultado = await self.db.scalars(stmt)
        return list(resultado)
```

O banco não recebe Python. Recebe SQL. Dá para ver o SQL que o SQLAlchemy escreve sem subir nada, pedindo para ele compilar a consulta:

```console
$ uv run python -c "
from datetime import datetime, UTC
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from app.models import Booking
s=datetime(2031,1,1,10,tzinfo=UTC); e=datetime(2031,1,1,12,tzinfo=UTC)
stmt = select(Booking).where(Booking.resource_id == 7, Booking.starts_at < e, Booking.ends_at > s)
print(stmt.compile(dialect=postgresql.asyncpg.dialect()))
"
SELECT bookings.id, bookings.user_id, bookings.resource_id, bookings.starts_at, bookings.ends_at 
FROM bookings 
WHERE bookings.resource_id = $1::INTEGER AND bookings.starts_at < $2::TIMESTAMP WITH TIME ZONE AND bookings.ends_at > $3::TIMESTAMP WITH TIME ZONE
```

Os `$1`, `$2` e `$3` são os parâmetros: o asyncpg manda os valores separados do texto. É o `$2` da lição 02, aliás. A bancada tem essa consulta com valores fixos, em `bancada/explain.sql`: recurso 7, das 10h às 12h de 1º de janeiro de 2031.

## Volume

Para perguntar sobre um milhão de reservas, é preciso ter um milhão de reservas. Criar uma por uma pela API levaria horas. O Postgres tem um atalho: `generate_series(0, N)` é uma função que devolve uma tabela de números, de 0 a N. Junte com um `INSERT ... SELECT`, e cada número vira uma linha.

O coração do `bancada/seed.sql`:

```sql
INSERT INTO bookings (user_id, resource_id, starts_at, ends_at)
SELECT 1,
       i % 50 + 1,
       timestamptz '2030-01-01 00:00+00' + (i / 50) * interval '1 hour',
       timestamptz '2030-01-01 00:00+00' + (i / 50 + 1) * interval '1 hour'
FROM generate_series(0, :linhas - 1) i;
```

O `i % 50 + 1` distribui as reservas pelas 50 quadras, em rodízio. O `i / 50` é divisão inteira: as linhas 0 a 49 caem na primeira hora, as 50 a 99 na segunda, e assim por diante. Cada quadra fica com reservas de uma hora, encostadas, **sem nenhuma sobreposição**. Isso vai importar na lição 11. O `:linhas` é uma variável do `psql`, que você passa com `-v`.

**Atenção:** o script começa com um `TRUNCATE` em `users`, `resources` e `bookings`. Ele **apaga** o seu banco de dev. É uma bancada, não uma migração.

```console
$ B=chapters/04-o-banco-de-dados-de-verdade/bancada
$ docker compose exec -T postgres psql -U fairfare -d fairfare -v linhas=1000000 < $B/seed.sql
...
INSERT 0 1000000
Time: 18147.952 ms (00:18.148)
ANALYZE
Time: 102.688 ms
```

Dezoito segundos. Nas rodadas seguintes, deu 24 e 22. *(Por curiosidade, medi onde vai esse tempo. Metade são as chaves estrangeiras: cada reserva confere se o usuário e o recurso existem, e sem essa conferência o milhão saiu em 11 s. O resto é quase todo disco. Gerar o mesmo milhão numa tabela temporária, que não passa pelo log de segurança do Postgres, levou meio segundo. Numa máquina com disco mais rápido, o seed cai bastante.)*

O `ANALYZE` no fim não é enfeite. Ele atualiza as **estatísticas** da tabela: quantas linhas há, como os valores se distribuem. O Postgres usa isso para decidir como executar cada consulta. Sem ele, o banco decide no escuro.

## Ler um plano

O `explain.sql` não roda a consulta "seca". Ele a roda com um prefixo:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM bookings
WHERE resource_id = 7
  AND starts_at < timestamptz '2031-01-01 12:00+00'
  AND ends_at > timestamptz '2031-01-01 10:00+00';
```

O `EXPLAIN` pede ao Postgres o **plano**: a receita que ele escolheu para achar as linhas. Com um milhão de reservas e sem índice nenhum além da chave primária:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare < $B/explain.sql
                                                                                 QUERY PLAN
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 Gather  (cost=1000.00..16138.37 rows=4937 width=28) (actual time=14.841..16.781 rows=2.00 loops=1)
   Workers Planned: 2
   Workers Launched: 2
   Buffers: shared hit=7353
   ->  Parallel Seq Scan on bookings  (cost=0.00..14644.67 rows=2057 width=28) (actual time=10.689..13.018 rows=0.67 loops=3)
         Filter: ((starts_at < '2031-01-01 12:00:00+00'::timestamp with time zone) AND (ends_at > '2031-01-01 10:00:00+00'::timestamp with time zone) AND (resource_id = 7))
         Rows Removed by Filter: 333333
         Buffers: shared hit=7353
 Planning:
   Buffers: shared hit=80
 Planning Time: 0.178 ms
 Execution Time: 16.806 ms
(12 rows)
```

Parece um muro. Vamos por partes.

Pense num livro de mil páginas **sem índice remissivo** no fim. Você quer achar onde ele fala de "quadra 7, janeiro de 2031". Não tem jeito: você lê o livro inteiro, página por página, e anota o que serve. Se tiver dois amigos, divide o livro em três e cada um lê um pedaço.

Foi exatamente isso que o Postgres fez. Agora o rigor:

- **O plano é uma árvore de nós.** Cada `->` é um nó, e ele entrega linhas para o nó de cima. Lê-se de dentro para fora.
- **`Seq Scan`** é a leitura sequencial: a tabela inteira, do começo ao fim. **`Parallel`** quer dizer que o trabalho foi dividido. O `Workers Launched: 2` são os dois amigos, e o processo da conexão também lê, por isso `loops=3`. O **`Gather`** é o nó que junta o que os três acharam.
- **`Filter`** é a condição aplicada linha a linha, depois de ler. **`Rows Removed by Filter: 333333`** é por loop: três vezes isso, um milhão de linhas lidas e jogadas fora, para entregar **`rows=2`**. As duas reservas das 10h às 11h e das 11h às 12h.
- **`cost=0.00..14644.67`** é a **estimativa** do planner, numa unidade própria e arbitrária (não é milissegundo). O primeiro número é o custo até a primeira linha, o segundo até a última. Ao lado, `rows=2057` é quantas linhas ele **achou** que viriam.
- **`actual time=...`** e o outro `rows=` são o que **aconteceu de fato**, em milissegundos.
- **`Buffers: shared hit=7353`** são as páginas lidas. O Postgres guarda a tabela em páginas de 8 kB, e "hit" quer dizer que estavam na memória dele. 7353 × 8 kB dá uns 57 MB, que é a tabela inteira.
- **`Execution Time: 16.806 ms`**, o número que você quer olhar primeiro.

E a diferença que mais pega gente: **`EXPLAIN` sozinho só planeja.** Ele mostra os `cost=` e para por aí. **`EXPLAIN ANALYZE` executa a consulta de verdade** para poder medir. Num `SELECT`, tanto faz. Num `DELETE`, ele **apaga as linhas**. Se for analisar uma escrita, faça dentro de um `BEGIN` ... `ROLLBACK`.

Repare também no desencontro: o planner estimou 4937 linhas e vieram 2. Ele calcula a chance de cada condição separadamente e multiplica, como se `starts_at` e `ends_at` não tivessem nada a ver um com o outro. Aqui eles têm tudo a ver. Estimativa errada é comum. Por isso a opção `ANALYZE` do `EXPLAIN` existe (é outro `ANALYZE`, não o das estatísticas): sem ela, você só vê o palpite.

### Sem volume, todo plano parece bom

Rodei o seed com 1 mil, 10 mil, 100 mil e 1 milhão de linhas, e o `explain.sql` depois de cada um:

| reservas | plano | lidas e descartadas | tempo |
|---|---|---|---|
| 1 mil | Seq Scan | 1 000 | 0,065 ms |
| 10 mil | Seq Scan | 10 000 | 0,433 ms |
| 100 mil | Seq Scan | 100 000 | 3,948 ms |
| 1 milhão | Parallel Seq Scan | 1 000 000 | 16,806 ms |

*(Abaixo de 1 milhão, as reservas acabam antes de 2031, e a consulta devolve zero linhas. Para o que se mede aqui, ler tudo, não faz diferença.)*

Com mil reservas, 0,065 ms. Ninguém olha para isso. O tempo cresce junto com a tabela, porque o trabalho **é** a tabela. Num teste com três linhas, toda consulta é rápida. É por isso que a gente mede com volume.

E 17 ms é pouco? Para uma consulta só, é. Mas ela roda em **todo** `POST /bookings`, segurando uma conexão do pool (lição 05), e cresce com cada reserva nova.

## O índice

A solução do livro é óbvia: o índice remissivo. Uma lista em ordem alfabética, com o número da página. Você acha "quadra" em segundos, porque a lista **está ordenada**, e pula direto para as páginas certas.

No banco, a estrutura mais comum para isso é a **B-tree** (ou "btree"): uma árvore que guarda os valores de uma ou mais colunas **em ordem**, cada um apontando para a linha da tabela. Achar um valor numa árvore ordenada custa poucos passos, mesmo com milhões de entradas. E, uma vez achado o ponto de partida, as entradas vizinhas estão do lado.

### A ordem das colunas

O índice do FairFare tem duas colunas: `(resource_id, starts_at)`. Isso quer dizer: ordenado por recurso e, **dentro de cada recurso**, por horário de início. Como uma lista telefônica: sobrenome, depois nome.

Por que nessa ordem? Porque a consulta usa as duas de jeitos diferentes:

- `resource_id = 7` é **igualdade**. Todas as entradas do recurso 7 estão juntas, num bloco.
- `starts_at < 12h` é um **intervalo**. Dentro do bloco do recurso 7, as entradas estão ordenadas por início, e as que servem formam um trecho contínuo.

Igualdade primeiro, intervalo depois: o banco pula para o bloco certo e lê um trecho só.

Ao contrário, `(starts_at, resource_id)`, as entradas do recurso 7 ficam espalhadas entre as dos outros 49, ao longo de toda a linha do tempo. Testei isso, dentro de um `BEGIN` ... `ROLLBACK`, então nada ficou no banco. Com a ordem trocada, o planner **ignorou o índice** e voltou ao `Parallel Seq Scan` (13,8 ms). Forçando o uso dele (`SET LOCAL enable_seqscan = off`), a parte do índice sozinha leu 1692 páginas e levou 10,9 ms. O índice na ordem certa lê 37 páginas.

Lista telefônica ordenada por nome, depois sobrenome: tecnicamente um índice, inútil para achar os Silvas.

### No model e na migração

O índice entra no model, em `__table_args__`:

```diff
-from sqlalchemy import DateTime, ForeignKey
+from sqlalchemy import DateTime, ForeignKey, Index
 from sqlalchemy.orm import Mapped, mapped_column
 
 from app.database import Base
@@ -8,6 +8,10 @@ from app.database import Base
 
 class Booking(Base):
     __tablename__ = "bookings"
+    __table_args__ = (
+        # find_overlapping roda em toda reserva: filtra por recurso, depois por horário (lição 06).
+        Index("ix_bookings_resource_id_starts_at", "resource_id", "starts_at"),
+    )
```

O `__table_args__` é onde vai o que é da tabela, não de uma coluna só. O nome segue a convenção `ix_<tabela>_<colunas>`. Ele vai voltar a aparecer, então vale ser legível.

O autogenerate do Alembic enxerga a mudança, como na lição 04. A diferença é que, desta vez, o arquivo gerado sai pronto, sem precisar de edição à mão:

```console
$ uv run alembic revision --autogenerate -m "indice de reservas por recurso e inicio"
...
INFO  [alembic.autogenerate.compare.constraints] Detected added index 'ix_bookings_resource_id_starts_at' on '('resource_id', 'starts_at')'
```

A migração gerada. Passei o `ruff format` e o `ruff check --fix`, que tirou o `import sqlalchemy as sa` do cabeçalho: o Alembic sempre o põe, e desta vez ninguém o usa.

```python
def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(
        "ix_bookings_resource_id_starts_at", "bookings", ["resource_id", "starts_at"], unique=False
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("ix_bookings_resource_id_starts_at", table_name="bookings")
    # ### end Alembic commands ###
```

Nada para editar. O `upgrade head`, com o milhão de reservas já no banco, levou 6,8 s: o Postgres leu a tabela inteira e montou a árvore. Os testes não precisam de nada: o `conftest` cria as tabelas pelo model (lição 03), e o índice vem junto.

### O plano novo

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare < $B/explain.sql
                                                                     QUERY PLAN
-----------------------------------------------------------------------------------------------------------------------------------------------------
 Bitmap Heap Scan on bookings  (cost=224.36..8100.72 rows=4855 width=28) (actual time=3.265..3.265 rows=2.00 loops=1)
   Recheck Cond: ((resource_id = 7) AND (starts_at < '2031-01-01 12:00:00+00'::timestamp with time zone))
   Filter: (ends_at > '2031-01-01 10:00:00+00'::timestamp with time zone)
   Rows Removed by Filter: 8770
   Heap Blocks: exact=3225
   Buffers: shared hit=3262
   ->  Bitmap Index Scan on ix_bookings_resource_id_starts_at  (cost=0.00..223.15 rows=8672 width=0) (actual time=0.415..0.416 rows=8772.00 loops=1)
         Index Cond: ((resource_id = 7) AND (starts_at < '2031-01-01 12:00:00+00'::timestamp with time zone))
         Index Searches: 1
         Buffers: shared hit=37
 Planning:
   Buffers: shared hit=104
 Planning Time: 0.213 ms
 Execution Time: 3.298 ms
(14 rows)
```

**16,8 ms → 3,3 ms.** Cinco vezes mais rápido. De dentro para fora:

- **`Bitmap Index Scan`** percorre o índice. O **`Index Cond`** é a parte da condição que o índice resolve: recurso 7 e início antes das 12h. Ele leu 37 páginas do índice e achou 8772 entradas. Em vez de ir à tabela uma por uma, ele monta um **bitmap**, um mapa de quais páginas da tabela têm linhas interessantes.
- **`Bitmap Heap Scan`** visita essas páginas, em ordem. "Heap" é o nome que o Postgres dá à tabela em si. Foram 3225 páginas, das 7353. As reservas do recurso 7 estão espalhadas pela tabela inteira (uma a cada 50 linhas), e por isso o planner preferiu o mapa a pular de página em página.
- O **`Filter`** com o `ends_at` é aplicado na tabela, linha a linha, como antes.

Com o índice, a curva também muda de forma:

| reservas | entradas lidas no índice | tempo |
|---|---|---|
| 1 mil | 20 | 0,045 ms |
| 10 mil | 200 | 0,126 ms |
| 100 mil | 2 000 | 0,834 ms |
| 1 milhão | 8 772 | 3,588 ms |

*(Mesma sessão, seed refeito com o índice já criado. O 3,588 é a primeira execução depois do seed. Repetida, a mesma consulta fica em 3,3 ms.)*

## O preço

Índice não é de graça. Três contas:

**Espaço.**

```console
$ docker compose exec postgres psql -U fairfare -c "SELECT pg_size_pretty(pg_relation_size('ix_bookings_resource_id_starts_at')), pg_size_pretty(pg_relation_size('bookings')), pg_size_pretty(pg_relation_size('bookings_pkey'));"
 pg_size_pretty | pg_size_pretty | pg_size_pretty 
----------------+----------------+----------------
 30 MB          | 57 MB          | 21 MB
(1 row)
```

Trinta megabytes, mais da metade do tamanho da tabela. *(O terceiro número é o índice da chave primária. Ele já existia, e você já pagava por ele sem saber.)*

**Escrita.** Todo `INSERT` grava a linha na tabela **e** uma entrada em cada índice. Todo `DELETE` e todo `UPDATE` das colunas indexadas também mexem nele. Mais índices, escritas mais caras. Tentei medir isso com o próprio seed: um milhão de linhas levou 18, 24 e 22 s sem o índice, e 35 e 21 s com ele. O disco desta máquina oscila mais do que a diferença, então não cito número. O custo existe. Ele só não aparece nessa régua.

**Manutenção.** Criar o índice num banco cheio leva tempo (6,8 s aqui) e, por padrão, o `CREATE INDEX` **bloqueia escritas** na tabela enquanto roda. Num milhão de linhas, 7 s de reservas travadas. Em produção, com mais dados, isso pesa. O Postgres tem um `CREATE INDEX CONCURRENTLY` para isso, que não entra neste capítulo.

Regra de bolso: índice é para a consulta que você **mediu** e que importa. Não para toda coluna que "talvez um dia" apareça num `WHERE`.

## O número que fica para a lição 11

Volte ao plano novo e olhe duas linhas:

```
   Rows Removed by Filter: 8770
...
         Index Cond: ((resource_id = 7) AND (starts_at < '2031-01-01 12:00:00+00'::timestamp with time zone))
```

O índice entregou **8772** entradas para achar **2** linhas. As outras 8770 foram buscadas na tabela e jogadas fora.

O motivo está no `Index Cond`: o `ends_at > 10h` não está nele. O índice sabe o recurso e o início, então ele consegue responder "quais reservas do recurso 7 começam antes das 12h?". Mas isso inclui **todo o passado** da quadra 7, desde 2030. Quem decide quais delas ainda não acabaram às 10h é o `Filter`, depois, na tabela.

E "todo o passado" cresce. A mesma consulta, em três janelas diferentes do mesmo banco:

| janela (10h–12h) | entradas lidas | linhas | tempo |
|---|---|---|---|
| 2 de janeiro de 2030 | 36 | 2 | 0,038 ms |
| 1º de janeiro de 2031 | 8 772 | 2 | 3,3 ms |
| 1º de janeiro de 2032 | 17 532 | 2 | 6,1 ms |

Quanto mais histórico a quadra tem antes do horário pedido, mais o índice lê. O btree ordena por uma coisa de cada vez, e um intervalo que se sobrepõe a outro intervalo tem **duas** pontas, em duas colunas. Uma árvore ordenada não resolve as duas ao mesmo tempo.

Guarde esse número: **8772 lidas para 2 encontradas**. A lição 11 volta nele, com um tipo de índice que entende intervalos.

## O que fica declarado

- **Os números são desta máquina, nesta sessão:** doze núcleos, Postgres 18.6 no Docker, um disco lento. O tempo do seed vai variar muito. A ordem de grandeza do `EXPLAIN`, bem menos.
- **O `seed.sql` apaga** usuários, recursos e reservas do banco de dev. Depois dele, o banco fica com um milhão de reservas, e as próximas lições contam com isso.
- **O teste da ordem trocada** foi feito num `BEGIN` ... `ROLLBACK`, e o índice dele não existe no repositório.
- **O índice ainda lê todo o passado do recurso.** É a observação acima, e ela tem lição marcada: a 11.

## O que você deve conseguir fazer agora

- Rodar um `EXPLAIN (ANALYZE, BUFFERS)` e dizer qual nó domina, quantas linhas ele leu e quantas jogou fora.
- Explicar a diferença entre `EXPLAIN` e `EXPLAIN ANALYZE`, e por que o segundo é perigoso num `DELETE`.
- Explicar por que `(resource_id, starts_at)` funciona e `(starts_at, resource_id)` não, para esta consulta.
- Dizer o que um índice custa, além do espaço.
- Apontar, no plano, a condição que o índice **não** resolve.
