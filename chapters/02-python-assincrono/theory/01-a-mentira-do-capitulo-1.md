# Lição 01 — Eu te menti no fim do capítulo 1

## A frase

Estava lá, no README do capítulo 1, na seção "Ao terminar":

> E uma notícia desconfortável: **nosso servidor atende uma pessoa de cada vez.** Sério. Enquanto uma request espera o banco, todas as outras esperam a request.

Boa frase. Cria tensão, promete cura, abre o capítulo seguinte.

E é falsa.

(Se você for conferir, não vai encontrá-la: o README do capítulo 1 já traz a versão corrigida, e a original ficou registrada na `ERRATA.md`. No checkpoint `v-chapter-01`, ela ainda está no lugar.)

## Eu te menti

Não foi malandragem, foi descuido — eu repeti uma frase que se ouve em todo lugar sem medir. Mas o estrago é o mesmo, e por isso ela abre o capítulo em vez de sumir numa correção discreta.

O contrato deste curso é medir o que afirma. Então a primeira coisa que a gente vai medir derruba uma afirmação do próprio autor. É o melhor uso possível de um instrumento novo: apontar para casa primeiro.

Vamos montar a bancada e ver o tamanho da mentira.

## A bancada

Dois endpoints. A diferença entre eles é de **três letras**.

`chapters/02-python-assincrono/bancada/servidor.py`:

```python
import time

from fastapi import FastAPI

app = FastAPI(title="bancada")


@app.get("/sync")
def rota_sync():
    time.sleep(1)  # finge um I/O lento: banco, rede, disco
    return {"ok": "sync"}


@app.get("/async-bloqueante")
async def rota_async_bloqueante():
    time.sleep(1)  # o MESMO sleep — e é aqui que o mundo para
    return {"ok": "async-bloqueante"}
```

O `time.sleep(1)` é um dublê. Ele finge o que um backend de verdade faz o tempo todo: esperar. Esperar o banco responder, esperar uma API externa, esperar o disco. Um segundo é uma eternidade para um computador e um piscar de olhos para você — perfeito para medir.

E o disparador, `bancada/carga.py`, que faz N requests ao mesmo tempo e cronometra:

```python
async def main() -> None:
    url = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    async with httpx2.AsyncClient(timeout=120) as client:
        comeco = time.perf_counter()
        codigos = await asyncio.gather(*(uma(client, url) for _ in range(n)))
        total = time.perf_counter() - comeco

    print(f"{n} requests em {total:.2f}s  (status: {set(codigos)})")
```

Tem magia nesse código, e magia sem aviso é dívida. O aviso: **`asyncio.gather` dispara todas as requests ao mesmo tempo em vez de uma depois da outra.** Por enquanto, aceite. A lição 03 abre a caixa e mostra como isso funciona por dentro — inclusive esse `async`/`await` que você está vendo antes de eu ter explicado.

## A medição

Numa aba, o servidor:

```bash
uv run uvicorn bancada.servidor:app --port 8123 --app-dir chapters/02-python-assincrono
```

Em outra, a carga — 10 requests simultâneas em cada rota:

```bash
uv run python chapters/02-python-assincrono/bancada/carga.py http://localhost:8123/sync 10
uv run python chapters/02-python-assincrono/bancada/carga.py http://localhost:8123/async-bloqueante 10
```

O que saiu aqui:

| Rota | 10 requests de 1s cada | Leitura |
|---|---|---|
| `/sync` (`def`) | **1,02s** | atendeu as 10 ao mesmo tempo |
| `/async-bloqueante` (`async def`) | **10,03s** | atendeu uma por vez |

Seus números vão variar um pouco. A ordem de grandeza, não: um segundo contra dez.

Leia a tabela devagar, porque ela é o contrário do que quase todo mundo diria. A rota "antiga", `def`, é a que atende dez pessoas ao mesmo tempo. A rota `async def` — a moderna, a que supostamente existe *para* isso — atendeu **uma pessoa de cada vez**.

A frase do capítulo 1 não era só falsa. Ela descrevia com precisão o outro caso.

## Por que

