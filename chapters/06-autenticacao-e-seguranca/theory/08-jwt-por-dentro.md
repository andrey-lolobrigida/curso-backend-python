# Lição 08 — JWT por dentro

A lição 07 deixou uma imagem: um crachá que carrega a própria validade dentro dele, assinado, e um servidor que confere a assinatura sem consultar lista nenhuma. Esse crachá existe. Chama-se **JWT** (JSON Web Token, RFC 7519, que sugere pronunciar "jót").

Esta lição monta um à mão, na bancada, e depois tenta enganar o verificador de três jeitos: adulterar o payload, forjar um crachá sem assinatura e usar uma cópia depois do logout. Os dois primeiros esbarram no verificador certo (o segundo passa no ingênuo). O terceiro passa, e é o que mais ensina.

## Um crachá que se verifica sozinho

O token do FairFare é **opaco** (lição 04): o número do guarda-volumes. Ele não diz nada. Para saber de quem é, o servidor pergunta ao banco, em toda request. É o `SELECT` a mais que a lição 05 contou.

O JWT é o contrário. Pense num ingresso de show com selo holográfico. O porteiro não liga para a bilheteria para saber se ele vale. Ele olha o selo: se é legítimo, o que está impresso no ingresso é verdade.

Agora a versão precisa. O JWT carrega os dados (quem é, até quando vale) e uma **assinatura** calculada sobre esses dados com uma chave secreta. Quem tem a chave refaz a conta e confere. Bateu, os dados são os que o emissor escreveu. Ninguém precisou consultar nada.

Um aviso antes de abrir: **a bancada é de brinquedo, e o app não muda.** O FairFare continua com o token opaco e a tabela `sessions`. A lição 09 explica por quê. Aqui o objetivo é ver o mecanismo, para saber o que uma biblioteca de JWT faz por você, e o que ela pode fazer errado.

```console
$ uv run python chapters/06-autenticacao-e-seguranca/bancada/jwt_na_mao.py
```

## As três partes

Um JWT são três pedaços de texto separados por ponto: `header.payload.assinatura`.

- O **header** diz como o token foi assinado: `{"alg":"HS256","typ":"JWT"}`.
- O **payload** traz os dados. No nosso, `{"sub":"1","nome":"Ana","exp":...}`. O `sub` (*subject*) é de quem é o crachá. O `exp` é quando ele vence, em segundos desde 1970.
- A **assinatura** amarra as duas partes anteriores à chave.

O header e o payload são JSON, mas não viajam como JSON. Viajam em **base64url**, o mesmo que o `token_urlsafe` da lição 04 usa: o base64 com `-` e `_` no lugar de `+` e `/`. O JWT tira também o `=` que o base64 põe no fim para completar o tamanho. O resultado passa por URL e por header HTTP sem ninguém precisar escapar nada.

A bancada tem tudo isso em poucas linhas:

```python
def b64url(dados: bytes) -> str:
    # O base64 de sempre, com - e _ no lugar de + e /, e sem o = do fim (RFC 7515, seção 2).
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def hs256(entrada: str, segredo: bytes) -> bytes:
    # HMAC: um hash com chave. Sem a chave, ninguém calcula o mesmo resultado.
    return hmac.new(segredo, entrada.encode("ascii"), hashlib.sha256).digest()


def montar(header: bytes, payload: bytes, segredo: bytes) -> str:
    # As três partes: header.payload.assinatura. A assinatura cobre as duas primeiras,
    # do jeito que elas viajam (em base64url), e não o JSON original.
    entrada = f"{b64url(header)}.{b64url(payload)}"
    return f"{entrada}.{b64url(hs256(entrada, segredo))}"


def assinar(payload: dict, segredo: bytes) -> str:
    return montar(para_json({"alg": "HS256", "typ": "JWT"}), para_json(payload), segredo)
```

O `HS256` do header é isto: **HMAC com SHA-256**. O HMAC, em uma frase, é um hash com chave. Você já conhece o sha256 da lição 02: qualquer um calcula o hash de qualquer coisa. O HMAC mistura uma chave secreta na conta, e aí só quem tem a chave chega no mesmo resultado.

### Conferindo contra o RFC

