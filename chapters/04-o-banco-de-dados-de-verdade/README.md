# Capítulo 4 — O banco de dados, de verdade

Três capítulos inteiros, e o banco do FairFare foi um arquivo: `fairfare.db`, na raiz do projeto. Este capítulo troca o arquivo por um servidor. Um PostgreSQL, rodando num container, com senha, com teto de conexões e com outros clientes além do seu app.

E a troca muda mais do que a URL. **Um banco de verdade não é um lugar onde você guarda coisas. É um programa que decide.** Ele decide quantos entram, em que ordem, quem espera quem. E o mais importante que ele sabe fazer é **dizer não**: não para a 101ª conexão de um servidor que só aceita 100, não para a segunda reserva da mesma quadra no mesmo horário.

É por isso que este capítulo fecha a dívida mais antiga do curso. A reserva dupla nasceu no capítulo 1, ganhou nome no capítulo 2 e mora no `ERRATA.md` desde então. Aqui ela é reproduzida, contada, atacada com transação, com isolamento, com cadeado, e por fim morre do único jeito que não depende de combinado: com a regra escrita dentro do banco.

## Pré-requisitos

O capítulo 3 completo (ou `git checkout v-chapter-03`, `uv sync`).

E uma coisa nova para instalar: **Docker, com o Compose.** O PostgreSQL do curso roda num container, e só ele; o FairFare continua rodando fora do Docker, com `uv run`, do jeito de sempre. A [lição 01](theory/01-um-banco-que-e-um-servidor.md) explica por que, e o que fazer se a porta 5432 já estiver ocupada na sua máquina.

Com o Docker instalado, a partir da lição 01:

```bash
uv sync
docker compose up -d --wait
```

O `--wait` só devolve o terminal quando o banco já aceita conexões. **A partir da lição 03, o `pytest` precisa do compose de pé**: a suíte passa a rodar no PostgreSQL, num banco só dela, o `fairfare_test`. Sem o banco, o `conftest.py` para tudo e manda você subir.

As dependências novas (`asyncpg` para o app, `psycopg` para o Alembic) entram na lição 02, com `uv add`, e a lição explica por que são duas.

## As lições

Em ordem. Cada uma tem uma ideia só e termina com um checkpoint:

| # | Lição | A ideia única |
|---|-------|---------------|
| 01 | [Um banco que é um servidor](theory/01-um-banco-que-e-um-servidor.md) | O SQLite é uma planilha; o PostgreSQL é um cartório, com guichês contados. Sobe o banco, o app não muda uma linha |
| 02 | [A troca](theory/02-a-troca.md) | Duas URLs, dois drivers, poucas linhas de diff, e o primeiro `500`: o banco que grita onde o SQLite engolia |
| 03 | [O teste que passava no banco errado](theory/03-o-teste-que-passava-no-banco-errado.md) | Um teste verde só garante alguma coisa no banco onde ele rodou. A suíte vai para o `fairfare_test` |
| 04 | [Que horas são?](theory/04-que-horas-sao.md) | Horário de parede não é instante: `timestamptz`, e a suposição sobre o passado escrita na migração |
| 05 | [O pool encontra o teto](theory/05-o-pool-encontra-o-teto.md) | 15 por processo, 100 no servidor, e a conta que fecha: `workers × (pool + overflow) ≤ teto − reserva` |
| 06 | [Índices e o `EXPLAIN`](theory/06-indices-e-o-explain.md) | Um milhão de reservas, e como perguntar ao próprio banco o que ele vai fazer, em vez de chutar |
| 07 | [Reproduzindo a corrida](theory/07-reproduzindo-a-corrida.md) | A reserva dupla, no seu terminal, quantas vezes você quiser. Primeiro ver, depois consertar |
| 08 | [Transação não é cadeado](theory/08-transacao-nao-e-cadeado.md) | "Põe numa transação" não basta: em `READ COMMITTED`, o check-then-act passa duas vezes |
| 09 | [Níveis de isolamento](theory/09-niveis-de-isolamento.md) | Subir a escada até `SERIALIZABLE` fecha a corrida, e cobra em abortos e retry obrigatório |
| 10 | [Trancando a porta certa](theory/10-trancando-a-porta-certa.md) | `FOR UPDATE` no recurso disputado, nem mais nem menos, e a corrida acaba. Enquanto todo mundo combinar |
| 11 | [A regra mora no banco](theory/11-a-regra-mora-no-banco.md) | Uma `EXCLUDE` constraint: o banco recusa a sobreposição, venha a reserva de onde vier |
| 12 | [O que este código ainda não resolve](theory/12-o-que-ainda-nao-resolve.md) | O inventário das limitações declaradas, com o capítulo em que cada uma morre, e um item riscado |

A lição 11 é a mais longa do capítulo, perto de 17 minutos. Não dá para cortar no meio: a constraint, a migração que falha, a tradução do erro e o índice novo são a mesma ideia vista de quatro lados.

## Este capítulo se acompanha com o banco aberto

O capítulo 2 se acompanhava medindo. O 3, com três terminais. Este se acompanha com **um `psql` aberto** ao lado do app. Metade das perguntas do capítulo só o próprio banco responde: quantas conexões estão abertas, que plano ele escolheu, quem está esperando quem.

