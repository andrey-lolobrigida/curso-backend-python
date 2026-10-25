# Capítulo 5 — Relações e dinheiro

Quatro capítulos inteiros, e o FairFare só sabia reservar. O nome promete outra coisa também: **dividir a conta.** Este capítulo entrega a outra metade. Grupos de amigos, despesas pagas por um e divididas entre vários, o saldo de cada um e a quitação que acerta as contas.

E dividir a conta parece fácil até você tentar. Um usuário está em vários grupos, e um grupo tem vários usuários: nenhuma tabela tem uma coluna só para isso. R$ 100 entre três não fecha em centavos. Um `float` erra a soma de dez moedas de dez centavos. Duas quitações ao mesmo tempo pagam a mesma dívida duas vezes. **Dinheiro é o domínio em que "quase certo" é errado.** Cada um desses problemas tem uma lição, e cada lição termina com o problema morto ou declarado.

Antes do domínio novo, porém, o capítulo paga uma conta velha. O 2N+1 do `GET /bookings` nasceu no capítulo 1, mora no `ERRATA.md` desde o capítulo 2 e esgotou um pool no capítulo 4. Ele morre aqui, nas três primeiras lições, com uma regra que impede que ele volte e um teste que conta as consultas.

## Pré-requisitos

O capítulo 4 completo (ou `git checkout v-chapter-04`, `uv sync`), com o compose de pé e o banco no `head`:

```bash
uv sync
docker compose up -d --wait
uv run alembic upgrade head
```

**Nenhuma dependência nova.** O capítulo 4 trouxe o PostgreSQL, o Docker e dois drivers. Este usa o que já está aí: o `Decimal` é da biblioteca padrão, e o resto é SQLAlchemy que você ainda não tinha usado.

O `pytest` continua precisando do compose de pé, como desde a lição 03 do capítulo 4.

## As lições

Em ordem. Cada uma tem uma ideia só e termina com um checkpoint. São três partes: a dívida (01 a 03), o dinheiro (04 a 07) e as operações (08 a 11). A 12 fecha a conta.

| # | Lição | A ideia única |
|---|-------|---------------|
| 01 | [`relationship()`: o objeto sabe dos vizinhos](theory/01-relationship-o-objeto-sabe-dos-vizinhos.md) | A chave estrangeira liga as tabelas; a `relationship()` liga os objetos. E o banco nem fica sabendo |
| 02 | [O lazy load que explode no async](theory/02-o-lazy-load-que-explode-no-async.md) | Ler uma relação que ninguém carregou é uma consulta escondida. No async, ela não esconde: ela explode |
| 03 | [O N+1 morre](theory/03-o-n-mais-1-morre.md) | `selectinload`, `lazy="raise"` e um teste que conta consultas. 4001 viram 3, e não voltam |
| 04 | [Grupos e membros](theory/04-grupos-e-membros.md) | O muitos-para-muitos mora numa tabela do meio, e a chave composta é quem diz não ao membro repetido |
| 05 | [Dinheiro não é float](theory/05-dinheiro-nao-e-float.md) | Seis desastres do `float`, a cratera prometida no capítulo 0 |
| 06 | [`Decimal` de ponta a ponta](theory/06-decimal-de-ponta-a-ponta.md) | Três fronteiras, nenhum `float`: string no JSON, `Decimal` no Python, `Numeric(12, 2)` no banco |
| 07 | [O centavo que sobra](theory/07-o-centavo-que-sobra.md) | `Decimal` não basta: R$ 100 entre três precisa de uma regra para o centavo, escrita e sempre a mesma |
| 08 | [Quem comita?](theory/08-quem-comita.md) | Uma despesa são várias gravações. O service abre a transação, o repository só faz `flush` |
| 09 | [Saldos: quem soma?](theory/09-saldos-quem-soma.md) | O saldo se calcula, nunca se guarda. E quem soma é o banco, não o Python |
| 10 | [Quando descer para SQL puro](theory/10-quando-descer-para-sql-puro.md) | O mesmo saldo em `text()`: quando vale a pena, e a injeção de SQL ao vivo |
| 11 | [Quitações: dois lados, dois cadeados](theory/11-quitacoes-dois-lados-dois-cadeados.md) | A corrida do capítulo 4, agora com dinheiro: `FOR UPDATE` nas duas linhas, sempre na mesma ordem |
| 12 | [O que este código ainda não resolve](theory/12-o-que-ainda-nao-resolve.md) | O inventário das limitações declaradas, com o capítulo em que cada uma morre, e o 2N+1 riscado |