Código de criptografia escrito à mão tem um jeito fácil de estar errado sem dar erro nenhum. Então o ato 1 confere a bancada contra o exemplo oficial: o apêndice A.1 do RFC 7515, que dá o header, o payload, a chave e a assinatura esperada.

```console
== 1. Conferir contra o RFC 7515 (apêndice A.1) ==
header  (bytes): b'{"typ":"JWT",\r\n "alg":"HS256"}'
payload (bytes): b'{"iss":"joe",\r\n "exp":1300819380,\r\n "http://example.com/is_root":true}'
chave: 64 bytes
header     eyJ0eXAiOiJKV1QiLA0KICJhbGciOiJIUzI1NiJ9
payload    eyJpc3MiOiJqb2UiLA0KICJleHAiOjEzMDA4MTkzODAsDQogImh0dHA6Ly9leGFtcGxlLmNvbS9pc19yb290Ijp0cnVlfQ
assinatura dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
confere com o RFC: True
```

Repare: o exemplo do RFC tem um `\r\n` e um espaço dentro do header, e o RFC lista os bytes um por um. A bancada copia essa lista em vez de chamar o `json.dumps`, que geraria outra coisa:

```console
$ python3 -c "import json; print(json.dumps({'typ':'JWT','alg':'HS256'}))"
{"typ": "JWT", "alg": "HS256"}
```

Espaço depois de `:` e de `,`, e nada de `\r\n`. (Compacto, sem espaço nenhum, ele só sai com `separators=(",", ":")`, que é o que o `para_json` da bancada usa para o crachá do FairFare.) Parece o mesmo JSON. Para a assinatura, não é: um byte a mais ou a menos muda o resultado inteiro.

Com o RFC conferido, o ato 2 emite um crachá do FairFare de mentira, válido por uma hora:

```console
== 2. Emitir um crachá do FairFare de mentira ==
AVISO: JWT_SEGREDO não definida; usando o padrão da bancada, que está no código
token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwibm9tZSI6IkFuYSIsImV4cCI6MTc5MjkwMTg2Mn0.ru6SkTFOa8rC6LNedzk0sXie3a2TmSnC4wVVU9WXtcs
header     eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9
payload    eyJzdWIiOiIxIiwibm9tZSI6IkFuYSIsImV4cCI6MTc5MjkwMTg2Mn0
assinatura ru6SkTFOa8rC6LNedzk0sXie3a2TmSnC4wVVU9WXtcs
verificar: aceitou {'sub': '1', 'nome': 'Ana', 'exp': 1792901862}
```

O seu vai ter outro `exp` e outra assinatura: o relógio andou. O header vai ser igual. O aviso volta mais abaixo.

## Assinado não é secreto

O ato 3 lê o crachá sem segredo nenhum:

```console
== 3. Ler sem o segredo ==
header:  {"alg":"HS256","typ":"JWT"}
payload: {"sub":"1","nome":"Ana","exp":1792901862}
Nenhuma chave foi usada. Assinado não é secreto.
```

Nem precisa de Python. O `base64` do terminal faz isso, desde que você devolva o `=` que o JWT tirou (e, se aparecer `-` ou `_`, troque por `+` e `/`):

```console
$ echo 'eyJzdWIiOiIxIiwibm9tZSI6IkFuYSIsImV4cCI6MTc5MjkwMTg2Mn0' | base64 -d
{"sub":"1","nome":"Ana","exp":1792901862}base64: invalid input
$ echo 'eyJzdWIiOiIxIiwibm9tZSI6IkFuYSIsImV4cCI6MTc5MjkwMTg2Mn0=' | base64 -d
{"sub":"1","nome":"Ana","exp":1792901862}
```

Base64 não é criptografia. É só outra forma de escrever os mesmos bytes. A assinatura garante que ninguém **mudou** o payload. Ela não impede ninguém de **ler**. Quem pegar o token no log de um proxy, na aba de rede do navegador ou num print, lê tudo.

A regra: nada sensível no payload. Id de usuário, sim. Email, talvez. CPF, saldo, senha, nunca.

## A assinatura segura

O ato 4 tenta o óbvio. Pega o payload, troca o `"sub": "1"` por `"2"`, codifica de novo e cola a assinatura antiga:

```console
== 4. Adulterar o payload ==
payload trocado: {"sub":"2","nome":"Ana","exp":1792901862} (a assinatura é a mesma de antes)
verificar: recusou (assinatura não confere)
```

