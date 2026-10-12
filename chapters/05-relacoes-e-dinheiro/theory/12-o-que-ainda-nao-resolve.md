# Lição 12 — O que este código ainda não resolve

Todo capítulo desde o 2 fecha com esta lição, e pelo mesmo motivo: **um curso que entrega código tem uma dívida com quem vai ler esse código.** Se eu sei que tem um defeito, eu te conto.

Este capítulo pôs dinheiro no FairFare. Grupos, membros, despesas, saldos, quitações. Cada peça chegou com algum pedaço faltando, e cada pedaço foi declarado no fim da lição onde apareceu, na seção "O que fica declarado". Aqui vai tudo junto, com endereço e com o capítulo em que morre.

Dois itens têm capítulo marcado. O resto é escolha ou ressalva. E tem um item **riscado**, o mais velho do curso: o 2N+1. Ele ganha uma seção própria no fim.

## 1. Sem autenticação, sem permissões

**Onde:** todas as rotas. E este capítulo abriu mais quatro portas em `app/routers/groups.py`:

- `POST /groups/{id}/members` aceita qualquer `user_id`;
- `POST /groups/{id}/expenses` aceita qualquer `paid_by`;
- `POST /groups/{id}/settlements` aceita qualquer `de_user_id` e `para_user_id`;
- `GET /groups/{id}/balances` mostra o saldo de qualquer grupo a qualquer um.

**Como se manifesta:** qualquer cliente põe qualquer pessoa em qualquer grupo. Lança uma despesa de R$ 500 "paga pela Ana" sem ser a Ana. Registra que o Bruno pagou a dívida dele, sem o Bruno saber. O service confere quem é **membro**, não quem está **pedindo**: ninguém se identifica.

**Morre no:** capítulo 6.

## 2. O saldo é recalculado a cada request

**Onde:** `SALDOS` e `GroupRepository.balances`, em `app/repositories/group.py`. Quem chama: o `GroupService.balances` (o `GET .../balances`) e o `SettlementService.create`, que lê os saldos a cada quitação.

**Como se manifesta:** a lição 09 decidiu que saldo se calcula, nunca se guarda. Correto: não existe número guardado para ficar velho. Mas o preço cresce com o grupo. A bancada mediu a consulta: ~10 ms com 2000 despesas, ~70 ms com 20000. Cada `GET` e cada quitação pagam isso de novo, mesmo que nada tenha mudado desde o último.

Guardar o resultado e saber quando ele deixou de valer é um capítulo inteiro.

**Morre no:** capítulo 7.

## 3. Decisões, não defeitos

Estes não morrem em capítulo nenhum. Não são bugs. São escolhas, escritas para você poder discordar delas.

