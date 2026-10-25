# Lição 07 — Revogar

Lá na lição 09 do capítulo 0 ficou uma frase: o crachá é "emitido, verificado e revogado". Três promessas. A lição 04 cumpriu a primeira: o login emite um token. A lição 05 cumpriu a segunda: toda request mostra o token, e a dependência confere. Falta a terceira. Um crachá que nunca deixa de valer não é crachá, é chave copiada.

Revogar tem dois jeitos de acontecer. Alguém pede (o **logout**). Ou o tempo passa (a **expiração**). Esta lição faz o primeiro e prova o segundo.

## Logout é apagar uma linha

Pense na portaria de um prédio com uma lista de visitantes. O seu crachá é só um número. Quem decide se ele vale é a lista do porteiro. Para cancelar um crachá, o porteiro não precisa caçar você na rua e tomar o crachá da sua mão. Ele risca o número da lista. Você pode continuar com o plástico no bolso: na próxima vez que mostrar, não passa.

No FairFare, a lista é a tabela `sessions`. Cada login é uma linha, com o sha256 do token (lição 04). A dependência acha o usuário procurando essa linha (lição 05). Então o logout é isto, no `SessionRepository`:

```python
    async def delete_by_token_hash(self, token_hash: str) -> None:
        # Logout é isto: apagar a linha. Sem flush(): um DELETE como este vai direto ao banco,
        # não passa pela fila do add() (lição 07).
        await self.db.execute(delete(UserSession).where(UserSession.token_hash == token_hash))
```

O `create` da lição 04 precisava do `flush()`: o `add()` só põe o objeto numa fila, e o `flush()` manda o `INSERT`. Aqui não tem fila. O `execute` de um `delete()` vira um `DELETE` na hora, dentro da transação aberta.

No `AuthService`, a transação de sempre (a regra do capítulo 5: o service delimita, o repository não comita):

```python
    async def logout(self, token: str) -> None:
        # Uma transação, um DELETE. A sessão mora no servidor, então revogar é esquecê-la.
        async with self.db.begin():
            await self.sessions.delete_by_token_hash(hash_token(token))
```

E a rota, em `app/routers/auth.py`:

```python
# O login é público; o logout, não. Por isso o get_current_user vem aqui, por parâmetro,
# e não no router inteiro.
@router.post("/logout", status_code=204)
async def logout(
    # O eu não é usado no corpo. Ele está aqui para a dependência rodar: token vencido ou
    # desconhecido leva 401 antes de chegar ao DELETE.
    eu: User = Depends(get_current_user),
    # O mesmo bearer do get_current_user: o FastAPI o resolve uma vez só por request.
    cred: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    await AuthService(db).logout(cred.credentials)
```

Três detalhes:

- **Por que as dependências vêm por parâmetro.** Os routers de recursos, reservas e grupos pedem o `get_current_user` no router inteiro (lição 05). O de auth não pode: o `POST /auth/login` mora nele, e é público. Então o logout pede a dependência sozinho.
- **Por que o `eu`, se ninguém usa.** Ele faz a dependência rodar. Sem ela, um token desconhecido chegaria ao `DELETE`, apagaria zero linhas e levaria 204. Com ela, leva 401, como em qualquer outra rota. E o guardião de rotas da lição 05 viu a rota nova sozinho: o `test_toda_rota_exige_login_menos_as_publicas` passou sem que eu tocasse nele.
- **Por que o `bearer` de novo.** O service precisa do token, e o `get_current_user` devolve o usuário, não o token. Pedir o `bearer` outra vez não lê o header duas vezes: é o cache de dependências da lição 05, que entrega o mesmo resultado para quem pedir durante a request.

A request faz duas transações: a de leitura, da dependência, e a do `DELETE`, do service. A dependência fecha a dela antes de o service abrir a sua. É o arranjo da lição 05.

### Pelo uvicorn

Um usuário novo para a demo, o Hugo, no banco de dev. Login, e o `/users/me` com o token:

```console
$ curl -si localhost:8000/users/me -H "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK
date: Sun, 25 Oct 2026 03:02:11 GMT
server: uvicorn
content-length: 57
content-type: application/json

{"id":281,"nome":"Hugo","email":"hugo.cap06@example.com"}
```

A linha dele na tabela:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare -c "SELECT s.id, s.user_id, s.expira_em FROM sessions s JOIN users u ON u.id = s.user_id WHERE u.email = 'hugo.cap06@example.com';"
 id | user_id |           expira_em
----+---------+-------------------------------
  5 |     281 | 2026-10-26 03:02:05.007538+00
