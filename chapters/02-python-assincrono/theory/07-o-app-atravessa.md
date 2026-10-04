# Lição 07 — O app atravessa

Chegou o dia. O FairFare vira async: `database.py`, três repositories, um service, três routers, o `alembic/env.py` e o override do banco nos testes.

Tudo num commit só.

## Por que este commit é grande

Você aprendeu, no capítulo 1, que commit bom é commit pequeno. Este tem dez arquivos. Não é desleixo — é a forma do problema, e vale mais como aula do que qualquer parágrafo sobre acoplamento.

O motivo é uma frase: **o engine é um só.**

Olhe o que acontece na primeira linha da migração. `create_engine` vira `create_async_engine`. Nesse instante, o objeto que representa a conexão com o banco mudou de espécie — e um `sessionmaker` síncrono **não pode se ligar a um engine assíncrono**. Não é questão de estilo; é incompatibilidade de tipo. Toda sessão que sai dali é uma `AsyncSession`, e toda chamada que ela recebe precisa de `await`.

A partir daí o dominó cai sozinho:

- A sessão virou `AsyncSession` → os repositories precisam de `await` em `get`, `scalars`, `commit`.
- Os métodos dos repositories viraram corrotinas → o service precisa de `await` neles.
- Os métodos do service viraram corrotinas → os routers precisam de `await` neles.
- Os routers com `await` no corpo → precisam ser `async def`.

Tem como parar no meio? Só mantendo **dois engines vivos** — um síncrono para a metade que ainda não migrou, um assíncrono para a que já migrou. Fora a complexidade, isso quebra os testes na hora: dois engines não compartilham um SQLite em memória, então metade do app enxergaria um banco e metade enxergaria outro.

Então a resposta honesta é: o app atravessa inteiro, ou não atravessa. E é isso que "acoplamento" significa, de forma concreta e sem metáfora — a fronteira mínima em que uma decisão técnica pode ser trocada. Aqui, a fronteira mínima é *o app inteiro*.

Guarde a régua, porque ela decide muita coisa na vida real: **o tamanho de um commit não é uma escolha de gosto, é uma propriedade do código.** Um app com camadas bem separadas troca de banco numa linha (foi a lição 11 do capítulo 1). O mesmo app não consegue trocar de *modelo de execução* em menos de tudo. São tipos diferentes de mudança.

## O coração: `database.py`

Antes e depois, lado a lado:

```python
# antes
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

```python
# depois
DATABASE_URL = "sqlite+aiosqlite:///fairfare.db"
SYNC_DATABASE_URL = "sqlite:///fairfare.db"   # o Alembic continua síncrono; lição 08

engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as db:
        yield db
```

Três coisas sumiram e uma apareceu. Vale olhar cada uma, porque as três que sumiram são configurações que a gente copia de tutorial sem entender.

**Sumiu o `connect_args={"check_same_thread": False}`.** Aquilo existia para desligar uma proteção do driver `sqlite3`, que por padrão recusa ser usado de uma thread diferente da que o criou — e o threadpool do FastAPI faz exatamente isso. O dialeto `aiosqlite` **já passa esse argumento sozinho**, porque a arquitetura dele é justamente uma thread de trabalho por conexão (lição 05). A linha virou redundância.

**Sumiu o `try/finally`.** O `async with` fecha a sessão na saída do bloco, inclusive quando uma exceção sobe. É o mesmo contrato do `with` de sempre, na versão assíncrona.

**Sumiu o `.close()` explícito**, pelo mesmo motivo.

**Apareceu o `expire_on_commit=False`.** Essa merece atenção. Por padrão, depois de um `commit()`, o SQLAlchemy marca todos os objetos da sessão como "expirados": na próxima vez que você ler um atributo deles, ele vai ao banco buscar o valor atualizado. No mundo síncrono, isso é invisível e conveniente.

No mundo async, é uma bomba. Ler `user.nome` depois do commit dispararia I/O **dentro de um acesso a atributo** — exatamente o cenário do `MissingGreenlet` da lição 05. `expire_on_commit=False` diz: depois do commit, mantenha os valores que já estão em memória. Sem I/O escondido, sem surpresa.

Repare no padrão: as três remoções e a adição são todas sobre **I/O escondido**. Async não tolera magia implícita, e é por isso que ele te obriga a entender configurações que você vinha carregando no piloto automático.

## A transformação, três vezes

Os repositories são o caso mais mecânico. `UserRepository`, na íntegra:

```python
class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, nome: str, email: str) -> User:
        user = User(nome=nome, email=email)
        self.db.add(user)              # <- sem await
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)

    async def list_all(self) -> list[User]:
        resultado = await self.db.scalars(select(User))
        return list(resultado)
