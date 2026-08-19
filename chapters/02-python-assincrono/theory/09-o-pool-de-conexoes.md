# Lição 09 — O pool de conexões, e o teto que mudou de lugar

Hora da conta. O app inteiro foi reescrito na lição 07. O que a gente ganhou com isso, em números?

A resposta tem duas partes, e a primeira vai te decepcionar de propósito.

## Parte 1: o ganho é zero

Vamos medir o que interessa a uma pessoa só usando o site. Cinquenta requests simultâneas em `GET /bookings`, com a bancada da lição 01, contra as duas versões do FairFare — a do capítulo 1 (síncrona) e a de agora:

| 50 requests em `/bookings` | Resultado |
|---|---|
| FairFare síncrono (capítulo 1) | **0,09s**, todas 200 |
| FairFare async (capítulo 2) | **0,08s**, todas 200 |

Empate. A diferença entre os dois é da espessura do ruído de medição — rode três vezes e a ordem troca.

Isso não é uma medição ruim, é a medição certa mostrando a verdade: **async não deixa uma request mais rápida.** Nunca deixou, nunca vai deixar. Uma consulta que leva 3ms leva 3ms nos dois mundos. O que muda é o que o processo consegue fazer *enquanto* ela acontece — e com cinquenta clientes numa máquina moderna, não faz diferença nenhuma.

Some a isso o que a lição 05 já tinha declarado: o SQLite não é um banco de rede, o `aiosqlite` é uma thread com uma fachada bonita, e um arquivo local não tem handshake para economizar. Se você esperava que a refatoração de dez arquivos aparecesse como um gráfico caindo, não vai aparecer.

Guarde essa primeira metade antes de ler a segunda, porque é ela que te protege de vender async como remédio de velocidade.

## Parte 2: agora aumente a carga

Mesma medição, mesmas duas versões, mesmo banco. Só o número de clientes simultâneos muda:

| Simultâneas em `/bookings` | Síncrono (cap. 1) | Async (cap. 2) |
|---|---|---|
| 50 | 0,09s — todas 200 | 0,08s — todas 200 |
| 100 | **60,16s — 80 requests com erro 500** | 0,15s — todas 200 |
| 200 | **colapso: o cliente é desconectado** | 0,30s — todas 200 |
| 500 | — | 1,36s — todas 200 |
| 1000 | — | 7,51s — todas 200 |

O FairFare do capítulo 1 aguenta 50 pessoas e derrete com 100. Não fica lento: **falha**. Oitenta das cem pessoas recebem erro 500 depois de esperar meio minuto — enquanto a versão async despacha as mesmas cem em 0,15s, sem perceber que houve um pico.

O FairFare de hoje atende mil.

E o log do app síncrono diz exatamente de que ele morreu:

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached,
connection timed out, timeout 30.00
```

Não foi o SQLite. Não foi a CPU. Foi o **pool de conexões**.

## O que é um pool, e por que ele tem um teto

Abrir uma conexão com um banco é caro: handshake de rede, autenticação, memória alocada do lado do servidor. Fazer isso a cada request seria um desperdício absurdo. Então o SQLAlchemy mantém um **pool**: um conjunto de conexões já abertas, que o código pega emprestado e devolve.

Três números governam esse conjunto — e até agora eles estavam invisíveis, valendo os defaults. Dá para perguntar:

```bash
uv run python -c "
from app.database import engine
p = engine.pool
print(p.__class__.__name__, p.size(), p._max_overflow, p._timeout)"
# AsyncAdaptedQueuePool 5 10 30.0
```

- **`pool_size=5`** — conexões mantidas abertas o tempo todo.
- **`max_overflow=10`** — extras que podem ser abertas num pico, e descartadas depois.
- **`pool_timeout=30`** — quantos segundos uma request espera por uma conexão livre antes de desistir com erro.

Agora a aritmética que assusta na hora certa: **5 + 10 = 15**. Quinze conexões simultâneas, no máximo. A décima sexta request que precisar de banco ao mesmo tempo **espera**. Se em 30 segundos nenhuma vagar, ela não fica lenta — ela morre com 500.

Um app que aceita mil conexões HTTP ainda passa por esse funil de quinze. Nenhuma quantidade de `async def` muda isso.

## Por que o síncrono estourou e o async não

As duas versões têm o **mesmo pool**: 5 + 10 = 15. Então por que uma quebra aos 100 clientes e a outra atravessa 1000?

A diferença não está no trabalho de banco — ele é o mesmo nas duas versões, e leva os mesmos milissegundos. Está no **preço de esperar**, e em quanto tempo cada conexão fica presa.

No modelo síncrono, cada request ocupa uma thread do threadpool (lição 01) e abre a sua sessão — e a sessão segura a conexão que pegou do primeiro toque no banco até o fim da request. São quarenta threads revezando na CPU umas com as outras e disputando quinze conexões. Sob carga, essa disputa alonga cada request; cada conexão fica presa por mais tempo; a fila do pool anda cada vez mais devagar — até alguém completar trinta segundos de espera e morrer com 500. E repare no desperdício dobrado: quem espera vaga no pool está, o tempo todo, ocupando uma thread inteira para não fazer nada.

No event loop, esperar é barato. Uma request aguardando vaga no pool não custa thread nenhuma — é uma corrotina pausada, uma anotação de "me avise quando vagar". E quem está com uma conexão na mão a usa pelos poucos milissegundos das suas queries e devolve. O funil de quinze escoa rápido, a fila anda, ninguém chega perto dos trinta segundos. Mil requests em andamento convivem com quinze conexões porque estar em andamento, no async, não consome quase nada.

Aí está a frase que resume o capítulo inteiro:

> **Async não aumenta a capacidade do seu banco. Ele impede que a espera pelo banco consuma recursos.**

E a consequência para o teto: ele não desapareceu. Na lição 01 o limite eram as 40 threads. Agora o limite são as 15 conexões. **O teto mudou de lugar** — e essa mudança é o ganho de verdade, porque a espera parou de ocupar thread, e o novo teto é um número que *você escolhe*.

## Deixando os três números à vista

Já que eles decidem a vida do app, não podem ficar escondidos num default. Em `app/database.py`:

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,  # conexões mantidas abertas
    max_overflow=10,  # extras sob pico, descartadas depois
    pool_timeout=30,  # segundos esperando uma conexão livre antes de estourar
)
```

