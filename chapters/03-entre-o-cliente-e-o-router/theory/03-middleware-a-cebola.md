# Lição 03 — Middleware: a cebola

A lição 02 terminou com um endereço vago. Contar requests por cliente é "trabalho para dentro do processo" — mas *onde* dentro do processo?

A resposta óbvia está errada, e vale começar por ela.

## O lugar óbvio, e por que ele não serve

Você já sabe pendurar código em uma rota. O capítulo 1 usou dependências, e o capítulo 2 as deixou assim (`app/routers/users.py`):

```python
@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    ...
```

Então por que não uma `Depends(contar_requests)`? Três motivos, e cada um sozinho já mataria a ideia.

Primeiro: uma dependência é **por rota**. Você teria que lembrar de colocá-la em cada uma, para sempre, inclusive nas que ainda não existem. (Dá para torná-la global com `dependencies=[...]` no `FastAPI()` — mas ela continua rodando depois do roteamento, e os dois motivos seguintes sobrevivem.)

Segundo: uma dependência roda **depois do roteamento**. O FastAPI precisou olhar o path, achar a rota, casar os parâmetros. Um cliente que dispara mil requests para `/nao-existe` nunca chega perto da sua dependência — ele bate no 404 e o seu contador nem sabe que ele existiu.

Terceiro: a dependência não consegue **abortar barato**. Ela roda depois que o roteamento aconteceu e o corpo já foi lido. Você paga o trabalho todo para depois dizer "não".

O que a gente quer é um lugar que rode em **toda** request, antes do roteamento, com poder de responder sozinho. Esse lugar existe, e a lição 01 já passou por ele sem nomear.

## O corredor

Lembre do `espiao.py`:

```python
async def app(scope, receive, send) -> None:
    if scope["type"] == "http":
        print(...)
    await fairfare(scope, receive, send)
```

Uma corrotina de três argumentos que imprime e depois chama outra corrotina de três argumentos. Aquilo tem nome: é um **middleware**.

A analogia é uma cebola. O seu router está no centro. Cada camada envolve a de dentro por inteiro: para chegar ao centro, a request atravessa todas; para sair, atravessa todas de novo, na ordem contrária. Nada entra nem sai sem passar por cada camada duas vezes.

Agora o rigor, sem a cebola: **um middleware ASGI é um app ASGI que recebe outro app ASGI.** Mesma assinatura `(scope, receive, send)` dos dois lados. Ele guarda o app de dentro e decide se, quando e com o quê chamá-lo.

Essa frase carrega mais do que parece. "Se" — ele pode não chamar, e responder ele mesmo. "Quando" — pode fazer coisas antes e depois. "Com o quê" — pode alterar o `scope`, ou entregar um `send` embrulhado e ver cada mensagem que sai.

Para o uvicorn, nada disso aparece. Ele continua chamando uma corrotina de três argumentos. Só que essa corrotina agora é a camada de fora da cebola, e o FastAPI está lá no meio.

## A cebola, no terminal

Chega de desenho. A bancada ganhou o `cebola.py`: três middlewares que imprimem quando entram e quando saem, um router que imprime quando é alcançado.

```python
class CamadaASGI:
    """Middleware ASGI puro: recebe o app de dentro e vira ele mesmo um app."""

    def __init__(self, app, nome: str) -> None:
        self.app = app
        self.nome = nome

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        print(f"→ entrei em {self.nome}")

        async def send_espiao(mensagem) -> None:
            if mensagem["type"] == "http.response.start":
                print(f"← saindo de {self.nome} (status {mensagem['status']})")
            await send(mensagem)

        await self.app(scope, receive, send_espiao)
```

Três detalhes dessa classe, porque essa forma é a que o capítulo inteiro vai repetir:

- **`__init__(self, app, ...)`.** O primeiro argumento é sempre o app de dentro. Quem passa é o framework, não você.
- **O passe livre para `scope["type"] != "http"`.** Lifespan e websocket (o outro tipo de conexão que o ASGI carrega; o curso não vai usar) também atravessam aqui. Se o seu middleware só entende HTTP, ele repassa o resto intacto em vez de quebrar. E isso não é zelo excessivo. Tire a guarda de um middleware que leia, digamos, `scope["path"]`, e o `KeyError` estoura no lifespan:

  ```
  INFO:     Waiting for application startup.
  INFO:     ASGI 'lifespan' protocol appears unsupported.
  INFO:     Application startup complete.
  ```

  O app **sobe assim mesmo**, e é aí que mora o perigo: o uvicorn engole a exceção, conclui que você não implementou lifespan e segue em frente. Nenhum erro vermelho. Só o seu `startup` inteiro — o pool que ia abrir, o cliente HTTP que ia nascer — silenciosamente não acontecendo.
- **O `send` embrulhado.** Você não recebe a resposta pronta em lugar nenhum. Você troca o `send` por uma função sua, e ela vê cada mensagem passando. É assim que se olha o status: interceptando o `http.response.start`, que é a primeira mensagem a sair.

O resto do arquivo é um router de uma linha e o registro das camadas:

```python
app.add_middleware(CamadaASGI, nome="A (registrado primeiro)")
app.add_middleware(CamadaASGI, nome="B (registrado depois)")
app.add_middleware(CamadaFacil, nome="C (registrado por último, BaseHTTPMiddleware)")
```

Suba:

```bash
uv run uvicorn cebola:app --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
```

Bata uma vez com `curl -s localhost:8000/` e olhe o terminal **do servidor** (cortei o banner de subida do uvicorn):

