# Lição 10 — O certificado: quem garante que é você

A lição 09 subiu um servidor com TLS e contou o handshake — mas passou correndo por duas coisas: o `certificado.py` que montou o palco, e o `--cacert` sem o qual o `curl` se recusava a falar. As duas são a mesma pergunta: **quem garante que este servidor é quem diz ser?**

Deixe o FairFare da 8443 de pé, do jeito que a lição 09 subiu. Vamos precisar dele. Na aba dos `curl`, defina o mesmo atalho da aba do servidor:

```bash
B=chapters/03-entre-o-cliente-e-o-router/bancada
```

## O certificado

Um certificado é um arquivo que diz: *esta chave pública pertence a estes nomes, e quem garante sou eu*. Quem garante é a **autoridade certificadora** (*CA*, de *Certificate Authority*) — uma organização em cuja assinatura o seu sistema operacional e o seu browser já foram ensinados a confiar. Ela assina o certificado do servidor; o browser confere a assinatura; a corrente que liga um ao outro é a **cadeia de confiança**.

O da bancada é o que o `certificado.py` gerou na lição 09, com a biblioteca `cryptography` — a única dependência nova deste capítulo. Ela já está no `pyproject.toml` (senão o script nem teria rodado); entrou assim:

```bash
uv add --dev cryptography
```

O `--dev` não é detalhe. Ela entra no **grupo de desenvolvimento** porque só a bancada usa: nenhuma linha do FairFare importa `cryptography`, e servidor de produção não gera o próprio certificado. O grupo dev fica de fora da instalação de produção (`uv sync --no-dev`).

`chapters/03-entre-o-cliente-e-o-router/bancada/certificado.py`:

```python
DESTINO = Path(__file__).with_name("certs")
VALIDADE = dt.timedelta(days=30)


def main() -> None:
    DESTINO.mkdir(exist_ok=True)

    # 1. A chave: um par (privada + pública). A privada nunca sai desta máquina.
    chave = ec.generate_private_key(ec.SECP256R1())

    # 2. O certificado: a chave pública + para quem ela vale + quem assina. Aqui, nós mesmos.
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    agora = dt.datetime.now(dt.timezone.utc)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(nome)  # para quem é
        .issuer_name(nome)  # quem assina — o mesmo: "autoassinado"
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora)
        .not_valid_after(agora + VALIDADE)
        .add_extension(
            # Os nomes pelos quais o cliente pode chamar este servidor. É isto que o browser confere.
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(chave, hashes.SHA256())
    )
```

*(O arquivo completo tem também a escrita dos dois `.pem`; o miolo é este.)*

Campo a campo, porque cada um responde uma pergunta:

- **A chave.** `ec.generate_private_key` cria um par. A **pública** vai dentro do certificado, à vista de todos. A **privada** fica no `chave.pem` e é a única prova de que este servidor é o dono dele. Quem tem a chave privada *é* o servidor.
- **`subject_name`** — para quem o certificado vale.
- **`issuer_name`** — quem assinou. Aqui é o mesmo nome, e é literalmente o que **autoassinado** significa: eu assinei o meu próprio documento.
- **`not_valid_before` / `not_valid_after`** — certificado tem prazo. Trinta dias aqui; na vida real, meses.
- **`SubjectAlternativeName` (SAN)** — a lista de nomes pelos quais o cliente pode chamar este servidor. É este campo que o cliente compara com o que você digitou na barra de endereço.

Esse último merece uma demonstração, porque é a armadilha mais comum. Abra o `certificado.py`, ache a lista da SAN e tire dela o `x509.IPAddress(ipaddress.ip_address("127.0.0.1"))` — deixe só o `x509.DNSName("localhost")`. Rode o script de novo. E aqui está o detalhe que morde: **o uvicorn lê os dois `.pem` uma vez, na subida.** Regenerar o arquivo não muda o que o servidor da 8443 está apresentando. Mate-o e suba de novo, com o mesmo comando. Só então chame o mesmo endereço pelos dois nomes:

```console
$ curl -sS --cacert $B/certs/cert.pem -o /dev/null -w '%{http_code}\n' https://localhost:8443/users
200
$ curl -sS --cacert $B/certs/cert.pem https://127.0.0.1:8443/users
curl: (60) SSL: no alternative certificate subject name matches target host name '127.0.0.1'
…
```

Mesma máquina, mesmo servidor, mesmo certificado confiado explicitamente — e mesmo assim `60`. O nome não bate, então a identidade não foi provada. É por isso que o `certificado.py` põe `localhost` **e** `127.0.0.1` na SAN.

