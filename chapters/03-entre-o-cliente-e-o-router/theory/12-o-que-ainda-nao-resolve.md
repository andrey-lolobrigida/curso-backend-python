# Lição 12 — O que este código ainda não resolve

O capítulo 2 fechou com uma lição igual a esta, e pelo mesmo motivo: **um curso que entrega código tem uma dívida com quem vai ler esse código.** Se eu sei que tem um defeito, eu te conto.

O capítulo 3 aumentou essa dívida bastante. Ele encostou duas camadas no FairFare e montou uma bancada inteira em volta dele — proxy, página, certificado, carga. Cada uma dessas peças foi entregue com um pedaço faltando, e cada pedaço faltando foi declarado na lição onde ele apareceu. Esta lição é o lugar onde tudo isso vira uma lista só, com endereço e com o capítulo em que morre.

Nada aqui é novidade. Se você leu o capítulo inteiro, já viu todos os itens. O valor está em vê-los juntos.

## 1. O rate limiter tem três buracos, não um

**Onde:** `app/middleware/rate_limit.py`. Os três já estão escritos no docstring do módulo, desde a lição 05.

### 1a. O balde é do processo, não do app

```python
        # ip -> (fichas disponíveis, instante da última atualização)
        self.baldes: dict[str, tuple[float, float]] = {}
```

Um `dict` comum, num atributo de instância, na memória de **um** processo Python.

**Como se manifesta:** a lição 11 mediu. Com um worker, cem requests do mesmo cliente dão `200: 20`. Com `--workers 4`, dão `200: 61`, `200: 67`, `200: 62` — três rodadas, e o limite de 20 virou algo perto de 60. Quatro processos, quatro baldes, e o cliente cobra de cada um.

**Por que continua:** o conserto não é uma linha melhor de Python. É tirar o estado da memória do processo e pôr num lugar que os quatro workers enxerguem.

E há um respingo na suíte: a linha `fastapi_app.middleware_stack = None` do `conftest.py` existe só porque o processo do pytest também é um processo, com um balde só que um teste esvazia para o seguinte. É uma gambiarra de teste comprada por esta limitação, e some quando a limitação sumir.

**Resolvido no:** capítulo 7, com Redis.

### 1b. A chave é o IP em que o servidor resolveu acreditar

```python
        cliente = scope["client"][0] if scope.get("client") else "desconhecido"
```

O middleware pergunta ao `scope` quem é o cliente, e usa a resposta como chave do balde. Isso está **certo** — quem tem que garantir que esse valor é confiável é a configuração do servidor, não o middleware.

**Como se manifesta:** a lição 08 fez cem requests com um `X-Forwarded-For: 10.0.0.{i}` diferente em cada uma, contra um uvicorn com os padrões. Resultado: `200: 100`. Cem baldes novos, limite nenhum. Um header inventado pelo cliente desmontou o limitador.

**Por que continua:** a cura é de configuração, não de código — a borda escreve o header, o app só confia em quem está listado, e o app não é alcançável por fora da borda. A lição 08 escreveu essa configuração; numa máquina só, com proxy e atacante no mesmo `127.0.0.1`, ela não tem como ser demonstrada.

**Resolvido no:** capítulo 11, onde Docker e endereços de verdade tornam a configuração rodável.

### 1c. O dicionário nunca esquece ninguém

Cada IP que bate na porta vira uma entrada. Nenhuma entrada sai. Não há TTL, não há limpeza, não há teto.

**Como se manifesta:** devagar e sem barulho, que é o pior jeito. A memória do processo cresce com o número de IPs distintos que já apareceram — e quem decide quantos IPs aparecem é exatamente o tráfego que o limitador deveria conter. Um limitador que fica mais caro quanto mais gente ele recusa.

**Por que continua:** um `dict` com expiração feito à mão é código de infraestrutura, e Redis já resolve isso com uma linha por chave.

**Resolvido no:** capítulo 7, via TTL.

