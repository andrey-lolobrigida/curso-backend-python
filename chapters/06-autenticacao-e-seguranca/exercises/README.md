# Exercícios do capítulo 6

**Aviso, porque isto importa: todo código desta pasta está quebrado de propósito.**

O FairFare, em `app/`, não tem defeito escondido: o que ele ainda não resolve está declarado na lição 13. O que você encontrar de errado lá fora disso vale um issue. O que está *aqui* foi escrito errado de caso pensado, para você consertar.

Cada bloco tem testes que você mesmo roda. O teste é a definição de "pronto": enquanto ele estiver vermelho, o exercício não acabou.

Nenhum destes testes é coletado pelo `uv run pytest` do projeto (o `testpaths` do `pyproject.toml` cuida disso). Você roda cada bloco apontando o caminho.

Os blocos são **autocontidos**: nenhum deles importa `app/`, e nenhum usa banco. Tudo mora em memória, num `dict`. Não precisa subir o Postgres. O `exercises/conftest.py` não tem fixture nenhuma: ele existe para o pytest pôr a pasta `exercises/` no caminho de importação, e é por isso que o `from bloco1.login import entrar` funciona.

O bloco 4 é **opcional**. Os três primeiros são o capítulo. O quarto é para quem quer ver o JWT da lição 08 quebrar por dentro.

---

## Bloco 1 — O login que fala demais

**Arquivo:** `bloco1/login.py` — **quebrado de propósito.**

```bash
uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco1 -v
```

Estado inicial: **4 falharam, 2 passaram.**

Um login de bolso. A tabela de usuários é um `dict` de email para hash argon2. Uma conta antiga, de antes do cadastro com senha, aparece com o hash `None`. A função `entrar` devolve `"ok"` ou levanta `LoginRecusado`.

O `hasher` do arquivo usa parâmetros baixos (t=1, m=8 MiB, p=1), para o teste rodar em décimos de segundo. É só para o exercício. No app, quem manda são os padrões da biblioteca (lição 03).

São dois defeitos. O primeiro aparece no texto da recusa. O teste compara cada caso com a recusa de uma conta de verdade com a senha errada:

```
E       AssertionError: assert 'email não cadastrado' == 'senha incorreta'
...
E       AssertionError: assert 'conta sem senha' == 'senha incorreta'
```

Esse é o fácil. A lição 06 chamou de "a forma óbvia". O segundo aparece no cronômetro. O teste faz 9 logins com um email sem hash para conferir e 9 com a senha errada de uma conta de verdade, intercalados, e compara as medianas. Ele roda duas vezes: com um email que ninguém cadastrou e com a conta sem senha. Na máquina do autor:

```
E       AssertionError: ninguem@example.com 0.003 ms × senha errada 3.407 ms
...
E       AssertionError: velho@example.com 0.004 ms × senha errada 3.379 ms
```

Quase mil vezes, nos dois. E repare: com a mensagem já consertada, esses dois continuam vermelhos.

A dica: a lição 06 ("A forma sutil, medida"). Olhe os dois caminhos da função e pergunte o que um deles faz que o outro pula. E pergunte de novo, com a pergunta que a lição fez: "por que gastar?".

**Pronto quando:** os 6 testes do bloco passam **10 vezes seguidas**:

```bash
for i in $(seq 10); do uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco1 -q | tail -1; done
```

Sem `time.sleep`: a lição 06 explicou por que um `sleep` não acompanha o argon2. O conserto precisa cobrir os dois casos sem hash: um que cuide só do email inexistente deixa o `sem senha` vermelho. Antes de consertar, explique por que a conta sem senha também precisa demorar igual.

---

## Bloco 2 — A porta dos fundos

**Arquivo:** `bloco2/app.py` — **quebrado de propósito.**

```bash
uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco2 -v
```

Estado inicial: **3 falharam, 2 passaram.**

Um FastAPI de bolso, tudo em memória. Três crachás: `tk-ana`, `tk-bruno` e `tk-carla`. Um grupo, o 10, com a Ana e o Bruno. A Carla tem crachá, e não é de grupo nenhum. A rota `GET /grupos/{grupo_id}/saldos/{user_id}` devolve o saldo de um membro. Os testes falam com o app pelo `ASGITransport`, como os do projeto.

A dependência `quem_pede` está certa: sem crachá, 401. A rota até confere se alguém é do grupo. Só que a Carla, de fora, pede o saldo da Ana:

```
E       assert 200 == 404
```

`200`. A Carla lê o saldo de um grupo do qual não faz parte. Bastou saber o número do grupo e o id da Ana.

O mesmo teste roda de novo com a Carla pedindo um id que não é de ninguém, `/grupos/10/saldos/99`. Ela leva 404, mas com outra frase:

```
E       AssertionError: assert {'detail': 'saldo não existe'} == {'detail': 'grupo não existe'}
```

"Saldo não existe" quer dizer "o grupo existe, esse saldo é que não". É o 403 da lição 11 com outra roupa: um código diferente, ou uma frase diferente, conta a mesma coisa.

O outro teste pede o grupo 999, que não existe, e nem chega a ver uma resposta:

```
>       if user_id not in GRUPOS[grupo_id]:
E       KeyError: 999
```

