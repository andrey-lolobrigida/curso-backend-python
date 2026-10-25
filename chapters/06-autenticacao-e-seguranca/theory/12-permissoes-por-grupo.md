# Lição 12 — Permissões por grupo

A lição 11 fez a segunda pergunta, "você pode fazer isso?", numa rota só. Esta faz a mesma pergunta nas cinco rotas de um grupo que já existe. E fecha o `curl` que abriu o capítulo.

## De volta ao `curl` da lição 01

No banco de dev, criei três usuários novos, com emails próprios desta demo: a Katia (id 284), o Leo (285) e a Mila (286). Cada um fez login e guardou o token numa variável do shell. A Katia criou um grupo:

```console
$ curl -s -X POST localhost:8000/groups -H "Authorization: Bearer $KATIA" \
    -H 'content-type: application/json' -d '{"nome": "Casa da praia"}'
{"id":51,"nome":"Casa da praia","membros":[{"user_id":284,"nome":"Katia"}]}
```

Repare no `membros`: a Katia já está lá. Até a lição 11, um grupo novo nascia vazio. Depois ela adicionou o Leo. A Mila ficou de fora.

Agora a Mila manda o `curl` da lição 01, com o crachá **dela**:

```console
$ curl -si -X POST localhost:8000/groups/51/expenses -H "Authorization: Bearer $MILA" \
    -H 'content-type: application/json' \
    -d '{"paid_by": 284, "descricao": "Jantar que a Katia não pagou", "valor": "500.00"}'
HTTP/1.1 404 Not Found
date: Sun, 25 Oct 2026 04:04:26 GMT
server: uvicorn
content-length: 30
content-type: application/json

{"detail":"grupo não existe"}
```

`404`. Para a Mila, o grupo 51 não existe. A mesma request no grupo 999999, que nunca existiu, saiu idêntica: o mesmo status, o mesmo corpo, o mesmo `content-length: 30`. E sem crachá nenhum, como na lição 01, o FairFare responde `401 {"detail":"Not authenticated"}` desde a lição 05.

Só que a lição 01 tinha um segundo buraco: o `paid_by` vinha do corpo. Um membro podia lançar despesa em nome de outro. O Leo tenta:

```console
$ curl -si -X POST localhost:8000/groups/51/expenses -H "Authorization: Bearer $LEO" \
    -H 'content-type: application/json' \
    -d '{"paid_by": 284, "descricao": "Jantar que a Katia não pagou", "valor": "500.00"}'
HTTP/1.1 201 Created
date: Sun, 25 Oct 2026 04:04:31 GMT
server: uvicorn
content-length: 220
content-type: application/json

{"id":86042,"group_id":51,"paid_by":285,"descricao":"Jantar que a Katia não pagou","valor":"500.00","criada_em":"2026-10-25T04:04:31.792820Z","partes":[{"user_id":284,"valor":"250.00"},{"user_id":285,"valor":"250.00"}]}
```

`201`, mas olhe o `paid_by`: **285**, o Leo. O `284` do corpo foi descartado. O `ExpenseCreate` não tem mais o campo, e o Pydantic joga fora o que o schema não declara. Quem pagou é quem está no token. O cliente antigo que ainda manda o `paid_by` não quebra, e também não manda.

## Ser membro é a regra

Lembra da festa no 302, na lição 01? O porteiro confere o documento. Lá em cima, o dono da festa confere a lista de convidados. No FairFare, o porteiro é a `get_current_user`, desde a lição 05. A lista de convidados é a tabela `group_members`, desde o capítulo 5. Faltava alguém conferir a lista.

Agora o rigor. Toda rota de um grupo que já existe pergunta se quem pede é membro:

| Rota | Regra |
|---|---|
| `POST /groups` | Quem cria entra como membro, na mesma transação |
| `GET /groups/{id}`, `GET /groups/{id}/balances` | Só membros |
| `POST /groups/{id}/members` | Só membros. Qualquer membro adiciona qualquer pessoa |
| `POST /groups/{id}/expenses` | Só membros. Quem paga é quem lança |
| `POST /groups/{id}/settlements` | Só membros. Quem recebe é quem lança |

