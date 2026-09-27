# Capítulo 3 — Entre o cliente e o router

Desde o capítulo 1 você digita `uvicorn app.main:app` e nunca perguntou o que é esse `uvicorn`. Este capítulo abre a caixa.

E a caixa é maior do que parece. **O seu app não fala com o cliente.** Ele fala com o que está na frente dele. Um servidor ASGI que já parseou o HTTP. Uma pilha de middlewares que já decidiu coisas. Às vezes um proxy reverso que terminou o TLS e reescreveu headers. Quando a primeira linha do seu router roda, meia dúzia de decisões já foram tomadas por outra pessoa. Este capítulo é sobre essas decisões: quem as toma, onde, e o que quebra quando você não sabe que elas existem.

O FairFare ganha duas camadas — CORS e limitação de taxa. O resto do capítulo acontece **em volta** do app: um proxy escrito à mão, um certificado gerado na sua máquina, quatro workers e a descoberta desconfortável de que o seu app não é um processo.

## Pré-requisitos

O capítulo 2 completo (ou `git checkout v-chapter-02`, `uv sync`).

Nada para instalar agora. A única dependência que este capítulo acrescenta é a `cryptography`, e ela entra como **dev** (`uv add --dev cryptography`) na lição 09, para gerar um certificado de mentira — o FairFare não importa nada dela.

Você também vai precisar de um `curl` e de um browser com o console aberto. As duas coisas são instrumentos de leitura aqui, não enfeite.

## As lições

Em ordem — cada uma tem uma ideia só e termina com um checkpoint:

| # | Lição | A ideia única |
|---|-------|---------------|
| 01 | [Abrindo a caixa do uvicorn](theory/01-abrindo-a-caixa-do-uvicorn.md) | Um app ASGI são três argumentos: `scope`, `receive`, `send` |
| 02 | [O que o servidor faz antes do seu app](theory/02-o-que-o-servidor-faz-antes.md) | Do socket ao `scope` — keep-alive e os freios brutos do servidor |
| 03 | [Middleware: a cebola](theory/03-middleware-a-cebola.md) | Um app que embrulha outro — e `add_middleware` empilha de dentro para fora |
| 04 | [O browser também está no meio](theory/04-o-browser-tambem-esta-no-meio.md) | CORS protege o usuário do browser, não a sua API |
| 05 | [Muita gente batendo na porta](theory/05-muita-gente-batendo-na-porta.md) | Token bucket por cliente, com o relógio injetado para o teste poder mentir |
| 06 | [O proxy reverso](theory/06-o-proxy-reverso.md) | Um servidor que faz requests a outro servidor — cinquenta linhas de código na frente do app |
| 07 | [Mesma origem, e a mesma coisa em outra língua](theory/07-mesma-origem-e-a-mesma-coisa-em-outra-lingua.md) | Página e API na mesma origem, e o CORS fica quieto; o mesmo proxy em Caddy e em nginx |
| 08 | [Atrás do proxy, em quem confiar](theory/08-atras-do-proxy-em-quem-confiar.md) | `X-Forwarded-For` só vale se quem está na borda não acreditar em ninguém |
| 09 | [TLS: a conversa fica secreta](theory/09-tls-a-conversa-fica-secreta.md) | As três garantias, as duas que ele não dá — e o handshake contado em idas e voltas |
| 10 | [O certificado: quem garante que é você](theory/10-o-certificado-quem-garante-que-e-voce.md) | Autoassinado não é xingamento: o que falta é cadeia — e quem termina o TLS é o proxy |
| 11 | [Mais de um processo, e o que acontece quando o processo para](theory/11-varios-processos.md) | Quatro workers, quatro baldes: o seu app não é um processo |
| 12 | [O que este código ainda não resolve](theory/12-o-que-ainda-nao-resolve.md) | O inventário das limitações declaradas, com o capítulo em que cada uma morre |

## Este capítulo se acompanha com várias abas

