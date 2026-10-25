# Capítulo 6 — Autenticação e segurança

Cinco capítulos inteiros, e o FairFare acreditava em tudo o que qualquer um dizia. Reservava quadra sem reserva dupla, dividia a conta sem perder centavo, quitava dívida com cadeado. E qualquer cliente lançava uma despesa de R$ 500 "paga pela Ana" sem ser a Ana.

Este capítulo ensina o app a fazer duas perguntas a cada request. **Quem é você?** E **você pode fazer isso?** São perguntas diferentes, com códigos diferentes, e a ordem importa. A primeira pede senha, login e um crachá que o cliente mostra a cada request. A segunda pede uma regra por rota: só o dono cancela a reserva, só o membro mexe no grupo, só quem recebe lança a quitação.

E cada passo tem uma armadilha com cara de detalhe. A senha que não se guarda, nem cifrada. O login que denuncia quem tem conta pelo cronômetro. O crachá que não morre. O JWT que aceita qualquer um. A reserva alheia que responde 403 e, com isso, conta que existe. Cada uma tem uma lição, e cada lição termina com a armadilha medida e fechada, ou declarada.

No fim, cai o último item da entrada 2 do `ERRATA.md`: o "sem autenticação" que nasceu no capítulo 1.

## Pré-requisitos

O capítulo 5 completo (ou `git checkout v-chapter-05`, `uv sync`), com o compose de pé e o banco no `head`:

```bash
uv sync
docker compose up -d --wait
uv run alembic upgrade head
```

**Uma dependência nova: `argon2-cffi`, a biblioteca que faz o hash das senhas** (lição 03). O `uv sync` a traz.

O `pytest` continua precisando do compose de pé, como desde a lição 03 do capítulo 4.

## As lições

Em ordem. Cada uma tem uma ideia só e termina com um checkpoint. São três partes: quem é você (01 a 07), sessão ou JWT (08 a 10) e o que você pode (11 e 12). A 13 fecha a conta.

| # | Lição | A ideia única |
|---|-------|---------------|
| 01 | [Duas perguntas, dois códigos](theory/01-duas-perguntas-dois-codigos.md) | Autenticação pergunta quem é você; autorização, o que você pode. Uma vem antes da outra, e cada uma tem o seu código |
| 02 | [Senha não se guarda](theory/02-senha-nao-se-guarda.md) | Texto puro, sha256, sal e a KDF lenta, na bancada: guarda-se o hash, e um hash feito para demorar |
| 03 | [Cadastro com senha](theory/03-cadastro-com-senha.md) | O argon2 numa thread e fora da transação, a coluna que nasce anulável, o hash que nunca sai |
| 04 | [O login e o token](theory/04-o-login-e-o-token.md) | O crachá são 256 bits de acaso, e o banco só guarda o sha256 dele, na tabela `sessions` |
| 05 | [A dependência que pergunta quem é você](theory/05-a-dependencia-que-pergunta-quem-e-voce.md) | Uma pergunta, um lugar: a `get_current_user` em toda rota, os dois 401, e o `user_id` sai do corpo |
| 06 | [O login que fala demais](theory/06-o-login-que-fala-demais.md) | Mensagem igual não basta: o cronômetro denuncia quem tem conta, e o hash fantasma o cala |
| 07 | [Revogar](theory/07-revogar.md) | Logout é apagar uma linha. A expiração se prova trazendo o vencimento para o passado |
| 08 | [JWT por dentro](theory/08-jwt-por-dentro.md) | Um JWT montado à mão, conferido contra o RFC, e o `alg: none` que aceita qualquer um |
| 09 | [Sessão ou JWT?](theory/09-sessao-ou-jwt.md) | Quem revoga um JWT, o refresh token, o OAuth2 como delegação, e por que o FairFare ficou com sessão |
| 10 | [Onde o crachá mora no browser](theory/10-onde-o-cracha-mora-no-browser.md) | Cookie ou header, CSRF ou XSS, e o `Authorization` que passa a pedir licença ao CORS |
| 11 | [O dono da reserva](theory/11-o-dono-da-reserva.md) | O BOLA, e por que a reserva alheia é 404, e não 403 |
| 12 | [Permissões por grupo](theory/12-permissoes-por-grupo.md) | Ser membro é a regra, checada no service. E quem ganha com a mentira não lança |
| 13 | [O que este código ainda não resolve](theory/13-o-que-ainda-nao-resolve.md) | O inventário das limitações declaradas, com o capítulo em que cada uma morre, e o "sem autenticação" riscado |

