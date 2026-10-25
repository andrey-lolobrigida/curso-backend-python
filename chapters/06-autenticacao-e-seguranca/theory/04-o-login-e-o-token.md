# Lição 04 — O login e o token

Lá na lição 09 do capítulo 0 ficou uma promessa: depois do login, o servidor entrega um crachá, e o cliente o mostra a cada request. O HTTP não lembra de ninguém. Quem lembra é o cliente, repetindo a apresentação.

A lição 03 deu senha ao FairFare. Esta lição emite o crachá: `POST /auth/login`, um token, e uma tabela nova, `sessions`.

## O crachá na mão

Primeiro o resultado, depois o mecanismo. Pelo uvicorn, no banco de dev, um usuário novo da demo:

```console
$ curl -s -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{"nome": "Edu", "email": "edu.cap06@example.com", "senha": "pão de queijo quentinho"}'
{"id":268,"nome":"Edu","email":"edu.cap06@example.com"}
$ curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' -d '{"email": "edu.cap06@example.com", "senha": "pão de queijo quentinho"}'
{"access_token":"6qWhYkeor3NOGcnJJbo1j9DDoixe0NzA2z3QBDlLr_M","token_type":"bearer"}
```

O `access_token` é o crachá. O `token_type: "bearer"` diz que tipo de crachá ele é. *Bearer* quer dizer "portador": quem mostrar o token, entra. Não tem foto, não tem assinatura de quem o recebeu. Como um ingresso de show. Por isso ele não pode vazar.

Os dois campos têm esses nomes porque é o formato que o OAuth2 padronizou (RFC 6749), e os clientes já esperam por ele. O OAuth2 em si fica para a lição 09.

## Token opaco: nada dentro

Olhe o token de novo: `6qWhYkeor3NOGcnJJbo1j9DDoixe0NzA2z3QBDlLr_M`. Não tem id de usuário, não tem data, não tem nome. São 43 caracteres de acaso, e só.

É o que se chama de **token opaco**: o cliente não lê nada nele. Quem sabe o que ele significa é o servidor, que guardou numa tabela "este token é do Edu, e vale até amanhã". O token é o número do guarda-volumes. O casaco fica lá dentro.

(Existe o contrário: um token que carrega os dados dentro de si, assinado. É o JWT, que a lição 08 abre na bancada. O FairFare usa o opaco, e a lição 09 explica por quê.)

Quem fabrica o token é o `app/security.py`, que ganhou três peças:

```python
# Validade fixa, sem renovação: 24 horas depois do login, o crachá vence (lição 04).
VALIDADE_DA_SESSAO = timedelta(hours=24)


# 32 bytes do gerador do sistema operacional: 256 bits de acaso, e nada dentro.
# É o `secrets`, e não o `random`: o `random` é previsível para quem viu saídas dele.
def novo_token() -> str:
    return secrets.token_urlsafe(32)


# sha256 basta aqui, ao contrário da senha: ninguém chuta 256 bits aleatórios (lição 04).
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
```

O `secrets.token_urlsafe(32)` pega 32 bytes do gerador aleatório do sistema operacional (o mesmo do `os.urandom` da lição 02) e os escreve em **base64url**: o base64 com `-` e `_` no lugar de `+` e `/`, para caber numa URL ou num header sem escape. 32 bytes viram 43 caracteres.

E o `random`? Ele serve para sortear e simular, não para segredo. O gerador dele é determinístico: quem observa saídas suficientes reconstrói o estado e prevê as próximas. O `secrets` existe exatamente para isso não acontecer.

## A tabela `sessions`, e o que ela não guarda

Quando o login dá certo, o FairFare grava uma linha nova:

```python
class UserSession(Base):
    """Um login que deu certo. UserSession, e não Session, para não confundir com a AsyncSession."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # O sha256 do token, nunca o token: se a tabela vazar, os crachás não vazam (lição 04).
    token_hash: Mapped[str] = mapped_column(unique=True)
    # O repository grava o criada_em; o server_default é só rede de segurança.
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

O nome da classe é `UserSession` porque o código já tem uma `AsyncSession` em todo canto, e é a sessão do SQLAlchemy, outra coisa. A tabela continua `sessions`.

Repare na coluna: `token_hash`, e não `token`. Depois do login do Edu, no `psql`:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare -c "SELECT user_id, token_hash, criada_em, expira_em FROM sessions;"
 user_id |                            token_hash                            |           criada_em           |           expira_em
---------+------------------------------------------------------------------+-------------------------------+-------------------------------
     268 | b069591bd8a954e9d05dfc99dee8d41e09bf55888b00b5abc0f611e78cc61cea | 2026-10-25 01:59:47.062586+00 | 2026-10-26 01:59:47.062586+00
(1 row)
```

O token não está lá. Está o sha256 dele:

```console
$ echo -n '6qWhYkeor3NOGcnJJbo1j9DDoixe0NzA2z3QBDlLr_M' | sha256sum
b069591bd8a954e9d05dfc99dee8d41e09bf55888b00b5abc0f611e78cc61cea  -
```

Por quê? Pela mesma razão da lição 02: **imagine que a tabela vazou.** Um backup esquecido, um dump num lugar errado, uma injeção de SQL. Se ela guardasse o token puro, quem a pegou teria o crachá de todo mundo logado. Bastaria colar um deles num header e entrar como o Edu.

Com o hash, o vazamento entrega 64 caracteres hexadecimais por sessão, e nenhum serve de crachá. O servidor não aceita o hash: aceita o token, calcula o sha256 dele e procura a linha (é a lição 05). Para entrar, o atacante precisaria do token que gerou aquele hash.

### Mas a lição 02 não disse que sha256 é ruim?

Disse. Para **senha**. E aqui está o coração desta lição: o problema do sha256 nunca foi o sha256. Foi o que se coloca dentro dele.

O ataque da lição 02 não desfazia o hash. **Chutava**: calculava o sha256 de senhas prováveis até um bater. Funcionava porque senha é escolhida por gente. Gente escolhe `senha123`, `flamengo`, o nome do cachorro. O espaço de senhas prováveis é pequeno, e um dicionário de milhões de entradas cobre boa parte dele. A 3,9 milhões de sha256 por segundo, numa máquina só, um dicionário de um milhão leva um quarto de segundo. A KDF lenta existe para encarecer cada chute, porque chutar dá certo.

O token não foi escolhido por ninguém. São 256 bits sorteados. Não existe "token provável", não existe dicionário. Para achar o token pelo hash, só testando os 2^256 possíveis. Na mesma velocidade de 3,9 milhões por segundo, isso dá uns 9 × 10^62 anos. Uma placa de vídeo um bilhão de vezes mais rápida ainda deixa um número com mais de 50 dígitos de anos. O universo tem uns 14 bilhões.

A regra que sai daqui: **a KDF lenta protege o que é chutável.** Senha é chutável, então precisa de argon2. Token de 256 bits aleatórios não é, então um sha256 basta, e ainda é rápido, o que importa: o hash do token vai ser calculado em **toda** request autenticada, a partir da lição 05. Um argon2 de 55 ms por request seria um desastre sem ganho nenhum.

E o sal? Também não precisa. O sal da lição 02 matava duas coisas: hash igual para senha igual e tabela pronta. Dois tokens iguais não acontecem, e tabela pronta de 2^256 entradas não cabe no universo.

O `unique=True` cuida do resto. A migração desta lição, gerada pelo autogenerate, cria a tabela com `sa.UniqueConstraint("token_hash")`, e o Postgres monta um índice para garantir a unicidade. É esse índice que a busca da lição 05 vai usar.

## O login em três passos

O `AuthService`, novo:

```python
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
```

Três passos: buscar, conferir, gravar. O buscar e o gravar ficam cada um na sua transação curta. O conferir fica entre as duas, **fora** de qualquer transação. A lição 03 deixou o motivo: são uns 55 ms de conta, e conexão segurada enquanto a CPU calcula é vaga do pool ocupada à toa. No cadastro isso pesava pouco. No login, que é bem mais frequente, pesa mais.

O `user.senha_hash` continua legível depois do primeiro `begin()` terminar porque a sessão foi criada com `expire_on_commit=False`: o commit não apaga o que o objeto já trouxe.

E a conta sem senha, dos usuários de antes da lição 03, cai fora **antes** do `confere_senha`. Não é só educação. Chamado com `None`, o `verify` estoura `AttributeError: 'NoneType' object has no attribute 'encode'`, que o `confere_senha` não captura: viraria um 500. E a conta sem senha simplesmente não tem como provar quem é, como a lição 03 avisou.

Agora o recusado:

```console
$ curl -i -X POST localhost:8000/auth/login -H 'Content-Type: application/json' -d '{"email": "edu.cap06@example.com", "senha": "pão de queijo frio"}'
HTTP/1.1 401 Unauthorized
date: Sun, 25 Oct 2026 02:03:46 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 38
content-type: application/json

{"detail":"email ou senha inválidos"}
```

O 401 da lição 01, com o `www-authenticate: Bearer` dizendo como se apresentar. E a mensagem não diz **qual** dos dois estava errado. Um email que não existe leva a resposta idêntica:

```console
$ curl -i -X POST localhost:8000/auth/login -H 'Content-Type: application/json' -d '{"email": "ninguem.cap06@example.com", "senha": "pão de queijo frio"}'
HTTP/1.1 401 Unauthorized
date: Sun, 25 Oct 2026 02:03:46 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 38
content-type: application/json

{"detail":"email ou senha inválidos"}
```