A primeira linha é obrigatória por causa das outras. Sem ela, a Katia criaria o grupo 51 e levaria 404 ao abrir o grupo que acabou de criar.

E a terceira linha tinha uma surpresa. Escrevi os testes antes do código, e um deles era a Carla, de fora, se adicionando ao grupo da Ana. Antes do conserto, ele falhou assim:

```
E       assert 201 == 404
```

`201`. A Carla entrava sozinha em qualquer grupo. Bastava saber o id. E, uma vez dentro, viraria membro de verdade para todas as outras regras.

Quem é de fora recebe **404**, com o critério da lição 11. Lá, o 404 da reserva alheia tinha um preço: o `GET /bookings` mostra a reserva que o `DELETE` diz não existir. Aqui não tem. O FairFare não tem rota que liste grupos, e nenhuma rota de grupo conta a quem é de fora que um grupo existe, fora o que o id sequencial já conta, como a lição 11 declarou para as reservas: quem cria o grupo 53 fica sabendo que os grupos 1 a 52 existem. Tirando isso, **aqui o 404 esconde de verdade.**

E, como na lição 11, a defesa só vale se a resposta for igual em tudo. O teste compara as cinco rotas com um grupo que não existe:

```python
@pytest.mark.parametrize(
    "metodo, caminho, corpo",
    [
        ("get", "/groups/{g}", None),
        ("get", "/groups/{g}/balances", None),
        ("post", "/groups/{g}/members", {"user_id": "{carla}"}),
        ("post", "/groups/{g}/expenses", {"descricao": "x", "valor": "10.00"}),
        ("post", "/groups/{g}/settlements", {"de_user_id": "{ana}", "valor": "1.00"}),
    ],
)
async def test_quem_nao_e_membro_recebe_404(pessoa, metodo, caminho, corpo):
    # A Carla, de fora, pede no grupo da Ana. A resposta tem de ser idêntica à de um grupo
    # que não existe: qualquer diferença contaria à Carla que o grupo existe (lição 11).
    ana = await pessoa("Ana")
    carla = await pessoa("Carla")
    grupo = await cria_grupo(ana.client)
    ids = {"{ana}": ana.id, "{carla}": carla.id}
    if corpo is not None:
        # Os ids entram como int: uma string "{ana}" levaria 422 no schema, antes do service.
        corpo = {campo: ids.get(valor, valor) for campo, valor in corpo.items()}

    do_grupo = await carla.client.request(metodo, caminho.format(g=grupo["id"]), json=corpo)
    inexistente = await carla.client.request(metodo, caminho.format(g=999), json=corpo)

    assert do_grupo.status_code == inexistente.status_code == 404
    assert do_grupo.json() == inexistente.json() == {"detail": "grupo não existe"}
```

A ordem das checagens segue a regra da lição 11. No `add_member`, o "quem pede é membro?" vem antes do "o usuário alvo existe?". Primeiro "é seu?", e só depois o app responde qualquer outra coisa. Quem é de fora ouve uma frase só: `"grupo não existe"`.

## Quem ganha com a mentira?

Tirar o `paid_by` do corpo resolve a despesa. Mas e a quitação? Ela tem dois ids, `de_user_id` (quem pagou) e `para_user_id` (quem recebeu). Qual dos dois sai do token?

Um critério ajuda: **para cada fato que o cliente afirma, pergunte quem ganha se ele for mentira.** Quem ganha é justamente quem não deve poder afirmar sozinho. Quem perde é quem tem motivo para só afirmar a verdade.

Veja o estrago primeiro. Rodei isto no uvicorn do commit da lição 11, num grupo novo (o 52). O Leo pagou R$ 500 de mercado, e a Katia ficou devendo R$ 250. Ela manda:

```console
$ curl -si -X POST localhost:8000/groups/52/settlements -H "Authorization: Bearer $KATIA" \
    -H 'content-type: application/json' \
    -d '{"de_user_id": 284, "para_user_id": 285, "valor": "250.00"}'
HTTP/1.1 201 Created
date: Sun, 25 Oct 2026 04:05:35 GMT
server: uvicorn
content-length: 118
content-type: application/json

{"id":68,"group_id":52,"de_user_id":284,"para_user_id":285,"valor":"250.00","criada_em":"2026-10-25T04:05:35.597271Z"}
```

Saldos: Katia `0.00`, Leo `0.00`. Ninguém pagou nada. A dívida sumiu porque a devedora disse "paguei".

Aplique o critério. O fato é "a Katia pagou o Leo". Se for mentira, quem ganha é a Katia, e quem perde é o Leo. Então quem registra o pagamento é **quem recebe**. O `para_user_id` sai do corpo e vem do token. Fica só o `de_user_id`.

No código desta lição, a Katia manda o mesmo `curl` no grupo 51:

```console
$ curl -si -X POST localhost:8000/groups/51/settlements -H "Authorization: Bearer $KATIA" \
    -H 'content-type: application/json' \
    -d '{"de_user_id": 284, "para_user_id": 285, "valor": "250.00"}'
HTTP/1.1 422 Unprocessable Entity
date: Sun, 25 Oct 2026 04:04:50 GMT
server: uvicorn
content-length: 53
content-type: application/json

{"detail":"ninguém quita uma dívida consigo mesmo"}
```

O `285` caiu. Quem recebe é quem está no token, a própria Katia. O pedido virou "a Katia pagou a Katia". E o Leo, que recebeu de verdade, registra com `{"de_user_id": 284, "valor": "250.00"}`: `201`, e os dois saldos vão a zero.

Agora o detalhe que fecha a regra. Tudo o que a Katia consegue lançar é "eu recebi de alguém". Receber nunca apaga dívida de quem recebe: é dinheiro que entrou no bolso dela, e o saldo dela só desce. Além disso, a regra dos dois lados, do capítulo 5, exige que o outro deva e que ela tenha a receber. Sobra um caminho só: `de_user_id` igual a ela mesma. Esse fica barrado no service:

```python
            if data.de_user_id == user.id:
                raise SettlementToSelfError
```

Até a lição 11, essa regra morava num `model_validator` do schema, que comparava os dois ids do corpo. A lição 11 do capítulo 5 descreve esse validador. Com um id só no corpo, o schema não tem com o que comparar: quem pede, só o service sabe. Testei sem essas duas linhas (só na minha máquina). O teste do devedor, com o Bruno no papel da Katia, ainda levou 422, mas com `"quem paga precisa ser membro"`. Com os dois ids iguais, o `lock_members` tranca uma linha só, e o erro sai pelo motivo errado. O Bruno é membro. A checagem existe para a recusa dizer a verdade. O `CHECK` do banco, do capítulo 5, continua de guarda embaixo.

E a despesa? Aplique o mesmo critério ao "o Leo pagou o jantar". Se for mentira, quem ganha é o Leo, e quem perde são os participantes. O critério pediria que eles confirmassem. O FairFare não faz isso: confirmar despesa é um fluxo de aprovação, que este capítulo não tem. O que a regra garante é menos, e vale dizer exatamente o quê: **ninguém lança gasto em nome de outro**. A mentira, se houver, sai assinada pelo token de quem mentiu.

## A checagem mora no service

Por que não uma dependência `exige_membro` no router, ao lado da `get_current_user`? Três motivos.

Ela duplicaria consulta. A dependência perguntaria ao banco "é membro?", e o service perguntaria de novo, porque precisa dos membros para trabalhar. O `get` já carrega os membros, e a despesa já lê os `member_ids` para conferir os participantes.

