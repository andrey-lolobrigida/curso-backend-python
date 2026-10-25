# Lição 13 — O que este código ainda não resolve

Todo capítulo desde o 2 fecha com esta lição, e pelo mesmo motivo: **um curso que entrega código tem uma dívida com quem vai ler esse código.** Se eu sei que tem um defeito, eu te conto.

Este capítulo ensinou o FairFare a perguntar quem é você e o que você pode. Cada ponta solta foi declarada no fim da lição onde apareceu. Aqui vai tudo junto, com endereço e com o capítulo em que morre.

Três itens têm capítulo marcado. O resto é escolha, colateral ou ressalva. E tem um item **riscado**: o último dos três que o capítulo 1 deixou.

## 1. Força bruta numa conta só

**Onde:** `RateLimitMiddleware`, em `app/middleware/rate_limit.py`, cuja chave do balde é `scope["client"]`, o IP. E o `AuthService.login`, em `app/services/auth.py`, que não conta as tentativas de conta nenhuma.

**Como se manifesta:** o limitador conta por IP e por processo. Cada IP ganha 20 fichas, que recarregam 5 por segundo (os números do `app/main.py`). Quem chuta senhas da conta da Ana a partir de mil IPs tem mil baldes, e nenhum esvazia. Com vários workers, cada processo tem o próprio dicionário de baldes, como a lição 12 do capítulo 3 declarou.

O argon2 protege a senha se a tabela vazar. Contra o chute pela porta da frente, só há o limitador, e ele não conhece contas. Contar por conta pede um contador que todos os processos vejam.

O mesmo buraco tem um segundo uso. Toda tentativa de login paga um `verify` do argon2, até a do email que não existe (o fantasma da lição 06): uns 200 ms de CPU cada. A 5 por segundo, um IP ocupa cerca de um núcleo, e uma dúzia de IPs ocupa uma máquina de 12 núcleos. É negação de serviço pela porta da frente, e o limitador por IP também não a segura.

**Morre no:** capítulo 7.

## 2. As sessões vencidas se acumulam

**Onde:** a tabela `sessions` (`UserSession`, em `app/models/session.py`). Só o `SessionRepository.delete_by_token_hash` apaga linha, e só o logout o chama.

**Como se manifesta:** todo login grava uma linha. A vencida para de valer na hora, porque o `user_by_token_hash` filtra `expira_em > func.now()` (o `test_sessao_vencida_e_401` prova). Mas a linha fica. A de quem nunca fez logout também. No banco de dev, agora:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare \
    -c "SELECT count(*) AS linhas, count(*) FILTER (WHERE expira_em <= now()) AS vencidas FROM sessions;"
 linhas | vencidas 
--------+----------
     10 |        1
