# Soluções — capítulo 5

Leia depois de tentar. Uma solução lida antes da tentativa vira informação; depois da tentativa, vira entendimento.

Cada item tem o código consertado, **por que aquele conserto e não outro**, como você poderia ter chegado nele sozinho e a saída que você deve ver.

Todas as mensagens e todos os números daqui saíram de um terminal de verdade, com o Postgres do `compose.yaml` na mesma máquina. Os seus tempos vão ser parecidos, não iguais. As contagens (de testes, de consultas, de linhas) devem bater.

---

## Bloco 1 — Dinheiro

### 1.1 — A taxa que ninguém pediu para arredondar assim

#### O que estava errado

O `quantize` sem `rounding=` usa o arredondamento padrão do `Decimal`. A lição 06, em "Quem arredonda?", deu o nome dele: **bancário**, `ROUND_HALF_EVEN`. No empate, ele vai para o vizinho **par**. A regra da casa é outra: no empate, para cima.

O enunciado pediu para explicar antes de consertar por que `0.35` e `80.15` passavam. Ponha as cinco contas lado a lado:

| conta | 10% exato | `quantize` padrão | `ROUND_HALF_UP` |
|---|---|---|---|
| `10.00` | `1.0000` | `1.00` | `1.00` |
| `0.25` | `0.0250` | `0.02` | `0.03` |
| `0.35` | `0.0350` | `0.04` | `0.04` |
| `10.05` | `1.0050` | `1.00` | `1.01` |
| `80.15` | `8.0150` | `8.02` | `8.02` |

Olhe o dígito que **fica**, o dos centavos, nas quatro linhas que terminam em meio centavo. Em `0.025`, os candidatos são `0.02` e `0.03`. O par é `0.02`, e o bancário desce. Em `0.035`, os candidatos são `0.03` e `0.04`. O par é `0.04`, e o bancário sobe. Por coincidência, sobe para o mesmo lugar que a regra da casa. O mesmo vale para `8.015` (`8.02` é par) e `1.005` (`1.00` é par, desce).

Então os três verdes não provavam nada. Dois são empates em que "para o par" e "para cima" calham de concordar. O terceiro, `10.00`, nem é empate. Metade das vezes o bancário acerta por acaso. É o pior tipo de teste verde.

#### O conserto

Em `bloco1/taxa.py`. O `ROUND_HALF_UP` entra no import:

```python
from decimal import ROUND_HALF_UP, Decimal

CENTAVO = Decimal("0.01")


def taxa_de_servico(conta: Decimal) -> Decimal:
    """Os 10% do garçom, ao centavo. Regra da casa: meio centavo arredonda PARA CIMA.

    EXERCÍCIO 1.1: esta função tem um defeito de propósito. Os testes mostram qual.
    """
    return (conta * Decimal("0.10")).quantize(CENTAVO, rounding=ROUND_HALF_UP)
```

#### Por que esse, e não outro

**Por que não `ROUND_UP`.** O nome engana. `ROUND_UP` não é "meio para cima": é "qualquer resto para cima", para longe do zero. Ele passa nos cinco casos do teste, porque todos terminam em `0` ou em `5`. E cobra errado de quase todo mundo que não está no empate:

| conta | 10% exato | `ROUND_HALF_UP` | `ROUND_UP` |
|---|---|---|---|
| `0.21` | `0.0210` | `0.02` | `0.03` |
| `12.34` | `1.2340` | `1.23` | `1.24` |

```console
$ uv run python -c '
from decimal import ROUND_HALF_UP, ROUND_UP, Decimal
c = Decimal("0.01")
for s in ["0.21", "12.34"]:
    x = Decimal(s) * Decimal("0.10")
    print(s, x.quantize(c, rounding=ROUND_HALF_UP), x.quantize(c, rounding=ROUND_UP))'
0.21 0.02 0.03
12.34 1.23 1.24
```

Um centavo a mais em quase toda conta. Teste verde, cliente lesado.

