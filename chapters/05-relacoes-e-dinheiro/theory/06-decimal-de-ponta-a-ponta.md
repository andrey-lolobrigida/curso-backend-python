# Lição 06 — `Decimal` de ponta a ponta

A lição 05 terminou com uma pergunta: se o `float` não serve, o que serve? A resposta já estava no script, fazendo papel de lupa. É o `Decimal`.

Mas trocar o tipo numa variável não resolve nada. O valor de uma despesa atravessa três fronteiras: chega como JSON, vira objeto Python e é gravado no banco. Depois faz o caminho de volta. Se uma dessas fronteiras falar `float`, o erro entra por ali. Esta lição fecha as três.

## O `Decimal`

Pense numa calculadora de balcão. Ela conta em base 10, do jeito que você conta dinheiro, e mostra exatamente as casas que você digitou. O `Decimal`, do módulo `decimal` da biblioteca padrão, é essa calculadora.

O rigor: um `Decimal` guarda um número **em base 10**, como uma sequência de dígitos e um expoente. `0.1` vira o dígito `1` com expoente `-1`. Sem dízima binária, sem vizinho mais próximo. A precisão das contas é a que você pedir (28 dígitos significativos por padrão).

Só que tem uma pegadinha, e ela é a lição inteira em uma linha:

```console
$ uv run python -c '
from decimal import Decimal
print(Decimal("0.1"), Decimal(0.1))
print(Decimal("0.1") + Decimal("0.2"))'
0.1 0.1000000000000000055511151231257827021181583404541015625
0.3
```

`Decimal("0.1")` nasce de um texto e é exatamente um décimo. `Decimal(0.1)` nasce de um `float`, e o `float` já chegou torto. O `Decimal` só copia o erro, dígito por dígito. Foi assim que ele serviu de lupa na lição 05.

A regra: **`Decimal` nasce de string, nunca de float.** Se o número passou por um `float` em algum momento, o estrago já aconteceu, e nenhum `Decimal` depois desfaz.

## No banco: `Numeric(12, 2)`

O Postgres tem o equivalente: o tipo `numeric`. Ele também conta em base 10. No model, ele aparece como `Numeric(12, 2)`.

Os dois números:

- **12 é a precisão:** o total de dígitos, somando os dois lados da vírgula.
- **2 é a escala:** quantos desses dígitos ficam depois da vírgula.

Sobram 10 dígitos para a parte inteira. O maior valor é `9999999999.99`, perto de dez bilhões. Para dividir o chalé, dá e sobra. E o Postgres conta isso sozinho quando você passa do limite. Os comandos desta lição vão no `psql` interativo do banco de dev, que se abre com `docker compose exec postgres psql -U fairfare -d fairfare` (o prompt vira `fairfare=#`):

```console
fairfare=# SELECT 12345678901.00::numeric(12, 2);
ERROR:  numeric field overflow
DETAIL:  A field with precision 12, scale 2 must round to an absolute value less than 10^10.
```

Agora o `numeric` fazendo o que o `float` não faz, lado a lado, no `psql` do banco de dev:

```console
fairfare=# SELECT 0.1::numeric + 0.2::numeric, 0.1::float8 + 0.2::float8;
 ?column? |      ?column?
----------+---------------------
      0.3 | 0.30000000000000004
(1 row)
```

O `float8` do Postgres é o mesmo IEEE 754 de 64 bits do Python, e erra igualzinho. O `numeric` não.

Do lado do Python, o driver devolve a coluna `numeric` como `Decimal`, já com as duas casas. Um `Decimal("80.10")` vai e um `Decimal("80.10")` volta. Por isso o model declara `Mapped[Decimal]`, e não `Mapped[float]`.

## No JSON: string

A terceira fronteira é a mais traiçoeira. O JSON tem um tipo numérico só, o "number". A especificação não diz como ler. Cada parser decide, e quase todos leem como `float`: o `json.loads` do Python (desastre 5 da lição 05) e o `JSON.parse` do JavaScript, que nem tem outro tipo de número.

Então, se a API devolver `{"valor": 80.10}`, o front-end recebe um `float`. A API pode estar perfeita e o erro aparece do outro lado do fio.

A saída é não mandar número. **A API manda dinheiro como string.** O Pydantic já faz isso com `Decimal`, sem configuração. Com um schema de uma linha, a `Conta` que o `tests/test_dinheiro.py` usa (o tipo `Dinheiro` aparece logo abaixo, em "Na entrada"):

