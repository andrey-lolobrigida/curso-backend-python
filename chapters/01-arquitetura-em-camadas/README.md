# Capítulo 1 — Arquitetura em camadas

No capítulo 0, o `server.py` era uma caixa-preta: você conversava com ele sem saber como era por dentro. Este capítulo constrói o nosso — e constrói *em camadas*, cada uma nascendo de uma dor que você vai sentir antes de curar. Nada de organograma para decorar no primeiro dia: o mapa da arquitetura é a **última** lição, quando cada caixa dele já tiver sido um problema seu.

O app tem nome: **FairFare** — grupos de amigos reservam recursos compartilhados (quadras, chalés, salas de ensaio) e racham os custos. *Fair fare*, tarifa justa. Neste capítulo nasce a metade das reservas: usuários, recursos e a primeira regra de negócio de verdade (não reservar horário ocupado). O resto chega quando cada capítulo precisar.

## Pré-requisitos

| Ferramenta | Conferir com | Nota |
|------------|--------------|------|
| uv | `uv --version` | [instalação](https://docs.astral.sh/uv/getting-started/installation/) — a lição 01 explica o que ele é |
| git | `git --version` | para navegar pelos commits do capítulo |

Python? Não precisa instalar: o uv baixa o 3.12 sozinho se a sua máquina não tiver. É a primeira lição.

## As lições

Em ordem — cada uma tem uma ideia só e termina com um checkpoint:

| # | Lição | A ideia única |
|---|-------|---------------|
| 01 | [Ferramentas: uv e o esqueleto](theory/01-ferramentas-uv-e-o-esqueleto.md) | Ambiente reproduzível: contrato + carimbo |
| 02 | [Por que FastAPI](theory/02-por-que-fastapi.md) | A comparação vale mais que o vencedor |
| 03 | [Nasce o FairFare: v0 tudo-em-um](theory/03-fairfare-v0-tudo-em-um.md) | Três rotas num arquivo — e duas dores plantadas |
| 04 | [Schemas: a porta aprende a dizer não](theory/04-schemas-pydantic.md) | Validação de forma na borda, 422 como diagnóstico |
| 05 | [Persistência: o FairFare ganha memória](theory/05-persistencia-sqlite.md) | SQLite, o ciclo do SQL cru — e seu boilerplate |
| 06 | [Models: contratamos um ORM](theory/06-models-sqlalchemy.md) | Tabela ↔ classe, Session como carrinho, `Depends` |
| 07 | [Migrações: o banco ganha controle de versão](theory/07-migracoes-alembic.md) | Schema evolui sem apagar dados |
| 08 | [Repositories: o acesso a dados ganha endereço fixo](theory/08-repositories.md) | A única porta para o banco de cada entidade |
| 09 | [Services: a regra de negócio encontra sua casa](theory/09-services-regra-de-negocio.md) | Os três tipos de "não pode" |
| 10 | [Routers e a forma final: o app ganha seu mapa](theory/10-routers-forma-final.md) | O diagrama de camadas — derivado, não decorado |
| 11 | [Smoke tests: a rede de segurança](theory/11-smoke-tests.md) | Do checklist manual ao `pytest` em 0,2s |

## Como percorrer

Este capítulo é uma **refatoração contínua**: o app nasce feio de propósito na lição 03 e ganha uma camada por lição. Por isso a ordem importa — e por isso cada lição corresponde a um commit, marcado com uma tag de nome previsível:

```bash
git log --oneline --reverse v-chapter-00..v-chapter-01   # os commits do capítulo
git tag -l "v-cap01-licao*"                              # as tags, uma por lição
```

O jeito certo de acompanhar é **rodando**. Vá até a lição que você está lendo, suba o app, provoque a dor que ela descreve — e veja a cura na lição seguinte:

```bash
git checkout v-cap01-licao05         # o app no fim da lição 05
uv sync                              # o ambiente daquele ponto do curso
uv run uvicorn app.main:app --reload
```

### O aviso assustador que o git vai te dar

Esse checkout deixa você em **detached HEAD**, e o git anuncia isso com um parágrafo alarmado. Ele não está te repreendendo — está sendo literal, e vale entender agora, porque é um dos conceitos que mais confunde quem está começando.

Normalmente você está *em cima de uma branch*: um nome que anda junto com você, avançando a cada commit. Ao fazer checkout de uma tag, você foi para um commit específico, e não existe nome nenhum acompanhando. O HEAD ficou solto, apontando direto para o commit em vez de para uma branch.

Na prática: olhe, rode e experimente à vontade — nada quebra. O que você **não** deve fazer é commitar e esperar reencontrar o trabalho depois: sem uma branch para carregar o ponteiro, o commit fica órfão. Se quiser mexer e guardar, dê um nome ao lugar antes:

```bash
git switch -c minha-experiencia-licao05
```

E para voltar ao presente, com o capítulo inteiro no lugar:

```bash
git switch chapter-01
```

É o primeiro de vários hábitos de git que este curso ensina de lado, usando o próprio repositório como laboratório.

Depois da lição 11, os [exercícios](exercises/README.md) — três blocos: depurar, estender, refatorar. E só depois de tentar, o [SOLUTIONS.md](SOLUTIONS.md).

## Como rodar o app

No estado final do capítulo:

```bash
uv sync                            # materializa o ambiente (Python incluso)
uv run alembic upgrade head        # cria/atualiza o banco (fairfare.db)
uv run uvicorn app.main:app --reload
```

Documentação interativa em `http://localhost:8000/docs`. E a rede de segurança:

```bash
uv run pytest
```

## O diff deste capítulo

Diffs são material de leitura neste curso. O capítulo inteiro, mudança a mudança: o comando `git log` acima, ou [a comparação no GitHub](https://github.com/andrey-lolobrigida/curso-backend-python/compare/v-chapter-00...v-chapter-01) — lá os commits vêm do mais novo para o mais antigo; leia de baixo para cima.

## Ao terminar

Você terá um backend em camadas, com migrações, testes e uma regra de negócio de verdade. E uma notícia desconfortável: **cada request do nosso servidor ocupa uma thread inteira, e existem só 40 delas.** Enquanto uma request espera o banco, uma thread fica parada segurando o lugar — e a quadragésima primeira pessoa espera na porta. O capítulo 2 começa medindo isso — e o resto dele é a cura.

## O que este código ainda não resolve

O FairFare chega ao fim deste capítulo com três limitações conhecidas. Elas continuam aí de propósito: consertar qualquer uma exigiria conceitos que o curso ainda não ensinou. Nenhuma delas é pegadinha — são dívidas com data de vencimento marcada.

- **Duas pessoas podem reservar o mesmo horário.** `BookingService.create` verifica o conflito e só depois insere; duas requests simultâneas passam as duas pela verificação. → **capítulo 4**
- **Listar reservas faz 2N+1 consultas.** Cada reserva na lista busca usuário e recurso separadamente (o problema N+1). → **capítulo 4**
- **Não existe autenticação.** `POST /bookings` aceita qualquer `user_id`, então qualquer pessoa reserva no nome de qualquer outra. → **capítulo 5**

A versão longa, com o mecanismo de cada uma, está na [lição 11 do capítulo 2](../02-python-assincrono/theory/11-o-que-ainda-nao-resolve.md). O histórico de por que isso não estava escrito aqui desde o começo está na [ERRATA](../../ERRATA.md).
