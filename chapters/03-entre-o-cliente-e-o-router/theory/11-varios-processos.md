# Lição 11 — Mais de um processo, e o que acontece quando o processo para

O capítulo veio de dentro para fora: o ASGI cru, os freios do servidor, o middleware, o CORS, o rate limit, o proxy, a fronteira de confiança, o TLS. Falta uma peça que não é uma camada nova — é uma **cópia**. Rodar o mesmo app várias vezes ao mesmo tempo.

A ideia inteira desta lição cabe numa frase: **o seu app não é um processo.** Tudo que você guardou dentro de um processo achando que estava guardando "no app" vai descobrir isso hoje.

## Por que mais de um

Uma trava por processo Python, e dentro dele o bytecode roda em **uma thread por vez** — o GIL, da lição 10 do capítulo 2. O async resolveu a espera — enquanto uma request espera o banco, outra roda. Mas ele não resolveu, e não tinha como resolver, a parte que é CPU: serializar JSON, validar um Pydantic, montar um SQL. Isso é bytecode, e bytecode faz fila.

Nesta máquina:

```console
$ nproc
12
```

Doze núcleos. Um uvicorn sozinho usa um; os outros onze assistem. Sendo exato, porque a frase é boa demais para ficar solta: o que usa um núcleo por vez é a **execução de bytecode Python**. Uma extensão em C que solte o GIL enquanto trabalha — comprimir, criptografar, redimensionar uma imagem — sai desse gargalo e usa outro núcleo real. O que faz fila é o Python do seu router.

A saída é a mesma de lá: **processo é a unidade de paralelismo em Python**. Quatro processos, quatro interpretadores, quatro GILs, paralelismo de verdade. O uvicorn faz isso com uma flag:

```bash
uv run uvicorn app.main:app --port 8000 --workers 4
```

```console
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started parent process [25344]
INFO:     Started server process [25347]
INFO:     Started server process [25346]
INFO:     Waiting for application startup.
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Application startup complete.
INFO:     Started server process [25348]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Started server process [25349]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

Repare em duas coisas. Primeiro, **`Started server process` aparece quatro vezes, com quatro PIDs diferentes** — e o `Application startup complete` também. O `lifespan` da lição 01 roda uma vez por worker, não uma vez por servidor. Segundo, **a linha da porta aparece uma vez só**. Os quatro processos compartilham um socket na 8000: quem chama `bind()` é o processo pai, que passa o socket já aberto para os filhos (está em `.venv/lib/python3.12/site-packages/uvicorn/main.py` — procure `bind_socket`; são três linhas). É o kernel que decide qual deles vai aceitar cada conexão nova.

Contando os filhos por fora:

```console
$ ps --ppid 25344 -o pid=,cmd=
  25345 .venv/bin/python -c from multiprocessing.resource_tracker import main;main(7)
  25346 .venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=8, pipe_handle=10) --multiprocessing-fork
  25347 .venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=8, pipe_handle=14) --multiprocessing-fork
  25348 .venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=8, pipe_handle=18) --multiprocessing-fork
  25349 .venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=8, pipe_handle=22) --multiprocessing-fork
