# Soluções — capítulo 2

Leia depois de tentar. Uma solução lida antes da tentativa vira informação; depois da tentativa, vira entendimento.

Cada item tem o código consertado, **por que aquele conserto e não outro**, e como você poderia ter chegado nele sozinho.

---

## Bloco 1 — Depurar: quem está travando o loop?

### Como localizar, antes de consertar

Duas ferramentas da lição 04, nesta ordem.

A primeira é aritmética: **total ≈ n × unitário é a assinatura do bloqueio.** Cinco requests de 0,3s levando 1,5s é uma fila. Levando 0,3s é concorrência. Rodar o `carga.py` nas três rotas antes de abrir o arquivo já te diz quais estão doentes, sem ler uma linha de código.

A segunda é o detector embutido:

```bash
PYTHONASYNCIODEBUG=1 uv run uvicorn rotas:app --port 8200 \
  --app-dir chapters/02-python-assincrono/exercises/bloco1
```

Cada request bloqueante deixa um `took 0.3 seconds` no log. Um loop saudável mede em milissegundos.

### `/lenta`

```python
@app.get("/lenta")
async def lenta():
    await asyncio.sleep(0.3)
    return {"rota": "lenta"}
```

`time.sleep` segura a thread do loop sem devolver o controle; `asyncio.sleep` devolve. É a cena 3 da lição 03, inteirinha, dentro de uma rota.

Repare que a `/rapida` — a que já passava — é *idêntica* a esta. A diferença entre elas sempre foi uma palavra.

### `/misteriosa`

```python
@app.get("/misteriosa")
async def misteriosa():
    total = await asyncio.to_thread(lambda: sum(i * i for i in range(VOLTAS_DE_CPU)))
    await asyncio.sleep(0.3)
    return {"rota": "misteriosa", "total": total}
```

Duas mudanças, porque havia **dois** problemas de naturezas diferentes:

1. O `sum(...)` é **CPU-bound**. Nenhum `asyncio.sleep` no mundo resolveria isso — não há espera para tornar cooperativa, há trabalho. A saída é tirá-lo do loop: `asyncio.to_thread`.
2. O `time.sleep(0.3)` é **I/O-bound** fingido, e vira `asyncio.sleep`.

**A lição de método está aqui, e ela vale mais que o conserto.** Se você trocou só o `time.sleep` e rodou o teste, ele continuou vermelho — e a conclusão tentadora é "meu conserto estava errado". Não estava. Havia dois problemas empilhados, e cada conserto certo revelou o próximo. É o mesmo padrão do capítulo 0: consertar-observar-consertar, e cada erro que muda de forma é progresso.

Uma honestidade sobre o `to_thread` aqui, que a lição 10 já tinha adiantado: ele resolve o **bloqueio do loop**, não o GIL. As cinco requests continuam disputando a mesma trava para calcular, e por isso a versão consertada leva ~0,8s e não ~0,3s. O que a gente comprou foi que o servidor **inteiro** deixou de congelar — as outras rotas voltaram a responder. Se esse cálculo fosse pesado de verdade, a resposta certa não seria thread nenhuma: seria outro processo, ou uma fila (capítulo 7).

---

## Bloco 2 — Estender: duas esperas que podiam ser uma

```python
@app.get("/painel")
async def painel():
    reservas, recursos = await asyncio.gather(buscar_reservas(), buscar_recursos())
    return {"reservas": reservas, "recursos": recursos}
```

Uma linha no lugar de duas, e o tempo cai de 0,8s para 0,4s.

**Por que trocar a ordem dos `await` não resolve.** É a tentação óbvia, e ela não leva a lugar nenhum: `await A` seguido de `await B` executa A inteiro e depois B, em qualquer ordem que você escreva. `await` não é "comece isto"; é "pause aqui até isto terminar" (lição 03, cena 1). Enquanto as duas chamadas estiverem em linhas separadas com `await` na frente, elas são sequenciais.

Quem cria concorrência é o `gather`, porque ele embrulha as duas corrotinas em Tasks e as entrega ao loop **antes** de esperar por qualquer uma.

**A pré-condição, que é o que realmente importa aprender:** isso só é válido porque `buscar_recursos()` não precisa do resultado de `buscar_reservas()`. Se precisasse, não haveria otimização possível — a dependência entre os dados é uma restrição da realidade, não do Python. (Era essa a pergunta bônus do enunciado.)

**Confirme por fora.** O teste já prova, mas o `carga.py` prova de novo, contra o servidor de pé (o bloco 2 também é um app FastAPI — sobe igual ao do bloco 1, só noutra porta):

```bash
uv run uvicorn rotas:app --port 8201 --app-dir chapters/02-python-assincrono/exercises/bloco2
```

e, noutra aba:

```bash
uv run python chapters/02-python-assincrono/bancada/carga.py http://localhost:8201/painel 10
```

### A forma moderna: `TaskGroup`