O capítulo 2 se acompanhava medindo. Este se acompanha com **três terminais abertos ao mesmo tempo** — porque o assunto é o que acontece entre duas peças, e para ver o meio você precisa das duas pontas de pé.

Cada aba ocupa uma porta, e o capítulo inteiro respeita este mapa:

| Porta | Quem mora ali |
|---|---|
| 8000 | O FairFare (ou um servidor da bancada no lugar dele) |
| 8080 | A página estática / o proxy reverso |
| 8443 | Qualquer servidor com TLS: o proxy terminando TLS, ou o FairFare direto (lição 10) |

Se uma porta estiver ocupada, o uvicorn morre na subida com `address already in use`. Mate o servidor da aba anterior antes de subir o próximo. (Os exercícios usam a 8200, de propósito fora do mapa: dá para deixar a bancada montada enquanto você resolve o bloco 1.)

O aparelho que você mais vai usar é o `carga.py` — herdeiro do disparador do capítulo 2, agora contando os status um a um e sabendo mandar headers inventados:

```bash
C=chapters/03-entre-o-cliente-e-o-router/bancada/carga.py
uv run python $C http://localhost:8000/users 100
uv run python $C http://localhost:8000/users 100 --header 'X-Forwarded-For: 10.0.0.{i}'
```

Com o FairFare de pé na 8000, os dois comandos dão isto:

```
100 requests em 0.12s  status → 200: 20  429: 80  (Retry-After: 1s)
100 requests em 0.17s  status → 200: 100
```

A primeira linha é o rate limiter da lição 05 funcionando. A segunda é o mesmo limitador desmontado por um header que o cliente inventou — `{i}` vira o número da request, então são cem clientes falsos, cem baldes novos. É a lição 08 inteira em um comando, e o susto vale mais lido no seu terminal do que aqui.

### A bancada

A pasta [`bancada/`](bancada/) é o instrumental do capítulo: um app ASGI sem framework nenhum, um espião que imprime o `scope` de cada request, três middlewares que anunciam quando entram e quando saem, um proxy reverso de cinquenta linhas de código, um espelho que conta em quem o servidor resolveu acreditar, um gerador de certificado, uma página que conversa com o FairFare via `fetch`, e as versões em Caddy e nginx do mesmo proxy — **lidas como texto, nunca executadas**.

**Nada dali faz parte do FairFare.** São aparelhos de medição, e o [README da bancada](bancada/README.md) tem as regras, a tabela do que nasce em qual lição e o comando de subida de cada peça.

## Como percorrer

Cada lição corresponde a um commit, marcado com uma tag de nome previsível:

```bash
git log --oneline --reverse v-chapter-02..v-chapter-03   # os commits do capítulo
git tag -l "v-cap03-licao*"                              # as tags, uma por lição
```

Para ver o app num ponto específico do capítulo:

```bash
git checkout v-cap03-licao05         # o FairFare logo depois do rate limiter
uv sync
uv run uvicorn app.main:app --reload
```

