# Soluções — capítulo 6

Leia depois de tentar. Uma solução lida antes da tentativa vira informação; depois da tentativa, vira entendimento.

Cada bloco tem o que estava errado, o código consertado, **por que aquele conserto e não outro**, como você poderia ter chegado nele sozinho e a saída que você deve ver.

Todas as mensagens e todos os números daqui saíram de um terminal de verdade. Nenhum bloco usa banco, então não tem Postgres na história. Os seus tempos vão ser parecidos, não iguais. As contagens de testes devem bater.

---

## Bloco 1 — O login que fala demais

### O que estava errado

Dois defeitos, um em cima do outro.

O primeiro está no texto. São três recusas, e cada uma com a sua frase: `"email não cadastrado"`, `"conta sem senha"`, `"senha incorreta"`. É "a forma óbvia" da lição 06. Mil emails com uma senha qualquer, e as respostas separam a lista em pilhas.

O segundo está no caminho:

```python
    if email not in usuarios:
        raise LoginRecusado("email não cadastrado")
    senha_hash = usuarios[email]
    if senha_hash is None:
        raise LoginRecusado("conta sem senha")
    try:
        hasher.verify(senha_hash, senha)
```

Dois dos três caminhos saem **antes** do `verify`. Só a conta de verdade paga o argon2. É o "por que gastar?" da lição 06, com outras palavras.

E o segundo se esconde atrás do primeiro. Quem conserta a mensagem acha que acabou. Conserte só o texto, com a frase única nos três `raise`, e rode de novo. Medido:

```
E       AssertionError: ninguem@example.com 0.004 ms × senha errada 3.412 ms
...
E       AssertionError: velho@example.com 0.004 ms × senha errada 3.568 ms
...
2 failed, 4 passed in 0.11s
```

A mensagem ficou igual, e o cronômetro continua falando. É por isso que a mensagem única não bastava: ela fecha a boca do login, e não o relógio.

### O conserto

Em `bloco1/login.py`. O `secrets` entra no import, e duas constantes nascem perto do `hasher`:

```python
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

hasher = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1)

# Um hash de verdade, do mesmo hasher, de uma senha sorteada e jogada fora (lição 06).
HASH_FANTASMA = hasher.hash(secrets.token_urlsafe(32))
MENSAGEM = "email ou senha inválidos"


class LoginRecusado(Exception):
    pass


def entrar(usuarios: dict[str, str | None], email: str, senha: str) -> str:
    """Devolve "ok" se o email e a senha conferem. Senão, levanta LoginRecusado.

    EXERCÍCIO 1: esta função tem dois defeitos de propósito. Os testes mostram quais.
    """
    senha_hash = usuarios.get(email)
    if senha_hash is None:
        # Sem conta, ou conta sem senha: o argon2 roda mesmo assim, e o resultado é descartado.
        try:
            hasher.verify(HASH_FANTASMA, senha)
        except VerifyMismatchError:
            pass
        raise LoginRecusado(MENSAGEM)
    try:
        hasher.verify(senha_hash, senha)
    except VerifyMismatchError:
        raise LoginRecusado(MENSAGEM) from None
    return "ok"
```

É o `AuthService.login` da lição 06, de bolso. Uma frase só, a mesma do app. E um hash fantasma que sai do **mesmo** `hasher`, de uma senha que ninguém tem, calculado uma vez, na importação. O `verify` contra ele falha, porque ninguém tem aquela senha, e tanto faz: o resultado é jogado fora, e o login recusa de qualquer jeito.

### Por que esse, e não outro

**Por que `usuarios.get(email)`.** Uma linha junta os dois casos sem hash. Email que ninguém cadastrou dá `None`. Conta sem senha também dá `None`. Os dois caem no mesmo ramo, e os dois pagam o fantasma.

O enunciado pediu para explicar antes de consertar por que a conta sem senha também precisa demorar igual. Porque ela existe. Se ela sai rápido, o cronômetro diz "essa conta existe, mas é antiga". Ainda é saber quem tem conta. Veja o conserto pela metade, com o fantasma só para o email inexistente e a conta sem senha recusando na hora. Medido:

```
E       AssertionError: velho@example.com 0.004 ms × senha errada 3.749 ms
...
FAILED chapters/06-autenticacao-e-seguranca/exercises/bloco1/test_bloco1.py::test_tempo_nao_denuncia_o_email[sem senha]
1 failed, 5 passed in 0.16s
```

Quase mil vezes mais rápido, de novo. Só que agora para um tipo de conta só.

**O atalho que passa e não vale: o `sleep`.** Troque o `verify` do fantasma por um `time.sleep(0.004)`, "mais ou menos o que o verify leva". Medido: **10 de 10** verdes, `6 passed` em todas.

Passa porque o número foi afinado à mão para esta máquina e para estes parâmetros. A lição 06 disse o problema: o `sleep` não acompanha o argon2. Dá para ver acontecer. Troque o `hasher` do arquivo pelos padrões da biblioteca, `PasswordHasher()`, os mesmos do app. O teste usa o `hasher` do `login.py`, então ele inteiro passa a pagar o custo de verdade. Com o `sleep`, medido:

```
E       AssertionError: ninguem@example.com 4.091 ms × senha errada 73.517 ms
E       AssertionError: velho@example.com 4.098 ms × senha errada 71.758 ms
...
2 failed, 4 passed in 1.84s
```

O argon2 ficou umas vinte vezes mais caro. O `sleep` ficou onde estava. É o que acontece no dia em que alguém sobe o custo, troca de máquina ou o servidor fica ocupado. Com o fantasma, nos mesmos padrões, medido: `6 passed in 2.83s`, e de novo `6 passed in 2.65s`. O mesmo trabalho dá o mesmo tempo, porque **é** o mesmo trabalho.

**O limiar é de um lado só.** O teste pede `sem_hash >= 0.5 * senha_errada`. Ele proíbe o lado rápido, e só esse. É de propósito: o vazamento que o código natural produz é "rápido quer dizer sem conta", e é esse que ele pega, com folga larga para o ruído da máquina. Com o conserto de referência, a razão entre as medianas, medida em 50 rodadas de 9 + 9: de **0,98 a 1,02** para o email inexistente e de **0,97 a 1,03** para a conta sem senha. Longe demais do 0,5 para falhar por azar.

O preço é que o teste não pega o vazamento ao contrário. Um fantasma feito com **outro** hasher, digamos `PasswordHasher().hash(...)`, passa: `6 passed in 1.46s`, medido. Só que o `verify` do argon2 lê os parâmetros de dentro do hash, então quem não tem conta passa a pagar o argon2 padrão, e quem tem paga o barato. Medido em 50 rodadas: o lado sem conta ficou de **12 a 19 vezes mais lento**. O cronômetro denuncia do mesmo jeito, só que de cabeça para baixo. É por isso que a lição 06 insistiu: o fantasma sai do **mesmo** `_hasher`.

**Por que parâmetros baixos aqui, e os padrões no app.** São perguntas diferentes. O teste compara dois caminhos do mesmo `hasher`, e a comparação não depende do custo: o conserto passou com t=1 e com os padrões. Então o exercício escolhe o custo pelo que ele custa a **você**. Com t=1, m=8 MiB e p=1, o bloco leva uns 0,18 s. Com os padrões, 2,83 s por rodada, e o "pronto" pede dez.

No app, o custo é a própria defesa. A lição 02 mostrou o ataque: a tabela vaza, e alguém chuta senhas contra os hashes, offline, quanto quiser. Cada chute custa um argon2. Baixar o custo no app é baratear cada chute de quem roubou a tabela. Aqui, a tabela é um `dict` de três contas de mentira. Não tem senha de ninguém para proteger.

### Como chegar nele sozinho

Comece pela mensagem do teste de tempo: 0,004 ms contra 3,5 ms. Quatro milionésimos de segundo não dão tempo de fazer quase nada, muito menos de calcular um hash. Então o caminho rápido não faz conta nenhuma. Leia a função procurando onde cada caminho sai, e marque quais passam pelo `verify`. Dois saem antes.

Daí, a pergunta da lição 06: e se o caminho sem hash fizesse a mesma conta? Contra o quê, se não tem hash? Contra um hash que não é de ninguém. E o "do mesmo `hasher`" sai de olhar o que o `verify` faz: ele confere a senha com os parâmetros escritos dentro do hash.

### A saída que você deve ver

