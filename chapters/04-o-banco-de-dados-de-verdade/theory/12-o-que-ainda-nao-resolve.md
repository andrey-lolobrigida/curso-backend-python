# Lição 12 — O que este código ainda não resolve

Os capítulos 2 e 3 fecharam com uma lição igual a esta, e pelo mesmo motivo: **um curso que entrega código tem uma dívida com quem vai ler esse código.** Se eu sei que tem um defeito, eu te conto.

Este capítulo trocou o banco inteiro. Pôs um servidor no lugar de um arquivo, um pool contra um teto, um índice, uma constraint. Cada peça chegou com algum pedaço faltando, e cada pedaço foi declarado no fim da lição onde apareceu, na seção "O que fica declarado". Esta lição junta tudo numa lista só, com endereço e com o capítulo em que morre.

Nada aqui é novidade. O valor está em ver junto.

E, desta vez, a lista tem uma coisa que as outras não tinham: um item **riscado**. A reserva dupla morreu. Ela tem uma seção própria no fim.

## 1. `GET /bookings` ainda faz 2N+1 consultas

**Onde:** `app/services/booking.py`, em `BookingService._to_out`.

```python
    async def _to_out(self, booking: Booking) -> BookingOut:
        user = await self.users.get(booking.user_id)
        resource = await self.resources.get(booking.resource_id)
```

Uma consulta para a lista, e duas para cada reserva dela. É o N+1 do capítulo 1, com endereço desde a lição 11 do capítulo 2.

**Como se manifesta:** neste capítulo ele deixou de ser só uma conta. A lição 05 mediu: com 2002 reservas no banco, uma única request levou quase um segundo e fez 4005 consultas, **segurando uma conexão do pool** do começo ao fim. Foi esse endpoint que esgotou o pool. E a lição 05 provou que pool maior não ajuda: o dobro de conexões deu os mesmos 120 ok. A causa é o endpoint lento, não o tamanho do funil.

**Morre no:** capítulo 5.

## 2. Ainda não existe autenticação

**Onde:** todas as rotas. `POST /bookings` aceita qualquer `user_id`. O `user_id` é uma afirmação do cliente, e ninguém confere.

Nada neste capítulo mexeu nisso. A constraint da lição 11 garante que uma quadra não tem duas reservas no mesmo horário. Ela não sabe **quem** reservou, nem se essa pessoa podia.

**Morre no:** capítulo 6.

## 3. A configuração do banco está escrita no código

**Onde:** em três arquivos.

```python
# app/database.py
DATABASE_URL = "postgresql+asyncpg://fairfare:fairfare@localhost:5432/fairfare"
SYNC_DATABASE_URL = "postgresql+psycopg://fairfare:fairfare@localhost:5432/fairfare"
```

```yaml
# compose.yaml
      POSTGRES_USER: fairfare
      POSTGRES_PASSWORD: fairfare
```

E o `tests/conftest.py` tem mais três URLs com o mesmo `fairfare:fairfare`: duas para o `fairfare_test` e uma para o banco `postgres`, de onde ele é criado.

**Como se manifesta:** de três jeitos.

- **A senha está em texto puro, no repositório.** Serve para desenvolvimento local, e só (lição 01).
- **Duas URLs para o mesmo banco** (lição 02). Uma para o app, uma para o Alembic. Se alguém trocar uma e esquecer a outra, o Alembic migra um banco e o app fala com outro.
- **O app conecta como superusuário.** A imagem do Postgres dá esse poder ao `POSTGRES_USER`. A lição 05 mostrou o preço: o Postgres guarda 3 vagas de emergência para superusuário (`superuser_reserved_connections`), e o app, sendo superusuário, entra por elas também. No pico, o `psql` do admin ficou trancado do lado de fora. A reserva só protege o admin se o app **não** for superusuário.

O conserto dos três é o mesmo pacote: configuração por ambiente, segredos fora do repositório, e um usuário do banco só para o app, sem superpoder.

**Morre no:** capítulo 11.

## 4. O Docker é uma caixa fechada

**Onde:** `compose.yaml`. O comentário do topo já diz:

```yaml
# O PostgreSQL do curso, e só ele. O app continua rodando fora do Docker (cap. 4, lição 01).
```

**Como se manifesta:** você usa o Docker sem saber o que é uma imagem, um volume ou uma rede por dentro. E o FairFare continua rodando fora dele, com `uv run uvicorn`, do jeito de sempre. Foi de propósito: este capítulo precisava de um Postgres, não de uma aula de Docker.

**Morre no:** capítulo 11.

## 5. A migração da constraint fecha a tabela

**Onde:** a migração `reserva nao sobrepoe` (`alembic/versions/257143851bec_reserva_nao_sobrepoe.py`).

**Como se manifesta:** a lição 11 mediu num milhão de linhas. A migração levou 51 s. E, no meio dela, um `SELECT` de **uma** reserva esperou 46 s. O `ADD CONSTRAINT` pega o `AccessExclusiveLock`, que barra até leitura. No banco de dev, tudo bem. Em produção, seria quase um minuto de FairFare fora do ar.

Mudar o schema sem parar o app é um assunto inteiro. Não foi tratado aqui.

**Morre no:** capítulo 11.

## 6. Um empate de verdade pode virar `500`

**Onde:** `BookingRepository.create`, no `commit()`. O repository traduz uma violação da constraint (SQLSTATE `23P01`) em `BookingOverlapError`, e o resto sobe como veio.

**Como se manifesta:** quando muita gente grava horários sobrepostos no **mesmo** instante, duas transações podem ficar esperando uma pela outra. O PostgreSQL detecta o ciclo, um *deadlock*, e aborta uma delas com SQLSTATE `40P01`. Isso não é `IntegrityError`, então ninguém traduz, e a resposta é `500`, não `409`.

A lição 11 reproduziu. Com 10 pessoas ao mesmo tempo, não apareceu em 30 rodadas. Com 30, apareceu em 2 de 10. E, quando apareceu, levou a rodada inteira: as 29 perdedoras receberam `500`, e a resposta demorou quase meio minuto. Atirando `INSERT`s direto no banco, 108 de 2000.

Repare no que **não** falha: a regra. Zero reservas duplicadas, em todas as rodadas. O banco não deixou passar nenhuma. O que falha é a **resposta**: o cliente recebe um erro feio em vez de um "esse horário já tem dono". Tratar falha transitória com retry é assunto de quem lida com falhas.

E há um primo barulhento: cada `409` que vem da constraint vira uma linha `ERROR` no log do PostgreSQL. É o banco trabalhando, mas suja o log. Saber o que merece alarme também é desse capítulo.

**Morre no:** capítulo 9.

## 7. Os testes

**Onde:** `tests/conftest.py`.

Duas coisas declaradas na lição 03:

- **A limpeza é por `TRUNCATE`**, antes de cada teste. Funciona, e é simples. Não é a única estratégia, nem a mais rápida.
- **O `fairfare_test` nasce do `create_all`, não das migrações.** Se uma migração divergir dos models, a suíte não percebe. A lição 11 tornou isso mais delicado: a constraint está no model **e** numa migração escrita à mão, e só a do model chega aos testes. Hoje as duas batem.

E uma terceira, que nem é limitação, é condição: **a suíte precisa do compose de pé.** Sem o banco, o `conftest.py` para tudo e manda subir.

**Morre no:** capítulo 10, que discute a estratégia de testes em si.

## 8. O autogenerate não é de confiança cega

**Onde:** `alembic revision --autogenerate`, em qualquer migração daqui para a frente.

Dois furos, os dois da lição 11:

- **Ele não enxerga a `ExcludeConstraint`.** Quem mudar a constraint no model escreve a migração à mão.
- **Ele quer apagar a `bancada_reservas`.** As lições 08 e 09 criaram essa tabela no banco de dev, sem model nenhum. O autogenerate compara o banco com os models e conclui que ela sobrou. Rodei o `alembic check`, que faz a mesma comparação sem gerar arquivo:

```console
$ uv run alembic check
...
FAILED: New upgrade operations detected: [('remove_index', Index('bancada_reservas_resource_id_starts_at_idx', ...)), ('remove_table', Table('bancada_reservas', ...))]
```

