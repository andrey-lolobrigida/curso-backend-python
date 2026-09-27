# Exercícios do capítulo 3

**Aviso, porque isto importa: os arquivos dos blocos 1 e 3 contêm código quebrado de propósito.**

O FairFare, em `app/`, está correto — o que você encontrar de errado lá vale um issue. O que está *aqui* foi escrito errado de caso pensado, para você consertar. E estão quebrados de jeitos diferentes. O bloco 1 está **funcionando errado e mostrando**: dois defeitos que os testes pegam. O bloco 3 está **funcionando errado e escondendo**: passa em todos os testes de comportamento e mesmo assim está mal desenhado. O bloco 2 é a exceção das exceções: não está quebrado, só sabe fazer metade do serviço.

Cada bloco tem testes que você mesmo roda. O teste é a definição de "pronto": enquanto ele estiver vermelho, o exercício não acabou.

Nenhum destes testes é coletado pelo `uv run pytest` do projeto (o `testpaths` do `pyproject.toml` cuida disso). Você roda cada bloco apontando o caminho.

Os três blocos são **autocontidos**: nenhum deles importa `app/`. São servidores de brinquedo, do tamanho de uma tela, para você mexer sem medo de estragar o FairFare.

---

## Bloco 1 — Depurar: bloqueia demais e bloqueia de menos

**Arquivo:** `bloco1/servidor.py` — **contém código quebrado deliberadamente.**

Um FairFare de brinquedo com CORS e rate limit: capacidade 5, uma ficha por segundo. São **dois** defeitos, e eles não têm nada a ver um com o outro — nem na causa, nem na camada, nem no jeito de aparecer.

Antes de abrir o código, **veja a dor**. Suba o servidor numa aba:

```bash
uv run uvicorn servidor:app --port 8200 --app-dir chapters/03-entre-o-cliente-e-o-router/exercises/bloco1
```

e, noutra, dispare carga duas vezes, com três segundos de intervalo:

```bash
C=chapters/03-entre-o-cliente-e-o-router/bancada/carga.py
uv run python $C http://localhost:8200/users 10
sleep 3
uv run python $C http://localhost:8200/users 10
```

Na máquina do autor, saiu isto:

```
10 requests em 0.01s  status → 200: 5  429: 5  (Retry-After: 1s)
10 requests em 0.01s  status → 429: 10  (Retry-After: 1s)
```

A primeira linha está certa: cinco fichas, cinco passam, cinco levam 429. A segunda é o defeito na sua cara — **três segundos depois, com uma ficha por segundo, nem uma request passou.** O `Retry-After` diz "tente em 1s"; o servidor está mentindo. Um limitador que nunca solta é uma porta trancada, não um limitador.

Se os seus números da primeira rodada saírem `200: 4  429: 6`, provavelmente você deu um `curl localhost:8200/health` antes, para ver se o servidor tinha subido. Isso não é ruído de medição: é o limitador fazendo o trabalho dele. **Ele não sabe o que é request "de verdade".** Health check gasta ficha, favicon gasta ficha — e guarde essa frase, porque o segundo defeito deste bloco é exatamente uma request que não devia estar gastando.

Esse é o defeito que aparece de fora. O outro só aparece com um browser no meio — ou com o teste que o imita.

```bash
uv run pytest chapters/03-entre-o-cliente-e-o-router/exercises/bloco1 -v
```

Estado inicial: **1 passou, 2 falharam**. Um dos testes é o da recarga que nunca vem. O outro fala do preflight e do 429 sem CORS — a lição 05 avisou que aquela ordem da pilha era uma *decisão*, e aqui ela chega tomada errado.

**Pronto quando:** os três testes passam, e você consegue dizer em uma frase por que os dois consertos não têm nada a ver um com o outro. (Dica de método: um deles é aritmética de tempo, o outro é topologia de pilha. Se você "consertou" os dois no mesmo lugar do arquivo, um dos dois não foi consertado de verdade.)

---

## Bloco 2 — Estender: um proxy que serve duas apps

**Arquivo:** `bloco2/proxy.py` — este **não** está quebrado. Ele funciona.

