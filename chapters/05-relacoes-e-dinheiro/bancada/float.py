"""Bancada da lição 05: dinheiro não é float.

Seis desastres, um por seção. Cada um imprime a conta e o resultado.
Nada aqui fala com o banco nem com o app: é Python puro.

  uv run python chapters/05-relacoes-e-dinheiro/bancada/float.py

O Decimal aparece nos desastres 2, 3 e 5, só como lupa: Decimal(um_float)
mostra o número que o float guarda de verdade. A solução é a lição 06.
"""

import json
from decimal import Decimal


def secao(titulo: str) -> None:
    print()
    print(f"== {titulo} ==")


# 1. Dez moedas de 10 centavos. Laço, e não sum(): o sum() do Python 3.12
#    compensa o erro de arredondamento e devolveria 1.0 (ver a lição).
secao("1. Dez vezes R$ 0,10, num laço")
total = 0.0
for _ in range(10):
    total += 0.1
print(f"total            = {total!r}")
print(f"total == 1.0     -> {total == 1.0}")

# 2. O clássico.
secao("2. 0.1 + 0.2")
print(f"0.1 + 0.2        = {0.1 + 0.2!r}")
print(f"0.1 + 0.2 == 0.3 -> {0.1 + 0.2 == 0.3}")
print(f"Decimal(0.1)     = {Decimal(0.1)}")

# 3. Arredondar "para cima no 5" que arredonda para baixo.
secao("3. round(2.675, 2)")
print(f"round(2.675, 2)  = {round(2.675, 2)!r}")
print(f"Decimal(2.675)   = {Decimal(2.675)}")

# 4. Uma conta de bar entre três amigos. Cada parte arredondada e somada de volta.
#    80,10 fecha por sorte; 90,30, não. Você não escolhe em qual número o erro cai.
secao("4. A conta do bar dividida entre 3")
for i, conta in enumerate((80.10, 90.30)):
    if i:
        print()
    parte = round(conta / 3, 2)
    reconstruido = parte + parte + parte
    print(f"conta            = {conta!r}")
    print(f"conta / 3        = {conta / 3!r}")
    print(f"parte (round)    = {parte!r}")
    print(f"parte * 3 somada = {reconstruido!r}")
    print(f"fecha?           -> {reconstruido == conta}")
    print(f"diferença        = {conta - reconstruido!r}")

# 5. O JSON não tem tipo decimal: número com ponto vira float.
secao("5. json.loads de um valor")
corpo = json.loads('{"valor": 80.10}')
print(f"json.loads(...)  = {corpo!r}")
print(f"type(valor)      = {type(corpo['valor']).__name__}")
print(f"Decimal(valor)   = {Decimal(corpo['valor'])}")

# 6. Mil lançamentos de R$ 0,10 num extrato.
secao("6. Extrato: mil lançamentos de R$ 0,10")
saldo = 0.0
for _ in range(1000):
    saldo += 0.1
print(f"saldo            = {saldo!r}")
print(f"saldo == 100.0   -> {saldo == 100.0}")
print(f"100.0 - saldo    = {100.0 - saldo!r}")
