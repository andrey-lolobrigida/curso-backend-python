# Lição 06 — A rede de segurança primeiro

A próxima lição reescreve o FairFare inteiro: `database.py`, três repositories, um service, três routers. Tudo num commit só.

Antes de fazer isso, uma pergunta: **como você vai saber se deu certo?**

Subir o servidor e clicar em tudo? Foi assim no capítulo 1, e a lição 11 daquele capítulo terminou com a confissão de que isso não escala. A resposta certa é o `uv run pytest`. Mas tem um detalhe: os nossos testes são síncronos, e o app que eles vão testar não vai ser.

Então a ordem é essa, e ela não é arbitrária: **primeiro o instrumento que mede, depois a mudança que precisa ser medida.** Quem inverte migra no escuro.

## O plano da lição

Trocar o cliente de teste síncrono por um assíncrono — **sem tocar em uma linha do app**. Ao fim, os 13 testes continuam passando exatamente como antes, e a rede está pronta para o salto.

Comece pelo plugin:

```bash
uv add --dev pytest-asyncio
```

E no `pyproject.toml`, uma linha nova:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

O que esse `asyncio_mode = "auto"` faz: manda o plugin tratar **toda** função de teste `async def` como corrotina a ser rodada num event loop, sem você marcar nada. A alternativa é decorar cada teste com `@pytest.mark.asyncio` e cada fixture com `@pytest_asyncio.fixture`, treze vezes, e não aprender nada em troca.

Vale ver o que acontece sem ele. Rode com o modo padrão do plugin, o `strict`:

```bash
uv run pytest -q -o asyncio_mode=strict
```

```
ERROR at setup of test_cria_e_busca_usuario
'test_cria_e_busca_usuario' requested an async fixture 'client', with no plugin
or hook that handled it. This is an error, as pytest does not natively support it.
```

Treze erros, todos assim. É uma falha barulhenta e específica, do jeito que a gente gosta — e note que ela vem do **pytest**, não do plugin: sem alguém que saiba rodar corrotinas, ele se recusa a fingir que testou.

Rode agora, antes de mexer em qualquer teste:

```bash
uv run pytest -q
# 13 passed
```

Isso é o baseline. O plugin entrou e não quebrou nada.

## O cliente que fala ASGI

No capítulo 1 a fixture usava o `TestClient` do FastAPI. Agora:

```python
@pytest.fixture()
async def client():
    ...
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
```

Três coisas mudaram, e só três:

1. A fixture virou `async def` (e, no modo `auto`, um `@pytest.fixture()` comum já dá conta de uma fixture assíncrona).
2. `TestClient` saiu, `AsyncClient` do httpx2 entrou.
3. Apareceu o `ASGITransport`.

O `ASGITransport` é a peça interessante. Um cliente HTTP normal abre um socket e manda bytes por uma porta. O `ASGITransport` diz ao httpx2: "não abra socket nenhum; entregue esta request direto para este app, chamando-o pela interface ASGI". É o mesmo truque do `TestClient` do capítulo 1 — request sem servidor de pé, e é por isso que os 13 testes rodam em pouco mais de um décimo de segundo.

**O que não mudou:** o `dependency_overrides`, o engine em memória, o `create_all`. O banco de teste continua **síncrono neste commit**, porque o app ainda é síncrono. Um eixo por vez.

## O detalhe que surpreende

Olhe de novo para o que a gente acabou de fazer. Um cliente **assíncrono** conversando com um app cujas rotas são todas `def`. Isso deveria funcionar?

Funciona. E entender por quê vale mais que a lição inteira.

**ASGI é a fronteira.** É o protocolo entre servidor e aplicação em Python — a mesma fronteira que o uvicorn atravessa em produção, e o capítulo 3 vai abrir essa caixa por completo. A interface ASGI é assíncrona: quem chama o app usa `await`. Sempre. Independentemente de como suas rotas estão escritas.

O que acontece do outro lado da fronteira é problema do Starlette, e você já sabe qual é a resolução dele (lição 01): rota `def` vai para o threadpool, rota `async def` roda no loop. O cliente não sabe disso, não precisa saber, e nunca vai saber.

Guarde essa fronteira, porque ela explica duas coisas de uma vez:

- Por que o `AsyncClient` fala com o app síncrono de hoje **e** com o app assíncrono de amanhã, sem uma linha de diferença.
- Por que a migração da próxima lição não vai encostar em `app/main.py`. O `main.py` monta o app e registra os routers; ele vive na fronteira, e a fronteira não muda.

E aproveite para entender o que o `TestClient` sempre foi: um invólucro **síncrono** em volta de um cliente assíncrono, que cria um event loop escondido para você a cada chamada. Ele fazia esse trabalho no capítulo 1 e fazia bem. Agora que a gente está aprendendo o loop, ter um loop escondido deixou de ser conforto e passou a ser névoa.

## O diff que quase não existe

Um teste, antes:

```python
def test_cria_e_busca_usuario(client):
    user = _cria_usuario(client)
    resp = client.get(f"/users/{user['id']}")
    assert resp.status_code == 200
    assert resp.json()["nome"] == "Ana"
```

Depois:

```python
async def test_cria_e_busca_usuario(client):
    user = await _cria_usuario(client)
    resp = await client.get(f"/users/{user['id']}")
    assert resp.status_code == 200
    assert resp.json()["nome"] == "Ana"
```

Duas palavras. `async` na assinatura, `await` nas chamadas. **Os asserts estão intactos.** Os payloads, os status codes, os nomes dos testes: idênticos.

Isso não é sorte, é sintoma de teste bem escrito. Nossos testes falam de **comportamento** — "criar um usuário devolve 201", "email duplicado devolve 409" — e o comportamento do FairFare não mudou nem vai mudar. Async é uma decisão sobre *como* o trabalho é executado, não sobre *o que* o app faz.

A régua que sai daí, e que vale muito além deste capítulo: quando você troca a mecânica interna e os testes precisam ser reescritos de verdade, eles estavam testando mecânica interna. Aqui só a pontuação mudou.

Um cuidado ao converter os seus: chamadas encadeadas precisam de parênteses ou de uma variável. Isto quebra —

```python
assert await client.get("/users/999").status_code == 404   # errado
```

— e o erro é uma velha conhecida da lição 03:

```
AttributeError: 'coroutine' object has no attribute 'status_code'
sys:1: RuntimeWarning: coroutine 'AsyncClient.get' was never awaited
```

O `await` se aplica ao `.status_code`, não ao `.get(...)`: o `get` devolveu um objeto corrotina — parado, nunca entregue ao loop — e você tentou ler um atributo dele. A forma legível é dar um nome à resposta:

```python
resp = await client.get("/users/999")
assert resp.status_code == 404
```

Rode e exija verde:

```bash
uv run pytest -q
# 13 passed
```

Treze passando, com um cliente async, contra um app que ainda não mudou uma vírgula. A rede está armada. Agora dá para pular.

## O que você deve conseguir fazer agora

- Configurar `pytest-asyncio` em modo `auto` e explicar o que aconteceria sem ele.
- Escrever uma fixture assíncrona que devolve um `AsyncClient` ligado ao seu app.
- Explicar o que o `ASGITransport` faz e por que o teste não precisa de servidor de pé.
- Explicar por que um cliente async conversa com rotas `def` sem reclamar.
- Converter um teste síncrono em async — e reconhecer a armadilha do `await` em chamada encadeada.
- Defender, para alguém com pressa, por que a rede de segurança vem antes da migração.
