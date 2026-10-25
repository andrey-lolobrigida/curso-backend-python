# Lição 11 — O dono da reserva

Desde a lição 05, o FairFare sabe quem pede. Toda rota de reserva confere o crachá antes de qualquer coisa. Mas saber quem pede é a primeira pergunta da lição 01. A segunda, "você pode fazer isso?", o app ainda não faz.

Esta lição faz a segunda pergunta numa rota só: o `DELETE /bookings/{id}`.

## O estrago primeiro

No banco de dev, criei dois usuários novos, com emails próprios desta demo: a Iara (id 282) e o Jonas (id 283). Cada um fez login e guardou o próprio token numa variável do shell, `$IARA` e `$JONAS`. A Iara cadastrou o recurso 52, o Chalé da Serra, e reservou o fim de semana:

```console
$ curl -s -X POST localhost:8000/bookings -H "Authorization: Bearer $IARA" \
    -H 'content-type: application/json' \
    -d '{"resource_id":52,"starts_at":"2026-12-18T14:00:00Z","ends_at":"2026-12-20T11:00:00Z"}'
{"id":2002,"user_id":282,"resource_id":52,"starts_at":"2026-12-18T14:00:00Z","ends_at":"2026-12-20T11:00:00Z","user_nome":"Iara","resource_nome":"Chalé da Serra"}
```

O Jonas também queria o chalé naquele fim de semana. Ele lista as reservas:

```console
$ curl -s localhost:8000/bookings -H "Authorization: Bearer $JONAS"
```

E, no meio da lista, acha esta:

```json
{"id":2002,"user_id":282,"resource_id":52,"starts_at":"2026-12-18T14:00:00Z","ends_at":"2026-12-20T11:00:00Z","user_nome":"Iara","resource_nome":"Chalé da Serra"}
```

Então ele manda isto, com o crachá **dele**:

```console
$ curl -si -X DELETE localhost:8000/bookings/2002 -H "Authorization: Bearer $JONAS"
HTTP/1.1 204 No Content
date: Sun, 25 Oct 2026 03:43:24 GMT
server: uvicorn
content-type: application/json

```

`204`. A reserva da Iara sumiu, e o chalé está livre para o Jonas. O log do uvicorn registrou tudo como se fosse normal:

```console
INFO:     127.0.0.1:51740 - "DELETE /bookings/2002 HTTP/1.1" 204 No Content
```

*(Isso rodou no uvicorn do commit da lição 10, antes do conserto desta lição. No código deste commit, a mesma request leva 404.)*

O pior detalhe: o app **sabia** que era o Jonas. O router de reservas tem `dependencies=[Depends(get_current_user)]` desde a lição 05. A dependência rodou, achou a sessão do Jonas, carregou o `User` dele e devolveu. E a rota jogou fora a resposta. Ela nem pedia o usuário:

```python
async def cancel_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
```

O porteiro conferiu o documento do Jonas. Ninguém conferiu de quem era a reserva. É o "autenticado, mas não autorizado" que a lição 05 deixou declarado.

## O buraco tem nome: BOLA

Pense num guarda-volumes. Você deixa a mochila, recebe a ficha 37. Na volta, o atendente confere que você tem **uma** ficha e pergunta o número. Você diz "a 38". Ele vai na prateleira, vê que a 38 existe, e entrega a mochila de outra pessoa.

O atendente conferiu duas coisas: que você é cliente, e que o volume existe. Faltou a terceira: que o volume é **seu**.

Agora o rigor. Isso se chama **BOLA**, *Broken Object Level Authorization*: autorização quebrada no nível do objeto. O servidor confere se você pode usar a **rota** ("logado pode cancelar reserva"), mas não confere se você pode mexer **neste objeto** ("esta reserva é sua?"). O nome mais antigo, do mundo das aplicações web, é **IDOR**, *Insecure Direct Object Reference*: referência direta e insegura a um objeto. É o mesmo buraco, com o nome da causa em vez do efeito.

E não é um buraco raro. O OWASP, uma fundação que mantém listas dos riscos de segurança mais comuns, publica um *API Security Top 10*. BOLA é o item 1 nas duas edições, a de 2019 e a de 2023.

A forma é sempre a mesma:

1. O id do objeto está na URL (`/bookings/2002`).
2. O cliente troca o número.
3. O servidor só confere se o objeto **existe**.

Repare que os ids do FairFare são sequenciais. A reserva da Iara é a 2002, a próxima vai ser a 2003. Adivinhar o vizinho é somar um. Ids aleatórios (um UUID, por exemplo) atrapalham o chute, e o próprio OWASP sugere usá-los. Mas eles não consertam nada: o id vaza de qualquer jeito, numa listagem, num link compartilhado, num log. O Jonas nem precisou chutar, a listagem entregou. O conserto é a checagem.

## O conserto

Duas mudanças. No router, a rota passa a pedir o usuário, como o `create_booking` já fazia:

