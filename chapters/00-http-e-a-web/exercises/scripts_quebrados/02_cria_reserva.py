"""Exercício 3.2 — este script deveria criar uma reserva, mas ele tem DOIS bugs.

QUANDO ESTIVER PRONTO, a saída deve ser (o número no final pode variar):

    Reserva criada! Ela mora em: /reservas/1

Conserte um bug de cada vez e observe como o ERRO MUDA — o servidor está
te contando o que falta. As lições 03 e 08 são suas amigas.
"""

from http.client import HTTPConnection


def cria_reserva(quadra_id, quem):
    conexao = HTTPConnection("localhost", 8000)
    corpo = str({"quadra_id": quadra_id, "quem": quem})
    conexao.request("POST", "/reservas", body=corpo)
    resposta = conexao.getresponse()
    if resposta.status != 201:
        detalhe = resposta.read().decode()
        raise RuntimeError(f"o servidor respondeu {resposta.status}: {detalhe}")
    return resposta.getheader("Location")


if __name__ == "__main__":
    endereco = cria_reserva(quadra_id=1, quem="voce")
    print(f"Reserva criada! Ela mora em: {endereco}")