| O quê | Onde | Por quê |
|---|---|---|
| Uma moeda só | `app/models/expense.py`: `Numeric(12, 2)`, sem coluna de moeda | Várias moedas trariam câmbio, e câmbio não ensina nada que este capítulo precise (lição 06). |
| Despesa imutável: não se lista, não se edita, não se apaga | `app/routers/groups.py` (só existe o `POST`) | O capítulo precisa de despesas para ensinar saldos e quitações, não de um CRUD completo (lição 08). |
| Quitação imutável: não se lista, não se desfaz | `app/routers/groups.py` (só existe o `POST`) | Uma quitação lançada por engano não tem volta. O estorno seria uma quitação no sentido contrário, e a regra dos dois lados quase sempre a recusa: quem recebeu não está devendo. Listar e estornar é CRUD, e o capítulo não precisava dele (lição 11). |
| O saldo é `NUMERIC(20, 2)`, não o `Numeric(12, 2)` da coluna | `SALDOS`, em `app/repositories/group.py` | Saldo é soma: três despesas no teto já estouravam o 12. Com 20, seriam precisos cem milhões delas. É um número escolhido, não infinito (lição 09). |
| O centavo que sobra vai aos menores `user_id` | `app/services/divisao.py::dividir` | Uma regra arbitrária, mas escrita e sempre a mesma. Quem tem id baixo paga até um centavo a mais por despesa, sempre do mesmo lado (lição 07). |
| A `dividir` supõe que o total tem duas casas | `dividir`, que não confere | Com três, a sobra trunca em silêncio. Quem garante é o tipo `Dinheiro` (`decimal_places=2`), e o único caminho até a `dividir` passa por ele (lições 07 e 08). |
| Ninguém sai do grupo | não existe `DELETE /groups/{id}/members/{user_id}` | Sair com dívida em aberto é um problema de domínio que o capítulo não precisava resolver (lição 04). |
| A relação só existe do lado da reserva | `app/models/booking.py`: `User` e `Resource` não sabem das reservas deles | Entra quando um capítulo precisar. Nenhum precisou (lição 01). |
| `GET /groups`, sem id, não existe | `app/routers/groups.py` | Nenhuma lição precisou listar todos os grupos (lição 04). |
| A quitação obriga a pagar em parcelas | `SettlementService.create`, a regra dos dois lados | Quem deve 20 a dois credores de 10 faz duas quitações. O menor conjunto de pagamentos é a *simplificação de dívidas*, problema de algoritmo, fora do curso (lição 11). |
| O saldo em `text()` não acusa coluna renomeada | `SALDOS` | Para o Python, é só uma string. Quem pega são os testes que executam a consulta: com a coluna trocada, quatro dos cinco testes de saldo falharam. Por isso os testes de saldo não são opcionais (lição 10). |
| Sem índice em `expenses.group_id` | o `Seq Scan` do `EXPLAIN` da lição 10 | O volume ainda é pequeno, e um grupo só cabe numa leitura inteira. Quando pesar, a técnica é a da lição 06 do capítulo 4: `EXPLAIN`, índice, `EXPLAIN` de novo. |
| O cadeado é um combinado | `GroupRepository.lock_members`, chamado **antes** do `balances` em `SettlementService.create` | Só protege porque todo caminho que decide com base nos saldos passa por ele. Um caminho novo que esqueça de trancar, ou um script que grave em `settlements` direto, volta a ter a corrida. É disciplina de código: o banco não sabe dessa regra (lição 11). |
| O `add_member` traduz **qualquer** `IntegrityError` em "já é membro" | `GroupRepository.add_member`, em `app/repositories/group.py` | Veja abaixo. |

A última pede um parágrafo. O `flush` do `add_member` pode estourar por dois motivos: a chave `(group_id, user_id)` repetida (SQLSTATE `23505`, `unique_violation`) ou uma chave estrangeira apontando para nada (`23503`). O repository não distingue: tudo vira `MemberAlreadyExistsError`, e a resposta é `409 usuário já é membro do grupo`.

Hoje é seguro. O `GroupService.add_member` confere antes que o grupo e o usuário existem, e nenhuma rota apaga grupo nem usuário. Então o `23503` não tem como acontecer. No dia em que existir exclusão, ele tem: o usuário some entre a conferência e o `flush`, e o cliente ouve "já é membro" de alguém que nem existe mais. O conserto já tem modelo no próprio repositório. O `BookingRepository.create` olha o código do erro antes de traduzir:

```python
if getattr(erro.orig, "sqlstate", None) == EXCLUSION_VIOLATION:  # "23P01"
    raise BookingOverlapError from erro
raise
```

No `add_member`, seria o mesmo, com `"23505"`.

## 4. Ressalvas de medição e de bancada

Também não morrem. São o contexto dos números.

| O quê | Onde |
|---|---|
| Os números são desta máquina, com o Postgres 18 no Docker, no mesmo computador. A direção se repete. Os milissegundos, não. | lições 03, 09, 10, 11 |
| O `seed.sql` do capítulo 4 **apaga** `users`, `resources` e `bookings`. Agora que existem grupos, o `CASCADE` leva junto `group_members`, `expenses`, `expense_shares` e `settlements`. Os grupos ficam, vazios. Por isso ele só rodou na lição 03, antes de existir grupo. | lição 03, `bancada/` do capítulo 4 |
| O `saldos.py` e o `quitacao.py` escrevem no banco de dev, mas criam e apagam só o que é deles. As sequências não voltam: os ids gastos ficam como buracos em `users`, `groups`, `expenses` e `settlements`. | lições 09 e 11 |
| As bancadas medem depois de um `ANALYZE`. Sem ele, o plano dos saldos chegou a 89 ms em vez de 13: as estatísticas eram de antes de o grupo existir. | lições 09 e 10 |
| O `injecao.py` precisa de uma `Ana` no banco de dev, a da lição 04. | lição 10 |
| O `quitacao.py` varia o `X-Forwarded-For`, como o `corrida.py` do capítulo 4, para o rate limiter ver N clientes. | lição 11 |
| Vários experimentos rodaram com mudanças temporárias que não estão no repositório: o `_to_out` lendo a relação, os `refresh` pela metade, o repository comitando, a quitação sem cadeado e com cadeado fora de ordem, os scripts de rascunho com `echo=True`, o `outerjoin` trocado por `join`, o saldo sem `coalesce` e sem `cast`, a coluna renomeada no `SALDOS`. | lições 01 a 04, 08 a 11 |