**Por que não somar meio centavo antes.** O README proibiu, e o motivo é este: `+ Decimal("0.005")` **simula** a regra com aritmética. Quem lê precisa fazer a conta de cabeça para descobrir qual regra é. `rounding=ROUND_HALF_UP` **escreve** a regra, com o nome dela. É a mesma ideia da lição 07, em "Por que `ROUND_DOWN`, e não o padrão": lá, o piso precisava ser piso, e o código diz `ROUND_DOWN`. Aqui, o meio precisa subir, e o código diz `ROUND_HALF_UP`.

E de brinde, o Python passa a concordar com o banco. A lição 06 mostrou o Postgres arredondando `0.025::numeric(12, 2)` para `0.03`, meio para longe do zero. Com o conserto, o Python faz o mesmo.

#### Então o bancário é errado?

Não. Ele existe por um bom motivo, e dá para medir. Pegue os cem valores que terminam em meio centavo entre `0.005` e `0.995`. Some exatos, e some depois de arredondar cada um:

```console
$ uv run python -c '
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
c = Decimal("0.01")
meios = [Decimal(i) / 1000 for i in range(5, 1000, 10)]  # 0.005, 0.015, ..., 0.995
print(len(meios), sum(meios))
print(sum(x.quantize(c, rounding=ROUND_HALF_UP) for x in meios))
print(sum(x.quantize(c, rounding=ROUND_HALF_EVEN) for x in meios))'
100 50.000
50.50
50.00
```

O "meio para cima" sempre empurra o empate para o mesmo lado. Em cem empates, sobra meio real a mais. O bancário empurra metade para cima e metade para baixo, e os erros se cancelam. Por isso ele é o padrão em estatística e em somas longas de valores arredondados: o viés some no total.

Mas uma taxa de serviço não é estatística. É uma regra da casa, escrita no cardápio, aplicada a uma conta de cada vez. Quando existe uma regra, o código usa a regra, com o nome dela. O padrão só serve quando ninguém decidiu nada, e em dinheiro alguém sempre decidiu.

#### Como chegar nele sozinho

As duas falhas são as únicas contas cujo resultado sai **para baixo**. Isso diz que o código arredonda, só que não do jeito pedido. A pergunta seguinte é "qual arredondamento o `quantize` usa quando ninguém diz?", e a resposta está na lição 06. Depois, é ler a lista de constantes do módulo `decimal` e achar a que diz "meio para cima" no nome.

#### A saída que você deve ver

```console
$ uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco1 -v -k taxa
...
test_bloco1.py::test_taxa_meio_centavo_para_cima[10.00-1.00] PASSED      [ 20%]
test_bloco1.py::test_taxa_meio_centavo_para_cima[0.25-0.03] PASSED       [ 40%]
test_bloco1.py::test_taxa_meio_centavo_para_cima[0.35-0.04] PASSED       [ 60%]
test_bloco1.py::test_taxa_meio_centavo_para_cima[10.05-1.01] PASSED      [ 80%]
test_bloco1.py::test_taxa_meio_centavo_para_cima[80.15-8.02] PASSED      [100%]

======================= 5 passed, 3 deselected in 0.01s ========================
```

### 1.2 — O valor que chegou como número

#### O que estava errado

```python
return Decimal(json.loads(corpo)["valor"])
```

Leia de dentro para fora. Primeiro roda o `json.loads`. Ele encontra `80.10` no texto e, como a lição 06 contou em "No JSON: string", lê como `float`. Nesse instante o `80.10` deixa de existir. O que existe é o `float` mais próximo, que não é `80.10`.

Só depois o `Decimal(...)` entra. E o `Decimal` de um `float` é **exato**: ele copia, dígito por dígito, o valor binário que recebeu. Por isso a mensagem do teste mostra aquela fila enorme:

```
E       assert Decimal('80.099999999999994315658113919198513031005859375') == Decimal('80.10')
```

O `Decimal` não criou o erro. Ele herdou o erro, e o mostrou com fidelidade total. O tipo estava certo e chegou tarde.

#### O conserto

Em `bloco1/entrada.py`:

```python
def valor_do_pedido(corpo: str) -> Decimal:
    """Lê o campo "valor" de um JSON vindo de um cliente que manda número, não string.

    EXERCÍCIO 1.2: esta função tem um defeito de propósito. Os testes mostram qual.
    """
    return Decimal(json.loads(corpo, parse_float=Decimal)["valor"])
```