*(Cortei as colunas. O resto da comparação bate: só a tabela da bancada sobra.)*

O que a lição 11 fez, e o que você faz: **abrir o arquivo gerado e ler** antes de rodar. Um `drop_table('bancada_reservas')` não pertence a migração nenhuma do FairFare. Se ele aparecer, sai do arquivo.

Quer o `alembic check` limpo antes do próximo capítulo? A tabela pode ir embora. Se você rodar a bancada das lições 08 e 09 de novo, ela é recriada:

```console
$ docker compose exec postgres psql -U fairfare -c 'DROP TABLE bancada_reservas;'
```

**Morre no:** em nenhum capítulo. O primeiro furo é do Alembic, e não tem conserto do nosso lado. O segundo é sujeira do banco de dev. É uma *ressalva de ferramenta*: o autogenerate é um rascunho, nunca a migração pronta.

## 9. Decisões, não defeitos

Estes itens não morrem em capítulo nenhum. Não são bugs. São escolhas que alguém precisava fazer, e que ficam escritas para você poder discordar delas.

| O quê | Onde | Por quê |
|---|---|---|
| Horário sem fuso é lido como UTC | `BookingCreate.sem_fuso_e_utc` | Um `10:00` sem fuso é ambíguo. Quem quis dizer "10h em São Paulo" grava o instante errado, e a API não tem como perceber. A alternativa (o relógio da máquina) seria pior (lição 04). |
| Os horários antigos estavam em UTC | migração `reservas com fuso` (`AT TIME ZONE 'UTC'`) | Uma suposição, escrita. Linhas gravadas nos capítulos 1 a 3 com outro fuso em mente andaram, e não há como saber quais (lição 04). |
| As respostas vêm sempre em UTC, com `Z` | `BookingOut` | O servidor fala em instantes. Mostrar no fuso de quem olha é trabalho do cliente (lição 04). |
| `SERIALIZABLE` e o retry ficaram na bancada | `bancada/isolamento.py` | O app usa a constraint. A lição 09 mediu o `SERIALIZABLE` abortando inocentes, e o retry obrigatório. A conta não fechou para o FairFare. |
| A limpeza das 47 duplicatas manteve o menor `id` | lição 11, um `DELETE` no banco de dev | Dados de teste. Num banco real, quem fica é decisão de gente, não de SQL. |
| A extensão `btree_gist` fica depois de um `downgrade` | migração `reserva nao sobrepoe` | Outro objeto do banco pode ter passado a depender dela (lição 11). |
| O `commit()` mora no repository | `BookingRepository.create` | Funciona para uma operação por request. Quem deve comitar quando há várias é pergunta do capítulo 5 (lição 08). |

A última tem capítulo, mas não é defeito: hoje nenhuma operação do FairFare precisa de duas gravações na mesma transação.

## 10. Ressalvas de medição e de bancada

Também não morrem em capítulo nenhum. São o contexto dos números.

| O quê | Onde |
|---|---|
| Os números são desta máquina, nesta sessão: doze núcleos, loopback, Postgres 18 no Docker, um disco lento. A direção se repete. Os valores, não. | lições 05, 06, 07, 09, 10, 11 |
| Mac e Windows não foram verificados com o Docker. Só Linux rodou. | lição 01 |
| O `seed.sql` **apaga** usuários, recursos e reservas do banco de dev, e deixa um milhão de reservas no lugar. | lição 06, `bancada/seed.sql` |
| O `corrida.py` varia o `X-Forwarded-For` para não levar `429` do rate limiter. Funciona porque o uvicorn confia em `127.0.0.1` por padrão. | lição 07, `bancada/corrida.py` |
| O retry do `isolamento.py` não espera entre tentativas, e em metade das rodadas desiste na quinta. De propósito: mostra que a transação nova é obrigatória, não como esperar. | lição 09, `bancada/isolamento.py` |
| Vários experimentos rodaram com mudanças temporárias (`echo=True`, pool 30, o papel `comum`, o índice `tmp_gist`) ou com scripts descartáveis. Nada disso está no repositório. | lições 05, 08, 09, 10, 11 |

