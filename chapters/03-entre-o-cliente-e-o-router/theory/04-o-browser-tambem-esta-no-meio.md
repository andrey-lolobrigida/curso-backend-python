# Lição 04 — O browser também está no meio

A lição 03 terminou prometendo duas camadas no FairFare. Esta é a primeira.

Mas ninguém adiciona middleware por esporte. Antes da camada, o problema — e o problema aparece no segundo em que o cliente do FairFare deixa de ser o `curl`.

## A cena

Três coisas rodando. O FairFare, na porta 8000:

```bash
uv run uvicorn app.main:app --port 8000
```

Uma página estática, na 8080:

```bash
python3 -m http.server 8080 --directory chapters/03-entre-o-cliente-e-o-router/bancada/pagina
```

Esse `http.server` é velho conhecido. No capítulo 0, o mini-servidor com que você conversou por HTTP era um `BaseHTTPRequestHandler` importado dele. O módulo também vem com um servidor de arquivos estáticos pronto, e é ele que você acabou de subir: uma linha, zero código. (É `python3` seco, sem `uv run`, de propósito: é a biblioteca padrão, e o venv do projeto não tem nada a ver com ela.)

E a página, `bancada/pagina/index.html`. O miolo dela é isto:

```js
const API = "http://localhost:8000";

async function listar() {
  const resposta = await fetch(`${API}/users`);
  const usuarios = await resposta.json();
  // ...preenche a <ul>
}
```

Nada de exótico. É a mesma request que você faz com `curl` desde o capítulo 1.

> **Um aviso antes de rodar.** Na branch inteira do capítulo essa constante já está como `const API = "/api"` —
> a lição 07 aponta a página para o proxy reverso. Se você fez `git checkout v-cap03-licao04`, ela está certa
> e só falta o passo do middleware, logo abaixo. Se está no fim da branch, troque a constante de volta para `"http://localhost:8000"`
> em `bancada/pagina/index.html`. Sem isso o `fetch` toma 404 do `http.server` em vez de esbarrar no CORS.

Mais um passo antes de abrir. O `app/main.py` que você tem já traz o conserto que esta lição vai escrever — ele é o commit dela. Para ver o problema antes da solução, comente o bloco do `app.add_middleware(CORSMiddleware, ...)` no `app/main.py` e reinicie o FairFare. Na seção "O commit", lá embaixo, você descomenta.

Abra `http://localhost:8080` com o console aberto. A lista vem **vazia**. E o console tem isto:

No Chrome:

```
Access to fetch at 'http://localhost:8000/users' from origin 'http://localhost:8080' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

No Firefox:

```
Cross-Origin Request Blocked: The Same Origin Policy disallows reading the remote resource at http://localhost:8000/users. (Reason: CORS header ‘Access-Control-Allow-Origin’ missing). Status code: 200.
```

*(Os dois textos foram capturados de verdade, num Chromium e num Firefox headless. As mensagens que você vai ver são estas.)*

Agora olhe o **outro** terminal, o do uvicorn:

```
INFO:     127.0.0.1:54820 - "GET /users HTTP/1.1" 200 OK
```

Leia as duas telas juntas. O Firefox chega a dizer o status na cara dura: `Status code: 200.`

A request saiu, chegou, foi roteada, abriu sessão no banco, montou o JSON e voltou `200 OK`. **O servidor respondeu. Quem escondeu foi o browser.**

Essa frase é a lição inteira. O resto é detalhe.

## O que aconteceu, em ordem

Primeiro o vocabulário, porque tudo depende dele. Uma **origem** é a tripla `esquema + host + porta`. `http://localhost:8080` e `http://localhost:8000` têm o mesmo esquema e o mesmo host — e portas diferentes. São origens **diferentes**. Mesma máquina, mesmo `localhost`, e mesmo assim: porta diferente basta.

Com isso, a sequência:

1. O JavaScript da página chamou `fetch` para outra origem. O browser mandou a request e acrescentou, sozinho, o header `Origin: http://localhost:8080`. Ele carimba; o seu JS não tem como tirar nem mentir.
2. O FairFare respondeu `200` com o JSON. Sem nenhum header falando de origem.
3. O browser olhou a resposta, não achou um `Access-Control-Allow-Origin` autorizando `http://localhost:8080`, e **não entregou ao JavaScript**. A promise do `fetch` rejeitou com `TypeError: Failed to fetch`. O corpo estava ali, na memória do browser, e foi jogado fora.

Por que essa regra existe? Ela se chama **same-origin policy**, e o motivo é o seguinte. Você está logado no seu banco numa aba; o cookie de sessão está no browser. Em outra aba você abre um site qualquer, e o JavaScript dele faz `fetch("https://banco.example/saldo")` — o browser manda o seu cookie junto, porque o cookie é do domínio do banco e a request é para o banco. Se o JS daquele site pudesse **ler** a resposta, um link mal clicado bastaria para o seu saldo vazar. (Os browsers de hoje atenuam esse cenário específico com o atributo `SameSite` dos cookies, mas a regra nasceu daí e continua valendo para tudo o mais.)

