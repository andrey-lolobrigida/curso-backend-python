# Lição 09 — Níveis de isolamento

A lição 08 terminou com duas transações em `READ COMMITTED` gravando duas reservas para a mesma quadra, dez de dez vezes. E com uma pergunta no ar: e se a transação fosse **mais desconfiada**?

O `READ COMMITTED` é só um dos níveis de isolamento. Existem outros, mais rígidos. Esta lição sobe a escada, degrau por degrau, com o mesmo experimento. A pergunta é simples: mais isolamento resolve?

## A escada

O padrão SQL define quatro níveis. Do mais frouxo ao mais rígido: `READ UNCOMMITTED`, `READ COMMITTED`, `REPEATABLE READ` e `SERIALIZABLE`.

No PostgreSQL, são três na prática. Você pode pedir `READ UNCOMMITTED`, mas ele se comporta igual ao `READ COMMITTED`: o Postgres nunca mostra dado não comitado de outra transação.

Para subir a escada, a bancada tem `bancada/isolamento.py`. Ele não reimplementa nada. Importa o `tentar` e a `rodada` do `transacao.py` e só troca o nível:

```python
from transacao import INICIO, URL, preparar, rodada, tentar

NIVEIS = {
    "read-committed": "READ COMMITTED",
    "repeatable-read": "REPEATABLE READ",
    "serializable": "SERIALIZABLE",
}
```

O nível vai parar no `conn.execution_options(isolation_level=nivel)` dentro do `tentar`. É a linha que estava lá, esperando, desde a lição 08. Mesma tabela, mesma barreira, mesmas dez rodadas. Só o nível muda.

## Degrau 1: `READ COMMITTED`

Você já conhece. Cada **comando** vê um retrato novo do banco, tirado no instante em que ele começa. Para conferir que o script novo mede o mesmo que o antigo:

```console
$ B=chapters/04-o-banco-de-dados-de-verdade/bancada
$ uv run python $B/isolamento.py --nivel read-committed
rodada  1: 201 + 201
...
rodada 10: 201 + 201

READ COMMITTED, recursos (1, 1): duas reservas em 10/10, abortou em 0/10
```

*(Daqui em diante, corto as rodadas do meio quando são todas iguais.)*

Deixa passar. Dez de dez, como na lição 08.

## Degrau 2: `REPEATABLE READ`

Aqui a transação tira **um retrato só**, no primeiro comando, e usa esse retrato até o fim. Se outra transação comitar algo no meio do caminho, você não vê. Ler a mesma coisa duas vezes dá a mesma resposta, daí o nome.

Parece mais seguro. Vamos ver:

```console
$ uv run python $B/isolamento.py --nivel repeatable-read
rodada  1: 201 + 201
...
rodada 10: 201 + 201

REPEATABLE READ, recursos (1, 1): duas reservas em 10/10, abortou em 0/10
```

Dez de dez. Nada mudou.

E faz sentido, se você pensar no que cada uma viu. As duas tiraram o retrato antes de a outra gravar. No retrato das duas, a quadra estava livre. E cada uma gravou uma linha **nova**, diferente da linha da outra. Ninguém tentou mudar a mesma linha que outra pessoa mudou, então o `REPEATABLE READ` não tem do que reclamar.

Esse padrão tem nome: **write skew**. Duas transações leem o mesmo conjunto de dados, cada uma decide com base no que leu, e cada uma escreve num lugar **diferente**. Sozinha, cada escrita é válida. Juntas, quebram uma regra que nenhuma das duas escritas viola sozinha. A regra aqui é "não pode haver duas reservas sobrepostas", e ela mora no conjunto, não em nenhuma linha.

Na agenda de papel: Ana e Bruno tiram, cada um, uma **foto** da agenda. A foto não muda, é isso que o `REPEATABLE READ` garante. A agenda de verdade, sim. Os dois olham a própria foto, veem o horário livre, e vão anotar.

## Degrau 3: `SERIALIZABLE`