Isso te coloca em **detached HEAD** — o git vai avisar com um parágrafo alarmado, e o [README do capítulo 1](../01-arquitetura-em-camadas/README.md#o-aviso-assustador-que-o-git-vai-te-dar) explica com calma o que isso significa e como voltar.

Um aviso de expectativa: neste capítulo, andar pelas tags muda **pouco** o `app/`. Só dois commits encostam nele (veja "O diff deste capítulo"). O que cresce a cada lição é a bancada — e é lá que a viagem no tempo vale a pena.

E um segundo aviso, sobre a bancada. Cada lição imprime os arquivos da bancada **como eles estavam no commit dela**. Alguns mudam depois: o `proxy.py` ganha duas linhas na lição 08, o `eco.py` ganha um `/lento` na 11. Quando isso acontece, a lição avisa numa linha em itálico logo abaixo do código. Para ver exatamente a versão de uma lição sem sair da branch:

```bash
git show v-cap03-licao06:chapters/03-entre-o-cliente-e-o-router/bancada/proxy.py
```

## Os exercícios

Três blocos em [`exercises/`](exercises/README.md), na ordem depurar → estender → refatorar.

Os blocos 1 e 3 contêm **código quebrado de propósito**, e o enunciado diz isso em letras garrafais. O bloco 2 é a exceção: ele não está quebrado, só sabe fazer metade do serviço.

```bash
uv run pytest chapters/03-entre-o-cliente-e-o-router/exercises/bloco1 -v   # 1 passou, 2 falharam
uv run pytest chapters/03-entre-o-cliente-e-o-router/exercises/bloco2 -v   # 1 passou, 2 falharam
uv run pytest chapters/03-entre-o-cliente-e-o-router/exercises/bloco3 -v   # 4 passaram, 1 falhou
```

O bloco 3 é o desconfortável: quatro dos cinco testes já passam, e o código continua mal desenhado. O teste que falha é **estrutural** — ele olha a pilha de middlewares e cobra uma forma, porque nenhum teste de comportamento consegue cobrar isso.

Nenhum dos três importa `app/`: são servidores de brinquedo do tamanho de uma tela, para você mexer sem medo de estragar o FairFare. As soluções, com o raciocínio de cada conserto — inclusive a ordem da pilha, que é decisão e não gosto —, estão em [SOLUTIONS.md](SOLUTIONS.md).

## Como rodar o app

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Documentação interativa em `http://localhost:8000/docs`. E a rede de segurança:

```bash
uv run pytest
```

## O diff deste capítulo

Diffs são material de leitura neste curso. O capítulo inteiro, mudança a mudança: o `git log` acima, ou [a comparação no GitHub](https://github.com/andrey-lolobrigida/curso-backend-python/compare/v-chapter-02...v-chapter-03) — lá os commits vêm do mais novo para o mais antigo; leia de baixo para cima.

Uma coisa salta aos olhos nesse diff: **de quinze commits, só dois tocam `app/`.**

- **Lição 04** — dez linhas em `app/main.py`: o `CORSMiddleware`, com uma origem explícita e um comentário: `Origem explícita: nada de "*"` — a lição 04 explica por quê.
- **Lição 05** — sete linhas em `app/main.py` e o arquivo novo `app/middleware/rate_limit.py`, com o token bucket.

Todo o resto do capítulo — proxy, TLS, workers, fronteira de confiança — acontece **fora** do app, e essa é a lição escondida no diff: uma parte enorme do comportamento do seu backend em produção não mora no seu código. Mora na configuração de quem está na frente dele.

## Ao terminar

O FairFare tem duas camadas novas: CORS com origem declarada e limitação de taxa por cliente. E você tem o que o capítulo 2 não deu — o que acontece **antes** da primeira linha do seu router.

Sem inventar, item por item: você sabe o que o uvicorn faz entre o socket e o `scope`, sabe escrever um app ASGI sem framework, sabe prever a ordem de uma pilha de middlewares, pôs um proxy reverso na frente do app e viu o CORS ficar quieto, sabe em quem confiar quando o `X-Forwarded-For` chega, gerou um certificado e viu TLS de verdade acontecer em `localhost` — e mediu o que quatro workers fazem com estado guardado na memória.

Fica de pé o que **não** foi resolvido, e é uma lista longa: a [lição 12](theory/12-o-que-ainda-nao-resolve.md) é o inventário completo, cada item com endereço e com o capítulo em que ele morre. Inclusive as três herdadas do capítulo 1, que este capítulo não encostou.

E fica um fio solto, que é o gancho do próximo capítulo. O rate limiter guarda o estado dele num `dict`, na memória de um processo, porque **ainda não temos onde guardar estado compartilhado** — a lição 11 mostrou o limite de 20 virar 60 com quatro workers. Guarde a forma desse problema: duas cópias do mesmo código, mexendo no mesmo estado, sem combinar nada.

Porque o próximo lugar onde estado compartilhado vai doer não é a memória. É o **banco**. Duas pessoas clicam em "reservar" na mesma quadra, no mesmo horário, no mesmo segundo — e o capítulo 4 é sobre por que as duas conseguem.