## 11. As herdadas

A lição 12 do capítulo 3 tem o inventário de lá. Quase tudo continua de pé, porque este capítulo não encostou no rate limiter, no CORS, no proxy da bancada, no TLS nem nos vários processos. Releia aquela lista: ela vale para este código.

Uma linha daquela lista foi paga aqui. Ela dizia que o pool, multiplicado pelos workers, ia doer no PostgreSQL. Doeu, na lição 05. E agora tem conta: `4 × (5 + 10) = 60 ≤ 100 − 10`.

E das três herdadas do capítulo 1, que andaram de capítulo em capítulo:

### A reserva dupla morreu

Era a entrada 2 da `ERRATA.md`, item 1: o *check-then-act* de `BookingService.create`. E a entrada 3 abriu um segundo caminho para ela: o mesmo instante, escrito em dois fusos, passava como dois horários diferentes.

Os dois caminhos fecharam neste capítulo:

- **O do fuso**, na lição 04. As colunas viraram `timestamptz`, e `10:00-03:00` e `13:00Z` são o mesmo instante. O `test_mesmo_instante_em_fusos_diferentes_conflita` guarda isso.
- **O da corrida**, nas lições 10 e 11. A lição 10 fechou com um cadeado no recurso. A lição 11 tirou o cadeado e pôs a regra no próprio banco, a `bookings_sem_sobreposicao`. Agora não importa por onde a reserva chega: app, script, `psql`.

A prova está nos testes e na bancada. O `test_reservas_simultaneas_so_uma_passa` dispara dez reservas iguais de uma vez e exige exatamente um `201` e exatamente uma reserva no banco. O `test_sem_a_verificacao_previa_o_banco_ainda_recusa` desliga a verificação do service e exige `409` mesmo assim. Rodei os dois vinte vezes seguidas, agora:

```console
$ for i in $(seq 1 20); do uv run pytest tests/test_concorrencia.py -q | tail -1; done | sed 's/ in .*//' | sort | uniq -c
     20 2 passed
```

E a corrida pelo uvicorn de verdade, que na lição 07 criava duplicata em dez de dez rodadas, deu `0/10` com o cadeado (lição 10) e `0/10` com a constraint (lição 11).

Com uma honestidade no fim: o item 6 continua valendo. Num empate de verdade, com muita gente, as perdedoras podem receber `500` em vez de `409`, e demorar para receber. Elas não ganham a reserva. Ninguém ganha duas. Mas a resposta é feia, e isso fica declarado até o capítulo 9.

### As que sobram

- **`GET /bookings` ainda faz 2N+1 consultas.** Item 1. Capítulo 5.
- **Ainda não existe autenticação.** Item 2. Capítulo 6.

E, das muitas coisas que nasceram neste capítulo, várias também já morreram nele: o `500` para horário com fuso (lição 02, morto na 04), os testes que rodavam no SQLite (morto na 03), o índice que lia todo o passado do recurso (lição 06, morto na 11), as duplicatas do banco de dev (lição 07, apagadas na 11) e o próprio cadeado da lição 10, que saiu na 11 porque a regra mudou de casa.

## A regra, em uma frase

**Este curso não esconde bugs no código que entrega.** Toda limitação conhecida está escrita no material do capítulo onde ela existe, junto com o capítulo que a resolve. Se você achar no FairFare um defeito que não esteja declarado em lugar nenhum, isso não é um exercício disfarçado: é um erro meu, e vale um issue.

## O que você deve conseguir fazer agora

- Para cada limitação desta lista, dizer onde ela está e em que capítulo ela morre. E separar as que são **decisão** ou **ressalva**, que não morrem em capítulo nenhum. Sem consultar a lista.
- Explicar por que o N+1 do item 1 esgotou o pool da lição 05, e por que aumentar o pool não resolveu.
- Explicar por que o app ser superusuário desmonta a reserva de emergência do PostgreSQL.
- Dizer por que a reserva dupla morreu e, no mesmo fôlego, por que um empate ainda pode dar `500`. E por que isso não é uma reserva dupla.
- Ler uma migração gerada pelo autogenerate e saber o que procurar antes de rodar.
