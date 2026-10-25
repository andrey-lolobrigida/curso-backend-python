"""Bancada da lição 06: o cronômetro do login.

O login responde a mesma coisa para "esse email não existe" e para "a senha está errada":
401, "email ou senha inválidos". Mas responde no mesmo TEMPO? Este script mede.

Suba o FairFare e rode:
  uv run uvicorn app.main:app --port 8000
  uv run python chapters/06-autenticacao-e-seguranca/bancada/enumeracao.py
(o uvicorn em outra porta? --url http://localhost:PORTA)

O script garante um usuário da bancada (o cadastro; um 409 também serve, quer dizer que ele
já existe). Depois faz N logins com um email que ninguém cadastrou e N com o email da bancada
e a senha errada, intercalados, e imprime mediana, mínimo e máximo de cada grupo, e a diferença
e a razão entre as medianas. Intercalar espalha o ruído da máquina pelos dois grupos por igual.

O QUE O SCRIPT FAZ NO BANCO DE DESENVOLVIMENTO (o fairfare do compose): cria, uma vez só, o
usuário bancada.cap06@example.com. Os logins recusados não gravam nada.
"""

import argparse
import statistics
import time

import httpx2

N = 30
EMAIL = "bancada.cap06@example.com"
SENHA = "a senha certa da bancada"
INEXISTENTE = "ninguem.cap06@example.com"  # bem formado: o LoginIn exige um EmailStr

# O rate limiter da lição 05 do cap. 3 dá 20 fichas por IP e devolve 5 por segundo.
# 61 requests de uma vez esvaziariam o balde, e um 429 responde em 1 ms: ia sujar a medida.
# Com 0,25 s entre uma e outra, são no máximo 4 por segundo, abaixo das 5 da recarga.
PAUSA = 0.25


def ms(segundos: float) -> str:
    """Milissegundos no jeito brasileiro: ms(0.0123) -> '12,3 ms'."""
    return f"{segundos * 1000:.1f} ms".replace(".", ",")


def mede_login(cliente: httpx2.Client, email: str, senha: str) -> float:
    comeco = time.perf_counter()
    resp = cliente.post("/auth/login", json={"email": email, "senha": senha})
    tempo = time.perf_counter() - comeco
    # Só vale medir um 401. Um 429 do limitador, ou um 200, seria outra conversa.
    assert resp.status_code == 401, (resp.status_code, resp.text)
    return tempo


def resume(nome: str, tempos: list[float]) -> None:
    print(
        f"  {nome:<18} mediana {ms(statistics.median(tempos)):>9}   "
        f"mín {ms(min(tempos)):>9}   máx {ms(max(tempos)):>9}"
    )


def main(url: str) -> None:
    # Um cliente só: a mesma conexão (keep-alive) para os dois grupos.
    with httpx2.Client(base_url=url) as cliente:
        cadastro = cliente.post("/users", json={"nome": "Bancada", "email": EMAIL, "senha": SENHA})
        assert cadastro.status_code in (201, 409), (cadastro.status_code, cadastro.text)
        print(f"usuário da bancada: {EMAIL} (cadastro: {cadastro.status_code})")
        time.sleep(PAUSA)

        inexistente: list[float] = []
        senha_errada: list[float] = []
        for _ in range(N):
            inexistente.append(mede_login(cliente, INEXISTENTE, SENHA))
            time.sleep(PAUSA)
            senha_errada.append(mede_login(cliente, EMAIL, "a senha errada"))
            time.sleep(PAUSA)

    print(f"{N} logins de cada, intercalados, todos 401:")
    resume("email inexistente", inexistente)
    resume("senha errada", senha_errada)
    diferenca = statistics.median(senha_errada) - statistics.median(inexistente)
    razao = statistics.median(senha_errada) / statistics.median(inexistente)
    print(f"  diferença entre as medianas: {ms(diferenca)}")
    print(f"  razão entre as medianas (senha errada / inexistente): {razao:.1f}x".replace(".", ","))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    main(args.url)
