# Capítulo 2 — Python assíncrono

O capítulo 1 terminou com uma frase minha sobre desempenho. Este capítulo começa medindo essa frase e descobrindo que ela é falsa.

Não é acidente de roteiro: é o método. Async é o assunto onde mais se repete crença sem medição — "async é mais rápido", "coloque `await` que resolve", "threads são coisa do passado". Aqui, cada afirmação vem com o comando que a produziu e o número que saiu. Inclusive as minhas, principalmente quando elas estão erradas.

Ao fim, o FairFare inteiro é assíncrono — engine, repositories, services, routers e testes — e você sabe dizer, olhando um trecho de código qualquer, se ele merece ser async e o que acontece se você errar.

## Pré-requisitos

O capítulo 1 completo (ou `git checkout v-chapter-01`, `uv sync`). Nada para instalar agora: as dependências deste capítulo (`aiosqlite`, `pytest-asyncio`) entram nas lições que as motivam, na hora.

## As lições

Em ordem — cada uma tem uma ideia só e termina com um checkpoint:

| # | Lição | A ideia única |
|---|-------|---------------|
| 01 | [Eu te menti no fim do capítulo 1](theory/01-a-mentira-do-capitulo-1.md) | Rota `def` vai para o threadpool; `async def` que bloqueia é pior |
| 02 | [Concorrência não é paralelismo](theory/02-concorrencia-nao-e-paralelismo.md) | O vocabulário: I/O-bound, CPU-bound, bloquear |
| 03 | [O event loop por dentro](theory/03-o-event-loop-por-dentro.md) | `await` marca a pausa; `gather` é quem concorre |
| 04 | [Quem bloqueia o loop para o mundo](theory/04-quem-bloqueia-o-loop.md) | Dentro de `async def`: ou é rápido, ou é `await` |
| 05 | [`await` só funciona se a biblioteca colaborar](theory/05-await-precisa-de-colaboracao.md) | Async é propriedade da stack toda — e a verdade sobre o `aiosqlite` |
| 06 | [A rede de segurança primeiro](theory/06-a-rede-de-seguranca-primeiro.md) | Os testes viram async antes do app; ASGI é a fronteira |
| 07 | [O app atravessa](theory/07-o-app-atravessa.md) | Dez arquivos num commit — e por que ele não pode ser menor |
| 08 | [O que ficou síncrono de propósito](theory/08-o-que-ficou-sincrono.md) | A régua das três perguntas; `async` é viral |
| 09 | [O pool de conexões](theory/09-o-pool-de-conexoes.md) | Empate em latência, abismo em escala — o teto mudou de lugar |
| 10 | [O GIL](theory/10-o-gil.md) | Threads servem para esperar, não para calcular |
| 11 | [O que este código ainda não resolve](theory/11-o-que-ainda-nao-resolve.md) | As três limitações conhecidas, declaradas |

## Este capítulo se acompanha medindo

Ler sobre concorrência convence pouco. Ver dez requests levarem dez segundos convence na hora.

A pasta [`bancada/`](bancada/) é o instrumental do capítulo: um servidor de mentira com duas rotas quase idênticas, um disparador de carga, o event loop em quatro cenas, um erro reproduzido de propósito e uma comparação de CPU. **Nada dali faz parte do FairFare** — são aparelhos de medição, e o README de lá explica as regras.

O comando que você mais vai usar:

```bash
# numa aba: o servidor da bancada
uv run uvicorn bancada.servidor:app --port 8123 --app-dir chapters/02-python-assincrono

# na outra: 10 requests ao mesmo tempo, cronometradas
uv run python chapters/02-python-assincrono/bancada/carga.py http://localhost:8123/sync 10
uv run python chapters/02-python-assincrono/bancada/carga.py http://localhost:8123/async-bloqueante 10
```

Os números das lições saíram da máquina do autor. Os seus vão ser parecidos, não idênticos — o que importa é a ordem de grandeza, e o texto sempre diz qual é.

## Como percorrer

Cada lição corresponde a um commit, marcado com uma tag de nome previsível:

```bash
git log --oneline --reverse v-chapter-01..v-chapter-02   # os commits do capítulo
git tag -l "v-cap02-licao*"                              # as tags, uma por lição
```

Para ver o app num ponto específico do capítulo:

```bash
git checkout v-cap02-licao07         # o app logo depois da travessia para async
uv sync
uv run uvicorn app.main:app --reload
```

Isso te coloca em **detached HEAD** — o git vai avisar com um parágrafo alarmado, e o [README do capítulo 1](../01-arquitetura-em-camadas/README.md#o-aviso-assustador-que-o-git-vai-te-dar) explica com calma o que isso significa e como voltar.

Um truque que a lição 09 usa e que vale para o curso inteiro: com `git worktree` você tem **duas versões do FairFare de pé ao mesmo tempo**, em portas diferentes, e pode disparar a mesma carga contra as duas.

```bash
git worktree add /tmp/fairfare-cap01 v-chapter-01
```

## Os exercícios

Três blocos em [`exercises/`](exercises/), na ordem depurar → estender → refatorar. Os blocos 1 e 3 contêm **código quebrado de propósito** (o enunciado diz isso em letras garrafais); o bloco 2 funciona e está lento.

```bash
uv run pytest chapters/02-python-assincrono/exercises/bloco1 -v
```

Quase todos os testes medem **tempo**, porque o defeito que você está aprendendo a caçar só aparece em número. As soluções, com o raciocínio de cada conserto — inclusive o de *não* converter uma função para async —, estão em [SOLUTIONS.md](SOLUTIONS.md).

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

## Uma correção ao capítulo 1

A frase que fechava o capítulo 1 — *"nosso servidor atende uma pessoa de cada vez"* — estava errada, e a lição 01 é inteirinha sobre isso. O texto do capítulo 1 já foi corrigido, e o registro do erro está na [ERRATA](../../ERRATA.md), junto com três limitações do FairFare que também não estavam declaradas e agora estão.

## O diff deste capítulo

Diffs são material de leitura neste curso. O capítulo inteiro, mudança a mudança: o `git log` acima, ou [a comparação no GitHub](https://github.com/andrey-lolobrigida/curso-backend-python/compare/v-chapter-01...v-chapter-02) — lá os commits vêm do mais novo para o mais antigo; leia de baixo para cima. O commit da lição 07 é o mais interessante do capítulo: dez arquivos de uma vez, com a explicação do porquê.

## Ao terminar

O FairFare é assíncrono de ponta a ponta, e a suíte de testes provou a travessia sem mudar um `assert`.

Sobre o que isso comprou, sem inventar: **em latência, nada** — uma request continua levando o mesmo tempo, e a lição 09 mostra o empate medido. O que mudou foi o teto. Antes, cada request ocupava uma das 40 threads do processo; agora, a espera não custa thread, e o limite virou o pool de conexões — um teto de 15 (5 fixas + 10 de pico) que está escrito no `app/database.py`, com um comentário do lado, e que você escolhe.

Fica de pé também o que **não** foi resolvido: a corrida de reserva dupla, o N+1 da listagem e a ausência total de autenticação, todos declarados na lição 11 com o capítulo que os mata.

E fica uma pergunta que o capítulo inteiro evitou: quem é esse `uvicorn` que a gente digita desde o capítulo 1 e nunca abriu? O capítulo 3 responde — servidores ASGI, proxies reversos, CORS, TLS e limitação de taxa. Ou seja: tudo que existe entre o cliente e a primeira linha do seu router.