O último degrau promete outra coisa. Ele não fala de retratos. Ele promete o **resultado**: o que sair de um monte de transações concorrentes vai ser igual ao de **alguma** ordem em que elas tivessem rodado uma de cada vez, em série. Se o banco perceber que não consegue garantir isso, ele aborta uma das transações.

Repare no "alguma". O banco não promete qual vai primeiro. Promete só que existe uma fila em que a história faz sentido.

No nosso caso, qualquer fila serve: se a T1 rodasse inteira antes da T2, a T2 veria a reserva da T1 e responderia `409`. O contrário também. O que não existe é uma fila em que **as duas** gravem. Então uma tem que cair:

```console
$ uv run python $B/isolamento.py --nivel serializable
rodada  1: 201 + abortada
rodada  2: abortada + 201
rodada  3: abortada + 201
...
rodada  7: 201 + abortada
...
rodada 10: abortada + 201

SERIALIZABLE, recursos (1, 1): duas reservas em 0/10, abortou em 10/10
```

Uma reserva por rodada. Finalmente.

O `abortada` é o `except` do `tentar` que ficou parado na lição 08. Ele pega o erro de sqlstate `40001`, `serialization_failure`. Para ver a mensagem inteira, rodei as duas transações à mão, num script descartável, e imprimi a exceção:

```console
(sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'asyncpg.exceptions.SerializationError'>: could not serialize access due to read/write dependencies among transactions
DETAIL:  Reason code: Canceled on identification as a pivot, during commit attempt.
HINT:  The transaction might succeed if retried.
(Background on this error at: https://sqlalche.me/e/20/dbapi)
```

Leia a mensagem com calma. "Read/write dependencies": o banco anotou que cada transação **leu** algo que a outra **escreveu**, e que as duas setas juntas não cabem em fila nenhuma. "Pivot" é a transação que ficou no meio das setas, com uma chegando e outra saindo: foi ela que o banco escolheu derrubar. "During commit attempt": a vítima só descobriu no `COMMIT`. Às vezes o erro sai já no `INSERT`. Depende de quem chega primeiro a cada ponto, e varia de rodada para rodada.

E a última linha. Ela não é educação do Postgres. É uma instrução.

## O retry é obrigatório

> HINT: The transaction might succeed if retried.

Quem levou `40001` não errou. Não tem bug, não tem dado inválido. Ela só **perdeu a vez**. Se tentar de novo **depois que a outra terminar**, ela vai ver a reserva e responder `409`. Que é a resposta certa. (Guarde esse "depois que a outra terminar". Ele vai cobrar o preço dele daqui a pouco.)

Ou seja: com `SERIALIZABLE`, o retry não é um enfeite. É parte do contrato. Quem liga o `SERIALIZABLE` e não trata o `40001` entrega um erro 500 a um usuário que só chegou meio milissegundo atrasado.

O `isolamento.py` tem esse retry:

```python
async def tentar_com_retry(
    engine: AsyncEngine, nivel: str, recurso: int, barreira: asyncio.Barrier
) -> str:
    # O retry obrigatório do SERIALIZABLE: quando o banco aborta, a transação morreu.
    # Tentar de novo é começar OUTRA, do zero — verificar de novo, decidir de novo.
    resultado = await tentar(engine, nivel, recurso, barreira)
    tentativa = 1
    while resultado == "abortada" and tentativa < 5:
        tentativa += 1
        resultado = await tentar(engine, nivel, recurso, None)
    return resultado if tentativa == 1 else f"{resultado} (tentativa {tentativa})"
```

O detalhe que importa está no comentário: **tentar de novo é começar outra transação do zero.** Cada chamada de `tentar` pega uma conexão, abre um `BEGIN` novo, faz o `SELECT` de novo e decide de novo. Não dá para "repetir só o `INSERT`": a decisão de inserir veio de uma leitura que o banco acabou de declarar inválida. E a transação abortada morreu. Qualquer comando que você mande nela depois volta com erro. *(Os exercícios do bloco 3 têm um retry escrito do jeito errado. Você vai ver o erro com os próprios olhos.)*