```

A régua da transformação é uma só: **`await` no que faz I/O, nada de `await` no que não faz.**

E o `self.db.add(user)` é o exemplo que fixa a régua. Ele não tem `await`, e não é esquecimento: `add` apenas coloca o objeto na sessão, em memória, marcado como "a inserir". Nenhum byte sai para o banco. Quem conversa com o banco é o `commit`. Se você tiver dúvida sobre alguma chamada, essa é a pergunta: *isso fala com o banco?* Se não fala, não é `await`.

*(E se você errar para o lado do excesso, o Python avisa na hora: `await` sobre um valor comum estoura com `object ... can't be used in 'await' expression`, como você viu na lição 05.)*

`ResourceRepository` e `BookingRepository` seguem o mesmo molde — incluindo o `find_overlapping`, cuja query complexa não muda em nada; só o `scalars` ganha `await`.

## O que os `await` do service revelam

O service é onde a migração deixa de ser mecânica e fica interessante. Uma linha em particular:

```python
    async def list_all(self) -> list[BookingOut]:
        return [await self._to_out(b) for b in await self.bookings.list_all()]
```

No capítulo 1 essa linha era uma list comprehension inofensiva. Agora ela tem um `await` dentro, e o `await` está delatando o que sempre esteve ali.

Cada `_to_out` faz **duas consultas** ao banco (busca o usuário, busca o recurso) para montar uma reserva. Com 50 reservas: uma consulta para listar, mais 100 para montar. É o **problema N+1**, e ele nasceu na lição 09 do capítulo 1 — sem que o capítulo 1 te contasse. Segunda vez neste capítulo que eu confesso algo, e pelo mesmo motivo: o silêncio ali foi um erro de método meu, não um enigma para você resolver. Está declarado na errata do curso, e a lição 11 fecha a conta.

A novidade desconfortável: **agora está pior.** Antes, as 101 consultas eram síncronas, uma atrás da outra. Agora são 101 corrotinas, uma atrás da outra — cada uma com o custo extra de ida e volta ao event loop. Async não conserta N+1. Async não conserta *nada* que seja "muitas idas ao banco"; ele só muda como cada ida é esperada.

E não, não vamos consertar isso aqui. O conserto é `selectinload` ou um `join` — assunto do capítulo 5, junto com as relações. **A lição 11 volta a essa dívida e a declara por escrito**, com todas as outras. O que este capítulo não faz, ele diz que não faz.

O resto do service é a transformação mecânica de sempre: `async def` nos métodos, `await` nas chamadas de repositório, `AsyncSession` no `__init__`. A regra de negócio — comparar datas, decidir conflito, recusar cancelamento no passado — não mudou uma vírgula. Ela nunca soube em que mundo estava rodando, e continua sem saber.

## Os routers, e o que não mudou

```python
@router.post("", status_code=201, response_model=BookingOut)
async def create_booking(data: BookingCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await BookingService(db).create(data)
    except RelatedNotFoundError:
        raise HTTPException(status_code=404, detail="usuário ou recurso não existe")
    except BookingConflictError:
        raise HTTPException(status_code=409, detail="o recurso já está reservado nesse horário")
```

