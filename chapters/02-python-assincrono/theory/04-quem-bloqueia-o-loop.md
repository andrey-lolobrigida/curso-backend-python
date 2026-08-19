# Lição 04 — Quem bloqueia o loop para o mundo

A lição 03 terminou com uma regra: se uma corrotina não devolve o controle, ninguém mais roda. Bonito no papel. O problema é que, no código real, o que bloqueia raramente vem com uma placa dizendo "eu bloqueio".

Esta lição é sobre caçar essas linhas.

## A regra, em uma frase

> **Dentro de uma função `async def`, tudo o que você escreve é rápido ou é `await`. Não existe terceira opção.**

Rápido significa: microssegundos, sem tocar em rede, disco ou banco. Comparar duas datas, montar um dicionário, formatar uma string — pode. Qualquer coisa que **espera alguém** precisa vir precedida de `await`. Se esperar sem `await`, você está segurando a única thread do processo.

Essa frase é o critério de revisão de código deste capítulo inteiro. Leia uma rota `async def` linha por linha e pergunte, para cada uma: isso é rápido, ou isso é um `await`?

## O catálogo do que bloqueia

Aqui está a parte desconfortável: a lista é banal. São as funções que você usa há anos, todas boas, nenhuma delas errada em si.

| Linha | O que ela faz | Por quanto tempo o loop para |
|---|---|---|
| `time.sleep(1)` | dorme | 1s |
| `requests.get(url)` | fala com uma API | o tempo da API |
| `open("arq.csv").read()` | lê disco | o tempo do disco |
| `session.query(...)` (SQLAlchemy síncrono) | consulta o banco | o tempo da query |
| `bcrypt.hashpw(...)` | calcula hash de senha | 100–300ms, **de CPU** |
| `json.loads(payload_gigante)` | parseia | proporcional ao tamanho |
| `for x in dez_milhoes: ...` | itera | o tempo do laço |
| `subprocess.run(...)` | roda um programa | o tempo do programa |

Olhe as três primeiras: elas são o dia a dia de qualquer backend. **A biblioteca `requests` é a coisa mais popular do ecossistema Python e é veneno dentro de uma rota `async`.** Não porque seja ruim — porque ela é síncrona, e síncrona dentro do loop significa "segura a thread até acabar".

Note também que a lista mistura as duas naturezas da lição 02. `requests.get` bloqueia por ser **I/O-bound** sem `await`; `bcrypt` bloqueia por ser **CPU-bound**, e nenhum `await` no mundo o salvaria. São dois problemas com o mesmo sintoma e curas diferentes — volte a isso quando chegar no fim da lição.

## Por que ninguém percebe em desenvolvimento

Aqui está o motivo de esse bug chegar tão longe: **com um cliente só, bloquear é invisível.**

Você abre o navegador, chama a rota, ela responde em 300ms. Perfeito. Você chama de novo, 300ms. Tudo funcionando. Não existe "outra request" sendo prejudicada, porque não existe outra request — é você sozinho no localhost.

Bloqueio não é um defeito que aparece numa chamada. É um defeito que aparece na **soma** das chamadas simultâneas. Com dez clientes, aquela rota de 300ms vira 3 segundos para o azarado do fim da fila — e, pior, ela leva junto todas as **outras** rotas do app, que não têm nada a ver com o problema.

É a diferença entre testar e medir. E é literalmente por isso que a bancada existe: `carga.py` é o mínimo necessário para transformar "parece rápido" em um número.

## Como detectar, do mais barato ao mais caro

### 1. Ler o código (custo zero)

Procure, dentro de qualquer `async def`, uma chamada que fale com o mundo e **não** tenha `await` na frente. É rápido, funciona, e pega a maioria dos casos. O truque mental: `async def` sem nenhum `await` no corpo é quase sempre um erro — ou a função não precisava ser async, ou ela está bloqueando.

### 2. Ligar o modo debug do asyncio (custo: uma variável de ambiente)

O Python tem um detector embutido. Suba o servidor com `PYTHONASYNCIODEBUG=1`:

```bash
PYTHONASYNCIODEBUG=1 uv run uvicorn bancada.servidor:app --port 8125 --app-dir chapters/02-python-assincrono
```

Em outra aba, três requests na rota bloqueante:

```bash
uv run python chapters/02-python-assincrono/bancada/carga.py http://localhost:8125/async-bloqueante 3
```

E o servidor entrega o culpado:

```
Executing <Task finished name='Task-9' coro=<RequestResponseCycle.run_asgi() done,
defined at .../uvicorn/protocols/http/h11_impl.py:414> ... > took 1.002 seconds
```

Traduzindo: *uma tarefa ficou com o loop por 1,002 segundo sem devolver o controle.* O modo debug cronometra cada passagem pelo loop e reclama de qualquer uma que passe de 100 milissegundos.

A parte que importa é a última palavra: **`took 1.002 seconds`**. Um loop saudável mede em milissegundos. Quando você vir "seconds" nessa linha, tem código bloqueante no caminho.

Agora o contraste que fecha a lição 01. Rode as mesmas três requests na rota `/sync`, a `def`, com o debug ligado:

```
3 requests em 1.02s
avisos no log: 0
```

Nenhum aviso. E é justo: a rota `def` bloqueia uma **thread do threadpool**, que existe para isso, e o loop continua girando livre. O detector não está sendo leniente — ele está medindo exatamente a coisa certa.

Duas ressalvas honestas sobre essa ferramenta. Ela deixa o processo mais lento (é instrumentação, não é para produção). E o traceback que ela imprime aponta para as entranhas do uvicorn, não para a sua linha — ele diz *que* alguém bloqueou, não *quem*. Para achar o quem, você volta ao método 1, agora sabendo em qual endpoint procurar.

*(Curiosidade que a gente mediu por desconfiança: o aviso também sai quando o servidor roda com `uvloop`, o event loop alternativo mais rápido. Dava para supor o contrário, já que o `uvloop` é uma implementação em C — mas fomos ver, e ele emite os mesmos avisos.)*

### 3. Medir com carga (custo: 30 segundos)

O teste definitivo, e o único que funciona em qualquer código, seu ou de terceiros:

```bash
uv run python chapters/02-python-assincrono/bancada/carga.py <url> 1
uv run python chapters/02-python-assincrono/bancada/carga.py <url> 10
```

A assinatura do bloqueio é aritmética: **tempo total ≈ n × tempo unitário.** Dez requests de 1s levando 10s é uma fila. Dez requests de 1s levando 1s é concorrência. Não precisa de mais nada para saber em qual dos dois mundos você está.

Essa é a medição que a lição 01 fez, e é a que a lição 09 vai repetir no FairFare de verdade — antes e depois da migração.

## As duas saídas

Encontrou o bloqueio. E agora?

**Saída 1 — trocar por uma versão awaitable (a boa).** Existe uma biblioteca async que faz a mesma coisa e devolve o controle enquanto espera. `requests` → `httpx2` com `AsyncClient`. Driver de banco síncrono → driver async. `time.sleep` → `asyncio.sleep`. É a saída certa para tudo que é I/O, e é o caminho que o FairFare inteiro vai seguir a partir da lição 06.

Ela tem um pré-requisito que a lição 05 vai atacar de frente: **essa biblioteca precisa existir e você precisa usá-la certo**. Escrever `await` na frente de código síncrono não transforma nada.

**Saída 2 — empurrar para uma thread (a válvula).** Quando não existe versão async, ou quando a operação é CPU-bound de verdade:

```python
resultado = await asyncio.to_thread(bcrypt.hashpw, senha, sal)
```

`asyncio.to_thread` manda a função para uma thread separada e devolve o controle ao loop enquanto ela roda. É exatamente o que o FastAPI faz sozinho com as rotas `def` — você está fazendo à mão, para um pedaço de código em vez do endpoint inteiro.

Chame de válvula de escape, não de solução: você voltou a gastar uma thread por operação, com o teto e o custo que a lição 01 mostrou. É a ferramenta certa para o caso pontual e a ferramenta errada para o caminho principal do seu app.

A lição 10 volta nessa segunda saída, quando o GIL entrar na conversa e a distinção entre "thread para esperar" e "thread para calcular" começar a doer.

## O que você deve conseguir fazer agora

- Ler uma rota `async def` e apontar as linhas que bloqueiam.
- Explicar por que `requests.get` dentro de uma rota async é um problema e dentro de uma rota `def` não é.
- Ligar o `PYTHONASYNCIODEBUG=1` e reconhecer o aviso de tarefa lenta.
- Provar bloqueio com um número: `tempo total ≈ n × tempo unitário`.
- Escolher entre trocar a biblioteca e usar `asyncio.to_thread` — e dizer por que a segunda é uma válvula, não uma cura.
