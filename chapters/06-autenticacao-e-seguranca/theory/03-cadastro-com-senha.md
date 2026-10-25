# Lição 03 — Cadastro com senha

A lição 02 montou sal e KDF à mão e terminou com um conselho: não escreva o seu. Agora o FairFare ganha senha de verdade, e quem faz a conta é uma biblioteca.

É a primeira lição do capítulo que muda o app: uma dependência, uma coluna, uma migração e o `app/security.py`.

## Não escreva o seu

O algoritmo é o **argon2**. Ele venceu a Password Hashing Competition de 2015, uma competição aberta para escolher o sucessor das KDFs antigas. A variante **argon2id** é a que o RFC 9106 recomenda para senha. A ideia é a do scrypt da lição 02: lento de propósito, caro em memória, com o custo num parâmetro.

A biblioteca é o **`argon2-cffi`**. O "cffi" do nome é o *C Foreign Function Interface*, o jeito de o Python chamar código C. É isso que o pacote faz: liga o Python à implementação de referência do argon2, que é em C. O Python não refaz a conta. Só a encomenda.

Por que essa, e não outra? Três motivos. Ela não reimplementa o algoritmo: usa o C de referência. Os parâmetros padrão dela são os recomendados pelo RFC 9106 (está no código dela: `profiles.RFC_9106_LOW_MEMORY`). E a API cabe numa mão: `hash` e `verify`. O bcrypt também é uma boa escolha. O argon2id é a recomendação de hoje.

```console
$ uv add argon2-cffi
Resolved 42 packages in 205ms
Installed 2 packages in 1ms
 + argon2-cffi==25.1.0
 + argon2-cffi-bindings==26.1.0
```

Vieram dois pacotes. O `argon2-cffi-bindings` é a parte compilada, o C. O `argon2-cffi` é a parte Python em cima dele.

## Lendo o hash

Num `uv run python`, o mesmo `segredo123` duas vezes. (Os três blocos desta seção são uma sessão só do REPL, copiada na ordem em que saiu.)

```pycon
>>> from argon2 import PasswordHasher
>>> ph = PasswordHasher()
>>> ph.hash("segredo123")
'$argon2id$v=19$m=65536,t=3,p=4$7Ep0N4GqWDDSkO80QRZFEQ$rfxXC5GkKrtHWGyMwwEml4NrQi4YnXoJ/JoS2RGjmrc'
>>> ph.hash("segredo123")
'$argon2id$v=19$m=65536,t=3,p=4$c/7eLySRPznKu632u2sErw$IqXptY4gTRKEpRXT8BewXcr+UYN0va9gR55yyAYdqjs'
```

Mesma senha, hashes diferentes. É o sal da lição 02, só que agora você não sorteou nada. A biblioteca sorteou.

E onde ele foi parar? Dentro da string. Ela tem cinco partes, separadas por `$`:

| Parte | No exemplo | O que é |
|---|---|---|
| algoritmo | `argon2id` | a variante do argon2 |
| versão | `v=19` | a versão do algoritmo (0x13) |
| parâmetros | `m=65536,t=3,p=4` | memória em KiB (64 MiB), passadas sobre ela, faixas em paralelo |
| sal | `7Ep0N4GqWDDSkO80QRZFEQ` | os 16 bytes aleatórios, em base64 |
| hash | `rfxXC5GkKr…` | os 32 bytes do resultado, em base64 |

Compare as duas linhas. As três primeiras partes são idênticas. Só o sal e o hash mudam.

É a promessa que a lição 02 deixou: **o hash do argon2 carrega o sal e os parâmetros dentro de si.** Na bancada, o sal morava numa variável ao lado. Aqui ele mora na própria string. Por isso o FairFare precisa de **uma coluna só**, `senha_hash`.

Conferir é o caminho de volta. O `verify` lê o sal e os parâmetros da string, refaz a conta com a senha que chegou e compara:

```pycon
>>> h = ph.hash("segredo123")
>>> ph.verify(h, "segredo123")
True
>>> ph.verify(h, "segredo124")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  ... (cinco linhas de dentro da biblioteca, cortadas aqui)
argon2.exceptions.VerifyMismatchError: The password does not match the supplied hash
```

