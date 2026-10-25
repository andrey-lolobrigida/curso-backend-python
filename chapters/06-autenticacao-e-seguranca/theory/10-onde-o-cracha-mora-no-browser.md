# Lição 10 — Onde o crachá mora no browser

A lição 09 terminou com uma pergunta: no browser, onde o cliente guarda o crachá?

Com o `curl`, a pergunta nem existe: você cola o token no `-H "Authorization: Bearer ..."`, e só você mexe nele.

Uma página web recebe o token do `POST /auth/login` e precisa guardá-lo para a próxima request. E o lugar decide quais ataques funcionam contra ela. São duas casas possíveis.

## Casa 1: o cookie

Um **cookie** é um valor que o servidor pede ao browser para guardar, com o header `Set-Cookie`. Dali em diante, o browser o manda de volta **sozinho**, em toda request para aquele domínio.

A vantagem: o cookie pode ser marcado `HttpOnly`, e aí nenhum JavaScript consegue lê-lo, nem o da própria página.

O perigo nasce da mesma frase: o browser manda o cookie **sozinho**. Ele não pergunta quem pediu a request, só para onde ela vai.

Pense num carimbo automático. Toda carta endereçada ao banco sai do seu correio com a sua assinatura carimbada, não importa quem escreveu a carta. Se um estranho deixa uma carta no seu correio, endereçada ao banco, ela sai assinada por você.

Esse ataque tem nome: **CSRF**, *Cross-Site Request Forgery*, a falsificação de request entre sites. O mecanismo, passo a passo:

1. Você faz login no site A, que guarda a sessão num cookie.
2. Em outra aba, você abre o site B, de alguém mal-intencionado.
3. A página de B dispara uma request para A. O browser vê o destino, acha o cookie de A e manda junto, a menos que o próprio cookie proíba (o `SameSite`, mais abaixo).
4. A recebe uma request com um cookie válido e obedece. Para A, foi você quem pediu.

O jeito clássico de disparar é um formulário escondido. Um FairFare imaginário, que guardasse a sessão em cookie, aceitasse formulário e tirasse da sessão quem recebe (a regra que chega na lição 12), cairia numa página assim (pseudocódigo, não está no repositório):

```html
<!-- pseudocódigo: a página do site malandro, contra um FairFare imaginário -->
<form action="https://fairfare.example/groups/7/settlements" method="POST" style="display:none">
  <input name="de_user_id" value="42">  <!-- 42 é o malandro -->
  <input name="valor" value="500.00">
</form>
<script>document.forms[0].submit()</script>
```

Você nem vê o formulário. A página carrega, o formulário se envia, e o browser carimba o cookie. O FairFare imaginário registra, em seu nome, que você recebeu 500 reais do usuário 42. A dívida dele com você some, e você nunca clicou em nada.

Repare no que **não** salva você aqui: o CORS. Lembra a frase da lição 04 do capítulo 3? *Mandar, tudo bem; ler, só com permissão.* O CSRF mora inteiro no "mandar". O site B não precisa ler a resposta. O estrago é o efeito colateral, e ele já aconteceu quando a request chegou.

## Casa 2: o header `Authorization`

É a casa do FairFare desde a lição 05. O token vai no header `Authorization: Bearer ...`, e o browser **não** põe esse header sozinho. Ele só vai se o JavaScript da página puser, à mão, em cada `fetch`.

Isso mata o CSRF pela raiz. O formulário escondido do site B não tem como pôr header nenhum. E o JavaScript de B não tem o token: ele foi guardado pela página do FairFare, numa origem que não é a de B. A same-origin policy não deixa B ler o que é de outra origem.

O preço: para pôr o header à mão, o JavaScript precisa **alcançar** o token. Então ele mora numa variável em memória, no `sessionStorage` ou no `localStorage`. Todas ao alcance do JS da página.

E se o JS que alcança não for o da página?

Esse ataque também tem nome: **XSS**, *Cross-Site Scripting*. É quando alguém consegue fazer o browser rodar um script dele **dentro** da sua página. O caminho clássico: alguém batiza um grupo com um nome que é HTML com script embutido (`<img src=x onerror="...">`, por exemplo), e uma página descuidada põe esse nome no HTML sem escapar. O script roda com todos os direitos da página, inclusive o de ler o `localStorage`. Uma linha manda o token para o atacante.

Agora o atacante tem o crachá. Feche a aba, não importa: ele usa de qualquer lugar até o logout ou até a sessão vencer.

## Não existe casa perfeita

O XSS ganha das duas casas. Com `HttpOnly`, o script intruso não **lê** o cookie. Mas ele roda dentro da página, então dispara requests dali mesmo, e o browser carimba o cookie nelas. A diferença é que, com o cookie, o estrago fica preso à aba aberta: o script age pela sua sessão enquanto a aba estiver aberta, e só. Com o header, o token sai e viaja.

Cada casa pede uma defesa diferente:

| | Cookie | Header `Authorization` |
|---|---|---|
| **Quem manda o crachá** | O browser, sozinho, em toda request. | O JS da página, à mão, em cada `fetch`. |
| **O JS alcança o crachá?** | Não, com `HttpOnly`. | Sim. Precisa alcançar para pôr no header. |
| **CSRF** | É o risco. Defesa: `SameSite` e token anti-CSRF. | Não acontece. Outro site não tem o token. |
| **XSS** | O script não lê o cookie, mas age pela aba aberta. | O script lê o token e leva embora. |
| **Defesa contra o XSS** | Não ter XSS. | Não ter XSS. |

Duas defesas da coluna do cookie pedem explicação. O **`SameSite`** é um atributo que o dono do cookie põe no `Set-Cookie`: ele diz ao browser para não mandar o cookie em requests disparadas por outro site. É a atenuação que a lição 04 do capítulo 3 já citou. Ela tem limites: no modo `Lax`, o cookie ainda vai quando um link de outro site navega até o seu com `GET`, e "site" não é "origem", porque a porta não conta (`localhost:8080` e `localhost:8000` são o mesmo site). O **token anti-CSRF** é um valor aleatório que o servidor dá à página e exige de volta em toda request que muda alguma coisa. A página de B não consegue lê-lo (same-origin policy), e a request falsa é recusada.

A última linha é igual nas duas colunas de propósito. Evitar XSS é dever de quem escreve a página: escapar tudo o que veio do usuário antes de pôr no HTML (trocar `<` por `&lt;`, e assim por diante, para virar texto e não tag).

O FairFare é uma API, sem página e sem cookie. Ele fala header, e por isso não sofre de CSRF. Onde guardar o token é decisão da página que um dia o consumir.

## O preflight que agora acontece

A lição 04 do capítulo 3 listou o que dispara um preflight: "qualquer header customizado — `Authorization` incluído". O `Authorization` não está na lista de headers seguros do browser. Então, antes de qualquer `fetch` com o crachá, o browser pergunta com um `OPTIONS`: "posso mandar um `GET` com o header `authorization`?".

Contra o FairFare do commit anterior, a resposta foi esta:

```console
$ curl -s -i -X OPTIONS -H "Origin: http://localhost:8080" \
    -H "Access-Control-Request-Method: GET" \
    -H "Access-Control-Request-Headers: authorization" \
    localhost:8000/bookings
HTTP/1.1 400 Bad Request
date: Sun, 25 Oct 2026 03:30:10 GMT
server: uvicorn
vary: Origin
access-control-allow-methods: GET, POST, DELETE
access-control-max-age: 600
access-control-allow-headers: Accept, Accept-Language, Content-Language, Content-Type
access-control-allow-origin: http://localhost:8080
content-length: 23
content-type: text/plain; charset=utf-8

Disallowed CORS headers
```

E no log do uvicorn:

```
INFO:     127.0.0.1:32842 - "OPTIONS /bookings HTTP/1.1" 400 Bad Request
```

Repare que a origem foi aceita: o `access-control-allow-origin` está lá. O problema é o `access-control-allow-headers`: ele traz a lista segura e mais nada, sem `Authorization`. O `CORSMiddleware` respondeu sozinho, o browser cancela o `GET`, e o router nunca fica sabendo.

O conserto é a linha que a lição 12 do capítulo 3 deixou anotada, com "**Capítulo 6.**" do lado. Em `app/main.py`:

```diff
 # A página da bancada mora em http://localhost:8080. Origem explícita: nada de "*".
-# Content-Type já é permitido por padrão; quando a API pedir Authorization (cap. 6),
-# ele entra em allow_headers.
+# Content-Type já é permitido por padrão. O crachá vai no header Authorization, que não
+# está na lista segura: ele precisa estar em allow_headers, senão o preflight leva 400.
+# Sem allow_credentials: o token é um header que o JS põe à mão, não um cookie.
 app.add_middleware(
     CORSMiddleware,
     allow_origins=["http://localhost:8080"],
     allow_methods=["GET", "POST", "DELETE"],
+    allow_headers=["Authorization"],
 )
```

O mesmo `curl`, depois:

```console
$ curl -s -i -X OPTIONS -H "Origin: http://localhost:8080" \
    -H "Access-Control-Request-Method: GET" \
    -H "Access-Control-Request-Headers: authorization" \
    localhost:8000/bookings
HTTP/1.1 200 OK
date: Sun, 25 Oct 2026 03:30:33 GMT
server: uvicorn
vary: Origin
access-control-allow-methods: GET, POST, DELETE
access-control-max-age: 600
access-control-allow-headers: Accept, Accept-Language, Authorization, Content-Language, Content-Type
access-control-allow-origin: http://localhost:8080
content-length: 2
content-type: text/plain; charset=utf-8

OK
```

O `Authorization` entrou na lista, no meio dos headers seguros que o Starlette já permitia. O `400` virou `200`. A promessa da lição 04 do capítulo 3 ("quando o capítulo 6 trouxer `Authorization`, aí sim") está cumprida.

No teste, a mesma pergunta, pelo cliente anônimo: o preflight não leva credencial.

```python
async def test_preflight_com_authorization_e_permitido(client):
    resp = await client.options(
        "/bookings",
        headers={
            "Origin": ORIGEM_PERMITIDA,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert resp.status_code == 200
    assert "authorization" in resp.headers["access-control-allow-headers"].lower()
```