## Este capítulo se acompanha com um token na mão

O capítulo 4 se acompanhava com um `psql` aberto. O 5, contando consultas. Este se acompanha com um crachá.

Desde a lição 05, toda rota pede um, menos as duas que existem para quem ainda não tem: o cadastro e o login. Sem crachá, a resposta é esta:

```console
$ curl -i localhost:8000/bookings
HTTP/1.1 401 Unauthorized
date: Sun, 25 Oct 2026 02:19:12 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 30
content-type: application/json

{"detail":"Not authenticated"}
```

O caminho é sempre o mesmo, em três passos. Cadastre alguém com senha. Faça o login. Guarde o `access_token` que voltou. Na lição 04, o Edu:

```console
$ curl -s -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{"nome": "Edu", "email": "edu.cap06@example.com", "senha": "pão de queijo quentinho"}'
{"id":268,"nome":"Edu","email":"edu.cap06@example.com"}
$ curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' -d '{"email": "edu.cap06@example.com", "senha": "pão de queijo quentinho"}'
{"access_token":"6qWhYkeor3NOGcnJJbo1j9DDoixe0NzA2z3QBDlLr_M","token_type":"bearer"}
```

Daí em diante, todo `curl` leva o token no header. Por exemplo (troque o `<token>` pelo seu):

```bash
curl -s localhost:8000/users/me -H 'Authorization: Bearer <token>'
```

O `GET /users/me` responde quem você é, com o email. É o jeito mais curto de conferir que o crachá vale.

No Swagger, em `http://localhost:8000/docs`, o caminho é o mesmo. Faça o login pelo próprio Swagger, copie o `access_token`, clique em **Authorize** e cole só o token, sem a palavra `Bearer`. Daí em diante, o Swagger põe o header em toda request.

O crachá vale 24 horas, ou até o `POST /auth/logout` (lição 07). Depois disso, login de novo.

### Seus usuários antigos não logam

Os usuários que você criou antes da lição 03 não têm senha. A coluna `senha_hash` nasceu anulável, porque não há senha honesta para inventar para eles. E uma conta sem senha não tem como provar que é ela: **não loga.** No banco de dev do autor, seis contas ficaram assim. A lição 03 explica a decisão.

Para usar o app, **cadastre usuários novos**, com email novo. O email antigo continua ocupado: cadastrar de novo responde `409`.