Esses são exatamente os valores que já valiam. **O comportamento não mudou em nada** — mudou a visibilidade. É uma daquelas edições que não fazem o app funcionar melhor e fazem a equipe pensar melhor: quando o pool estourar em produção às três da manhã, o número vai estar num arquivo do projeto, com um comentário do lado, e não numa página de documentação que alguém precisa lembrar de procurar.

*(Os testes continuam verdes — `13 passed` — e nem tocam nesses parâmetros: o banco de teste é em memória e usa `StaticPool`, uma conexão só, como a lição 07 comentou.)*

## Reproduzindo em casa

Não acredite em mim; a bancada está no repositório. O truque para ter as duas versões do app ao mesmo tempo é o git:

```bash
git worktree add /tmp/fairfare-cap01 v-chapter-01
cp fairfare.db /tmp/fairfare-cap01/
cd /tmp/fairfare-cap01 && uv sync && uv run uvicorn app.main:app --port 8127
```

Com o app antigo de pé numa porta e o novo em outra, é a mesma linha de comando nas duas:

```bash
uv run python chapters/02-python-assincrono/bancada/carga.py http://localhost:8127/bookings 100
```

Duas honestidades sobre esses números. **Eles variam com a máquina** — o ponto exato onde a versão síncrona quebra depende de núcleos, disco e do que mais está rodando aí. E **cada rodada precisa de um servidor novo**: um servidor que acabou de levar uma carga que o derrubou continua bagunçado, e medir em cima disso produz número sem significado. (Sei porque errei assim antes de acertar: a primeira leva de medições desta lição foi para o lixo por causa disso.)

O que não varia é a forma do resultado: empate em latência, abismo em escala.

## O gancho do capítulo 4

Repare que esta lição inteira foi sobre um gargalo de **quinze conexões** — e a gente nem discutiu se quinze é um bom número.

Não dá para discutir ainda. Com SQLite, "conexão" é um handle para um arquivo local; aumentar o pool não compra quase nada, e o próprio SQLite serializa as escritas de qualquer jeito. A conversa só fica interessante quando o banco for um servidor de verdade, com um limite próprio de conexões, do outro lado de uma rede.

É o capítulo 4. Lá o FairFare vai para o PostgreSQL com `asyncpg` — um driver async até o osso, sem thread escondida — e esses três números viram a diferença entre "aguenta o pico" e "cai na madrugada". A gente vai esgotar o pool de propósito, ver o erro, e aprender a dimensioná-lo.

Por hoje, o que importa é que o funil ficou visível.

## O que você deve conseguir fazer agora

- Explicar por que async **não** deixa uma request mais rápida, com o empate de 0,09s × 0,08s na mão.
- Calcular quantas conexões seu app abre no pico (`pool_size + max_overflow`) e dizer o que acontece com a request seguinte.
- Ler `QueuePool limit of size 5 overflow 10 reached` e saber exatamente o que fazer com essa informação.
- Explicar por que a versão síncrona esgotou o mesmo pool que a versão async não esgotou.
- Repetir a medição das duas versões usando `git worktree` — e saber por que cada rodada precisa de servidor novo.
