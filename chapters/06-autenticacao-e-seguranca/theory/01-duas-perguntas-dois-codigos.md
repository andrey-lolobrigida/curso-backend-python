# Lição 01 — Duas perguntas, dois códigos

Cinco capítulos depois, o FairFare reserva quadra sem reserva dupla, divide conta sem perder centavo e quita dívida com cadeado. E acredita em tudo o que qualquer um diz.

Esta lição não muda uma linha do app. Ela mostra o buraco, dá nome às duas perguntas que ele deixa sem resposta e apresenta os códigos HTTP de cada uma. O resto do capítulo tapa o buraco.

## O estrago primeiro

No banco de dev, criei a Ana (id 265) e o Bruno (id 266), com emails próprios desta demo, e o grupo 50, com os dois como membros. Ninguém gastou nada ainda:

```console
$ curl -s localhost:8000/groups/50/balances
[{"user_id":265,"nome":"Ana","saldo":"0.00"},{"user_id":266,"nome":"Bruno","saldo":"0.00"}]
```

Agora eu, que não sou a Ana nem o Bruno, mando isto:

```console
$ curl -s -i -X POST localhost:8000/groups/50/expenses -H 'content-type: application/json' \
  -d '{"paid_by": 265, "descricao": "Jantar que a Ana não pagou", "valor": "500.00"}'
HTTP/1.1 201 Created
date: Sun, 25 Oct 2026 01:18:03 GMT
server: uvicorn
content-length: 218
content-type: application/json

{"id":86041,"group_id":50,"paid_by":265,"descricao":"Jantar que a Ana não pagou","valor":"500.00","criada_em":"2026-10-25T01:18:03.823736Z","partes":[{"user_id":265,"valor":"250.00"},{"user_id":266,"valor":"250.00"}]}
```

`201 Created`. E o saldo:

```console
$ curl -s localhost:8000/groups/50/balances
[{"user_id":265,"nome":"Ana","saldo":"250.00"},{"user_id":266,"nome":"Bruno","saldo":"-250.00"}]
```

A Ana tem R$ 250 a receber, sem ter feito nada. O Bruno deve R$ 250 de um jantar que não existiu. A divisão está certinha, o centavo está no lugar, o `Decimal` fez o trabalho dele. A conta está perfeita e é mentira.

Quem mandou o `POST`? Pergunte ao servidor. O log do uvicorn é tudo o que ele sabe:

```console
INFO:     127.0.0.1:49836 - "POST /groups/50/expenses HTTP/1.1" 201 Created
```

Um IP e uma porta. Nenhum nome. O `paid_by: 265` do corpo não é uma identidade. É uma **afirmação** do cliente, e o app a aceitou sem perguntar nada.

Isso não é novidade. A lição 09 do capítulo 1 já dizia: "Mande `{"user_id": 1}` sendo você o usuário 7 e o FairFare obedece". E deu a isso o nome de terceiro tipo de "não pode", o que o app ainda não sabia dizer. A lição de fechamento de cada capítulo, do 2 ao 5, carregou o mesmo item: sem autenticação, capítulo 6. Chegou a hora.

*(Se você repetir a demo, seus ids vão ser outros. Os meus ficaram no banco de dev.)*

## Duas perguntas

O `curl` acima deixou duas perguntas sem resposta, e vale separá-las com cuidado.

Pense numa festa no apartamento 302. Na portaria do prédio, o porteiro confere o seu documento: você é mesmo a Carla? Ele não sabe de festa nenhuma. Lá em cima, o dono da festa confere a lista de convidados: a Carla está na lista do 302? Ele não confere documento, confia no porteiro. São dois trabalhos, feitos por duas pessoas, em dois lugares.

Agora o rigor.

- **Autenticação** responde **"quem é você?"**. O cliente apresenta uma credencial (uma senha, ou um token, o crachá que o login entrega na lição 04), e o servidor a confere. Se ela vale, a request deixa de ser anônima e passa a ter um usuário atrás.
- **Autorização** responde **"você pode fazer isso?"**. Com o usuário em mãos, o servidor decide se *esta* ação sobre *este* recurso é permitida para *ele*.

São passos separados, e a ordem não é opcional. A autorização precisa de alguém sobre quem decidir. Sem autenticação, a pergunta "a Carla pode?" não tem Carla.

E eles falham de jeitos diferentes. A autenticação falha quando a credencial falta, está errada ou venceu: o servidor não sabe quem está ali. A autorização falha com o servidor sabendo muito bem quem está ali. Ele só não deixa.

O `curl` da despesa falsa tem os dois buracos. Ninguém perguntou quem pedia. E, mesmo que alguém perguntasse, não existe regra nenhuma dizendo quem pode lançar uma despesa em nome de quem.

## Dois códigos

O HTTP tem um código para cada falha.

**401 Unauthorized:** "não sei quem você é". Faltou a credencial, ou ela não vale. O nome engana, e a lição 05 do capítulo 0 já avisou: apesar do "Unauthorized", o 401 é sobre identificação. É um erro histórico de nomenclatura do protocolo, e a gente convive com ele.

