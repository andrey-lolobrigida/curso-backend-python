# Lição 07 — O centavo que sobra

A lição 06 fechou as três fronteiras. O dinheiro chega como string, vira `Decimal` e é gravado como `Numeric(12, 2)`. Nenhum `float` no caminho.

E mesmo assim, olhe o que acontece quando o chalé custa R$ 100 e são três amigos:

```console
$ uv run python -c '
from decimal import Decimal
parte = Decimal("100.00") / 3
print(parte)
parte = parte.quantize(Decimal("0.01"))
print(parte, parte * 3)'
33.33333333333333333333333333
33.33 99.99
```

Três partes de 33,33 somam 99,99. Sumiu um centavo.

O `Decimal` não errou a conta. 100 dividido por 3 é mesmo 33,333…, e ele mostrou isso com 28 dígitos. O problema é que dinheiro não tem dízima. Alguém vai ter que pagar 33,34. **Quem?** O `Decimal` não sabe responder, porque isso não é aritmética. É uma regra. E faltava a regra.

## As duas tentativas ingênuas

Antes da regra certa, as duas que todo mundo escreve primeiro. Rodei as duas num script descartável, sobre os mesmos laços do teste que você vai ver mais abaixo: 143 totais (de R$ 0,01 a R$ 9,95, de 7 em 7 centavos) vezes grupos de 1 a 12 pessoas. São 1716 combinações.

**(a) Arredondar a parte de todo mundo.** `(total / n).quantize(CENTAVO)` para cada um.

```console
combinações: 1716
(a) quebra a soma em: 1294 exemplo: (Decimal('0.01'), 2, Decimal('0.00'), Decimal('0.00'))
(a) 100.00 ÷ 3 -> [Decimal('33.33'), Decimal('33.33'), Decimal('33.33')] soma 99.99
```

Em 1294 das 1716 combinações a soma não fecha. Três em cada quatro. O primeiro exemplo é o mais cruel: R$ 0,01 entre duas pessoas vira 0,00 + 0,00. O centavo não ficou com ninguém. Evaporou.

**(b) O último leva o resto.** Arredonda para os primeiros `n - 1` e dá ao último o que faltar: `total - soma dos outros`. Por construção, a soma fecha:

```console
(b) quebra a soma em: 0 pior distância: (Decimal('0.06'), (Decimal('0.78'), 12, Decimal('0.06'), Decimal('0.12')))
(b) 100.00 ÷ 12 -> 8.33 x11, último 8.37 soma 100.00
```

Zero quebras. Mas olhe quem paga. R$ 100 entre 12: onze pessoas pagam 8,33 e o último paga 8,37. Quatro centavos a mais, só por estar no fim da lista. No pior caso do laço, R$ 0,78 entre 12, os onze pagam 0,06 e o último paga 0,12. O dobro.

E fica pior. Às vezes o arredondamento dos outros **sobe**, e aí o resto é negativo:

```console
(b) 0.07 ÷ 12 -> 0.01 x11, último -0.04 soma 0.07
```

A soma fecha: 0,11 menos 0,04 dá 0,07. Mas uma parte de R$ −0,04 quer dizer que o último **recebe** dinheiro por ter participado de uma despesa. No laço, isso aconteceu 7 vezes. E o banco já sabia que isso é absurdo. O `CHECK` da parte, da lição 06, recusa. Rodei no `psql` do banco de dev, dentro de uma transação desfeita no fim: uma despesa de R$ 0,07 no grupo 1, e a parte de −0,04 do Bruno:

```console
fairfare=# BEGIN;
BEGIN
fairfare=*# INSERT INTO expenses (group_id, paid_by, descricao, valor) VALUES (1, 2, 'Pão de queijo', 0.07);
INSERT 0 1
fairfare=*# INSERT INTO expense_shares (expense_id, user_id, valor) VALUES (currval('expenses_id_seq'), 3, -0.04);
ERROR:  new row for relation "expense_shares" violates check constraint "expense_shares_valor_nao_negativo"
DETAIL:  Failing row contains (1, 3, -0.04).
fairfare=!# ROLLBACK;
ROLLBACK
```

O `currval` devolve o id que o `INSERT` anterior acabou de tirar da sequência. O `1` do `DETAIL` é esse id: a primeira despesa do banco. O `ROLLBACK` desfaz as duas linhas, mas **não devolve o número**: sequência não é transacional. A próxima despesa do seu banco vai nascer com o id 2, e é por isso que os ids da lição 08 não começam do 1.