Desfaça a edição, rode o script mais uma vez (ele sobrescreve o anterior, e avisa disso na última linha) — e **mate e suba o servidor de novo**, pelo mesmo motivo. Se esquecer, o `curl` reclama de `self-signed certificate` nos dois nomes: o arquivo em que você mandou confiar já não é o que o servidor mostra.

O `openssl` lê o resultado e confirma (recorte; a saída é bem maior):

```console
$ openssl x509 -in $B/certs/cert.pem -noout -text
        Issuer: CN = localhost
        Validity
            Not Before: Sep  7 16:41:37 2026 GMT
            Not After : Oct  7 16:41:37 2026 GMT
        Subject: CN = localhost
        X509v3 extensions:
            X509v3 Subject Alternative Name:
                DNS:localhost, IP Address:127.0.0.1
```

**Autoassinado não é xingamento — é uma descrição.** O certificado é criptograficamente perfeito: a chave é boa, a assinatura confere, e contra quem apenas **escuta** o fio o sigilo funciona igual ao de um certificado caríssimo. O que falta não é qualidade, é **cadeia**: nenhuma autoridade conhecida garante por ele.

Aqui está a parte que quase todo mundo erra; leia devagar: **a cadeia é justamente o que protegeria o sigilo contra quem consegue entrar no meio.** Um atacante nessa posição não precisa quebrar criptografia nenhuma — ele apresenta o certificado autoassinado *dele*, e um cliente que aceita certificado sem cadeia aceita o dele com o mesmo entusiasmo. A conexão fica cifrada, sim: **com o atacante**. É por isso que "autoassinado ainda é criptografado, então tá tudo bem" é a conclusão errada desta lição inteira — sigilo sem identidade não é sigilo com quem você queria.

E a pasta onde ele nasce entrou no `.gitignore`:

```
# certificado de desenvolvimento do cap. 3 (chave privada — nunca commitar)
chapters/03-entre-o-cliente-e-o-router/bancada/certs/
```

O motivo cabe numa frase: **chave privada em repositório é chave pública.** Basta um `git push` e ela está na internet — e o histórico do git guarda uma cópia mesmo que você a apague depois. Gere a sua rodando o script; ninguém mais precisa dela.

## Subindo com TLS

O comando da lição 09 já era a coisa inteira: o uvicorn recebe os dois arquivos e avisa na primeira linha de log:

```console
INFO:     Uvicorn running on https://127.0.0.1:8443 (Press CTRL+C to quit)
```

Repare no `https://`. Agora bata nele com o `curl` — sem o `--cacert`, desta vez:

```console
$ curl -sS https://localhost:8443/users
curl: (60) SSL certificate problem: self-signed certificate
…
```

Código de saída **60** (o `…` são linhas de ajuda). E no browser, abrindo `https://localhost:8443/`:

```
Your connection is not private
…
NET::ERR_CERT_AUTHORITY_INVALID
```

Clicando em **Advanced**, ele explica melhor:

```
This server could not prove that it is localhost; its security certificate is
not trusted by your computer's operating system. This may be caused by a
misconfiguration or an attacker intercepting your connection.

Proceed to localhost (unsafe)
```

*(Capturado no Chromium via Playwright (a ferramenta que dirige um browser por script) headless, em inglês; em português vem traduzido, com o mesmo código. O Firefox usa outro código para a mesma queixa: `MOZILLA_PKIX_ERROR_SELF_SIGNED_CERT`.)*

Leia de novo, porque é o certo: **"não consegui provar"**, não "está quebrado". `AUTHORITY_INVALID` é falta de autoridade, não defeito de certificado. O browser está fazendo o trabalho dele.

Existem dois jeitos de seguir em frente. Os dois devolvem `200`, e **não** são equivalentes:

```console
$ curl -s -k -o /dev/null -w '%{http_code}\n' https://localhost:8443/users
200
$ curl -s --cacert $B/certs/cert.pem -o /dev/null -w '%{http_code}\n' https://localhost:8443/users
200
```

O `-k` desliga a verificação: aceita **qualquer** certificado, até o de um atacante. O `--cacert` diz outra coisa — *"trate este arquivo como uma autoridade em que eu confio"*. A cadeia volta a existir, com você como a autoridade, e a verificação continua ligada: se o certificado mudar, o `curl` reclama de novo. É a forma honesta de aceitar um certificado de desenvolvimento. No browser, o equivalente é instalar o certificado entre os confiáveis do sistema — não o botão "Proceed".

