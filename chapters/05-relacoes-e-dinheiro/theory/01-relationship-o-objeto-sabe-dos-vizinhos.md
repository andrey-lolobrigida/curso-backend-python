# Lição 01 — `relationship()`: o objeto sabe dos vizinhos

O capítulo 4 deixou uma conta pendurada. Na lição 05, um único `GET /bookings`, com 2002 reservas no banco, fez **4005 consultas**. Duas por reserva, mais a lista. A lição declarou o problema e disse onde ele morria: aqui, no capítulo 5.

Ele não morre nesta lição. Morre na 03. Esta aqui monta a peça que falta para matá-lo: um jeito de o objeto `Booking` saber quem são os vizinhos dele.

## O que a chave estrangeira já faz

Abra o `app/models/booking.py`. A reserva guarda o usuário assim:

```python
user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
```

Para o Python, `user_id` é um número. Um `int`, e nada mais. Para o banco, ele é um pouco mais: o `ForeignKey` virou uma **chave estrangeira** (FK) na migração, e o Postgres garante que todo `user_id` aponta para uma linha que existe em `users`. Tente gravar uma reserva com `user_id = 999999` e ele recusa.

Mas repare no que a FK **não** faz. Ela garante que o usuário existe. Ela não traz o usuário. Se você quer o nome de quem reservou, alguém precisa ir buscar.

Hoje, quem busca é o `_to_out`, no `app/services/booking.py`:

```python
async def _to_out(self, booking: Booking) -> BookingOut:
    user = await self.users.get(booking.user_id)
    resource = await self.resources.get(booking.resource_id)
    ...
```

Ele pega o número, chama o repository, e o repository faz um `SELECT`. Um para o usuário, outro para o recurso. Por reserva. Daí as 4005.

O problema não é o `_to_out` ser burro. É que ele não tem outra opção. O objeto `Booking` sabe o **número** do vizinho, mas não sabe o **caminho** até ele. Cada pedaço de código que quer o nome precisa refazer a busca na mão.

## `relationship()`

Pense num envelope. O número do apartamento está escrito nele: "apto 42". Isso é a FK. O prédio garante que o 42 existe, e ninguém consegue entregar uma carta para o apto 9000.

Só que o número sozinho não leva você a lugar nenhum. Você ainda precisa achar a escada, subir, bater na porta. A `relationship()` é o porteiro. Você mostra o envelope e diz "me leva até lá", e ele leva.

Agora, o rigor. Uma `relationship()` é **configuração do ORM**, não coluna. Ela diz ao SQLAlchemy: "este objeto tem um vizinho do tipo `User`, e o caminho até ele é a FK `user_id`". Com isso, `booking.user` passa a ser um objeto `User` de verdade, com `nome`, `email` e tudo.

O banco não fica sabendo de nada. Não há coluna `user` na tabela `bookings`, e nunca vai haver. A FK `user_id` continua lá, fazendo o mesmo trabalho de antes. A relação mora inteira do lado do Python.

## O diff

Duas linhas no fim da classe, e os imports que elas pedem:

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.resource import Resource
from app.models.user import User
```

```python
    # A FK diz ao banco que a linha existe. A relação diz ao Python como chegar nela (lição 01).
    user: Mapped[User] = relationship()
    resource: Mapped[Resource] = relationship()
```

Três coisas para ler aí.

**`Mapped[User]`, e não `Mapped[list[User]]`.** Uma reserva tem **um** usuário. Um usuário pode ter muitas reservas. Visto do lado da reserva, é uma relação **muitos-para-um**: muitas reservas apontam para um usuário. Por isso o tipo é um `User` só. O SQLAlchemy lê a anotação e entende o formato.

**Nenhum argumento no `relationship()`.** Como ele sabe que o caminho é o `user_id`? Ele procura. Na tabela `bookings`, existe uma FK, e só uma, apontando para `users`. Não há dúvida possível, então ele não pergunta. Se um dia houvesse duas (digamos, `user_id` e `cancelado_por`, ambas para `users`), ele pararia e pediria que você dissesse qual é qual.

**`user_id` continua existindo.** A relação não substitui a coluna. As duas convivem: `booking.user_id` é o número, `booking.user` é o objeto. O `_to_out` desta lição continua usando o número e buscando pelos repositories, exatamente como antes. Ninguém no app lê `booking.user` ainda.

## A prova de que não é coluna

Se a relação fosse coluna, o Alembic enxergaria. O autogenerate compara os models com o banco, e uma coluna nova no model vira uma operação de migração. O `alembic check` faz essa mesma comparação sem gerar arquivo (lição 12 do capítulo 4, item 8).

Rodei no meu banco de dev, depois do diff:

```console
$ uv run alembic check
...
No new upgrade operations detected.
```

*(Cortei as linhas `INFO` do começo.)*

Nada. Nenhuma operação sobre `bookings`, nenhuma sobre `user` ou `resource`. As duas linhas novas do model não mudaram uma vírgula do que o banco precisa ter. A relação acrescentou **zero** operações.

Se você não apagou a `bancada_reservas` no fim do capítulo 4, vai ver um `FAILED` reclamando só dela (item 8 da lição 12 do capítulo 4).

E a suíte, que não sabe de relação nenhuma, continua como estava:

```console
$ uv run pytest -q -W error
..............................                                           [100%]
30 passed in 1.48s
```

## O porteiro em ação

Ninguém no app usa a relação ainda. Mas dá para ver o porteiro trabalhando, num script de bancada, contra o banco de dev. A reserva de id 1 é a do seed da lição 06 do capítulo 4:

```python
import asyncio