O `parse_float` diz ao `json.loads` o que fazer com o **texto** de cada número com casa decimal. O padrão é `float`. Com `parse_float=Decimal`, o parser entrega `"80.10"`, ainda texto, direto ao `Decimal`. O `float` nunca nasce. O `Decimal(...)` de fora ficou sobrando (o `Decimal` de um `Decimal` é ele mesmo), e não faz mal nenhum.

Números inteiros, como `{"valor": 80}`, não passam pelo `parse_float`. Viram `int`, e um `int` cabe inteiro no `Decimal`, sem perda.

#### O atalho que passa e não vale

```python
return Decimal(str(json.loads(corpo)["valor"]))
```

Passa nos três casos do teste. O `str` de um `float` devolve a forma mais curta que volta ao mesmo `float`: `80.1`, `0.1`, `19.99`. Parece conserto. Mas medido com o número da lição 06:

```console
$ uv run python -c '
import json
from decimal import Decimal
corpo = "{\"valor\": 1234567890.123456789}"
print(Decimal(json.loads(corpo)["valor"]))
print(Decimal(str(json.loads(corpo)["valor"])))
print(Decimal(json.loads(corpo, parse_float=Decimal)["valor"]))
print(repr(Decimal(str(json.loads("{\"valor\": 80.10}")["valor"]))))'
1234567890.1234567165374755859375
1234567890.1234567
1234567890.123456789
Decimal('80.1')
```

Na ordem: o código quebrado, o atalho e o conserto. O `str` só esconde a cauda do binário. Os dígitos que o `float` não guardou continuam perdidos. E mesmo no caso feliz ele perde a escala: a última linha mostra `{"valor": 80.10}` virando `Decimal('80.1')`, igual em valor, sem a segunda casa. É o mesmo `80.1` que a lição 06 viu o Pydantic devolver.

A regra é: quando qualquer código olha um `float`, o estrago já aconteceu. Consertar dinheiro é impedir o `float` de nascer, não tratar ele depois.

#### Como chegar nele sozinho

O enunciado perguntou "em que momento o `80.10` deixou de ser `80.10`". Teste por partes no terminal: `json.loads('{"valor": 80.10}')["valor"]` já é um `float`. Então o defeito está antes do `Decimal`, dentro do `json.loads`. Daí, a documentação do `json.loads`: o parâmetro `parse_float` está lá, com a descrição "por padrão, equivalente a `float(num_str)`".

#### A saída que você deve ver

O bloco inteiro:

```console
$ uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco1 -q
........                                                                 [100%]
8 passed in 0.02s
```

---

## Bloco 2 — As consultas

### 2.1 — O N+1 escrito à mão

#### O que estava errado

Nada na resposta. Tudo no caminho. Uma consulta para os grupos e, dentro do laço, duas por grupo: os membros e o total. São 1 + 2 × 20 = **41**. É o N+1 da lição 03, só que em dobro, e escrito à mão em vez de escondido num lazy load.

São dois N+1 diferentes, e eles pedem remédios diferentes:

- **Os membros** são uma coleção. Você precisa de cada um, nome por nome. A lição 03 resolveu isso: carregue a relação junto, com uma consulta por relação.
- **O total** é um resumo. Você não precisa de nenhuma despesa, só da soma delas. A lição 09, em "Três jeitos de somar", tirou a regra: **leve a conta para onde os dados estão.**

#### O conserto

Em `bloco2/listagem.py`. O `selectinload` entra no import do `sqlalchemy.orm`, e o `Bloco2Membro` sai do import dos modelos (ninguém mais o usa, e o `ruff` reclamaria com `F401`):

