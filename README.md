# Curso Completo de Backend em Python

*(título provisório — mas o app em torno do qual o curso é construído já tem nome: **FairFare**)*

Um curso mão na massa para quem já sabe escrever Python e talvez já tenha construído um pequeno app web — e agora quer entender como **backends de verdade** funcionam. Não é mais um tutorial de CRUD: este é o curso sobre tudo o que acontece *depois* que o tutorial acaba.

Você vai construir uma aplicação do zero — o FairFare, um app de reservas em grupo com divisão de despesas — e fazê-la crescer capítulo a capítulo até algo com cara de produção: arquitetura em camadas, async, banco de dados de verdade, relações e dinheiro, autenticação, cache, jobs em segundo plano, observabilidade, testes e deploy.

## Para quem é este curso

Você está no lugar certo se:

- Você está confortável com o básico de Python: funções, classes, dicionários, ambientes virtuais. Não precisa ser expert — precisa não ter medo de uma definição de classe.
- Você já escreveu *algum* código que faz *alguma coisa* — scripts, um pequeno app em Django/Flask, um bot, trabalhos de curso. Você já sentiu o momento "ok, funciona... e agora?".
- Você quer entender o **porquê** por trás dos padrões de backend, não apenas copiar estruturas de pastas.
- Você já construiu algo com um framework e funciona, mas fica com aquela sensação incômoda de que não conseguiria defender a própria arquitetura em um code review.

Este curso vive no que às vezes chamam de **deserto intermediário** — a lacuna entre os mil tutoriais para iniciantes e as palestras de conferência que assumem que você já sabe tudo. Se você terminou um curso de "Python + primeiro app web" e pensou *"...e depois?"*, este é o *e depois*.

## Para quem este curso NÃO é

Poupe-se de alguma frustração — pule este curso (por enquanto!) se:

- **Você é totalmente novo em Python.** Não vamos cobrir sintaxe, básicos de POO nem tratamento de exceções. Faça um curso introdutório primeiro — a gente espera, sério. Este repositório não vai a lugar nenhum.
- **Você nunca encostou na linha de comando ou no git.** Não precisa ser um mago do git (navegar por este curso vai te *deixar* melhor em git — isso é proposital), mas `git checkout` não pode ser um encantamento assustador.
- **Você quer uma referência rápida ou um cheatsheet.** Este é um curso de construir junto, com exercícios em que as coisas estão deliberadamente quebradas e você conserta. Ele recompensa tempo, não leitura dinâmica.
- **Você quer frontend.** Aqui construímos a API — o motor, não o painel. JSON entra, JSON sai.

Nota honesta: se você está *um pouquinho* abaixo do piso, ainda dá para chegar lá — só espere pausar e pesquisar algumas coisas. Se está bem acima, passe rápido pelos primeiros capítulos e roube os exercícios.

## Como o curso funciona

- **Um app, crescendo.** Nada de exemplos de brinquedo desconectados. Todo conceito aterrissa na mesma base de código, adicionado apenas quando um capítulo precisa dele.
- **Branches são capítulos.** Cada branch `chapter-XX` é a base de código ao final daquele capítulo. Os diffs entre capítulos são material do curso — leia-os.
- **Teoria em pequenas doses.** Cada capítulo tem uma pasta `theory/` com lições curtas, uma ideia por arquivo.
- **Quebre para aprender.** Os exercícios te entregam código quebrado ou incompleto. O `SOLUTIONS.md` explica o *raciocínio*, não só a resposta.

## Comece aqui

O curso começa no [capítulo 0 — HTTP e a web](chapters/00-http-e-a-web/README.md).
Sem código do app ainda: primeiro a gramática, depois a conversa.

Escritos até agora:

| # | Capítulo | O que você sai sabendo |
|---|----------|------------------------|
| 0 | [HTTP e a web](chapters/00-http-e-a-web/README.md) | A conversa que todo backend tem: métodos, status, corpo, cabeçalhos |
| 1 | [Arquitetura em camadas](chapters/01-arquitetura-em-camadas/README.md) | Routers, services, repositories, models, schemas, migrações e testes |
| 2 | [Python assíncrono](chapters/02-python-assincrono/README.md) | Event loop, bloqueio, o GIL, pool de conexões — e como medir tudo isso |
| 3 | [Entre o cliente e o router](chapters/03-entre-o-cliente-e-o-router/README.md) | O que o uvicorn faz, middleware, CORS, rate limiting, proxy reverso, TLS, workers |

## A stack

Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, pytest — com Redis, uma fila de tarefas e Docker entrando quando o curso os merecer. Por que FastAPI e não Django ou Flask? Essa comparação é, por si só, [uma lição](chapters/01-arquitetura-em-camadas/theory/02-por-que-fastapi.md).

## Arco do curso

0. HTTP e a web — a gramática na qual todo o resto é escrito
1. Arquitetura em camadas — routers, services, repositories, models, schemas, migrações
2. Python assíncrono — event loops, bloqueio, o GIL, pools de conexão
3. Entre o cliente e o router — servidores ASGI, proxies reversos, CORS, TLS, rate limiting
4. O banco de dados, de verdade — PostgreSQL, pool de conexões, índices, transações, isolamento, locking
5. Relações e dinheiro — relações, N+1, matemática de dinheiro, quando descer para SQL puro
6. Autenticação e segurança — sessões vs JWTs, OAuth2, permissões
7. Cache e estado — Redis, invalidação, e quando o cache mente
8. Trabalho em segundo plano e filas — workers, retentativas, idempotência
9. Falhas e observabilidade — logging, métricas, timeouts, backoff
10. Estratégia de testes — o que testar em cada camada
11. Colocando no ar — Docker, CI/CD, segredos, escalabilidade

(Os capítulos são planejados em detalhe conforme são escritos — este arco é o mapa, não o terreno.)

## Licenças

O código é [MIT](LICENSE) — pegue, use, construa em cima. O conteúdo escrito do curso é [CC BY 4.0](LICENSE-CONTENT) — compartilhe e adapte com atribuição.

---

*Construído em público, por alguém consolidando o próprio entendimento ao ensiná-lo. A melhor forma de encontrar as lacunas no que você sabe é tentar explicar — este repositório é essa tentativa. Issues e correções são bem-vindas.*