`criar_proxy` recebe um dicionário `{prefixo: cliente httpx2}` e devolve um app Starlette. Hoje ele pega o primeiro par do dicionário e ignora o resto: tudo que chega vai para o mesmo upstream, com o mesmo prefixo removido. Faça-o rotear **por prefixo**, e responder `404` quando nenhum prefixo casar.

O que já está lá e tem que continuar lá: o prefixo sai do caminho, a query string atravessa inteira, o `Host` original é preservado e o `X-Forwarded-For` é **sobrescrito** com o cliente de verdade (lição 08 — quem está na borda não acredita em ninguém).

Um aviso sobre o `Host`, porque ele contraria a bancada por escolha: o `proxy.py` das lições 06 e 08 **tira** o `Host` ("o httpx põe o do upstream"), e aqui ele **atravessa**. As duas escolhas existem no mundo real — o `nginx.conf` da lição 07 preserva, com `proxy_set_header Host $host`, justamente para o upstream saber por qual nome ele foi chamado. Neste bloco a escolha é preservar, e o teste que já está verde cobra isso. Se você copiar o `!= "host"` da bancada por reflexo, vai derrubar um teste que não tinha pedido para ser mexido.

```bash
uv run pytest chapters/03-entre-o-cliente-e-o-router/exercises/bloco2 -v
```

Estado inicial: **1 passou, 2 falharam**. O que já passa é o do formato — e continuar passando é metade da tarefa: refatoração que muda o contrato do proxy não é refatoração, é bug.

Nenhuma porta é aberta neste bloco. Os upstreams são apps ASGI de brinquedo ligados por `ASGITransport`, e o proxy inteiro roda dentro do processo do pytest. É o mesmo truque do `conftest.py` do FairFare, usado para testar uma peça de rede sem rede nenhuma.

**Pronto quando:** os três testes passam. Bônus, para responder de cabeça: se um upstream devolvesse `429` com um `Retry-After: 30`, o que acontece com esse header ao atravessar o seu proxy — e o que você *queria* que acontecesse?

---

## Bloco 3 — Refatorar: o middleware que faz tudo

**Arquivo:** `bloco3/main.py` — **está funcionando errado de propósito.**

Este é o bloco desconfortável: **os testes de comportamento já passam.** Um único `BaseHTTPMiddleware` chamado `FazTudo` responde preflight na mão, aplica rate limit e carimba um header de identificação, tudo entrelaçado no mesmo `dispatch`. Do lado de fora, ninguém reclama.

Do lado de dentro, é código que ninguém consegue mudar sem quebrar duas coisas que não têm relação — e um CORS na mão que faz menos do que parece.

Desmonte-o em middlewares de responsabilidade única, na ordem certa, mantendo os quatro testes de comportamento verdes.

```bash
uv run pytest chapters/03-entre-o-cliente-e-o-router/exercises/bloco3 -v
```

Estado inicial: **4 passaram, 1 falhou**. O que falha é o último, e ele é **estrutural**: olha `app.user_middleware` e cobra que o `FazTudo` tenha sumido e que existam pelo menos três camadas. Um teste estrutural é uma ferramenta esquisita e você deve desconfiar dela — aqui ela existe porque a tarefa *é* a estrutura, e nenhum teste de comportamento consegue exigir isso.

A parte difícil não é escrever os middlewares. É decidir três coisas:

- o que vira `CORSMiddleware` pronto (o do Starlette faz coisas que o `FazTudo` não faz — abra o fonte dele e ache pelo menos uma);
- o que fica como middleware ASGI puro escrito por você;
- **em que ordem** eles entram, lembrando que `add_middleware` empilha de dentro para fora.

A ordem não é gosto: o carimbo tem que aparecer no preflight (que quem responde é o CORS) **e** no 429 (que quem responde é o rate limiter), e o 429 tem que sair com os headers de CORS. Isso deixa uma ordem de pé, e só uma.

**Pronto quando:** os cinco testes passam, e você consegue justificar a ordem das camadas apontando qual teste cairia se você trocasse duas delas de lugar.