Desde o Python 3.11 existe uma alternativa, e ela é a recomendada para código novo:

```python
async with asyncio.TaskGroup() as tg:
    t_reservas = tg.create_task(buscar_reservas())
    t_recursos = tg.create_task(buscar_recursos())
return {"reservas": t_reservas.result(), "recursos": t_recursos.result()}
```

Mais verboso, e melhor num ponto específico: **tratamento de erro.** Se uma das duas tarefas explodir, o `TaskGroup` cancela a outra automaticamente e propaga tudo junto. Com `gather` no padrão, o irmão continua rodando sozinho — e você pode acabar com uma tarefa órfã trabalhando para uma request que já morreu.

Para este exercício, `gather` está perfeito. Guarde o `TaskGroup` para quando as tarefas paralelas tiverem efeitos colaterais que você não quer deixar pela metade.

---

## Bloco 3 — Refatorar: async por fora, bloqueante por dentro

Este bloco tem três funções e **três decisões diferentes**. A régua é a das três perguntas da lição 08: *espera alguém? tem fila atrás? a lib colabora?*

(Detalhe de manutenção que os trechos abaixo assumem: o `servico.py` original não importa `asyncio` — os consertos pedem um `import asyncio` no topo. E o `import time` fica órfão depois deles; apague, que o único trabalho dele era bloquear.)

### `buscar` — vira async de verdade

```python
async def buscar(item_id: int) -> dict:
    await asyncio.sleep(0.3)
    return {"id": item_id, "nome": f"item {item_id}"}
```

Espera alguém: sim (finge um serviço externo). Tem gente na fila atrás: sim, é chamada durante requests. A lib colabora: sim. Três sins — async de verdade, com `await` numa espera cooperativa.

Num código real, este seria o momento de trocar `requests` por `httpx2.AsyncClient`. O `time.sleep` aqui é o dublê de uma chamada de rede síncrona, e o conserto é o mesmo: usar a versão que devolve o controle.

### `resumo_pesado` — sai do loop

```python
async def resumo_pesado() -> int:
    return await asyncio.to_thread(lambda: sum(i * i for i in range(VOLTAS_DE_CPU)))
```

Espera alguém: **não**. É CPU pura. Mas ela trava o loop por um segundo inteiro, e o teste mede isso de um jeito bonito: uma tarefa paralela que deveria "bater" a cada 10ms e que, com o código quebrado, bate **zero** vezes.

`asyncio.to_thread` tira o cálculo da thread do loop. O servidor volta a responder enquanto a conta acontece.

E a honestidade obrigatória, pela terceira vez neste capítulo: **isso resolve o bloqueio, não resolve o GIL.** O cálculo continua disputando a trava com o resto do processo, e um segundo de CPU continua custando um segundo de CPU. Se fosse pesado de verdade e frequente, a resposta certa seria outro processo (`ProcessPoolExecutor`) ou tirá-lo do caminho da request e mandá-lo para uma fila de tarefas — capítulo 7. `to_thread` aqui é a válvula, e ela está sendo usada com consciência do preço.

### `carregar_config` — **deixa de ser async**

```python
def carregar_config() -> dict:
    return json.loads(CONFIG.read_text())
```

Este é o item mais importante do capítulo inteiro, e ele te pede para **desfazer** trabalho.

Aplique a régua com cuidado:

1. *Espera alguém?* Sim — lê um arquivo do disco.
2. *Espera enquanto outra pessoa poderia estar sendo atendida?* **Não.** Roda uma vez, na subida do processo, antes de existir a primeira request. Não há fila. Não há ninguém para atender no meio-tempo.

A segunda pergunta já encerra o caso. É a mesma decisão do Alembic, na lição 08, pelo mesmo motivo — e é a pergunta que quase ninguém faz, porque "faz I/O, logo tem que ser async" é a regra que a gente decora sem entender.

E o `async` aqui não é neutro, é caro: como `async` é viral, toda função que chamar `carregar_config` precisa ser `async` também, e o custo sobe pela pilha inteira. Você adicionaria cerimônia a um monte de código para ganhar exatamente nada.

**Se a sua estratégia foi "colocar `await` em tudo", este teste foi escrito para te dizer não.** Não por implicância: converter tudo é o erro mais comum depois de aprender async, e ele produz código que parece moderno e é só mais difícil de ler.

---

## O fio que costura os três blocos

Se você olhar as sete decisões destes exercícios, elas se reduzem a uma pergunta feita sete vezes: **o que este código está fazendo quando parece parado?**

- Esperando alguém, com gente na fila → `await`, se a biblioteca colaborar.
- Esperando alguém, com uma biblioteca que não colabora → `asyncio.to_thread`.
- Trabalhando → tire do loop, e saiba que o GIL continua ali.
- Parado sem ninguém esperando → deixe em paz.

Async não é um estilo de escrita. É uma resposta a uma pergunta sobre o que acontece com o tempo do seu processo — e a resposta é diferente para cada trecho de código.