```console
$ uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco1 -v
...
chapters/06-autenticacao-e-seguranca/exercises/bloco1/test_bloco1.py::test_login_certo_passa PASSED [ 16%]
chapters/06-autenticacao-e-seguranca/exercises/bloco1/test_bloco1.py::test_mensagem_igual_para_os_tres_casos[inexistente] PASSED [ 33%]
chapters/06-autenticacao-e-seguranca/exercises/bloco1/test_bloco1.py::test_mensagem_igual_para_os_tres_casos[sem senha] PASSED [ 50%]
chapters/06-autenticacao-e-seguranca/exercises/bloco1/test_bloco1.py::test_mensagem_igual_para_os_tres_casos[senha errada] PASSED [ 66%]
chapters/06-autenticacao-e-seguranca/exercises/bloco1/test_bloco1.py::test_tempo_nao_denuncia_o_email[inexistente] PASSED [ 83%]
chapters/06-autenticacao-e-seguranca/exercises/bloco1/test_bloco1.py::test_tempo_nao_denuncia_o_email[sem senha] PASSED [100%]

============================== 6 passed in 0.17s ===============================
```

E as 10 seguidas:

```console
$ for i in $(seq 10); do uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco1 -q | tail -1; done
6 passed in 0.18s
6 passed in 0.17s
6 passed in 0.17s
6 passed in 0.18s
6 passed in 0.17s
6 passed in 0.17s
6 passed in 0.18s
6 passed in 0.18s
6 passed in 0.17s
6 passed in 0.17s
```

Medido: 10 de 10.

---

## Bloco 2 — A porta dos fundos

### O que estava errado

```python
@app.get("/grupos/{grupo_id}/saldos/{user_id}")
def saldo(grupo_id: int, user_id: int, eu: int = Depends(quem_pede)) -> dict:
    if user_id not in GRUPOS[grupo_id]:
        raise HTTPException(status_code=404, detail="saldo não existe")
    return {"user_id": user_id, "saldo": SALDOS[(grupo_id, user_id)]}
```

A rota confere se alguém é do grupo. Só que confere o **alvo**, o `user_id` da URL. A pergunta certa é sobre **quem pede**, o `eu`. E olhe o `eu`: ele chega por parâmetro, a dependência faz o trabalho dela direitinho, e ninguém lê o que ela devolveu. A rota sabe quem está pedindo e não pergunta nada a essa pessoa.

O alvo é escolhido por quem pede. É um número na URL. A Carla escreve `/grupos/10/saldos/1` e a rota confere "o 1 é do grupo 10?". É. Então `200`, e ela lê o saldo da Ana. É o BOLA da lição 11 de novo: o servidor confere uma coisa que o cliente escolheu, e não quem o cliente é.

O segundo defeito é o `GRUPOS[grupo_id]`. Com um grupo que não existe, o colchete estoura:

```
>       if user_id not in GRUPOS[grupo_id]:
E       KeyError: 999
```

No teste, o `ASGITransport` deixa a exceção subir até o pytest. Sob o uvicorn, ela vira resposta. Medido com o mesmo `ASGITransport`, só que com `raise_app_exceptions=False`, que faz o papel do servidor:

```
500 Internal Server Error
```

Um 500 para o grupo que não existe, e um 404 ou um 200 para o grupo que existe. A diferença já conta quais ids existem. E um 500 ainda acende o alarme de quem cuida do servidor, por uma request que só pediu um id errado.

### O conserto

Em `bloco2/app.py`, o corpo da rota:

```python
@app.get("/grupos/{grupo_id}/saldos/{user_id}")
def saldo(grupo_id: int, user_id: int, eu: int = Depends(quem_pede)) -> dict:
    """O saldo de um membro do grupo.

    EXERCÍCIO 2: esta rota tem um defeito de propósito. Os testes mostram qual.
    """
    membros = GRUPOS.get(grupo_id)
    # Primeiro "é seu?": quem pede é membro? De fora, o grupo não existe (lições 11 e 12).
    if membros is None or eu not in membros:
        raise HTTPException(status_code=404, detail="grupo não existe")
    # Só depois a pergunta sobre o alvo.
    if user_id not in membros:
        raise HTTPException(status_code=404, detail="saldo não existe")
    return {"user_id": user_id, "saldo": SALDOS[(grupo_id, user_id)]}
```

