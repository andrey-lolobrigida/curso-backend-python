import hashlib
import hmac

import pytest
from bloco4.jwt import assinar, b64url, de_b64url, para_json, verificar

SEGREDO = b"segredo-do-exercicio"
ANA = {"sub": "1", "nome": "Ana"}


def test_token_legitimo_passa():
    assert verificar(assinar(ANA, SEGREDO), SEGREDO) == ANA


def test_assinatura_adulterada_e_recusada():
    h64, p64, s64 = assinar(ANA, SEGREDO).split(".")
    # A adulteração mexe nos bytes, e não no texto. Trocar a última letra da assinatura
    # pode não mudar nada: os 32 bytes viram 43 caracteres, e os 2 últimos bits da última
    # letra são enchimento, que o decodificador joga fora. Enfiar caracteres fora do
    # alfabeto também não serve: o urlsafe_b64decode os descarta, em vez de recusar.
    # Com "!!!!" no meio da assinatura, os bytes que saem são os mesmos de antes.
    bytes_ = bytearray(de_b64url(s64))
    bytes_[0] ^= 1
    with pytest.raises(ValueError):
        verificar(f"{h64}.{p64}.{b64url(bytes(bytes_))}", SEGREDO)


def test_alg_none_e_recusado():
    # O token forjado da lição 08: header "none", o payload que o atacante quiser, e nada
    # depois do último ponto. Nenhum segredo foi usado para montá-lo.
    forjado = f"{b64url(para_json({'alg': 'none', 'typ': 'JWT'}))}.{b64url(para_json(ANA))}."
    with pytest.raises(ValueError):
        verificar(forjado, SEGREDO)


@pytest.mark.parametrize("mac", [hashlib.sha256, hashlib.sha512], ids=["mac-sha256", "mac-sha512"])
def test_alg_inesperado_e_recusado(mac):
    # Header que pede HS512, com assinatura que CONFERE (feita com o segredo certo).
    # O header não escolhe nada: no máximo confirma o HS256 que o verificador espera.
    header = b64url(para_json({"alg": "HS512", "typ": "JWT"}))
    entrada = f"{header}.{b64url(para_json(ANA))}"
    assinatura = hmac.new(SEGREDO, entrada.encode(), mac).digest()
    with pytest.raises(ValueError):
        verificar(f"{entrada}.{b64url(assinatura)}", SEGREDO)
