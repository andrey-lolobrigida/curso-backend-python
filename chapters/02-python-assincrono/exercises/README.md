# Exercícios do capítulo 2

**Aviso, porque isto importa: os arquivos dos blocos 1 e 3 contêm código quebrado de propósito.**

O FairFare, em `app/`, está correto — o que você encontrar de errado lá vale um issue. O que está *aqui* foi escrito errado de caso pensado, para você consertar. O bloco 2 é a exceção: ele funciona, só está lento.

Cada bloco tem testes que você mesmo roda. O teste é a definição de "pronto": enquanto ele estiver vermelho, o exercício não acabou. E, ao contrário do capítulo 1, aqui quase todos os testes medem **tempo** — porque a coisa que você está aprendendo a consertar só aparece em número.

Nenhum destes testes é coletado pelo `uv run pytest` do projeto (o `testpaths` do `pyproject.toml` cuida disso). Você roda cada bloco apontando o caminho.

Uma nota sobre os relógios: os limites de tempo dos testes foram calibrados numa máquina específica. Se o seu computador for bem mais lento e um teste falhar por pouco — tipo 1,6s contra um limite de 1,5s — não é você que está errado. Ajuste o limite, anote por quê, e siga.

---

## Bloco 1 — Depurar: quem está travando o loop?

**Arquivo:** `bloco1/rotas.py` — **contém código quebrado de propósito.**

Três rotas `async`. Todas deveriam atender cinco pessoas ao mesmo tempo, sem virar fila. Uma consegue (0,3s); as outras duas, não. Um aviso de calibragem: a `/misteriosa`, mesmo consertada, não vai chegar aos 0,3s da `/rapida` — ela carrega um trabalho de CPU que custa o que custa (a solução explica por quê, e o teste sabe disso).

Antes de consertar qualquer coisa, **veja o número ruim**. Suba a bancada:

```bash
uv run uvicorn rotas:app --port 8200 --app-dir chapters/02-python-assincrono/exercises/bloco1
```

e, noutra aba, dispare carga em cada rota:

```bash
uv run python chapters/02-python-assincrono/bancada/carga.py http://localhost:8200/rapida 5
uv run python chapters/02-python-assincrono/bancada/carga.py http://localhost:8200/lenta 5
uv run python chapters/02-python-assincrono/bancada/carga.py http://localhost:8200/misteriosa 5
```

Comparar os três números *antes* de abrir o código é o exercício de verdade. Depois:

```bash
uv run pytest chapters/02-python-assincrono/exercises/bloco1 -v
```

Aviso sobre a `/misteriosa`: ela tem **duas** causas de lentidão, de naturezas diferentes (lição 02 te deu os nomes). Consertar uma só não deixa o teste verde.

**Pronto quando:** os três testes passam, e você consegue explicar em uma frase o que cada conserto fez — e por que os dois consertos da `/misteriosa` são diferentes um do outro.

---

## Bloco 2 — Estender: duas esperas que podiam ser uma

**Arquivo:** `bloco2/rotas.py` — este **não** está quebrado. Ele funciona.

A rota `/painel` faz duas consultas que não dependem uma da outra e espera cada uma na sua vez. Faça as duas acontecerem ao mesmo tempo, sem mudar **nada** do que a rota devolve.

```bash
uv run pytest chapters/02-python-assincrono/exercises/bloco2 -v
```

São dois testes. O primeiro (o formato da resposta) já passa, e continuar passando é metade da tarefa: refatoração que muda o contrato da API não é refatoração, é bug. O segundo é o que você faz passar.

**Pronto quando:** os dois testes passam. Bônus, para responder de cabeça: se a segunda consulta precisasse do resultado da primeira, essa otimização seria possível?

---

## Bloco 3 — Refatorar: async por fora, bloqueante por dentro

**Arquivo:** `bloco3/servico.py` — **contém código quebrado de propósito.**

Este módulo foi "convertido para async" do jeito que a maioria das conversões reais sai no mundo: `async def` em tudo, bloqueio por dentro. É o capítulo 2 inteiro em três funções.

```bash
uv run pytest chapters/02-python-assincrono/exercises/bloco3 -v
```

Cada função pede uma decisão diferente, e a régua da lição 08 (as três perguntas) é o seu instrumento. Um aviso que vale ouro: **para uma das três funções, o conserto certo é ela deixar de ser `async`.** Se a sua estratégia for "colocar `await` em tudo", um dos testes vai te dizer não.

**Pronto quando:** os três testes passam, e você consegue justificar cada uma das três decisões usando as três perguntas — inclusive a de não fazer nada de async.