O `.get` troca o `KeyError` por `None`. E o `None` cai no **mesmo** `if` de quem é de fora, com a mesma frase.

### Por que esse, e não outro

**Por que 404, e não 403.** O critério da lição 11: 404 quando o simples "existe" já é informação que a pessoa não deveria ter. A Carla não é de grupo nenhum. Para ela, o grupo 10 não pode existir. Um 403 diria "existe, e não é seu". E aqui, como a lição 12 mostrou para os grupos do FairFare, o 404 esconde de verdade: nada mais conta à Carla que o grupo 10 existe.

**Por que o `KeyError` não era o defeito principal.** Conserte só ele, com o `.get` e um 404 para o grupo inexistente, e mantenha a pergunta sobre o alvo. Medido:

```
>       assert resp.status_code == 404
E       assert 200 == 404
...
E       AssertionError: assert {'detail': 'saldo não existe'} == {'detail': 'grupo não existe'}
...
2 failed, 3 passed in 0.19s
```

O 500 sumiu. A porta dos fundos continua aberta.

**Por que a ordem importa.** O atalho mais tentador é acrescentar a pergunta certa **depois** da errada:

```python
    membros = GRUPOS.get(grupo_id)
    if membros is None:
        raise HTTPException(status_code=404, detail="grupo não existe")
    if user_id not in membros:
        raise HTTPException(status_code=404, detail="saldo não existe")
    if eu not in membros:
        raise HTTPException(status_code=404, detail="grupo não existe")
```

Agora a Carla não lê o saldo da Ana. Mas medido:

```
E       AssertionError: assert {'detail': 'saldo não existe'} == {'detail': 'grupo não existe'}
...
FAILED chapters/06-autenticacao-e-seguranca/exercises/bloco2/test_bloco2.py::test_quem_nao_e_membro_recebe_404[alvo inexistente]
1 failed, 4 passed in 0.18s
```

A Carla pede o saldo do 99, que não é de ninguém, e ouve "saldo não existe". Essa frase quer dizer "o grupo existe, esse saldo é que não". A pergunta sobre o alvo respondeu antes da pergunta sobre ela, e contou o que a outra ia esconder. O enunciado chamou isso de o 403 da lição 11 com outra roupa, pelo que vaza. Pelo porquê, é o 409 da mesma lição: lá, o "já começou" respondia antes do "é seu?", e o 409 contava que a reserva existia.

A regra da lição 11 vale inteira: **toda checagem que pode revelar algo sobre o objeto vem depois da checagem de quem pede.** Primeiro "é seu?", depois qualquer outra coisa.

### Como chegar nele sozinho

Duas pistas no próprio código. A primeira: o parâmetro `eu` é recebido e nunca lido. Parâmetro que ninguém usa é um cheiro. Por que a rota pediu "quem é você?" se não ia usar a resposta?

A segunda: leia a URL e pergunte, para cada pedaço, quem escreveu. O `10` e o `1` vêm do cliente. O `eu` vem do token, conferido pela dependência. Toda decisão de permissão que só olha o que o cliente escreveu, o cliente decide.

Para a ordem, o caso `alvo inexistente` é o que ensina. Rode o seu conserto e veja qual frase a Carla ouve com o alvo 99. Se ela não for a mesma do grupo 999, alguma pergunta respondeu antes da hora.

### A saída que você deve ver

```console
$ uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco2 -v
...
chapters/06-autenticacao-e-seguranca/exercises/bloco2/test_bloco2.py::test_membro_ve_saldo_de_outro_membro PASSED [ 20%]
chapters/06-autenticacao-e-seguranca/exercises/bloco2/test_bloco2.py::test_quem_nao_e_membro_recebe_404[saldo da ana] PASSED [ 40%]
chapters/06-autenticacao-e-seguranca/exercises/bloco2/test_bloco2.py::test_quem_nao_e_membro_recebe_404[alvo inexistente] PASSED [ 60%]
chapters/06-autenticacao-e-seguranca/exercises/bloco2/test_bloco2.py::test_grupo_inexistente_e_404 PASSED [ 80%]
chapters/06-autenticacao-e-seguranca/exercises/bloco2/test_bloco2.py::test_sem_token_e_401 PASSED [100%]

============================== 5 passed in 0.18s ===============================
```

