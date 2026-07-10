# Exercícios do capítulo 0

Ler sobre HTTP cria familiaridade. Falar HTTP cria entendimento. Aqui você fala.

## Preparação

Abra dois terminais. No primeiro, suba o mini-servidor e deixe-o rodando:

```console
$ cd chapters/00-http-e-a-web/exercises
$ python3 server.py
Mini-servidor no ar em http://localhost:8000 — Ctrl+C para parar.
```

O segundo terminal é o seu playground.

Duas coisas antes de começar:

- **Você não precisa entender o `server.py`.** Sério. Ele é só o interlocutor. No capítulo 1 você escreve o seu, e aí ele deixa de ser mágico. Espiar não é proibido — mas não é exercício.
- **As reservas moram na memória do servidor**: reiniciou, zerou. Se algo parecer sumir misteriosamente, cheque se você reiniciou o servidor. (E guarde esse detalhe; uma das perguntas abaixo brinca com ele.)

---

## Exercício 1 — Caça ao tesouro com curl

**Pronto quando:** todas as oito perguntas tiverem, anotados, o comando que você usou e a resposta que encontrou.

As lições 03–05 dão todas as ferramentas (`-v`, `-i`, `-X`, `-H`, `-d`, `-L`). Nenhuma pergunta exige adivinhar — o servidor sempre conta o que falta, se você souber onde ler.

- **T1.** Qual o status code e o `Content-Type` da resposta de `GET /quadras`?
- **T2.** Quantas quadras de tênis existem? Que pedaço da URL fez a peneira?
- **T3.** Existe uma rota `/segredo`. O que mora lá? Você vai bater na porta, ser recusado — e a chave está *na própria recusa*, se você ler todos os headers dela.
- **T4.** A rota `/antigo` se mudou. Qual status ela devolve, qual header aponta o novo endereço, e o que a flag `-L` faz com essa resposta?
- **T5.** Crie uma reserva na Quadra Central, em seu nome. Qual status confirma a criação e qual header diz onde a reserva mora agora? (Se levar um 415 no caminho: ótimo, era esperado — anote o que faltou e conserte.)
- **T6.** Tente `PUT /quadras`. Qual status volta e qual header da resposta lista o que você *podia* ter feito?
- **T7.** Repita a request do T5, idêntica, mais uma vez. O que apareceu em `GET /reservas`? Qual conceito da lição 06 isso demonstra — e por que ele ficará caro quando envolver dinheiro?
- **T8.** Reza a lenda que este servidor se recusa a fazer café. Encontre a rota e o status que provam isso. (Pista: RFC 2324. Sim, ela existe.)

---

## Exercício 2 — A request crua, na unha

O curl escreve as cartas por você. Uma vez na vida, escreva você.

**Pronto quando:** as duas requests abaixo estiverem em arquivos de texto e ambas receberem resposta do servidor via `nc`, com as respostas coladas nas suas anotações.

O `nc` (netcat) é um canal direto: conecta na porta e transmite os bytes do arquivo, sem opinar. O que estiver no arquivo é o que chega — se a carta estiver torta, a culpa é toda sua. Essa é a graça.

- **R1.** Escreva `request-quadras.txt` com uma request `GET /quadras` válida: request line, header `Host`, header `Connection: close`, e a linha em branco final. Dispare:

  ```bash
  nc localhost 8000 < request-quadras.txt
  ```

  Se o terminal ficar mudo, sua carta está incompleta (aposto na linha em branco). O `Connection: close` pede ao servidor para desligar depois de responder — sem ele, o `nc` fica pendurado esperando uma próxima request que nunca vem.

- **R2.** Agora a versão difícil: `request-reserva.txt` com um `POST /reservas` completo que **cria uma reserva**. Você vai precisar de: request line, `Host`, `Content-Type` (lição 08), `Content-Length`, `Connection: close`, a linha em branco, e o corpo JSON. A pegadinha honesta: `Content-Length` é o número de **bytes do corpo** — conte-os (sem contar a linha em branco). Se mentir no número, o servidor lê de menos ou fica esperando o resto.

Quando o 201 chegar, aprecie o momento: você falou HTTP fluente, sem intermediários. O curl nunca mais será mágico.

---

## Exercício 3 — Scripts quebrados

Três scripts Python em [`scripts_quebrados/`](scripts_quebrados/) deveriam conversar com o servidor — e alguém os quebrou. O docstring de cada um declara qual é a saída correta; seu trabalho é consertar até ela aparecer.

Regra de ouro: **leia o que o servidor responde.** Os três consertos estão escritos nas respostas de erro, para quem souber interpretá-las — e é exatamente essa a habilidade que o exercício treina.

Ordem sugerida: `01_lista_quadras.py` → `02_cria_reserva.py` → `03_acha_as_quadras.py` (dificuldade crescente).

---

Empacou de verdade? As respostas comentadas estão no [`SOLUTIONS.md`](../SOLUTIONS.md) — mas o valor do exercício mora no atrito antes de abri-lo.