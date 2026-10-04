# Lição 11 — O que este código ainda não resolve

Um curso que entrega código tem uma dívida com quem vai ler esse código.

Você provavelmente vai usar o FairFare como referência — copiar um padrão daqui, imitar a organização de pastas ali. Isso só funciona se você puder confiar no que está escrito. E confiança, aqui, significa uma coisa bem específica: **se eu sei que tem um defeito, eu te conto.**

Então esta lição é o inventário. Três limitações conhecidas, cada uma com endereço exato, o motivo de continuar ali, como ela se manifesta, e o capítulo que resolve.

## 1. Duas pessoas podem reservar o mesmo horário

**Onde:** `app/services/booking.py`, em `BookingService.create`.

```python
    overlapping = await self.bookings.find_overlapping(...)
    if overlapping:
        raise BookingConflictError
    booking = await self.bookings.create(...)
```

Olhe a sequência: primeiro **verifica** se há conflito, depois **insere**. Entre uma coisa e outra existe uma janela, e nessa janela o mundo pode ter mudado.

Duas requests pedindo a mesma quadra no mesmo horário, ao mesmo tempo: as duas rodam o `find_overlapping`, as duas encontram a agenda livre, as duas passam pela verificação, as duas gravam. O banco fica com duas reservas sobrepostas e o app achando que fez seu trabalho. O nome disso é **check-then-act**, e é uma das corridas mais clássicas que existem.

**Por que não consertamos agora:** a cura é transação com o nível de isolamento certo, ou um lock explícito no recurso. Isso exige entender o que uma transação garante — e explicar `SELECT ... FOR UPDATE` antes de explicar transação seria ensinar o remédio antes da doença.

**O que o capítulo 2 mudou nisso:** piorou. Sério. No capítulo 1 o app já era concorrente — as rotas `def` iam para o threadpool (lição 01), então a corrida já existia. Agora o caminho ficou mais rápido e mais estreito: mais requests chegam ao mesmo trecho de código no mesmo intervalo de tempo. Concorrência maior não cria a corrida, mas aumenta muito a chance de ela acontecer.

**Resolvido no:** capítulo 4.

## 2. Listar reservas faz uma enxurrada de consultas

**Onde:** `app/services/booking.py`, em `_to_out` e `list_all`.

```python
    async def list_all(self) -> list[BookingOut]:
        return [await self._to_out(b) for b in await self.bookings.list_all()]
```

Cada `_to_out` faz **duas** consultas — uma para o usuário, uma para o recurso. Com N reservas na lista, o total é **2N + 1** idas ao banco: uma para listar, duas por reserva. Cinquenta reservas viram cento e uma consultas para montar uma tela.

Esse é o **problema N+1**, o clássico dos ORMs: você escreve uma linha de código e o ORM emite uma consulta por item, sem avisar.

**Onde ele nasceu:** na lição 09 do capítulo 1, e o capítulo 1 não te contou. Isso foi erro meu — e é justamente o tipo de silêncio que a política deste curso passou a proibir. Está corrigido na errata do repositório e declarado aqui.

**O que o capítulo 2 mudou nisso:** também piorou, e ficou mais visível. O `await` dentro da list comprehension é a delação: agora são 2N+1 corrotinas em fila indiana, cada uma com o custo extra de uma passagem pelo event loop. Async não conserta N+1 — nunca prometeu isso. Ele torna cada espera mais barata; não torna o número de esperas menor.

**Por que não consertamos agora:** a cura é carregar os dados relacionados junto, com `join` ou `selectinload`, e isso pressupõe `relationship()` entre os models — que o FairFare ainda não tem, e que traz junto o `MissingGreenlet` da lição 05.

**Resolvido no:** capítulo 5.

## 3. Não existe autenticação nenhuma

**Onde:** em todo lugar. `POST /bookings` aceita qualquer `user_id` que chegue no corpo da request.

```bash
curl -X POST localhost:8000/bookings \
  -H 'content-type: application/json' \
  -d '{"user_id": 7, "resource_id": 1, "starts_at": "...", "ends_at": "..."}'
```

Nada no app pergunta *quem está fazendo isso*. Qualquer pessoa reserva no nome de qualquer outra, cancela a reserva de qualquer outra, e o app obedece sem piscar. O `user_id` é uma afirmação do cliente, e o servidor acredita.

**Por que não consertamos agora:** autenticação é um capítulo inteiro — sessões contra tokens, onde guardar segredo, hashing de senha, permissões por grupo. Enfiar um "meio-jeito" agora produziria segurança de mentira, que é pior que nenhuma, porque parece resolvida.

**Resolvido no:** capítulo 6.

## A regra que essas três seções ilustram

**Este curso não esconde bugs no código que entrega.**

Toda limitação conhecida está escrita no material do capítulo onde ela existe, junto com o capítulo que a resolve. Se você encontrar no FairFare algum defeito que não esteja declarado em lugar nenhum, isso não é um exercício disfarçado — é um erro meu, e vale um issue.

O contrário também vale, e é importante: **onde houver código quebrado de propósito, o enunciado do exercício diz que ele está quebrado.** Depurar ensina mais que ler, e os exercícios deste capítulo continuam cheios de código com defeito — anunciado, delimitado, com o "pronto" descrito. Aprender consertando é ótimo. Ser enganado pelo material do curso é outra coisa.

Há uma diferença entre um professor que esconde a resposta e um professor que esconde o problema. A primeira é pedagogia. A segunda é só uma armadilha.

## O que você deve conseguir fazer agora

- Apontar, no código, a janela da corrida de reserva dupla — e explicar por que o capítulo 2 aumentou o risco dela.
- Calcular quantas consultas `GET /bookings` faz com 50 reservas no banco.
- Explicar por que async não conserta N+1.
- Dizer, para cada uma das três limitações, em que capítulo ela morre.
- Confiar no resto do código do FairFare — porque o que a gente sabe que está errado, você acabou de ler.
