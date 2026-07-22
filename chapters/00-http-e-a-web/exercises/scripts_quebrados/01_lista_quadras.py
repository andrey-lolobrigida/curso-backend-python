"""Exercício 3.1 — este script deveria listar as quadras, mas alguém o quebrou.

QUANDO ESTIVER PRONTO, a saída deve ser exatamente:

    Quadra Central (tenis) - R$80/h
    Ginasio Azul (basquete) - R$120/h
    Saibro do Fundo (tenis) - R$60/h

Regras do jogo: conserte SEM mudar a função exibe(). O bug está na conversa
com o servidor. A lição 06 é sua amiga.
"""

import json
from http.client import HTTPConnection


def busca_quadras():
    conexao = HTTPConnection("localhost", 8000)
    conexao.request("POST", "/quadras")
    resposta = conexao.getresponse()
    if resposta.status != 200:
        raise RuntimeError(f"o servidor respondeu {resposta.status} {resposta.reason}")
    return json.loads(resposta.read())


def exibe(quadras):
    for q in quadras:
        print(f"{q['nome']} ({q['esporte']}) - R${q['preco_hora']}/h")


if __name__ == "__main__":
    exibe(busca_quadras())
