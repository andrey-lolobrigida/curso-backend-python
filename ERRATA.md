# Errata

Este curso usa branches como checkpoints de capítulo (`chapter-00`,
`chapter-01`, ...). Quando um bug é encontrado em um capítulo antigo, nós
**corrigimos para frente** (na `main` e na branch de trabalho atual) e
**documentamos para trás** (aqui). Reescrever branches antigas quebraria o
histórico que você pode ter baixado — então elas ficam como estão, e este
arquivo é o mapa dos problemas conhecidos.

Formato de cada entrada:

- **Capítulo afetado:** qual branch/tag contém o problema
- **O que está errado:** descrição honesta do bug ou erro
- **Correção:** o que mudar (com link para o commit corretivo na main)

---

> **O arco foi renumerado em outubro de 2026.** O capítulo 4 planejado prometia coisas demais, e virou dois: 4 "O banco de dados, de verdade" (Postgres, pool, índices, transações, a reserva dupla) e 5 "Relações e dinheiro" (relações, N+1, `Decimal`, SQL puro). Todos os capítulos seguintes andaram uma casa: autenticação virou o 6, cache o 7, filas o 8, observabilidade o 9, testes o 10 e deploy o 11. A `main` já usa os números novos, inclusive nas entradas abaixo. **Se você está numa branch de `chapter-00` a `chapter-03`, as remissões usam a numeração antiga.** Lá, "capítulo 4" para N+1 ou dinheiro quer dizer 5, e qualquer capítulo de 5 em diante é o número seguinte.

## 1. O gancho do fim do capítulo 1 é falso

- **Capítulo afetado:** 1 (`chapter-01`, tag `v-chapter-01`) — `chapters/01-arquitetura-em-camadas/README.md`, seção "Ao terminar".
- **O que está errado:** a frase *"nosso servidor atende uma pessoa de cada vez"*. Não atende. Rotas escritas com `def` (que é o caso de **todas** as rotas do FairFare no capítulo 1) não rodam no event loop: o Starlette as despacha para um threadpool. Medido: 10 requests simultâneas de 1 segundo terminam em **1,02s** numa rota `def` — e em **10,03s** numa rota `async def` que bloqueia. A frase descrevia com precisão o caso oposto ao nosso.
- **Correção:** o texto do README foi trocado na `main` pela versão verdadeira — o teto real são **40 threads** (o limite do threadpool do `anyio`), e o custo é **uma thread por request**. Medido: 40 requests simultâneas levam 1,05s; 41 levam 2,03s, porque a última espera uma vaga abrir.
- **Onde ver a medição inteira:** capítulo 2, lição 01 (`chapters/02-python-assincrono/theory/01-a-mentira-do-capitulo-1.md`), que abre reproduzindo o erro com a bancada em `chapters/02-python-assincrono/bancada/`.

## 2. Três limitações do capítulo 1 que não foram declaradas

- **Capítulo afetado:** 1 (`chapter-01`, tag `v-chapter-01`).
- **O que está errado:** o código entregue no capítulo 1 tem três problemas conhecidos, e o material do capítulo não avisava sobre nenhum deles. Isso era consequência de uma política de ensino que o curso **abandonou em 2026-08-15** (a de plantar defeitos para que fossem sentidos depois). Um curso que entrega código precisa poder ser usado como referência; para isso, o que se sabe que está errado tem que estar escrito.

  | # | Onde | O quê | Resolvido no |
  |---|---|---|---|
  | 1 | `app/services/booking.py::BookingService.create` | Verifica conflito de horário e **depois** insere, sem transação nem lock. Duas requests simultâneas para o mesmo horário passam as duas pela verificação e gravam as duas (*check-then-act*). | capítulo 4, lições 10 e 11 (tags `v-cap04-licao10` e `v-cap04-licao11`) |
  | 2 | `app/services/booking.py::_to_out` | Cada reserva listada busca usuário e recurso em consultas separadas: `GET /bookings` faz **2N+1** idas ao banco (problema N+1). | capítulo 5, lição 03 (tag `v-cap05-licao03`) |
  | 3 | todas as rotas | Não existe autenticação. `POST /bookings` aceita qualquer `user_id`; qualquer pessoa reserva ou cancela no nome de qualquer outra. | capítulo 6, lições 05, 11 e 12 (tags `v-cap06-licao05`, `v-cap06-licao11`, `v-cap06-licao12`) |