Em produção você não faz nada disso: uma CA pública emite o certificado — a **Let's Encrypt** faz isso de graça, e o Caddy da lição 07 pede e renova sozinho quando o endereço do site é um **nome público**, alcançável de fora. Com `localhost:8080`, como no `Caddyfile` da bancada, a documentação dele diz que ele gera uma CA local e tenta instalá-la entre os confiáveis da sua máquina — o `--cacert`, automatizado.

## Quem termina o TLS é o proxy

Volte ao mapa da lição 06. Se cada app cuidasse do próprio certificado, seriam N lugares para renovar. A prática de produção é **terminar o TLS na borda**: o proxy fala TLS com o mundo, decifra, e conversa em HTTP simples com o app — que está na mesma máquina, ou numa rede interna.

Mate os servidores de antes — a 8000 e a 8443 vão ser reocupadas. Espelho da lição 08 na 8000, proxy com TLS na 8443, cada um na sua aba, com o `B` definido nas duas:

```bash
uv run uvicorn eco:app --port 8000 --app-dir $B
uv run uvicorn proxy:app --port 8443 --no-proxy-headers \
    --ssl-keyfile $B/certs/chave.pem --ssl-certfile $B/certs/cert.pem --app-dir $B
```

```console
$ curl -s --cacert $B/certs/cert.pem https://localhost:8443/api/
{
  "cliente": [
    "127.0.0.1",
    0
  ],
  "esquema": "https",
  "path": "/",
  "x-forwarded-for": "127.0.0.1",
  "x-forwarded-proto": "https"
}
```

Olhe o `"esquema": "https"`. O `eco.py` recebeu **texto puro** — o proxy falou HTTP simples com ele, sem TLS nenhum. Mesmo assim o `scope["scheme"]` dele diz `https`.

A corrente inteira é a lição 08 pagando: o `proxy.py` escreve `x-forwarded-proto` com `request.url.scheme`, que agora é `https` porque foi por aí que a request chegou nele; o uvicorn do espelho vê uma conexão vinda de `127.0.0.1`, que é confiável por padrão, lê o header e **troca o `scheme` do `scope`** antes do app rodar. É assim que uma aplicação atrás de um proxy descobre que o mundo lá fora é `https` — e é por isso que a lição 08 veio antes desta. O app **acredita** no proxy. Então o proxy precisa ser digno disso.

## O que fica declarado

- **Este certificado não vale nada fora da sua máquina.** Autoassinado, de trinta dias, para `localhost` e `127.0.0.1`: serve para ver TLS funcionando, e só. Certificado de verdade, emitido e renovado por uma CA, é capítulo 11.
- **O `-k` continua existindo e continua sendo perigoso.** Num script que fala com um serviço real, `-k` desliga justamente a parte do TLS que te protege de um atacante no meio.
- **A bancada não mediu o custo do handshake em milissegundos.** A lição 09 mediu a **estrutura** dos dois handshakes, com o `curl -v`. Em loopback a diferença de tempo some no ruído. A conta que importa é a da lição 02: uma ida e volta na internet custa ~5,9 ms, e agora são duas ou três antes do primeiro byte.
- **Nada de Let's Encrypt, nem de Caddy, rodou aqui.** O que esta lição diz sobre HTTPS automático é leitura da documentação do Caddy: o `Caddyfile` da bancada segue lido e nunca executado. E HTTPS público exige o que a bancada não tem — domínio público e portas abertas para o mundo. Capítulo 11.
- **O `carga.py` e a `pagina/index.html` não falam TLS.** Os dois apontam para `http://`. A bancada continua em texto puro por padrão; o TLS é um arranjo extra, montado à mão.
- **Terminar TLS na borda deixa o trecho proxy→app em texto puro**, e isso é aceitável exatamente quando esse trecho é loopback ou rede interna confiável. Se ele atravessar uma rede que você não controla, o problema desta lição volta inteiro — só que dentro da sua infraestrutura.

## O que você deve conseguir fazer agora

- Explicar o aviso do browser sem usar a palavra "erro" — dizendo o que falta ao certificado, e por que `--cacert` é uma resposta melhor que `-k`.
- Dizer o que a SAN é, e o que acontece quando o nome chamado não está nela.
- Dizer por que a pasta `certs/` está no `.gitignore`.
- Explicar por que o espelho responde `"esquema": "https"` mesmo falando HTTP puro — e o que isso exige do proxy.