---

## Bloco 3 — O token que não morre

### O que estava errado

Dois defeitos, três testes vermelhos.

O `criar_sessao` grava o `expira_em`, e o `usuario_do_token` nunca olha para ele:

```python
    sessao = sessoes.get(token)
    if sessao is None:
        return None
    return sessao["user_id"]
```

A validade está na tabela, escrita. Ninguém a lê. Por isso, 25 horas depois do login:

```
E       AssertionError: assert 1 is None
```

E o teste da borda, que pede a hora cravada, leva a mesma mensagem. O crachá de 24 horas vale para sempre. É o que a lição 05 evitou ao nascer conferindo o `expira_em`: uma coluna que só é gravada não protege nada.

O outro defeito é a chave. `sessoes[token] = ...` guarda o crachá como ele é. O teste olha a tabela do jeito que um vazamento olharia, e acha o token lá dentro:

```
E       AssertionError: assert 'CoQA7OhPRsk-d461REx2QAas-bCHPRdCdd_cM5d2JXQ' not in {1, datetime.datetime(2030, 1, 2, 10, 0, tzinfo=datetime.timezone.utc), 'CoQA7OhPRsk-d461REx2QAas-bCHPRdCdd_cM5d2JXQ'}
```

(O token muda a cada rodada. O defeito, não.) Quem lê essa tabela cola a chave num header e entra. É o cenário da lição 04: o backup esquecido, o dump no lugar errado.

### O conserto

Em `bloco3/sessoes.py`. O `hashlib` entra no import, e nasce uma função:

```python
import hashlib
import secrets
from datetime import datetime, timedelta

VALIDADE = timedelta(hours=24)


def hash_token(token: str) -> str:
    # sha256 basta: ninguém chuta 256 bits aleatórios (lição 04).
    return hashlib.sha256(token.encode()).hexdigest()


def criar_sessao(sessoes: dict, user_id: int, agora: datetime) -> str:
    """Abre uma sessão e devolve o token, que vai para o cliente.

    EXERCÍCIO 3: este módulo tem dois defeitos de propósito. Os testes mostram quais.
    """
    token = secrets.token_urlsafe(32)
    sessoes[hash_token(token)] = {"user_id": user_id, "expira_em": agora + VALIDADE}
    return token


def usuario_do_token(sessoes: dict, token: str, agora: datetime) -> int | None:
    """O user_id dono do token, ou None se o token não vale."""
    sessao = sessoes.get(hash_token(token))
    # O mesmo critério do WHERE da lição 05: vale enquanto expira_em > agora.
    if sessao is None or sessao["expira_em"] <= agora:
        return None
    return sessao["user_id"]
```

As duas pontas passam pelo mesmo `hash_token`: grava pelo hash, busca pelo hash. O cliente continua levando o token. A tabela só conhece o sha256 dele, como a `sessions` do FairFare.

### Por que esse, e não outro

**Por que sha256 basta aqui.** A lição 02 tinha condenado o sha256 para guardar senha, e a lição 04 explicou por que ele volta: o problema nunca foi o sha256, foi o que se coloca dentro dele. Senha é escolhida por gente, e gente escolhe `senha123`. Chutar dá certo, e por isso a senha pede uma KDF lenta, que encarece cada chute. O token são 256 bits sorteados pelo `secrets`. Não existe token provável, nem dicionário. **A KDF lenta protege o que é chutável**, e o token não é.

E ainda tem o custo. O hash do token é calculado em toda request autenticada. Um argon2 por request seria tempo jogado fora, sem ganho nenhum.

**Por que nem daria para usar o argon2.** O argon2 sorteia um sal a cada hash. A lição 03 mostrou: mesma senha, hashes diferentes. Para a senha, é o que você quer. Para a chave de uma tabela, é o fim: o hash calculado no `usuario_do_token` nunca seria o mesmo gravado no `criar_sessao`, e o `sessoes.get` nunca acharia nada. Uma chave de busca precisa ser **determinística**: o mesmo token, o mesmo hash, sempre. O sha256 é. E o sal faz falta? Também não, pelo mesmo motivo da lição 04: dois tokens iguais não acontecem, e tabela pronta de 2^256 entradas não cabe no universo.