## Este capítulo se acompanha contando

O capítulo 4 se acompanhava com um `psql` aberto. Este também, mas a pergunta muda. Lá era "quem está esperando quem". Aqui é **"quantas consultas isso custou?"**

A resposta vem de um contador pendurado na engine, em `tests/apoio.py::conta_consultas`. Ele nasce na lição 03 e vira o guardião de todo endpoint novo do capítulo: o `GET /bookings` faz 3 consultas, o `GET /groups/{id}` faz 3, o `GET .../balances` faz 2. Nenhum desses números cresce com o tamanho do banco. Quando crescer, o teste fica vermelho.

E o `psql` continua útil. A lição 06 mostra o `numeric` acertando a conta que o `float` erra. A lição 10 cola a consulta de saldos inteira nele, com `EXPLAIN`:

```bash
docker compose exec postgres psql -U fairfare -d fairfare
```

### A bancada

A pasta [`bancada/`](bancada/) tem os instrumentos de medição do capítulo. **Nada dali faz parte do FairFare.** O [README dela](bancada/README.md) tem o comando de cada script.

| Script | Lição | O que mostra |
|---|---|---|
| `conta_consultas.py` | 03 | quantas consultas e quanto tempo custa um `GET /bookings`, antes e depois do `selectinload` |
| `float.py` | 05 | seis desastres do `float` com dinheiro. Python puro: não precisa do compose |
| `saldos.py` | 09, 10 | o saldo calculado de três jeitos, lado a lado; com `--manter`, deixa o grupo no banco para a lição 10 |
| `injecao.py` | 10 | a mesma busca com f-string e com parâmetro, e o que o nome `x' OR '1'='1` faz com cada uma |
| `quitacao.py` | 11 | N quitações iguais ao mesmo tempo, pelo uvicorn de verdade; conta em quantas rodadas a dívida foi paga além |

**Dois avisos antes de rodar.** O `saldos.py` e o `quitacao.py` escrevem no banco de dev. Eles criam e apagam só o que é deles, mas os ids gastos ficam como buracos nas sequências.

O outro aviso é sobre o `seed.sql` do capítulo 4, que a lição 03 usa para encher o banco de reservas. Ele **apaga** `users`, `resources` e `bookings`. Depois da lição 04, o `CASCADE` leva junto membros, despesas, partes e quitações, e os grupos ficam vazios. Por isso ele só roda na lição 03, antes de existir grupo.

## Como percorrer

Cada lição corresponde a um commit, marcado com uma tag de nome previsível:

```bash
git log --oneline --reverse v-chapter-04..v-chapter-05   # os commits do capítulo
git tag -l "v-cap05-licao*"                              # as tags, uma por lição
```

Para ver o app num ponto específico do capítulo:

```bash
git checkout v-cap05-licao09         # os saldos no Core, antes de descerem para SQL puro
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Isso te coloca em **detached HEAD**. O git vai avisar com um parágrafo alarmado, e o [README do capítulo 1](../01-arquitetura-em-camadas/README.md#o-aviso-assustador-que-o-git-vai-te-dar) explica com calma o que isso significa e como voltar.

### O banco não viaja no tempo com você

O aviso do capítulo 4 continua valendo, e este capítulo tem três migrações novas. O `git checkout` troca o código. **Não troca o banco.** Se você terminou o capítulo e volta para a lição 04, o banco de dev tem as tabelas de despesas e de quitações, que o código da lição 04 nem conhece. E o Alembic daquela tag não tem os arquivos das migrações mais novas, então não sabe nem desfazê-las.

Por isso, **antes** do `checkout`, ainda no código mais novo, desça o banco até a migração da lição para onde você vai:

| Para ver as lições | O banco tem que estar em | O que a migração cria |
|---|---|---|
| 01 a 03 | `257143851bec` (a constraint do capítulo 4) | nada novo: as três lições só mexem no código |
| 04 e 05 | `9ea95ccd37e3` (grupos e membros) | `groups` e `group_members` |
| 06 a 10 | `390721a6515b` (despesas e partes) | `expenses` e `expense_shares` |
| 11 em diante | `2db1b72e440a` (quitações), que é o `head` | `settlements` |

```bash
uv run alembic downgrade 9ea95ccd37e3   # ainda na chapter-05
git checkout v-cap05-licao04
```

**Descer apaga.** Cada `downgrade` derruba as tabelas que a migração criou, e os dados vão junto. Descer até `9ea95ccd37e3` leva as despesas, as partes e as quitações. Descer até `257143851bec` leva também os grupos e os membros. Na volta, o `upgrade head` recria as tabelas, vazias.

Se o banco se enrolou, o caminho curto é o mesmo do capítulo 4, jogar fora e recomeçar:

```bash
docker compose down -v               # o -v apaga o volume: o banco de dev inteiro
docker compose up -d --wait
uv run alembic upgrade head
```

Os dois caminhos têm preço. O `downgrade` apaga o domínio de despesas. O `down -v` apaga tudo, inclusive os usuários e as reservas.

O `fairfare_test` tem a mesma pegadinha. A suíte recria as tabelas a cada rodada, mas só as que os models daquele commit conhecem. Volte para antes da lição 04, e o `drop_all` tenta derrubar `users` com os grupos e as despesas ainda pendurados nela: `cannot drop table users because other objects depend on it`, em todo teste. Antes de rodar a suíte num commit mais antigo, jogue o banco de teste fora. O `conftest.py` o recria na rodada seguinte:

```bash
docker compose exec postgres psql -U fairfare -d postgres -c 'DROP DATABASE fairfare_test'
```

## Os exercícios

Três blocos em [`exercises/`](exercises/README.md): o dinheiro, as consultas, e a transação com o cadeado.

Quase tudo ali está **quebrado de propósito**, e o enunciado diz isso em letras garrafais. A exceção é a 2.1, um N+1 escrito à mão que **funciona, mas do jeito caro**: a resposta sai certa, o número de consultas é que está errado.

```bash
uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco1 -v   # 5 falharam, 3 passaram
docker compose up -d --wait
uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco2 -v   # 2 falharam, 1 passou
uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco3 -v   # 2 falharam
```

O bloco 1 nem usa banco: é só `Decimal`. Os testes que passam nos blocos 1 e 2 são parte do exercício. No bloco 1, a pergunta é por que eles passam. No bloco 2, o `test_resumo_correto` tem que continuar passando depois do conserto.

Nenhum bloco importa `app/`. Os blocos 2 e 3 criam as próprias tabelas no `fairfare_test` e as apagam no fim; o banco de dev do FairFare não é tocado. As soluções, com o raciocínio de cada conserto (por que `0.35` passava, por que dois N+1 pedem dois remédios diferentes, por que trancar antes de ler), estão em [SOLUTIONS.md](SOLUTIONS.md).

## Como rodar o app

```bash
uv sync
docker compose up -d --wait
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Documentação interativa em `http://localhost:8000/docs`, agora com as rotas de grupos. E a rede de segurança:

```bash
uv run pytest
```

## O diff deste capítulo

