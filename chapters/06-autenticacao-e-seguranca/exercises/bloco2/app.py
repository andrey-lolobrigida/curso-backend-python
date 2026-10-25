"""Bloco 2 — a porta dos fundos. (QUEBRADO DE PROPÓSITO)

Um FastAPI de bolso, tudo em memória: três crachás, um grupo e os saldos dele.
A Ana (1) e o Bruno (2) são do grupo 10. A Carla (3) tem crachá, e não é de grupo nenhum.
"""

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

TOKENS = {"tk-ana": 1, "tk-bruno": 2, "tk-carla": 3}
GRUPOS = {10: {1, 2}}
SALDOS = {(10, 1): "50.00", (10, 2): "-50.00"}

app = FastAPI()
bearer = HTTPBearer()


def quem_pede(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> int:
    user_id = TOKENS.get(cred.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="token inválido ou vencido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


@app.get("/grupos/{grupo_id}/saldos/{user_id}")
def saldo(grupo_id: int, user_id: int, eu: int = Depends(quem_pede)) -> dict:
    """O saldo de um membro do grupo.

    EXERCÍCIO 2: esta rota tem um defeito de propósito. Os testes mostram qual.
    """
    if user_id not in GRUPOS[grupo_id]:
        raise HTTPException(status_code=404, detail="saldo não existe")
    return {"user_id": user_id, "saldo": SALDOS[(grupo_id, user_id)]}