**Por que `.hexdigest()`.** Porque é o que o teste confere, e é o que a coluna `token_hash` do FairFare guarda: 64 caracteres hexadecimais. Um `.digest()` daria 32 bytes, e esconderia o token do mesmo jeito. Só que aí a sua tabela e a do app falariam línguas diferentes.

**Por que `<=`.** A lição 05 escreveu a validade no `WHERE` assim: `expira_em > now()`. Vale enquanto o vencimento está no futuro. O `<=` é o contrário exato disso: recusa quando o vencimento já chegou. Medido, com um login às 10h:

```
23:59:59 depois: 1
24:00:00 cravadas: None
```

Um segundo antes, entra. Na hora cravada, já não entra. Igual ao Postgres do app.

**Por que um teste na hora cravada.** O `test_token_vencido_e_recusado` adianta o relógio 25 horas. Com ele sozinho, `<` e `<=` passariam iguais: os dois recusam um token vencido há uma hora. A diferença mora num instante só, o das 24 horas cravadas, e é lá que o `test_token_vence_na_hora_cravada` olha. Troque o `<=` por `<` e rode:

```
>       assert usuario_do_token(sessoes, token, LOGIN + timedelta(hours=24)) is None
E       AssertionError: assert 1 is None
...
FAILED chapters/06-autenticacao-e-seguranca/exercises/bloco3/test_bloco3.py::test_token_vence_na_hora_cravada
1 failed, 4 passed in 0.02s
```

Com `<`, o crachá vale também no instante exato do vencimento, um instante a mais que o app. Não é um buraco que alguém explore. Mas o critério que você quer copiar é o da lição 05, e o teste da borda é o que sabe qual dos dois você copiou. Ele confere os dois lados: um segundo antes ainda entra, e na hora cravada já não entra.

**E o `agora` por parâmetro.** O módulo não chama `datetime.now()`. Quem decide que horas são é quem chama. É isso que deixa o teste do relógio mandar no relógio. A lição 07 resolveu o mesmo problema por outro lado: lá, quem decide é o `now()` do banco, que o teste não controla, e por isso o teste trazia o vencimento para o passado. Aqui o relógio é um parâmetro, e o teste o adianta.

### Como chegar nele sozinho

Para o primeiro: procure no módulo quem **lê** o `expira_em`. Um `grep` resolve. Ele aparece uma vez, no lado de quem grava. Toda coluna de segurança que só é gravada é uma promessa que ninguém cumpre.

Para o segundo: a mensagem do teste mostra a tabela inteira, e o token está nela, como chave. Pergunte o que a `sessions` do FairFare guarda no lugar do token. A lição 04 respondeu com um `psql` e um `sha256sum`: o hash, e só o hash.

### A saída que você deve ver

```console
$ uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco3 -v
...
chapters/06-autenticacao-e-seguranca/exercises/bloco3/test_bloco3.py::test_token_valido PASSED [ 20%]
chapters/06-autenticacao-e-seguranca/exercises/bloco3/test_bloco3.py::test_token_desconhecido PASSED [ 40%]
chapters/06-autenticacao-e-seguranca/exercises/bloco3/test_bloco3.py::test_token_vencido_e_recusado PASSED [ 60%]
chapters/06-autenticacao-e-seguranca/exercises/bloco3/test_bloco3.py::test_token_vence_na_hora_cravada PASSED [ 80%]
chapters/06-autenticacao-e-seguranca/exercises/bloco3/test_bloco3.py::test_tabela_nao_guarda_o_token PASSED [100%]

============================== 5 passed in 0.01s ===============================
```

---

## Bloco 4 (opcional) — O JWT que aceita qualquer um

### O que estava errado

```python
    if header.get("alg") == "none":
        return payload  # sem algoritmo, nada para conferir
```

É a `verificar_ingenua` da lição 08. O token diz como quer ser conferido, e o verificador obedece. Com `"none"`, não confere nada, e qualquer pessoa vira qualquer pessoa.

E tem um segundo jeito de ver o mesmo defeito, que o `mac-sha256` mostra. O header pede `HS512`, e a assinatura é HMAC-SHA256, feita com o segredo certo. O verificador nem olha o header nesse caminho: confere em HS256, bate, aceita. O token disse uma coisa e era outra, e passou. O `verificar` quebrado trata o `alg` como um pedido a ser atendido quando lhe convém, e ignorado quando não.

