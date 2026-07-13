# Lição 08 — Repositories: o acesso a dados ganha endereço fixo

## A dor: a rota com três empregos

Olhe o `create_user` como ele estava ao fim da lição 07:

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

Uma função, três empregos: fala HTTP (status codes, `HTTPException`), decide política ("email duplicado vira 409") e opera o banco (`add`, `commit`, `refresh`). Parece inofensivo em dez linhas. As consequências aparecem quando você tenta:

- **Testar a lógica.** Quer conferir que usuário duplicado é rejeitado? Hoje só há um jeito: subir o app e fazer uma request. A regra está soldada no HTTP.
- **Mudar o banco.** Se um dia a forma de gravar mudar (outra query, outro banco, cache na frente), a caçada é rota por rota, porque cada uma carrega seu próprio SQLAlchemy.

O emprego de "operar o banco" precisa de um endereço fixo. É a primeira camada que extraímos deliberadamente.

## Repository: a única porta para o banco daquela entidade

A analogia: um almoxarifado com balcão. Ninguém entra na prateleira pegando peça — você chega no balcão e pede "me vê um parafuso M6". Quem sabe o corredor, a caixa e o estoque é o almoxarife. Se o almoxarifado for reorganizado inteiro, você não fica sabendo: continua pedindo parafuso M6 no mesmo balcão.

O rigor: um **repository** é uma classe que encapsula todo o acesso a dados de uma entidade atrás de métodos com nome de intenção. O novo `app/repositories.py`:

```python
class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome: str, email: str) -> User:
        user = User(nome=nome, email=email)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def list_all(self) -> list[User]:
        return list(self.db.scalars(select(User)))
```

(`ResourceRepository` é o gêmeo para recursos — veja o arquivo.) Repare no que o repository **não** sabe: nada de `HTTPException`, nada de status code, nada de request. Ele fala apenas a língua dos dados: recebe valores, devolve objetos ou `None`.

## O antes e o depois

A mesma rota, agora com o balcão no lugar:

```python
@app.post("/users", status_code=201, response_model=UserOut)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    try:
        return UserRepository(db).create(nome=user.nome, email=user.email)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="email já cadastrado")
```

Leia em voz alta: "crie um usuário com este nome e email; se o banco reclamar de duplicata, responda 409". A rota virou uma frase. O `add`/`commit`/`refresh` não sumiu — mudou de endereço: agora mora no repository, escrito uma vez, com nome de intenção. E o comportamento externo é **idêntico**: mesmos curls, mesmos status codes, mesmos corpos. Refatorar é isso — mudar a estrutura sem mudar o comportamento observável.

## "Mas isso é só indireção?"

Pergunta justa. Hoje, quase: movemos dez linhas de lugar e criamos uma classe. Se o FairFare morresse neste commit, seria burocracia.

Ele não morre — e o pagamento vem em parcelas datadas:

- **Lição 11:** os testes vão trocar o banco real por um descartável em memória *sem tocar em nenhuma rota*. Só é barato porque o acesso a dados tem endereço fixo.
- **Capítulo 2:** o app vira async; as queries mudam de forma. Mexeremos nos repositories, e as rotas nem ficam sabendo.
- **Capítulo 4:** SQLite dá lugar ao Postgres, e queries espertas (índices, locks) entram — tudo atrás do mesmo balcão.

Guarde o princípio, que vale mais que o padrão: **um padrão de projeto se justifica pelo que ele habilita, não pela elegância de hoje**. Quando alguém propuser uma camada nova, pergunte "o que ela vai habilitar?". Se a resposta for silêncio, é burocracia.

## Por que uma classe (e não funções soltas)?

`create_user_no_banco(db, nome, email)`, `busca_usuario(db, user_id)`... funcionaria. A classe ganha por dois motivos práticos: **agrupa o que muda junto** — as operações de usuário formam uma família, e quando a persistência de usuário mudar, muda tudo num arquivo só; e **a sessão entra uma vez** — `UserRepository(db)` no construtor, em vez de `db` de carona em cada chamada.

## O que você deve conseguir fazer agora

- Escrever de cabeça um método `count()` para o `ResourceRepository` (dica: `len` da lista serve por enquanto — o jeito fino chega no capítulo 4).
- Responder sem olhar: "onde mora o SELECT de listar usuários?" — arquivo e método.
- Apontar, na rota nova, o que é tradução HTTP e o que é acesso a dados.
- Explicar a frase "padrões se justificam pelo que habilitam" usando a lição 11 como exemplo (mesmo sem tê-la lido ainda).