A same-origin policy é o que impede isso: mandar, tudo bem; **ler**, só com permissão.

E é aqui que o nome aparece. **CORS** — *Cross-Origin Resource Sharing* — é o conjunto de headers com que o servidor concede essa permissão. Note a inversão: CORS não é a restrição. CORS é a maneira de **afrouxar** a restrição, caso a caso, para as origens que você escolher.

## O `curl` nunca reclamou

Você bate nesse mesmo endpoint desde o capítulo 1 e nunca viu esse erro. Nem os seus testes. Por quê?

Antes de mexer no app, com o header `Origin` na mão:

```console
$ curl -s -i -H "Origin: http://localhost:8080" localhost:8000/users
HTTP/1.1 200 OK
server: uvicorn
content-length: 49
content-type: application/json

[{"id":1,"nome":"Ana","email":"ana@exemplo.com"}]
```

Duzentos, com o corpo. O `curl` recebeu tudo. Ele leu o mesmo que o browser leu — e, ao contrário do browser, entregou.

Porque **CORS é uma regra do cliente, não do servidor**. O servidor apenas anuncia o que permite. Quem obedece é quem quiser obedecer, e só os browsers obedecem.

Guarde isto, porque é o mal-entendido mais comum do assunto: **CORS não protege a sua API. Ele protege o usuário do browser.** Um script em Python, um `curl` num terminal, um backend chamando o seu backend, o Postman — nenhum deles jamais viu um erro de CORS na vida. Se a sua API precisa decidir *quem* pode fazer *o quê*, isso é autenticação e autorização (capítulo 6). Se precisa segurar volume, é rate limiting (lição 05). CORS não é nenhum dos dois.

## O preflight

Agora o formulário da página. Ele faz um `POST` com JSON no corpo:

```js
const resposta = await fetch(`${API}/users`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(dados),
});
```

Clique em "Criar" e olhe o log do servidor:

```
INFO:     127.0.0.1:54820 - "OPTIONS /users HTTP/1.1" 405 Method Not Allowed
```

`OPTIONS`? Ninguém escreveu `OPTIONS` em lugar nenhum. E o `POST` não aparece no log — ele nunca aconteceu.

Isso é o **preflight**. Para requests que podem ter efeito colateral, o browser não arrisca mandar primeiro e perguntar depois. Ele pergunta antes, com um `OPTIONS` de reconhecimento:

```console
$ curl -s -i -X OPTIONS \
    -H "Origin: http://localhost:8080" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: content-type" \
    localhost:8000/users
HTTP/1.1 405 Method Not Allowed
allow: POST
content-type: application/json

{"detail":"Method Not Allowed"}
```

"Eu pretendo mandar um `POST` com um header `content-type`. Pode?" O FastAPI não tem rota `OPTIONS` em `/users`, então respondeu o que responderia a qualquer método desconhecido: `405`, com um `allow: POST` educado que o browser nem lê. Sem um `sim` explícito, o browser cancelou o `POST`. Nada foi criado.

O Firefox conta a história toda na mensagem — repare no status:

```
Cross-Origin Request Blocked: The Same Origin Policy disallows reading the remote resource at http://localhost:8000/users. (Reason: CORS header ‘Access-Control-Allow-Origin’ missing). Status code: 405.
```

E o Chrome diz de onde veio o problema:

```
Access to fetch at 'http://localhost:8000/users' from origin 'http://localhost:8080' has been blocked by CORS policy: Response to preflight request doesn't pass access control check: No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

O que dispara um preflight, na prática: um método fora de `GET`/`HEAD`/`POST`; ou um `Content-Type` que não seja um dos três de formulário (`application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain`); ou qualquer header customizado — `Authorization` incluído.

Repare no que sobrou de fora dessa lista: `application/json`. Ou seja, **praticamente toda API JSON leva preflight**. Não é caso raro; é o caso normal.

## O commit

Uma linha de configuração resolve os dois problemas. Em `app/main.py`:

```diff
 from fastapi import FastAPI
+from fastapi.middleware.cors import CORSMiddleware

 from app.routers import bookings, resources, users

 app = FastAPI(title="FairFare")

+# A página da bancada mora em http://localhost:8080. Origem explícita: nada de "*".
+# Content-Type já é permitido por padrão; quando a API pedir Authorization (cap. 6),
+# ele entra em allow_headers.
+app.add_middleware(
+    CORSMiddleware,
+    allow_origins=["http://localhost:8080"],
+    allow_methods=["GET", "POST", "DELETE"],
+)
+
 app.include_router(users.router)
```

Descomente o bloco que você comentou lá na cena, reinicie e refaça o preflight na mão:

```console
$ curl -s -i -X OPTIONS -H "Origin: http://localhost:8080" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: content-type" \
    localhost:8000/users