```

**Cinco** filhos, não quatro, e o primeiro não é um worker. O `resource_tracker` é um processo auxiliar do módulo `multiprocessing` da biblioteca padrão, que existe para limpar recursos compartilhados se alguém morrer feio. Se você contar filhos com `wc -l` vai ler `5` e achar que a flag está errada. Não está: são quatro workers (os `spawn_main`) mais um faxineiro.

## A medição que estraga a lição 05

Agora a parte que interessa. O rate limiter da lição 05 é de 20 fichas por cliente, recarregando 5 por segundo. Cem requests de uma vez, do mesmo cliente, contra o mesmo FairFare — só mudando `--workers`:

```bash
C=chapters/03-entre-o-cliente-e-o-router/bancada/carga.py
uv run python $C http://localhost:8000/users 100
```

| Workers | Rodada | Resultado |
|---|---|---|
| 1 | 1 | `100 requests em 0.11s  status → 200: 20  429: 80  (Retry-After: 1s)` |
| 1 | 2 | `100 requests em 0.10s  status → 200: 20  429: 80  (Retry-After: 1s)` |
| 4 | 1 | `100 requests em 0.10s  status → 200: 61  429: 39  (Retry-After: 1s)` |
| 4 | 2 | `100 requests em 0.11s  status → 200: 67  429: 33  (Retry-After: 1s)` |
| 4 | 3 | `100 requests em 0.11s  status → 200: 62  429: 38  (Retry-After: 1s)` |

*(Uma sessão só, com seis segundos de pausa entre as rodadas para os baldes recarregarem.)*

Com um worker, `20`. Vinte, exato, nas duas rodadas — é a capacidade do balde, e o limitador está fazendo exatamente o que a lição 05 prometeu.

Com quatro workers, **três vezes mais gente passa**. O limite que você escreveu era 20; o limite que o cliente sentiu foi 61, 67, 62.

Duas perguntas, nessa ordem.

**Por que passou mais?** Porque `self.baldes` é um `dict` num atributo de instância, e cada worker tem a sua instância. São quatro dicionários independentes. O mesmo cliente, `127.0.0.1`, tem quatro baldes de 20 fichas — um em cada processo — e nenhum deles sabe dos outros. O middleware está correto; a suposição de que existe *um* middleware é que não estava.

**Por que não foi 80, então?** Porque o kernel distribui as conexões entre os workers sem prometer nada sobre igualdade. Não há rodízio: os quatro esperam no mesmo socket e quem estiver pronto primeiro leva.

E o sorteio é por **conexão**, não por request. Medi com `ss` numa rodada à parte, enquanto a carga corria: o pico foi de cem conexões estabelecidas na 8000, uma para cada request. Cem sorteios, então.

Um worker pode ficar com trinta (gasta as 20 fichas e recusa 10) enquanto outro fica com quinze (e sobra ficha sem uso). Fichas sobrando num balde não ajudam a request que caiu no balde vazio do vizinho. Quatro baldes de 20 dão *até* 80, e o que se vê na prática é menos. (Se o cliente reaproveitasse conexões em vez de abrir cem, o desequilíbrio seria ainda maior, e por outro motivo: uma conexão fica presa ao worker que a aceitou, e todas as requests dela caem no mesmo balde.)

O número exato vai dançar na sua máquina. O que não dança é a direção: **o limite se multiplica pelo número de workers, de forma desigual e imprevisível.**

Guarde a frase, porque ela é maior que o rate limiter:

**estado em memória não é estado do app, é estado do processo.**

Você já viu essa frase agir uma vez, disfarçada. A lição 05 tem uma linha estranha no `conftest.py` — `fastapi_app.middleware_stack = None` — que existe porque o processo do pytest também é *um* processo, com *um* balde, e um teste deixava o balde vazio para o próximo. Lá era um teste quebrando. Aqui é o limite do seu app valendo o triplo em produção. Mesma causa, dois tamanhos.

Isto é uma **limitação declarada**, não um bug escondido: está escrita no topo de `app/middleware/rate_limit.py` desde a lição 05, a lição 12 vai recolhê-la junto com as outras, e o conserto tem endereço — **capítulo 6**, quando os baldes saírem da memória do processo e forem para o Redis, que é um lugar que os quatro workers enxergam.

## E o pool foi junto

O mesmo raciocínio, aplicado a outra coisa que você configurou uma vez e achou que era global. Em `app/database.py`:

```python
    pool_size=5,  # conexões mantidas abertas
    max_overflow=10,  # extras sob pico, descartadas depois
```

Cinco mais dez são quinze conexões — **por processo**. Com `--workers 4`, o app pode abrir 60. O teto de que a lição 09 do capítulo 2 falava mudou de lugar de novo, e agora ele tem um multiplicador que não está escrito em lugar nenhum do código: está na linha de comando.

Aqui isso ainda não dói, porque o banco é um arquivo SQLite. Vai doer no capítulo 4, quando o FairFare for para o PostgreSQL — que tem um limite próprio de conexões, para o servidor inteiro, e não se importa nem um pouco com quantos workers você achou que podia subir.

## `--reload` e `--workers` não convivem

Uma armadilha barata de cair. As duas flags juntas:

```bash
uv run uvicorn app.main:app --port 8000 --workers 4 --reload
```

```console
INFO:     Will watch for changes in these directories: ['/home/andrey/PycharmProjects/python-backend-course']
WARNING:  "workers" flag is ignored when reloading is enabled.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [25595] using StatReload
INFO:     Started server process [25597]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

O aviso está lá, no meio do barulho de subida, e é fácil de não ver. Um `Started server process` só. Contando os filhos, dois — o `resource_tracker` e o único worker:

```console
$ ps --ppid 25595 -o pid=,cmd=
  25596 .venv/bin/python -c from multiprocessing.resource_tracker import main;main(5)
  25597 .venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=6, pipe_handle=8) --multiprocessing-fork
```

Regra simples: **`--reload` é ferramenta de desenvolvimento, `--workers` é ferramenta de produção.** Elas nunca aparecem no mesmo comando. Se você medir rate limit com as duas juntas achando que tem quatro workers, você mede um worker e conclui besteira.

## O que acontece quando o processo para

A outra metade da fronteira do processo. Um processo não só *guarda* coisas — ele também **morre**, e quase sempre no meio de alguma request.

Para ver isso preciso de uma request lenta, e o espelho da lição 08 ganhou uma:

```python
    if scope["path"] == "/lento":
        await asyncio.sleep(5)  # uma request em voo, para a demonstração de shutdown gracioso
```

Sobe o espelho numa aba e dispara `/lento` na outra; um segundo depois, o `SIGINT` que o Ctrl+C manda.

```bash
B=chapters/03-entre-o-cliente-e-o-router/bancada
uv run uvicorn eco:app --port 8000 --app-dir $B
```

```bash
curl -s -w '\ncurl terminou com %{http_code} em %{time_total}s\n' localhost:8000/lento
```

O terminal do servidor:

```console
INFO:     Shutting down
INFO:     Waiting for connections to close. (CTRL+C to force quit)
INFO:     127.0.0.1:33668 - "GET /lento HTTP/1.1" 200 OK
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [25646]
```

E o do `curl` (o corpo da resposta, que é o JSON do espelho de sempre, foi cortado daqui):

```console
curl terminou com 200 em 5.003400s
```

Leia a ordem das linhas: o servidor recebeu o sinal, **parou de aceitar conexões novas**, esperou a que estava em voo terminar, respondeu `200`, e só então rodou o shutdown do `lifespan` e morreu. Isso é **shutdown gracioso**: o processo não some no meio da frase. A request que já estava sendo atendida é atendida até o fim.

Só que essa espera não pode ser infinita — um cliente com uma conexão pendurada impediria o servidor de morrer para sempre. Existe um prazo, e ele tem flag. Com um segundo de paciência e uma request que precisa de cinco:

```bash
uv run uvicorn eco:app --port 8000 --app-dir $B --timeout-graceful-shutdown 1
```

```console
INFO:     Shutting down
INFO:     Waiting for connections to close. (CTRL+C to force quit)
ERROR:    Cancel 1 running task(s), timeout graceful shutdown exceeded
INFO:     Waiting for application shutdown.
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  (...)
  File "chapters/03-entre-o-cliente-e-o-router/bancada/eco.py", line 21, in app
    await asyncio.sleep(5)  # uma request em voo, para a demonstração de shutdown gracioso
  (...)
asyncio.exceptions.CancelledError: Task cancelled, timeout graceful shutdown exceeded
INFO:     127.0.0.1:37328 - "GET /lento HTTP/1.1" 500 Internal Server Error
INFO:     Application shutdown complete.
```

```console
Internal Server Error
curl terminou com 500 em 2.198978s
```

*(O traceback está encurtado nos dois `(...)` — as linhas de fora são frames do uvicorn e do `asyncio` — e os caminhos absolutos foram encurtados aqui e nas saídas do `ps` lá em cima, para caber na página. O resto é literal.)*

Esse `500` é o fato interessante desta lição, e é uma surpresa. O uvicorn **não** derruba a conexão quando o prazo estoura — seria o que a intuição diz, e seria mais honesto. O que ele faz é **cancelar a task** da sua coroutine. E cancelar uma task do jeito do asyncio significa levantar `CancelledError` de dentro do `await` — a exceção sobe pelo seu código como qualquer outra, o uvicorn a trata como "explodiu no app" e responde a única coisa que sabe responder quando o app explode: `500 Internal Server Error`. Isso vale **enquanto a resposta ainda não começou** — se os headers já tivessem ido para a rede, não dava para voltar atrás e o uvicorn aí sim derrubaria a conexão. Aqui a request morreu dentro do `sleep`, antes de qualquer byte sair.

Ou seja: um deploy apertado demais não entrega ao cliente um erro de rede, que uma biblioteca decente repetiria. Entrega um `500` bonito e bem-formado, indistinguível de um bug seu.

É por isso que esse número importa fora do laboratório. Todo deploy é uma troca de processos: sobe o novo, para o velho. Se o prazo do velho for menor que a request mais lenta que ele atende, cada deploy espirra `500` em quem estava no meio de alguma coisa. **Deploy sem downtime começa aqui** — e continua no capítulo 10, com quem manda o sinal, quem espera, e quem tira o processo velho do balanceador antes de qualquer uma dessas coisas.

## O que fica declarado

- **Tudo aqui foi medido no Linux.** O uvicorn documenta `--workers` no Windows também (via `spawn`, que é justamente o que aparece nos `ps` acima), mas **não foi verificado nesta máquina**. Se falhar por lá, o caminho conhecido é o WSL.
- **Os números da tabela são desta máquina, nesta sessão.** Doze núcleos, loopback, SQLite. A direção se repete em qualquer lugar; os valores exatos, não — e a própria tabela já mostra 61, 67 e 62 para a mesma pergunta.
- **`--workers` não é um número de sorte.** Não medi qual é o melhor valor aqui, e "um por núcleo" é regra de bolso, não resultado. Medir isso direito precisa de carga parecida com a real e de um banco de verdade — nenhum dos dois existe nesta bancada.
- **Um worker que morre sozinho não foi testado.** A demonstração do Ctrl+C rodou com o `eco.py` em um processo só — mandei sinal em quem estava atendendo, e não havia pai nem irmão para reagir. Quem devolve o worker que caiu — o pai do uvicorn, um supervisor, um orquestrador — é assunto do capítulo 10.
- **O rate limiter continua com os três problemas declarados desde a lição 05.** Esta lição só mostrou o primeiro deles acontecendo na tela.

## O que você deve conseguir fazer agora

- Explicar por que quatro workers multiplicam por **até** quatro o limite do rate limiter — e por que o medido deu três, e não quatro.
- Dizer onde o estado do rate limiter precisa morar para que o limite valha para o app inteiro, e por que o `dict` em memória nunca vai dar conta disso.
- Descrever o que acontece com uma request em voo num Ctrl+C, com e sem `--timeout-graceful-shutdown`, incluindo qual status o cliente recebe em cada caso.
