# Lição 05 — Dinheiro não é float

O grupo existe. A Ana e o Bruno estão no chalé. A próxima coisa que eles vão fazer é gastar dinheiro e querer dividir. Antes de o FairFare aceitar o primeiro real, tem uma conta antiga para acertar.

Lá na lição 08 do capítulo 0, olhando a tabela JSON ↔ Python, ficou uma bandeira fincada:

> Não vamos resolver isso agora; só fincar a bandeira: **dinheiro não é float**. Quando o app de despesas compartilhadas nascer e começarmos a dividir contas (capítulo 5), essa rachadura vira cratera — de propósito, para você ver o desastre antes da solução.

O app nasceu. Estamos no capítulo 5. Esta lição é a cratera.

## Seis desastres

Está tudo num script só, Python puro, sem banco e sem app:

```bash
uv run python chapters/05-relacoes-e-dinheiro/bancada/float.py
```

Vou mostrar a saída em pedaços, um desastre por vez. O script usa o `Decimal` em três lugares, nos desastres 2, 3 e 5, mas só como lupa: `Decimal(um_float)` mostra o número que o `float` guarda de verdade. Já já você vê por que isso importa.

### 1. Dez moedas de dez centavos

Some R$ 0,10 dez vezes, num laço:

```python
total = 0.0
for _ in range(10):
    total += 0.1
```

```console
== 1. Dez vezes R$ 0,10, num laço ==
total            = 0.9999999999999999
total == 1.0     -> False
```

Dez moedas de dez centavos não dão um real. Não no `float`.

Uma nota de rodapé curiosa. Se você escrever `sum([0.1] * 10)`, o Python 3.12 devolve `1.0`. Rodei:

```console
$ uv run python -c 'print(sum([0.1] * 10))'
1.0
```

Desde o 3.12, o `sum()` usa uma soma compensada: ele carrega à parte o erro de cada passo e o devolve no fim. Até o Python tenta te salvar. Mas só ali, dentro do `sum`. O `+=` num laço, que é como saldo de verdade costuma ser calculado, não tem essa proteção.

### 2. O clássico

```console
== 2. 0.1 + 0.2 ==
0.1 + 0.2        = 0.30000000000000004
0.1 + 0.2 == 0.3 -> False
Decimal(0.1)     = 0.1000000000000000055511151231257827021181583404541015625
```

Guarde a última linha. Ela é a explicação de tudo, e volta mais abaixo.

### 3. O arredondamento que arredonda errado

`2.675` com duas casas. A regra da escola diz: termina em 5, sobe. Então `2.68`.

```console
== 3. round(2.675, 2) ==
round(2.675, 2)  = 2.67
Decimal(2.675)   = 2.67499999999999982236431605997495353221893310546875
```

O `round` não errou. Ele recebeu `2.67499999…`, e isso arredonda para baixo mesmo. Quem errou foi o literal `2.675`, que nunca foi `2.675`. Você digitou um número, e o Python guardou outro.

### 4. A conta do bar

R$ 80,10 entre três amigos. Cada parte arredondada para centavos, e as três somadas de volta para conferir:

```python
parte = round(conta / 3, 2)
reconstruido = parte + parte + parte
```

```console
== 4. A conta do bar dividida entre 3 ==
conta            = 80.1
conta / 3        = 26.7
parte (round)    = 26.7
parte * 3 somada = 80.1
fecha?           -> True
diferença        = 0.0

conta            = 90.3
conta / 3        = 30.099999999999998
parte (round)    = 30.1
parte * 3 somada = 90.30000000000001
fecha?           -> False
diferença        = -1.4210854715202004e-14
```

Os R$ 80,10 fecharam. Eu esperava que não fechassem, e fecharam. Por sorte: cada arredondamento do caminho caiu no vizinho binário certo. Mudei a conta para R$ 90,30, a mesma operação, e a sorte acabou.

Esse é o desastre de verdade. Não é "o `float` erra". É **você não saber em quais números ele erra**. Um teste com 80,10 passa. Uma conta real com 90,30 não fecha. O bug passa pelo teste e aparece em produção, numa conta qualquer.

### 5. O JSON

A rachadura do capítulo 0 era esta. Um cliente manda um valor no corpo da request:

```console
== 5. json.loads de um valor ==
json.loads(...)  = {'valor': 80.1}
type(valor)      = float
Decimal(valor)   = 80.099999999999994315658113919198513031005859375
```

O JSON tem um tipo numérico só, e o `json.loads` traduz número com ponto para `float`. O capítulo 0 disse que `80.10` "pode virar `80.09999999...` num float". Agora você vê os dígitos, todos eles. O valor entrou na API e já chegou torto, antes de qualquer conta.

### 6. O extrato

Mil lançamentos de R$ 0,10. Um extrato de um mês movimentado, ou de um ano de cafezinho.

```console
== 6. Extrato: mil lançamentos de R$ 0,10 ==
saldo            = 99.9999999999986
saldo == 100.0   -> False
100.0 - saldo    = 1.4068746168049984e-12
```

Com dez somas, o erro estava na 16ª casa decimal. Com mil, subiu para a 12ª. O erro não fica parado: cada conta deposita um pouco, e ele se acumula.

