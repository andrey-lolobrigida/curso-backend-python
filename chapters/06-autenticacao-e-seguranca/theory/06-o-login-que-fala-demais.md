# Lição 06 — O login que fala demais

A lição 04 deixou o login respondendo igual, byte a byte, para quem não tem conta e para quem errou a senha. E deixou um aviso: o cronômetro conta o que a mensagem esconde. Esta lição mede isso e fecha a porta.

## Saber quem tem conta já é um ataque

Parece pouco. "Descobri que a Ana tem conta no FairFare." E daí?

E daí que essa é a primeira peça de três ataques:

- **Phishing sob medida.** Um email "FairFare: sua reserva foi cancelada, clique aqui" só engana quem usa o FairFare. Com a lista, o golpista não atira no escuro.
- **Força bruta com alvo.** Chutar senhas custa tentativas. Gastá-las em emails que nem existem é desperdício. Com a lista, toda tentativa vai numa conta de verdade.
- **Exposição.** Às vezes estar cadastrado já é a informação. Pense num app de clínica, de dívidas, de namoro. Num app de dividir conta, "o Bruno está nesse grupo de viagem" já é mais do que ele queria contar.

O nome disso é **enumeração de contas**: perguntar ao sistema, um email por vez, "esse aqui existe?". E o sistema responder.

## A forma óbvia

O jeito mais direto de responder é dizer com todas as letras. Este trecho **não** é código do FairFare, e não roda sozinho. É o login que a lição 04 evitou escrever:

```python
# NÃO é o código do repo: é a enumeração óbvia, com uma mensagem para cada caso.
if user is None:
    raise HTTPException(status_code=401, detail="email não cadastrado")
if not await confere_senha(user.senha_hash, senha):
    raise HTTPException(status_code=401, detail="senha incorreta")
```

Parece gentil. Mas o atacante manda uma senha qualquer com mil emails, e as respostas separam a lista em duas pilhas.

O FairFare nunca teve esse login: a mensagem é uma só, e o `test_login_recusado_e_sempre_igual` trava isso. Só que a mensagem é a metade fácil.

## A forma sutil, medida

Volte no código da lição 04, o que estava no repo até agora:

```python
        if user is None or user.senha_hash is None:
            raise InvalidCredentialsError
        if not await confere_senha(user.senha_hash, senha):
            raise InvalidCredentialsError
```

Duas saídas, a mesma exceção. Só que uma sai **antes** do argon2, e a outra sai **depois**. Se o email não existe, não tem hash para conferir, e o login cai fora na hora. Se o email existe, o login paga o `verify` do argon2 antes de dizer não.

É o código natural. Ninguém escreveu isso de propósito. Por que gastar um argon2 conferindo a senha de uma conta que não existe? Pois é exatamente esse "por que gastar" que vaza. E é por isso que esta lição existe: o vazamento não parece um bug quando você olha o código.

Para ver, o `bancada/enumeracao.py`. Ele cadastra um usuário da bancada, depois faz 30 logins com um email que ninguém cadastrou e 30 com o email da bancada e a senha errada, intercalados. Todos levam 401, com a mesma mensagem. O script cronometra cada um. Rodei contra o uvicorn **no commit da lição 05**, antes do conserto, no banco de dev:

```console
$ uv run python chapters/06-autenticacao-e-seguranca/bancada/enumeracao.py
usuário da bancada: bancada.cap06@example.com (cadastro: 409)
30 logins de cada, intercalados, todos 401:
  email inexistente  mediana    7,8 ms   mín    2,3 ms   máx    9,5 ms
  senha errada       mediana   94,0 ms   mín   45,4 ms   máx  106,9 ms
  diferença entre as medianas: 86,2 ms
  razão entre as medianas (senha errada / inexistente): 12,0x
```

Doze vezes. Mas olhe o mínimo e o máximo: o login **mais lento** de email inexistente (9,5 ms) foi mais rápido que o **mais rápido** de senha errada (45,4 ms). As duas faixas nem se encostam. O atacante não precisa de estatística. Uma request por email basta: acima de uns 30 ms, a conta existe.

