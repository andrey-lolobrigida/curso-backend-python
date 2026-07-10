# Lição 07 — URLs por dentro

Você já usa URLs há uma década. Esta lição é para que você nunca mais *leia* uma sem ver as engrenagens. Vamos abrir uma:

```
http://localhost:8000/quadras?esporte=tenis
\__/   \_______/ \__/\______/ \___________/
  |        |       |     |          |
esquema   host   porta caminho  query string
```

- **Esquema** — o protocolo da conversa: `http`, `https` (o mesmo HTTP, criptografado — capítulo 3), e primos como `ftp` que você raramente verá.
- **Host** — o nome (ou IP) de quem atende. O DNS da lição 02 trabalha aqui.
- **Porta** — o apartamento. Omitida = padrão do esquema (80 para http, 443 para https).
- **Caminho** — *qual recurso* você quer.
- **Query string** — tudo depois do `?`: refinamentos do pedido, em pares `chave=valor` separados por `&`.

(Existe ainda o **fragmento** — o `#secao-3` no fim de algumas URLs. Curiosidade importante: ele **nunca chega ao servidor**. É uso interno do navegador, tipo "role até esse pedaço da página". Se seu backend tentar ler o fragmento, vai ler o vazio.)

## Caminho identifica, query refina

A distinção que você vai usar todos os dias:

O **caminho** aponta para o recurso. `/quadras` é a coleção; `/quadras/2` é *aquela* quadra:

```console
$ curl -s localhost:8000/quadras/2
{
  "id": 2,
  "nome": "Ginasio Azul",
  "esporte": "basquete",
  "preco_hora": 120
}
```

A **query string** modifica o pedido sem mudar de recurso — filtros, ordenação, paginação:

```console
$ curl -s "localhost:8000/quadras?esporte=tenis"
[
  { "id": 1, "nome": "Quadra Central", ... },
  { "id": 3, "nome": "Saibro do Fundo", ... }
]
```

Continua sendo a coleção `/quadras` — só que peneirada. A regra de bolso: **se identifica, vai no caminho; se refina, vai na query.** (Aspas no comando: no seu terminal, `?` e `&` têm significado próprio; as aspas impedem o shell de se meter na conversa.)

## Nem tudo pode viajar cru

URLs têm alfabeto restrito. Espaços, acentos e símbolos como `&` ou `?` *dentro de um valor* precisam ser codificados — é o **percent-encoding**: o byte vira `%XX`. Um espaço vira `%20`; um `ê` (em UTF-8) vira `%C3%AA`.

E aqui, um erro instrutivo. Tente filtrar por "tênis", com acento:

```console
$ curl -s "localhost:8000/quadras?esporte=t%C3%AAnis"
[]
```

Lista vazia. A URL estava *válida*, corretamente codificada... e inútil: os dados do servidor dizem `tenis`, sem acento, e `tênis != tenis`. Duas lições numa: (1) encoding resolve o transporte, não o significado; (2) servidores comparam strings exatas — o "quase igual" humano não existe aqui.

## O dialeto que vamos falar

Repare no padrão das rotas do mini-servidor — ele não é acidente, é o dialeto que o curso inteiro vai usar:

- Recursos em **substantivos no plural**: `/quadras`, `/reservas`. Nunca `/getQuadras` — o verbo já vai no método.
- **Id no caminho**: `/quadras/2`, `/reservas/1`.
- **Filtros na query**: `/quadras?esporte=tenis`.

Há quem chame esse estilo de "RESTful" e há quem escreva teses raivosas sobre o que REST significa de verdade. Não vamos entrar nessa briga: para nós é só uma convenção consistente que qualquer dev de backend reconhece de longe.

## O que você deve conseguir fazer agora

- Decompor `https://api.exemplo.com/grupos/7/reservas?mes=2026-07&ordem=data` em todas as suas partes (inclusive a porta invisível).
- Decidir "caminho ou query?" para: o id de uma reserva; um filtro de esporte; um critério de ordenação.
- Explicar por que `curl` precisa de aspas em URLs com `?` e `&`.
- Explicar o que `%20` e `%C3%AA` são — e por que o filtro por "tênis" voltou vazio mesmo com a URL perfeita.