A assinatura foi calculada sobre `header.payload` como estavam. O verificador refaz o HMAC sobre o que chegou, com a chave dele, e o resultado é outro. Para fazer uma assinatura que bata com o payload novo, o atacante precisaria da chave.

O `verificar` inteiro:

```python
def verificar(token: str, segredo: bytes) -> dict:
    header, payload, assinatura, entrada = partes(token)
    # O verificador decide o algoritmo. O token não opina: o alg dele só pode confirmar.
    if header.get("alg") != "HS256":
        raise TokenInvalido(f"alg {header.get('alg')!r} recusado: aqui só entra HS256")
    esperada = hs256(entrada, segredo)
    # Comparação em tempo constante (lição 06), sobre bytes: com str, ela só aceita ASCII.
    # Ela não esconde o comprimento, e nem precisa: a assinatura HS256 sempre tem 32 bytes.
    if not hmac.compare_digest(esperada, assinatura):
        raise TokenInvalido("assinatura não confere")
    # Sem exp, o crachá valeria para sempre. Aqui, sem exp não entra.
    exp = payload.get("exp")
    if not isinstance(exp, int | float):
        raise TokenInvalido("sem exp")
    if exp <= time.time():
        raise TokenInvalido("vencido")
    return payload
```

O `partes` quebra o token nos pontos e decodifica cada pedaço (está no script). Repare na terceira checagem.

Lembra do `compare_digest` da lição 06? É aqui. O FairFare nunca compara segredo em Python. Este verificador compara: a assinatura que chegou contra a que ele calculou. Com `==`, cada byte certo no começo de um chute levaria um tiquinho a mais, e dá para montar a assinatura de um payload falso byte a byte, medindo. O `compare_digest` leva o mesmo tempo onde quer que as duas difiram.

Dois detalhes. A comparação é entre **bytes**: o `compare_digest` também aceita `str`, mas só se for ASCII, e com bytes a dúvida nem aparece. E ele **não esconde o comprimento**: com entradas de tamanhos diferentes, o tempo pode entregar o tamanho da certa. Aqui isso não vaza nada, porque a assinatura HS256 sempre tem 32 bytes, e qualquer um sabe disso.

## O buraco histórico: `alg: none`

Olhe a primeira checagem de novo. Por que conferir o `alg`, se o token é sempre HS256?

Porque o padrão prevê outros. Inclusive um chamado `none` (RFC 7518, seção 3.6): um JWT sem assinatura, para quando a integridade já está garantida por outro meio. Um verificador que lê o `alg` do header e obedece fica assim:

```python
def verificar_ingenua(token: str, segredo: bytes) -> dict:
    # NÃO faça isto. É o buraco histórico: o algoritmo vem do próprio token.
    header, payload, assinatura, entrada = partes(token)
    if header.get("alg") == "none":
        return payload  # "sem algoritmo, nada para conferir"
    if not hmac.compare_digest(hs256(entrada, segredo), assinatura):
        raise TokenInvalido("assinatura não confere")
    return payload
```

O ato 5 forja um token: header `{"alg":"none"}`, o payload adulterado do ato 4 e a assinatura vazia (o token termina no ponto). Sem segredo nenhum.

```console
== 5. O alg "none" ==
token forjado, sem segredo nenhum: eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIyIiwibm9tZSI6IkFuYSIsImV4cCI6MTc5MjkwMTg2Mn0.
verificar_ingenua: aceitou {'sub': '2', 'nome': 'Ana', 'exp': 1792901862}
verificar        : recusou (alg 'none' recusado: aqui só entra HS256)
```

A ingênua aceitou o usuário 2. Qualquer pessoa vira qualquer pessoa.

Isso não é invenção de bancada. Em 2015, o pesquisador Tim McLean mostrou, no texto "Critical vulnerabilities in JSON Web Token libraries", que várias bibliotecas de JWT populares aceitavam tokens com `alg: none`. Elas escolhiam o algoritmo pelo header e, com `none`, não tinham o que conferir. A `verificar_ingenua` é uma versão encolhida desse defeito, mas o mecanismo é o mesmo: o token dizia como devia ser conferido, e o verificador acreditava.