Então a tentativa (b) não é só injusta. Com o banco que a gente tem, ela vira um erro na cara de quem lança a despesa.

## A regra

Pense em distribuir balas. Você tem 100 balas e três crianças. Dá 33 para cada uma. Sobra 1. Essa uma vai para alguém, e você decide para quem **antes** de começar, para ninguém brigar.

A regra do FairFare:

1. **Todo mundo recebe o piso** da divisão, ao centavo.
2. **A sobra é distribuída centavo a centavo**, um para cada pessoa, começando do menor `user_id`.

O código mora em `app/services/divisao.py`:

```python
def dividir(total: Decimal, participantes: list[int]) -> dict[int, Decimal]:
    """Divide `total` em partes iguais, ao centavo, sem perder nenhum (lição 07).

    Cada um recebe o piso da divisão. Os centavos que sobram vão, um a um,
    aos menores user_id: uma regra arbitrária, mas escrita e sempre a mesma.
    """
    if not participantes or len(set(participantes)) != len(participantes):
        raise ValueError("participantes precisa ter ids distintos e não pode ser vazio")
    ordem = sorted(participantes)
    base = (total / len(ordem)).quantize(CENTAVO, rounding=ROUND_DOWN)
    sobra = int((total - base * len(ordem)) / CENTAVO)
    return {user_id: base + (CENTAVO if i < sobra else 0) for i, user_id in enumerate(ordem)}
```

Linha a linha:

- `ordem = sorted(participantes)`: a ordem de quem chama não importa. `[3, 1, 2]` e `[1, 2, 3]` dão o mesmo resultado.
- `base`: o piso. `ROUND_DOWN` corta as casas que sobram, sem arredondar.
- `sobra`: quantos centavos faltam para fechar o total. É sempre um número entre `0` e `n - 1`.
- O `return` dá `base + 0,01` aos primeiros `sobra` da fila e `base` aos outros.

E o resultado:

```console
>>> dividir(Decimal("100.00"), [3, 1, 2])
{1: Decimal('33.34'), 2: Decimal('33.33'), 3: Decimal('33.33')}
```

O user 1 paga 33,34. Os outros, 33,33. A soma dá 100,00, e ninguém está a mais de um centavo de ninguém.

### Por que `ROUND_DOWN`, e não o padrão

A lição 06 mostrou que o `quantize` padrão é o bancário: vai para o mais próximo, e no empate, para o par. Para a `base`, isso é exatamente o erro da tentativa (b). Olhe R$ 0,07 entre 12:

```console
$ uv run python -c '
from decimal import ROUND_DOWN, Decimal
c = Decimal("0.01")
x = Decimal("0.07") / 12
print(x, x.quantize(c), x.quantize(c, rounding=ROUND_DOWN))'
0.005833333333333333333333333333 0.01 0.00
```

O padrão arredonda 0,0058 **para cima**, 0,01. Doze pessoas vezes 0,01 dá 0,12, mais do que a despesa. A sobra fica negativa, e a regra não tem o que distribuir.

O `ROUND_DOWN` dá 0,00. A base vezes `n` nunca passa do total, então a sobra nunca é negativa. **O piso precisa ser piso**, não "o vizinho mais próximo". Aqui:

```console
>>> dividir(Decimal("0.07"), list(range(1, 13)))
{1: Decimal('0.01'), 2: Decimal('0.01'), 3: Decimal('0.01'), 4: Decimal('0.01'), 5: Decimal('0.01'), 6: Decimal('0.01'), 7: Decimal('0.01'), 8: Decimal('0.00'), 9: Decimal('0.00'), 10: Decimal('0.00'), 11: Decimal('0.00'), 12: Decimal('0.00')}
```

Sete pessoas pagam um centavo, cinco pagam zero. Soma 0,07. É aqui que aparece a parte zero que a lição 06 prometeu, e por isso o `CHECK` da parte é `valor >= 0`.

E a lista vazia? Dividir por zero pessoas não faz sentido, e um id repetido daria a mesma pessoa duas vezes. A função levanta `ValueError` nos dois casos. Quem chama (o service da lição 08) deve garantir isso antes. A função só se recusa a fingir que está tudo bem.

## A regra é arbitrária, e tudo bem

"Menor `user_id` paga o centavo" é justo? Não especialmente. Poderia ser o maior `user_id`. Poderia ser quem pagou a despesa. Poderia ser um sorteio.

