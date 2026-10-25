import hashlib
from datetime import UTC, datetime, timedelta

from bloco3.sessoes import criar_sessao, usuario_do_token

LOGIN = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)


def test_token_valido():
    sessoes = {}
    token = criar_sessao(sessoes, 1, LOGIN)
    assert usuario_do_token(sessoes, token, LOGIN + timedelta(hours=1)) == 1


def test_token_desconhecido():
    sessoes = {}
    criar_sessao(sessoes, 1, LOGIN)
    assert usuario_do_token(sessoes, "um-token-que-ninguem-emitiu", LOGIN) is None


def test_token_vencido_e_recusado():
    # O teste do relógio: 25 horas depois do login, o crachá de 24 horas já venceu.
    sessoes = {}
    token = criar_sessao(sessoes, 1, LOGIN)
    assert usuario_do_token(sessoes, token, LOGIN + timedelta(hours=25)) is None


def test_token_vence_na_hora_cravada():
    # A borda, com o critério do WHERE da lição 05: vale enquanto expira_em > agora.
    sessoes = {}
    token = criar_sessao(sessoes, 1, LOGIN)
    um_segundo_antes = LOGIN + timedelta(hours=24) - timedelta(seconds=1)
    assert usuario_do_token(sessoes, token, um_segundo_antes) == 1
    assert usuario_do_token(sessoes, token, LOGIN + timedelta(hours=24)) is None


def test_tabela_nao_guarda_o_token():
    # Se a tabela vazar, quem a lê não pode sair dela com um crachá que funciona.
    sessoes = {}
    token = criar_sessao(sessoes, 1, LOGIN)
    guardado = set(sessoes) | {v for sessao in sessoes.values() for v in sessao.values()}
    assert token not in guardado
    assert list(sessoes) == [hashlib.sha256(token.encode()).hexdigest()]
