# Capítulo 0 — HTTP e a web

Todo o resto deste curso — FastAPI, bancos, filas, deploys — é escrito numa gramática só: HTTP. Frameworks vêm e vão; o protocolo de 1991 continua embaixo de todos eles. Este capítulo ensina você a ler e falar essa gramática **sem intermediários**: requests escritas à mão, respostas lidas linha a linha, erros interpretados como o diagnóstico que são.

Uma escolha deliberada: **não há código do app aqui**. Você vai passar o capítulo conversando com um mini-servidor pronto — porque aprender um protocolo e construir um servidor ao mesmo tempo é aprender mal os dois. O nosso app nasce no capítulo 1, e aí a conversa deste capítulo vira a planta da casa.

## Pré-requisitos

| Ferramenta | Conferir com | Nota |
|------------|--------------|------|
| Python 3.11+ | `python3 --version` | o curso mira 3.12+, mas este capítulo roda em 3.11 |
| curl | `curl --version` | já vem em praticamente todo sistema |
| nc (netcat) | `nc -h` | usado num único (e ótimo) exercício |

## As lições

Em ordem — cada uma tem uma ideia só e termina com um checkpoint:

| # | Lição | A ideia única |
|---|-------|---------------|
| 01 | [Cliente, servidor e o ciclo request-response](theory/01-cliente-servidor-e-o-ciclo-request-response.md) | A conversa de pergunta-e-resposta que move a web |
| 02 | [Por baixo do capô: DNS, portas e TCP](theory/02-por-baixo-do-capo-dns-portas-tcp.md) | O suficiente para `localhost:8000` fazer sentido |
| 03 | [Anatomia de uma request](theory/03-anatomia-de-uma-request.md) | Request é texto — e o curl entra em cena |
| 04 | [Anatomia de uma response](theory/04-anatomia-de-uma-response.md) | Status line, headers, corpo: o espelho da request |
| 05 | [Status codes](theory/05-status-codes.md) | Quatro famílias, dez códigos, um culpado por família |
| 06 | [Métodos HTTP e idempotência](theory/06-metodos-http-e-idempotencia.md) | Os verbos — e a propriedade que vale dinheiro |
| 07 | [URLs por dentro](theory/07-urls-por-dentro.md) | Caminho identifica, query refina |
| 08 | [Headers, Content-Type e JSON](theory/08-headers-content-type-e-json.md) | O corpo é bytes; o header dá o significado |
| 09 | [HTTP não lembra de você](theory/09-http-nao-lembra-de-voce.md) | Statelessness: a amnésia que escala |

## Como percorrer

O caminho que recomendo intercala teoria e prática:

1. Lições **01–05**.
2. [Exercícios](exercises/README.md) **1 e 2** — a caça ao tesouro com curl e a request crua na unha.
3. Lições **06–09**.
4. Exercício **3** — os scripts quebrados.

Os exercícios usam um mini-servidor local (`exercises/server.py` — `python3 server.py` e pronto). Você **não precisa entender o código dele**; ele é só o interlocutor. Empacou? O [SOLUTIONS.md](SOLUTIONS.md) explica cada resposta com o raciocínio — depois que você tentar.

## O diff deste capítulo

Este curso trata diffs como material de leitura: ver *o que mudou e por quê* ensina tanto quanto o estado final. Este capítulo nasceu na branch `chapter-00`, commit a commit:

```bash
git log --oneline --reverse v-chapter-00
```

Escolha um commit e abra-o inteiro com `git show <hash>`. Os commits foram escritos para serem lidos nessa ordem — são a narrativa do capítulo em forma de código. Prefere o browser? [A mesma lista está no GitHub](https://github.com/andrey-lolobrigida/curso-backend-python/commits/v-chapter-00) — só repare que lá ela vem do mais novo para o mais antigo; leia de baixo para cima.

## Ao terminar

Você saberá ler qualquer conversa HTTP — e vai notar que ainda não escreveu um servidor. É proposital, e é a deixa do **capítulo 1**: construir, em camadas, o backend de um app de reservas em grupo com divisão de despesas. O `server.py` que este capítulo tratou como caixa-preta será a primeira coisa que você vai desmontar.