- **Correção:** **o código não muda.** Consertar qualquer um dos três exigiria conceitos que o curso ainda não ensinou (transações, eager loading, autenticação) — e ensiná-los fora de hora é pior que declará-los. O que mudou é que agora eles estão escritos: aqui, numa seção nova do README do capítulo 1, e em detalhe na lição 11 do capítulo 2 (`chapters/02-python-assincrono/theory/11-o-que-ainda-nao-resolve.md`), com o mecanismo de cada um e o que o capítulo 2 mudou neles.

## 3. O fuso horário é descartado em silêncio

- **Capítulo afetado:** 1 a 3 (`chapter-01` a `chapter-03`, tags `v-chapter-01` a `v-chapter-03`), em `app/models/booking.py`, cujas colunas `starts_at` e `ends_at` são `DateTime()` sem fuso, gravadas no SQLite.
- **O que está errado:** um horário com fuso é aceito e gravado sem ele. `POST /bookings` com `"starts_at": "2030-01-01T10:00:00-03:00"` responde `201` e devolve `"2030-01-01T10:00:00"`: o `-03:00` sumiu. Uma segunda reserva para `"2030-01-01T13:00:00Z"`, que é **o mesmo instante**, também recebe `201`, e não `409`. É um segundo caminho para a reserva dupla da entrada 2, e nenhuma transação o conserta, porque para o banco 10:00 e 13:00 são horários diferentes. E misturar um horário com fuso e outro sem (`starts_at` com `-03:00`, `ends_at` sem fuso) derruba a request com 500: o Python se recusa a comparar os dois. Por fim, o `DELETE /bookings/{id}` decide se a reserva já começou comparando o horário gravado com `datetime.now()`, o relógio **local** da máquina, sem fuso. Numa máquina em `-03:00`, uma reserva marcada para as 10h UTC continua contando como futura, e cancelável, por três horas depois de ter começado.
- **Correção:** capítulo 4, lição 04 (tag `v-cap04-licao04`). As colunas viram `timestamptz`, que guarda um instante, e não um horário de parede. A migração escreve explicitamente que os horários antigos estavam em UTC. Um horário que chega sem fuso passa a ser lido como UTC, por decisão escrita no schema. O `cancel` passa a comparar com `datetime.now(UTC)`. Medido no capítulo 4: no PostgreSQL, a mesma request deixa de ser engolida e vira um erro (500) até a correção, o que é melhor do que um sucesso falso.

## 4. A injeção de SQL foi ensinada antes do prometido

- **Capítulo afetado:** 1 (`chapter-01`, tag `v-chapter-01`) — `chapters/01-arquitetura-em-camadas/theory/05-persistencia-sqlite.md`, a frase que dá à injeção de SQL "um lugar cativo no capítulo 6". A lição segue igual, a menos do número do capítulo, em todas as branches até a `chapter-05`. Nas tags `v-chapter-01` a `v-chapter-03`, pela numeração antiga, a frase diz "capítulo 5".
- **O que está errado:** a promessa aponta o capítulo de autenticação, e o assunto não esperou por ele. A injeção foi mostrada ao vivo no capítulo 5, lição 10 (`chapters/05-relacoes-e-dinheiro/theory/10-quando-descer-para-sql-puro.md`, seção "O perigo: injeção de SQL"), com a bancada `injecao.py`. O capítulo 6 só a cita de passagem, como um dos jeitos de um banco vazar (lições 02 e 04).
- **Correção:** a frase, na `main`, passa a apontar a lição 10 do capítulo 5. Trocada no fechamento do capítulo 6 (tag `v-chapter-06`).

## 5. O material antigo que chama a API para de funcionar na `main`