O mesmo vale para o material dos capítulos anteriores. Os `curl` das lições dos capítulos 1 a 5 e as bancadas que chamam a API não mandam senha nem crachá. Na `main`, levam `401` ou `422`. A regra: **rode o material de um capítulo na tag dele** (`git checkout v-chapter-05`, por exemplo). A [entrada 5 do `ERRATA.md`](../../ERRATA.md#5-o-material-antigo-que-chama-a-api-para-de-funcionar-na-main) lista as bancadas atingidas e o `alembic downgrade` que cada tag pede.

## A bancada

A pasta [`bancada/`](bancada/) tem os instrumentos de medição do capítulo. **Nada dali faz parte do FairFare.** Eles montam à mão o que o app entrega a uma biblioteca, e alguns fazem errado de propósito. O [README dela](bancada/README.md) tem o comando de cada script.

| Script | Lição | O que mostra |
|---|---|---|
| `senhas.py` | 02 | quatro jeitos de guardar senha (texto puro, sha256, sha256 com sal, scrypt) e o ataque de dicionário contra cada um |
| `argon2_no_loop.py` | 03 | quanto custa um `hash` do argon2; o `verify` no loop × numa thread; e o argon2 soltando o GIL |
| `enumeracao.py` | 06 | 30 logins de email inexistente × 30 de senha errada, contra o app de verdade, e a diferença entre as medianas |
| `jwt_na_mao.py` | 08 | um JWT HS256 montado à mão e conferido contra o RFC; o payload adulterado; o `alg: none`; a cópia que sobrevive ao "logout" |

Três deles são só Python: não falam com o banco nem com o app, e não precisam do compose. **O `enumeracao.py` é a exceção.** Ele precisa do uvicorn de pé na porta 8000, e cria no banco de dev, uma vez só, o usuário `bancada.cap06@example.com`.

## Como percorrer

Cada lição corresponde a um commit, marcado com uma tag de nome previsível:

```bash
git log --oneline --reverse v-chapter-05..v-chapter-06   # os commits do capítulo
git tag -l "v-cap06-licao*"                              # as tags, uma por lição
```

Para ver o app num ponto específico do capítulo:

```bash
git checkout v-cap06-licao10         # o CORS com Authorization, antes de existir o dono da reserva
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Isso te coloca em **detached HEAD**. O git vai avisar com um parágrafo alarmado, e o [README do capítulo 1](../01-arquitetura-em-camadas/README.md#o-aviso-assustador-que-o-git-vai-te-dar) explica com calma o que isso significa e como voltar.

### O banco não viaja no tempo com você

O aviso dos capítulos 4 e 5 continua valendo, e este capítulo tem duas migrações novas. O `git checkout` troca o código. **Não troca o banco.** E o Alembic de uma tag antiga não tem os arquivos das migrações mais novas, então não sabe nem desfazê-las.

Por isso, **antes** do `checkout`, ainda no código mais novo, desça o banco até a migração da lição para onde você vai:

| Para ver as lições | O banco tem que estar em | O que a migração cria |
|---|---|---|
| 01 e 02 | `2db1b72e440a` (as quitações do capítulo 5) | nada novo: as duas lições não mexem no app |
| 03 | `37f5e01d58df` (usuários ganham senha) | a coluna `users.senha_hash` |
| 04 em diante | `100c03ec1ccf` (sessões), que é o `head` | a tabela `sessions` |

```bash
uv run alembic downgrade 37f5e01d58df   # ainda na chapter-06
git checkout v-cap06-licao03
```

**Descer apaga, e desta vez o preço é traiçoeiro.** Descer até `37f5e01d58df` derruba a tabela `sessions`: todo crachá emitido morre. Descer até `2db1b72e440a` derruba também a coluna `senha_hash`, e com ela **a senha de todo mundo.** Na volta, o `upgrade head` recria a coluna, vazia. Os usuários continuam lá, com nome e email, e nenhum deles loga mais. São usuários antigos, como os da seção acima: para usar o app, cadastre gente nova, com email novo.

Se o banco se enrolou, o caminho curto é o mesmo de antes, jogar fora e recomeçar:

```bash
docker compose down -v               # o -v apaga o volume: o banco de dev inteiro
docker compose up -d --wait
uv run alembic upgrade head
```

O `down -v` apaga tudo, inclusive as reservas e os grupos.

O `fairfare_test` tem a mesma pegadinha, e ela morde nas lições 01 a 03. A suíte recria as tabelas a cada rodada, mas só as que os models daquele commit conhecem. Antes da lição 04, eles não conhecem a `sessions`, e o `drop_all` tenta derrubar `users` com ela pendurada. Todo teste dá erro:

```
E           psycopg.errors.DependentObjectsStillExist: cannot drop table users because other objects depend on it
E           DETAIL:  constraint sessions_user_id_fkey on table sessions depends on table users
```

Antes de rodar a suíte num commit mais antigo, jogue o banco de teste fora. O `conftest.py` o recria na rodada seguinte:

```bash
docker compose exec postgres psql -U fairfare -d postgres -c 'DROP DATABASE fairfare_test'
```

## Os exercícios

Quatro blocos em [`exercises/`](exercises/README.md): o login que fala demais, a porta dos fundos, o token que não morre e o JWT que aceita qualquer um. O bloco 4 é **opcional**. Os três primeiros são o capítulo.

Todo código ali está **quebrado de propósito**, e o enunciado diz isso em letras garrafais.

```bash
uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco1 -v   # 4 falharam, 2 passaram
uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco2 -v   # 3 falharam, 2 passaram
uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco3 -v   # 3 falharam, 2 passaram
uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco4 -v   # 2 falharam, 3 passaram
```

Nenhum bloco importa `app/`, e nenhum usa banco: tudo mora em memória, num `dict`. Não precisa subir o compose. O bloco 1 tem um cuidado a mais: ele mede tempo, então o "pronto" é passar 10 vezes seguidas.

As soluções, com o raciocínio de cada conserto (por que a mensagem igual não bastava, quem decide o `alg`), estão em [SOLUTIONS.md](SOLUTIONS.md).

## Como rodar o app

```bash
uv sync
docker compose up -d --wait
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Documentação interativa em `http://localhost:8000/docs`, agora com o botão **Authorize** e um cadeado em cada rota protegida. E a rede de segurança:

```bash
uv run pytest
```

## O diff deste capítulo

Diffs são material de leitura neste curso. O capítulo inteiro, mudança a mudança: o `git log` acima, ou [a comparação no GitHub](https://github.com/andrey-lolobrigida/curso-backend-python/compare/v-chapter-05...v-chapter-06). Lá os commits vêm do mais novo para o mais antigo; leia de baixo para cima.

Desta vez, nenhum commit entrou pela `main` entre as duas tags: o capítulo partiu do próprio commit da `v-chapter-05`. Das lições, oito tocam `app/`:

- **Lição 03**: o `argon2-cffi` no `pyproject.toml`, o `app/security.py` com o hash numa thread, a coluna `senha_hash` no model e numa migração, e o cadastro pedindo senha.
- **Lição 04**: a tabela `sessions` no model e numa migração, o `SessionRepository`, o `AuthService.login` e o `POST /auth/login`.
- **Lição 05**: `app/dependencies.py`, com a `get_current_user`; o login exigido em todos os routers, menos o cadastro e o login; o `GET /users/me`; e o `user_id` saindo do `BookingCreate`.
- **Lição 06**: o `HASH_FANTASMA` em `app/security.py`, conferido pelo login quando não há hash de verdade para conferir.
- **Lição 07**: o `POST /auth/logout`, que apaga a sessão do token da request.
- **Lição 10**: `allow_headers=["Authorization"]` no `CORSMiddleware`, em `app/main.py`.
- **Lição 11**: o `cancel` recebe quem pede, e a reserva alheia responde `404`.
- **Lição 12**: o `is_member` no `GroupRepository`; os services de grupo, despesa e quitação recebendo quem pede; o `paid_by` e o `para_user_id` saindo dos schemas.

Repare no que **não** está na lista. As lições 01, 09 e 13 são só texto. A 02 e a 08 mexem só na bancada: a senha mal guardada e o JWT forjado são experimentos, e nenhum deles entra no código. O FairFare não usa JWT. Depois das lições vêm três commits que também não tocam `app/`: os exercícios, o `SOLUTIONS.md` e este README.

## Ao terminar

O FairFare sabe quem pede. Um usuário se cadastra com senha, faz login e recebe um crachá. Toda rota confere o crachá, e o crachá morre no logout ou em 24 horas. E o app sabe o que cada um pode: só o dono cancela a reserva, só o membro vê e mexe no grupo, a despesa é de quem lança e a quitação é lançada por quem recebe.

Sem inventar, item por item: a senha é guardada em argon2, calculada numa thread e fora da transação; o banco guarda o sha256 do token, e não o token; o login responde igual, na mensagem e no tempo, para quem não tem conta e para quem errou a senha; o vencimento da sessão é conferido pelo relógio do banco; recurso alheio é `404`, igual ao inexistente; e uma rota nova já nasce exigindo login, com um teste que lê o OpenAPI e cobra o `401` de cada uma. E **o "sem autenticação" morreu.** Era o item 3 da entrada 2 do `ERRATA.md`. Das três limitações herdadas do capítulo 1, não sobra nenhuma.

O resto do que fica de pé está na [lição 13](theory/13-o-que-ainda-nao-resolve.md), cada item com endereço: as sessões vencidas que se acumulam (capítulo 8), uma lista de decisões que não são defeitos, e o material antigo que só roda na tag dele.

E duas delas têm o mesmo endereço, porque têm a mesma raiz. **O saldo é recalculado a cada request**, e a soma pesa mais a cada despesa. **O limitador não enxerga os outros workers**: cada processo conta as próprias fichas, por IP, e não conhece conta nenhuma. Quem chuta a senha da Ana a partir de mil IPs tem mil baldes cheios. Os dois pedem a mesma coisa: um lugar, fora do processo, onde todos guardem e leiam o mesmo estado. É o capítulo 7.