```bash
docker compose exec postgres psql -U fairfare -d fairfare
```

Na lição 10, são **três** `psql` lado a lado: um tranca a quadra, outro espera o cadeado, e o terceiro pergunta à `pg_stat_activity` quem está esperando quem.

### A bancada

A pasta [`bancada/`](bancada/) tem os instrumentos de medição do capítulo. **Nada dali faz parte do FairFare.** Todos falam com o PostgreSQL do `compose.yaml`.

| Script | Lição | O que mostra |
|---|---|---|
| `pool.py` | 05 | o pool do app estourando (`pool`) e a soma dos pools estourando o servidor (`servidor`) |
| `seed.sql` | 06 | um milhão de reservas com `generate_series`, sem sobreposição |
| `explain.sql` | 06, 11 | o plano da consulta do `find_overlapping`, nas duas formas |
| `corrida.py` | 07, 10, 11 | N reservas idênticas ao mesmo tempo, pelo uvicorn de verdade; conta quantas passaram |
| `transacao.py` | 08 | duas transações fazendo check-then-act em `READ COMMITTED`: as duas gravam |
| `isolamento.py` | 09 | o mesmo experimento em cada nível de isolamento; o falso positivo do `SERIALIZABLE`; o retry |
| `sobreposicoes.sql` | 11 | as reservas que se sobrepõem, antes de a constraint existir (limpar é decisão humana) |

**Um aviso antes de rodar o `seed.sql`: ele apaga os dados do banco de dev.** Começa com um `TRUNCATE` em usuários, recursos e reservas, e deixa um milhão de reservas no lugar. O `fairfare_test` não é tocado. Se você tem no banco de dev alguma coisa que quer guardar, não rode. O número de linhas vai na linha de comando, e sem ele o script falha:

```bash
docker compose exec -T postgres psql -U fairfare -d fairfare -v linhas=1000000 \
  < chapters/04-o-banco-de-dados-de-verdade/bancada/seed.sql
```

O comando de cada uma das outras peças está na lição que a usa (e no cabeçalho do próprio script).

## Como percorrer

Cada lição corresponde a um commit, marcado com uma tag de nome previsível:

```bash
git log --oneline --reverse v-chapter-03..v-chapter-04   # os commits do capítulo
git tag -l "v-cap04-licao*"                              # as tags, uma por lição
```

Para ver o app num ponto específico do capítulo:

```bash
git checkout v-cap04-licao10         # o FairFare com o cadeado, antes da constraint
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Isso te coloca em **detached HEAD**. O git vai avisar com um parágrafo alarmado, e o [README do capítulo 1](../01-arquitetura-em-camadas/README.md#o-aviso-assustador-que-o-git-vai-te-dar) explica com calma o que isso significa e como voltar.

### O banco não viaja no tempo com você

Este é o aviso novo deste capítulo, e ele morde. O `git checkout` troca o código. **Não troca o banco.** O PostgreSQL mora num volume do Docker, fora do repositório, e guarda o estado da última migração que você rodou.

Se você terminou o capítulo e volta para a lição 04, o banco de dev está **à frente** do código: tem o índice da lição 06 e a constraint da lição 11, que o código da lição 04 nem conhece. Pior: o Alembic daquela tag não tem os arquivos das migrações mais novas, e não sabe nem desfazê-las.

Por isso, **antes** do `checkout`, ainda no código mais novo, desça o banco até a migração da lição para onde você vai:

| Para ver as lições | O banco tem que estar em |
|---|---|
| 02 e 03 | `4b1f163d18ea` (as reservas do capítulo 1) |
| 04 e 05 | `12388da2dbe5` (reservas com fuso) |
| 06 a 10 | `735b317a52e9` (o índice) |
| 11 em diante | `257143851bec` (a constraint), que é o `head` |

```bash
uv run alembic downgrade 735b317a52e9   # ainda na chapter-04
git checkout v-cap04-licao10
```

(A lição 01 nem usa o PostgreSQL: o app dela ainda fala com o `fairfare.db`.)

Se o banco se enrolou, o caminho curto é jogar fora e recomeçar:

```bash
docker compose down -v               # o -v apaga o volume: o banco de dev inteiro
docker compose up -d --wait
uv run alembic upgrade head
```

Os dois caminhos têm preço. O `downgrade` de um banco com um milhão de reservas demora. O `down -v` apaga tudo, inclusive o que você criou à mão. O `fairfare_test` não precisa de nada disso: a suíte recria as tabelas dos models a cada rodada.

## Os exercícios

Três blocos em [`exercises/`](exercises/README.md): a migração que mudou o passado, o banco sob carga e a concorrência.

Quase tudo ali está **quebrado de propósito**, e o enunciado diz isso em letras garrafais: o bloco 1, o 2.2, o 2.3, o 3.1 e o 3.2. A exceção é a 2.1, um `count()` que **funciona, mas do jeito caro**: a resposta sai certa, o preço é que está errado.

```bash
docker compose up -d --wait
uv run pytest chapters/04-o-banco-de-dados-de-verdade/exercises/bloco1 -v      # 2 falharam
uv run pytest chapters/04-o-banco-de-dados-de-verdade/exercises/bloco2 -v -s   # 1 passou, 3 falharam
uv run pytest chapters/04-o-banco-de-dados-de-verdade/exercises/bloco3 -v      # 2 falharam
```

O teste que passa no bloco 2 é parte do exercício: ele confere que o resultado está certo, e o defeito da 2.3 é justamente um resultado certo pelo caminho errado.

Nenhum bloco importa `app/`. Cada um cria as próprias tabelas no `fairfare_test` e as apaga no fim; o banco de dev do FairFare não é tocado. As soluções, com o raciocínio de cada conserto (por que um fuso com nome e não `-03:00`, por que a espera do retry precisa variar, por que a ordem dos locks resolve o deadlock), estão em [SOLUTIONS.md](SOLUTIONS.md).

## Como rodar o app

```bash
uv sync
docker compose up -d --wait
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Documentação interativa em `http://localhost:8000/docs`. E a rede de segurança, que agora roda no PostgreSQL de verdade:

```bash
uv run pytest
```

## O diff deste capítulo

Diffs são material de leitura neste curso. O capítulo inteiro, mudança a mudança: o `git log` acima, ou [a comparação no GitHub](https://github.com/andrey-lolobrigida/curso-backend-python/compare/v-chapter-03...v-chapter-04). Lá os commits vêm do mais novo para o mais antigo; leia de baixo para cima.

Os dois primeiros commits da comparação não são lições. São correções que entraram na `main` antes do capítulo começar, e por isso aparecem no intervalo entre as duas tags:

- **A entrada 3 do `ERRATA.md`**: o fuso horário descartado em silêncio nos capítulos 1 a 3.
- **A renumeração do arco**: o capítulo 4 planejado prometia coisas demais e virou dois (4, o banco; 5, relações e dinheiro). Os capítulos seguintes andaram uma casa, e as remissões em todo o curso foram atualizadas.

Das lições, cinco tocam `app/`:

- **Lição 02**: `app/database.py` troca o `sqlite+aiosqlite` pelas duas URLs do PostgreSQL.
- **Lição 04**: `starts_at` e `ends_at` viram `timestamptz` no model, a migração escreve que o passado estava em UTC, e o schema passa a ler horário sem fuso como UTC.
- **Lição 06**: um índice em `(resource_id, starts_at)`, no model e numa migração.
- **Lição 10**: `get_for_update` no repository de recursos, e o service trancando a quadra antes de verificar.
- **Lição 11**: a `EXCLUDE` constraint (e um `CHECK` que fecha a brecha da reserva de duração zero) no model e numa migração escrita à mão, a tradução do erro dela em `409`, o cadeado da lição 10 saindo, e o `find_overlapping` reescrito na forma que o índice novo entende.

Repare no que **não** está na lista. A lição 03 mexe só em `tests/` e no `pyproject.toml`; a 01, só no `compose.yaml`. E a lição 05, a do pool, não muda o `app/database.py`: a conta mostrou que os números de lá já cabiam. Uma lição inteira sobre pool que termina sem mudar o pool é uma das mais importantes do capítulo.

## Ao terminar

O FairFare mora num PostgreSQL. Os testes rodam num banco de verdade, o mesmo tipo de banco do app, e não num SQLite que concordava com tudo.

Sem inventar, item por item: um horário chega com fuso e é gravado como o instante que ele é; o pool tem uma conta escrita por trás dos números, e você sabe dizer o que acontece se alguém mexer em qualquer um deles; o `find_overlapping` usa um índice, e você sabe ler o `EXPLAIN` que prova isso. E **a reserva dupla morreu**, com a regra escrita no próprio banco. Os dois caminhos que ela tinha, a corrida (entrada 2 do `ERRATA.md`) e o fuso descartado (entrada 3), estão fechados.

Com uma honestidade que a [lição 11](theory/11-a-regra-mora-no-banco.md) mediu e a 12 repete: num empate de verdade, com muita gente gravando no mesmo instante, as perdedoras podem, raramente, receber `500` em vez de `409`, e quase meio minuto depois. É um deadlock que o banco detecta e desfaz. Elas não ganham a reserva, e ninguém ganha duas. A regra não falha. A resposta é que fica feia, e isso fica declarado até o capítulo 9.

O resto do que fica de pé está na [lição 12](theory/12-o-que-ainda-nao-resolve.md), cada item com endereço e com o capítulo em que morre: o `GET /bookings` com suas 2N+1 consultas, a falta de autenticação, a senha no repositório, o Docker como caixa fechada, a migração que fecha a tabela. E o inventário do capítulo 3, que este capítulo não encostou.

Até aqui, o FairFare só reserva. Falta a outra metade do nome: **dividir a conta.** E ela traz três coisas que este capítulo deixou na porta. Relações entre tabelas, de verdade, com usuários em grupos e despesas entre eles. A cobrança do N+1, que espera desde o capítulo 1 e esgotou o pool na lição 05. E dinheiro, que não é `float`. O capítulo 5 é sobre isso.
