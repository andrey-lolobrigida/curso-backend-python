# Lição 05 — Persistência: o FairFare ganha memória

## A dor curada (teste você mesmo)

Suba o servidor, crie a Ana, derrube tudo com Ctrl+C, suba de novo:

```console
$ curl -s localhost:8000/users
[{"id":1,"nome":"Ana","email":"ana@example.com"}]
```

Ela sobreviveu. A amnésia da lição 03 está curada: os usuários agora moram num **banco de dados**, fora da memória do processo.

O banco é o **SQLite**, e a primeira surpresa é onde ele mora: num arquivo, `fairfare.db`, na raiz do projeto. Sem servidor para instalar, sem senha, sem configuração — a biblioteca `sqlite3` já vem com o Python. Uma frase de honestidade: bancos de produção (PostgreSQL, MySQL) são *servidores*, processos separados feitos para muitos acessos simultâneos — e o Postgres nos espera no capítulo 4. O SQLite é a escolha certa de agora porque nos deixa aprender todo o resto sem instalar nada.

Como `fairfare.db` é um banco *local* — seu, de testes, da sua máquina — ele não é código-fonte. Por isso `*.db` entrou no `.gitignore` deste commit.

## O ciclo: connect → execute → commit → close

Toda conversa com o SQLite segue o mesmo ritual. Olhe o `create_user` novo:

```python
@app.post("/users", status_code=201, response_model=UserOut)
def create_user(user: UserCreate):
    conn = get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO users (nome, email) VALUES (?, ?)",
            (user.nome, user.email),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="email já cadastrado")
    row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    conn.close()
    return dict(row)
```

Linha a linha:

- **`get_conn()`** abre a conexão com o arquivo (e configura `row_factory = sqlite3.Row`, que faz as linhas saírem acessáveis por nome de coluna em vez de por índice).
- **`conn.execute(...)`** roda o SQL. O INSERT ainda não está gravado em pedra —
- **`conn.commit()`** é quem grava. Sem commit, a mudança evapora quando a conexão fecha. (Por que essa cerimônia em dois passos? Transações — e elas merecem capítulo próprio, o 4.)
- **`sqlite3.IntegrityError`** é o banco dizendo "isso viola uma regra minha". Qual regra? A que declaramos na criação da tabela: `email TEXT NOT NULL UNIQUE`. Duas Anas com o mesmo email — o problema que o schema da lição 04 *não podia* resolver — agora dá `409 Conflict`. Repare: quem garante a unicidade é o banco, não o Python.
- **`cursor.lastrowid`** devolve o `id` que o banco acabou de atribuir; buscamos a linha de volta para responder ao cliente.
- **`conn.close()`** devolve os recursos. Toda rota abre, toda rota fecha.

Há também o `ensure_tables()`, que roda na subida do app e cria a tabela `users` se não existir. É tosco de propósito; a lição 07 aposenta esse padrão com estilo.

## Placeholders `?`, nunca f-string

Repare no INSERT: os valores entram como `?` mais uma tupla, e **nunca** interpolados na string. A tentação de escrever `f"... WHERE email = '{email}'"` é grande. Veja o que ela custa. Um script de sandbox (não está no app):

```python
import sqlite3

conn = sqlite3.connect("fairfare.db")
conn.row_factory = sqlite3.Row

email = "' OR '1'='1"
query = f"SELECT * FROM users WHERE email = '{email}'"
print("query executada:", query)
for row in conn.execute(query):
    print(dict(row))
```

Saída real:

```console
$ uv run python inj.py
query executada: SELECT * FROM users WHERE email = '' OR '1'='1'
{'id': 1, 'nome': 'Ana', 'email': 'ana@example.com'}
```

O "email" malicioso fechou a aspa, injetou um `OR '1'='1'` — verdadeiro para toda linha — e a query devolveu **a tabela inteira**. Se essa string vem de um campo de formulário, qualquer visitante do seu site lê (ou apaga) seu banco. Isso tem nome, **SQL injection**, décadas de história e um lugar cativo no capítulo 5. Com placeholder `?`, o valor viaja separado do SQL e nunca é interpretado como comando: a mesma busca devolveria zero linhas, educadamente.

Regra inegociável deste curso: **valor entra em query só via placeholder**.

## Espiando o banco por fora

Até aqui você só viu os dados pela API. Vale abrir o arquivo direto, sem passar pelo app — é assim que você vai depurar "mas eu *jurava* que tinha salvado":

```bash
uv run python -m sqlite3 fairfare.db "SELECT * FROM users"
```

Esse cliente vem embutido no Python 3.12 — o mesmo que a lição 01 pinou —, então você já tem, sem instalar nada. De brinde, um lembrete que vale para a carreira toda: a biblioteca padrão te dá mais coisa do que você imagina.

Existe também o `sqlite3` standalone (`apt install sqlite3`, `brew install sqlite`), mais completo, e você vai encontrá-lo em todo tutorial por aí. Duas diferenças, para não estranhar:

- A saída vem como tupla Python — `(1, 'Ana', 'ana@example.com')` — em vez do `1|Ana|ana@example.com` do standalone.
- Os atalhos com ponto (`.tables`, `.schema`) **não existem** no embutido: ele aceita SQL, mais `.help` e `.quit`. Perda pequena, porque esses atalhos são SQL disfarçado e você pode escrever o original:

```bash
uv run python -m sqlite3 fairfare.db "SELECT name FROM sqlite_master WHERE type='table'"
uv run python -m sqlite3 fairfare.db "SELECT sql FROM sqlite_master WHERE name='users'"
```

Repare no que acabou de acontecer: o `sqlite_master` é a tabela onde o SQLite guarda o catálogo dele mesmo. As tabelas do seu banco estão descritas **dentro** do seu banco. Guarde a ideia — ela volta na lição 07, quando o Alembic precisar de uma tabela só para anotar o que já aplicou.

## A dor nova, contada em linhas

A amnésia custou caro. Conte comigo, no `create_user`: abrir conexão, try/except de integridade, commit, buscar a linha de volta, fechar conexão no caminho feliz E no caminho triste, converter `Row` em `dict`... O miolo — "insere um usuário" — são duas linhas; o resto é cerimônia. E esse ritual se repete, com variações, nas *três* rotas.

Agora projete: o FairFare ainda vai ter recursos, reservas, grupos, despesas. Três, quatro, cinco entidades × esse boilerplate em cada rota. Alguém precisa ser contratado para cuidar dessa burocracia.

A lição 06 faz a entrevista.

## O que você deve conseguir fazer agora

- Abrir o banco direto no terminal, com `uv run python -m sqlite3`, e conferir os dados sem passar pela API.
- Explicar o papel de cada etapa do ciclo connect → execute → commit → close.
- Explicar por que o 409 do email duplicado só ficou possível nesta lição, e não na 04.
- Dizer por que `*.db` está no `.gitignore`.
- Completar a frase: "valor entra em query só via ______" — e dizer o que acontece se não.
