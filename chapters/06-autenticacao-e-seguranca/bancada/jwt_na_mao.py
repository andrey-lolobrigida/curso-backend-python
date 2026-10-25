"""Bancada da lição 08: JWT por dentro.

Um JWT montado à mão, só com a biblioteca padrão: base64url, HMAC-SHA256 e json.
Primeiro ele é conferido contra o exemplo do RFC 7515 (apêndice A.1). Depois vira um
crachá do FairFare de mentira, que o script lê, adultera e falsifica, um ato por vez.

  uv run python chapters/06-autenticacao-e-seguranca/bancada/jwt_na_mao.py

O segredo vem da variável de ambiente JWT_SEGREDO. Sem ela, o script cai num padrão
escrito aqui, e avisa: o padrão existe só para a bancada rodar de primeira.

É brinquedo. Não use em produção: lá quem monta e confere JWT é uma biblioteca
mantida e auditada. E o app não usa nada disto. O FairFare continua com o token opaco
da lição 04, guardado na tabela sessions. A lição 09 explica por quê.
"""

import base64
import hashlib
import hmac
import json
import os
import time


class TokenInvalido(Exception):
    pass


def b64url(dados: bytes) -> str:
    # O base64 de sempre, com - e _ no lugar de + e /, e sem o = do fim (RFC 7515, seção 2).
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def de_b64url(texto: str) -> bytes:
    # O caminho de volta. O decodificador do Python exige o =, então ele volta aqui.
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def hs256(entrada: str, segredo: bytes) -> bytes:
    # HMAC: um hash com chave. Sem a chave, ninguém calcula o mesmo resultado.
    return hmac.new(segredo, entrada.encode("ascii"), hashlib.sha256).digest()


def montar(header: bytes, payload: bytes, segredo: bytes) -> str:
    # As três partes: header.payload.assinatura. A assinatura cobre as duas primeiras,
    # do jeito que elas viajam (em base64url), e não o JSON original.
    entrada = f"{b64url(header)}.{b64url(payload)}"
    return f"{entrada}.{b64url(hs256(entrada, segredo))}"


def para_json(obj: dict) -> bytes:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()


def assinar(payload: dict, segredo: bytes) -> str:
    return montar(para_json({"alg": "HS256", "typ": "JWT"}), para_json(payload), segredo)


def partes(token: str) -> tuple[dict, dict, bytes, str]:
    # Quebra o token e decodifica. Tudo o que der errado aqui (sem três partes, base64
    # torto, JSON torto) é ValueError por baixo, e vira TokenInvalido.
    # O último item é o que a assinatura cobre: as duas primeiras partes, como vieram.
    try:
        h64, p64, s64 = token.split(".")
        header, payload = json.loads(de_b64url(h64)), json.loads(de_b64url(p64))
        assinatura = de_b64url(s64)
    except ValueError as erro:
        raise TokenInvalido(f"token mal formado ({erro})") from None
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise TokenInvalido("token mal formado (header e payload são objetos JSON)")
    return header, payload, assinatura, f"{h64}.{p64}"


def verificar(token: str, segredo: bytes) -> dict:
    header, payload, assinatura, entrada = partes(token)
    # O verificador decide o algoritmo. O token não opina: o alg dele só pode confirmar.
    if header.get("alg") != "HS256":
        raise TokenInvalido(f"alg {header.get('alg')!r} recusado: aqui só entra HS256")
    esperada = hs256(entrada, segredo)
    # Comparação em tempo constante (lição 06), sobre bytes: com str, ela só aceita ASCII.
    # Ela não esconde o comprimento, e nem precisa: a assinatura HS256 sempre tem 32 bytes.
    if not hmac.compare_digest(esperada, assinatura):
        raise TokenInvalido("assinatura não confere")
    # Sem exp, o crachá valeria para sempre. Aqui, sem exp não entra.
    exp = payload.get("exp")
    if not isinstance(exp, int | float):
        raise TokenInvalido("sem exp")
    if exp <= time.time():
        raise TokenInvalido("vencido")
    return payload


def verificar_ingenua(token: str, segredo: bytes) -> dict:
    # NÃO faça isto. É o buraco histórico: o algoritmo vem do próprio token.
    header, payload, assinatura, entrada = partes(token)
    if header.get("alg") == "none":
        return payload  # "sem algoritmo, nada para conferir"
    if not hmac.compare_digest(hs256(entrada, segredo), assinatura):
        raise TokenInvalido("assinatura não confere")
    return payload


def secao(titulo: str) -> None:
    print()
    print(f"== {titulo} ==")


def tenta(nome: str, funcao, token: str, segredo: bytes) -> None:
    try:
        print(f"{nome}: aceitou {funcao(token, segredo)}")
    except TokenInvalido as erro:
        print(f"{nome}: recusou ({erro})")


