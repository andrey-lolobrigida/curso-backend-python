# Lição 11 — Smoke tests: a rede de segurança

## A dor (confissão)

Hora de confessar o que fizemos nas últimas sete lições: refatoramos o app **inteiro** — trocamos o banco, extraímos três camadas, movemos tudo de arquivo — conferindo na mão, com curl, a cada mudança. Criar usuário: confere. Email duplicado: confere. Conflito de reserva: confere. De novo. E de novo.

Você sentiu o medo? Aquele "será que a reserva encostada ainda funciona?" depois de mover código de lugar? Nas vezes em que a gente *esqueceu* de conferir uma rota, ela podia ter quebrado em silêncio e o commit teria ido em frente. Checklist manual não escala e a memória mente. Isso tem cura, e ela é a última camada do capítulo.

## Smoke test em uma frase

O nome vem da eletrônica: ligou o aparelho e **não saiu fumaça**, já é alguma coisa. Um smoke test não prova que o app está certo em todos os detalhes — prova que ele não está *obviamente quebrado*: as rotas respondem, os status codes principais saem, o caminho feliz anda.

É pouco? É o suficiente para transformar "espero que não quebrei nada" em `uv run pytest`, 0,2 segundos, resposta objetiva. Rede de segurança, não certificado de qualidade.

## TestClient: a request sem servidor

A ferramenta: **pytest** (o executor de testes do mundo Python) e o **TestClient** do FastAPI (que usa a biblioteca httpx2 por baixo — `uv add --dev pytest httpx2`; `--dev` porque teste é ferramenta de desenvolvimento, como o ruff).

Se você vir tutoriais mandando instalar `httpx` em vez de `httpx2`, eles não estão errados — estão velhos. O `httpx` parou de receber releases e o `httpx2` é o sucessor mantido; o TestClient já prefere o novo quando ele está instalado. Guarde o caso, porque ele é a lição 01 cobrando o que prometeu: dependências morrem, e o lockfile é o que transforma isso em "você troca quando quiser" em vez de "seu projeto quebrou numa terça-feira".

Um teste real, de `tests/test_smoke.py`:

```python
def test_cria_e_busca_usuario(client):
    user = _cria_usuario(client)
    resp = client.get(f"/users/{user['id']}")
    assert resp.status_code == 200
    assert resp.json()["nome"] == "Ana"
```

O `client.get(...)` é a mesma conversa HTTP do capítulo 0 — método, caminho, corpo, status — mas **sem servidor de pé**: o TestClient entrega a request direto ao app, por dentro, sem passar por porta de rede. Por isso os 10 testes rodam em fração de segundo.

Todo teste tem a mesma anatomia em três tempos: **preparar** o cenário (criar o usuário), **agir** (buscar o usuário), **conferir** (os `assert`s). Se um `assert` falhar, o pytest mostra exatamente o que esperava e o que veio.

## A recompensa da arquitetura

A pergunta que separa este teste de uma gambiarra: esses usuários de teste vão parar no seu `fairfare.db`? **Não.** E o mecanismo é a lição inteira. No `tests/conftest.py` (o arquivo onde o pytest busca as *fixtures* — os ingredientes que os testes pedem por parâmetro, como o `client`):

```python
fastapi_app.dependency_overrides[get_db] = override_get_db
```

`dependency_overrides` é um interruptor do FastAPI: "quando alguém pedir `get_db`, entregue `override_get_db` no lugar". E o `override_get_db` abre sessões num **SQLite em memória** (`"sqlite://"` sem caminho de arquivo — um banco que vive na RAM e morre com o processo), criado zerado para **cada teste**.

Agora a conta que paga sete lições de refatoração: trocamos o banco do app inteiro **sem tocar em uma linha de rota, service ou repository**. Só foi barato porque *toda* rota pede a sessão pelo mesmo `Depends(get_db)` (lição 06) e *todo* acesso a dados passa pelos repositories (lição 08). O acesso a banco tem endereço fixo; trocar o inquilino desse endereço é uma linha. Essa é a recompensa prometida — padrões se justificam pelo que habilitam.

## Duas honestidades

**Sobre o `create_all`.** O conftest cria as tabelas com `Base.metadata.create_all(engine)` — o método que a lição 07 aposentou em favor de migrações. Contradição? Não: migração existe para levar um banco **com vida longa e dados dentro** de um schema a outro sem perdas. O banco de teste vive milissegundos e nasce vazio; não há nada a preservar. Ferramenta certa para cada trabalho.

**Sobre a profundidade.** Dez testes de fumaça não são uma estratégia de testes. Não testamos o service isolado, não testamos casos de borda de datas, não medimos cobertura. Está tudo bem — por enquanto. Estratégia de testes (o que testar em cada camada, e por quê) é assunto do capítulo 10. O que temos hoje é o mínimo que nos deixa refatorar sem medo.

## O que você deve conseguir fazer agora

- Rodar `uv run pytest` e ler a saída — quantos passaram, quanto demorou.
- Escrever um teste novo: `GET /resources/{id}` inexistente deve dar 404. Colocá-lo em `tests/test_smoke.py` e vê-lo passar. (Molde: `test_usuario_inexistente_e_404`.)
- Explicar, com o diagrama da lição 10 na cabeça, por que trocar o banco nos testes custou uma linha.
- Explicar por que `create_all` é aceitável no conftest mas foi demitido do app.
