# Lição 02 — Por baixo do capô: DNS, portas e TCP

Daqui a duas lições, você vai rodar um servidor e conversar com ele em `http://localhost:8000`. Essa frasezinha esconde três perguntas:

1. Como um **nome** (`localhost`, `google.com`) vira um lugar na rede?
2. O que é esse **`:8000`**?
3. Quem garante que os bytes da conversa **chegam inteiros e em ordem**?

Esta lição responde as três — e só as três. Não é um curso de redes; é o mínimo para o chão não ficar oco.

## Nomes viram números: DNS

A rede não entende nomes. Ela entende **endereços IP** — números como `142.250.79.46` que identificam uma máquina. Nomes existem para humanos.

Pense na agenda do seu telefone: você toca em "Mãe", e o aparelho disca o número. Você nunca decorou o número — mas ele existe, e é ele que faz a ligação acontecer. O **DNS** (Domain Name System) é a agenda de contatos da internet: antes de qualquer conversa, o cliente pergunta ao DNS "qual é o IP de `google.com`?" e recebe o número de volta.

A afirmação precisa: **a resolução de nome acontece antes de qualquer conexão**. Primeiro descobre-se o IP; só então se bate na porta.

E `localhost`? É um nome especial que sempre aponta para `127.0.0.1` — o "IP de casa", o endereço que toda máquina usa para falar consigo mesma. Quando você acessa `localhost:8000`, a conversa nem sai do seu computador. Perfeito para desenvolvimento.

## O número do apartamento: portas

O IP identifica a **máquina**. Mas uma máquina roda dezenas de programas ao mesmo tempo — quando chega um pedido, entrega para quem?

O IP é o endereço do prédio; a **porta** é o número do apartamento. A versão técnica: uma porta é um número (de 0 a 65535) que identifica **qual programa** naquela máquina deve receber a conexão. O par IP + porta identifica um destino exato — e por isso **dois programas não podem escutar na mesma porta ao mesmo tempo**: seria dois moradores disputando a mesma campainha. (Você vai tropeçar no erro `address already in use` uma hora. Agora já sabe o que ele significa.)

Algumas portas têm significado combinado mundialmente:

- **80** é a porta padrão do HTTP.
- **443** é a padrão do HTTPS (HTTP com criptografia — capítulo 3).

"Padrão" quer dizer: se você não disser nada, o navegador assume. `http://google.com` é, por baixo, `http://google.com:80` — o `:80` está lá, só que invisível. Já `localhost:8000` precisa do número explícito porque 8000 não é padrão de nada; é só uma convenção de desenvolvedores para "meu servidor de testes" (8080 e 5000 são outras da mesma turma).

## O carteiro obsessivo: TCP

Descobrimos o IP, batemos na porta certa. Agora a conversa em si: requests e responses são, no fim das contas, **bytes viajando pela rede**. E a rede, crua, é caótica — pacotes podem se perder, chegar fora de ordem, chegar duplicados.

O HTTP não quer saber desse caos. Ele terceiriza o problema para o **TCP**, o protocolo de transporte que promete: *os bytes que entram de um lado saem do outro, inteiros e na mesma ordem*. Como um carteiro obsessivo que numera cada página da carta, confirma o recebimento de cada uma e reenvia o que se perder. A versão precisa: TCP dá ao HTTP a ilusão de um **tubo confiável de bytes** entre cliente e servidor, e cuida sozinho de retransmissões e ordenação.

Um detalhe que vai importar mais tarde: antes de transportar qualquer coisa, o TCP faz um aperto de mão (*handshake*) — uma ida e volta de "podemos falar?" / "podemos". Isso custa tempo. Guarde essa fatura; no capítulo 3, ela explica por que conexões são reaproveitadas em vez de abertas a cada request.

## A pilha inteira em uma figura

```
  [ DNS ]  "google.com? é 142.250.79.46"     ← antes de tudo, a agenda
     |
     v
  +--------------------------------------+
  |  HTTP   — a conversa                 |   "GET /quadras" / "200 OK"
  +--------------------------------------+
  |  TCP    — a entrega confiável        |   bytes inteiros, em ordem
  +--------------------------------------+
  |  IP     — o endereçamento            |   de 192.168.0.12 para 142.250.79.46
  +--------------------------------------+
```

Cada camada só conhece a de baixo e confia nela. O HTTP escreve a conversa; o TCP entrega; o IP endereça. Neste curso, moramos no andar de cima — mas agora você sabe sobre o que ele está construído.

## O que você deve conseguir fazer agora

- Decompor `http://localhost:8000/quadras` e dizer o papel de cada pedaço: o que é o `localhost`, o que é o `8000`, o que é o `/quadras` (spoiler da lição 07).
- Explicar por que `http://google.com` funciona sem `:80` na frente.
- Explicar por que dois programas não podem escutar na mesma porta — e o que provavelmente aconteceu quando você vir `address already in use`.
- Dizer, em uma frase cada, o que DNS, TCP e IP fazem pelo HTTP.