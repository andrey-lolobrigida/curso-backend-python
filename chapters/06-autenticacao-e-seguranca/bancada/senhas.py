"""Bancada da lição 02: senha não se guarda.

Quatro jeitos de guardar a senha de três contas, um por ato. Em cada um, o
script faz o papel de quem roubou a tabela e tenta descobrir as senhas.
Nada aqui fala com o banco nem com o app: é só a biblioteca padrão.

  uv run python chapters/06-autenticacao-e-seguranca/bancada/senhas.py

A "tabela" é um dict. O "dicionário" do atacante é uma lista de ~1000 senhas
comuns gerada aqui mesmo. Os tempos são de um núcleo só, chamando o hashlib
(que roda em C, via OpenSSL) de um laço Python. Quem ataca de verdade usa placa
de vídeo, e o ganho dela é maior justamente no sha256.

As contas impressas usam os valores arredondados que aparecem na tela, para
fecharem na calculadora.

O app não usa nada disto. O FairFare guarda senha com argon2 (lição 03).
"""

import hashlib
import os
import statistics
import time

# As três contas. Ana e Bruno escolheram a mesma senha, sem combinar.
CONTAS = {
    "ana@example.com": "senha123",
    "bruno@example.com": "senha123",
    "carla@example.com": "flamengo",
}

# O dicionário do atacante: senha1 a senha999 e umas famosas.
FAMOSAS = [
    "123456",
    "123456789",
    "12345678",
    "password",
    "qwerty",
    "abc123",
    "111111",
    "iloveyou",
    "admin",
    "senha",
    "102030",
    "brasil",
    "flamengo",
    "corinthians",
    "palmeiras",
    "minhasenha",
]
DICIONARIO = [f"senha{i}" for i in range(1, 1000)] + FAMOSAS


def secao(titulo: str) -> None:
    print()
    print(f"== {titulo} ==")


def num(x: float, casas: int = 0) -> str:
    """Número no jeito brasileiro: num(1234567.891, 2) -> '1.234.567,89'."""
    return f"{x:,.{casas}f}".translate(str.maketrans(",.", ".,"))


def sha256(dados: bytes) -> bytes:
    return hashlib.sha256(dados).digest()


def scrypt(senha: str, sal: bytes, n: int) -> bytes:
    # O OpenSSL tem um teto de memória padrão, e o n=2^15 passa dele. O maxmem sobe o teto.
    return hashlib.scrypt(senha.encode(), salt=sal, n=n, r=8, p=1, dklen=32, maxmem=64 * 2**20)


# 1. Como estão.
secao("1. Texto puro")
tabela = dict(CONTAS)
for email, senha in tabela.items():
    print(f"{email:<18} senha = {senha}")
print("Vazou o banco, vazou tudo. Não há o que atacar: está escrito.")

# 2. sha256, sem mais nada.
secao("2. sha256 puro")
inicio = time.perf_counter()
contagem = 0
while time.perf_counter() - inicio < 1.0:
    for _ in range(10_000):
        sha256(b"senha123")
    contagem += 10_000
por_segundo = round(contagem / (time.perf_counter() - inicio))
print(f"sha256 por segundo neste computador: {num(por_segundo)}")
print()

tabela = {email: sha256(senha.encode()) for email, senha in CONTAS.items()}
for email, h in tabela.items():
    print(f"{email:<18} {h.hex()}")
print("Ana e Bruno: mesmo hash. Quem vê um, sabe que os dois usam a mesma senha.")
print()

# O ataque: calcula o hash de cada palavra do dicionário UMA vez...
inicio = time.perf_counter()
tabela_pronta = {sha256(palavra.encode()): palavra for palavra in DICIONARIO}
montagem = time.perf_counter() - inicio
# ...e depois cada hash vazado é só uma consulta no dict.
inicio = time.perf_counter()
achadas = {email: tabela_pronta.get(h) for email, h in tabela.items()}
consulta = time.perf_counter() - inicio
print(f"dicionário: {len(DICIONARIO)} senhas")
print(f"montar a tabela pronta (hash -> senha): {num(montagem * 1000, 3)} ms")
print(f"consultar as {len(tabela)} contas: {num(consulta * 1000, 3)} ms")
for email, senha in achadas.items():
    print(f"{email:<18} -> {senha}")

# 3. sha256 com sal: 16 bytes aleatórios por conta, guardados ao lado do hash.
secao("3. sha256 com sal")
tabela = {}
for email, senha in CONTAS.items():
    sal = os.urandom(16)
    tabela[email] = (sal, sha256(sal + senha.encode()))
for email, (sal, h) in tabela.items():
    print(f"{email:<18} sal = {sal.hex()}")
    print(f"{'':<18} hash = {h.hex()}")
print("Ana e Bruno: mesma senha, hashes diferentes.")
print()

achadas = [tabela_pronta.get(h) for _, h in tabela.values()]
print(
    f"a tabela pronta do ato 2 contra os hashes com sal: "
    f"{sum(a is not None for a in achadas)} de {len(tabela)} achadas"
)
print()

# O atacante refaz o dicionário, agora conta a conta, com o sal de cada uma.
print("o mesmo dicionário, refeito para cada conta com o sal dela:")
for email, (sal, h) in tabela.items():
    inicio = time.perf_counter()
    achada = None
    for palavra in DICIONARIO:
        if sha256(sal + palavra.encode()) == h:
            achada = palavra
            break
    gasto = time.perf_counter() - inicio
    print(f"{email:<18} -> {achada}  ({num(gasto * 1000, 3)} ms)")
print("O sal matou a tabela pronta. A força bruta continua rápida, conta a conta.")

# 4. Uma KDF lenta de propósito: scrypt.
secao("4. scrypt (r=8, p=1)")
sal = os.urandom(16)
custo_ms = {}
for expoente in (14, 15):
    n = 2**expoente
    tempos = []
    for _ in range(7):
        inicio = time.perf_counter()
        scrypt("senha123", sal, n)
        tempos.append(time.perf_counter() - inicio)
    custo_ms[n] = round(statistics.median(tempos) * 1000, 1)
    memoria = 128 * 8 * n // 2**20
    print(
        f"n=2^{expoente}: {num(custo_ms[n], 1)} ms por hash "
        f"({num(1000 / custo_ms[n])} por segundo), {memoria} MiB de memória (128·r·n)"
    )
print()

n = 2**14
d = len(DICIONARIO)
print(f"o dicionário de {d} senhas, contra UMA conta:")
print(f"  sha256 com sal: {d} ÷ {num(por_segundo)}/s = {num(d / por_segundo * 1000, 2)} ms")
print(
    f"  scrypt n=2^14:  {d} × {num(custo_ms[n], 1)} ms = {num(d * custo_ms[n], 1)} ms "
    f"(~{num(d * custo_ms[n] / 1000, 1)} s)"
)
# Um scrypt custa o tempo de quantos sha256? custo de um × sha256 por segundo.
print(
    f"  o scrypt sai {num(custo_ms[n], 1)} ms × {num(por_segundo)}/s "
    f"= {num(custo_ms[n] / 1000 * por_segundo)} vezes mais caro"
)
print(f"e o login de quem sabe a senha: um hash só, {num(custo_ms[n], 1)} ms")