Sob o uvicorn, isso seria um 500. No teste, o `ASGITransport` deixa a exceção subir até o pytest, e é ela que você vê.

A dica: a lição 11 ("Onde mora a checagem, e por que a ordem importa") e a lição 12 ("Ser membro é a regra"). A rota confere se **uma** pessoa é do grupo. Qual? E qual delas a lição 12 mandou conferir primeiro?

**Pronto quando:** os 5 testes do bloco passam. Quem é de fora e quem pede um grupo que não existe ouvem a mesma frase, `{"detail": "grupo não existe"}`, com o critério da lição 11: qualquer diferença contaria à Carla que o grupo 10 existe. A ordem conta: um conserto que confere o alvo antes de conferir quem pede deixa o caso `alvo inexistente` vermelho.

---

## Bloco 3 — O token que não morre

**Arquivo:** `bloco3/sessoes.py` — **quebrado de propósito.**

```bash
uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco3 -v
```

Estado inicial: **3 falharam, 2 passaram.**

A tabela `sessions` da lição 04, de bolso: um `dict`. O `criar_sessao` sorteia um token, grava a sessão com 24 horas de validade e devolve o token. O `usuario_do_token` diz de quem é o token, ou `None`. Quem chama passa o `agora`, e é assim que o teste adianta o relógio sem esperar um dia.

Dois defeitos, três testes vermelhos. O primeiro defeito acende dois. Vinte e cinco horas depois do login, o crachá de 24 horas ainda entra:

```
E       AssertionError: assert 1 is None
```

E na hora cravada, 24 horas depois do login, também. O teste da borda leva a mesma mensagem, só que na linha do `LOGIN + timedelta(hours=24)`.

O segundo: o teste olha a tabela do jeito que um vazamento olharia, chave por chave, valor por valor. E acha o crachá lá dentro:

```
E       AssertionError: assert 'SllUBG0E62NAoJx8Io7lK93ahmTqwMHctA5iKy4UwMA' not in {1, datetime.datetime(2030, 1, 2, 10, 0, tzinfo=datetime.timezone.utc), 'SllUBG0E62NAoJx8Io7lK93ahmTqwMHctA5iKy4UwMA'}
```

O token muda a cada rodada. O defeito, não: quem lê essa tabela sai dela com um crachá que funciona.

A dica: a lição 04 ("A tabela `sessions`, e o que ela não guarda") e a lição 07 ("Expiração: o teste do relógio"). A coluna `expira_em` está sendo gravada. Quem lê ela?

**Pronto quando:** os 5 testes do bloco passam. A borda conta: um segundo antes das 24 horas o token ainda vale, e na hora cravada já não vale, o mesmo `expira_em > now()` da lição 05. A chave da tabela é o sha256 do token, em hexadecimal, como na lição 04: é exatamente isso que o teste confere. O `agora` continua vindo por parâmetro: nada de `datetime.now()` dentro do módulo, senão o teste do relógio deixa de mandar no relógio.

---

## Bloco 4 (opcional) — O JWT que aceita qualquer um

**Arquivo:** `bloco4/jwt.py` — **quebrado de propósito.**

```bash
uv run pytest chapters/06-autenticacao-e-seguranca/exercises/bloco4 -v
```

Estado inicial: **2 falharam, 3 passaram.**

O JWT HS256 da bancada da lição 08, com a biblioteca padrão e nada mais. O `assinar` está certo. O `verificar` devolve o payload, ou levanta `ValueError`. Para o exercício ficar numa ideia só, aqui não tem `exp`.

O teste monta o token forjado da lição 08: header `{"alg":"none"}`, o payload que quiser, e nada depois do último ponto. Nenhum segredo foi usado. E o verificador aceita:

```
E       Failed: DID NOT RAISE ValueError
```

O `test_alg_inesperado_e_recusado` roda duas vezes, sempre com um header que pede `HS512` e uma assinatura feita com o segredo certo. No `mac-sha512`, a assinatura é mesmo HMAC-SHA512, e o verificador quebrado já recusa: ele confere em HS256, e não bate. No `mac-sha256`, o header diz `HS512` e a assinatura é HMAC-SHA256. E o verificador aceita:

```
E       Failed: DID NOT RAISE ValueError
```

A assinatura confere, então qual é o problema? O token disse uma coisa e era outra. O verificador fingiu que não ouviu e seguiu em frente. A lição 08 foi clara: o `alg` do header pode, no máximo, **confirmar** o que o servidor já esperava. Um header que pede outro algoritmo é um token que não é deste servidor.

E leia o comentário do `test_assinatura_adulterada_e_recusada`: ele conta por que "trocar uma letra da assinatura" é um jeito traiçoeiro de testar adulteração.

A dica: a lição 08 ("O buraco histórico: `alg: none`"). Quem decide como o token é conferido?

**Pronto quando:** os 5 testes do bloco passam, e a comparação da assinatura continua em `hmac.compare_digest`. O token que pede outro algoritmo é recusado, mesmo com uma assinatura que confere. Dois atalhos deixam o `mac-sha256` vermelho. Um é proibir só o `"none"`: é a lista do que não pode, e a lição 08 pediu a lista do que pode. O outro é apagar o ramo do `"none"` e ignorar o header: aí o header deixa de confirmar qualquer coisa.
