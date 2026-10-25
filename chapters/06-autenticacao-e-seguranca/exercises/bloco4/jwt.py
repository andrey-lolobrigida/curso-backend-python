"""Bloco 4 (opcional) — o JWT que aceita qualquer um. (QUEBRADO DE PROPÓSITO)

O JWT HS256 da bancada da lição 08, só com a biblioteca padrão. O `assinar` está certo.
O `verificar` tem um defeito. Recusar um token é levantar `ValueError`.

Para o exercício ficar numa ideia só, aqui não tem `exp`. A bancada da lição 08 confere.
É brinquedo: em produção, quem monta e confere JWT é uma biblioteca mantida e auditada.
"""

import base64
import hashlib
import hmac
import json


def b64url(dados: bytes) -> str:
    # O base64 de sempre, com - e _ no lugar de + e /, e sem o = do fim.
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def de_b64url(texto: str) -> bytes:
    # O caminho de volta. O decodificador do Python exige o =, então ele volta aqui.
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def para_json(obj: dict) -> bytes:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()


def hs256(entrada: str, segredo: bytes) -> bytes:
    return hmac.new(segredo, entrada.encode("ascii"), hashlib.sha256).digest()


def assinar(payload: dict, segredo: bytes) -> str:
    entrada = f"{b64url(para_json({'alg': 'HS256', 'typ': 'JWT'}))}.{b64url(para_json(payload))}"
    return f"{entrada}.{b64url(hs256(entrada, segredo))}"


def verificar(token: str, segredo: bytes) -> dict:
    """Devolve o payload se o token vale. Senão, levanta ValueError.

    EXERCÍCIO 4: esta função tem um defeito de propósito. Os testes mostram qual.
    """
    h64, p64, s64 = token.split(".")
    header, payload = json.loads(de_b64url(h64)), json.loads(de_b64url(p64))
    if header.get("alg") == "none":
        return payload  # sem algoritmo, nada para conferir
    if not hmac.compare_digest(hs256(f"{h64}.{p64}", segredo), de_b64url(s64)):
        raise ValueError("assinatura não confere")
    return payload