```python
async def resumo_dos_grupos(db: AsyncSession) -> list[dict]:
    """Nome, membros e total gasto de cada grupo, em ordem de id.

    EXERCÍCIO 2.1: a resposta sai certa. O número de consultas, não.
    """
    stmt = select(Bloco2Grupo).options(selectinload(Bloco2Grupo.membros)).order_by(Bloco2Grupo.id)
    grupos = (await db.scalars(stmt)).all()
    por_grupo = select(Bloco2Despesa.grupo_id, func.sum(Bloco2Despesa.valor)).group_by(
        Bloco2Despesa.grupo_id
    )
    totais = dict((await db.execute(por_grupo)).all())
    return [
        {
            "nome": grupo.nome,
            "membros": [m.nome for m in grupo.membros],
            "total": totais.get(grupo.id),
        }
        for grupo in grupos
    ]
```

Três consultas, com 20 grupos ou com 200:

1. os grupos;
2. os membros de todos eles, num `WHERE grupo_id IN (...)` (é o `selectinload`);
3. os totais de todos eles, num `GROUP BY grupo_id`.

O `GROUP BY` devolve uma linha por grupo: `(grupo_id, soma)`. O `dict(...)` vira essas linhas num dicionário `{grupo_id: soma}`, e a montagem só consulta o dicionário. Nenhuma ida ao banco dentro do laço.

#### Por que esse, e não outro

**Por que o total não vai num `selectinload` das despesas.** Daria para carregar as despesas de cada grupo e somar no Python. Seriam 3 consultas também, e o teste passaria. Mas é o jeito (b) da lição 09, o "Python carregando tudo": trazer todas as linhas, montar um objeto para cada, só para somar e jogar fora. Lá, ele foi o mais lento dos três. Aqui as despesas são 80. Num grupo de verdade, com anos de despesas, são milhares. O `GROUP BY` traz 20 linhas, uma por grupo, não importa quantas despesas existam.

**Por que `totais.get(grupo.id)`, e não `totais[grupo.id]`.** Um grupo sem despesa nenhuma não aparece no `GROUP BY`, porque não tem linha para agrupar. Com `[]`, ele daria `KeyError`. Com `.get`, dá `None`, que é exatamente o que o código antigo devolvia: o `sum` do SQL sobre zero linhas é `NULL`. A resposta continua a mesma, até no caso de canto.

**Uma honestidade sobre o "3".** O `selectinload` manda os ids num `IN (...)` em lotes de 500. A lição 09 mostrou isso em "Três jeitos de somar": o "poucas consultas" dele não é fixo. Com 20 grupos, é um lote. Medido, com `GRUPOS = 2000` no teste: `6 consultas para 2000 grupos` (os grupos, quatro lotes de membros, os totais). Continua sem crescer de um em um com os grupos, que é o que importa. O teste pede `<= 3` porque a semente tem 20.

#### Como chegar nele sozinho

Comece pela aritmética da mensagem: 41 para 20 grupos. 41 = 1 + 2 × 20. O "2 ×" diz que são **dois** laços de consulta, e não um. Olhe o que cada um traz. Um traz linhas que você vai mostrar (os nomes). O outro traz um número que o banco poderia ter calculado (a soma). Para o primeiro, a lição 03. Para o segundo, a lição 09.

#### A saída que você deve ver

```console
$ uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco2 -v -k resumo
...
test_bloco2.py::test_resumo_correto PASSED                               [ 50%]
test_bloco2.py::test_resumo_sem_n_mais_1 PASSED                          [100%]

======================= 2 passed, 1 deselected in 0.28s ========================
```

Contado com o mesmo `conta_consultas` do teste: **3** consultas, contra as 41 de antes.

### 2.2 — O `joinedload` na coleção

#### O que estava errado

O `joinedload` faz um `LEFT OUTER JOIN`. Este é o SQL que ele gera, copiado do log com `echo=True` na engine:

```sql
SELECT bloco2_grupos.id, bloco2_grupos.nome, bloco2_membros_1.id AS id_1, bloco2_membros_1.grupo_id, bloco2_membros_1.nome AS nome_1
FROM bloco2_grupos LEFT OUTER JOIN bloco2_membros AS bloco2_membros_1 ON bloco2_grupos.id = bloco2_membros_1.grupo_id ORDER BY bloco2_grupos.id, bloco2_membros_1.id
```

