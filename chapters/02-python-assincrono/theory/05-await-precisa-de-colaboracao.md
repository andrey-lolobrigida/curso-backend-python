# Lição 05 — `await` só funciona se a biblioteca colaborar

Você chegou até aqui com um modelo mental montado e uma pergunta na ponta da língua:

> "Beleza. Então é só botar `async def` nas rotas e `await` nas consultas ao banco, certo?"

Não. E esta é a lição mais importante do capítulo, porque é onde quase todo mundo se machuca.

## `await` não converte nada

Volte à definição da lição 03: `await` significa *pausa aqui e devolve o controle ao loop*. Para pausar, a coisa esperada precisa **saber ser pausada** — precisa avisar o loop "estou aguardando o banco, me acorde quando a resposta chegar".

Um driver de banco síncrono não sabe fazer isso. Ele chama o sistema operacional e fica ali, parado, segurando a thread até a resposta voltar. Não existe ponto de pausa. Não há nada que o loop possa aproveitar.

Então o que acontece se você escrever `await` na frente do SQLAlchemy síncrono?

```python
result = await session.execute(select(User))   # session é uma Session normal
```

Não é lentidão. É **erro de tipo**. O `session.execute` devolve um resultado já pronto, e `await` sobre um resultado pronto estoura na hora:

```
TypeError: object ChunkedIteratorResult can't be used in 'await' expression
```

*(O nome da classe muda conforme a consulta — `CursorResult` para SQL cru, por exemplo. O que importa é a segunda metade da frase.)*

O Python não tem como fingir: ou a biblioteca devolve algo aguardável, ou não devolve. `await` é uma pergunta, e um objeto comum não sabe respondê-la.

A regra que sai daí é dura e é o eixo do capítulo:

> **Async é propriedade da stack inteira, não da sua função.** Uma biblioteca síncrona no fundo do poço apaga o benefício de todas as camadas acima dela.

Você pode ter rota async, service async, repository async — e uma linha síncrona no acesso ao banco derruba tudo. Foi o que a lição 04 mostrou com números, agora você sabe o porquê.

## Trocando a peça

A cura é usar um driver que colabore. Para SQLite, é o `aiosqlite`:

```bash
uv add aiosqlite
```

Note que ele entra como dependência de **runtime**, não de dev: quando a migração acontecer, o app não sobe sem ele. E note também que ele entra **sozinho neste commit** — o FairFare ainda não mudou nenhuma linha. A dependência chega antes porque a lição precisa dela para te mostrar uma coisa desconfortável.

Com ele instalado, a URL do banco ganha um sobrenome:

```python
"sqlite:///fairfare.db"           # antes: driver sqlite3, síncrono
"sqlite+aiosqlite:///fairfare.db" # depois: driver aiosqlite, awaitable
```

E aí o `await` passa a fazer sentido, porque agora existe alguém do outro lado que sabe se pausar.

## A desilusão, dita antes de você migrar

Agora a parte que os tutoriais não contam, e que você merece ouvir **antes** de refatorar o app inteiro:

> **`aiosqlite` é o `sqlite3` de sempre rodando numa thread de fundo.**

Não é um driver assíncrono de verdade. Não existe driver assíncrono de verdade para SQLite, e o motivo é estrutural: **o SQLite não tem I/O de rede.** Ele é uma biblioteca C que lê e escreve um arquivo no seu disco, dentro do seu processo. Não há socket, não há servidor do outro lado, não há nada que o event loop possa vigiar e dizer "me avise quando chegar resposta". Só existe uma chamada de sistema que bloqueia até o disco responder.

Então o `aiosqlite` faz a única coisa possível: pega o `sqlite3` normal, coloca numa thread separada, e te devolve uma interface `await`-ável que na verdade está conversando com essa thread.

Isso não é opinião nem leitura de documentação — dá para ver:

```python
import asyncio, threading, aiosqlite

async def main():
    print("threads antes:", threading.active_count())
    conns = [await aiosqlite.connect(":memory:") for _ in range(5)]
    print("threads com 5 conexões abertas:", threading.active_count())
    print("nomes:", sorted({t.name for t in threading.enumerate()}))

asyncio.run(main())
```

