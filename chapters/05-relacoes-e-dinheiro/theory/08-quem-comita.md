# Lição 08 — Quem comita?

Essa pergunta está pendurada desde o capítulo 4. Na lição 08 de lá:

> Quem deve comitar é uma pergunta do capítulo 5, quando as despesas chegarem e uma operação passar a mexer em várias tabelas de uma vez.

E na lição 12, na tabela das escolhas: o `commit()` mora no repository, e isso "funciona para uma operação por request".

As despesas chegaram. Uma despesa é uma linha em `expenses` e uma linha em `expense_shares` para cada participante. Uma operação, várias gravações. Hora de responder.

## O estrago

Primeiro, a despesa escrita no estilo que o FairFare tinha até agora. Cada método do repository comita o que gravou:

```python
# A versão "antes". Ela NÃO está no repositório: existiu só para esta medição.
async def create(self, group_id, paid_by, descricao, valor):
    expense = Expense(group_id=group_id, paid_by=paid_by, descricao=descricao, valor=valor)
    self.db.add(expense)
    await self.db.commit()
    ...

async def add_share(self, expense_id, user_id, valor):
    self.db.add(ExpenseShare(expense_id=expense_id, user_id=user_id, valor=valor))
    await self.db.commit()
    ...
```

O service chama `create` uma vez e `add_share` num laço, uma vez por participante. Agora, uma falha no meio. Coloquei um `RuntimeError` temporário antes da terceira parte, que faz o papel de "a conexão caiu" ou "o processo morreu". No banco de dev, acrescentei uma terceira pessoa ao grupo 1, a Carla, do mesmo jeito que a lição 04 pôs a Ana e o Bruno. Os seus ids podem ser outros:

```console
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/users -H 'content-type: application/json' -d '{"nome": "Carla", "email": "carla@fairfare.dev"}'
{"id":4,"nome":"Carla","email":"carla@fairfare.dev"}
201
$ curl -s -w '\n%{http_code}\n' -X POST localhost:8000/groups/1/members -H 'content-type: application/json' -d '{"user_id":4}'
{"user_id":4,"nome":"Carla"}
201
```

Depois, uma despesa de R$ 90 no mercado, paga pela Ana. O id da despesa vai ser 2, e não 1, porque o experimento do `CHECK` da lição 07 gastou o 1:

```console
$ curl -s -i -X POST localhost:8000/groups/1/expenses -H 'content-type: application/json' \
    -d '{"paid_by": 2, "descricao": "Mercado", "valor": "90.00"}'
HTTP/1.1 500 Internal Server Error
...
Internal Server Error
```

Um 500. Quem lançou a despesa acha que nada aconteceu. O banco discorda:

```console
fairfare=# SELECT id, paid_by, descricao, valor FROM expenses;
 id | paid_by | descricao | valor
----+---------+-----------+-------
  2 |       2 | Mercado   | 90.00
(1 row)

fairfare=# SELECT * FROM expense_shares;
 expense_id | user_id | valor
------------+---------+-------
          2 |       2 | 30.00
          2 |       3 | 30.00
(2 rows)
```

Uma despesa de R$ 90 com partes que somam R$ 60. A Carla não deve nada. A lição 07 inteira gastou esforço para a soma das partes fechar ao centavo, e aqui ela erra por trinta reais. Cada `commit()` fez exatamente o que prometia: gravou para sempre a sua parte. O problema é que ninguém perguntou se aquela parte, sozinha, fazia sentido.

Esse estrago não pode ficar no banco de dev: a lição 09 soma saldos, e uma despesa torta faria eles não fecharem em zero. Apaguei na mão, as partes primeiro (elas apontam para a despesa). Troque o 2 pelo id que o seu `SELECT` mostrou (vai ser 1 se você pulou o experimento da lição 07):

```console
fairfare=# DELETE FROM expense_shares WHERE expense_id = 2;
DELETE 2
fairfare=# DELETE FROM expenses WHERE id = 2;
DELETE 1
```

O teste que pega isso está em `tests/test_despesas.py`. Ele troca o `add_share` por uma versão que estoura na terceira chamada e depois olha o banco por fora da API, com a `engine_de_teste` da lição 03:

