# Lição 07 — Mesma origem, e a mesma coisa em outra língua

A lição 04 terminou com uma promessa: *a melhor configuração de CORS é a que você não precisa ter*. A lição 06 pôs um proxy na frente do app por quatro motivos que não tinham nada a ver com CORS. Esta lição cobra a promessa — e, de brinde, traduz o `proxy.py` para as duas línguas em que você vai encontrá-lo na vida real.

## A página muda de endereço

Uma linha mudou em `bancada/pagina/index.html`:

```javascript
// Lição 07: a página e a API saem do MESMO lugar (o proxy, na 8080).
// Mesma origem — o browser não tem do que reclamar.
const API = "/api";
```

Era `"http://localhost:8000"`. Virou `"/api"`. Um caminho relativo — o browser resolve contra a origem da própria página, que agora é `http://localhost:8080`. Então o `fetch` vai para `http://localhost:8080/api/users`, o proxy repassa, e a resposta volta.

(A partir daqui a página **só** funciona atrás do proxy. Se você quiser voltar e refazer a lição 04 com o `python3 -m http.server`, troque a constante de volta junto — o `README.md` da bancada tem os dois arranjos lado a lado.)

Releia a definição de origem da lição 04: esquema + host + porta. A página veio de `http://localhost:8080`. O `fetch` vai para `http://localhost:8080`. **Mesma origem.**

Com as duas abas da lição 06 de pé — o FairFare na 8000, o proxy na 8080 —, abra `http://localhost:8080` com o console aberto e use a página. A lista aparece, o formulário cria usuário, console limpo. Estas são as requests que o browser fez, do load até o segundo item entrar na lista:

```
GET    http://localhost:8080/              origin=None
GET    http://localhost:8080/api/users     origin=None
POST   http://localhost:8080/api/users     origin='http://localhost:8080'
GET    http://localhost:8080/api/users     origin=None
```

*(Capturado de verdade com Playwright — uma ferramenta que dirige um browser por script — em Chromium e em Firefox. Os dois deram exatamente as mesmas quatro linhas.)*

Duas coisas para reparar, e a segunda é uma armadilha.

**Nenhum `OPTIONS`.** Zero, nas duas engines. O `POST` com JSON no corpo — o mesmo que na lição 04 disparava um preflight — foi direto. Preflight só existe para outra origem; aqui não há outra origem.

**Mas o header `Origin` não sumiu.** Olhe a terceira linha: no `POST`, o browser mandou `Origin: http://localhost:8080` do mesmo jeito. Isso não é bug de browser: os dois fizeram igual, e a spec do Fetch manda fazer isso — o `Origin` é carimbado sempre que o método não é `GET` nem `HEAD`, mesmo para a própria origem. Ele serve a mais coisas do que CORS. E como o nosso proxy repassa os headers, ele chega ao FairFare, e o `CORSMiddleware` **é** executado e carimba a resposta:

```console
$ curl -s -i -X POST localhost:8080/api/users -H 'content-type: application/json' \
    -H 'Origin: http://localhost:8080' -d '{"nome":"Eva","email":"eva@exemplo.com"}' \
    | grep -iE '^HTTP|access-control'
HTTP/1.1 201 Created
access-control-allow-origin: http://localhost:8080
```

Então cuidado com a frase fácil. Não é que o CORS "deixou de rodar" — em pelo menos uma das requests ele roda. É que **o browser parou de cobrar**: quando a resposta vem da mesma origem da página, ele a entrega ao JavaScript sem procurar `Access-Control-Allow-Origin` nenhum. O carimbo virou enfeite.

E dá para provar isso de um jeito que não deixa dúvida: comente o bloco do `CORSMiddleware` no `app/main.py`, reinicie o FairFare, e use a página de novo. Sem nenhum header de CORS na resposta —

```console
$ curl -s -i -X POST localhost:8080/api/users -H 'content-type: application/json' \
    -H 'Origin: http://localhost:8080' -d '{"nome":"Zed","email":"zed@exemplo.com"}' \
    | grep -ic 'access-control'
0
```

— a página **continua funcionando inteira** nos dois browsers: lista carrega, formulário cria, `#erro` vazio, console vazio, zero `OPTIONS`. (Também capturado com Playwright. Foi um teste temporário: descomente o bloco antes de seguir. O FairFare do repositório continua com o CORS ligado, e a seção seguinte diz por quê.)