(1 row)
```

A validade é de 24 horas cravadas. Vinte e quatro horas depois do último login desta tabela, as dez estarão vencidas, e continuam lá. Para a segurança, nada muda. A tabela só cresce. Apagar as vencidas não é trabalho de request nenhuma: é um serviço que roda de tempos em tempos, em segundo plano.

**Morre no:** capítulo 8.

## 3. O saldo é recalculado a cada request

Herdado: era o item 2 da lição 12 do capítulo 5.

**Onde:** `SALDOS` e `GroupRepository.balances`, em `app/repositories/group.py`. Quem chama: o `GroupService.balances` e o `SettlementService.create`.

**Como se manifesta:** como antes. ~10 ms com 2000 despesas, ~70 ms com 20000, a cada `GET` e a cada quitação. O `GET .../balances` foi de duas consultas para três: entrou a da sessão (lição 05), e o `is_member` tomou o lugar do "o grupo existe?" (lição 12). A contagem segue constante. Só a soma pesa.

**Morre no:** capítulo 7.

## 4. Decisões, não defeitos

Estes não morrem em capítulo nenhum. São escolhas, escritas para você poder discordar delas.

| O quê | Onde | Por quê |
|---|---|---|
| Sem login social | `app/routers/auth.py`: só email e senha | O OAuth2 ficou como conceito: um provedor pede serviço externo e fluxo de browser (lição 09). |
| Sem recuperação ou troca de senha, verificação de email ou 2FA | não existem rotas | Cada um é um fluxo inteiro. Consequência concreta: quem esquece a senha perde a conta (lição 03). |
| Usuários antigos sem senha | `User.senha_hash`, anulável, e o `senha_hash is None` do `AuthService.login` | Não há senha honesta para inventar. No banco de dev, seis contas não logam (lição 03). |
| Piso de 8 caracteres | `UserCreate.senha`, em `app/schemas/user.py` | A revisão 4 da SP 800-63B do NIST pede 15 quando a senha é o único fator, o caso daqui. O app segue no 8 da revisão 3 (lição 03). |
| O 422 devolve a senha | o campo `input` da validação padrão do FastAPI, no cadastro e no login | Qualquer 422 pode trazer a senha, inclusive a boa, quando falta outro campo. No login, é a senha da conta. Volta só para quem mandou, mas um proxy que grave respostas em log a guardaria. O conserto é um handler de `RequestValidationError` que tira o `input`, sem dependência nova (lições 03 e 04). |
| Email sem normalização | o `EmailStr` do `UserCreate` e do `LoginIn` | Só o domínio baixa. `ana@example.com` e `Ana@example.com` são duas contas (lições 03 e 04). |
| O cadastro denuncia quem tem conta | `create_user`, em `app/routers/users.py`: `409 email já cadastrado` | Fechar pede verificação por email, fora do escopo (lição 06). |
| A listagem denuncia quem tem conta | `list_users`, em `app/routers/users.py` | Id e nome de todo mundo, para qualquer logado: o app precisa dela para montar grupos. O email não sai (`test_listagem_de_usuarios_nao_mostra_email`) (lição 06). |
| Sessão de validade fixa | `VALIDADE_DA_SESSAO`, em `app/security.py` | 24 horas, sem esticar com o uso e sem refresh token (lições 07 e 09). |
| Sem "sair de todos os dispositivos" | `AuthService.logout` | Apaga só a sessão do token da request. O resto seria um `DELETE` pelo `user_id` (lição 07). |
| Onde o cliente guarda o token | fora do app | O FairFare entrega o token e confere o header. Quem guarda escolhe onde, e herda o dever de não ter XSS (lição 10). |
| Sem cookie, sem `allow_credentials` | o `CORSMiddleware`, em `app/main.py` | Sem cookie, não há CSRF. Se a sessão for para um cookie, o `SameSite` e o token anti-CSRF entram junto (lição 10). |
| O `GET /bookings` mostra quem reservou | `BookingService._to_out` (o `user_nome`) e `BookingService.cancel` | A disponibilidade é pública no app. O preço: quem vê a reserva na listagem ouve "reserva não existe" no `DELETE` (lição 11). |
| Ids sequenciais | o `id` de `Booking` e de `Group`, em `app/models/` | O id novo conta que os anteriores existem. UUID não conserta, porque o id vaza de qualquer jeito. O conserto é a checagem (lições 11 e 12). |
| Sem papéis | `create_resource`, em `app/routers/resources.py`, e o `GroupService` | Qualquer logado cria recurso. Todo membro pode o mesmo que o criador do grupo, e ninguém remove membro (lição 12). |
| Ser adicionado sem consentir | `GroupService.add_member` | Qualquer membro põe qualquer pessoa no grupo, e logo depois lança despesa dividida com ela (lição 12). |
| A despesa falsa do próprio pagador | `ExpenseService.create`, que grava `user.id` como `paid_by` | O app não sabe se o jantar existiu. Garante só que ninguém lança gasto em nome de outro (lição 12). |

## 5. O colateral: o material antigo que chama a API

**Onde:** todo material dos capítulos 1 a 5 que fala com o FairFare pela API: os `curl` das lições e as bancadas. Desde a lição 03, o cadastro pede `senha`. Desde a lição 05, toda rota pede crachá, menos o cadastro e o login. As bancadas atingidas:

- `chapters/02-python-assincrono/bancada/carga.py`, que a lição 09 do capítulo 2 aponta para o `GET /bookings`;
- em `chapters/03-entre-o-cliente-e-o-router/bancada/`: o `carga.py` (lições 02, 05, 08 e 11 do capítulo 3, e 05 do capítulo 4), o `espiao.py` e o `proxy.py` (que repassam ao app o `/users` das lições 01 e 06) e a `pagina/index.html`;
- `chapters/04-o-banco-de-dados-de-verdade/bancada/corrida.py`;
- `chapters/05-relacoes-e-dinheiro/bancada/quitacao.py` e `conta_consultas.py`.

Ficam de fora as que falam com um servidor próprio (`servidor.py`, `eco.py`, `asgi_cru.py`, `cebola.py`), as que falam direto com o banco, e o `Caddyfile` e o `nginx.conf`, que o curso só lê.

**Como se manifesta:** quem só lê leva `401`. Quem começa cadastrando gente leva `422`, porque falta a `senha`. Rodei três delas agora. O `corrida.py` quebra ao ler a resposta do cadastro:

```console
$ uv run python chapters/04-o-banco-de-dados-de-verdade/bancada/corrida.py --rodadas 1
...
KeyError: 'id'
```

O `quitacao.py` diz por quê:

```console
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/quitacao.py
POST /users devolveu 422: {"detail":[{"type":"missing","loc":["body","senha"],"msg":"Field required","input":{"nome":"Ana","email":"ana-bb1f1398@bancada-l11.fairfare.dev"}}]}
```

E o `conta_consultas.py`, que só faz `GET`:

```console
$ uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py
...
httpx2.HTTPStatusError: Client error '401 Unauthorized' for url 'http://bancada/bookings'
```

**Morre no:** em lugar nenhum, de propósito. Reescrever material publicado é mexer no que você pode ter baixado. A regra: o material de um capítulo roda na tag dele (`git checkout v-chapter-05`, por exemplo; nos capítulos 4 e 5, desça o banco antes, e a `ERRATA.md` tem os degraus). A `ERRATA.md` registra isso no fim deste capítulo.

## 6. Ressalvas de medição e de bancada

| O quê | Onde |
|---|---|
| Os números são desta máquina, com 12 núcleos. A direção se repete. Os milissegundos, não. | lições 02, 03 e 06 |
| A bancada do JWT é de brinquedo: só HS256, e só confere `alg`, assinatura e `exp`. A `verificar_ingenua` está errada de propósito. | lição 08 |
| As demos ficaram no banco de dev, e cada lição lista as suas. O grosso: a Ana (265) e o Bruno (266), sem senha, com o grupo 50 e a despesa 86041; onze contas com `cap06` no email (ids 267 a 271 e 281 a 286); o recurso 52 e a reserva 2003; os grupos 51 e 52, com as despesas 86042 e 86043 e as quitações 67 e 68. | lições 01, 03 a 07, 11 e 12 |
| Vários experimentos rodaram com mudanças temporárias, fora do repositório, e cada lição diz quais. Os "antes" das lições 10, 11 e 12 rodaram no uvicorn do commit anterior. | lições 05, 06, 07, 10, 11 e 12 |

## 7. As herdadas

A lição 12 do capítulo 5, e por ela a do capítulo 4, continuam valendo, menos o item 1 (o sem autenticação). O item 2 virou o item 3 daqui. A tabela de decisões de lá segue de pé. O `add_member` ainda traduz **qualquer** `IntegrityError` em "já é membro", e ainda é seguro, porque nenhuma rota apaga grupo nem usuário. Uma decisão de lá ganhou peso: o `GET /groups` sem id não existir é o que deixa o 404 da lição 12 esconder de verdade. Se nascer uma listagem de grupos, ela filtra por membro.

### O "sem autenticação" morreu

Era a entrada 2 da `ERRATA.md`, item 3: "Não existe autenticação. `POST /bookings` aceita qualquer `user_id`". Nasceu no capítulo 1. As lições finais dos capítulos 2 a 5 o carregaram, e o capítulo 5 abriu mais quatro portas com ele.

Morreu aqui, em três partes, como o 2N+1 no capítulo anterior:

- **O conserto:** a `get_current_user`, em `app/dependencies.py`, responde "quem é você" a partir de um token que o banco guarda como sha256 (lições 04 e 05). O `user_id`, o `paid_by` e o `para_user_id` saíram dos schemas e vêm do token (lições 05 e 12).
- **A regra:** em reservas, recursos e grupos, o login é exigido no router inteiro (`dependencies=[Depends(get_current_user)]`), e rota nova ali já nasce protegida. Em `users` e `auth`, que têm as duas rotas públicas, a proteção é rota a rota. A permissão mora no service (lição 12).
- **O guardião:** `test_toda_rota_exige_login_menos_as_publicas`, em `tests/test_auth.py`. Ele lê todas as rotas do OpenAPI e cobra 401 com `WWW-Authenticate: Bearer` de cada uma, menos `POST /users` e `POST /auth/login`. Uma rota nova que nasça aberta, em qualquer router, deixa o teste vermelho.

As quatro portas da lição 12 do capítulo 5, e quem as mantém fechadas:

| A porta | Como fechou | O teste, em `tests/test_permissoes.py` |
|---|---|---|
| `POST .../members` aceitava qualquer um | só membro adiciona | `test_quem_nao_e_membro_recebe_404` |
| `POST .../expenses` aceitava qualquer `paid_by` | quem paga é quem lança | `test_paid_by_e_quem_lanca`, `test_paid_by_no_corpo_e_ignorado` |
| `POST .../settlements` aceitava qualquer par | quem recebe é quem lança | `test_quitacao_e_lancada_por_quem_recebe`, `test_para_user_id_no_corpo_e_ignorado`, `test_devedor_nao_registra_o_proprio_pagamento` |
| `GET .../balances` mostrava qualquer grupo | só membro vê | `test_quem_nao_e_membro_recebe_404` |

A reserva, a dona original do item 3, tem os dela: `test_user_id_no_corpo_e_ignorado` (em `tests/test_auth.py`), `test_cancelar_reserva_alheia_e_404` e `test_404_alheio_e_igual_ao_inexistente`.

E o `curl` que abriu o capítulo, a despesa de R$ 500 "paga pela Ana" lançada por outra pessoa. Na lição 12, ele voltou contra o grupo da Katia. A Mila, de fora:

```console
HTTP/1.1 404 Not Found
date: Sun, 25 Oct 2026 04:04:26 GMT
server: uvicorn
content-length: 30
content-type: application/json