(1 row)
```

O logout:

```console
$ curl -si -X POST localhost:8000/auth/logout -H "Authorization: Bearer $TOKEN"
HTTP/1.1 204 No Content
date: Sun, 25 Oct 2026 03:02:11 GMT
server: uvicorn
content-type: application/json
```

204 é "deu certo, e não tenho nada para devolver" (lição 05 do capítulo 0). Logout não tem o que devolver. O mesmo token, de novo:

```console
$ curl -si localhost:8000/users/me -H "Authorization: Bearer $TOKEN"
HTTP/1.1 401 Unauthorized
date: Sun, 25 Oct 2026 03:02:11 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 39
content-type: application/json

{"detail":"token inválido ou vencido"}
```

E a mesma consulta, de novo:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare -c "SELECT s.id, s.user_id, s.expira_em FROM sessions s JOIN users u ON u.id = s.user_id WHERE u.email = 'hugo.cap06@example.com';"
 id | user_id | expira_em
----+---------+-----------
(0 rows)
```

A linha 5 sumiu. O Hugo ainda tem o token, igual ao visitante com o plástico no bolso. Não serve para nada.

Um segundo logout com o mesmo token leva 401, não 204: a dependência roda primeiro e não acha a sessão. É uma escolha. Quem pede logout com um crachá que já não vale recebe a mesma resposta de qualquer rota com crachá inválido.

### Uma sessão por login, não por pessoa

A Ana loga no celular e no notebook. São dois logins, duas linhas (o `test_dois_logins_duas_sessoes` da lição 04). O logout do celular apaga a linha do celular, e só ela:

```python
async def test_logout_de_uma_sessao_nao_derruba_a_outra(pessoa, client):
    # A Ana no celular (ana.client) e no notebook (o client, com o outro token).
    ana = await pessoa("Ana")
    do_notebook = await faz_login(client, ana.email)
    assert (await ana.client.post("/auth/logout")).status_code == 204
    assert (await ana.client.get("/users/me")).status_code == 401
    resp = await client.get("/users/me", headers={"Authorization": f"Bearer {do_notebook}"})
    assert resp.status_code == 200
```

O `WHERE` do `DELETE` é pelo `token_hash`, não pelo `user_id`. Apagar pelo `user_id` seria outra função: "sair de todos os dispositivos". O FairFare não tem. Volta lá embaixo.

### Por que isso foi fácil

Foi fácil porque a lista mora no servidor. O servidor decide, a cada request, se o crachá vale. Riscar da lista é um `DELETE`.

Agora imagine um crachá que carrega a própria validade dentro dele, assinado, e um servidor que confere a assinatura sem consultar lista nenhuma. É o JWT, que a lição 08 monta à mão. Com ele, o servidor não tem linha para apagar. Como se revoga uma coisa assim é a pergunta central da lição 09.

## Expiração: o teste do relógio

O outro jeito de revogar é o tempo. A sessão vale 24 horas (lição 04), e a dependência já confere isso desde a lição 05, no `WHERE`:

```python
            .where(UserSession.token_hash == token_hash, UserSession.expira_em > func.now())
```

Conferir é uma coisa. Provar é outra. E um teste que espera 24 horas não roda nunca.

A saída comum é mexer no relógio. Bibliotecas como o `freezegun` congelam ou adiantam o `datetime.now()` do Python durante o teste. Congelar ou adiantar o relógio depois do login não muda nada aqui. Quem decide se a sessão venceu é o `now()` **do banco** (lição 05), e o Postgres não sabe que o Python mexeu no relógio dele. Congelar no momento do login, num instante de mais de 24 horas atrás, já muda alguma coisa: o `expira_em` sai do `agora` do Python (lição 04), e nasceria vencido. Mas aí o que o teste mexeu de verdade foi o dado, por tabela.

Então o teste não mexe no relógio. Ele mexe no dado. Em vez de levar o presente até o vencimento, traz o vencimento para o passado:

```python
async def test_sessao_vencida_e_401(pessoa, engine_de_teste):
    # O teste do relógio: em vez de esperar 24 h, o vencimento vem para o passado.
    ana = await pessoa("Ana")
    async with engine_de_teste.begin() as conn:
        await conn.execute(text("UPDATE sessions SET expira_em = now() - interval '1 second'"))
    resp = await ana.client.get("/users/me")
    assert (resp.status_code, resp.json()) == (401, {"detail": "token inválido ou vencido"})
    assert resp.headers["www-authenticate"] == "Bearer"
```

O `UPDATE` usa o mesmo `now()` que a dependência vai usar. Os dois lados olham o mesmo relógio, então a sessão está vencida por um segundo, sem margem para dúvida.

Escrevi os cinco testes desta lição antes do código. Quatro ficaram vermelhos, e este passou de primeira:

```console
PASSED tests/test_auth.py::test_sessao_vencida_e_401
FAILED tests/test_auth.py::test_logout_revoga_o_token - assert 404 == 204
FAILED tests/test_auth.py::test_logout_de_uma_sessao_nao_derruba_a_outra - as...
FAILED tests/test_auth.py::test_logout_sem_token_e_401 - AssertionError: asse...
FAILED tests/test_auth.py::test_reloga_depois_do_logout_e_da_expiracao - asse...
4 failed, 1 passed, 30 deselected in 1.02s
```