### O conserto

Em `bloco4/jwt.py`, o `verificar`:

```python
def verificar(token: str, segredo: bytes) -> dict:
    """Devolve o payload se o token vale. Senão, levanta ValueError.

    EXERCÍCIO 4: esta função tem um defeito de propósito. Os testes mostram qual.
    """
    h64, p64, s64 = token.split(".")
    header, payload = json.loads(de_b64url(h64)), json.loads(de_b64url(p64))
    # O verificador decide o algoritmo. O alg do header só pode confirmar (lição 08).
    if header.get("alg") != "HS256":
        raise ValueError(f"alg {header.get('alg')!r} recusado: aqui só entra HS256")
    if not hmac.compare_digest(hs256(f"{h64}.{p64}", segredo), de_b64url(s64)):
        raise ValueError("assinatura não confere")
    return payload
```

Uma linha muda de sentido. Antes: "se o token pede `none`, atenda". Agora: "se o token não diz exatamente o que eu já ia fazer, recuse". O algoritmo é do verificador, escolhido antes de o token chegar. O header só pode concordar. É a primeira checagem do `verificar` da bancada, só com o `ValueError` do exercício no lugar do `TokenInvalido`.

A comparação continua em `hmac.compare_digest`, sobre bytes, pelo motivo da lição 08: com `==`, a assinatura de um payload falso poderia ser montada byte a byte, medindo.

### Por que esse, e não outro

**Os dois atalhos.** O enunciado avisou dos dois, e os dois caem no mesmo lugar. Um é proibir só o `"none"`:

```python
    if header.get("alg") == "none":
        raise ValueError("alg 'none' recusado")
```

O outro é apagar o ramo do `"none"` e ignorar o header de vez. Os dois, medido:

```
E       Failed: DID NOT RAISE ValueError
FAILED chapters/06-autenticacao-e-seguranca/exercises/bloco4/test_bloco4.py::test_alg_inesperado_e_recusado[mac-sha256]
1 failed, 4 passed in 0.02s
```

O primeiro é a lista do que não pode. Ele fecha o buraco que você conhece, e só esse. Qualquer outro valor de `alg` segue em frente sem ninguém ter decidido o que fazer com ele. Aqui, ele cai no HMAC por acaso, e o `mac-sha256` mostra que "cair por acaso" aceita um token que mentiu. A lição 08 pediu a lista do que pode: uma entrada só, `HS256`.

**Mas o segundo atalho parece seguro.** E aqui, neste brinquedo, ele é. Sem ramo do `none`, a assinatura vazia não confere, e o forjado da lição 08 cai. Só existe um segredo e um algoritmo. Um token que diz `HS512` e confere em HS256 foi assinado com o segredo certo, então quem o fez tinha o segredo. Ignorar o header não vaza nada **hoje**.

O teste recusa mesmo assim, de propósito. O motivo aparece quando o verificador conhece mais de um tipo de chave, como as bibliotecas de verdade conhecem. A lição 08 citou o RS256 de passagem: um algoritmo de chave pública. Nele, o emissor assina com uma chave **privada**, que só ele tem, e quem confere usa a chave **pública**, que por definição qualquer um pode ver. É o que permite um serviço emitir crachás e dez outros conferirem sem ninguém mais ter o poder de emitir.

Agora imagine um verificador que aceita RS256 e HS256 e escolhe pelo header. O atacante pega a chave pública do servidor, que é pública. Escreve `"alg": "HS256"` no header. Assina o payload que quiser com HMAC, usando os bytes da chave pública como se fossem o segredo. O verificador lê o header, vai pelo caminho do HMAC e confere com a chave que ele tem guardada para aquele emissor: a mesma chave pública. A conta bate. Aceito.

Ninguém precisou de segredo. O atacante usou uma chave que o servidor deixa à vista de propósito, porque o token convenceu o servidor a usá-la para outra coisa. O nome disso é **confusão de algoritmo**, e é o mesmo defeito do `alg: none`: o token escolhendo como deve ser conferido. Por isso a regra da lição 08 não é "proíba o `none`". É "**o verificador decide o algoritmo**", e o `alg` do header pode, no máximo, confirmar. Num verificador de verdade, o algoritmo vem amarrado à chave: esta chave é RS256 e só RS256. Um header que discorda é um token que não é deste servidor.