A segunda tentativa vai sem barreira (`None`). A barreira serve para forçar o pior encaixe na primeira volta. Na segunda, não tem mais ninguém para esperar.

Rodando:

```console
$ uv run python $B/isolamento.py --nivel serializable --retry
rodada  1: abortada (tentativa 5) + 201
rodada  2: 409 (tentativa 3) + 201
rodada  3: 201 + 409 (tentativa 3)
rodada  4: 409 (tentativa 3) + 201
rodada  5: abortada (tentativa 5) + 201
rodada  6: 409 (tentativa 3) + 201
rodada  7: 409 (tentativa 3) + 201
rodada  8: abortada (tentativa 5) + 201
rodada  9: abortada (tentativa 5) + 201
rodada 10: abortada (tentativa 5) + 201

SERIALIZABLE, recursos (1, 1): duas reservas em 0/10, abortou em 5/10
```

Nenhuma reserva dupla, ótimo. Mas olhe o lado de quem perdeu. Nesta execução, metade chegou no `409` certo, e a outra metade gastou as cinco tentativas e desistiu. Rode de novo e a proporção dança: já vi de 1 a 9 desistências em 10. E nas que deram certo, quase nunca bastou a segunda tentativa.

Por quê? Pus um carimbo de tempo em cada passo, num script descartável, e a história ficou clara. A vencedora manda o `COMMIT` e fica esperando o PostgreSQL confirmar que gravou no disco. Isso leva uns 3 ms nesta máquina, e às vezes passa de 80 ms. Enquanto isso, a perdedora faz uma tentativa inteira em menos de 1 ms. Ela olha, vê a quadra livre (o `COMMIT` da outra ainda não terminou), tenta inserir, e leva outro `40001`. E de novo. E de novo. Cinco tentativas cabem com folga dentro de um `COMMIT` lento.

Testei também com uma pausa de 10 ms antes de cada nova tentativa, de novo num script descartável. Melhorou bastante: 26 de 30 rodadas terminaram em `409 (tentativa 2)`. Mas não zerou. Quando o disco demora 100 ms, 10 ms não bastam.

Esperar o tempo certo antes de tentar de novo tem nome, **backoff**, e é assunto do capítulo 9. O retry desta bancada é ingênuo de propósito: ele mostra que a transação nova é obrigatória, não como esperar. É o tema que vai voltar o curso inteiro: o problema aqui não é lógica, é **tempo**.

## O preço

Agora, a parte que ninguém conta no folheto. Mesmo experimento, mas cada transação reserva uma quadra **diferente**: a T1 a quadra 1, a T2 a quadra 2. Não há conflito nenhum. Em qualquer nível, as duas deviam passar.

```console
$ uv run python $B/isolamento.py --nivel serializable --recursos diferentes
rodada  1: 201 + abortada
rodada  2: abortada + 201
...
rodada 10: 201 + abortada

SERIALIZABLE, recursos (1, 2): duas reservas em 0/10, abortou em 10/10
```

Dez de dez abortadas. Duas pessoas que **nem disputavam** a mesma coisa, e uma delas perdeu a vez em toda rodada. É um **falso positivo**: o banco viu um conflito que não existia.

Para entender, precisa saber como o `SERIALIZABLE` do PostgreSQL vigia. Ele não tranca nada: ninguém espera por ninguém. Em vez disso, ele **anota o que cada transação leu**. Essas anotações aparecem na tabela `pg_locks` com o modo `SIReadLock` (os "predicate locks"; o nome tem "lock", mas não bloqueiam ninguém). Quando alguém escreve num lugar que outra transação leu, o banco desenha uma seta entre as duas. Seta para um lado e para o outro é o padrão perigoso, e uma das duas cai.

O pulo do gato está no "lugar". Abri duas transações `SERIALIZABLE` à mão, num script descartável, cada uma fez o `SELECT` da sua quadra, e consultei `pg_locks` por uma terceira conexão:

```console
('page', 'bancada_reservas_resource_id_starts_at_idx', 1, None, 'SIReadLock', 23687)
('page', 'bancada_reservas_resource_id_starts_at_idx', 1, None, 'SIReadLock', 23688)
```