Qualquer regra serve, desde que três coisas sejam verdade:

- **Ela está escrita.** No código e na docstring, não na cabeça de alguém.
- **Ela é testada.** Se alguém mudar a regra sem querer, um teste quebra.
- **Ela é sempre a mesma.** Sorteio estaria fora: a mesma despesa daria partes diferentes cada vez que fosse calculada.

O que não pode é a regra ser **implícita**. A tentativa (b) também tinha uma regra, "o último da lista paga o resto". Só que ninguém escolheu. Ela saiu do jeito que o laço foi escrito, e "o último da lista" depende da ordem em que o cliente mandou os ids.

## O teste que roda mil e setecentas combinações

O `tests/test_divisao.py` tem os casos que a gente conferiu à mão: 100 entre 3, 1 centavo entre 3, 90 entre 3 (divisão exata, que não pode inventar centavo) e as listas inválidas. Mas o teste mais importante é este:

```python
def test_a_soma_sempre_fecha():
    # Centenas de totais × tamanhos de grupo. Sem hypothesis: um laço basta.
    for centavos in range(1, 1001, 7):
        total = Decimal(centavos) / 100
        for n in range(1, 13):
            partes = dividir(total, list(range(1, n + 1)))
            assert sum(partes.values()) == total
            assert max(partes.values()) - min(partes.values()) <= Decimal("0.01")
            assert all(p.as_tuple().exponent == -2 for p in partes.values())
```

Ele não confere um valor específico. Ele confere **propriedades**, coisas que têm que ser verdade para qualquer entrada:

- a soma das partes é exatamente o total;
- ninguém está a mais de um centavo de ninguém;
- toda parte tem exatamente duas casas (o `exponent == -2` olha o expoente do `Decimal`, aquele da lição 06).

Isso se chama **teste de propriedade**. Em vez de "para 100 entre 3, a resposta é tal", ele diz "para tudo isto, a resposta obedece a tal regra". A tentativa (a) falharia na primeira linha. A (b), na segunda.

Existe uma biblioteca famosa para isso, a `hypothesis`. Ela gera entradas aleatórias e, quando acha uma que quebra, encolhe até o menor exemplo. Ela não entra aqui, de propósito. As entradas deste problema são poucas e fáceis de enumerar: dinheiro em centavos e grupos de algumas pessoas. Um laço cobre as 1716 combinações:

```console
$ uv run pytest -q tests/test_divisao.py -k soma
1 passed, 5 deselected in 0.09s
```

Nove centésimos de segundo. Uma dependência nova não compraria nada.

## Por que a parte é gravada, de novo

A lição 06 já decidiu gravar cada parte em `expense_shares`, em vez de calcular na hora. Agora dá para ver o porquê na prática. A regra do centavo é uma escolha. Escolhas mudam. Se amanhã o centavo passar a ir para quem pagou a despesa, as despesas de ontem não podem mudar junto. Com a parte gravada, a `dividir` roda **uma vez**, no lançamento, e o resultado fica no banco como foi.

## O que fica declarado

- **A regra favorece os menores `user_id`.** Quem tem id baixo paga, no máximo, um centavo a mais por despesa, em toda despesa. É uma escolha, não um bug. Num grupo com muitas despesas pequenas, esses centavos se acumulam sempre do mesmo lado. Ela volta na lição 12, na lista do que fica.
- **A `dividir` confia que o `total` tem duas casas.** Ela não confere. Com três casas, a conta da sobra trunca em silêncio: `dividir(Decimal("0.105"), [1, 2])` dá `{1: Decimal('0.05'), 2: Decimal('0.05')}`, que soma `0.10`. Quem garante as duas casas é o tipo `Dinheiro` da lição 06, na entrada da API, e o único caminho até a `dividir` passa por ele (lição 08).

## O que você deve conseguir fazer agora

- Dividir um valor à mão pela regra do FairFare: R$ 10,00 entre quatro pessoas de ids 7, 2, 9 e 4. (Piso 2,50, sobra zero. E R$ 10,01? Piso 2,50, sobra 1, e o centavo vai para o id 2.)
- Explicar por que o `Decimal` sozinho não fecha a conta: ele faz a aritmética certa, mas não decide quem fica com o centavo.
- Dizer por que a `base` usa `ROUND_DOWN`, e o que dá errado com o arredondamento padrão.
- Escrever um teste de propriedade com um laço: escolher as entradas, e afirmar o que tem que ser verdade para todas elas.