```python
async def test_despesa_nunca_fica_pela_metade(client, engine_de_teste, monkeypatch):
    ...
    monkeypatch.setattr(ExpenseRepository, "add_share", falha_na_terceira)
    with pytest.raises(RuntimeError):
        await cria_despesa(client, g, paid_by=1, valor="100.00")

    async with AsyncSession(engine_de_teste) as db:
        assert await db.scalar(select(func.count()).select_from(Expense)) == 0
        assert await db.scalar(select(func.count()).select_from(ExpenseShare)) == 0
```

Na versão "antes":

```console
$ uv run pytest -q tests/test_despesas.py::test_despesa_nunca_fica_pela_metade
>           assert await db.scalar(select(func.count()).select_from(Expense)) == 0
E           assert 1 == 0
...
1 failed in 0.25s
```

## A regra

O repository não sabe o que é uma operação. Ele sabe gravar uma despesa e sabe gravar uma parte. Quem sabe que "lançar uma despesa" é a despesa **mais** todas as partes é o service.

Então a regra do FairFare, daqui para frente:

- **O repository fala SQL.** Ele adiciona, consulta e faz `flush`. Nunca `commit()`, nunca `rollback()`.
- **O service decide o que é uma operação.** Ele abre a transação e a fecha.

O que é esse `flush`? Pense num contrato. Você manda o rascunho para o cartório, e ele fica na sua pasta, lá dentro. Ninguém mais vê. Se você desistir, o rascunho vai para o lixo. Quando você assina, o documento passa a valer para todo mundo. O `flush` é mandar o rascunho. O `commit` é assinar.

Agora o rigor. O `flush` executa de verdade o `INSERT` (ou `UPDATE`, ou `DELETE`) no Postgres, dentro da transação aberta. O banco confere as constraints nessa hora: o `CHECK`, a chave estrangeira, a `EXCLUDE` do capítulo 4. Um erro de constraint estoura no `flush`, não depois. O `id` gerado pelo banco volta para o objeto. Mas outras conexões não veem a linha. No `READ COMMITTED` do capítulo 4, só o que foi comitado é visível. O `commit` é o que torna tudo visível de uma vez. E o `rollback` desfaz tudo, inclusive o que já passou pelo `flush`.

O `ExpenseRepository` de verdade é assim:

```python
async def create(self, group_id: int, paid_by: int, descricao: str, valor: Decimal) -> Expense:
    expense = Expense(group_id=group_id, paid_by=paid_by, descricao=descricao, valor=valor)
    self.db.add(expense)
    await self.db.flush()
    await self.db.refresh(expense)  # criada_em vem do servidor
    return expense
```

O `refresh` fica. O `criada_em` tem `server_default`, e é o banco que preenche. Sem o refresh, o atributo fica expirado, e lê-lo depois seria I/O escondido. É o mesmo raciocínio da lição 02.

## `async with self.db.begin()`

E o service:

```python
async def create(self, group_id: int, data: ExpenseCreate) -> ExpenseOut:
    async with self.db.begin():
        if not await self.groups.exists(group_id):
            raise GroupNotFoundError
        membros = await self.groups.member_ids(group_id)
        participantes = data.participantes or sorted(membros)
        if data.paid_by not in membros or not set(participantes) <= membros:
            raise NotAMemberError
        expense = await self.expenses.create(group_id, data.paid_by, data.descricao, data.valor)
        for user_id, valor in dividir(data.valor, participantes).items():
            await self.expenses.add_share(expense.id, user_id, valor)
        expense = await self.expenses.get_with_shares(expense.id)
    return self._to_out(expense)
```

O `async with self.db.begin()` abre uma transação e cuida do fim dela. Se o bloco termina normalmente, ele comita. Se qualquer exceção atravessa o bloco, ele faz rollback e deixa a exceção seguir. Não tem `try`, não tem `commit()` esquecido num caminho, não tem `rollback()` esquecido no outro.

Repare no `GroupNotFoundError` e no `NotAMemberError`. Eles também atravessam o `begin()`. A transação desfeita não tinha gravado nada, e tudo bem: o rollback de quem não escreveu é só a conexão voltando limpa.

O mesmo teste, agora:

```console
$ uv run pytest -q tests/test_despesas.py::test_despesa_nunca_fica_pela_metade
1 passed in 0.20s
```

O `RuntimeError` estourou na terceira parte, o `begin()` desfez a despesa e as duas partes, e o banco ficou como estava antes.

