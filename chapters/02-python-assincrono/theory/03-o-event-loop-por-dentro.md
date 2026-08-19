# Lição 03 — O event loop por dentro

Na lição 01 eu pedi para você aceitar uma linha de mágica: o `asyncio.gather` do `carga.py`, que dispara dez requests ao mesmo tempo. Dívida vence hoje.

Esta lição tem um script companheiro, `bancada/loop.py`, com quatro cenas. Rode antes de continuar lendo:

```bash
uv run python chapters/02-python-assincrono/bancada/loop.py
```

Cada seção daqui para baixo explica uma cena.

## Corrotina: uma função que pode ser pausada

Comece pelo que `async def` faz — e principalmente pelo que ele **não** faz.

```python
async def tarefa(nome: str, segundos: float) -> str:
    print(f"  [{nome}] comecei")
    await asyncio.sleep(segundos)
    print(f"  [{nome}] terminei")
    return nome
```

`async def` não cria uma thread. Não cria um processo. Não torna nada paralelo. Ele cria uma **corrotina**: uma função que sabe ser **pausada no meio e retomada depois**, de onde parou.

Uma função comum é tudo-ou-nada: você chama, ela roda até o `return`, e só então devolve o controle. Uma corrotina tem pontos de saída no meio do corpo — e cada um deles é marcado com `await`.

Analogia: uma função comum é um livro que você lê de capa a capa sem levantar. Uma corrotina é um livro com marcadores de página: você para num marcador, vai fazer outra coisa, e depois volta exatamente ali. A precisão técnica: a corrotina guarda o próprio estado de execução (variáveis locais, onde parou) e devolve o controle a quem a estava rodando, podendo ser retomada em seguida.

Quem é "quem a estava rodando"? O event loop. Chegamos lá em duas cenas.

## Cena 1: `await` não é concorrência

O erro mais comum de quem acabou de aprender `async` é achar que `await` significa "faça isso em paralelo". Ele significa quase o oposto.

```python
await tarefa("a", 1)
await tarefa("b", 1)
```

Saída da cena 1:

```
  [a] comecei
  [a] terminei
  [b] comecei
  [b] terminei
  total: 2.00s  <- 2s: await espera mesmo
```

Dois segundos. `a` inteiro, depois `b` inteiro. **Zero concorrência.** Se você tinha alguma esperança de mágica, ela morre aqui — e é bom que morra cedo.

O que `await` faz, literalmente: *pausa esta corrotina aqui, devolve o controle ao loop, e me retome quando aquilo que estou esperando estiver pronto.* A pausa é da corrotina que chamou; o loop fica livre para rodar **outras** coisas nesse meio-tempo.

O detalhe que muda tudo: na cena 1 não existem outras coisas. A gente pausou e não deu nada mais ao loop para fazer. Ele esperou de braços cruzados, exatamente como você esperaria.

`await` cria a **possibilidade** de concorrência — o ponto de pausa. Quem cria a concorrência de fato é outra coisa.

## Cena 2: quem concorre é o `gather`

Mesmas duas tarefas, uma linha diferente:

```python
await asyncio.gather(tarefa("a", 1), tarefa("b", 1))
```

```
  [a] comecei
  [b] comecei
  [a] terminei
  [b] terminei
  total: 1.00s  <- 1s: agora sim
```

Um segundo. E olhe a ordem das mensagens — os dois "comecei" saíram antes de qualquer "terminei". As duas tarefas estão em andamento ao mesmo tempo, intercaladas. É a cozinha da lição 02: um cozinheiro, duas panelas.

O que o `gather` faz: pega cada corrotina e a embrulha numa **Task**. Task é uma corrotina agendada — entregue ao loop com a instrução "toque isto adiante sozinho, quando puder". Com duas Tasks na fila, o `await asyncio.sleep(1)` de `a` deixa de ser tempo morto: o loop aproveita a pausa para começar `b`.

Guarde a divisão de trabalho, porque ela é o coração do modelo:

- **`await`** marca onde é seguro pausar.
- **`gather` (ou `create_task`)** coloca mais de uma coisa em andamento.

Dívida da lição 01 quitada: era isso que o `carga.py` estava fazendo com as dez requests.

E uma nota que vale para o resto do capítulo: no FairFare a gente vai escrever muito `await` e **nenhum** `gather`. Não é distração — é que num servidor web quem cria a concorrência não é o seu código. Cada request que chega já vira uma Task, criada pelo uvicorn. Suas rotas são as panelas; o servidor é o cozinheiro.