```python
from decimal import Decimal

from pydantic import BaseModel

from app.schemas import Dinheiro


class Conta(BaseModel):
    valor: Dinheiro

Conta(valor=Decimal("80.10")).model_dump_json()
```

```console
{"valor":"80.10"}
```

String no JSON, com as duas casas. Quem recebe decide como ler, e o texto chegou intacto.

E se o cliente mandar um número em vez de string? O Pydantic aceita, mas olhe o que acontece:

```console
{"valor": "80.10"}  ->  Decimal('80.10')  ->  {"valor":"80.10"}
{"valor": 80.10}    ->  Decimal('80.1')   ->  {"valor":"80.1"}
```

O número passou por um `float` no parser e voltou pela forma mais curta, `80.1`. O valor bate (`Decimal("80.1") == Decimal("80.10")`), mas a segunda casa sumiu. E com dígitos demais é pior: mandei `1234567890.123456789` como número, num campo `Decimal` sem restrição nenhuma, e chegou `Decimal('1234567890.1234567')`. Os últimos dígitos ficaram no `float`. Com string, nada disso acontece.

## Na entrada: o tipo `Dinheiro`

Banco e JSON resolvidos. Falta decidir **o que a API aceita**. Um `Decimal` puro aceita `-1`, `0`, `NaN` e `80.105`. Nenhum deles é uma despesa.

O tipo novo mora em `app/schemas/dinheiro.py`:

```python
Dinheiro = Annotated[Decimal, Field(max_digits=12, decimal_places=2, gt=0)]
```

O `Annotated` cola regras de validação num tipo. Aqui: `Decimal`, no máximo 12 dígitos e 2 casas (o mesmo `Numeric(12, 2)` do banco) e maior que zero. Um schema escreve `valor: Dinheiro` e herda tudo.

O `tests/test_dinheiro.py` passa sete valores ruins e confere que todos são recusados. Rodei cada um para ver a mensagem:

```console
"80.105"              -> Decimal input should have no more than 2 decimal places
80.105                -> Decimal input should have no more than 2 decimal places
"-1"                  -> Input should be greater than 0
"0"                   -> Input should be greater than 0
"NaN"                 -> Input should be a finite number
0.30000000000000004   -> Decimal input should have no more than 12 digits in total
"1234567890123.45"    -> Decimal input should have no more than 12 digits in total
```

Dois deles merecem uma olhada.

O `"NaN"` é "not a number", um valor especial que o `Decimal` aceita. Uma despesa de NaN reais estragaria qualquer soma em que entrasse. O `Field` recusa.

O `0.30000000000000004` é o resultado do `0.1 + 0.2` em `float`, mandado como número. Ele chega com todos os 17 dígitos depois do ponto: o parser leu o `float` e o converteu pela forma mais curta, que aqui é a forma inteira. Dezessete dígitos não cabem em 12. Quem recusa é o `max_digits`, antes de o `decimal_places` olhar. A mensagem completa:

```console
1 validation error for Conta
valor
  Decimal input should have no more than 12 digits in total [type=decimal_max_digits, input_value=0.30000000000000004, input_type=float]
```

Repare no `input_type=float`. É a confissão do parser.

Na saída, os schemas da lição 08 vão usar `Decimal` puro, sem o `Dinheiro`. O valor vem do banco e já está validado, com duas casas.

## Quem arredonda?

Por que recusar `80.105` em vez de arredondar para `80.11`? Afinal, é o que o usuário quis dizer.

Porque "arredondar" não é uma operação só. Olhe o banco e o Python arredondando os mesmos números para duas casas:

```console
fairfare=# SELECT 80.105::numeric(12, 2), 80.115::numeric(12, 2);
 numeric | numeric
---------+---------
   80.11 |   80.12
(1 row)

fairfare=# SELECT 0.025::numeric(12, 2), 0.035::numeric(12, 2);
 numeric | numeric
---------+---------
    0.03 |    0.04
(1 row)
```

```console
$ uv run python -c "
from decimal import Decimal
for s in ['80.105','80.115','0.025','0.035']: print(s, Decimal(s).quantize(Decimal('0.01')))"
80.105 80.10
80.115 80.12
0.025 0.02
0.035 0.04
```

O Postgres arredonda **meio para longe do zero**: terminou em 5, sobe. O `quantize` do Python usa, por padrão, o **arredondamento bancário** (`ROUND_HALF_EVEN`): terminou em 5, vai para o vizinho par. `80.105` vira `80.11` no banco e `80.10` no Python. `80.115` dá `80.12` nos dois. Às vezes concordam, às vezes não, e você não sabe de antemão qual dos dois.

