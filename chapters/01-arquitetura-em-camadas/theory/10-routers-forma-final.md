# Lição 10 — Routers e a forma final: o app ganha seu mapa

## A última dor do capítulo

O `main.py` chegou a este commit com ~150 linhas: oito rotas de três domínios diferentes, empilhadas numa ordem que só o histórico do git explica. Quer mexer no 404 de recurso? Role até achar. Quer ver só as rotas de reserva? Elas estão... em algum lugar. Cada entidade nova empurraria o arquivo para 200, 300 linhas — achar qualquer coisa vira caça ao tesouro.

Todas as outras camadas já têm casa própria. Faltava a camada HTTP.

## `APIRouter`: cada domínio vira um mini-app

O FastAPI resolve isso com o `APIRouter`: um "mini-app" com suas próprias rotas, que depois é plugado no app principal. O novo `app/routers/users.py` começa assim:

```python
router = APIRouter(prefix="/users", tags=["users"])


@router.post("", status_code=201, response_model=UserOut)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    ...
```

Duas novidades na primeira linha: o **prefix** (`/users`) faz as rotas declararem só o sufixo — `""` é o próprio `/users`, `"/{user_id}"` é `/users/{user_id}` — e as **tags** agrupam as rotas no `/docs`, que agora exibe três seções dobráveis (users, resources, bookings) de graça.

Os corpos das rotas foram **movidos, não modificados** — o diff deste commit é quase todo mudança de endereço. E o `main.py` inteiro virou isto:

```python
from fastapi import FastAPI

from app.routers import bookings, resources, users

app = FastAPI(title="FairFare")

app.include_router(users.router)
app.include_router(resources.router)
app.include_router(bookings.router)
```

Nove linhas. O arquivo que já foi o app inteiro agora só apresenta as partes umas às outras.

No mesmo commit, os arquivos achatados (`models.py`, `schemas.py`, `repositories.py`, `services.py`) viraram **pacotes com um arquivo por entidade** — `app/models/user.py`, `app/schemas/booking.py`, e assim por diante. Conteúdo idêntico, endereço melhor: para achar qualquer coisa agora bastam duas perguntas — *que camada?* (a pasta) e *que entidade?* (o arquivo).

## O mapa, enfim

Onze lições atrás o FairFare era um arquivo. Agora ele tem esta forma — e cada caixa do diagrama foi uma **dor** antes de ser uma camada:

```
        request HTTP
             │
             ▼
┌─────────────────────────┐
│  router                 │  traduz HTTP ↔ domínio        (dor: lição 10)
│  app/routers/           │  rota fina: delega e traduz
└────────────┬────────────┘
             │              ┌──────────────────────────┐
             │◄────────────►│  schemas                 │  os contratos das bordas
             │              │  app/schemas/            │  validam forma (lição 04)
             ▼              └──────────────────────────┘
┌─────────────────────────┐
│  service                │  decide: regras de negócio    (dor: lição 09)
│  app/services/          │  não conhece HTTP
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│  repository             │  busca e grava: única porta   (dor: lição 08)
│  app/repositories/      │  para o banco
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│  model                  │  descreve o dado              (dores: lições 05–07)
│  app/models/            │  tabela ↔ classe
└────────────┬────────────┘
             ▼
        banco de dados
```

Este diagrama fecha o capítulo **de propósito**, e não o abre. Se você o tivesse visto na lição 03, seria um organograma para decorar. Agora ele é um resumo do que você sentiu: a validação nasceu do `{"nome": 42}`, o repository nasceu do boilerplate, o service nasceu da regra de conflito. Arquitetura boa não se decora — se deriva.

(Uma ausência honesta: usuários e recursos pulam a camada de service e vão direto ao repository. Regra da lição 09: camada vazia é burocracia.)

## A regra de ouro das dependências

Olhe as setas do mapa: apontam todas para dentro. A regra que mantém o desenho de pé: **camada de fora conhece a de dentro, nunca o contrário.**

O router importa service e schemas; o service importa repositories; o repository importa models. Mas o model não sabe que repositories existem, o repository nunca ouviu falar de HTTP, e o service não importa nada de `fastapi`. É por isso que as camadas são trocáveis: quem está por dentro não tem fios ligados para fora, então dá para trocar a borda (testes na lição 11 farão exatamente isso) sem que o miolo perceba.

Quando bater a dúvida sobre onde algo mora, pergunte "quem eu precisaria importar?" — se a resposta violar a seta, é o lugar errado.

## Teste de arquitetura: chegou a feature, que arquivo você abre?

- *"O front precisa que `GET /resources` aceite `?tipo=quadra`."* — Parâmetro de query é HTTP: comece em `app/routers/resources.py`; a query nova com filtro vai para `app/repositories/resource.py`.
- *"Reserva não pode durar mais de 8 horas."* — Compare `starts_at` e `ends_at`: os dois estão na request, não precisa de banco. É forma: `app/schemas/booking.py`.
- *"Máximo de 3 reservas futuras por usuário."* — Precisa contar o que existe no banco: regra de estado do mundo. `app/services/booking.py` decide, com uma query nova em `app/repositories/booking.py`.

## A outra forma

Releia as três respostas acima. Em todas, a resposta é "dois ou três arquivos, em pastas diferentes". Uma feature vive espalhada — e isso não é acidente nosso, é a consequência natural de organizar **por camada**: uma pasta por tipo de arquivo, uma feature fatiada entre elas.

Existe o layout oposto, e ele é comum no ecossistema FastAPI — organizar **por feature**:

```
app/
├── users/        → model.py, schema.py, repository.py, router.py
├── bookings/     → model.py, schema.py, repository.py, service.py, router.py
└── resources/    → model.py, schema.py, repository.py, router.py
```

Mesmas camadas, mesma regra de ouro das dependências, mesmo tudo — só o critério de agrupamento mudou. A feature inteira mora numa pasta; o que se espalha agora são as camadas.

Quando cada um ganha? **Por camada** rende com poucas entidades, quando você está aprendendo, e quando as mudanças atravessam tudo ("todo repository vai passar a logar queries" é um passeio numa pasta só). **Por feature** rende quando há muitas features e times donos de fatias — cada um mexe na sua pasta, e o merge conflict do vizinho não é problema seu.

E este capítulo escolheu camadas de propósito, por um motivo pedagógico, não arquitetural: para *ensinar* uma camada é preciso vê-la isolada, nascendo de uma dor própria. `repositories/` virou uma pasta visível porque a lição 08 precisava que ela fosse. Num projeto seu, com o conceito já na cabeça, a outra forma é escolha legítima — e a maioria dos backends grandes acaba nela.

## O que você deve conseguir fazer agora

- Desenhar o mapa de memória — as cinco caixas e a direção das setas.
- Responder "onde mora?" sem hesitar:
  1. validar que `email` tem arroba → ?
  2. uma query nova ("reservas de um usuário") → ?
  3. a regra "recurso em manutenção não aceita reserva" → ?
  4. mudar o 409 do conflito para outro status → ?
  5. uma coluna nova em `resources` → ? (pegadinha: são dois lugares — qual o segundo?)
- Explicar a regra de ouro das dependências e o que ela compra.