O 401 tem uma regra que pouca gente lembra. A RFC 9110, que define o HTTP, manda toda resposta 401 levar o header **`WWW-Authenticate`**, que diz ao cliente **como** se apresentar. Não basta dizer "não te conheço". O servidor precisa dizer que documento aceita. O FairFare vai responder assim:

```http
WWW-Authenticate: Bearer
```

Tradução: "mande um token no esquema Bearer". *Bearer* é "portador", em inglês: quem porta o token é aceito, como quem porta o ingresso entra no cinema. Você vê esse header saindo do FairFare na lição 04.

Lembra do `/segredo`, o mini-servidor do capítulo 0? Rodei de novo:

```console
$ curl -s -i localhost:8000/segredo
HTTP/1.1 401 Unauthorized
Server: MiniServidorCap00/0.1 Python/3.12.12
Date: Sun, 25 Oct 2026 01:20:13 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 64
X-Dica: a senha e clube-do-backend

{
  "erro": "faltou o header X-Senha (ou a senha esta errada)"
}
```

Sem `WWW-Authenticate`. No lugar dele, um `X-Dica` caseiro, que diz como se apresentar e, de brinde, entrega a senha. Era brinquedo de propósito. O FairFare vai seguir o protocolo.

**403 Forbidden:** "sei quem você é, e você não pode". A credencial valeu. A autorização é que disse não.

A diferença prática está no que o cliente faz depois. Com um 401, faz sentido logar de novo e repetir. Com um 403, não adianta: logar de novo traz a mesma pessoa, e a mesma pessoa continua sem poder.

**E um terceiro, às vezes.** Imagine o Bruno, logado, pedindo o grupo 51, de que ele não faz parte. Se o app responde 403, ele acabou de contar ao Bruno que o grupo 51 existe. Às vezes o simples "existe" já é informação que a pessoa não deveria ter. Aí o **404** é a resposta mais honesta: para você, isto não existe. O critério de quando usar cada um é a lição 11.

## O que não é autenticação

Três camadas do capítulo 3 têm cara de segurança e não respondem a "quem é você?".

- **TLS** autentica o **servidor**, não você. O certificado prova ao seu cliente que ele fala com o FairFare de verdade. Que a Carla é a Carla é outro assunto (lição 09 do capítulo 3). O `curl` da despesa falsa, por HTTPS, chegaria cifrado e seria aceito do mesmo jeito.
- **Rate limit** conta requests, não pessoas. Ele sabe que o `127.0.0.1` mandou uma request, e só (lição 12 do capítulo 3). O ataque acima coube com folga no balde.
- **CORS** protege o usuário do browser, não a API. Um `curl` nunca viu um erro de CORS na vida (lição 04 do capítulo 3).

## O mapa do capítulo

O capítulo responde às duas perguntas, nesta ordem, em três partes. **Quem é você** (lições 02 a 07): como guardar uma senha sem guardá-la, o cadastro com senha, o login que emite um crachá, a peça do app que confere esse crachá em toda request, o login que fala demais e o logout que revoga. **Sessão ou JWT** (lições 08 a 10): o JWT montado à mão na bancada, a comparação com a sessão que o FairFare escolheu e onde o crachá mora no browser. **O que você pode** (lições 11 e 12): o dono da reserva e as regras de quem é membro do grupo. A lição 13 fecha a conta, como sempre.

## O que fica declarado

- **O `curl` desta lição funciona no código deste commit.** É o FairFare como os capítulos 1 a 5 o entregaram.
- **Ele não morre de uma vez.** A partir da lição 05, toda rota exige login, menos o cadastro e o próprio login, e o mesmo `curl` sem crachá leva 401. Mas o `paid_by` continua vindo do corpo até a lição 12. Entre uma e outra, o app fica **autenticado, mas não autorizado**: ele sabe quem pede, e ainda deixa qualquer pessoa logada lançar despesa em nome de outra. É a distinção desta lição, vista no código. Morre na lição 12.
- **A demo ficou no banco de dev:** a Ana (265), o Bruno (266), o grupo 50 e a despesa 86041.

## O que você deve conseguir fazer agora

- Dizer, para cada cenário, se a resposta é 401, 403 ou 404, e por quê:
  1. Um cliente chama uma rota que exige login sem mandar header `Authorization` nenhum.
  2. Num sistema de empresa, a Carla está logada e vê o relatório de salários na lista, porque todo mundo vê os títulos. Ela tenta editá-lo, e só o RH edita.
  3. No FairFare, o Bruno está logado e pede um grupo do qual não é membro.
- Explicar a diferença entre autenticação e autorização, e por que uma vem antes da outra.
- Dizer o que o `WWW-Authenticate` faz numa resposta 401.
- Explicar por que servir o FairFare com TLS não impediria o `curl` da despesa falsa.