Se a API deixasse a terceira casa passar, o valor gravado dependeria de quem arredondou primeiro. Então ninguém arredonda em silêncio. A API recusa, com um 422 que diz o porquê, e quem mandou decide o que quis dizer.

Arredondar de propósito, com regra escrita, vai acontecer. Dividir R$ 100 entre três exige isso. É a lição 07.

## Os models novos

Com as três fronteiras fechadas, o dinheiro pode entrar no app. O `app/models/expense.py` traz duas tabelas.

A `Expense` é a despesa: de qual grupo, quem pagou (`paid_by`), a descrição, o valor e quando foi criada. O valor é `Numeric(12, 2)` com um `CHECK (valor > 0)`, chamado `expenses_valor_positivo`. O tipo `Dinheiro` já recusa zero e negativo, mas o banco é a última palavra: se outro caminho tentar gravar, ele recusa também.

A `ExpenseShare` é a parte de cada participante. A chave é composta, `(expense_id, user_id)`, como a do `GroupMember` da lição 04: uma pessoa tem uma parte por despesa, e não duas.

Por que **gravar** a parte, se dá para calcular a partir do valor e dos participantes? Porque a regra de divisão pode mudar. Hoje é divisão igual. Amanhã alguém inventa divisão por percentual. Se as partes fossem calculadas na hora, a despesa de ontem mudaria junto com a regra. Gravada, ela fica como foi lançada.

E o `CHECK` da parte é `valor >= 0`, não `> 0`. Zero é permitido de propósito. R$ 0,01 entre três pessoas dá 0,01 para um e 0,00 para os outros dois. Quem fica com o centavo, e por quê, é a lição 07.

A migração `despesas e partes` cria as duas tabelas. Desta vez o autogenerate escreveu os dois `CHECK` sozinho. Na criação de tabela ele escreve. O que ele não faz, como o capítulo 4 mostrou, é enxergar um `CHECK` acrescentado (ou alterado) numa tabela que já existe. No banco:

```console
fairfare=# \d expenses
                                      Table "public.expenses"
  Column   |           Type           | Collation | Nullable |               Default
-----------+--------------------------+-----------+----------+--------------------------------------
 id        | integer                  |           | not null | nextval('expenses_id_seq'::regclass)
 group_id  | integer                  |           | not null |
 paid_by   | integer                  |           | not null |
 descricao | character varying        |           | not null |
 valor     | numeric(12,2)            |           | not null |
 criada_em | timestamp with time zone |           | not null | now()
Indexes:
    "expenses_pkey" PRIMARY KEY, btree (id)
Check constraints:
    "expenses_valor_positivo" CHECK (valor > 0::numeric)
Foreign-key constraints:
    "expenses_group_id_fkey" FOREIGN KEY (group_id) REFERENCES groups(id)
    "expenses_paid_by_fkey" FOREIGN KEY (paid_by) REFERENCES users(id)
Referenced by:
    TABLE "expense_shares" CONSTRAINT "expense_shares_expense_id_fkey" FOREIGN KEY (expense_id) REFERENCES expenses(id)
```

Ainda não existe rota para lançar despesa. As tabelas estão prontas e vazias. O endpoint chega na lição 08.

## O que fica declarado

- **As tabelas `expenses` e `expense_shares` existem sem endpoint.** Nada no app escreve nelas até a lição 08.
- **Uma moeda só.** O FairFare não guarda moeda junto do valor: tudo é real. É uma escolha, não um esquecimento. Várias moedas trariam câmbio, e câmbio não ensina nada que este capítulo precise.
- **`"1e2"` passa pelo `Dinheiro` e volta como `"1E+2"`.** Notação científica é um `Decimal` válido, com zero casas, então o tipo aceita. O valor está certo, mas a forma de devolver não. A lição 08 garante que a resposta volte sempre com duas casas (`"100.00"`), com um teste.

## O que você deve conseguir fazer agora

- Criar um `Decimal` sem herdar o erro do `float`, e explicar por que `Decimal(0.1)` não serve.
- Dizer o que `Numeric(12, 2)` guarda: 12 dígitos no total, 2 depois da vírgula, até `9999999999.99`.
- Explicar por que a API manda dinheiro como string no JSON, e o que acontece quando o cliente manda número.
- Ler as recusas do tipo `Dinheiro` e dizer qual regra barrou cada valor.
- Explicar por que a API recusa a terceira casa em vez de arredondar: o banco e o Python arredondam diferente.
