"""Bloco 1 — o login que fala demais. (QUEBRADO DE PROPÓSITO)

Confere email e senha contra uma tabela de usuários em memória: email -> hash argon2.
Uma conta antiga, de antes do cadastro com senha, aparece com o hash `None`.

O `hasher` daqui usa parâmetros baixos (t=1, m=8 MiB, p=1) só para os testes do exercício
rodarem rápido. Não copie para lugar nenhum: no app, quem manda são os padrões da
biblioteca (lição 03).
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

hasher = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1)


class LoginRecusado(Exception):
    pass


def entrar(usuarios: dict[str, str | None], email: str, senha: str) -> str:
    """Devolve "ok" se o email e a senha conferem. Senão, levanta LoginRecusado.

    EXERCÍCIO 1: esta função tem dois defeitos de propósito. Os testes mostram quais.
    """
    if email not in usuarios:
        raise LoginRecusado("email não cadastrado")
    senha_hash = usuarios[email]
    if senha_hash is None:
        raise LoginRecusado("conta sem senha")
    try:
        hasher.verify(senha_hash, senha)
    except VerifyMismatchError:
        raise LoginRecusado("senha incorreta") from None
    return "ok"
