# Lição 10 — O GIL

Uma pergunta que vai aparecer no FairFare mais cedo ou mais tarde:

> O app divide despesas. Um dia vai ter uma rota que calcula o saldo de todo mundo num grupo grande — muita conta, muita iteração, nada de banco no meio. Posso simplesmente calcular isso dentro da rota `async`?

Você já tem metade da resposta pela lição 02: cálculo é **CPU-bound**, e async não faz nada por CPU-bound. Esta lição é a outra metade — o que fazer então, e por que a solução "óbvia" (jogar em threads) não funciona em Python.

## O GIL, em uma frase

**GIL** é a *Global Interpreter Lock*: uma trava, uma por processo Python, que permite que **apenas uma thread execute bytecode Python de cada vez**.

Leia de novo, porque a frase é mais forte do que parece. Não importa quantas threads você criar nem quantos núcleos a máquina tenha: dentro de um processo Python, o código Python roda em uma thread por vez. As threads existem, alternam, dão a impressão de simultaneidade — mas para executar bytecode elas fazem fila.

A analogia: quatro cozinheiros na cozinha, mas uma faca só. Eles se revezam com a faca educadamente, e no fim do dia a quantidade de cebola picada é a mesma que um cozinheiro sozinho picaria — descontando o tempo perdido passando a faca de mão em mão.

E é *pior* que isso, porque passar a faca custa. Vamos medir.

## A medição

`bancada/cpu.py` faz a mesma soma pesada quatro vezes, de três jeitos: em série, em quatro threads, em quatro processos.

```bash
uv run python chapters/02-python-assincrono/bancada/cpu.py
```

Nesta máquina (12 núcleos, `nproc` conta):

```
em série                     1.05s
em 4 threads                 1.63s
em 4 processos               0.37s
```

Três leituras, e a do meio é a que dói:

**Em série: 1,05s.** É a linha de base — um núcleo trabalhando, sem truque nenhum.

**Em 4 threads: 1,63s.** Quatro threads, doze núcleos ociosos, e o resultado ficou **mais lento que fazer tudo em fila**. O GIL serializou a execução, e ainda cobrou o custo de alternar entre as threads o tempo todo. Você pagou a complexidade de concorrência para receber um prejuízo. (Rode de novo e o número dança — 1,88s na segunda vez daqui — porque contenção não é determinística.)

**Em 4 processos: 0,37s.** Quase três vezes mais rápido que a série. Processos separados têm **interpretadores separados**, e portanto **GILs separados**. Aqui há paralelismo de verdade, no sentido exato da lição 02: quatro coisas acontecendo no mesmo instante, em núcleos diferentes. (Este número também dança, e mais na primeira rodada: criar quatro processos tem custo de partida, e num terminal recém-aberto ele pesa — daqui já saiu um 0,85s de estreia que virou 0,31s na repetição. Rode mais de uma vez antes de acreditar em qualquer linha desta tabela.)

*(Detalhe do script que não é estilo: o `if __name__ == "__main__":` no fim é obrigatório. O `ProcessPoolExecutor` cria os filhos importando o módulo de novo; sem essa guarda, cada filho reexecutaria o script inteiro e criaria mais filhos. Sem paralelismo, sem parar.)*

## Então threads são inúteis?

Não — e entender por que não fecha uma dívida que a lição 01 deixou aberta.

**O GIL é liberado durante I/O.** Quando uma thread chama o sistema operacional para esperar rede, disco ou banco, ela solta a trava antes de ficar parada. Outra thread pega a faca e trabalha.

Isso ilumina duas coisas que você já viu funcionando:

- **O threadpool da lição 01** atendeu 10 requests lentas em 1,02s justamente porque as threads passaram aquele segundo *esperando*, com o GIL solto. Se as rotas estivessem calculando em vez de dormindo, o resultado teria sido 10 segundos.
- **O `aiosqlite` numa thread** (lição 05) não é fraude: enquanto o SQLite lê o arquivo, o GIL está liberado, e o event loop continua girando. É uma solução legítima — só não é a mesma coisa que um driver de rede assíncrono.

Então a regra fica: **threads em Python servem para esperar, não para calcular.**

## A hierarquia de decisão

Juntando esta lição com a 04 e a 05, você tem a árvore completa. Diante de uma operação lenta:

| A operação é… | A solução é… | Por quê |
|---|---|---|
| I/O, e existe lib async | `await` | a espera não custa thread nem conexão |
| I/O, e a lib só existe síncrona | `asyncio.to_thread(...)` | a thread espera com o GIL solto |
| CPU pesado | **outro processo** | é a única forma de escapar do GIL |
| CPU pesado **e** demorado | fila de tarefas | não segure a request; cap. 7 |

A promessa da lição 04 está cumprida: `asyncio.to_thread` é a válvula para o segundo caso, e a linha "CPU pesado" é o motivo de ela ser válvula e não solução geral.

Em três linhas, ela é assim:

```python
resultado = await asyncio.to_thread(hash_lento, "segredo")
```

O loop fica livre enquanto `hash_lento` roda numa thread separada — a rota não trava o servidor inteiro. Mas leia o aviso com atenção: **`to_thread` resolve bloqueio, não resolve CPU.** Se `hash_lento` for cálculo puro, ele vai disputar o GIL com todo o resto do processo, e o seu app inteiro fica mais lento enquanto isso. A request que você salvou custou desempenho de todas as outras.

Para o FairFare, isso vira uma decisão concreta lá no capítulo 7: cálculo de saldo pesado não vira `to_thread`, vira **job em segundo plano**, com o resultado guardado. Segurar uma request HTTP enquanto se calcula por dez segundos é errado por motivos que nem têm a ver com Python.

## Uma nota que vai envelhecer

Escrevendo isto em **agosto de 2026**, e sendo honesto sobre o que está em movimento: o GIL está em processo de deixar de ser inevitável.

Desde o Python 3.13 existem builds *free-threaded* — um interpretador compilado sem a trava global — e a partir do 3.14 esse modo passou a ser oficialmente suportado, não mais experimental. Ainda **não é o padrão**: você precisa de um build específico, parte do ecossistema de extensões em C ainda está se adaptando, e código de thread única costuma rodar um pouco mais devagar nesses builds.

Ou seja: a árvore de decisão desta lição continua valendo para o Python que você provavelmente está usando hoje. Mas se você estiver lendo isto em 2029 e alguém disser "GIL? isso é história antiga", pode ser que essa pessoa esteja certa. Confira antes de discutir — e, de preferência, meça, que é o hábito que este capítulo inteiro tentou instalar.

## O que você deve conseguir fazer agora

- Explicar o GIL em uma frase, sem usar analogia.
- Prever o resultado de `bancada/cpu.py` antes de rodar, e explicar por que as threads ficaram mais lentas que a série.
- Explicar por que o threadpool da lição 01 funcionou, mesmo com o GIL existindo.
- Escolher, para uma tarefa lenta qualquer, entre `await`, `asyncio.to_thread` e outro processo — e justificar.
- Dizer o que `asyncio.to_thread` resolve e o que ele não resolve.