O exercício não tem RSA, e não precisa. O hábito é o mesmo com um algoritmo ou com dez: o header que discorda é recusado, não ignorado. Ignorar parece inofensivo até o dia em que alguém acrescenta o segundo tipo de chave, e aí o verificador que "não ligava para o header" vira o que obedece a ele.

**Por que o `mac-sha512` já passava no quebrado.** Uma assinatura HMAC-SHA512 tem 64 bytes. O quebrado calcula a HS256, de 32, e o `compare_digest` responde que não bate. A recusa saiu certa, pelo motivo errado: ninguém olhou o header, foi a conta que não bateu. No `mac-sha256`, a conta bate, e é aí que o header mente sem ninguém perceber. Quem recusa tem de ser a regra, e não a sorte da conta.

### Como chegar nele sozinho

A pergunta da dica era "quem decide como o token é conferido?". Leia o `verificar` quebrado e procure de onde sai cada decisão. A do `if` sai do `header`. E o `header` sai do token. Então quem decide é o token, e o token é escrito por quem o manda.

Depois, a primeira checagem do `verificar` da bancada da lição 08. Ela já tem a resposta, com um comentário em cima. O exercício é perceber por que ela é um `!=`, e não um `==`.

### A saída que você deve ver

```console
$ uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco4 -v
...
chapters/06-autenticacao-e-seguranca/exercises/bloco4/test_bloco4.py::test_token_legitimo_passa PASSED [ 20%]
chapters/06-autenticacao-e-seguranca/exercises/bloco4/test_bloco4.py::test_assinatura_adulterada_e_recusada PASSED [ 40%]
chapters/06-autenticacao-e-seguranca/exercises/bloco4/test_bloco4.py::test_alg_none_e_recusado PASSED [ 60%]
chapters/06-autenticacao-e-seguranca/exercises/bloco4/test_bloco4.py::test_alg_inesperado_e_recusado[mac-sha256] PASSED [ 80%]
chapters/06-autenticacao-e-seguranca/exercises/bloco4/test_bloco4.py::test_alg_inesperado_e_recusado[mac-sha512] PASSED [100%]

============================== 5 passed in 0.01s ===============================
```

---

## O fio que costura os quatro blocos

Olhe o que cada defeito tinha em comum. Nos quatro, o servidor acreditou em algo que o cliente controla.

No bloco 1, acreditou que só a mensagem falava. O cliente escolhe o email, segura o cronômetro e mede quanto o servidor demora para dizer não. O tempo de resposta era uma resposta. O conserto fez o servidor gastar o mesmo trabalho nos dois caminhos, para o cronômetro não ter o que contar.

No bloco 2, acreditou no id do alvo. O `1` da URL foi escrito pela Carla, e a rota perguntou a ele, e não a ela, se podia. O conserto fez a rota perguntar primeiro a quem pede, que vem do token, e só depois olhar o que a URL diz.

No bloco 3, acreditou no token guardado. Qualquer token que um dia esteve na tabela valia para sempre, e a própria tabela guardava o crachá pronto para uso. O cliente que tem uma cópia velha, ou que leu a tabela, entrava. O conserto fez o servidor guardar só o que não serve de crachá e conferir, a cada request, se o crachá ainda vale.

No bloco 4, acreditou no `alg`. O token dizia como devia ser conferido, e o verificador obedecia. O conserto devolveu a decisão a quem confere.

A regra que sai daqui: **o que vem do cliente é uma alegação, não um fato.** O email, o id na URL, o token e o header do JWT chegam escritos por alguém que pode estar mentindo. O servidor só confia no que ele mesmo confere contra o que ele mesmo sabe: o trabalho do `hasher`, a lista de membros, o hash e a validade na tabela dele, o algoritmo que ele escolheu antes de o token chegar.

E repare que nenhum dos quatro fazia barulho no caso comum. A Ana loga, a Ana vê o saldo do Bruno, a sessão de ontem funciona, o token legítimo passa. Os defeitos só aparecem para quem testa a porta errada de propósito. É exatamente quem você precisa que não passe.