{"detail":"grupo não existe"}
```

O Leo, de dentro, mandando `"paid_by": 284`:

```console
{"id":86042,"group_id":51,"paid_by":285,"descricao":"Jantar que a Katia não pagou","valor":"500.00","criada_em":"2026-10-25T04:04:31.792820Z","partes":[{"user_id":284,"valor":"250.00"},{"user_id":285,"valor":"250.00"}]}
```

O `paid_by` gravado é o dele. E sem crachá, o mesmo `curl` leva `401 {"detail":"Not authenticated"}`.

Uma ressalva honesta: morreu o "sem autenticação", não toda dúvida de autorização. O que sobrou tem nome e endereço, na seção 4. Nenhuma linha dela deixa alguém lançar gasto ou quitação no nome de outro.

### As que sobram

Das três herdadas do capítulo 1, a reserva dupla morreu no capítulo 4, o 2N+1 no 5 e a autenticação aqui. **Não sobra nenhuma.**

## A regra, em uma frase

**Este curso não esconde bugs no código que entrega.** Toda limitação conhecida está escrita no material do capítulo onde ela existe, junto com o capítulo que a resolve. Se você achar no FairFare um defeito que não esteja declarado em lugar nenhum, isso não é um exercício disfarçado: é um erro meu, e vale um issue.

## O que você deve conseguir fazer agora

- Para cada item desta lista, dizer onde ele está e em que capítulo morre. E separar as escolhas, o colateral e as ressalvas, que não morrem em capítulo nenhum.
- Explicar por que o limitador por IP não para a força bruta numa conta só, e o que falta para contar por conta.
- Explicar por que as sessões vencidas são inofensivas para a segurança, e por que alguém precisa apagá-las mesmo assim.
- Dizer o que matou o "sem autenticação", e o que impede uma rota nova de nascer aberta.