HTTP/1.1 200 OK
vary: Origin
access-control-allow-methods: GET, POST, DELETE
access-control-max-age: 600
access-control-allow-headers: Accept, Accept-Language, Content-Language, Content-Type
access-control-allow-origin: http://localhost:8080
```

Três coisas para ler aí:

- Nenhuma rota `OPTIONS` foi criada. O `CORSMiddleware` é ASGI puro e, no preflight, **responde sozinho** — ele nem chama o app de dentro. Lembra a regra da lição 03? *Se você só quer olhar, o fácil serve; se precisa controlar, ASGI puro.* Responder no lugar do app é controlar. O seu router nunca soube que esse `OPTIONS` existiu.
- O `access-control-allow-headers` lista `Content-Type` sem a gente ter pedido: o Starlette já permite os headers da lista segura por padrão. Por isso não há `allow_headers` na configuração. Quando o capítulo 6 trouxer `Authorization`, aí sim.
- O `access-control-max-age: 600` diz ao browser para guardar essa resposta por dez minutos. O preflight não se repete a cada `POST`.

E a página, recarregada: a lista aparece, o formulário cria usuário. No log:

```
INFO:     127.0.0.1:59306 - "OPTIONS /users HTTP/1.1" 200 OK
INFO:     127.0.0.1:59306 - "POST /users HTTP/1.1" 201 Created
INFO:     127.0.0.1:59306 - "GET /users HTTP/1.1" 200 OK
```

O commit traz também `tests/test_cors.py`, com quatro testes. Cada um é uma frase desta lição virada em asserção.

**O preflight é respondido** — o `405` virou `200`, e ele diz o que pode:

```python
async def test_preflight_de_origem_permitida_e_respondido(client):
    resp = await client.options(
        "/users",
        headers={
            "Origin": ORIGEM_PERMITIDA,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA
    assert "POST" in resp.headers["access-control-allow-methods"]
```

**A request simples ganha o carimbo** — o que faltava lá no começo:

```python
async def test_request_simples_de_origem_permitida_ganha_o_header(client):
    resp = await client.get("/users", headers={"Origin": ORIGEM_PERMITIDA})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA
```

**Origem desconhecida não ganha nada** — e olhe bem a primeira asserção:

```python
async def test_origem_desconhecida_nao_ganha_header_nenhum(client):
    resp = await client.get("/users", headers={"Origin": "http://malandro.example"})
    assert resp.status_code == 200  # o servidor responde normalmente...
    assert "access-control-allow-origin" not in resp.headers  # ...e o browser vai esconder
```

O app **responde 200 com o corpo inteiro** para o malandro. Não é bug, é a mecânica: o servidor não recusa ninguém por causa de CORS, ele só deixa de carimbar. Quem esconde é o browser da vítima. (Se você quer *recusar*, é outra camada: a lição 05, para volume, ou o capítulo 6, para identidade.)

**Sem `Origin`, nada muda** — o `curl` de sempre continua o `curl` de sempre:

```python
async def test_sem_origin_passa_intacta(client):
    resp = await client.get("/users")
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers
```

## Por que não `*`

Você vai encontrar `allow_origins=["*"]` em muito tutorial. Traduzido para português: *qualquer site do mundo pode ler a minha API usando o browser do meu usuário, com o que quer que ele tenha ali dentro.*

Para uma API pública e anônima, tudo bem. Para uma API que um dia terá login — a nossa, no capítulo 6 —, não.

E tem uma armadilha específica aí, que vale conhecer antes de cair nela. O browser **recusa** um `Access-Control-Allow-Origin: *` quando a request leva credenciais (cookie, `Authorization`). Então a pessoa tenta `allow_origins=["*"]` com `allow_credentials=True`, e funciona — porque o Starlette, nessa combinação, para de mandar `*` e passa a **ecoar o `Origin` que chegou**. Leia de novo: o resultado é uma API que autoriza, com credenciais, qualquer origem que peça. O `*` que o browser bloquearia virou um `*` que funciona.

Não é o Starlette sendo malicioso. A spec proíbe `*` com credenciais, e ecoar a origem é a única forma de o seu `*` "funcionar" — ele faz o que você pediu, ao pé da letra. É exatamente por isso que a combinação parece resolvida quando não está.

Origem explícita, na lista, sempre. É uma linha a mais por ambiente e um problema a menos por incidente.

## O gancho

Repare no que a gente acabou de fazer. Havia um arranjo — página numa porta, API em outra — e a gente configurou o servidor para conviver com ele.

A lição 07 vira o jogo: um proxy reverso na frente dos dois, tudo servido pela **mesma** origem, e o browser não tem sobre o que reclamar. A melhor configuração de CORS é a que você não precisa ter.

Isso não apaga esta lição. Um app mobile, um frontend de terceiros, um domínio separado de propósito — todos trazem o problema de volta, e aí você configura sabendo o que está configurando. O que muda é que deixa de ser reflexo.

## O que você deve conseguir fazer agora

- Ler um erro de CORS no console e dizer exatamente qual header faltou na resposta.
- Explicar por que o `curl` nunca vê esse problema — e por que isso significa que CORS não protege a sua API.
- Dizer o que é uma origem, e por que `localhost:8000` e `localhost:8080` são duas.
- Dizer o que dispara um preflight, e por que quase toda API JSON tem um.
- Explicar por que o app responde `200` para uma origem desconhecida em vez de recusar.
- Dizer por que `allow_origins=["*"]` é uma má ideia numa API com login.