Repare: senha errada não devolve `False`. Levanta exceção. Guarde isso, que vai aparecer no código.

E os parâmetros guardados resolvem um problema que a lição 02 deixou no ar: como subir o custo daqui a dois anos sem invalidar quem já tem conta? A resposta é o `check_needs_rehash`:

```pycon
>>> ph.check_needs_rehash(h)
False
>>> PasswordHasher(time_cost=4).check_needs_rehash(h)
True
```

Um `PasswordHasher` com `t=4` olha um hash feito com `t=3` e diz: este está velho. A senha só aparece em texto puro no login, então é ali que se refaz o hash, com o custo novo. Cada conta migra sozinha, no dia em que entra. O FairFare não faz isso ainda. Mas o formato já deixa a porta aberta.

## O app: `app/security.py`

```python
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
```

Duas funções, e a exceção vira `False` aqui dentro: quem chamar `confere_senha` não precisa saber dela.

## O hash fora do loop

A bancada desta lição começa medindo quanto custa um:

```bash
uv run python chapters/06-autenticacao-e-seguranca/bancada/argon2_no_loop.py
```

```console
== Ato 0: quanto custa um ==
hash: 56,7 ms (mediana de 15)
verify: 53,6 ms de relógio, 188,7 ms de CPU (mediana de 15)
```

Uns 55 ms. Para uma pessoa, nada. Para o event loop, uma eternidade. (A coluna da CPU volta daqui a pouco.)

O capítulo 2 explicou por quê: o loop é uma thread só, e enquanto uma corrotina faz conta sem `await`, ninguém mais anda (lição 04). Cinquenta e tantos milissegundos de conta numa rota `async` param o servidor para **todo mundo**.

Os atos seguintes medem isso. Oito logins chegam juntos e cada um faz um `verify`. Ao lado, uma corrotina "batimento" dorme 10 ms, acorda e anota quanto atrasou. Loop livre, ela acorda na hora. Loop preso, ela espera.

```console
== Ato 1: o verify no loop ==
8 verify: 520,6 ms no total
maior atraso do batimento: 510,4 ms

== Ato 2: o verify numa thread (asyncio.to_thread) ==
8 verify: 285,1 ms no total
maior atraso do batimento: 3,6 ms
```

No ato 1, o `verify` roda direto dentro da corrotina. O batimento ficou 510 ms sem acordar: as oito corrotinas rodaram em fila, sem soltar o loop nenhuma vez. Num servidor, seria um `GET /resources` esperando meio segundo por oito logins alheios.

No ato 2, o mesmo `verify` vai para uma thread. O loop segue girando, e o batimento atrasou 3,6 ms. (Em outras rodadas, deu 6,4, 10,7 e 16,3. Esse número dança. O do ato 1 também dança, mas fica em geral na casa das centenas de ms.)

E o total caiu para cerca da metade. Estranho: a lição 10 do capítulo 2 disse que thread não ajuda conta, porque o GIL deixa uma thread só executar Python por vez. O ato 3 é a prova:

```console
== Ato 3: o GIL ==
20 verify em sequência: 1201,6 ms
20 verify em 4 threads: 542,7 ms
```

Se o GIL ficasse preso, quatro threads levariam pelo menos o tempo da sequência. Foi cerca da metade. O motivo: o argon2 não roda em Python. Roda em C, e a biblioteca **solta o GIL** antes de começar a conta. O bytecode Python espera na fila. O C, não.

E por que não 4 vezes mais rápido? Volte ao ato 0: 53,6 ms de relógio para 188,7 ms de CPU. O `p=4` do hash já reparte um `verify` em quatro faixas paralelas, quase quatro núcleos por `verify`. Os oito do ato 2 viram 32 faixas disputando os 12 núcleos desta máquina. É por isso que eles levaram 285 ms, e não 55.

Então a regra do capítulo 2 ("threads servem para esperar, não para calcular") tem uma exceção honesta: thread serve para calcular **quando o cálculo é em C e solta o GIL**. Não é o caso de um laço Python. É o caso do argon2.

## E fora da transação

A rota de cadastro:

```python
@router.post("", status_code=201, response_model=UserMeOut)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # O hash vem antes do begin(): ~55 ms de conta sem segurar uma conexão do pool.
    senha_hash = await hash_senha(user.senha)
    # Sem service, quem diz o que é "uma operação" é o router (cap. 5, lição 08).
    try:
        async with db.begin():
            return await UserRepository(db).create(
                nome=user.nome, email=user.email, senha_hash=senha_hash
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail="email já cadastrado")
```

A ordem importa. O hash acontece **antes** de a rota encostar no banco. Durante os ~55 ms de conta, nenhuma conexão emprestada, nenhuma transação aberta. Só depois vem o `begin()` e o `INSERT`, que levam milissegundos.

Por quê? Lembre a lição 05 do capítulo 4: o pool empresta até 15 conexões por processo, e quando elas acabam, a request seguinte espera na fila. Conexão segurada enquanto a CPU calcula é vaga ocupada à toa. Cadastro é raro, e o estrago aqui seria pequeno. No login da lição 04, o cuidado vale mais.

## A migração: a coluna que nasce anulável

O model ganha uma linha:

```python
    # Anulável de propósito: os usuários de antes da lição 03 não têm senha, e não
    # existe senha para inventar para eles. Sem senha, não logam (lição 03).
    senha_hash: Mapped[str | None]
```

Por que `str | None`? Por que não obrigatória, como todo bom campo de senha?

Porque a tabela `users` não está vazia. O banco de dev daqui tem seis usuários de antes desta lição (o seu terá outro número). Veja o que acontece se a coluna nascer obrigatória:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare -c "ALTER TABLE users ADD COLUMN senha_hash varchar NOT NULL;"
ERROR:  column "senha_hash" of relation "users" contains null values
```

O Postgres recusa, e com razão: a coluna nova chega vazia nas seis linhas, e `NOT NULL` com seis nulos é contradição. Nada foi criado.

A saída de sempre seria um valor padrão. Só que aqui não existe valor honesto. Não dá para calcular o hash de uma senha que ninguém escolheu. E uma senha inventada pelo sistema é uma que ninguém sabe, ou pior, uma que alguém adivinha.

Então a coluna nasce anulável, e o autogenerate do Alembic gera exatamente isso:

```python
def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("users", sa.Column("senha_hash", sa.String(), nullable=True))
    # ### end Alembic commands ###
```

```console
$ uv run alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 2db1b72e440a -> 37f5e01d58df, usuarios ganham senha
$ uv run alembic check
...
No new upgrade operations detected.
```

Depois da migração e de um cadastro novo pela API (a Duda, com email próprio da demo):

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare -c "SELECT id, nome, senha_hash FROM users ORDER BY id;"
 id  |  nome   |                                            senha_hash
-----+---------+---------------------------------------------------------------------------------------------------
   1 | Semente |
   2 | Ana     |
   3 | Bruno   |
   4 | Carla   |
 265 | Ana     |
 266 | Bruno   |
 267 | Duda    | $argon2id$v=19$m=65536,t=3,p=4$KEVkTAW8lzvLNKvVADHrig$x+aG5Py2QzuVCx7gGmQghV4PzOSwBgFmPNrYQxAO7KY
(7 rows)
```

Seis antigos sem senha, e a Duda, com. E os seis? **Não logam.** Quando o login chegar, na lição 04, uma conta sem `senha_hash` simplesmente não tem como provar que é ela. É uma decisão, e fica declarada.

## O que nunca sai

O `senha_hash` não aparece em schema de resposta nenhum, nem no cadastro. Inútil para o cliente, valioso para quem ataca: é a linha que a lição 02 inteira tentou proteger.

E, de carona, o email também saiu da vitrine. Antes, `GET /users` listava o email de todo mundo para qualquer um. Agora são dois schemas:

```python
# O que qualquer um vê de um usuário. Sem email: o email é de quem é dono dele.
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str


# O que só o próprio usuário vê. O senha_hash não sai em schema de resposta nenhum.
class UserMeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
```

O `POST /users` devolve `UserMeOut`: quem acabou de se cadastrar vê o próprio email. O `GET /users` e o `GET /users/{id}` devolvem `UserOut`:

```console
$ curl -s localhost:8000/users/267
{"id":267,"nome":"Duda"}
```

