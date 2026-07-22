# Lição 06 — Models: contratamos um ORM

## A dor: o boilerplate × N entidades

Faça as contas da lição 05. Cada rota: abrir conexão, montar SQL na mão, commit, converter `Row` em dict, fechar conexão nos dois caminhos. Uns dez toques de cerimônia por rota, três rotas por entidade. O FairFare vai ter usuários, recursos, reservas — e mais adiante grupos e despesas. É burocracia crescendo em linha reta com o produto.

O empregado que contratamos para isso chama-se **ORM** — Object-Relational Mapper. Em uma frase: ele mapeia tabela ↔ classe e linha ↔ objeto, e o SQL do dia a dia vira detalhe de implementação. O nosso é o **SQLAlchemy**, o ORM de referência do mundo Python (`uv add sqlalchemy`).

## A tabela agora é uma classe

O arquivo novo `app/models.py`:

```python
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
```

Isso é um **model**: a descrição, em Python, de uma tabela do banco. `Mapped[int]` diz o tipo da coluna; `mapped_column(...)` adiciona o que o tipo sozinho não conta (chave primária, unicidade). O `CREATE TABLE` da lição 05 — `id INTEGER PRIMARY KEY`, `email TEXT UNIQUE` — está todo aqui, só que numa classe que o resto do código pode importar e o editor pode autocompletar.

Pela terceira vez no capítulo, type hints são material de construção: primeiro nas rotas (`user_id: int`), depois nos schemas (`nome: str`), agora nas colunas (`Mapped[str]`). É a assinatura do nosso stack.

E repare no ganho imediato: a **segunda entidade custou seis linhas**. O `Resource` (por ora só `id` e `nome` — ele cresce na lição 07) ganhou as rotas POST/GET no `main.py` sem uma linha de SQL. Na lição 05, esse mesmo recurso teria custado outro `ensure_tables`, outro ciclo connect/commit/close por rota, outro punhado de `dict(row)`.

## Session: o carrinho de compras de mudanças

A conversa com o banco agora passa pela **Session**. O `create_user` novo:

```python
@app.post("/users", status_code=201, response_model=UserOut)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    new_user = User(nome=user.nome, email=user.email)
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="email já cadastrado")
    db.refresh(new_user)
    return new_user
```

Pense num carrinho de compras: `db.add(new_user)` põe o objeto no carrinho — nada foi ao banco ainda; `db.commit()` fecha a compra — é aí que o INSERT acontece, tudo ou nada; `db.refresh(new_user)` volta na prateleira para pegar o que o banco preencheu (o `id` gerado). O rigor: esse padrão se chama *unit of work* — a Session acumula mudanças pendentes e as aplica de uma vez no commit.

As leituras também mudaram de cara:

- `db.get(User, user_id)` — busca por chave primária; devolve o objeto ou `None`. O `SELECT ... WHERE id = ?` de antes, em uma chamada.
- `db.scalars(select(User))` — o `SELECT * FROM users`, devolvendo objetos `User` prontos em vez de `Row`s para converter.

O `IntegrityError` é o mesmo aviso de sempre do banco ("email duplicado"), só que agora com o sobrenome do SQLAlchemy. E os schemas de saída ganharam `model_config = ConfigDict(from_attributes=True)` — um aviso ao Pydantic: "os dados vêm como atributos de objeto (`user.nome`), não como chaves de dict".

## `Depends(get_db)`: a primeira injeção de dependência

De onde vem o `db` das rotas? Do novo `app/database.py`:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

E na assinatura da rota: `db: Session = Depends(get_db)`. Isso é **injeção de dependência** — a primeira do curso. Em vez de cada rota abrir e fechar sua sessão (o abre/fecha manual da lição 05, lembra?), a rota *declara* "preciso de uma sessão" e o FastAPI providencia.

O `yield` é o truque: o FastAPI executa `get_db()` até o `yield` e entrega a sessão à rota; quando a response sai, ele retoma a função, e o `finally` fecha a sessão — mesmo se a rota explodiu no meio. Abre-antes, fecha-depois, garantido, para toda rota, escrito uma vez. Guarde o nome `get_db`: essa pequena função vai pagar um dividendo desproporcional na lição 11.

## A limitação anunciada

Uma linha do `main.py` merece desconfiança:

```python
Base.metadata.create_all(engine)
```

É o sucessor do `ensure_tables()`: na subida, cria as tabelas que os models descrevem. Mas com uma regra sorrateira: **cria o que não existe, nunca altera o que existe**. A tabela `users` do seu `fairfare.db` da lição 05? O `create_all` a encontra, dá de ombros e segue — mesmo que o model tenha mudado.

Foi por isso que, neste commit, **apagamos o banco** (`rm fairfare.db`): o arquivo antigo não tinha a tabela `resources`, e recriar do zero era o caminho curto. Doeu pouco porque só tínhamos a Ana. Guarde essa sensação de "apaguei o banco para mudar o schema" — ela é a dor inteira da próxima lição.

## O que você deve conseguir fazer agora

- Narrar o caminho completo de um `POST /users`: request → validação do schema → `User(...)` → `add` → `commit` → `refresh` → response.
- Dizer o que `db.get(User, 1)` faz — e o que devolve se o usuário não existe.
- Explicar o `yield` do `get_db` em duas frases: o que roda antes dele, o que roda depois.
- Apontar a linha do `main.py` que vai ser demitida na lição 07, e por quê.