Um `JOIN` devolve uma linha por **combinação**. Cada grupo tem 3 membros, então cada grupo aparece 3 vezes. Medido, com um `count(*)` sobre esse mesmo `JOIN`, na semente do teste: **60 linhas** para 20 grupos. Era isso que a lição 03, em "Por que `selectinload` aqui", chamou de multiplicar as linhas: "e é preciso desfazer a multiplicação depois". O SQLAlchemy se recusa a decidir sozinho como desfazer. Sem ninguém dizer, o `.all()` devolveria o mesmo grupo três vezes. Ele prefere parar com um erro que diz o que falta:

```
E       sqlalchemy.exc.InvalidRequestError: The unique() method must be invoked on this Result, as it contains results that include joined eager loads against collections
```

#### O conserto

Em `bloco2/listagem.py`:

```python
async def grupos_com_membros(db: AsyncSession) -> list[Bloco2Grupo]:
    """Os grupos, cada um com a coleção `membros` já carregada, numa consulta só.

    EXERCÍCIO 2.2: esta função tem um defeito de propósito. O teste mostra qual.
    """
    stmt = select(Bloco2Grupo).options(joinedload(Bloco2Grupo.membros)).order_by(Bloco2Grupo.id)
    return list((await db.scalars(stmt)).unique().all())
```

Uma palavra: `unique()`. Ele percorre o resultado e fica com cada objeto uma vez só. As três linhas do Grupo 01 apontam para o **mesmo** objeto `Bloco2Grupo` (o identity map garante que um id é um objeto só na sessão), e o `unique()` descarta as repetições. Medido: as 60 linhas viram **20 objetos**, cada um com os seus 3 membros pendurados.

#### Por que o `selectinload` não precisa disso

Porque ele não multiplica nada. A primeira consulta é só dos grupos: uma linha por grupo, 20 linhas. A segunda traz os membros, num `WHERE grupo_id IN (...)`, e o SQLAlchemy os pendura no grupo certo. Nenhuma linha de grupo se repete, então não há nada para desfazer. Medido, com a mesma semente e o mesmo `conta_consultas`: **2 consultas**, **20 objetos**.

Duas consultas em vez de uma, e nenhuma repetição. É o critério da lição 03: **coleção, `selectinload`**. O exercício manteve o `joinedload` para você ver de perto o custo que o critério evita.

#### Como chegar nele sozinho

A mensagem dá o conserto. O exercício pedia o porquê, e o caminho é contar. Quantas linhas um `JOIN` de 20 grupos com 3 membros cada devolve? Se você não tem certeza, cole o `JOIN` no `psql` com um `count(*)`. 60. E quantos grupos você quer? 20. A diferença é a multiplicação. Quem a desfaz é o `unique()`.

#### A saída que você deve ver

O bloco inteiro:

```console
$ uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco2 -v
...
test_bloco2.py::test_resumo_correto PASSED                               [ 33%]
test_bloco2.py::test_resumo_sem_n_mais_1 PASSED                          [ 66%]
test_bloco2.py::test_grupos_com_membros PASSED                           [100%]

============================== 3 passed in 0.67s ===============================
```

---

## Bloco 3 — Transação e cadeado

### 3.1 — O extrato pela metade

#### O que estava errado

```python
async with AsyncSession(engine) as db:
    for i, (descricao, valor) in enumerate(linhas):
        ...
        db.add(Lancamento(descricao=descricao, valor=valor))
        await db.commit()
```

Um `commit()` por linha. Cada lançamento é assinado no cartório assim que fica pronto. Quando a falha chega na terceira linha, as duas primeiras já valem para todo mundo, e não há rollback que as desfaça. Duas de quatro linhas, para sempre.

É o "antes" da lição 08, em "O estrago": o repository que comitava cada gravação e deixava uma despesa de R$ 90 com partes que somavam R$ 60. Aqui não tem repository nem service. É uma função só. E o defeito é o mesmo: quem comitou não sabia o que era "uma operação".

#### O conserto

Em `bloco3/lancamento.py`:

```python
async def lancar_extrato(
    engine: AsyncEngine, linhas: list[tuple[str, Decimal]], falhar_na: int | None = None
) -> None:
    """Grava todas as linhas do extrato, ou nenhuma.
    ...
    """
    async with AsyncSession(engine) as db, db.begin():
        for i, (descricao, valor) in enumerate(linhas):
            if i == falhar_na:
                raise RuntimeError(f"falha simulada na linha {i}")
            db.add(Lancamento(descricao=descricao, valor=valor))
            await db.flush()
```

Duas mudanças. O `db.begin()` entra no `async with`, e o `commit()` vira `flush()`.

Na analogia da lição 08, em "A regra": o `flush` manda o rascunho ao cartório, e o `commit` assina. Agora cada linha vai como rascunho. O `INSERT` roda de verdade, dentro da transação, e o banco confere as constraints na hora. Mas ninguém assina linha por linha. Quem assina é o fim do `begin()`: se o bloco termina normalmente, comita tudo; se uma exceção atravessa o bloco, desfaz tudo, inclusive o que já passou pelo `flush`. O `RuntimeError` atravessa. Zero linhas.

#### Por que esse, e não outro

**O primeiro tropeço provável: `begin()` com o `commit()` ainda dentro.** Medido:

```
E               sqlalchemy.exc.InvalidRequestError: Can't operate on closed transaction inside context manager.  Please complete the context manager before emitting further commands.
```

O `begin()` disse "eu cuido do fim da transação". O `commit()` dentro do bloco fecha a transação antes da hora, e a próxima linha não tem onde rodar. O SQLAlchemy não deixa dois donos para o mesmo fim.

**A alternativa que também passa: um `commit()` só, depois do laço.** Sem `begin()`, com o `await db.commit()` fora do `for`. Medido: `1 passed`. Ela funciona porque a falha estoura antes do `commit`, e a sessão fechada pelo `async with` desfaz a transação aberta pelo autobegin.

Não está errada. A de referência é melhor por dois motivos:

- **A fronteira está escrita.** Com o `begin()`, quem lê vê onde a operação começa e onde termina. Na outra, o começo é o autobegin, invisível, e o rollback depende de lembrar que fechar a sessão desfaz o que não foi comitado. Funciona, mas é conhecimento implícito.
- **Erros aparecem na linha certa.** Com o `flush` a cada linha, um `CHECK` violado estoura no lançamento que o violou. Sem `flush`, tudo vai junto no `commit`, e o erro aparece no fim, longe da causa.

Os dois motivos são os da lição 08, em "`async with self.db.begin()`". O ponto do exercício é que o princípio não depende da arquitetura do FairFare. Não tem service aqui, e mesmo assim a pergunta é a mesma: o que é uma operação, e quem a delimita?

#### Como chegar nele sozinho

A falha deixou **2** linhas, e a falha foi na linha de índice **2**. As duas linhas que sobraram são exatamente as que vieram antes da falha. Então cada uma foi gravada de forma definitiva antes de a próxima começar. Procure no código o que torna uma gravação definitiva. É o `commit()`, dentro do laço.

#### A saída que você deve ver

```console
$ uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco3 -q -k extrato
.                                                                        [100%]
1 passed, 1 deselected in 0.13s
```

E a tabela com **zero** linhas depois da falha, que é o que o teste confere.

### 3.2 — O cadeado que chega tarde

#### O que estava errado

```python
async with engine.begin() as conn:
    saldo = await conn.scalar(LE_SALDO, {"id": de})
    if depois_de_ler is not None:
        await depois_de_ler()
    await conn.execute(TRANCA, {"de": de, "para": para})
    if saldo < valor:
        raise SaldoInsuficiente(...)
    ...
```

O cadeado é perfeito. Um comando só, as duas contas, em ordem de id: o da lição 11, em "O cadeado certo". O problema é **quando** ele chega. Siga as duas transferências, A e B:

1. A lê o saldo da conta 1: `100.00`. B lê o saldo da conta 1: `100.00`. O gancho segura cada uma até a outra ler também. Por isso o resultado é sempre o mesmo, e não às vezes.
2. A pega o cadeado. B pede o cadeado e espera.
3. A confere `100.00 >= 80.00`, debita, credita, comita. Saldo: `20.00`. O cadeado solta.
4. B pega o cadeado. Ela confere `saldo < valor` com a variável `saldo` do passo 1: `100.00`. Passa. Debita 80. Saldo: **−60.00**.