Diffs são material de leitura neste curso. O capítulo inteiro, mudança a mudança: o `git log` acima, ou [a comparação no GitHub](https://github.com/andrey-lolobrigida/curso-backend-python/compare/v-chapter-04...v-chapter-05). Lá os commits vêm do mais novo para o mais antigo; leia de baixo para cima.

Os dois primeiros commits da comparação não são lições. Não estão na `chapter-04`: entraram pela `main`, e por isso aparecem no intervalo entre as duas tags:

- **Um complemento à entrada 3 do `ERRATA.md`**: além do fuso descartado, o `cancel` dos capítulos 1 a 3 comparava o horário gravado com o relógio local da máquina.
- **O merge do capítulo 4 na `main`**, de onde este capítulo partiu.

Das lições, nove tocam `app/`:

- **Lição 01**: as relações `user` e `resource` no `Booking`, em `app/models/booking.py`.
- **Lição 03**: `lazy="raise"` nas duas relações, o `selectinload` no `BookingRepository.list_all`, e o `_to_out` lendo a relação em vez de buscar usuário e recurso um por um.
- **Lição 04**: grupos e membros. Model, migração, repository, service, schema e as primeiras rotas em `app/routers/groups.py`.
- **Lição 06**: despesas e partes no model e numa migração, com `Numeric(12, 2)`, e o tipo `Dinheiro` em `app/schemas/dinheiro.py`.
- **Lição 07**: `app/services/divisao.py`, a regra do centavo que sobra.
- **Lição 08**: o `commit()` sai de todos os repositories, e os services passam a abrir a transação com `async with self.db.begin()`. Nasce o `POST /groups/{id}/expenses`.
- **Lição 09**: o `GET /groups/{id}/balances`, com a soma feita pelo banco.
- **Lição 10**: a mesma consulta de saldos, reescrita em `text()`.
- **Lição 11**: quitações no model e numa migração, o `POST /groups/{id}/settlements`, e o `lock_members` trancando as duas linhas em ordem de `user_id`.

Repare no que **não** está na lista. A lição 02 mexe só em `tests/`: é o experimento que dá errado, e ele não entra no código. A 12 é só texto. E a lição 05, a do `float`, não muda uma linha do app: ela mostra o desastre na bancada, e o conserto é a lição seguinte. Primeiro ver, depois consertar.

## Ao terminar

O FairFare divide a conta. Um grupo tem membros, um membro paga uma despesa, a despesa se divide entre quem participou, e cada um sabe o próprio saldo. Quem deve paga, e o saldo acerta.

Sem inventar, item por item: o dinheiro é `Decimal` do JSON ao banco, e um valor com três casas, zero ou `NaN` é recusado na entrada, com `422`; o centavo que sobra tem dono, por uma regra escrita; uma despesa grava tudo ou nada, porque quem delimita a transação é o service; o saldo é calculado pelo banco, em duas consultas, e não cresce com o grupo; duas quitações ao mesmo tempo não pagam a mesma dívida duas vezes. E **o 2N+1 morreu**, com uma regra que impede a volta dele e um teste que conta as consultas. Era o item 2 da entrada 2 do `ERRATA.md`. Das três limitações herdadas do capítulo 1, sobra uma.

O resto do que fica de pé está na [lição 12](theory/12-o-que-ainda-nao-resolve.md), cada item com endereço: o saldo recalculado a cada request (capítulo 7), uma lista de decisões que não são defeitos, e o inventário do capítulo 4, que continua valendo.

E a que sobra é a mais grave, porque agora tem dinheiro no meio. **Hoje, qualquer um quita a dívida de qualquer um.** O `POST /groups/{id}/settlements` aceita qualquer pagador e qualquer recebedor. Qualquer cliente registra que o Bruno pagou a Ana, sem o Bruno saber, ou lança uma despesa de R$ 500 "paga pela Ana" sem ser a Ana. O service confere quem é **membro**. Ninguém confere quem está **pedindo**, porque ninguém se identifica. Saber quem está do outro lado da request, e o que essa pessoa pode fazer em cada grupo, é o capítulo 6.