A regra: **o verificador decide o algoritmo, nunca o token.** O `alg` do header pode, no máximo, confirmar o que o servidor já esperava. Nas bibliotecas de hoje, quem confere passa a lista de algoritmos aceitos, e em várias delas a lista é obrigatória. Quem passa a lista errada reabre o buraco.

## Onde mora o segredo

O ato 2 avisou: `JWT_SEGREDO não definida; usando o padrão da bancada, que está no código`. O segredo vem de uma **variável de ambiente**, uma configuração que o sistema operacional entrega ao processo na hora de rodar, fora do código:

```console
$ JWT_SEGREDO=outro-segredo uv run python chapters/06-autenticacao-e-seguranca/bancada/jwt_na_mao.py
...
== 2. Emitir um crachá do FairFare de mentira ==
segredo: lido de JWT_SEGREDO
token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwibm9tZSI6IkFuYSIsImV4cCI6MTc5MjkwMTg2Mn0.jeAlvRIs4IkXbX0W-N6n9gsF726q297JiJYGecyEi2o
```

Mesmo payload, outra assinatura.

Por que tanto cuidado? Porque com HS256 **quem tem o segredo emite crachá de qualquer um.** O mesmo segredo assina e confere. Vazou, o atacante não precisa de `alg: none`: ele assina `{"sub": "1"}` e entra como a Ana. Segredo no código vai parar no repositório, e o histórico do git guarda para sempre, mesmo depois de apagado. O `segredo-de-bancada` existe só para a bancada rodar de primeira. Este repositório é público: esse segredo é de todo mundo.

Lá na lição 11 do capítulo 2 ficou a promessa de discutir "onde guardar segredo". A resposta é esta: fora do código, entregue pelo ambiente. Como fazer isso num deploy de verdade, sem o segredo aparecer em lugar nenhum, é o capítulo 11.

E o FairFare? **O app não tem chave de assinatura nenhuma.** O token opaco é acaso puro, e o banco só guarda o sha256 dele (lição 04). Não há chave que, vazada, deixe alguém fabricar uma sessão. Quem ler todo o código do FairFare não ganha crachá nenhum. Ganha a senha do banco, que está no `app/database.py`, mas essa é outra limitação, declarada na lição 12 do capítulo 4, e morre no capítulo 11. Quem ler a tabela `sessions` também não ganha crachá. Essa é uma das vantagens que a lição 09 põe na balança.

## O logout que não desloga

O ato 6 faz o logout de um app com JWT. O cliente apaga o token. Mas alguém tinha uma cópia: num log, num proxy, num notebook roubado.

```console
== 6. O logout que não desloga ==
o cliente apagou o token: {}
verificar a cópia: aceitou {'sub': '1', 'nome': 'Ana', 'exp': 1792901862}
e ela continua passando até o exp, 3600 s depois da emissão
verificar um token com exp no passado: recusou (vencido)
```

O `verificar` não consulta lista nenhuma, então não há linha para apagar. A cópia vale até o `exp`. Só o tempo a derruba.

Na lição 07, o logout foi um `DELETE` e o token morreu na hora. Aqui, a mesma coisa que torna o JWT rápido (ninguém pergunta ao banco) torna o logout impossível do jeito simples. Quem revoga um JWT, então? É a pergunta da lição 09.

## O que fica declarado

- **O app não muda.** O FairFare continua com o token opaco da lição 04. O JWT vive só na bancada.
- **A bancada é de brinquedo.** Ela só faz HS256 e só confere `alg`, assinatura e `exp`. Não confere `iat`, `nbf`, `iss` nem `aud`, outros campos que o padrão prevê. Não faz algoritmos de chave pública, como o RS256. Num app de verdade, quem monta e confere JWT é uma biblioteca mantida e auditada.
- **A `verificar_ingenua` está errada de propósito.** Ela existe só para o ato 5 mostrar o buraco.

## O que você deve conseguir fazer agora

- Decodificar o payload de um JWT à mão, com `base64 -d` ou com três linhas de Python, e explicar por que isso não precisa de chave nenhuma.
- Explicar por que trocar um caractere do payload faz o `verificar` recusar, e o que o atacante precisaria ter para assinar o payload novo.
- Explicar o ataque do `alg: none`: o que o token forjado leva, por que o verificador ingênuo aceita, e qual regra fecha o buraco.