A fila funcionou. B esperou A terminar, direitinho. Só que B esperou com a decisão já tomada. O `saldo` dela é uma foto tirada antes da fila, guardada numa variável do Python. Nenhum cadeado no banco atualiza uma variável do Python.

É o *check-then-act* que o capítulo 4 reproduziu na lição 07, "Reproduzindo a corrida". Olha, depois age, supondo que o que viu continua valendo. A lição 08 de lá disse que **transação não é cadeado**. Esta aqui completa a frase: **cadeado depois da leitura é cadeado decorativo.** Ele está lá, tranca de verdade, e não protege nada.

#### O conserto

Em `bloco3/transferencia.py`, duas linhas mudam de lugar:

```python
    async with engine.begin() as conn:
        # Os dois cadeados num comando só, em ordem de id: sem ciclo, sem deadlock.
        await conn.execute(TRANCA, {"de": de, "para": para})
        saldo = await conn.scalar(LE_SALDO, {"id": de})
        if depois_de_ler is not None:
            await depois_de_ler()
        if saldo < valor:
            raise SaldoInsuficiente(f"a conta {de} tem {saldo}, e a transferência é de {valor}")
        await conn.execute(DEBITA, {"valor": valor, "id": de})
        await conn.execute(CREDITA, {"valor": valor, "id": para})
```

A ordem certa, sempre: **trancar, ler, decidir, escrever.**

#### Por que resolve

Siga as duas de novo:

1. A pega o cadeado. B pede o cadeado e espera, **antes de ler qualquer coisa**.
2. A lê `100.00`, decide que cabe, debita, credita, comita. Saldo: `20.00`. O cadeado solta.
3. B pega o cadeado e **só agora** lê o saldo. Lê `20.00`. Decide que não cabe. `SaldoInsuficiente`.

Medido, imprimindo o que o `gather` devolveu:

```console
[None, SaldoInsuficiente('a conta 1 tem 20.00, e a transferência é de 80.00')]
```

A ordem dos dois pode vir trocada. O `gather` devolve os resultados na ordem em que as tarefas foram criadas, mas qual delas pega o cadeado primeiro, e faz o papel de A, muda de rodada para rodada. Medi 8 vezes e vi as duas. O que não muda: um `None` e um `SaldoInsuficiente`.

Por que B lê `20.00`, e não o `100.00` de antes? Porque a transação roda em `READ COMMITTED`, o padrão do Postgres. A lição 10 do capítulo 4, em "Quanto tempo o cadeado dura", explicou: nesse nível, cada **comando** tira um retrato novo do banco. O `LE_SALDO` de B é um comando que começa depois do `COMMIT` de A. O retrato já tem o débito.

É a frase que fecha a seção da lição 11, "Por que funciona em `READ COMMITTED`": **fila para olhar, e não fila para anotar.** No código quebrado, B fazia fila só para anotar. Com o conserto, faz fila para olhar.

E repare que o conserto não mexeu no cadeado. Ele já era o certo. Só mudou de lugar.

**E por que não um `FOR UPDATE` no próprio `LE_SALDO`?** Fecharia a corrida da leitura, mas trancaria só a conta `de`. O `TRANCA` existe para trancar as duas pontas, em ordem de id, para que transferências em direções opostas não formem um ciclo. É o deadlock da lição 11, em "Dois cadeados, ordem errada". O enunciado pediu para não trocar o `FOR UPDATE` por outra coisa, e o conserto não precisa: basta ele vir primeiro.

#### O bônus: o meio segundo

Com o conserto, o teste leva meio segundo. Medido, dez vezes com `--durations`: **0,54 s a 0,55 s** de `call`, em todas.

O meio segundo é o timeout do gancho. A pega o cadeado, lê, e chega ao `depois_de_ler`. O gancho de A espera B chegar ao mesmo ponto. Mas B nunca chega: está parada no `TRANCA`, esperando o cadeado que A segura. A espera de A não termina por encontro. Termina pelo `wait_for(..., timeout=0.5)`. Aí A segue, comita, solta, e B anda. Quando B enfim chega ao gancho, ela é a segunda a chegar: o contador vai a 2, ela mesma dispara o evento, e passa direto, sem esperar ninguém.