Byte a byte, o mesmo corpo. Se o login respondesse "email não cadastrado", qualquer pessoa descobriria quem tem conta no FairFare, um email por vez. Os três casos (email inexistente, senha errada e conta sem senha) são o mesmo `InvalidCredentialsError`, e o `test_login_recusado_e_sempre_igual` fixa isso. Mas a mensagem igual é a metade fácil. A lição 06 mostra a outra metade.

O `LoginIn` passa o email pela mesma régua do cadastro:

```python
class LoginIn(BaseModel):
    # A mesma régua do cadastro: o EmailStr baixa o domínio aqui também, senão quem
    # digita igual nas duas telas não entra. O teto da senha também é o mesmo (lição 03).
    # Sem min_length: o login só confere a senha que chegou.
    email: EmailStr
    senha: str = Field(max_length=128)
```

Quem se cadastrou digitando `Fe.Cap06@Example.COM` loga digitando a mesma coisa. Os dois lados baixam o domínio, e o banco compara `Fe.Cap06@example.com` com `Fe.Cap06@example.com` (o `test_login_aceita_o_email_digitado_como_no_cadastro` trava isso). A parte antes do `@` continua sem normalização, como a lição 03 declarou. Um email mal formado leva 422, e isso não denuncia ninguém: o 422 diz que o texto não é um email, não se a conta existe. E a senha ganha o teto de 128 do cadastro, pelo mesmo motivo: o que passa disso não é senha de ninguém, e nem chega ao argon2.

## 24 horas, do mesmo relógio

O `SessionRepository.create` grava as duas datas:

```python
    async def create(self, user_id: int, token_hash: str, agora: datetime) -> UserSession:
        # criada_em e expira_em saem do mesmo relógio: a validade é exata, 24 h cravadas.
        sessao = UserSession(
            user_id=user_id,
            token_hash=token_hash,
            criada_em=agora,
            expira_em=agora + VALIDADE_DA_SESSAO,
        )
        self.db.add(sessao)
        await self.db.flush()
        return sessao
```

O `agora` vem do service, com fuso (`datetime.now(UTC)`, o hábito do capítulo 4). Se o `criada_em` ficasse com o `now()` do banco e o `expira_em` com o relógio do Python, a sessão valeria 24 horas mais ou menos uns milissegundos, e para mais ou para menos conforme a diferença entre os dois relógios. Do mesmo `agora`, a conta é exata. Olhe o `psql` lá em cima: `01:59:47.062586` e, no dia seguinte, `01:59:47.062586`. O `test_sessao_vale_24_horas` lê `expira_em - criada_em` do banco e exige `24:00:00` cravado.

A validade é fixa. Não renova a cada uso e não tem "lembrar de mim". Passadas 24 horas, faz login de novo.

E cada login cria uma sessão nova. Logar no celular e no notebook dá duas linhas e dois tokens, cada um com a sua validade (`test_dois_logins_duas_sessoes`).

## O que fica declarado

- **O token existe, mas nenhuma rota pede por ele.** Todas as rotas continuam abertas, e o `user_id` ainda vem do corpo. É a lição 05 que ensina o app a perguntar "quem é você?" e a conferir o `expira_em`. Por enquanto, a coluna só é gravada.
- **O login de email inexistente responde mais rápido que o de senha errada.** O primeiro cai fora sem argon2; o segundo paga os ~55 ms. A mensagem é igual, mas o cronômetro denuncia quem tem conta. A lição 06 mede isso e conserta.
- **O 422 do login devolve a senha no `input`, e aqui ela é a de verdade.** É o 422 da lição 03, só que pior: no cadastro, a senha ainda não abria conta nenhuma. Um cliente que mande `mail` no lugar de `email` recebe de volta a senha da conta:

  ```console
  $ curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' -d '{"mail": "edu.cap06@example.com", "senha": "pão de queijo quentinho"}'
  {"detail":[{"type":"missing","loc":["body","email"],"msg":"Field required","input":{"mail":"edu.cap06@example.com","senha":"pão de queijo quentinho"}}]}
  ```

  O conserto é o mesmo handler de `RequestValidationError` da lição 03. Fica como está.
- **As sessões vencidas vão se acumular na tabela.** Nada apaga as linhas velhas. O logout, que apaga a sua, é a lição 07. A limpeza das vencidas é um job em segundo plano, do capítulo 8.

## O que você deve conseguir fazer agora

- Explicar por que sha256 serve para guardar o token e não serve para guardar a senha.
- Dizer o que um vazamento da tabela `sessions` entrega ao atacante, e o que não entrega.
- Desenhar os três passos do login, dizendo o que roda dentro de transação e o que roda fora.
- Explicar por que o token vem do `secrets`, e não do `random`.
- Dizer por que `criada_em` e `expira_em` saem do mesmo `agora`.