```
threads antes: 1
threads com 5 conexões abertas: 6
nomes: ['MainThread', 'Thread-1 (_connection_worker_thread)', ... 'Thread-5 (_connection_worker_thread)']
```

Uma thread de trabalho por conexão, com o nome escrito na testa. É a válvula `asyncio.to_thread` da lição 04, embrulhada numa API bonita.

### Então por que migrar?

Pergunta justa. Se o banco vai continuar numa thread, o que a migração compra?

**O que você não ganha:** velocidade de banco. Aqui, com SQLite, o acesso a dados vai custar aproximadamente o mesmo. A lição 09 vai medir isso e o número vai ser decepcionante — de propósito, e a gente vai olhar para ele de frente.

**O que você ganha:**

1. **O resto do app deixa de gastar thread.** Só o trecho do banco fica numa thread; a rota, a serialização, as chamadas HTTP futuras e todo o resto passam a viver no loop. O teto de 40 requests simultâneas da lição 01 deixa de valer para o app inteiro.
2. **A estrutura certa para quando o banco for de verdade.** No capítulo 4 o FairFare vai para o PostgreSQL, que **fala por rede** — e aí o `asyncpg` é async até o osso, sem thread nenhuma escondida. Nesse dia, o ganho aparece de verdade. E não vai ter refatoração para fazer: só a URL muda.
3. **Uma stack coerente.** Metade async e metade síncrona é o pior lugar para se estar: você paga a complexidade das duas e não colhe o benefício de nenhuma.

Migrar agora é montar a tubulação certa sabendo que a água boa vem depois. Isso é diferente de migrar achando que o app vai ficar 10x mais rápido amanhã — e é por isso que essa conversa vem **antes** da refatoração, não depois.

## Um aviso com o erro na tela

Tem uma armadilha específica do SQLAlchemy async que vale conhecer antes de encostar nela, e ela tem nome: **`MissingGreenlet`**.

O script `bancada/lazy_load.py` a reproduz de propósito. Ele cria dois models com uma relação entre eles, carrega um objeto e toca no atributo relacionado:

```python
coisa = (await db.scalars(select(Coisa))).first()
print(coisa.dono.nome)  # <- estoura aqui
```

```bash
uv run python chapters/02-python-assincrono/bancada/lazy_load.py
```

```
carreguei a coisa. agora vou tocar em coisa.dono, que não foi carregado:
...
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call
await_only() here. Was IO attempted in an unexpected place?
(Background on this error at: https://sqlalche.me/e/20/xd2s)
```

Olhe **onde** o erro acontece: num acesso a atributo. Um ponto. Não há `await` nenhum naquela linha, não há chamada de método, não há nada que pareça tocar no banco.

Mas toca. É o **lazy load** (carregamento preguiçoso) do ORM: `coisa.dono` não veio na consulta, então o SQLAlchemy tenta ir buscá-lo no banco naquele exato instante. No mundo síncrono isso é invisível e funciona. No mundo async, buscar significa I/O, e I/O precisa de `await` — que é impossível de inserir no meio de um `.` de acesso a atributo. Daí a mensagem: *IO foi tentado num lugar inesperado*.

A tradução prática de `greenlet_spawn has not been called`: o SQLAlchemy tentou fazer I/O num contexto síncrono de onde não dava para voltar ao loop.

**O FairFare escapa disso hoje por sorte:** nossos models (`User`, `Resource`, `Booking`) não têm nenhum `relationship()`. As relações chegam no capítulo 4, e junto com elas o carregamento explícito (`selectinload` e companhia) que é a cura. Este parágrafo existe para que, no dia em que a mensagem aparecer na sua tela, você já a tenha visto uma vez, na bancada, num script de dez linhas — em vez de descobri-la em produção.

## O que você deve conseguir fazer agora

- Explicar por que `await` na frente de código síncrono não o torna assíncrono.
- Verificar se uma biblioteca é async de verdade: ela expõe funções que devolvem algo aguardável, ou está embrulhando uma thread?
- Dizer o que o `aiosqlite` realmente faz — e provar contando threads.
- Explicar, para alguém cético, o que a migração do FairFare ganha e o que ela **não** ganha.
- Reconhecer `MissingGreenlet` e saber que ele quase sempre significa lazy load.
