# Lição 09 — TLS: a conversa fica secreta

A lição 08 acabou com o proxy digno de confiança. Ele sabe quem conectou, não acredita em header de estranho, e conta a verdade para o app.

Duas abas, como sempre — a 8000 continua sendo o FairFare de verdade, como no fim da lição 08, porque a gente quer um POST que crie usuário.

```bash
uv run uvicorn app.main:app --port 8000
```

```bash
uv run uvicorn proxy:app --port 8080 --no-proxy-headers \
    --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

Crie a Carla pelo proxy, e depois olhe o terminal **dele**:

```console
$ curl -s -X POST localhost:8080/api/users \
    -H 'content-type: application/json' \
    -d '{"nome":"Carla","email":"carla@exemplo.com"}'
```

No terminal do proxy:

```console
→ POST /users  corpo=b'{"nome":"Carla","email":"carla@exemplo.com"}'
← 201
```

*(Se você rodar isso duas vezes, o `← 201` vira `← 409` — o FairFare recusa e-mail repetido. A linha de cima, que é a que interessa aqui, sai igual nos dois casos.)*

O e-mail da Carla está ali, em texto, na tela de outro programa. O `proxy.py` imprime de propósito — é instrumento de bancada, a lição 06 avisou. Mas o ponto não é o `print`. O ponto é que **ele pôde**. Aqueles bytes atravessaram a rede legíveis. Todo mundo no caminho pôde fazer o mesmo: o Wi-Fi do café, o roteador do prédio, o provedor, qualquer máquina entre o browser da Carla e a sua.

O capítulo 0 prometeu duas vezes que https era "HTTP com criptografia — capítulo 3". Esta é a hora. E não é uma promessa de proteger senha: é o e-mail da Carla, num POST comum, num app sem nada de secreto.

## O que o TLS garante — e o que ele não garante

**TLS** (*Transport Layer Security*) é uma camada entre o TCP e o HTTP. O HTTP não muda em nada: os mesmos métodos, os mesmos headers, o mesmo corpo. O que muda é que eles viajam cifrados. `https` é exatamente isso — HTTP dentro de TLS, na porta 443 em vez da 80.

Pense num envelope lacrado, com o nome do remetente conferido na portaria. Agora o rigor, porque a analogia esconde metade:

**Garante três coisas.**

- **Sigilo.** Quem está no meio vê bytes embaralhados. Não vê o e-mail da Carla, nem o path, nem os headers.
- **Integridade.** Quem está no meio não consegue *alterar* nada sem que o outro lado perceba. Cada pedaço vai com uma marca de autenticidade; um bit trocado derruba a conexão.
- **Identidade do servidor.** O cliente confere que está falando com quem pensa que está — não com alguém que sequestrou o caminho.

**Não garante outras duas, e confundir isso é caro.**

- **Quem *você* é.** TLS autentica o servidor, não o usuário. Que a Carla é a Carla é assunto de autenticação — capítulo 5.
- **O que o servidor faz com o dado depois.** O envelope chega lacrado; o que o destinatário faz com a carta é problema dele. Um servidor `https` pode logar o e-mail da Carla em texto puro, vender a lista, ou vazar tudo. TLS protege o **caminho**, não o destino.

E repare no que sobrevive mesmo com TLS: o **endereço** do servidor e a **porta** continuam visíveis (é preciso rotear os pacotes), e o nome do host normalmente também, porque o cliente o anuncia no começo do handshake para o servidor saber qual certificado apresentar. Quem está no meio sabe que você falou com `fairfare.exemplo.com`. Não sabe o que vocês disseram.

## O handshake, em quatro frases

Antes do primeiro byte de HTTP, os dois lados negociam. No TLS 1.3, que é o que a sua máquina provavelmente vai negociar:

1. O cliente diz olá e lista o que sabe falar (versões, algoritmos) — o **Client Hello** — já mandando junto a metade dele de uma troca de chaves.
2. O servidor responde com a metade dele. **Neste ponto os dois já têm a chave de sessão**, e nada mais precisa ir em claro.
3. Ainda na mesma leva, e **já cifrado**, o servidor manda o **certificado** e uma assinatura provando que a chave privada correspondente é dele.
4. O cliente confere o certificado, os dois trocam um `Finished`, e o HTTP começa.

Repare na ordem, porque ela é uma mudança do TLS 1.3: **a chave é combinada antes de o certificado chegar**, então o certificado viaja cifrado. No TLS 1.2 era o contrário — certificado em claro primeiro, chave depois.

Isso custa idas e voltas, e a lição 02 deixou essa fatura anotada. Vamos abrir a conta com o `curl -v`, que imprime cada mensagem do handshake com a direção (`OUT` = saiu do cliente, `IN` = chegou).

Para isso é preciso um servidor falando TLS. Numa terceira aba, gere o certificado e suba o FairFare na 8443 — o script é o assunto da lição 10; aqui ele é só o palco:

```bash
B=chapters/03-entre-o-cliente-e-o-router/bancada
uv run python $B/certificado.py
uv run uvicorn app.main:app --port 8443 \
    --ssl-keyfile $B/certs/chave.pem --ssl-certfile $B/certs/cert.pem