### E uma frase para guardar: rate limit não é autenticação

Ele conta requests por IP. Não sabe quem é ninguém, e o item 1b mostrou como IP é uma identidade frágil. Contar volume e decidir permissão são dois problemas diferentes, e o segundo é o capítulo 6.

## 2. As origens e os limites estão cravados no código

**Onde:** `app/main.py`.

```python
app.add_middleware(RateLimitMiddleware, capacidade=20, recarga_por_segundo=5.0)
...
    allow_origins=["http://localhost:8080"],
```

`http://localhost:8080` é o endereço da bancada. Capacidade 20 e recarga 5/s são números que escolhi para a demonstração caber numa tela.

**Como se manifesta:** publicar a página em outro domínio exige editar Python e fazer deploy. Afrouxar o limite em produção sem afrouxar em desenvolvimento é impossível. Configuração misturada com código sempre acaba assim.

E falta ali um valor que o capítulo 6 vai obrigar a escrever: não existe `allow_headers`, porque os headers da lista segura já passam sozinhos — quando a API pedir `Authorization`, ele entra. O comentário ao lado do `CORSMiddleware` no `main.py` já avisa. **Capítulo 6.**

**Resolvido no:** capítulo 11, com configuração por ambiente.

## 3. O proxy da bancada é instrumento, não produto

**Onde:** `chapters/03-entre-o-cliente-e-o-router/bancada/proxy.py`. As lições 06 e 08 já disseram quase tudo isto; aqui é só a lista.

| O que falta | Como aparece | Morre no |
|---|---|---|
| `HOP_BY_HOP` é uma lista fixa, não a definição do RFC 7230 | um header citado em `Connection:` mas fora do conjunto atravessa; faltam `proxy-authenticate`/`proxy-authorization` | cap. 11 |
| Headers repetidos da resposta viram um só, com vírgula | inofensivo hoje; errado quando o cap. 6 trouxer `set-cookie` e este arquivo for reaproveitado | cap. 11 |
| Segura o corpo inteiro na memória | um upload grande vira RAM | cap. 11 |
| Cria o `AsyncClient` no import e nunca o fecha | num app de verdade isso vai para o `lifespan` | cap. 11 |
| Duplica `date` e `server` na resposta | visível em qualquer `curl -i` na 8080 | cap. 11 |
| Imprime toda request no terminal, corpo incluído | de propósito: é o gancho da lição 09 | *ressalva de bancada* |
| Sobrescreve o `X-Forwarded-For`, nunca acrescenta | certo para uma borda; como segundo proxy de uma cadeia, apagaria o cliente real | cap. 11 |
| Sem timeout fino, sem retry, sem HTTP/2 | — | cap. 11 |

**Por que continua:** ele existe para caber em cinquenta linhas legíveis. Um proxy correto é maior que este capítulo.

**Resolvido no:** capítulo 11, com Caddy ou nginx de verdade, em Docker. Os arquivos `Caddyfile` e `nginx.conf` da bancada continuam sendo **lidos como texto e nunca executados** neste curso.

## 4. Nesta bancada o FairFare continua alcançável pela porta dos fundos

**Onde:** no arranjo, não num arquivo. O proxy escuta na 8080; o uvicorn do FairFare escuta na 8000 e continua aceitando quem bater lá direto, com os padrões dele — inclusive o `X-Forwarded-For` do item 1b.

**Por que continua:** de propósito. As duas cargas — a que passa pelo proxy e a que fura o proxy — precisam existir lado a lado para a lição 08 poder compará-las.

**Resolvido no:** capítulo 11. A cura não é código: é a rede do deploy, onde só o proxy alcança o app.

## 5. O TLS ficou pela metade, e a metade que falta está declarada

Duas dívidas com capítulo, e duas ressalvas que não são defeito e não morrem em capítulo nenhum.

