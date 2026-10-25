from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import SessionRepository, UserRepository
from app.security import confere_senha, hash_token, novo_token


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
        # Email que não existe e conta sem senha (anterior à lição 03) caem fora ANTES do hash.
        # Isso responde mais rápido, e o tempo denuncia a conta: é a lição 06.
        if user is None or user.senha_hash is None:
            raise InvalidCredentialsError
        if not await confere_senha(user.senha_hash, senha):
            raise InvalidCredentialsError
        # 3. Outra transação curta para gravar a sessão. O banco guarda o hash, o cliente leva o token.
        token = novo_token()
        async with self.db.begin():
            await self.sessions.create(user.id, hash_token(token), agora=datetime.now(UTC))
        return token
