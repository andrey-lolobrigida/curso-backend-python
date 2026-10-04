# Lição 09 — HTTP não lembra de você

Última lição de teoria do capítulo, e ela começa com um experimento levemente ofensivo. Apresente-se ao servidor com a senha certa:

```console
$ curl -i -H "X-Senha: clube-do-backend" localhost:8000/segredo
HTTP/1.1 200 OK

{
  "segredo": "voce leu os headers. e exatamente assim que se faz."
}
```

Ótimo, ele te conhece. Agora peça de novo, *sem* a senha:

```console
$ curl -i localhost:8000/segredo
HTTP/1.1 401 Unauthorized
```

Você se apresentou há dois segundos! Ele já te viu! Não importa: **cada request nasce órfã**. O servidor não guarda nenhuma lembrança de quem falou com ele — nem da request anterior, nem de você.

## O nome disso: stateless

A afirmação precisa: **HTTP é um protocolo sem estado (stateless)** — nenhuma request depende de outra; cada uma deve carregar, dentro de si, todo o contexto necessário para ser atendida (headers, corpo, URL). O protocolo não oferece nenhum "como eu ia dizendo...".

À primeira vista parece um defeito de fábrica. É o oposto: é uma das decisões de design mais geniais da web.

## Por que amnésia é uma superpotência

Imagine que o HTTP *lembrasse*: cada conversa teria um fio de contexto, e o servidor que começou a te atender seria o único capaz de continuar — ele teria suas lembranças.

Sem memória, qualquer request pode ser atendida por **qualquer servidor**. Dez máquinas idênticas atrás de um distribuidor de carga: a request 1 cai na máquina 3, a request 2 na máquina 7, e nada quebra — nenhuma delas precisava lembrar de você. Uma máquina morre? As outras seguem. Tráfego dobrou? Ligue mais máquinas. **Escalar backends é infinitamente mais fácil porque o protocolo é desmemoriado.** (Capítulo 11 colhe esse fruto.)

O preço: o problema "quem é você?" não é resolvido pelo protocolo — ele é **empurrado para dentro de cada request**. Foi o que fizemos com o `X-Senha`: a credencial viajou em toda request que precisou dela.

## Mas o site lembra que estou logado...

Você loga uma vez e navega logado por dias. Se cada request nasce órfã, como?

Resposta curta: a credencial está indo em **todas as requests** — você é que não vê. Depois do login, o servidor entrega ao navegador um crachá (um **cookie** de sessão ou um **token**), e o navegador o anexa automaticamente, como um header, a cada request seguinte. O protocolo continua sem memória; o *cliente* é que repete a apresentação, incansavelmente, em seu nome.

Como esse crachá é emitido, verificado e revogado — sessões vs JWTs, os detalhes que separam um login seguro de uma vulnerabilidade — é o coração do capítulo 6. Por ora, basta o mecanismo: **estado de "quem é você" viaja na request, sempre.**

## "Mas o servidor guarda as reservas!"

Pegadinha final, e é fina. Nosso servidor **guarda** reservas: você faz um POST, e um GET seguinte mostra a reserva lá. Isso não contradiz tudo o que acabei de dizer?

Não — são dois estados diferentes:

- **Estado da aplicação**: os dados do negócio (quadras, reservas). Servidores guardam isso, claro — é o trabalho deles (em breve, num banco de dados de verdade).
- **Estado da conversa**: memória sobre *o diálogo com você* — quem você é, o que pediu antes. **É disso que o HTTP abre mão.**

O servidor lembra *das reservas*; não lembra *de você*. A reserva existe para qualquer cliente que perguntar — ela é um fato do mundo, não uma lembrança da nossa conversa.

## Fim da teoria — e o mapa do que vem

Você passou o capítulo inteiro do lado de fora, batendo educadamente na porta de um servidor pronto. Agora vá aos exercícios (se ainda não foi) — e no **capítulo 1**, invertemos o jogo: você escreve o servidor. O app de reservas em grupo nasce lá, e o `server.py` que hoje parece mágica vira o "ah, era só isso?".

## O que você deve conseguir fazer agora

- Explicar "HTTP é stateless" em uma frase, sem usar a palavra "stateless".
- Dizer onde viaja o "quem é você" se o protocolo não guarda a conversa.
- Explicar por que statelessness facilita escalar um backend para várias máquinas.
- Desmontar a pegadinha: por que um servidor que *guarda reservas* continua sendo um servidor HTTP sem estado?