| O quê | Como aparece | Morre no |
|---|---|---|
| O certificado é autoassinado, de trinta dias, para `localhost` | serve para ver TLS funcionando, e só | cap. 11 (CA de verdade, emissão e renovação) |
| O custo do handshake em milissegundos nunca foi medido | a lição 09 mediu a *estrutura* (uma ida e volta no 1.3, duas no 1.2); em loopback o tempo some no ruído — o número usável é o da lição 02, ~5,9 ms por ida e volta, vezes duas ou três | *ressalva de medição* |
| O trecho proxy→app viaja em texto puro | aceitável enquanto for loopback ou rede interna confiável; fora disso, o problema da lição 09 volta dentro da sua infraestrutura | cap. 11, com a rede do deploy |
| `carga.py` e `pagina/index.html` apontam para `http://` | a bancada é texto puro por padrão; TLS é arranjo montado à mão | *ressalva de bancada* |

## 6. Sobre os vários processos, o que não foi testado

Duas dívidas com capítulo, três ressalvas de bancada ou de medição.

| O quê | Como aparece | Morre no |
|---|---|---|
| Um worker que morre sozinho nunca foi testado | a demonstração de shutdown da lição 11 rodou num processo único, com sinal mandado à mão; quem devolve o worker que caiu é o pai do uvicorn, um supervisor ou um orquestrador | cap. 11 |
| Windows não foi verificado | o uvicorn documenta `--workers` lá, via `spawn`; aqui só Linux rodou; caminho conhecido em caso de problema: WSL | *ressalva de bancada* |
| Qual é o melhor valor de `--workers` não foi medido | "um por núcleo" é regra de bolso, não resultado | *ressalva de medição* |
| Os números são desta máquina, nesta sessão | doze núcleos, loopback, SQLite; a direção se repete, os valores não (61, 67, 62 para a mesma pergunta) | *ressalva de medição* |
| Todo teto dentro de um processo ganha o multiplicador do item 1a | o pool do SQLAlchemy: 15 conexões por processo, 60 com quatro workers; não dói com SQLite | cap. 4, com PostgreSQL e o limite de conexões do servidor |

## 7. As herdadas, que continuam de pé

Nada do que este capítulo fez mexeu nelas. Cada uma está explicada na lição 11 do capítulo 2:

- **Duas pessoas ainda podem reservar o mesmo horário** — o check-then-act de `BookingService.create`. Capítulo 4.
- **`GET /bookings` ainda faz 2N+1 consultas** — o N+1 do capítulo 1. Capítulo 5.
- **Ainda não existe autenticação nenhuma** — o `user_id` continua sendo uma afirmação do cliente. Capítulo 6.

E vale reler as duas primeiras à luz deste capítulo. O rate limiter recusa volume, não intenção: um cliente dentro do limite ainda dispara a corrida de reserva dupla. O CORS não protege nada disso — ele protege o usuário do browser, e um `curl` nunca viu um erro de CORS na vida.

## A regra, em uma frase

**Este curso não esconde bugs no código que entrega.** Toda limitação conhecida está escrita no material do capítulo onde ela existe, junto com o capítulo que a resolve. Se você achar no FairFare um defeito que não esteja declarado em lugar nenhum, isso não é um exercício disfarçado — é um erro meu, e vale um issue.

Onde houver código quebrado de propósito — e os exercícios deste capítulo têm —, o enunciado diz que ele está quebrado. Aprender consertando é ótimo. Ser enganado pelo material do curso é outra coisa.

## O que você deve conseguir fazer agora

- Listar os **três** problemas do rate limiter, apontar cada um no arquivo, e dizer em que capítulo cada um morre (dois no 6, um no 10).
- Explicar por que o `X-Forwarded-For` da lição 08 e o `--workers 4` da lição 11 quebram o mesmo middleware por motivos completamente diferentes.
- Para qualquer limitação desta lista, dizer onde ela está e em que capítulo ela morre — e reconhecer as poucas que são **ressalva** de medição ou de bancada, que não morrem em capítulo nenhum. Sem consultar a lista.