"Mas formatado com duas casas fica certo", você pensa. Fica. E isso é pior:

```console
$ uv run python -c '
saldo = 0.0
for _ in range(1000):
    saldo += 0.1
print(f"{saldo:.2f}", saldo >= 100.0)'
100.00 False
```

A tela mostra `100.00`. O `if saldo >= 100.0` diz que não. O usuário vê cem reais e o sistema diz que ele não tem cem reais. Esse ticket de suporte ninguém consegue reproduzir olhando a tela.

## Por quê

Tente escrever 1/3 em decimal. `0,333333…` Você para em algum lugar, e o que você escreveu é um pouco menor que 1/3. Não há falta de cuidado: 1/3 simplesmente não cabe num número finito de casas na base 10. A base 10 só representa com exatidão frações cujo denominador é feito de 2 e de 5.

O computador conta na base 2. Lá, só cabem exatas as frações cujo denominador é potência de 2: 1/2, 1/4, 3/8. E 1/10 tem um 5 no denominador. Em binário, 0,1 é uma dízima:

```text
0,1 (base 10) = 0,0001100110011001100110011… (base 2)
```

O `0011` se repete para sempre. Igualzinho ao 3 do 1/3.

Agora o rigor. O `float` do Python é um número **IEEE 754 binário de 64 bits** (o padrão que praticamente todo processador implementa). São 64 bits: um para o sinal, 11 para o expoente e 52 para os dígitos da fração. A dízima de 0,1 não cabe em 52 bits, então o que fica guardado é a fração binária **mais próxima** de 0,1. Ela não é 0,1. É isto:

```text
0.1000000000000000055511151231257827021181583404541015625
```

O `Decimal(0.1)` do desastre 2 não arredonda nada. Ele converte o `float` dígito por dígito, e mostra o número que de fato está na memória. Cada `0.1` que você digita já vem com esse resto de `0.0000000000000000055…`. E cada soma arredonda de novo, para o vizinho binário mais próximo do resultado. Cada soma pode arredondar de novo, e o total escorrega para `0.9999999999999999`. O 2.675 é a mesma história, só que o vizinho mais próximo ficou do lado de baixo.

## "Mas o `print` mostrou 0.1!"

Mostrou:

```console
$ uv run python -c 'print(0.1)'
0.1
```

Se o número guardado é `0.1000000000000000055…`, por que o Python mostra `0.1`?

Porque o `repr` de um `float` (o que o `print` e o terminal usam) não mostra o número guardado. Ele mostra o **decimal mais curto que, lido de volta, cai no mesmo `float`**. Vários decimais caem no mesmo vizinho binário. `0.1` é o mais curto deles, então é o que aparece.

É uma escolha gentil, e enganosa. O `repr` esconde o erro. O erro continua lá. Ele só aparece quando a conta empurra o resultado para um vizinho binário diferente, e aí o decimal mais curto deixa de ser bonito: `0.30000000000000004`, `0.9999999999999999`.

## Por que dinheiro é diferente

Para muita coisa, isso não importa. A temperatura de um sensor, a posição de um pixel, a distância até a quadra. Ninguém liga para a 16ª casa decimal de um quilômetro. O `float` foi feito para isso: rápido, com um erro relativo minúsculo e previsível.

Dinheiro tem outra regra. **A soma precisa fechar no centavo, sempre.** Não "quase sempre", não "com erro relativo pequeno". Se a Ana pagou R$ 90,30 e a conta foi dividida em três, as três partes somam R$ 90,30. Se não somam, sumiu dinheiro, ou apareceu.

E um erro minúsculo não fica minúsculo. Ele se acumula, como no extrato. E ele vira decisão: um `==` que dá `False`, um `>=` que nega um saldo, um `round` que cai para o lado errado. Quando essa decisão mexe num centavo, o centavo errado aparece num extrato. Num extrato, um centavo errado é um bug. Não é um arredondamento.

## O que fica declarado

- **O `float.py` não é código do app.** É bancada, Python puro, e não fala com o banco.
- **O desastre 4 tem duas contas, e não uma.** Os R$ 80,10 fecharam no `float`, por sorte. A segunda conta, de R$ 90,30, está lá para mostrar a sorte acabando.
- **O app ainda não tem dinheiro nenhum.** Nenhuma coluna, nenhum schema e nenhuma rota do FairFare guarda valor monetário até aqui. Nada para consertar no código. Ainda.

## O que você deve conseguir fazer agora

- Explicar por que `0.1 + 0.2 != 0.3`, com a analogia do 1/3 e depois com o rigor: base 2, IEEE 754, a fração binária mais próxima.
- Dizer o que o `repr` de um `float` esconde, e usar `Decimal(um_float)` para enxergar o número que ele guarda.
- Prever, antes de rodar, que somar `0.1` num laço não dá o número redondo, e explicar por que o `sum()` do 3.12 dá.
- Explicar por que um erro de arredondamento que não incomoda num sensor é um bug num extrato.

Falta a pergunta óbvia. Se o `float` não serve, o que serve? O Python tem um tipo que conta em base 10, do jeito que você conta dinheiro. Ele já apareceu nesta lição, discreto, fazendo papel de lupa. Na lição 06, ele vira a solução: o `Decimal`.