# RFC 7515, apêndice A.1: os octetos exatos do header e do payload, copiados do RFC.
# O header tem um \r\n e um espaço no meio. Por isso eles não saem de um json.dumps:
# qualquer byte a mais ou a menos muda a assinatura.
RFC_HEADER = bytes(
    [123, 34, 116, 121, 112, 34, 58, 34, 74, 87, 84, 34, 44, 13, 10, 32,
     34, 97, 108, 103, 34, 58, 34, 72, 83, 50, 53, 54, 34, 125]
)  # fmt: skip
RFC_PAYLOAD = bytes(
    [123, 34, 105, 115, 115, 34, 58, 34, 106, 111, 101, 34, 44, 13, 10,
     32, 34, 101, 120, 112, 34, 58, 49, 51, 48, 48, 56, 49, 57, 51, 56,
     48, 44, 13, 10, 32, 34, 104, 116, 116, 112, 58, 47, 47, 101, 120, 97,
     109, 112, 108, 101, 46, 99, 111, 109, 47, 105, 115, 95, 114, 111,
     111, 116, 34, 58, 116, 114, 117, 101, 125]
)  # fmt: skip
# A chave do apêndice, no formato JWK: o campo "k" é a chave em base64url.
RFC_CHAVE = de_b64url(
    "AyM1SysPpbyDfgZld3umj1qzKObwVMkoqQ-EstJQLr_T-1qS0gZH75aKtMN3Yj0iPS4hcgUuTwjAzZr1Z9CAow"
)
RFC_TOKEN = (
    "eyJ0eXAiOiJKV1QiLA0KICJhbGciOiJIUzI1NiJ9"
    ".eyJpc3MiOiJqb2UiLA0KICJleHAiOjEzMDA4MTkzODAsDQogImh0dHA6Ly9leGFt"
    "cGxlLmNvbS9pc19yb290Ijp0cnVlfQ"
    ".dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
)


def main() -> None:
    secao("1. Conferir contra o RFC 7515 (apêndice A.1)")
    print(f"header  (bytes): {RFC_HEADER!r}")
    print(f"payload (bytes): {RFC_PAYLOAD!r}")
    print(f"chave: {len(RFC_CHAVE)} bytes")
    token_rfc = montar(RFC_HEADER, RFC_PAYLOAD, RFC_CHAVE)
    for nome, parte in zip(("header", "payload", "assinatura"), token_rfc.split(".")):
        print(f"{nome:<10} {parte}")
    print(f"confere com o RFC: {token_rfc == RFC_TOKEN}")

    secao("2. Emitir um crachá do FairFare de mentira")
    if "JWT_SEGREDO" in os.environ:
        print("segredo: lido de JWT_SEGREDO")
    else:
        print("AVISO: JWT_SEGREDO não definida; usando o padrão da bancada, que está no código")
    segredo = os.environ.get("JWT_SEGREDO", "segredo-de-bancada").encode()
    agora = int(time.time())
    token = assinar({"sub": "1", "nome": "Ana", "exp": agora + 3600}, segredo)
    print(f"token: {token}")
    for nome, parte in zip(("header", "payload", "assinatura"), token.split(".")):
        print(f"{nome:<10} {parte}")
    tenta("verificar", verificar, token, segredo)

    secao("3. Ler sem o segredo")
    h64, p64, s64 = token.split(".")
    print(f"header:  {de_b64url(h64).decode()}")
    print(f"payload: {de_b64url(p64).decode()}")
    print("Nenhuma chave foi usada. Assinado não é secreto.")

    secao("4. Adulterar o payload")
    falso = json.loads(de_b64url(p64)) | {"sub": "2"}
    adulterado = f"{h64}.{b64url(para_json(falso))}.{s64}"
    print(f"payload trocado: {para_json(falso).decode()} (a assinatura é a mesma de antes)")
    tenta("verificar", verificar, adulterado, segredo)

    secao('5. O alg "none"')
    sem_assinatura = (
        f"{b64url(para_json({'alg': 'none', 'typ': 'JWT'}))}.{b64url(para_json(falso))}."
    )
    print(f"token forjado, sem segredo nenhum: {sem_assinatura}")
    tenta("verificar_ingenua", verificar_ingenua, sem_assinatura, segredo)
    tenta("verificar        ", verificar, sem_assinatura, segredo)

    secao("6. O logout que não desloga")
    copia = token  # num log, num proxy, num notebook roubado...
    cliente = {"token": token}
    del cliente["token"]  # o "logout": o cliente esquece o token
    print(f"o cliente apagou o token: {cliente}")
    tenta("verificar a cópia", verificar, copia, segredo)
    exp = json.loads(de_b64url(p64))["exp"]
    print(f"e ela continua passando até o exp, {exp - agora} s depois da emissão")
    vencido = assinar({"sub": "1", "nome": "Ana", "exp": agora - 1}, segredo)
    tenta("verificar um token com exp no passado", verificar, vencido, segredo)


if __name__ == "__main__":
    main()