Esse meio segundo é a prova de que o cadeado vem antes da leitura. No código quebrado, as duas se encontravam no gancho na hora, porque nenhuma estava esperando por nada. Por isso, quebrado, o pytest inteiro terminava em 0,15 s a 0,24 s.

E repare que, se o gancho fosse uma barreira sem timeout, o conserto travaria para sempre: A esperando B no gancho, B esperando A no cadeado. É o que o comentário no teste avisa.

#### Como chegar nele sozinho

A dica era a palavra "quando". Leia as linhas dentro do `async with` e pergunte, para cada uma: "o que ela sabe nesse momento?". O `saldo` é lido na primeira linha. O cadeado entra na quarta. Entre as duas, qualquer outra transação pode mudar o saldo, e a variável não fica sabendo. Depois, compare com o `SettlementService` da lição 11: o `lock_members` vem antes do `balances`, e o comentário diz por quê.

#### A saída que você deve ver

```console
$ for i in $(seq 10); do uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco3 -q -k transferencias | tail -1; done
1 passed, 1 deselected in 0.66s
1 passed, 1 deselected in 0.65s
1 passed, 1 deselected in 0.66s
1 passed, 1 deselected in 0.65s
1 passed, 1 deselected in 0.64s
1 passed, 1 deselected in 0.65s
1 passed, 1 deselected in 0.65s
1 passed, 1 deselected in 0.65s
1 passed, 1 deselected in 0.65s
1 passed, 1 deselected in 0.65s
```

Medido: 10 de 10. Com o código quebrado, também 10 de 10, só que falhando, todas com `(2, Decimal('-60.00'))`. O gancho tira a sorte da corrida, nos dois sentidos.

E o bloco inteiro:

```console
$ uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco3 -v
...
test_bloco3.py::test_extrato_nunca_fica_pela_metade PASSED               [ 50%]
test_bloco3.py::test_duas_transferencias_nao_estouram_o_saldo PASSED     [100%]

============================== 2 passed in 0.70s ===============================
```

---

## O fio que costura os três blocos

Olhe o que cada conserto mudou. Quase nunca foi a conta. Foi **quem decide, e quando**.

Na 1.1, quem decidia o arredondamento era o padrão do `Decimal`. O conserto pôs a decisão no código, com o nome da regra. Na 1.2, o `float` decidia o valor antes de o `Decimal` chegar. O conserto pôs o `Decimal` dentro do parser, antes de qualquer decisão. Na 2.1, o Python somava o que o banco podia somar. O conserto mandou a conta para onde os dados estão. Na 2.2, alguém precisava decidir o que fazer com as linhas repetidas, e o SQLAlchemy se recusou a decidir sozinho. Na 3.1, cada linha decidia sozinha que já valia. O conserto deu essa decisão a quem sabe o que é a operação inteira. Na 3.2, a transferência decidia antes de entrar na fila. O conserto fez ela entrar na fila primeiro.

Três desses defeitos são, literalmente, coisa fora de hora. O `Decimal` chegou tarde. O `commit` chegou cedo. O cadeado chegou tarde.

E quase nenhum fez barulho no caso comum. A taxa acertou três de cinco contas. O atalho do `str` passou em todos os testes. O resumo de 41 consultas devolvia a resposta certa. O extrato só fica pela metade quando algo falha no meio. A transferência só estoura o saldo quando duas chegam juntas. Em todos, o defeito mora no caso de canto: o empate, o número longo, a escala, a falha, a concorrência.

Dinheiro é justamente onde o caso de canto não pode ser ignorado. Um centavo a mais em toda conta, um extrato pela metade, um saldo negativo que ninguém autorizou. Ninguém aceita "funciona na maioria das vezes" de uma conta bancária. Por isso os testes destes exercícios **forçam** o caso de canto, em vez de esperar que ele apareça sozinho: o empate, a falha no meio, as duas transferências chegando juntas. E onde um teste não alcança, como no atalho do `str`, alguém precisa saber perguntar.