- **Capítulo afetado:** 1 a 5 (`chapter-01` a `chapter-05`, tags `v-chapter-01` a `v-chapter-05`): todo material que fala com o FairFare pela API. São os `curl` das lições e estas bancadas:
  - `chapters/02-python-assincrono/bancada/carga.py`, que a lição 09 do capítulo 2 aponta para o `GET /bookings`;
  - em `chapters/03-entre-o-cliente-e-o-router/bancada/`: o `carga.py` (lições 02, 05, 08 e 11 do capítulo 3, e 05 do capítulo 4), o `espiao.py` e o `proxy.py` (que repassam ao app o `/users` das lições 01 e 06) e a `pagina/index.html`;
  - `chapters/04-o-banco-de-dados-de-verdade/bancada/corrida.py`;
  - `chapters/05-relacoes-e-dinheiro/bancada/quitacao.py` e `conta_consultas.py`.

  Ficam de fora as que falam com um servidor próprio (`servidor.py`, `eco.py`, `asgi_cru.py`, `cebola.py`), as que falam direto com o banco, e o `Caddyfile` e o `nginx.conf`, que o curso só lê.
- **O que está errado:** desde o capítulo 6, a API pede senha e crachá. Desde a lição 03, o cadastro exige `senha`. Desde a lição 05, toda rota exige `Authorization: Bearer <token>`, menos `POST /users` e `POST /auth/login`. O material antigo faz requests sem token: quem só lê leva `401`, quem começa cadastrando gente leva `422`, porque falta a `senha`. A lição 13 do capítulo 6 mostra três dessas bancadas quebrando (`chapters/06-autenticacao-e-seguranca/theory/13-o-que-ainda-nao-resolve.md`, seção 5).
- **Correção:** **nenhuma no código nem no texto.** Reescrever material publicado é mexer no que você pode ter baixado. A regra: **o material de um capítulo roda na tag dele.** Os capítulos 1 a 3 usam o SQLite (`fairfare.db`), que as migrações do PostgreSQL nunca tocaram: `git checkout v-chapter-03`, `uv sync`, `uv run alembic upgrade head`. Os capítulos 4 e 5 usam o mesmo PostgreSQL de dev da `main`, então desça o banco **antes** do `checkout`, ainda na `main`: `uv run alembic downgrade 2db1b72e440a` para a `v-chapter-05`, e `uv run alembic downgrade 257143851bec` para a `v-chapter-04`. Descer apaga: as sessões, as senhas e, até a `v-chapter-04`, também os grupos e as despesas. O README do capítulo 6 conta o preço de cada degrau. E o `fairfare_test` também precisa de cuidado: antes de rodar o `pytest` numa tag mais antiga, jogue-o fora (`docker compose exec postgres psql -U fairfare -d postgres -c 'DROP DATABASE fairfare_test'`), e a suíte o recria. Sem isso, todo teste dá erro (entrada 7).
- **Uma ressalva que muda de endereço:** o capítulo 3, lição 06 (`chapters/03-entre-o-cliente-e-o-router/theory/06-o-proxy-reverso.md`), avisou que o `proxy.py` da bancada funde os `set-cookie` repetidos num só, e chamou isso de "errado assim que o capítulo 6 trouxer login por cookie e este arquivo for reaproveitado". O login veio por header, não por cookie, e o FairFare continua sem mandar `set-cookie`. A ressalva continua valendo para quem um dia reaproveitar o proxy com cookie.

## 6. O `Authorization` não é credencial no CORS

