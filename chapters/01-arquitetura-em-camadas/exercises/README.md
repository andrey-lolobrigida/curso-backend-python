# Exercícios — Capítulo 1

Três blocos, três habilidades: **depurar** código quebrado (bloco 1), **estender** o app atravessando as camadas (bloco 2) e **refatorar** sob rede verde (bloco 3). Nada de página em branco: você recebe código — às vezes quebrado de propósito — e conserta.

## Como trabalhar

**1. Crie uma branch para os exercícios.** Assim o app oficial fica intacto e desfazer é barato:

```bash
git switch -c meus-exercicios
```

**2. Copie os arquivos indicados.** Cada exercício diz qual arquivo daqui vai por cima de qual arquivo do app (e qual arquivo de teste vai para `tests/`). Exemplo do padrão:

```bash
cp chapters/01-arquitetura-em-camadas/exercises/bloco1/user_model_quebrado.py app/models/user.py
```

**3. Rode os testes — só os testes.** A definição de "pronto" de todo exercício é a mesma: `uv run pytest` verde.

> **Por que não via curl?** Os arquivos do bloco 1 mudam o *schema do banco* (campo novo no model), e o seu `fairfare.db` local não tem essas colunas — o servidor subiria quebrado. O banco dos testes nasce do zero a cada teste (lição 11), então ele sempre bate com os models. Use o pytest como sua lente.

**4. Para desfazer tudo** e voltar ao app oficial:

```bash
git checkout -- app/ tests/
```

---

## Bloco 1 — depurar: uma dor por camada

Três estagiários, três estragos. Cada um quebrou uma camada diferente; os testes de `bloco1/test_bloco1.py` acusam os três. Copie o arquivo de teste uma vez:

```bash
cp chapters/01-arquitetura-em-camadas/exercises/bloco1/test_bloco1.py tests/
```

### 1a — o schema que vaza

*A história:* o time adicionou uma anotação interna sobre cada usuário ("vip", "caloteiro?") — e ela está saindo na API pública.

```bash
cp chapters/01-arquitetura-em-camadas/exercises/bloco1/user_model_quebrado.py app/models/user.py
cp chapters/01-arquitetura-em-camadas/exercises/bloco1/user_schema_quebrado.py app/schemas/user.py
```

*O que observar falhando:* `test_saida_de_usuario_nao_vaza_campos_internos` — o JSON da resposta contém `internal_note`.

*Pronto quando:* o teste passa **e** a coluna continua existindo no banco. Pense: o que é contrato público e o que é detalhe interno? (Lição 04 tem a frase-chave.)

### 1b — a fronteira errada

*A história:* alguém achou a query de conflito "complicada demais" e a reescreveu "mais simples, em Python puro". Duas reservas encostadas pararam de ser aceitas.

```bash
cp chapters/01-arquitetura-em-camadas/exercises/bloco1/booking_service_quebrado.py app/services/booking.py
```

*O que observar falhando:* `test_reservas_encostadas_nao_conflitam` — que já existia no smoke test! Rode `uv run pytest` e veja a rede de segurança da lição 11 trabalhando.

*Pronto quando:* todos os testes passam. Há **dois** problemas no código novo — um que o teste acusa e um adormecido. Ache os dois (o SOLUTIONS discute ambos).

### 1c — status codes mentirosos

*A história:* o router de recursos foi "simplificado" numa sexta-feira: buscar um recurso que não existe devolve `200` com `null`, e criar recurso sem `tipo` explode com erro 500.

```bash
cp chapters/01-arquitetura-em-camadas/exercises/bloco1/resources_router_quebrado.py app/routers/resources.py
```

*O que observar falhando:* `test_recurso_inexistente_e_404` (veio 200) e `test_recurso_sem_tipo_e_422` (o teste explode junto com o KeyError do servidor — falha barulhenta).

*Pronto quando:* os dois testes passam. Dica: compare com o router de usuários — o que ele tem que este perdeu?

---

## Bloco 2 — estender: o recurso ganha capacidade

Sem código quebrado desta vez: uma feature nova, do banco à API. O FairFare precisa saber quantas pessoas cabem num recurso — `capacity`, **opcional** (uma quadra pode não declarar).

```bash
cp chapters/01-arquitetura-em-camadas/exercises/bloco2/test_bloco2.py tests/
```

*A tarefa:* fazer os dois testes passarem. O caminho atravessa as camadas de baixo para cima:

1. O model `Resource` ganha `capacity` — que pode ser nulo (procure `int | None` na documentação de `Mapped`).
2. Uma migração nova (`--autogenerate`, **leia o rascunho**, `upgrade head`). Pergunta para responder no caminho: por que desta vez não precisa de `server_default`, sendo que o `tipo` da lição 07 precisou?
3. Os schemas `ResourceCreate` e `ResourceOut` ganham o campo (opcional, com `None` de padrão).
4. Siga o caminho do dado: o router entrega `capacity` ao repositório? O `ResourceRepository.create` aceita? Olhe antes de mexer.

*Pronto quando:* `uv run pytest` verde **e** `uv run alembic upgrade head` funciona num banco recém-apagado (`rm fairfare.db` antes, para conferir a cadeia inteira).

---

## Bloco 3 — refatorar: o pastelão

*A história:* um freelancer entregou o cancelamento de reservas. **Funciona** — os testes provam — mas está tudo na rota: SQL cru com `text()`, regra de negócio no meio do HTTP, nenhuma camada respeitada. É o anti-capítulo-1 em 15 linhas.

```bash
cp chapters/01-arquitetura-em-camadas/exercises/bloco3/bookings_router_pastelao.py app/routers/bookings.py
cp chapters/01-arquitetura-em-camadas/exercises/bloco3/test_bloco3.py tests/
```

Rode `uv run pytest`: **tudo verde, inclusive com o pastelão**. Essa é a graça do exercício.

*A tarefa:* refatorar o DELETE para as camadas certas **sem quebrar nenhum teste**:

- `BookingRepository`: buscar já existe (`get`); falta um `delete`.
- `BookingService`: um método `cancel` com a regra "só reservas futuras podem ser canceladas" — e as exceções de domínio que a regra pedir.
- Router: só tradução (exceção → status code).

É a experiência do capítulo inteiro em miniatura: mudar estrutura sem mudar comportamento, com a rede verde dizendo se você escorregou. Rode o pytest a cada passo da refatoração, não só no final.

*Pronto quando:* `uv run pytest` verde e nenhum `text(`, `datetime` ou regra de negócio sobrando no router.

---

Empacou? Tudo bem — o [SOLUTIONS.md](../SOLUTIONS.md) explica cada conserto com o raciocínio. Mas tente antes: a dor é o material didático.
