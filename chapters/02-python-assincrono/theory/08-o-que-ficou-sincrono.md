# Lição 08 — O que ficou síncrono de propósito

Terminar uma migração dessas produz um efeito colateral curioso: `async def` vira reflexo. Você abre qualquer arquivo do projeto, vê um `def` sozinho e sente uma coceira.

Resista. Esta lição é sobre os pedaços do FairFare que **continuaram síncronos**, cada um por um motivo específico — e sobre a régua que decide isso, que vale para o resto da sua carreira melhor do que qualquer regra decorada.

## O Alembic ficou de fora, e não foi esquecimento

Você viu a linha aparecer no `app/database.py` sem explicação:

```python
DATABASE_URL = "sqlite+aiosqlite:///fairfare.db"

# O Alembic continua síncrono, e por isso precisa da sua própria URL.
SYNC_DATABASE_URL = "sqlite:///fairfare.db"
```

E o `alembic/env.py` foi apontado para a segunda:

```python
from app.database import SYNC_DATABASE_URL, Base
...
config.set_main_option("sqlalchemy.url", SYNC_DATABASE_URL)
```

Duas linhas mudaram naquele arquivo. Nada mais. Por quê?

Faça a pergunta da lição 02 — esperando ou trabalhando? — e uma migração está esperando: é I/O quase puro. Mas há uma segunda pergunta, que a régua da lição 02 não cobre e que decide este caso: **quem mais está na fila?** Uma migração roda **uma vez**, na linha de comando, disparada por você. Ninguém está na fila atrás dela. Não existe uma segunda request esperando o loop girar. Não há nada — literalmente nada — para intercalar com a espera.

Async serve para **atender outra pessoa enquanto esta espera**. Numa migração não há outra pessoa. O benefício é exatamente zero.

E o custo não é zero. O Alembic tem um template async oficial, e dá para medir o que ele cobra: comparado ao template síncrono, o `env.py` async tem **onze linhas a mais**, e o `run_migrations_online` — que era uma função — vira três (`do_run_migrations`, `run_async_migrations` e uma `run_migrations_online` que só chama `asyncio.run`). Tudo isso porque o Alembic, por dentro, precisa de uma conexão síncrona de qualquer jeito, e o template async gasta essas linhas montando uma ponte com `connection.run_sync` para chegar de volta ao mesmo lugar.

Onze linhas de cerimônia, três funções onde havia uma, num arquivo que você abre uma vez por trimestre, para ganhar nada. A escolha é fácil quando a pergunta é feita direito.

## O preço, declarado

Nenhuma decisão é grátis, e esta tem uma conta a pagar: **duas URLs no `database.py` são dois lugares para trocar.**

Quando o FairFare for para o PostgreSQL no capítulo 4, você não vai mexer numa string — vai mexer em duas, e elas precisam apontar para o mesmo banco (`postgresql+asyncpg://...` e `postgresql+psycopg://...`). Se divergirem, você tem o pior bug possível: as migrações rodam num banco e o app fala com outro, sem erro nenhum, até alguém perguntar por que a tabela nova não apareceu.

Existe defesa contra isso — derivar uma URL da outra, ou montar as duas a partir de uma configuração única. O FairFare não faz nada disso hoje porque configuração ainda não é assunto do curso; as duas strings estão literais no código, uma embaixo da outra, com um comentário entre elas. Quando as variáveis de ambiente entrarem, esse é um dos primeiros lugares a arrumar.

Estou te contando isso em vez de fingir que a decisão foi limpa. O trade-off é: **um arquivo simples e uma duplicação declarada**, contra **um arquivo complexo e uma fonte única**. Escolhi o primeiro, para o tamanho de projeto que temos, e você agora sabe o preço.

## Os schemas e os models também não mudaram

Isso vai te dar uma pontada de suspeita, então vamos matar a dúvida.

