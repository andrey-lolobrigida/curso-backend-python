from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import SessionRepository, UserRepository
from app.security import HASH_FANTASMA, confere_senha, hash_token, novo_token


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)

    async def login(self, email: str, senha: str) -> str:
        # 1. Uma transação curta só para achar o usuário.
        async with self.db.begin():
            user = await self.users.get_by_email(email)
        # 2. O argon2 fora de transação: ~55 ms de conta sem segurar conexão do pool (lição 03).
        if user is None or user.senha_hash is None:
            # Sem conta (ou sem senha), o argon2 roda mesmo assim, contra o hash fantasma:
            # o tempo não pode denunciar quem tem conta. O resultado não importa, e é descartado.
            await confere_senha(HASH_FANTASMA, senha)
            raise InvalidCredentialsError
        if not await confere_senha(user.senha_hash, senha):
            raise InvalidCredentialsError
        # 3. Outra transação curta para gravar a sessão. O banco guarda o hash, o cliente leva o token.
        token = novo_token()
        async with self.db.begin():
            await self.sessions.create(user.id, hash_token(token), agora=datetime.now(UTC))
        return token

    async def logout(self, token: str) -> None:
        # Uma transação, um DELETE. A sessão mora no servidor, então revogar é esquecê-la.
        async with self.db.begin():
            await self.sessions.delete_by_token_hash(hash_token(token))