Rodando de novo, a razão dança (deu 10,4, 11,8 e 11,6 em outras rodadas). Ela depende muito do quanto a máquina descansa entre uma request e outra. A diferença, não: uns 85 ms, que um lado paga e o outro não. É esse o número que denuncia.

E por que 85, se a lição 03 mediu o `verify` em uns 55? Lá era a conta sozinha, fora de request. Aqui o cronômetro pega o `verify` dentro de uma request de verdade: a ida e a volta da thread, as quatro pistas do argon2 (p=4) dividindo a CPU com o resto do processo, e uma CPU que estava descansando entre uma request e outra. A ida ao banco não entra na conta: os dois lados vão ao banco. Daqui em diante, o número é o da bancada: uns 85 ms.

O 409 da primeira linha é o cadastro dizendo que o usuário da bancada já existe. Guarde ele: volta no fim da lição.

## O hash fantasma

Se o problema é que um caminho pula o argon2, o conserto é não pular. Quando a conta não existe, o login confere a senha mesmo assim, contra um hash que não é de ninguém.

No `app/security.py`:

```python
# Um hash de verdade, de uma senha sorteada aqui e jogada fora: ninguém tem essa senha.
# O login confere contra ele quando a conta não existe, só para gastar o mesmo argon2 (lição 06).
HASH_FANTASMA = _hasher.hash(secrets.token_urlsafe(32))
```

E no `AuthService.login`:

```python
        if user is None or user.senha_hash is None:
            # Sem conta (ou sem senha), o argon2 roda mesmo assim, contra o hash fantasma:
            # o tempo não pode denunciar quem tem conta. O resultado não importa, e é descartado.
            await confere_senha(HASH_FANTASMA, senha)
            raise InvalidCredentialsError
```

Quatro detalhes, cada um com motivo:

- **É calculado uma vez, na importação.** O custo de um hash quando o app sobe, e nunca mais. Por request, só o `verify`, igual ao de uma conta de verdade.
- **Sai do mesmo `_hasher`.** Mesmos parâmetros (argon2id, t=3, m=64 MiB, p=4), então o `verify` contra ele custa o mesmo que contra o hash de qualquer usuário.
- **A senha é sorteada e jogada fora.** São 256 bits do `secrets`, como o token da lição 04, e ninguém guardou. Ninguém tem essa senha, por construção.
- **O resultado é descartado.** O login levanta `InvalidCredentialsError` de qualquer jeito, sem olhar o que o `confere_senha` devolveu. O fantasma serve para gastar tempo, e só.

A conta sem senha, dos usuários de antes da lição 03, cai no mesmo ramo. Ela também precisa demorar igual: senão o cronômetro denunciaria "essa conta existe, mas é antiga".

E por que não um `asyncio.sleep(0.085)` no lugar? Porque o sleep não acompanha o argon2. Numa máquina mais lenta, o `verify` demora mais e o sleep continua nos mesmos 85 ms. Com a CPU ocupada, o argon2 atrasa e o sleep não. Só o mesmo trabalho dá o mesmo tempo, com a mesma variação.

O preço: todo login recusado agora custa um argon2, de propósito. Quem limita quanto um IP pode gastar é o rate limiter da lição 05 do capítulo 3.

### O teste

O teste nasceu antes do conserto, em `tests/test_auth.py`. Um helper cronometra, e dois testes cobrem os dois ramos sem hash para conferir: o email que não existe e a conta sem senha.