- **Capítulo afetado:** 3 (`chapter-03`, tag `v-chapter-03`) — `chapters/03-entre-o-cliente-e-o-router/theory/04-o-browser-tambem-esta-no-meio.md`, seção "Por que não `*`". A lição segue igual até a `chapter-05`.
- **O que está errado:** o parêntese "(cookie, `Authorization`)" põe o header `Authorization` entre as credenciais de que o CORS fala. O termo é mais estreito. Para o browser, credencial é o que **ele mesmo** anexa à request: cookies, a autenticação HTTP que ele guarda e certificados de cliente. Um `Authorization` que o JavaScript da página põe à mão é só mais um header: vai junto até com `credentials: "omit"`, e não depende do `allow_credentials`. Por tabela, o "não" ao `*` para "uma API que um dia terá login" vale para login por cookie. Com o token no header, que é o caso do FairFare, o `*` faria menos estrago do que a lição deu a entender: o site alheio leria a resposta, mas sem o token, então só o que qualquer anônimo lê. A armadilha do `*` com `allow_credentials=True` (o Starlette passa a ecoar qualquer origem) continua verdadeira.
- **Correção:** nenhuma no texto do capítulo 3. A conta certa está no capítulo 6, lição 10 (`chapters/06-autenticacao-e-seguranca/theory/10-onde-o-cracha-mora-no-browser.md`), na seção "Por que não `allow_credentials`" e no parágrafo "E o `*`?". Lá também está por que o FairFare mantém a origem explícita mesmo assim.

## 7. O `fairfare_test` também não viaja no tempo

- **Capítulo afetado:** 5 (`chapter-05`, tag `v-chapter-05`) — `chapters/05-relacoes-e-dinheiro/README.md`, seção "O banco não viaja no tempo com você", a frase "O `fairfare_test` não precisa de nada disso".
- **O que está errado:** a suíte recria as tabelas a cada rodada, mas só as que os models **daquele commit** conhecem. O `drop_all` de um commit mais antigo não sabe das tabelas mais novas, e elas têm chave estrangeira para `users`. Medido: a árvore da `v-chapter-04` contra o `fairfare_test` deixado pela `main` dá `30 errors`, todos com `cannot drop table users because other objects depend on it` (`constraint expenses_paid_by_fkey on table expenses depends on table users`). O mesmo acontece dentro do capítulo 5, ao voltar para antes da lição 04, e dentro do 6, ao voltar para antes da lição 04 (a tabela `sessions`).
- **Correção:** a frase foi trocada na `main`, no README do capítulo 5 e no do 6, pelo conserto: jogar fora o `fairfare_test` antes de rodar a suíte num commit mais antigo (`docker compose exec postgres psql -U fairfare -d postgres -c 'DROP DATABASE fairfare_test'`). O `conftest.py` o recria na rodada seguinte. Trocada no fechamento do capítulo 6 (tag `v-chapter-06`).

## 8. Quitar para si mesmo não é mais barrado no schema

- **Capítulo afetado:** 5 (`chapter-05`, tag `v-chapter-05`) — `chapters/05-relacoes-e-dinheiro/theory/11-quitacoes-dois-lados-dois-cadeados.md`, a frase "Quitar para si mesmo é `422`, barrado no schema".
- **O que está errado:** na tag do capítulo 5, nada. Na `main`, a frase envelheceu. Desde a lição 12 do capítulo 6, quem recebe vem do token, e o corpo traz um id só: o schema não tem mais com o que comparar. A checagem foi para o `SettlementService`, com o mesmo `422` e a mesma mensagem. O `CHECK` do banco continua de guarda embaixo.
- **Correção:** nenhuma no texto do capítulo 5. A mudança está contada no capítulo 6, lição 12 (`chapters/06-autenticacao-e-seguranca/theory/12-permissoes-por-grupo.md`).

## 9. O checkpoint do capítulo 3 aponta capítulos errados para o rate limiter

- **Capítulo afetado:** 3 — `chapters/03-entre-o-cliente-e-o-router/theory/12-o-que-ainda-nao-resolve.md`, o checkpoint do fim, que diz em que capítulo morre cada problema do rate limiter: "dois no 6, um no 10". Na `chapter-03`, pela numeração antiga, estava certo. A renumeração de outubro trocou os números nos itens da lição e esqueceu o checkpoint, e ele ficou errado nas branches `chapter-04` e `chapter-05`.
- **O que está errado:** os itens da própria lição dizem que dois problemas morrem no capítulo 7 e um no 11. O checkpoint mandava dois para o capítulo 6, que não mexe no limitador.
- **Correção:** o checkpoint passa a dizer "dois no 7, um no 11" na `main`. Trocado no fechamento do capítulo 6 (tag `v-chapter-06`).