## Cena 3: o loop é uma thread só, e isso tem consequências

Troque o `asyncio.sleep(1)` por `time.sleep(1)` e mantenha o `gather`:

```
  [a] comecei
  [a] terminei
  [b] comecei
  [b] terminei
  total: 2.00s  <- 2s: o gather não salva ninguém
```

Dois segundos, e as mensagens voltaram a sair em blocos. O `gather` continua ali, as Tasks continuam criadas — e não adiantou nada.

Aqui está o event loop em uma frase: **uma thread, uma fila de tarefas prontas, e um laço que roda cada uma até ela pausar.** Só isso. Não há supervisor, não há relógio interrompendo ninguém, não há preempção. A tarefa roda **até decidir devolver o controle**.

`asyncio.sleep(1)` devolve o controle (é para isso que ele existe). `time.sleep(1)` não devolve nada: ele segura a única thread do loop e o laço não avança para a próxima tarefa. `b` não começa porque, do ponto de vista do loop, `a` ainda está rodando.

Isso explica a lição 01 sem espaço para dúvida. A rota `async def` com `time.sleep` não estava lenta — ela estava impedindo o loop de girar. E agora dá para enunciar a regra sem analogia nenhuma:

> **Se uma corrotina não devolve o controle, ninguém mais roda. Nem o `gather`, nem outra request, nem o health check.**

O corolário incômodo: uma única linha bloqueante em qualquer lugar do caminho async derruba a concorrência do processo inteiro. Não do endpoint — do processo. É por isso que a lição 04 é dedicada a caçar essas linhas.

## Cena 4: corrotina sem `await` não roda

```python
coro = tarefa("fantasma", 0)
print(f"  o que voltou: {coro!r}")
```

```
  o que voltou: <coroutine object tarefa at 0x737bcf89b840>
  nada foi executado. o await é quem entrega ao loop.
```

Nenhum "comecei". Nenhum "terminei". Chamar uma corrotina **não a executa** — devolve um objeto corrotina, que é a tarefa embalada, parada, esperando alguém entregá-la ao loop. Quem entrega é o `await` (ou o `gather`, ou o `create_task`).

Esse é o bug mais comum de quem está começando, e ele é traiçoeiro porque não estoura: a função simplesmente não acontece. Seu `db.commit()` sem o `await` não grava nada, e nenhuma exceção aparece.

Python te dá um aviso — se você deixar o objeto ser coletado sem usar:

```
RuntimeWarning: coroutine 'tarefa' was never awaited
```

Decore essa mensagem. Ela é a que mais vai te salvar neste capítulo. Quando um comportamento "sumiu" sem erro nenhum, procure por ela na saída antes de procurar qualquer outra coisa.

*(Na cena 4 a gente chama `coro.close()` no fim justamente para não poluir a saída com o warning — a cena é sobre o objeto, não sobre o aviso.)*

## Quem liga o loop

Falta uma peça: alguém precisa criar o loop e girá-lo. Nos scripts da bancada, é a última linha:

```python
asyncio.run(main())
```

`asyncio.run` faz três coisas, nesta ordem: cria um event loop, roda a corrotina que você passou até ela terminar, e fecha o loop. É a ponte entre o mundo síncrono (o `python arquivo.py`) e o mundo async.

**No FairFare você nunca vai escrever essa linha.** Quem cria e gira o loop é o uvicorn, antes de a primeira request chegar. Suas rotas `async def` são corrotinas que ele agenda como Tasks — uma por request. Você escreve as panelas; o cozinheiro já está contratado.

É por isso, aliás, que `asyncio.run` dentro de uma rota é um erro clássico: já existe um loop rodando, e tentar criar outro na mesma thread estoura na hora.

## O que você deve conseguir fazer agora

- Explicar a diferença entre `await f()` e `await gather(f(), g())` — e por que a primeira forma não concorre.
- Dizer o que `async def` cria (uma corrotina pausável) e o que ele não cria (thread, processo, paralelismo).
- Explicar por que a cena 3 não melhorou nem com o `gather`.
- Reconhecer `RuntimeWarning: coroutine ... was never awaited` e saber o que ele significa.
- Dizer quem cria o event loop num script de bancada e quem cria num app FastAPI.
