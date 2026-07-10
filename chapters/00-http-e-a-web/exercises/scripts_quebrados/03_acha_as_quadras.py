"""Exercício 3.3 — este script usa um endereço antigo do servidor e confia demais.

QUANDO ESTIVER PRONTO, a saída deve ser exatamente:

    O servidor conhece 3 quadras.

Regras do jogo: o endereço /antigo deve continuar no código (finja que veio
de um config velho que você não controla). Seu conserto deve ENSINAR o script
a reagir ao que o servidor responde. As lições 04 e 05 são suas amigas.
"""

import json
from http.client import HTTPConnection


def conta_quadras():
    conexao = HTTPConnection("localhost", 8000)
    conexao.request("GET", "/antigo")
    resposta = conexao.getresponse()
    dados = json.loads(resposta.read())
    return len(dados)


if __name__ == "__main__":
    print(f"O servidor conhece {conta_quadras()} quadras.")