Antes da linha nova, ele falhou assim:

```
>       assert resp.status_code == 200
E       assert 400 == 200
```

## Por que não `allow_credentials`

O `CORSMiddleware` tem um parâmetro com cara de que deveria estar aqui: `allow_credentials`. O token não é uma credencial?

No CORS, não. **"Credentials"**, no vocabulário do browser, quer dizer o que **o próprio browser** anexa à request: cookies, a autenticação HTTP que ele mesmo guarda (aquela janelinha de usuário e senha) e certificados de cliente. Para uma página mandar isso a outra origem, o `fetch` precisa pedir (`credentials: "include"`). E para o JS **ler** a resposta (e, quando há preflight, para a request sair), o servidor precisa responder `Access-Control-Allow-Credentials: true`. É isso que o `allow_credentials=True` liga.

O header que o JS põe à mão não é nada disso. Para o browser, é só mais um header, e ele vai mesmo com `credentials: "omit"`, o modo que não manda credencial nenhuma. Header se libera com `allow_headers`. Uma precisão sobre a lição 04 do capítulo 3: ela pôs `Authorization` no parêntese das credenciais. O termo é mais estreito, e o header posto à mão fica de fora dele.

O teste fixa a ausência:

```python
async def test_sem_allow_credentials(client):
    # O crachá é um header que o JS põe à mão. Não é cookie: o CORS não precisa liberar credenciais.
    resp = await client.options(
        "/bookings",
        headers={
            "Origin": ORIGEM_PERMITIDA,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert resp.status_code == 200
    assert "access-control-allow-credentials" not in resp.headers
```

E o `*`? A lição 04 do capítulo 3 disse que, para a nossa API com login, não. Com o crachá no header, o `*` simples faria menos estrago do que ela deu a entender: o site B leria a resposta, mas sem o token, então só leria o que qualquer um sem login lê. O perigo daquela lição é o do cookie, e a armadilha do `*` com `allow_credentials=True` (o Starlette passa a ecoar qualquer origem) continua longe, porque o FairFare não liga nenhum dos dois. Mesmo assim, a origem segue explícita. A defesa do header só vale enquanto não entrar cookie: no dia em que entrar, o `*` volta a ser o problema sem ninguém mexer no CORS. E as rotas anônimas ficariam legíveis por qualquer site. Lista explícita é mínimo privilégio: libera quem precisa, e só.

## O 401 também precisa de CORS

A sessão da página venceu. O preflight passa, o `GET` sai com o token vencido, e o FairFare responde `401`. Sem o `access-control-allow-origin`, o browser esconderia essa resposta, e a página veria "erro de CORS" em vez de "faça login". É o raciocínio do `429` na lição 05 do capítulo 3.

Aqui o `401` nasce dentro do app, e o `CORSMiddleware`, a camada de fora, carimba na saída:

```console
$ curl -s -i -H "Origin: http://localhost:8080" localhost:8000/bookings
HTTP/1.1 401 Unauthorized
date: Sun, 25 Oct 2026 03:30:33 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 30
content-type: application/json
access-control-allow-origin: http://localhost:8080
vary: Origin

{"detail":"Not authenticated"}
```

Isso quebra calado no dia em que a checagem do crachá sair da dependência e virar um middleware registrado por fora do CORS, o mesmo tropeço do rate limiter na ordem errada. Reordenar os dois middlewares de hoje não quebra: o `401` nasce por dentro dos dois. Então vira teste, anônimo como o `test_429_atravessa_o_cors`:

```python
async def test_401_atravessa_o_cors(client):
    # Anônimo de propósito: sem o carimbo, a página veria "erro de CORS" em vez de "faça login".
    resp = await client.get("/bookings", headers={"Origin": ORIGEM_PERMITIDA})
    assert resp.status_code == 401
    assert resp.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA
```

Antes da linha nova, o do preflight e o `test_sem_allow_credentials` falham, com o mesmo `400`. O do `401` já passava: ele entra para fixar o comportamento.

## O que fica declarado

- **Onde o cliente guarda o token é decisão do cliente.** O FairFare entrega o token e confere o header. A página que um dia consumir a API escolhe onde guardar, e com a escolha vem o dever de não ter XSS.
- **Nada de cookie de sessão.** Sem cookie, o FairFare não precisa de `SameSite` nem de token anti-CSRF. Se um dia a sessão for para um cookie, as duas defesas entram junto.
- **Sem `allow_credentials`.** O CORS libera o header `Authorization` e mais nada.

## O que você deve conseguir fazer agora

- Explicar o CSRF com o formulário escondido, e por que o CORS não o impede.
- Explicar por que o header `Authorization` não sofre de CSRF, e qual ataque ele troca por isso.
- Dizer por que o preflight do FairFare passou a acontecer, e ler no `400` qual header faltou.
- Dizer o que `allow_credentials=True` liga, e por que o FairFare não precisa dele.
- Explicar por que um `401` sem `access-control-allow-origin` viraria "erro de CORS" na página.
