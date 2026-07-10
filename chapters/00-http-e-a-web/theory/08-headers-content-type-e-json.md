# Lição 08 — Headers, Content-Type e JSON

Vamos começar pelo erro — é mais educativo que o acerto. Mande uma reserva para o servidor, com um JSON impecável no corpo, mas sem anunciar o formato:

```console
$ curl -i -X POST localhost:8000/reservas -d '{"quadra_id": 1, "quem": "ana"}'
HTTP/1.1 415 Unsupported Media Type

{
  "erro": "mande Content-Type: application/json"
}
```

O corpo estava perfeito. A recusa não foi pelo conteúdo — foi pela **etiqueta ausente**.

## O corpo é só bytes; o header dá o significado

Para o HTTP, o corpo de uma mensagem é uma sequência de bytes sem opinião. Aqueles mesmos bytes podem ser JSON, um formulário, XML, uma foto de capivara. Quem diz como interpretá-los é o header **`Content-Type`** — o rótulo no pote: sem ele, você não sabe se o pó branco é açúcar ou sal, e um servidor prudente se recusa a provar.

Detalhe do exemplo acima: quando você usa `-d`, o curl educadamente preenche um `Content-Type` — mas ele chuta `application/x-www-form-urlencoded` (o formato de formulários web antigos). O anúncio *errado* é tão inútil quanto nenhum. A versão que funciona anuncia certo:

```console
$ curl -i -X POST localhost:8000/reservas \
    -H "Content-Type: application/json" -d '{"quadra_id": 1, "quem": "ana"}'
HTTP/1.1 201 Created
Location: /reservas/1
```

Esses rótulos (`application/json`, `text/html`, `image/png`...) são os **media types** — um catálogo padronizado de formatos.

O `Content-Type` trabalha nos **dois sentidos**: você anuncia o que manda; o servidor anuncia o que devolve (as respostas do nosso servidor sempre trazem `Content-Type: application/json; charset=utf-8` — confira num `curl -i` qualquer). Existe também o header `Accept`, com que o cliente diz o que *aceita receber de volta* — negociação fina que raramente usaremos, mas você vai reconhecê-la nas linhas `>` do curl (`Accept: */*` = "aceito qualquer coisa").

## JSON, a língua franca

Nos anos 2000, serviços trocavam XML — verboso, cheio de cerimônia. O JSON (*JavaScript Object Notation*) venceu por três virtudes: **legível por humanos**, **um punhado de tipos simples que todas as linguagens têm**, e **parser em todo lugar**.

O mapa JSON ↔ Python, que você vai atravessar milhares de vezes:

| JSON | Python |
|------|--------|
| `{"chave": "valor"}` (object) | `dict` |
| `[1, 2, 3]` (array) | `list` |
| `"texto"` (string) | `str` |
| `42`, `3.14` (number) | `int`, `float` |
| `true` / `false` | `True` / `False` |
| `null` | `None` |

E as pegadinhas de quem chega do Python: aspas **sempre duplas**; `True` com maiúscula não existe (`true`); vírgula sobrando depois do último item é erro. É por isso que `str(dicionario)` **não** produz JSON — produz a sintaxe do Python, com aspas simples, que qualquer parser JSON cospe de volta. O tradutor oficial é o módulo `json` (`json.dumps` para gerar, `json.loads` para ler). Guarde essa; ela morde no exercício 3.

## Uma rachadura para lembrar depois

Olhe de novo a tabela: number → `int`, `float`. O JSON tem *um* tipo numérico, e ele não sabe nada de precisão decimal. `80.10` de preço pode virar `80.09999999...` num float — e float com dinheiro é receita de centavos sumindo em extratos.

Não vamos resolver isso agora; só fincar a bandeira: **dinheiro não é float**. Quando o app de despesas compartilhadas nascer e começarmos a dividir contas (capítulo 4), essa rachadura vira cratera — de propósito, para você ver o desastre antes da solução.

## O que você deve conseguir fazer agora

- Montar de cabeça um `curl -X POST` completo (com `-H` e `-d`) que devolve 201 no nosso servidor — e dizer qual status volta se remover o `-H`.
- Explicar por que o servidor recusou um corpo JSON perfeitamente válido.
- Traduzir sem consultar: `null`, `true`, array, object → seus equivalentes Python.
- Explicar por que `str(dicionario)` não serve como corpo JSON.