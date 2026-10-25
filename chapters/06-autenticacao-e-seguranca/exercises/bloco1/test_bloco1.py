import statistics
import time

import pytest
from bloco1.login import LoginRecusado, entrar, hasher

# Os hashes saem do mesmo hasher do login.py: mesmos parâmetros, mesmo custo por verify.
USUARIOS = {
    "ana@example.com": hasher.hash("senha da ana"),
    "bruno@example.com": hasher.hash("senha do bruno"),
    "velho@example.com": None,  # conta de antes do cadastro com senha
}


def recusa(email: str, senha: str) -> str:
    """A mensagem com que o login recusa esse email e essa senha."""
    with pytest.raises(LoginRecusado) as exc:
        entrar(USUARIOS, email, senha)
    return str(exc.value)


def test_login_certo_passa():
    assert entrar(USUARIOS, "ana@example.com", "senha da ana") == "ok"


@pytest.mark.parametrize(
    "email, senha",
    [
        ("ninguem@example.com", "qualquer uma"),  # email que ninguém cadastrou
        ("velho@example.com", "qualquer uma"),  # conta sem senha
        ("ana@example.com", "senha errada"),  # senha errada
    ],
    ids=["inexistente", "sem senha", "senha errada"],
)
def test_mensagem_igual_para_os_tres_casos(email, senha):
    # A referência é a recusa de uma conta de verdade com a senha errada (o Bruno).
    # Qualquer diferença em relação a ela conta ao atacante em que caso ele está.
    referencia = recusa("bruno@example.com", "senha errada")
    assert recusa(email, senha) == referencia


def cronometra(email: str, senha: str) -> float:
    comeco = time.perf_counter()
    with pytest.raises(LoginRecusado):
        entrar(USUARIOS, email, senha)
    return time.perf_counter() - comeco


@pytest.mark.parametrize(
    "email_sem_hash",
    ["ninguem@example.com", "velho@example.com"],
    ids=["inexistente", "sem senha"],
)
def test_tempo_nao_denuncia_o_email(email_sem_hash):
    # Um email sem hash para conferir × a senha errada de uma conta de verdade.
    # 9 de cada, intercalados: o ruído da máquina se espalha pelos dois grupos por igual.
    sem_hash, senha_errada = [], []
    for _ in range(9):
        sem_hash.append(cronometra(email_sem_hash, "senha errada"))
        senha_errada.append(cronometra("ana@example.com", "senha errada"))
    m_sem_hash = statistics.median(sem_hash) * 1000
    m_senha_errada = statistics.median(senha_errada) * 1000
    assert m_sem_hash >= 0.5 * m_senha_errada, (
        f"{email_sem_hash} {m_sem_hash:.3f} ms × senha errada {m_senha_errada:.3f} ms"
    )