```
→ entrei em C (registrado por último, BaseHTTPMiddleware)
→ entrei em B (registrado depois)
→ entrei em A (registrado primeiro)
   · o router, no centro da cebola
← saindo de A (registrado primeiro) (status 200)
← saindo de B (registrado depois) (status 200)
← saindo de C (registrado por último, BaseHTTPMiddleware) (status 200)
INFO:     127.0.0.1:52396 - "GET / HTTP/1.1" 200 OK
```

Leia de cima para baixo. A ordem de entrada é **C, B, A** — o inverso da ordem em que registramos. A ordem de saída é A, B, C. A cebola aparece inteira em sete linhas.

**`add_middleware` empilha: o último registrado é a camada de fora.** Ele entra primeiro e sai por último.

Se isso parece invertido, é porque a palavra "adicionar" engana. Pense em vestir roupa: a última peça que você veste é a de fora, e é a primeira que a chuva encontra. Tecnicamente, o Starlette monta a pilha de dentro para fora na primeira vez em que é chamado — sob o uvicorn, isso é o lifespan, ou seja, na subida. Cada `add_middleware` embrulha tudo que já existia, e quem embrulha por último fica por cima.

Guarde essa regra. Na lição 05, a pergunta "o rate limiter vem antes ou depois da outra camada?" vira uma linha de código, e a linha só faz sentido com essa ordem na cabeça.

## As duas formas

Você deve ter reparado que a camada C é de outra classe. Existem duas maneiras de escrever middleware num app FastAPI, e a escolha entre elas é uma decisão real.

### A forma fácil: `BaseHTTPMiddleware`

```python
class CamadaFacil(BaseHTTPMiddleware):
    """A forma fácil: você vê Request e Response, não scope/receive/send."""

    def __init__(self, app, nome: str) -> None:
        super().__init__(app)
        self.nome = nome

    async def dispatch(self, request, call_next):
        print(f"→ entrei em {self.nome}")
        resposta = await call_next(request)
        print(f"← saindo de {self.nome} (status {resposta.status_code})")
        return resposta
```

Compare com a `CamadaASGI`. Aqui não tem `scope`, não tem `send` embrulhado, não tem passe livre para lifespan. Você recebe um `Request`, chama `call_next`, recebe um `Response` com `.status_code` — os mesmos objetos que você já usa nos routers. É confortável, e o `@app.middleware("http")` do FastAPI é açúcar em cima disso.

O conforto tem preço. Para te entregar um `Request` e um `Response`, o Starlette roda o app de dentro numa task separada e passa a resposta por um canal em memória. Isso custa por request. Atrapalha respostas em streaming. E tem histórico de bugs difíceis de diagnosticar: `contextvars` definidas lá dentro que não chegam aqui fora, background tasks se comportando de forma inesperada. Não é fofoca de internet: a documentação do Starlette registra limitações do `BaseHTTPMiddleware` e aponta o middleware ASGI puro como alternativa quando elas importam.

### A forma pura: ASGI

Mais verbosa e mais poderosa. Você vê o protocolo, então você pode:

- **Mexer no `scope` antes do app de dentro ver.** É assim que um header mandado por um proxy vira o `scope["client"]` que o seu app enxerga — assunto da lição 08.
- **Responder sem chamar o app de dentro.** Dois `send` e acabou: nenhum router, nenhuma sessão de banco, nenhuma validação. É exatamente o que um `429 Too Many Requests` precisa fazer.
- **Ver cada mensagem que sai, uma a uma**, inclusive os headers antes de o corpo ir pelo fio.
- **Tratar lifespan e websocket**, ou deixá-los passar de propósito.

Sendo justo: dá para devolver uma resposta cedo no `dispatch` também, sem chamar `call_next`. A diferença não é "consegue ou não consegue" — é que na forma pura você paga só o que usa e enxerga a conversa inteira.

### A regra

**Se você só quer olhar, o fácil serve. Se você precisa controlar, ASGI puro.**

Olhar é medir tempo, contar status, logar. Controlar é responder antes, mudar o `scope`, mexer nos headers de saída.

**Decisão deste capítulo: o FairFare vai usar a forma pura.** Nos dois casos. Uma das camadas que vem por aí precisa recusar a request sem deixar o app rodar, e isso já resolve a questão. Mas tem um motivo pedagógico junto: você acabou de aprender `scope`, `receive` e `send`. Escrever middleware na forma que esconde os três seria jogar fora a lição 01 uma semana depois de aprendê-la.

## Onde o FairFare vai morar

Nada disso entrou no `app/` ainda. Esta lição é bancada inteira, de propósito: primeiro o mecanismo na tela, depois o uso.

O que vem: as lições 04 e 05 adicionam **duas camadas** ao FairFare, cada uma resolvendo um problema declarado. E a ordem entre elas não vai ser detalhe de estilo — vai ser uma decisão com consequência observável, do tipo que muda o que o browser mostra quando uma request é recusada.

Você já tem tudo para prever essa consequência. É só lembrar quem fica por fora.

## O que você deve conseguir fazer agora

- Dizer por que um contador por cliente não pode ser uma dependência de rota — três motivos.
- Explicar, sem a analogia, o que é um middleware ASGI: um app ASGI que recebe outro app ASGI e decide se, quando e com o quê chamá-lo.
- Dado o código que registra três middlewares, prever a ordem de entrada e a ordem de saída.
- Escrever um middleware ASGI puro do zero: `__init__(self, app, ...)`, `__call__(self, scope, receive, send)`, passe livre para o que não é `http`, `send` embrulhado para ler o status.
- Escolher entre `BaseHTTPMiddleware` e ASGI puro para um caso dado, e justificar com a regra do olhar e do controlar.