## A pegadinha do autobegin

O `begin()` abraça o método **inteiro**, desde a primeira linha. Parece exagero. Por que não abrir a transação só onde começam as gravações, depois das conferências?

Eu tentei. O `begin()` foi para depois do `exists`:

```console
$ uv run pytest -q tests/test_despesas.py::test_despesa_dividida_entre_o_grupo_todo
E           sqlalchemy.exc.InvalidRequestError: A transaction is already begun on this Session.
1 failed in 0.41s
```

É o autobegin, da lição 08 do capítulo 4. A primeira consulta que vai ao banco, o `exists`, já abriu uma transação sozinha. Quando o `begin()` chega, ela já está aberta, e a sessão se recusa a abrir outra por cima.

E o SQLAlchemy está certo em reclamar. As leituras **fazem parte** da operação. O `member_ids` é o que decide se a despesa pode existir. A leitura que decide mora na mesma transação que a escrita que ela autoriza. Isso é necessário, mas não é suficiente: a lição 08 do capítulo 4 mostrou que transação não é cadeado, e o check-then-act da lição 07 de lá acontece com ou sem ela. A despesa está a salvo por outro motivo. Ninguém sai do grupo, então a lista que ela confere só cresce. Quando a decisão depende de um dado que outra request pode mudar ao mesmo tempo, é preciso cadeado. Ele chega na lição 11.

## O nome disso: Unit of Work

O que a gente acabou de fazer tem nome. **Unit of Work**, unidade de trabalho: um objeto que junta todas as mudanças de uma operação de negócio e grava tudo de uma vez, ou nada.

E a `AsyncSession` já é uma. Ela anota cada objeto que você adiciona, muda ou apaga. O `flush` manda as mudanças anotadas. O `begin()` marca onde a unidade começa e termina.

Muitos projetos escrevem uma classe `UnitOfWork` própria, com os repositories pendurados nela. Ela resolve um problema real: trocar de ORM, ou de banco, sem mexer nos services. Esse não é o nosso problema. O FairFare usa SQLAlchemy e Postgres, e um embrulho em volta da sessão seria uma camada a mais para ler, sem nada para comprar.

## A outra forma, medida

Existe um jeito ainda mais curto: abrir a transação no `get_db`, uma por request.

```python
# O código da tentação. NÃO está no repositório.
async def get_db():
    async with SessionLocal() as db, db.begin():
        yield db
```

Nenhum service precisa saber de transação. Fiz o teste. Tirei o `begin()` do `ExpenseService` e pus o `get_db` acima, com um `raise RuntimeError("o commit falhou")` depois do `yield`. É o dublê de um commit que falha de verdade: uma conexão que cai, ou o erro de serialização do `SERIALIZABLE` da lição 09 do capítulo 4, que pode chegar só no `COMMIT`.

```console
$ curl -s -i -X POST localhost:8000/groups/1/expenses -H 'content-type: application/json' \
    -d '{"paid_by": 2, "descricao": "Mercado", "valor": "90.00"}'
HTTP/1.1 201 Created
...
{"id":3,"group_id":1,"paid_by":2,"descricao":"Mercado","valor":"90.00","criada_em":"2026-10-12T01:26:43.825781Z","partes":[{"user_id":2,"valor":"30.00"},{"user_id":3,"valor":"30.00"},{"user_id":4,"valor":"30.00"}]}
```

Um `201`, com `id` 3 e as três partes. E o banco:

```console
fairfare=# SELECT id, descricao, valor FROM expenses;
 id | descricao | valor
----+-----------+-------
(0 rows)
```

Vazio. O erro só apareceu no log do uvicorn, depois da resposta:

```console
INFO:     127.0.0.1:47404 - "POST /groups/1/expenses HTTP/1.1" 201 Created
ERROR:    Exception in ASGI application
...
RuntimeError: o commit falhou
```

O cliente recebeu a confirmação de uma despesa que não existe. No FastAPI, o código depois do `yield` roda por padrão **depois** que a resposta saiu. Dá para mudar isso. Com `Depends(get_db, scope="function")` na rota, o fim da dependência roda antes da resposta:

```console
HTTP/1.1 500 Internal Server Error
...
Internal Server Error
```