**A rota `def`.** Quando você escreve uma rota sem `async`, o FastAPI (por baixo, o Starlette) entende que aquele código pode bloquear e não a executa no fluxo principal: manda para um **threadpool**, um punhado de threads reservado justamente para código que trava. Dez requests, dez threads, e as dez esperas se sobrepõem: todo mundo dorme o seu segundo ao mesmo tempo que os outros. Total: um segundo. Você ganhou concorrência **sem pedir** — pagando uma thread por espera, o que é caro (volto nisso no fim da lição) — e é por isso que o FairFare do capítulo 1, que é `def` do primeiro router ao último, nunca foi um servidor de uma pessoa por vez.

**A rota `async def`.** Aqui o código roda no **event loop** — uma única thread que reveza entre todas as requests. O revezamento tem uma regra: cada tarefa devolve o controle quando começa a esperar. É um acordo, não uma imposição. E `time.sleep(1)` não cumpre o acordo. Ele trava a thread inteira, sem devolver nada a ninguém, por um segundo cravado. Como só existe uma thread, o servidor inteiro para junto: as outras nove requests, o health check, tudo. Dez vezes um segundo, em fila. Total: dez segundos.

A analogia: um garçom que anota o pedido, leva à cozinha e **fica parado esperando o prato ficar pronto** antes de atender a próxima mesa. Não é lentidão da cozinha; é escolha do garçom. Um garçom async faria o contrário — deixa o pedido, atende as outras mesas, volta quando a comida sai.

Agora a versão técnica, que é a que você precisa carregar: **o event loop é cooperativo.** Uma função `async` que executa uma operação bloqueante não fica lenta, ela fica *egoísta* — segura a única thread de execução e todo o resto do processo espera por ela.

Guarde a forma da frase: `async def` + código bloqueante = pior dos dois mundos. É a armadilha número um deste capítulo, e a gente vai voltar nela até virar reflexo (lição 04).

## O que a frase tinha de verdade

Mentira boa é a que carrega um pedaço de verdade. Aumente a carga e ela aparece.

Aquele threadpool não é infinito. Ele tem um teto, e dá para perguntar qual é:

```bash
uv run python -c "
import anyio, anyio.to_thread
async def m(): print(anyio.to_thread.current_default_thread_limiter().total_tokens)
anyio.run(m)"
```

Resposta: **40**.

Quarenta threads. Então vamos medir exatamente em cima da borda, sempre na rota `/sync`:

| Requests simultâneas | Tempo total |
|---|---|
| 40 | **1,05s** |
| 41 | **2,03s** |
| 80 | **2,09s** |

Olhe o pulo entre a primeira e a segunda linha. Quarenta requests: um segundo. **Quarenta e uma: dois segundos.** A quadragésima primeira pessoa não tem thread livre; ela espera uma vaga abrir, e só então começa o seu próprio segundo de espera. Ela pagou o dobro do preço, e a única coisa que ela fez de errado foi chegar por último.

Com 80 o padrão se confirma: dois lotes de 40, dois segundos.

Então a frase certa, a que substituiu a mentira no README do capítulo 1, é: *cada request do nosso servidor ocupa uma thread inteira, e existem só 40 delas.* Ou, virada para o usuário: atendemos no máximo 40 pessoas de cada vez — e pagamos uma thread por pessoa.

Melhor que uma? Muito. Suficiente? Não, e por dois motivos.

Primeiro, 40 é pouco quando as esperas são longas. Um endpoint que fala com uma API externa lenta enche o threadpool com quase ninguém no site.

Segundo, e mais importante: **thread por request é exatamente o custo que o async promete eliminar.** Cada thread carrega sua pilha de memória, e o sistema operacional gasta tempo alternando entre elas. Um event loop bem usado atende milhares de esperas simultâneas com uma thread só — porque esperar, para ele, não custa thread nenhuma. Custa uma anotação de "me avise quando chegar".

Esse é o prêmio no fim deste capítulo. E o caminho até ele começa entendendo por que a rota `async def` da nossa bancada, que tinha todo o ferramental para ganhar, perdeu feio.

## O que você deve conseguir fazer agora

- Subir a bancada e reproduzir os dois números na sua máquina.
- Explicar, para alguém que não leu esta lição, por que a rota `def` foi 10x mais rápida que a `async def`.
- Dizer o que o Starlette faz com uma rota `def` e o que ele faz com uma `async def`.
- Descobrir o teto do threadpool e explicar por que a 41ª pessoa espera o dobro.
- Desconfiar de qualquer afirmação de desempenho — inclusive das minhas — enquanto não vir o número.