Duas palavras novas (`async`, `await`) e uma anotação trocada (`Session` → `AsyncSession`). Os `try/except` que traduzem exceção de domínio em status HTTP: intactos.

Repare no `Depends(get_db)`. Ele **não mudou de forma** — mesmo o `get_db` tendo virado um gerador assíncrono. O FastAPI aceita dependências síncronas e assíncronas com a mesma sintaxe e resolve cada uma do jeito certo. Você trocou a implementação da dependência sem tocar em nenhum dos seus nove pontos de uso. É a mesma recompensa de arquitetura da lição 11 do capítulo 1, cobrada de novo.

Agora a lista do que **não** mudou no app inteiro, que é mais curiosa que a lista do que mudou:

| Arquivo | Mudou? | Por quê |
|---|---|---|
| `app/main.py` | **não** | vive na fronteira ASGI, e a fronteira sempre foi async (lição 06) |
| `app/models/*` | **não** | descrevem tabelas, não execução |
| `app/schemas/*` | **não** | descrevem formato de dados |
| `tests/test_smoke.py` | **não** | testam comportamento, e o comportamento é o mesmo |
| as migrações em `alembic/versions/` | **não** | lição 08 |

Quatro camadas do app não perceberam a maior refatoração do capítulo. Isso não é sorte: é o que separação por responsabilidade compra. Quem descreve *o quê* fica quieto; quem executa *como* muda.

## Os testes: só o override

No `conftest.py`, a única coisa que muda é o banco de teste — o cliente já era async desde a lição 06:

```python
    engine = create_async_engine("sqlite+aiosqlite://")
    TestingSession = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

Sumiu daqui o `poolclass=StaticPool` — que no capítulo 1 existia para forçar todas as conexões a compartilharem o **mesmo** banco em memória (senão cada conexão nova abriria um SQLite vazio e os testes veriam tabelas inexistentes). Com o dialeto async, `StaticPool` já é o padrão para banco em memória. Mais uma configuração que virou redundância.

E ficou o `run_sync`, que merece uma frase: `Base.metadata.create_all` é uma função **síncrona** do SQLAlchemy que precisa de uma conexão para trabalhar. `conn.run_sync(...)` é a ponte oficial: "rode esta função síncrona usando esta conexão async". Você vai reencontrar esse método sempre que uma API antiga do SQLAlchemy precisar rodar em contexto assíncrono.

## A prova

O momento de maior valor do capítulo:

```bash
uv run pytest -q
# 13 passed
```

Dez arquivos reescritos, o modelo de execução do app inteiro trocado — e a suíte que não mudou uma linha desde a lição 06 continua verde. É para isso que a rede de segurança foi armada antes do salto.

E porque teste verde não é a mesma coisa que app de pé, a prova manual:

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --port 8125
```

```bash
curl -s -X POST localhost:8125/users -H 'content-type: application/json' \
  -d '{"nome":"Ana","email":"ana2@exemplo.com"}'
# {"id":3,"nome":"Ana","email":"ana2@exemplo.com"}
```

O `alembic upgrade head` rodando sem erro é a prova de outra coisa: a `SYNC_DATABASE_URL` que apareceu no `database.py` funciona. Por que ela existe, e por que o Alembic ficou de fora da festa, é a próxima lição.

## O que você deve conseguir fazer agora

- Migrar uma stack SQLAlchemy de síncrona para assíncrona: engine, sessionmaker, sessão, repositories.
- Explicar por que essa migração não pode ser parcial — e por que o commit grande é honesto aqui.
- Decidir onde vai `await` com a régua "isso fala com o banco?", e justificar o `add` sem `await`.
- Explicar o que `expire_on_commit=False` evita, e ligar isso ao `MissingGreenlet`.
- Apontar, num diff, o que **não** mudou — e dizer o que isso revela sobre a arquitetura.
- Explicar por que o N+1 do `list_all` ficou pior, e por que a gente não o consertou aqui.