```diff
 @router.delete("/{booking_id}", status_code=204)
-async def cancel_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
+async def cancel_booking(
+    booking_id: int,
+    user: User = Depends(get_current_user),
+    db: AsyncSession = Depends(get_db),
+):
     try:
-        await BookingService(db).cancel(booking_id)
+        await BookingService(db).cancel(booking_id, user)
```

O `dependencies=` do router continua lá. A dependência agora aparece duas vezes, e o FastAPI guarda o resultado da primeira: a consulta da sessão roda uma vez só, como na lição 05.

No service, uma condição a mais:

```diff
-    async def cancel(self, booking_id: int) -> None:
+    async def cancel(self, booking_id: int, user: User) -> None:
         async with self.db.begin():
             booking = await self.bookings.get(booking_id)
-            if booking is None:
+            # Reserva de outra pessoa responde igual à que não existe: o mesmo 404. É o contrato
+            # da API para recurso alheio, mostre a listagem o que mostrar (lição 11 do cap. 6).
+            if booking is None or booking.user_id != user.id:
                 raise BookingNotFoundError
+            # Só depois de saber que é sua: o "já começou" responde 409, uma resposta diferente
+            # da do inexistente. Antes da checagem de dono, ele quebraria o contrato do 404.
             if booking.starts_at <= datetime.now(UTC):
                 raise BookingInPastError
             await self.bookings.delete(booking)
```

Reserva que não existe e reserva de outra pessoa caem no **mesmo** `BookingNotFoundError`. O router traduz para o mesmo `404 "reserva não existe"` que já existia.

Os testes moram num arquivo novo, `tests/test_permissoes.py`, que cresce na lição 12. O primeiro é o estrago, virado teste: o Bruno apaga a reserva da Ana, leva 404, e a Ana ainda vê a reserva no `GET /bookings`. Antes do conserto, ele falhou assim:

```
>       assert resp.status_code == 404
E       assert 204 == 404
```

## 403 ou 404?

A lição 01 apresentou os dois candidatos e deixou o critério para cá.

O 403 diz: "sei quem você é, e você não pode". Parece o código certo. Mas leia o que ele conta: **a reserva 2002 existe**, e é de outra pessoa. Quem troca o número para 2003, 2004, 2005 ganha uma confirmação a cada 403. Um 403 para cada reserva alheia e um 404 para cada buraco: dá para mapear o sistema sem nunca acertar uma request.

O 404 não diz nada. A reserva alheia e a reserva que nunca existiu respondem igual.

É a família da lição 06. Lá, o login respondia mais rápido para email inexistente, e o tempo contava quem tinha conta. Aqui seria o código. O princípio é o mesmo: **não entregue informação de graça**. E, como lá, a defesa só vale se as duas respostas forem iguais em tudo. Daí o segundo teste:

```python
async def test_404_alheio_e_igual_ao_inexistente(pessoa):
    # O contrato: a reserva alheia e a inexistente respondem igual, em tudo. Qualquer
    # diferença viraria um jeito de saber que o id existe.
    ana = await pessoa("Ana")
    bruno = await pessoa("Bruno")
    recurso = await cria_recurso(ana.client)
    reserva = (
        await cria_reserva(
            ana.client, recurso["id"], "2030-01-01T10:00:00Z", "2030-01-01T12:00:00Z"
        )
    ).json()

    alheia = await bruno.client.delete(f"/bookings/{reserva['id']}")
    inexistente = await bruno.client.delete("/bookings/999")

    assert alheia.status_code == inexistente.status_code == 404
    assert alheia.json() == inexistente.json()
```

**O critério, então.** Use 403 quando o objeto já é visível para a pessoa, e só a ação é que não pode. Use 404 quando o simples "existe" já é informação que ela não deveria ter. Os cenários da lição 01:

- A Carla vê o relatório de salários na lista, porque todo mundo vê os títulos, e não pode editar. **403.** Ela já sabe que o relatório existe. Esconder o que ela vê não protege nada, e o 403 diz a verdade: "isto existe e não é para você editar".
- O Bruno pede um grupo do qual não é membro. **404.** Saber que o grupo existe já é informação. O código disso é a lição 12.

E aqui o FairFare tem uma conta a fazer com ele mesmo. O Jonas **achou** a reserva 2002 no `GET /bookings`, com o nome da Iara do lado. Hoje, a listagem mostra a qualquer pessoa logada quem reservou o quê. Aplicado hoje, o critério acima aponta **403**. A reserva é visível para o Jonas, e só o cancelamento é que não pode.

O FairFare se afasta do critério de propósito, e o preço tem de ficar dito com todas as letras. O Jonas vê a reserva 2002 na listagem e, no `DELETE`, recebe "reserva não existe". Para ele, a frase é falsa. Quem consome a API pode achar que é bug.

Por que pagar? Porque a API fica com uma regra só: **recurso alheio é 404**. A lição 12 aplica a mesma regra aos grupos, e lá o 404 esconde de verdade. Quem usa a API, e quem mantém o código dela, guarda uma regra, não uma tabela de exceções. E o contrato do `DELETE` não depende do que a listagem mostra esta semana. No dia em que a listagem esconder quem reservou, o `DELETE` já não vaza, e ninguém precisa lembrar de mexer nele. Além disso, uma resposta só para "não é sua" é um ramo a menos no código.

