"""Bancada: gera uma chave privada e um certificado autoassinado para localhost.

Só para desenvolvimento. O certificado não tem cadeia até nenhuma autoridade que o
seu browser conheça — é ISSO que o aviso do browser está dizendo, e a lição 10 explica.

Rode:
  uv run python chapters/03-entre-o-cliente-e-o-router/bancada/certificado.py
Gera bancada/certs/chave.pem e bancada/certs/cert.pem (pasta gitignorada: chave privada não se commita).
Rodar de novo SOBRESCREVE os dois: o certificado anterior deixa de valer, e quem estava usando
--cacert cert.pem em algum terminal precisa apontar para o arquivo novo.
"""

import datetime as dt
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

DESTINO = Path(__file__).with_name("certs")
VALIDADE = dt.timedelta(days=30)


def main() -> None:
    DESTINO.mkdir(exist_ok=True)

    # 1. A chave: um par (privada + pública). A privada nunca sai desta máquina.
    chave = ec.generate_private_key(ec.SECP256R1())

    # 2. O certificado: a chave pública + para quem ela vale + quem assina. Aqui, nós mesmos.
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    agora = dt.datetime.now(dt.timezone.utc)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(nome)  # para quem é
        .issuer_name(nome)  # quem assina — o mesmo: "autoassinado"
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora)
        .not_valid_after(agora + VALIDADE)
        .add_extension(
            # Os nomes pelos quais o cliente pode chamar este servidor. É isto que o browser confere.
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(chave, hashes.SHA256())
    )

    (DESTINO / "chave.pem").write_bytes(
        chave.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    (DESTINO / "cert.pem").write_bytes(certificado.public_bytes(serialization.Encoding.PEM))
    print(
        f"gerados em {DESTINO}/: chave.pem (privada — não compartilhe) "
        f"e cert.pem (válido por {VALIDADE.days} dias). "
        f"Qualquer certificado gerado antes neste diretório foi sobrescrito."
    )


if __name__ == "__main__":
    main()