## 5. As herdadas

A lição 12 do capítulo 4 tem o inventário de lá, e ela continua valendo. A configuração do banco escrita no código, a senha no repositório e o app como superusuário (capítulo 11). O Docker como caixa fechada (capítulo 11). A migração que fecha a tabela (capítulo 11). O empate de verdade na `EXCLUDE` que vira `500` (capítulo 9): o `23P01` agora estoura no `flush`, e não no `commit()`, mas o `40P01` continua sem tradução. Os testes que nascem do `create_all` (capítulo 10). O autogenerate, que não é de confiança cega. Releia aquela lista: ela vale para este código. O `TRUNCATE` do `tests/conftest.py` só cresceu, de três tabelas para oito.

Duas linhas daquela lista foram pagas aqui.

A primeira estava na tabela de decisões, na linha do "`commit()` mora no repository": "Funciona para uma operação por request. Quem deve comitar quando há várias é pergunta do capítulo 5". Foi respondida na lição 08. A despesa trouxe a primeira operação com várias gravações, e o `commit()` saiu de todos os repositories. Quem delimita a transação é o service, com `async with self.db.begin()`.

A segunda é o item 1 daquela lista.

### O 2N+1 morreu

Era a entrada 2 da `ERRATA.md`, item 2: `_to_out` buscando usuário e recurso de cada reserva, uma consulta de cada vez. Nasceu no capítulo 1. A lição 11 do capítulo 2 explicou o mecanismo. As lições 12 dos capítulos 3 e 4 o carregaram. No capítulo 4, ele esgotou um pool.

Morreu na lição 03, em três partes:

- **O conserto:** `selectinload(Booking.user), selectinload(Booking.resource)` no `BookingRepository.list_all`. Uma consulta para as reservas, uma por relação.
- **A regra:** `relationship(lazy="raise")` nas duas relações de `app/models/booking.py`. Ler uma relação que ninguém carregou é erro na hora, com o nome dela na mensagem. O N+1 não volta em silêncio.
- **O guardião:** `test_listar_reservas_nao_cresce_com_o_numero_de_reservas`, em `tests/test_consultas.py`. Com 5 reservas, ele contou 11 consultas antes do conserto e cobra 3 depois.

E a medição, pelo endpoint, com o `bancada/conta_consultas.py` e 2000 reservas no banco de dev:

| | consultas | tempo |
|---|---|---|
| antes (2N+1) | 4001 | ~1000 ms |
| depois (`selectinload`) | 3 | 29 ms |

Três consultas com 5 reservas. Três com 2000. O número deixou de crescer com as linhas, que era o defeito. E o resto do capítulo seguiu a regra, com guardião: o `GET /groups/{id}` faz três consultas, e o `GET .../balances`, duas. Nenhum dos dois cresce com o grupo.

### As que sobram

Das três herdadas do capítulo 1, duas morreram: a reserva dupla, no capítulo 4, e o 2N+1, aqui. Sobra uma:

- **Ainda não existe autenticação.** Item 1. Capítulo 6.

## A regra, em uma frase

**Este curso não esconde bugs no código que entrega.** Toda limitação conhecida está escrita no material do capítulo onde ela existe, junto com o capítulo que a resolve. Se você achar no FairFare um defeito que não esteja declarado em lugar nenhum, isso não é um exercício disfarçado: é um erro meu, e vale um issue.

## O que você deve conseguir fazer agora

- Para cada item desta lista, dizer onde ele está e em que capítulo morre. E separar as decisões e ressalvas, que não morrem em capítulo nenhum.
- Explicar por que o cadeado das quitações é um combinado, e o que reabre a corrida.
- Explicar por que o `add_member` traduzir qualquer `IntegrityError` é seguro hoje, o que mudaria isso, e qual é o conserto.
- Dizer o que matou o 2N+1, e o que impede que ele volte.
