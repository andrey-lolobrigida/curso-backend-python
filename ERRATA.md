# Errata

Este curso usa branches como checkpoints de capítulo (`chapter-00`,
`chapter-01`, ...). Quando um bug é encontrado em um capítulo antigo, nós
**corrigimos para frente** (na `main` e na branch de trabalho atual) e
**documentamos para trás** (aqui). Reescrever branches antigas quebraria o
histórico que você pode ter baixado — então elas ficam como estão, e este
arquivo é o mapa dos problemas conhecidos.

Formato de cada entrada:

- **Capítulo afetado:** qual branch/tag contém o problema
- **O que está errado:** descrição honesta do bug ou erro
- **Correção:** o que mudar (com link para o commit corretivo na main)

---

## 1. O gancho do fim do capítulo 1 é falso

- **Capítulo afetado:** 1 (`chapter-01`, tag `v-chapter-01`) — `chapters/01-arquitetura-em-camadas/README.md`, seção "Ao terminar".
- **O que está errado:** a frase *"nosso servidor atende uma pessoa de cada vez"*. Não atende. Rotas escritas com `def` (que é o caso de **todas** as rotas do FairFare no capítulo 1) não rodam no event loop: o Starlette as despacha para um threadpool. Medido: 10 requests simultâneas de 1 segundo terminam em **1,02s** numa rota `def` — e em **10,03s** numa rota `async def` que bloqueia. A frase descrevia com precisão o caso oposto ao nosso.
- **Correção:** o texto do README foi trocado na `main` pela versão verdadeira — o teto real são **40 threads** (o limite do threadpool do `anyio`), e o custo é **uma thread por request**. Medido: 40 requests simultâneas levam 1,05s; 41 levam 2,03s, porque a última espera uma vaga abrir.
- **Onde ver a medição inteira:** capítulo 2, lição 01 (`chapters/02-python-assincrono/theory/01-a-mentira-do-capitulo-1.md`), que abre reproduzindo o erro com a bancada em `chapters/02-python-assincrono/bancada/`.

## 2. Três limitações do capítulo 1 que não foram declaradas

- **Capítulo afetado:** 1 (`chapter-01`, tag `v-chapter-01`).
- **O que está errado:** o código entregue no capítulo 1 tem três problemas conhecidos, e o material do capítulo não avisava sobre nenhum deles. Isso era consequência de uma política de ensino que o curso **abandonou em 2026-08-15** (a de plantar defeitos para que fossem sentidos depois). Um curso que entrega código precisa poder ser usado como referência; para isso, o que se sabe que está errado tem que estar escrito.

  | # | Onde | O quê | Resolvido no |
  |---|---|---|---|
  | 1 | `app/services/booking.py::BookingService.create` | Verifica conflito de horário e **depois** insere, sem transação nem lock. Duas requests simultâneas para o mesmo horário passam as duas pela verificação e gravam as duas (*check-then-act*). | capítulo 4 |
  | 2 | `app/services/booking.py::_to_out` | Cada reserva listada busca usuário e recurso em consultas separadas: `GET /bookings` faz **2N+1** idas ao banco (problema N+1). | capítulo 4 |
  | 3 | todas as rotas | Não existe autenticação. `POST /bookings` aceita qualquer `user_id`; qualquer pessoa reserva ou cancela no nome de qualquer outra. | capítulo 5 |

- **Correção:** **o código não muda.** Consertar qualquer um dos três exigiria conceitos que o curso ainda não ensinou (transações, eager loading, autenticação) — e ensiná-los fora de hora é pior que declará-los. O que mudou é que agora eles estão escritos: aqui, numa seção nova do README do capítulo 1, e em detalhe na lição 11 do capítulo 2 (`chapters/02-python-assincrono/theory/11-o-que-ainda-nao-resolve.md`), com o mecanismo de cada um e o que o capítulo 2 mudou neles.