Agora o cliente sabe que falhou. O tempo foi consertado.

E mesmo assim, não. Por dois motivos. Primeiro, fica implícito. Quem lê o service não vê a transação, e a correção depende de um parâmetro na rota que é fácil de esquecer. Segundo, amarra "uma request = uma transação". Toda request vira uma, inclusive a leitura longa que não precisava segurar nada, e inclusive a operação que precisaria de duas transações. Com o `begin()` no service, a fronteira está escrita onde a decisão é tomada.

## O diff que toca o passado

A regra só vale se valer em todo lugar. Uma regra que vale em metade do código não é regra. É uma sugestão, e o próximo a escrever um repository vai copiar a metade errada.

Então este commit mexe no que já existia:

- **`UserRepository`, `ResourceRepository`, `GroupRepository`, `BookingRepository`:** todo `commit()` vira `flush()`. Os `rollback()` somem. No `BookingRepository.create`, a violação da `EXCLUDE` (o `23P01`) agora chega no `flush`, e quem desfaz é o `begin()` do service.
- **`BookingService` e `GroupService`:** o `create`, o `cancel` e o `add_member` ganham o `begin()` abraçando o método inteiro. O `except BookingOverlapError` fica **dentro** do bloco: ele vira `BookingConflictError`, que atravessa o `begin()` e desfaz a transação. Leituras puras, como `get` e `list_all`, ficam sem `begin()`.
- **Os routers de `users` e `resources`:** eles não têm service. Ali, quem diz o que é uma operação é o router:

```python
@router.post("", status_code=201, response_model=UserOut)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # Sem service, quem diz o que é "uma operação" é o router (lição 08).
    try:
        async with db.begin():
            return await UserRepository(db).create(nome=user.nome, email=user.email)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="email já cadastrado")
```

O `IntegrityError` do e-mail repetido estoura no `flush`, o `begin()` desfaz, e o router traduz em `409`, como antes.

A prova de que não sobrou nenhum:

```console
$ grep -rn "commit()\|rollback()" app/
$
```

E a suíte inteira, com o teste de concorrência do capítulo 4 rodado cinco vezes à parte:

```console
$ uv run pytest -q -W error
65 passed in 2.42s
$ for i in 1 2 3 4 5; do uv run pytest -q tests/test_concorrencia.py | tail -1; done
2 passed in 0.34s
2 passed in 0.33s
2 passed in 0.34s
2 passed in 0.34s
2 passed in 0.35s
```

## Duas promessas cumpridas de carona

A lição 06 avisou que `"1e2"` voltava como `"1E+2"`. Agora a resposta sai do objeto que o `refresh` leu do banco, e o `Numeric(12, 2)` devolve duas casas. O teste `test_valor_em_notacao_cientifica_volta_com_duas_casas` confere: `"1e2"` volta `"100.00"`.

A lição 07 afirmou que o único caminho até a `dividir` passa pelo tipo `Dinheiro`:

```console
$ grep -rn "dividir(" app/
app/services/expense.py:32:            for user_id, valor in dividir(data.valor, participantes).items():
app/services/divisao.py:6:def dividir(total: Decimal, participantes: list[int]) -> dict[int, Decimal]:
```

Uma chamada só, com `data.valor`. E o `data` é um `ExpenseCreate`, cujo `valor` é `Dinheiro`.

## O que fica declarado

- **Não há endpoint para listar, editar ou apagar despesas.** É escolha. O capítulo precisa de despesas para ensinar saldos e quitações, não de um CRUD completo.
- **A dívida do capítulo 4 está paga.** A lição 12 de lá disse que o `commit()` no repository "funciona para uma operação por request". Agora existe uma operação com várias gravações, e o `commit()` saiu de todos os repositories.

## O que você deve conseguir fazer agora

- Dizer onde fica o `async with self.db.begin()` num service novo: na primeira linha do método, abraçando as leituras que decidem.
- Explicar a diferença entre `flush` e `commit`: o que cada um manda ao banco e quem consegue ver o resultado.
- Olhar uma operação com três gravações, imaginar uma falha na segunda e dizer o que o banco guarda: com o `begin()` no service, nada. Com um `commit()` por repository, a primeira.
- Explicar por que o `201` da transação por request pode mentir, e por que o `scope="function"` corrige o tempo mas não o resto.