### Então quando cada um?

Não é "proxy é melhor que CORS". São respostas para perguntas diferentes.

- **A sua página e a sua API.** Sirva as duas da mesma origem, atrás de um proxy. O CORS deixa de ser cobrado e você tem um problema a menos para configurar em cada ambiente.
- **Uma API que outros sites vão consumir pelo browser.** Um parceiro, um widget embutido, um frontend em outro domínio de propósito. Aí não existe "mesma origem" possível: é CORS, com a lista de origens explícita, exatamente como na lição 04.

O FairFare fica com os dois, e isso é deliberado: a lição 04 é conhecimento que você vai precisar, e o app é a referência dela. Num sistema real você escolheria um.

## Os mesmos três conceitos, em outra língua

Você não vai escrever um proxy em Python para produção. Vai configurar um pronto — quase sempre **nginx** ou **Caddy**. E aqui está o ganho de ter escrito o seu: os arquivos de configuração deles deixam de ser feitiço. São os mesmos três blocos do `proxy.py`: **escutar**, **repassar**, **servir estático**.

Estes dois arquivos estão na bancada e são **lidos como texto neste curso — nenhum dos dois é executado**. Instalar nginx ou Caddy é atrito que não ensina nada agora, e o capítulo 11 põe um deles para rodar de verdade, junto com Docker e deploy. Por ora o exercício é de reconhecimento. (Os arquivos no repositório trazem esse aviso num comentário no topo; os trechos abaixo começam depois dele.)

`bancada/Caddyfile`:

```
localhost:8080 {
    # ESCUTAR: o bloco acima. REPASSAR: /api/* vai para o FairFare, sem o prefixo.
    handle_path /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    # SERVIR ESTÁTICO: tudo o mais é a página.
    handle {
        root * pagina
        file_server
    }
}
```

*(Versão do commit desta lição. A lição 08 acrescenta dois comentários aqui.)*

Onze linhas. O `handle_path` é o `{caminho:path}` do `proxy.py`: ele casa `/api/*` e **remove** o prefixo antes de repassar — é literalmente a diferença entre `handle_path` e `handle` no Caddy. O `reverse_proxy` é o `upstream.request(...)`. O `root` + `file_server` é o `Mount("/", StaticFiles(...))`.

`bancada/nginx.conf`:

```nginx
events {}

http {
    server {
        listen 8080;                                   # ESCUTAR

        location /api/ {                               # REPASSAR
            proxy_pass http://127.0.0.1:8000/;         # a barra final tira o /api/
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $remote_addr;   # sobrescreve, não acrescenta (lição 08)
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location / {                                   # SERVIR ESTÁTICO
            root pagina;
            index index.html;
        }
    }
}
```

A linha que mais custa caro na vida real é a `proxy_pass`, por causa da **barra final**. `proxy_pass http://127.0.0.1:8000/` (com barra) substitui o trecho casado pelo `location` — `/api/users` vira `/users`. `proxy_pass http://127.0.0.1:8000` (sem barra) repassa o caminho inteiro — `/api/users` chega como `/api/users`, e o seu app responde 404. Um caractere.

Os três `proxy_set_header` não têm equivalente no nosso `proxy.py`. Ainda. São o assunto da lição 08 — e o comentário ao lado do `X-Forwarded-For` é uma pista de que a coisa é mais delicada do que parece.

E volte ao terminal do FairFare da lição 06, onde toda request chegava de `127.0.0.1`. O proxy ainda não conta ao app quem é o cliente de verdade. A lição 08 é sobre esse buraco — e sobre por que o conserto óbvio abre outro.

## O que você deve conseguir fazer agora

- Explicar por que `const API = "/api"` funciona sendo um caminho relativo — e por que isso faz o browser parar de cobrar CORS.
- Explicar por que, com a página e a API na mesma origem, o `CORSMiddleware` ainda roda e mesmo assim deixa de importar — e por que o `POST` leva `Origin` mas não leva preflight.
- Dizer quando a resposta certa é CORS e quando é mesma origem.
- Apontar no `nginx.conf` as três linhas que fazem o que o `proxy.py` faz, e dizer o que a barra final do `proxy_pass` muda.
