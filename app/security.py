import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Os parâmetros padrão da biblioteca: argon2id, t=3, m=64 MiB, p=4 (lição 03).
# O hash que sai daqui carrega o algoritmo, os parâmetros e o sal: a coluna é uma só.
_hasher = PasswordHasher()


# Cada hash leva ~55 ms de conta pesada. Chamado direto na rota, ele para o event loop
# (cap. 2, lição 04). Numa thread o loop segue girando, e aqui a thread rende de verdade:
# o argon2 calcula em C e solta o GIL (cap. 2, lição 10), então os hashes rodam em paralelo.
async def hash_senha(senha: str) -> str:
    return await asyncio.to_thread(_hasher.hash, senha)


async def confere_senha(senha_hash: str, senha: str) -> bool:
    try:
        return await asyncio.to_thread(_hasher.verify, senha_hash, senha)
    except VerifyMismatchError:
        return False