## Onde mora a checagem, e por que a ordem importa

A checagem mora no **service**, ao lado da regra do "já começou". As duas são regras de negócio sobre esta reserva, e o service é quem já tem a reserva na mão, dentro da transação. A dependência do router responde uma pergunta só: quem é você.

E, dentro do service, a ordem das checagens muda o status. Veja o que o código da lição 10 respondia quando o Jonas tentava cancelar a reserva 2003, que a Iara fez para julho, já passada:

```console
$ curl -si -X DELETE localhost:8000/bookings/2003 -H "Authorization: Bearer $JONAS"
HTTP/1.1 409 Conflict
date: Sun, 25 Oct 2026 03:43:34 GMT
server: uvicorn
content-length: 54
content-type: application/json

{"detail":"só reservas futuras podem ser canceladas"}
```

Um 409 conta que a reserva 2003 existe e que já começou. Hoje, a listagem já mostra isso ao Jonas. A ordem importa pelo mesmo motivo de antes: o contrato do 404 não depende da listagem. Um 409 para a reserva alheia é uma resposta diferente da do inexistente, e quebra o contrato que o segundo teste fixou.

Se a checagem de dono entrasse **depois** do "já começou", esse 409 continuaria saindo. Testei: invertendo a ordem no service (só na minha máquina, não está no commit), o terceiro teste caiu, e só ele:

```python
async def test_reserva_alheia_passada_tambem_e_404(pessoa):
    # Não 409: o dono vem antes do "já começou". Um 409 seria uma resposta diferente da do
    # inexistente, e quebraria o contrato do 404.
    ana = await pessoa("Ana")
    bruno = await pessoa("Bruno")
    recurso = await cria_recurso(ana.client)
    reserva = (
        await cria_reserva(
            ana.client, recurso["id"], "2020-01-01T10:00:00Z", "2020-01-01T12:00:00Z"
        )
    ).json()

    resp = await bruno.client.delete(f"/bookings/{reserva['id']}")

    assert resp.status_code == 404
    assert resp.json() == {"detail": "reserva não existe"}
```

```
>       assert resp.status_code == 404
E       assert 409 == 404
```

A regra geral: **toda checagem que pode revelar algo sobre o objeto vem depois da checagem de dono.** Primeiro "é seu?", depois "pode agora?".

Com o conserto, o Jonas tenta a reserva futura (2004, a Iara reservou o fim de semana de novo), a passada (2003) e uma que nunca existiu:

```console
$ curl -si -X DELETE localhost:8000/bookings/2004 -H "Authorization: Bearer $JONAS"
HTTP/1.1 404 Not Found
date: Sun, 25 Oct 2026 03:44:25 GMT
server: uvicorn
content-length: 32
content-type: application/json

{"detail":"reserva não existe"}
```

A 2003 e a 999999 responderam idêntico: o mesmo `404`, o mesmo corpo, o mesmo `content-length: 32`. E a Iara, dona da 2004, cancelou a dela com `204`.

A suíte passou de 115 para 118 testes.

## O que fica declarado

- **O `GET /bookings` mostra a qualquer pessoa logada quem reservou o quê.** É escolha, não defeito: a disponibilidade é pública dentro do app. O custo está na seção do 403 ou 404: o Jonas vê a reserva na listagem, e o `DELETE` responde "reserva não existe", uma frase falsa para quem vê a listagem. Quem consome a API pode achar que é bug. É o preço da regra única (recurso alheio é 404).
- **Os ids continuam sequenciais.** Não são o conserto, e trocá-los não fecharia nada que a checagem não feche.
- **As rotas de grupo ainda não conferem nada.** Qualquer pessoa logada vê o grupo e o saldo de qualquer grupo, adiciona membros e lança despesa ou quitação em nome de outro. É a lição 12.
- **A demo ficou no banco de dev:** a Iara (282), o Jonas (283), o recurso 52 e a reserva passada 2003. A 2002 foi apagada pelo Jonas no "antes", e a 2004, pela Iara.

## O que você deve conseguir fazer agora

- Ler uma rota que recebe um id na URL e dizer se ela tem um BOLA: o que ela confere sobre o objeto, além de ele existir?
- Explicar por que ids aleatórios atrapalham o ataque e não o consertam.
- Decidir entre 403 e 404 em dois cenários:
  1. Num app de projetos, todos os membros veem as tarefas do quadro, com o nome de quem criou. Só quem criou a tarefa pode apagá-la. A Carla tenta apagar a tarefa do Davi. Pelo critério, qual é o código enquanto o quadro mostrar o autor? E se ele deixar de mostrar? Se você tivesse de fixar um só no contrato da API, qual escolheria, e por quê?
  2. Num app de notas, a Carla pede `GET /notas/815`, uma nota privada do Davi.
- Explicar por que, no `cancel`, a checagem de dono vem antes da de "já começou", e qual status a reserva alheia passada receberia com a ordem invertida.
