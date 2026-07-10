# Lição 01 — Cliente, servidor e o ciclo request-response

Você digita `google.com` e aperta Enter. Meio segundo depois, uma página aparece. Nesse meio segundo aconteceu uma conversa — e este curso inteiro é sobre um dos lados dela.

Vamos começar dando nome aos participantes.

## A cozinha e o salão

Pense num restaurante. Você senta, olha o cardápio e faz um pedido. O garçom leva o pedido para a cozinha. A cozinha prepara. O garçom volta com o prato. Você não entra na cozinha, não sabe quantas panelas foram usadas, não viu o cozinheiro suar. Você fez um pedido e recebeu uma resposta.

Essa é a analogia. Agora a versão precisa:

- O **cliente** é quem pede. Ele monta uma **request** (um pedido estruturado) e a envia.
- O **servidor** é quem responde. Ele recebe a request, faz o que precisar fazer — consultar um banco, calcular algo, checar permissões — e devolve uma **response**.
- A conversa **sempre começa pelo cliente**. O servidor nunca liga para você do nada; ele fica sentado, esperando o telefone tocar.

Esse último ponto parece detalhe, mas define tudo. Um servidor é, essencialmente, um programa em um loop infinito de "espera pedido, responde pedido, espera pedido". Quando alguém diz "o servidor caiu", quer dizer que esse programa parou de atender.

## O ciclo, desenhado

```
   CLIENTE                                SERVIDOR
      |                                       |
      |  ---------- request ---------------> |
      |   "me dá a lista de quadras"         |  (processa: consulta
      |                                      |   dados, decide, monta
      |  <--------- response ---------------  |   a resposta)
      |   "aqui: 3 quadras, em JSON"         |
      |                                       |
```

Uma request, uma response. Sempre nessa ordem, sempre em pares. Não existe response sem request — e quando uma request fica sem response, o cliente fica pendurado esperando (isso tem nome, timeout, e vai nos render um capítulo inteiro lá na frente).

## "Cliente" não é sinônimo de navegador

O navegador é o cliente mais famoso, mas está longe de ser o único:

- O **app de celular** do seu banco é um cliente — ele conversa com os servidores do banco.
- Um **script Python** que baixa dados de uma API é um cliente.
- E — aqui fica interessante — **um servidor pode ser cliente de outro servidor**. Quando o backend de uma loja consulta o servidor do cartão de crédito para cobrar você, ele está fazendo o papel de cliente naquela conversa.

"Cliente" e "servidor" não são tipos de máquina nem de programa. São **papéis em uma conversa**. Quem pergunta é cliente; quem responde é servidor. Fim.

Do mesmo jeito, servidor não é um computador especial zunindo num porão gelado. É só um programa que escuta e responde. Daqui a alguns capítulos, o servidor vai ser um processo Python rodando no seu notebook — e ele será tão "servidor" quanto o do Google.

## Onde este curso mora

Neste curso, nós construímos **o lado que responde**. A página bonita, os botões, o aplicativo — isso é o cliente, e é problema de outro curso. O nosso produto é o motor: recebe pedidos estruturados, aplica as regras do negócio, mexe nos dados e devolve respostas estruturadas.

Na prática, isso quase sempre significa: **JSON entra, JSON sai** (calma, JSON tem lição própria mais adiante). O cliente que consome essas respostas pode ser um site, um app, um script — para o nosso backend, tanto faz. E essa indiferença é uma força: um backend bem feito atende todos eles sem mudar uma linha.

## O que você deve conseguir fazer agora

- Explicar o ciclo request-response para um colega, sem colar.
- Dizer quem é cliente e quem é servidor em cada cena:
  1. Seu navegador abrindo a página da Wikipedia.
  2. O app do iFood pedindo a lista de restaurantes perto de você.
  3. Um script Python que baixa a cotação do dólar de uma API — e, de quebra: nessa cena, a API é o quê?
- Explicar por que a frase "meu notebook virou um servidor" faz todo o sentido.