```

Essa aba fica presa no uvicorn, então o `curl` roda em outra — e variável de shell não atravessa de uma aba para a outra. Defina o mesmo `B` lá, como na primeira linha abaixo. É por ele que o `curl` acha o certificado: o `--cacert` manda ele confiar naquele arquivo. Por que isso é preciso — e o que acontece sem a flag — é a lição 10.

```console
$ B=chapters/03-entre-o-cliente-e-o-router/bancada
$ curl -sv --cacert $B/certs/cert.pem -o /dev/null https://localhost:8443/users
* TLSv1.3 (OUT), TLS handshake, Client hello (1):
* TLSv1.3 (IN), TLS handshake, Server hello (2):
* TLSv1.3 (IN), TLS handshake, Encrypted Extensions (8):
* TLSv1.3 (IN), TLS handshake, Certificate (11):
* TLSv1.3 (IN), TLS handshake, CERT verify (15):
* TLSv1.3 (IN), TLS handshake, Finished (20):
* TLSv1.3 (OUT), TLS change cipher, Change cipher spec (1):
* TLSv1.3 (OUT), TLS handshake, Finished (20):
* SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384 / X25519 / id-ecPublicKey
```

(`Encrypted Extensions` é literalmente isso: "extensões cifradas" — a primeira mensagem que já vai protegida pela chave que os dois acabaram de combinar. Ela só existe no 1.3.)

Conte as **trocas de direção**, não as linhas: sai um bloco, entra um bloco, sai um bloco. O cliente manda o `Finished` já podendo mandar o HTTP junto — então **uma ida e volta** de TLS. Com o handshake do TCP antes dele, dá **duas** antes do primeiro byte de HTTP. É exatamente a conta que a lição 02 fez.

Agora o mesmo servidor, forçando a versão anterior com `--tls-max 1.2`:

```console
$ curl -sv --tls-max 1.2 --cacert $B/certs/cert.pem -o /dev/null https://localhost:8443/users
* TLSv1.2 (OUT), TLS handshake, Client hello (1):
* TLSv1.2 (IN), TLS handshake, Server hello (2):
* TLSv1.2 (IN), TLS handshake, Certificate (11):
* TLSv1.2 (IN), TLS handshake, Server key exchange (12):
* TLSv1.2 (IN), TLS handshake, Server finished (14):
* TLSv1.2 (OUT), TLS handshake, Client key exchange (16):
* TLSv1.2 (OUT), TLS change cipher, Change cipher spec (1):
* TLSv1.2 (OUT), TLS handshake, Finished (20):
* TLSv1.2 (IN), TLS handshake, Finished (20):
* SSL connection using TLSv1.2 / ECDHE-ECDSA-AES256-GCM-SHA384 / X25519 / id-ecPublicKey
```

Uma troca de direção a mais: o servidor ainda precisa responder um `Finished` antes de o cliente poder falar HTTP. **Duas** idas e voltas de TLS, três no total. O TLS 1.3 economizou uma — e essa é a diferença prática mais visível entre as duas versões.

Duas coisas para levar daqui. A primeira: o `curl` e o uvicorn desta máquina negociaram **1.3** sozinhos, sem eu pedir; o 1.2 só apareceu porque eu forcei. A segunda: é mais uma ida e volta *por conexão nova*, e a lição 02 mediu quanto custa uma ida e volta fora do loopback (5,9 ms contra 0,058 ms). **Keep-alive importa mais com TLS do que sem**, porque agora a conexão reaproveitada economiza o dobro.

Falta a metade que o handshake escondeu. No passo 3, o servidor mandou um **certificado**, e o `curl` só aceitou falar com ele porque o `--cacert` mandou confiar naquele arquivo. Sem a flag, ele se recusa — e o browser também. O que é esse arquivo, o que ele prova, e por que "criptografado" sem ele não quer dizer "seguro": lição 10.

## O que você deve conseguir fazer agora

- Listar as três garantias do TLS (sigilo, integridade, identidade do servidor) e as duas que ele **não** dá (quem você é; o que o servidor faz com o dado depois).
- Dizer o que continua visível mesmo com TLS, e por quê.
- Contar as idas e voltas do handshake no `curl -v`, dizer por que o TLS 1.3 gasta uma a menos que o 1.2, e por que keep-alive importa mais com TLS do que sem.