Ela separaria a regra da operação. Na quitação, a checagem acontece dentro da transação do service, antes do cadeado. A dependência rodaria antes, numa transação de leitura própria, como a da lição 05. E o "membro" muda de rota para rota: na despesa, quem pede precisa ser membro e os participantes também; na quitação, quem pede e quem pagou.

E é regra de domínio, não de HTTP. É o terceiro tipo de "não pode" da lição 09 do capítulo 1. Qualquer outro caminho que um dia chame o service, sem passar por HTTP, passa pela mesma regra. Uma dependência do router, ele pularia.

A dependência do router segue respondendo uma pergunta só: quem é você.

## A contagem não subiu

Os guardiões do N+1 ficaram onde estavam: 4 consultas no `GET /groups/{id}`, 3 no `GET .../balances`. Testei o jeito ingênuo (só na minha máquina): uma consulta "é membro?" no começo do `get`, e no `balances` ao lado do "o grupo existe?". Os dois guardiões caíram:

```
E       assert 5 == 4
E       assert 4 == 3
```

O conserto é não perguntar o que já se sabe. No `get`, os membros já vieram com o grupo, e conferir é olhar a lista em Python:

```python
        if group is None or user.id not in {m.user_id for m in group.membros}:
            raise GroupNotFoundError
```

No `balances`, o "o grupo existe?" saiu, e entrou o `is_member` no lugar dele:

```python
    async def is_member(self, group_id: int, user_id: int) -> bool:
        # Uma consulta. Grupo que não existe não tem membro nenhum: False, como o de fora.
        return await self.db.scalar(
            select(exists().where(GroupMember.group_id == group_id, GroupMember.user_id == user_id))
        )
```

Uma consulta responde as duas perguntas. Grupo que não existe não tem membros, então dá `False`, igual ao de fora. É por isso que os dois casos caem no mesmo 404 sem esforço nenhum. O `exists` do repository ficou sem quem o chamasse, e saiu. Na despesa, os `member_ids` já respondiam tudo, e o "o grupo existe?" saiu sem substituto: uma consulta a menos.

A suíte passou de 118 para 129 testes. Os do capítulo 5 mudaram pouco: os helpers de `tests/apoio.py` já recebiam o `client` de quem age desde a lição 05, e as quitações já saíam do client de quem recebe. Só os campos saíram do corpo. O teste das quitações em direções opostas segue passando 10 vezes em 10.

## O que fica declarado

- **Qualquer membro adiciona qualquer pessoa, sem pedir o consentimento dela.** E pode, logo depois, lançar uma despesa dividida com ela. Convite com aceite fica fora deste capítulo.
- **Não há papéis.** Nenhum "dono do grupo", e todo membro pode o mesmo que o criador. Também não existe sair do grupo nem remover membro. E qualquer pessoa logada cria recurso.
- **Os ids de grupo são sequenciais**, como os de reserva na lição 11. O id que o `POST /groups` devolve conta que os anteriores existem. O 404 esconde o resto: nome, membros, saldos.
- **Uma despesa falsa lançada pelo próprio pagador continua possível.** O app não sabe se o jantar existiu. O que mudou é que ela sai em nome de quem a lançou, e não de outra pessoa.
- **A demo ficou no banco de dev:** a Katia (284), o Leo (285) e a Mila (286). No grupo 51, a despesa 86042 e a quitação 67. No grupo 52, do "antes", a despesa 86043 e a quitação 68, a mentira da Katia que o código da lição 11 aceitou.

## O que você deve conseguir fazer agora

- Aplicar "quem ganha com a mentira?" a uma rota nova. Por exemplo, `PATCH /groups/{id}/expenses/{id}`, que muda o valor de uma despesa: quem pode editar, e quem perde se a edição for mentira?
- Explicar por que a quitação é lançada por quem recebe, e não por quem paga.
- Dizer por que a checagem de membro mora no service, e não numa dependência do router.
- Explicar por que trocar o "o grupo existe?" pelo "é membro?" não aumenta o número de consultas.