É o esperado: a conferência existe desde a lição 05, e o 404 dos outros é a rota de logout que ainda não existia. Mas teste que nunca ficou vermelho não provou nada. Tirei o `expira_em > func.now()` do `WHERE`, só para ver, e rodei de novo:

```console
$ uv run pytest -q tests/test_auth.py -k "vencida"
...
>       assert (resp.status_code, resp.json()) == (401, {"detail": "token inválido ou vencido"})
E       AssertionError: assert (200, {'id': ...example.com'}) == (401, {'detai... ou vencido'})
E
E         At index 0 diff: 200 != 401
E         Use -v to get more diff

tests/test_auth.py:312: AssertionError
=========================== short test summary info ============================
FAILED tests/test_auth.py::test_sessao_vencida_e_401
1 failed, 34 deselected in 0.33s
```

A sessão vencida entrando com 200. Condição de volta, verde. Agora ele trava a conferência: quem apagar aquela condição sem querer descobre na hora.

### Logar de novo

Depois de um logout, ou de um vencimento, a pessoa loga de novo e precisa ganhar um token novo que funciona, sem herdar nada do velho. O `test_reloga_depois_do_logout_e_da_expiracao` faz os dois caminhos em sequência: logout, login, o token novo dá 200 e o velho 401. Depois vence o segundo, loga de novo, e o terceiro dá 200. No fim, o banco tem 2 linhas, e só 1 válida. A do logout foi apagada. A vencida ficou.

Ficou. Guarde isso.

## O lixo

O logout apaga. A expiração não apaga nada: ela só faz o `WHERE` parar de achar a linha.

No banco de dev, forcei uma vencida: loguei o Hugo de novo e rodei o mesmo `UPDATE` do teste, só na sessão dele. O `/users/me` com esse token deu 401 `token inválido ou vencido`. E a tabela:

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare -c "SELECT count(*) FROM sessions WHERE expira_em < now();"
 count
-------
     1
(1 row)
```

```console
$ docker compose exec -T postgres psql -U fairfare -d fairfare -c "SELECT id, user_id, criada_em, expira_em FROM sessions ORDER BY id;"
 id | user_id |           criada_em           |           expira_em
----+---------+-------------------------------+-------------------------------
  1 |     268 | 2026-10-25 01:59:47.062586+00 | 2026-10-26 01:59:47.062586+00
  2 |     269 | 2026-10-25 02:03:47.090591+00 | 2026-10-26 02:03:47.090591+00
  3 |     270 | 2026-10-25 02:19:06.24877+00  | 2026-10-26 02:19:06.24877+00
  4 |     271 | 2026-10-25 02:44:07.008903+00 | 2026-10-26 02:44:07.008903+00
  6 |     281 | 2026-10-25 03:02:20.983081+00 | 2026-10-25 03:02:20.091586+00
(5 rows)
```

A linha 6 venceu e continua lá. As linhas 1 a 4 são das demos das lições anteriores: ninguém fez logout delas. Amanhã elas vencem, e também ficam. A linha 5, do primeiro login do Hugo, não aparece: foi a do logout.

Isso é perigoso? Não. A consulta da dependência ignora linha vencida, e a linha só guarda o sha256 do token. Uma sessão vencida esquecida na tabela não abre porta nenhuma.

Mas cresce. Cada login é uma linha nova, e a maioria das pessoas nunca clica em "sair". Num app com movimento, a tabela vira um cemitério de crachás vencidos. A limpeza é um `DELETE FROM sessions WHERE expira_em < now()` rodando de tempos em tempos, longe das requests. Isso é **trabalho em segundo plano**, e é o assunto do capítulo 8.

## O que fica declarado

- **As sessões vencidas e as de quem nunca fez logout ficam na tabela.** Inofensivas para a segurança, mas a tabela cresce. A limpeza é um job em segundo plano, do capítulo 8.
- **Não existe "sair de todos os dispositivos".** O logout apaga a sessão do token que veio na request, e só ela. Seria um `DELETE` pelo `user_id`. Fica fora por escolha, não por limitação.
- **Não existe renovação.** A sessão vale 24 horas a partir do login, e não estica com o uso. Quem usa o app o dia inteiro faz login de novo no dia seguinte. Também é escolha deste capítulo.

## O que você deve conseguir fazer agora

- Revogar uma sessão à mão no `psql`, com um `DELETE` (ou um `UPDATE` no `expira_em`), e ver a próxima request com aquele token levar 401.
- Explicar por que o teste da expiração mexe no `expira_em` do banco em vez de esperar 24 horas, e por que congelar o relógio do Python não adiantaria.
- Dizer o que acontece com uma sessão vencida que ninguém apaga: por que ela não abre porta nenhuma, e por que, mesmo assim, alguém precisa limpar.