```python
async def cronometra_logins(client, email_sem_hash):
    """7 logins com um email sem hash para conferir × 7 de senha errada, intercalados.

    Devolve as duas medianas. O ruído da máquina cai nos dois grupos por igual.
    1 cadastro + 7 + 7 logins = 15 requests, do mesmo IP: cabe nas 20 fichas do balde."""
    await cria_usuario(client, email="ana@example.com")
    sem_hash, senha_errada = [], []
    for _ in range(7):
        for tempos, email in ((sem_hash, email_sem_hash), (senha_errada, "ana@example.com")):
            comeco = time.perf_counter()
            resp = await client.post("/auth/login", json={"email": email, "senha": "outra-senha"})
            tempos.append(time.perf_counter() - comeco)
            assert resp.status_code == 401
    return statistics.median(sem_hash), statistics.median(senha_errada)


async def test_login_de_email_inexistente_demora_como_senha_errada(client):
    # A mensagem igual não basta: o cronômetro também não pode denunciar quem tem conta.
    inexistente, senha_errada = await cronometra_logins(client, "ninguem@example.com")
    # Folga de 2x: o argon2 dos dois lados oscila. Sem o hash fantasma, a razão dá ~0,03.
    assert inexistente >= 0.5 * senha_errada


async def test_login_de_conta_sem_senha_demora_como_senha_errada(client, engine_de_teste):
    # A conta de antes da lição 03 também não tem hash para conferir. Nem ela pode sair rápido.
    async with engine_de_teste.begin() as conn:
        await conn.execute(
            text("INSERT INTO users (nome, email) VALUES ('Velho', 'velho@example.com')")
        )
    sem_senha, senha_errada = await cronometra_logins(client, "velho@example.com")
    assert sem_senha >= 0.5 * senha_errada
```

Teste de tempo pode ficar intermitente. Por isso a folga é larga: o lado sem hash só precisa levar pelo menos metade do outro. Sem o fantasma, a razão fica em ~0,03, longe demais para passar por sorte. Com ele, deu entre 0,98 e 1,15 em seis medidas: longe demais para falhar por azar.

Com a linha do fantasma comentada, que é o login da lição 05, os dois ficam vermelhos:

```console
$ uv run pytest -q tests/test_auth.py -k demora
...
E       assert 0.002137552000931464 >= (0.5 * 0.07551614599651657)
...
E       assert 0.002354198004468344 >= (0.5 * 0.07394763099728152)
...
FAILED tests/test_auth.py::test_login_de_email_inexistente_demora_como_senha_errada
FAILED tests/test_auth.py::test_login_de_conta_sem_senha_demora_como_senha_errada
2 failed, 28 deselected in 1.43s
```

Uns 2 ms contra uns 75. Com a linha de volta, verde, e verde de novo: rodei os dois sozinhos 10 vezes, 10 de 10 passaram. A suíte foi a 107 testes.

### A bancada, depois

O mesmo script, contra o uvicorn com o conserto:

```console
$ uv run python chapters/06-autenticacao-e-seguranca/bancada/enumeracao.py
usuário da bancada: bancada.cap06@example.com (cadastro: 409)
30 logins de cada, intercalados, todos 401:
  email inexistente  mediana   88,3 ms   mín   49,9 ms   máx  109,6 ms
  senha errada       mediana   89,3 ms   mín   54,1 ms   máx  115,4 ms
  diferença entre as medianas: 1,0 ms
  razão entre as medianas (senha errada / inexistente): 1,0x
```

As duas faixas agora se sobrepõem quase inteiras. O vazamento de dezenas de ms fechou. Sobrou 1 ms, que some no ruído de uma request só, que vai de 50 a 110 ms. Igualar até o microssegundo não é a meta: a meta é que o tempo não separe mais as duas pilhas.

Quer ver o antes na sua máquina? Comente a linha `await confere_senha(HASH_FANTASMA, senha)` no `app/services/auth.py`, reinicie o uvicorn e rode a bancada de novo. Depois descomente. Enquanto ela estiver comentada, o `ruff` reclama do `HASH_FANTASMA` importado sem uso. É esperado.

## E o `hmac.compare_digest`?

Existe um parente desse ataque, bem mais miúdo: o **ataque de tempo na comparação de strings**.

Quando o Python faz `a == b` entre duas strings, ele compara do começo e para no primeiro caractere diferente. Um chute que acerta o primeiro caractere leva um tiquinho a mais que um que erra. São nanossegundos, mas com milhares de medidas, aparecem. E aí dá para descobrir o segredo um caractere por vez, como quem abre um cadeado ouvindo os cliques.

O `hmac.compare_digest(a, b)`, da biblioteca padrão, compara sem parar no meio: o tempo não depende de onde as duas diferem. Ele é necessário quando o **seu código Python** compara um segredo que veio na request com o valor esperado. Uma chave de API conferida com `==`. A assinatura HMAC de um webhook. A assinatura de um JWT, se for conferida na mão (a lição 08 abre um).