**Os schemas Pydantic (`app/schemas/`) não mudaram nem uma vírgula.** Validar dados é trabalho de CPU sobre coisas que já estão na memória: checar tipo, checar formato de email, converter string em `datetime`. Isso leva microssegundos e não fala com ninguém. Pela régua da lição 04, é código "rápido" — e código rápido pode viver dentro de uma corrotina sem nenhum `await`, tranquilamente.

**Os models SQLAlchemy (`app/models/`) também não mudaram.** Aqui o motivo é ainda mais interessante: um model é **declaração**, não execução. `class Booking(Base)` com seus `mapped_column` descreve o formato de uma tabela. Ele não abre conexão, não roda query, não faz I/O. Quem executa é a sessão — e foi a sessão que virou `AsyncSession`.

Essa separação é o que permitiu a lição 07 ser um diff tão cirúrgico. **O que descreve fica quieto; o que executa muda.** Se os seus models tivessem lógica de acesso a banco dentro deles, a migração teria contaminado tudo.

## A régua, em três perguntas

Guarde esta lista. Ela decide, para qualquer trecho de código, se ele merece ser async:

1. **Este código espera alguém?** (rede, disco, banco, outro processo)
2. **Ele espera enquanto outra pessoa poderia estar sendo atendida?**
3. **A biblioteca que faz essa espera colabora?** (existe versão awaitable de verdade)

Três "sim" → async vale a pena. **Qualquer "não" → deixe síncrono e siga em frente.**

Aplicando ao que a gente tem:

| Trecho | Espera? | Tem fila atrás? | Lib colabora? | Veredito |
|---|---|---|---|---|
| Rota `POST /bookings` | sim | sim | sim | **async** |
| Repository consultando o banco | sim | sim | sim (aiosqlite) | **async** |
| Validação Pydantic | não | — | — | síncrono |
| Definição de model | não | — | — | síncrono |
| Migração do Alembic | sim | **não** | (irrelevante) | síncrono |
| Comparar duas datas no service | não | — | — | síncrono (dentro de uma corrotina) |

Repare que a migração do Alembic responde "sim" à primeira pergunta e mesmo assim fica síncrona. É a **segunda** pergunta que decide o caso dela — e é justamente a pergunta que ninguém faz, porque "isso faz I/O, então tem que ser async" é o tipo de regra que a gente decora sem entender.

A pergunta 3 é a da lição 05, e ela é uma faca: se a biblioteca não colabora, escrever `async` em volta dela não produz concorrência nenhuma. Produz teatro.

## Async não é hierarquia de qualidade

Um último recado, e ele é sobre gosto, não sobre técnica.

Depois de aprender uma ferramenta nova, é natural achar que o código que não a usa está atrasado. Não está. **Código síncrono não é código de segunda.** Uma função `def` que faz uma conta e devolve um valor é perfeita do jeito que está, e envolvê-la em `async def` só a torna mais difícil de chamar — porque agora todo mundo que a usa precisa de `await`, e o `await` sobe pela pilha inteira contaminando quem não pediu nada.

Esse é o custo real do async, e ele é estrutural: **`async` é viral.** Uma vez que uma função vira corrotina, todo mundo acima dela na cadeia de chamadas precisa lidar com isso. Foi exatamente o dominó da lição 07 — só que lá o dominó era necessário, e aqui seria gratuito.

A pergunta certa nunca é "isto poderia ser async?". É: **"o que eu ganho tornando isto async, e quanto isso custa a quem chama?"**

## O que você deve conseguir fazer agora

- Justificar, para um colega apressado, por que o Alembic ficou síncrono.
- Nomear o preço dessa escolha (duas URLs) e dizer quando ele vai cobrar juros.
- Explicar por que schemas e models não mudaram na migração, com dois motivos diferentes.
- Aplicar as três perguntas a um trecho de código qualquer e defender o veredito.
- Explicar o que significa "`async` é viral" e por que isso é um custo de verdade.
