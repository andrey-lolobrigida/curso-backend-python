"""Bloco 3 — o token que não morre. (QUEBRADO DE PROPÓSITO)

A tabela de sessões da lição 04, em memória: um dict no papel da tabela `sessions`.
Quem chama passa o `agora`, para o teste poder adiantar o relógio sem esperar 24 horas.
"""

import secrets
from datetime import datetime, timedelta

VALIDADE = timedelta(hours=24)


def criar_sessao(sessoes: dict, user_id: int, agora: datetime) -> str:
    """Abre uma sessão e devolve o token, que vai para o cliente.

    EXERCÍCIO 3: este módulo tem dois defeitos de propósito. Os testes mostram quais.
    """
    token = secrets.token_urlsafe(32)
    sessoes[token] = {"user_id": user_id, "expira_em": agora + VALIDADE}
    return token


def usuario_do_token(sessoes: dict, token: str, agora: datetime) -> int | None:
    """O user_id dono do token, ou None se o token não vale."""
    sessao = sessoes.get(token)
    if sessao is None:
        return None
    return sessao["user_id"]