from app.database import SessionLocal, engine
from app.models import Booking


def vizinhos(s):
    booking = s.get(Booking, 1)
    return booking.user_id, booking.user.nome, booking.resource.nome


async def main():
    async with SessionLocal() as db:
        print(await db.run_sync(vizinhos))
    await engine.dispose()


asyncio.run(main())
```

```console
$ uv run python vizinhos.py
(1, 'Semente', 'Quadra 1')
```

O número, e os dois nomes. Repare que nenhuma linha do script chama um repository ou escreve um `SELECT` para buscar o usuário. O script pediu `booking.user.nome`, e o nome veio.

E repare num detalhe estranho: o `run_sync`. O script não lê `booking.user` direto no `main`, com um `await` na frente. Ele empacota a leitura numa função comum e entrega essa função para a sessão rodar. Por quê? Guarde a pergunta. Ela é a lição 02 inteira.

## `back_populates`: o outro lado

A reserva sabe chegar ao usuário. E o usuário, sabe chegar às reservas dele? Hoje, não. A relação só existe de um lado.

Dá para ter os dois. O SQLAlchemy chama isso de `back_populates`: cada lado declara a relação e diz qual é o atributo correspondente do outro lado. Ficaria mais ou menos assim (**pseudocódigo**, isto não está no FairFare):

```python
# PSEUDOCÓDIGO: não está no repositório.
class User(Base):
    ...
    bookings: Mapped[list[Booking]] = relationship(back_populates="user")


class Booking(Base):
    ...
    user: Mapped[User] = relationship(back_populates="bookings")
```

Do lado do `User`, o tipo vira `list[Booking]`: é o lado **um-para-muitos**, um usuário com várias reservas. O `back_populates` amarra os dois atributos, para o SQLAlchemy manter os dois lados coerentes na memória.

Por que não entra? Porque hoje ninguém navega do usuário para as reservas. O FairFare não tem um "minhas reservas", e o capítulo não precisa de um. A regra do curso vale aqui também: uma coisa só entra quando alguém precisa dela. Quando alguém precisar, são duas linhas.

## A pergunta que fica

O script mostrou que `booking.user.nome` funciona. Mas o objeto `Booking` saiu do banco só com as colunas de `bookings`. O nome do usuário mora em outra tabela.

Então, quando o Python lê `booking.user`, **quem** vai ao banco buscar o usuário? E **quando**?

A resposta explica o `run_sync`, e vai explicar um erro que você ainda não viu. Lição 02.

## O que fica declarado

- **O `_to_out` não mudou.** O `GET /bookings` continua com duas consultas por reserva. A relação existe, mas o app ainda não a usa. Morre na lição 03.
- **A relação só existe do lado da reserva.** `User` e `Resource` não sabem das reservas deles. Entra quando um capítulo precisar.
- **O script da bancada foi descartável**, rodado à mão, fora do repositório.

## O que você deve conseguir fazer agora

- Explicar a diferença entre a FK `user_id` e a relação `user`: quem garante o quê, e onde cada uma mora.
- Dizer por que o `alembic check` não viu nada depois do diff.
- Escrever a relação muitos-para-um de outro model. Por exemplo: se um `Resource` tivesse um `dono_id` apontando para `users`, como seria o `Resource.dono`? E por que o tipo seria `Mapped[User]`, e não `Mapped[list[User]]`?