As colunas são `locktype`, a relação, `page`, `tuple`, `mode` e o `pid` da conexão. As duas anotações são do tipo `page`, e caíram **na mesma página**: a página 1 do índice `(resource_id, starts_at)`. O banco não anotou "a T1 leu as reservas da quadra 1". Anotou "a T1 leu alguma coisa nesta página do índice". A quadra 1 e a quadra 2 moram vizinhas no índice, na mesma página. Para o banco, as duas leram o mesmo lugar e escreveram nele. Seta para cá, seta para lá, uma cai.

A prova: repeti com a quadra 1 e a quadra **40**, que fica lá no fim do índice (ele tem 41 páginas). As anotações caíram nas páginas 1 e 31, e as duas transações comitaram. Mesmo nível, mesma consulta. Só a vizinhança mudou.

Por que página, e não "as reservas da quadra 1"? Porque a T1 não leu reserva nenhuma: o `count(*)` deu zero. O que ela precisa vigiar é um **buraco**, o lugar do índice onde uma reserva da quadra 1 cairia se alguém a inserisse. Uma linha que não existe não dá para anotar. Então o PostgreSQL anota a página do índice que cobre aquele buraco, e a página cobre as vizinhas também.

Essa é a troca que o `SERIALIZABLE` faz, e ela é deliberada. A vigilância tem granularidade: linha, página, e, quando as anotações ficam muitas, a tabela inteira. Quanto mais grossa, mais barata, e mais falso positivo. E entre deixar passar uma anomalia e abortar quem não precisava, o banco sempre escolhe abortar.

Quem paga é todo mundo. Não só quem brigou pela mesma quadra: qualquer transação cujas leituras caiam perto das de outra. Cada uma delas faz o retry, com o custo de tempo que você acabou de ver.

## A decisão do curso

`SERIALIZABLE` com retry funciona. Nenhuma reserva dupla em nenhuma rodada. É uma ferramenta de verdade, usada em produção, e às vezes é a certa: quando a regra é complicada demais para escrever de outro jeito.

Mas ela fica aqui, na bancada. O FairFare vai por outro caminho. Em vez de deixar o banco desconfiar de **tudo** que foi lido, a próxima lição tranca **exatamente** o que está em disputa: o recurso. É o cadeado da agenda, aquele da lição 08. E a lição 11 vai um passo além: escreve a regra "não pode sobrepor" dentro do próprio banco, e deixa ele recusar.

## O que fica declarado

- **O app continua em `READ COMMITTED`**, com a corrida aberta. Esta lição só mediu os níveis na bancada.
- **O retry do `isolamento.py` não espera entre tentativas.** Numa parte das rodadas, que varia muito de uma execução para outra, ele desiste na quinta. Ficou assim de propósito, e o backoff é do capítulo 9.
- **A mensagem completa do `40001`, os carimbos de tempo, a pausa de 10 ms e as consultas a `pg_locks`** vieram de scripts descartáveis, fora do repositório. O `isolamento.py` só imprime o resumo de cada rodada.
- **As páginas do índice são desta tabela, nesta máquina.** Com outros dados, o índice tem outro formato e os vizinhos mudam. O que não muda é o mecanismo: a vigilância por página aborta quem só estava perto.

## O que você deve conseguir fazer agora

- Dizer o que cada nível vê: um retrato por comando (`READ COMMITTED`), um retrato pela transação inteira (`REPEATABLE READ`), ou a garantia de uma ordem em série (`SERIALIZABLE`).
- Explicar o write skew com o exemplo da reserva: por que o `REPEATABLE READ` deixa as duas gravarem.
- Ler a mensagem do `40001` e dizer o que "pivot" e "might succeed if retried" querem dizer, por alto.
- Explicar por que o retry do `SERIALIZABLE` não é opcional, e por que ele precisa de uma transação nova, do zero.
- Explicar por que o `SERIALIZABLE` aborta reservas em quadras diferentes, e o que a página do índice tem a ver com isso.