O outro lugar onde o email volta a aparecer é o `GET /users/me`, na lição 05.

## A regra da senha

O `UserCreate` ganhou o campo:

```python
    # Teto folgado: nenhuma senha de gente passa de 128, e a norma permite um máximo (lição 03).
    senha: str = Field(min_length=8, max_length=128)
```

```console
$ curl -s -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{"nome": "Duda", "email": "duda.cap06@example.com", "senha": "1234567"}'
{"detail":[{"type":"string_too_short","loc":["body","senha"],"msg":"String should have at least 8 characters","input":"1234567","ctx":{"min_length":8}}]}
```

O piso de 8 vem da SP 800-63B, o guia de identidade digital do NIST (o instituto de padrões americano), na revisão 3. A revisão 4, de 2025, subiu para 15 quando a senha é o único fator de login, o caso do FairFare. O app fica no 8 por enquanto, e isso fica declarado. O teto de 128 é folgado: o guia pede aceitar pelo menos 64, e deixa o app fixar um máximo. Ele não está aí para poupar CPU. O argon2 resume a senha com um hash rápido antes de tudo, e o custo vem dos parâmetros, não do tamanho: medido aqui, o `verify` leva os mesmos ~60 ms com 8 caracteres e com 1 milhão. O teto é higiene de entrada. Ninguém digita 128 caracteres de senha, então o que passa disso não é senha de ninguém, e leva 422 antes de chegar perto do argon2 (o `test_senha_longa_demais_e_422` fixa isso).

E nada de "uma maiúscula, um número e um símbolo". O mesmo guia proíbe essas regras de composição: elas não deixam a senha mais forte, só mais previsível (`Senha123!`). O que protege é o comprimento. Por isso `pão de queijo quentinho` é uma senha melhor que `S3nh@123`.

Volte ao 422 do `1234567`: a senha recusada voltou no `input`. Falte outro campo, e ele traz o corpo inteiro, senha boa junto:

```console
$ curl -s -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{"email": "duda.cap06@example.com", "senha": "senha-boa-de-verdade"}'
{"detail":[{"type":"missing","loc":["body","nome"],"msg":"Field required","input":{"email":"duda.cap06@example.com","senha":"senha-boa-de-verdade"}}]}
```

A validação responde antes do banco: o email da Duda já existe, e não veio 409.

## O que fica declarado

- **Os usuários antigos do banco de dev (seis, aqui) ficam sem senha e não vão logar.** Não há senha honesta para inventar. Para usar o app, cadastre um usuário novo.
- **O email não é normalizado.** O validador do Pydantic baixa só o domínio: `Ana@Example.COM` vira `Ana@example.com`, e `ana@example.com` é outra conta. Tratar isso direito é mais difícil do que parece, e fica fora do curso.
- **O piso de 8 está abaixo do NIST de hoje.** A revisão 4 da SP 800-63B pede 15 quando a senha é o único fator. O FairFare segue no 8 da revisão 3.
- **Qualquer 422 do cadastro pode devolver a senha no `input`.** A recusada, e também a boa, quando falta outro campo. Volta só para quem a mandou, mas um proxy que grave o corpo das respostas em log a guardaria. O conserto é um handler de `RequestValidationError` que tira o `input`, sem dependência nova. Fica como está.
- **Não há recuperação nem troca de senha, verificação de email ou 2FA.** Cada um é um fluxo inteiro. Quem esquece a senha perde a conta.
- **Ainda não existe login.** O `confere_senha` está no `app/security.py`, mas ninguém o chama ainda. Ele entra em uso na lição 04.
- **Os números da bancada são desta máquina**, com 12 núcleos. Os seus vão ser outros. O que não muda é a distância entre o ato 1 e o ato 2.

## O que você deve conseguir fazer agora

- Pegar um hash argon2 e apontar o algoritmo, os parâmetros, o sal e o resultado.
- Explicar por que uma coluna só basta, e o que o `check_needs_rehash` permite.
- Explicar por que a coluna `senha_hash` é anulável, e o que isso custa aos usuários antigos.
- Dizer por que o hash roda numa thread **e** fora da transação: o que cada um protege.
- Explicar por que, no caso do argon2, as threads ganham do GIL.
