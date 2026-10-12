# Exercícios do capítulo 5

**Aviso, porque isto importa: todo código desta pasta está quebrado de propósito.**

O FairFare, em `app/`, não tem defeito escondido: o que ele ainda não resolve está declarado na lição 12. O que você encontrar de errado lá fora disso vale um issue. O que está *aqui* foi escrito errado de caso pensado, para você consertar. Só um item foge um pouco da regra: o 2.1 não está quebrado, ele **funciona, mas do jeito caro**. A resposta sai certa. O número de consultas é que está errado.

Cada bloco tem testes que você mesmo roda. O teste é a definição de "pronto": enquanto ele estiver vermelho, o exercício não acabou.

Nenhum destes testes é coletado pelo `uv run pytest` do projeto (o `testpaths` do `pyproject.toml` cuida disso). Você roda cada bloco apontando o caminho.

Os blocos são **autocontidos**: nenhum deles importa `app/`. O bloco 1 nem usa banco. Os blocos 2 e 3 criam as próprias tabelas no `fairfare_test`, o banco do pytest (`bloco2_*`, `bloco3_*`), e as apagam no fim. O banco de desenvolvimento do FairFare não é tocado. As fixtures moram em `exercises/conftest.py`.

Os blocos 2 e 3 precisam do Postgres de pé:

```bash
docker compose up -d --wait
```

---

## Bloco 1 — Dinheiro

Dois itens, sem banco nenhum. Só `Decimal`.

```bash
uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco1 -v
```

Estado inicial: **5 falharam, 3 passaram.** Os 3 que passam fazem parte do exercício (veja a 1.1).

### 1.1 — A taxa que ninguém pediu para arredondar assim

**Arquivo:** `bloco1/taxa.py` — **quebrado de propósito.**

Os 10% do garçom, ao centavo. A regra da casa está escrita na docstring: meio centavo arredonda **para cima**. Uma conta de R$ 0,25 dá R$ 0,025 de taxa, e a casa cobra R$ 0,03.

O teste passa cinco contas. Duas falham. Na máquina do autor:

```
E       AssertionError: assert Decimal('0.02') == Decimal('0.03')
E        +  where Decimal('0.02') = taxa_de_servico(Decimal('0.25'))
...
E       AssertionError: assert Decimal('1.00') == Decimal('1.01')
E        +  where Decimal('1.00') = taxa_de_servico(Decimal('10.05'))
```

E três passam: `10.00`, `0.35` e `80.15`. Olhe as duas últimas com atenção. A `0.35` vira `0.035` de taxa, e a `80.15` vira `8.015`. As duas também terminam em meio centavo, e mesmo assim saem certas. Não é sorte. Antes de consertar, explique por que essas passam e a `0.25` não.

A dica: a lição 06 ("Quem arredonda?") mostrou que "arredondar" não é uma operação só, e qual delas o `quantize` usa quando ninguém diz nada. A lição 07 ("Por que `ROUND_DOWN`, e não o padrão") mostrou como se diz.

**Pronto quando:** os cinco casos de `test_taxa_meio_centavo_para_cima` passam. O conserto mora em `taxa_de_servico`. Somar meio centavo antes de arredondar não vale: a regra precisa estar escrita, não simulada.

### 1.2 — O valor que chegou como número

**Arquivo:** `bloco1/entrada.py` — **quebrado de propósito.**

Um cliente antigo manda o valor como número no JSON, `{"valor": 80.10}`, e não como string. Você não controla esse cliente. A função lê o campo e devolve um `Decimal`. O tipo está certo. O valor, não:

```
E       assert Decimal('80.099999999999994315658113919198513031005859375') == Decimal('80.10')
E       assert Decimal('0.1000000000000000055511151231257827021181583404541015625') == Decimal('0.1')
E       assert Decimal('19.989999999999998436805981327779591083526611328125') == Decimal('19.99')
```

Os três falham. Repare que o `Decimal` está ali, bem no `return`. Chegou tarde.

A dica: a lição 06 ("No JSON: string") contou quem lê o número primeiro, e como. Pergunte em que momento o `80.10` deixou de ser `80.10`. A resposta não está no `Decimal(...)`: está no que roda antes dele, dentro dos parênteses. E a documentação do `json.loads` tem um parâmetro feito exatamente para isso.

**Pronto quando:** os três casos de `test_valor_do_pedido_exato` passam. Um atalho passa nos três e mesmo assim não vale: `Decimal(str(...))` em cima do `float`. Com `{"valor": 1234567890.123456789}`, ele devolve `1234567890.1234567`, os mesmos dígitos perdidos da lição 06. Quando o `str` olha, o `float` já existe, e o estrago já foi feito. O conserto certo nunca deixa o `float` nascer.

**Pronto do bloco:** todos os 8 testes do bloco 1 verdes.

---

## Bloco 2 — As consultas

Três testes sobre a mesma semente: 20 grupos, cada um com 3 membros e 4 despesas. A fixture cria tudo e apaga no fim.

```bash
uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco2 -v
```

Estado inicial: **2 falharam, 1 passou.** O que passa é o `test_resumo_correto`, e ele precisa continuar passando.

### 2.1 — O N+1 escrito à mão

**Arquivo:** `bloco2/listagem.py`, função `resumo_dos_grupos` — **funciona, mas do jeito caro.**

