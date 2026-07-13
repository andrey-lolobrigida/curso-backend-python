# Lição 07 — Migrações: o banco ganha controle de versão

## A dor: campo novo no model, banco velho no disco

Na lição 06 o `Resource` era só `id` e `nome`. Hoje o FairFare precisa distinguir quadra de chalé de sala de ensaio — o model ganha um campo `tipo`. Você edita a classe, salva e... o banco no disco continua com a tabela antiga. O `create_all`, você lembra, **cria o que falta e nunca altera o que existe**. Na lição 06, a saída foi apagar o `fairfare.db` e recriar.

Funcionou porque o banco tinha uma Ana e uma quadra. Agora imagine o FairFare no ar, com mil usuários e as reservas do fim de semana. "Apaga o banco e recria" deixa de ser uma solução e vira uma demissão. Em produção, dado é sagrado; o schema é que precisa se mover — **sem derrubar os dados que já moram nele**.

## Migração = commit de schema

A analogia é direta: o que o git faz pelo seu código, as **migrações** fazem pelo formato do seu banco. Cada mudança de schema vira um arquivo versionado, com data, descrição e um passo à frente ("adiciona a coluna") e um passo atrás ("remove a coluna").

O rigor: uma migração é um script de DDL (os comandos SQL que mudam estrutura — `CREATE TABLE`, `ALTER TABLE`) numa cadeia linear, onde cada migração aponta para a anterior. O banco guarda em qual elo da cadeia ele está; aplicar as migrações pendentes o leva ao presente, sem tocar nos dados. A ferramenta que faz isso no mundo SQLAlchemy é o **Alembic** (`uv add alembic`).

## Anatomia mínima

O `uv run alembic init alembic` criou três coisas que importam:

- **`alembic.ini`** — configuração geral. Só mexemos numa linha (a URL do banco, que apontamos para o `env.py` resolver).
- **`alembic/env.py`** — o ponto de encontro entre o Alembic e o *nosso* app. Nossas linhas:

```python
from app.database import DATABASE_URL, Base
import app.models  # noqa: F401  (registra as tabelas no metadata)

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)
...
target_metadata = Base.metadata
```

  Traduzindo: "Alembic, o banco é este, e a verdade sobre como o schema *deveria ser* está nos models pendurados na nossa `Base`". O import de `app.models` parece inútil (ninguém usa o nome), mas é ele que executa as classes e registra as tabelas no metadata — sem ele, o Alembic acha que o schema ideal é o vazio.

- **`alembic/versions/`** — a pasta onde vivem as migrações. Nosso histórico do git para o banco.

## Autogenerate não é mágica (é um rascunho)

O comando do dia a dia:

```bash
uv run alembic revision --autogenerate -m "usuarios e recursos"
```

O Alembic compara os dois lados — o metadata dos models (como *deveria* ser) contra o banco real (como *está*) — e **escreve um rascunho** da migração que fecha a diferença. A primeira, a baseline, saiu assim (trecho):

```python
def upgrade() -> None:
    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table("users", ...)


def downgrade() -> None:
    op.drop_table("users")
    op.drop_table("resources")
```

A palavra importante é *rascunho*. O autogenerate enxerga bem o grosso (tabela nova, coluna nova) e enxerga mal sutilezas (renomear coluna vira "dropa uma, cria outra" — adeus, dados). Regra do curso: **sempre leia o arquivo gerado antes de aplicar**. Ele é uma proposta, não uma sentença.

Aplicar é:

```bash
uv run alembic upgrade head
```

`head` = a migração mais recente, mesma metáfora do git.

### Se você seguiu o curso na ordem, esse comando vai falhar

E é justo que falhe. Você tem o `fairfare.db` da lição 06, e dentro dele as tabelas `users` e `resources` já existem — criadas na mão pelo `create_all`. A migração que acabamos de gerar quer *criar* essas mesmas duas tabelas. O banco reclama:

```
sqlite3.OperationalError: table resources already exists
```

O Alembic não é adivinho. Sem a tabela de controle `alembic_version`, ele assume que o banco está zerado e começa da primeira migração. Falta contar a ele o que já aconteceu:

```bash
uv run alembic stamp 92b6a0b6e69f
```

Traduzindo: "estas tabelas já existem e correspondem exatamente a esta migração; anote como aplicada e siga daí". Nada é executado no schema — só a `alembic_version` é escrita. Depois disso, `uv run alembic upgrade head` roda liso.

E o `stamp` não é remendo nosso para sair de uma sinuca. É a operação de **adotar** um banco que já existe para dentro do controle de versão: o banco existe há anos, a primeira migração descreve o que ele já é, e o `stamp` alinha a história com a realidade sem tocar em um dado. Todo projeto legado que ganha Alembic passa por esse momento. Você acabou de ganhar o conceito de graça.

Os dois caminhos, para ficar claro quem é quem:

- **Clone limpo, sem `fairfare.db`:** só `uv run alembic upgrade head` — materializa o banco inteiro do zero.
- **Com o banco da lição 06:** `uv run alembic stamp 92b6a0b6e69f`, depois `uv run alembic upgrade head`.

Com a baseline no lugar, o `Base.metadata.create_all(engine)` do `main.py` foi demitido, como prometido: quem cria e evolui schema agora é migração, e mais ninguém.

## A evolução de verdade: `tipo` chega sem demolição

Agora o motivo do capítulo. O model mudou:

```python
class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    tipo: Mapped[str] = mapped_column(server_default="quadra")
```

Novo `--autogenerate`, e o rascunho desta vez diz:

```python
def upgrade() -> None:
    op.add_column(
        "resources", sa.Column("tipo", sa.String(), server_default="quadra", nullable=False)
    )
```

Repare no `server_default="quadra"` — ele não está aí por estética. Pense na tabela `resources` *com linhas dentro*: chega uma coluna nova que não pode ser nula (`nullable=False`). O que escrever nas linhas que já existem? Sem resposta, o banco recusa a operação. O `server_default` é a resposta: "as antigas viram `quadra`". Coluna obrigatória em tabela habitada exige um valor para os moradores antigos — grave essa, porque ela morde em todo projeto real.

Uma fronteira que vale marcar agora, antes que você generalize demais: `server_default` é do banco, não da porta de entrada. Ele preenche linhas que o banco escreve sem o campo — e **não** torna o campo opcional na sua API. Se você mandar um `POST /resources` sem `tipo`, leva 422, e está certo: quem decide o que é obrigatório na borda é o schema Pydantic (lição 04), não a coluna.

`uv run alembic upgrade head`, e o banco da lição 06 — *com* a Ana e a quadra dentro — ganhou a coluna sem perder um byte. Nenhum `rm fairfare.db`. A dor da lição 06 está oficialmente curada.

(Os schemas Pydantic e a rota de criação também passaram a falar `tipo`, claro — veja o diff do commit.)

## O que você deve conseguir fazer agora

- Num clone limpo do repo, materializar o banco inteiro do zero: `uv run alembic upgrade head`.
- Explicar a diferença entre o metadata dos models e o banco real — e qual comando compara os dois.
- Treino sem compromisso: adicione uma coluna qualquer num model, rode `--autogenerate`, **leia** o rascunho gerado... e apague o arquivo e a linha do model (nada de commit).
- Explicar por que o `tipo` precisou de `server_default` — e o que o banco faria sem ele.