E o token do FairFare? Ele não é comparado em Python. O `get_current_user` manda o sha256 dele para o banco, que acha a sessão pelo índice da constraint `unique`. A comparação acontece no Postgres, sobre o hash, e não sobre o token. Descobrir o começo de um hash guardado não ajudaria ninguém. Para usá-lo, ele precisaria de um token cujo sha256 seja aquele, e o token são 256 bits de acaso.

E a senha? Ela vai para o `verify` do argon2, que já compara o hash calculado com o guardado em tempo constante, por dentro. Nenhum segredo do FairFare passa por um `==` em Python.

## As outras portas

O login não é a única porta. Há outras duas, abertas.

**O cadastro.** Tente cadastrar um email que já existe:

```console
$ curl -si -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{"nome": "Bancada", "email": "bancada.cap06@example.com", "senha": "a senha certa da bancada"}'
HTTP/1.1 409 Conflict
date: Sun, 25 Oct 2026 02:44:06 GMT
server: uvicorn
content-length: 33
content-type: application/json

{"detail":"email já cadastrado"}
```

É o mesmo "esse email existe?", respondido com todas as letras. O tempo aqui não vaza: o cadastro calcula o argon2 antes de tentar gravar, exista o email ou não. A mensagem vaza.

Fechar isso pede responder igual nos dois casos ("enviamos um email para confirmar") e avisar quem já tinha conta pelo email, não na tela. É **verificação por email**, fora deste capítulo.

**A listagem.** Qualquer pessoa logada faz `GET /users` e recebe todo mundo:

```console
$ curl -s localhost:8000/users -H "Authorization: Bearer $TOKEN"
[{"id":1,"nome":"Semente"},{"id":2,"nome":"Ana"},{"id":3,"nome":"Bruno"},{"id":4,"nome":"Carla"},{"id":265,"nome":"Ana"},{"id":266,"nome":"Bruno"},{"id":267,"nome":"Duda"},{"id":268,"nome":"Edu"},{"id":269,"nome":"Fê"},{"id":270,"nome":"Gabi"},{"id":271,"nome":"Bancada"}]
```

(O `$TOKEN` é o `access_token` de um login do usuário da bancada.) Sem email desde a lição 03, mas com id e nome de todo mundo. Hoje o app precisa dela: é por ela que se acha o id de quem adicionar num grupo. Trocar isso por convite também está fora do escopo do capítulo.

## O que fica declarado

- **O cadastro denuncia quem tem conta** com o `409 email já cadastrado`. Fechar pede verificação por email, fora do escopo.
- **O `GET /users` lista id e nome de todo mundo** para qualquer pessoa logada, enquanto o app depende dele para montar grupos. A lição 13 lista as duas portas.
- **Força bruta numa conta só continua possível.** O rate limiter conta por IP. Com muitos IPs, um atacante chuta senhas da mesma conta sem esvaziar balde nenhum. Limitar por conta pede estado compartilhado entre os processos do app: capítulo 7.
- **Cada tentativa de login custa caro, de propósito, inclusive a do email que não existe.** O fantasma faz toda tentativa pagar um `verify` inteiro: uns 200 ms de CPU, porque o `p=4` reparte o hash em quatro núcleos (lição 03). Isso é uma alavanca de negação de serviço. A 5 tentativas por segundo, a recarga do limitador, cada IP ocupa cerca de um núcleo, e uma dúzia de IPs ocupa uma máquina de 12 núcleos. O limitador conta por IP e não segura muitos IPs. Morre junto com a força bruta, no capítulo 7.

## O que você deve conseguir fazer agora

- Explicar por que mensagens de erro iguais não bastam contra a enumeração de contas.
- Rodar o `enumeracao.py` contra o uvicorn, antes (com a linha do fantasma comentada) e depois, e ler o resultado: por que a diferença entre as medianas, e o mínimo e o máximo, dizem mais que a razão.
- Explicar o hash fantasma: por que um hash de verdade, por que do mesmo `_hasher`, por que o resultado é descartado, e por que um `sleep` não serve no lugar.
- Dizer onde o `hmac.compare_digest` é necessário, e por que o token e a senha do FairFare não precisam dele.