Um resumo para a tela inicial: o nome de cada grupo, os nomes dos membros e o total gasto. A resposta sai certa (o `test_resumo_correto` confere). O outro teste conta as consultas com o mesmo contador da lição 03, e pede no máximo 3. Na máquina do autor:

```
E       AssertionError: 41 consultas para 20 grupos
E       assert 41 <= 3
```

Uma consulta para os grupos. Depois, para cada grupo, uma para os membros e uma para o total. São 1 + 2 × 20. Com 200 grupos, 401.

A dica: são dois N+1 diferentes, e cada um tem um remédio diferente. Os membros são uma **coleção** que você precisa inteira, nome por nome: a lição 03 mostrou como pedir uma relação junto, numa consulta por relação. O total é um **resumo**: a lição 09 mostrou para onde a conta deve ir ("leve a conta para onde os dados estão"). Uma consulta só pode trazer o total de todos os grupos de uma vez, se você pedir agrupado.

**Pronto quando:** `test_resumo_sem_n_mais_1` passa **e** `test_resumo_correto` continua passando. A assinatura e o formato da resposta não mudam.

### 2.2 — O `joinedload` na coleção

**Arquivo:** `bloco2/listagem.py`, função `grupos_com_membros` — **quebrada de propósito.**

Os grupos, cada um com a coleção `membros` já carregada, numa consulta só. Alguém leu a lição 03, viu que o `joinedload` faz tudo num `JOIN` e usou. A consulta nem chega a devolver nada:

```
E       sqlalchemy.exc.InvalidRequestError: The unique() method must be invoked on this Result, as it contains results that include joined eager loads against collections
```

A mensagem já diz o que fazer. O exercício é entender **por quê**. A dica: a lição 03 ("Por que `selectinload` aqui") explicou o que um `JOIN` faz com uma coleção. Quantas linhas o banco devolve para estes 20 grupos? Quantos objetos `Bloco2Grupo` você quer no fim? Quem desfaz a diferença?

**Pronto quando:** `test_grupos_com_membros` passa: 20 grupos, cada um com 3 membros. Mantenha o `joinedload`: trocar por `selectinload` também funciona, mas aí o exercício vira outro.

---

## Bloco 3 — Transação e cadeado

Dois itens, o mesmo arquivo de teste. As tabelas são reais (não temporárias), porque várias conexões precisam enxergá-las ao mesmo tempo. O teste as cria e as apaga.

```bash
uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco3 -v
```

Estado inicial: **2 falharam.**

### 3.1 — O extrato pela metade

**Arquivo:** `bloco3/lancamento.py` — **quebrado de propósito.**

Um extrato de 4 lançamentos que só fazem sentido juntos: as despesas de um jogo. O teste força uma falha antes da terceira linha (é o `falhar_na=2`, no papel da conexão que cai no meio), espera a exceção e conta o que ficou na tabela:

```
E       AssertionError: o extrato ficou pela metade: 2 de 4 linhas
E       assert 2 == 0
```

Duas linhas gravadas para sempre, de um extrato que deu erro. É a despesa de R$ 90 com partes que somam R$ 60, em outra roupa.

A dica: a lição 08 inteira. Quem decide o que é "uma operação"? E qual é a diferença entre mandar o rascunho ao cartório e assinar?

**Pronto quando:** `test_extrato_nunca_fica_pela_metade` passa, com **zero** linhas na tabela depois da falha. Sem `try`/`except` com `rollback()` à mão: a lição 08 mostrou uma forma em que não dá para esquecer o rollback.

### 3.2 — O cadeado que chega tarde

**Arquivo:** `bloco3/transferencia.py` — **quebrado de propósito.**

A conta 1 tem R$ 100. Duas transferências de R$ 80 saem dela ao mesmo tempo. Uma tem que passar, e a outra tem que levantar `SaldoInsuficiente`. No fim, a conta 1 fica com R$ 20.

O código tem tudo o que a lição 11 pediu: `FOR UPDATE` nas duas contas, num comando só, em ordem de id. Deadlock não há. E mesmo assim:

```
E       AssertionError: assert (2, Decimal('-60.00')) == (1, Decimal('20.00'))
```

As duas passaram, e a conta ficou com R$ −60. O autor rodou o teste 10 vezes, e as 10 deram exatamente isso.

O teste usa um gancho, `depois_de_ler`, que faz cada transferência esperar a outra chegar ao mesmo ponto, por no máximo 0,5 s. Ele só torna a corrida certa em vez de provável: a janela que ele alarga existe sem ele. E repare no timeout: se uma das duas estiver parada esperando um cadeado, a outra desiste de esperar depois de 0,5 s e segue em frente. Nada trava.

A dica: a lição 11 ("Por que funciona em `READ COMMITTED`") terminou com uma frase sobre fila. Leia de novo, e olhe a **ordem** das linhas dentro do `async with`. O cadeado está certo. Quando ele chega é que não está.

**Pronto quando:** `test_duas_transferencias_nao_estouram_o_saldo` passa **10 vezes seguidas**:

```bash
for i in $(seq 10); do uv run pytest chapters/05-relacoes-e-dinheiro/exercises/bloco3 -q -k transferencias | tail -1; done
```

Sem mexer no teste nem no gancho, sem trocar o `FOR UPDATE` por outra coisa e sem um `CHECK` na tabela. Um bônus para conferir que você entendeu: com o conserto certo, o teste passa a levar cerca de meio segundo. Explique de onde vem esse meio segundo.
