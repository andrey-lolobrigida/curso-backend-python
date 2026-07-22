# Lição 04 — Schemas: a porta de entrada aprende a dizer não

## A dor, revisitada

Na lição passada você criou este usuário — e o FairFare agradeceu:

```console
$ curl -s -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{"nome": 42}'
{"id":2,"nome":42}
```

Nome numérico, email inexistente, `201 Created`. A culpa era da assinatura `user: dict`: aceitamos "qualquer JSON" e empurramos o problema para o futuro. Hoje a porta aprende a dizer não.

## Schema = o contrato da porta

Pense na entrada de uma festa com lista: o segurança não lê seu currículo nem julga seu caráter — ele confere **nome na lista e documento com foto**. Formato certo, entra; formato errado, nem chega no salão.

Agora o rigor. Um **schema** é uma classe que declara a forma exata dos dados: quais campos existem, de que tipo, quais são obrigatórios. No FastAPI, schemas são classes **Pydantic** — e quando um schema aparece como parâmetro da rota, o framework valida o corpo da request **antes da sua função rodar**. Dado torto não encosta no seu código.

Isto substituiu o `user: dict`:

```python
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    nome: str
    email: EmailStr


class UserOut(BaseModel):
    id: int
    nome: str
    email: str
```

E a rota agora declara o que aceita e o que devolve:

```python
@app.post("/users", status_code=201, response_model=UserOut)
def create_user(user: UserCreate):
    ...
```

De novo os type hints trabalhando: `nome: str` não é anotação decorativa, é regra executável. E `EmailStr` é um tipo do Pydantic que valida formato de email (ele vive no pacote extra `email-validator`, que adicionamos com `uv add email-validator`). Dentro da função, `user` não é mais um dicionário às cegas: é um objeto com `.nome` e `.email`, garantidos e tipados.

## 422: o não que ensina

Repita o ataque da lição 03:

```console
$ curl -s -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{"nome": 42}'
{"detail":[
  {"type":"string_type","loc":["body","nome"],"msg":"Input should be a valid string","input":42},
  {"type":"missing","loc":["body","email"],"msg":"Field required","input":{"nome":42}}
]}
```

Status `422 Unprocessable Content` — família 4xx, "o erro é seu" (capítulo 0, lição 05). Mas olhe o corpo com carinho, porque ele é diagnóstico, não muro:

- **`loc`** aponta o endereço do problema: no corpo, campo `nome`.
- **`msg`** diz o que está errado, em português de máquina: deveria ser string.
- **`input`** devolve o que você mandou, para não restar dúvida.

E repare: são **dois** erros, reportados de uma vez. O Pydantic confere o payload inteiro em vez de desistir no primeiro problema — quem consome sua API conserta tudo numa rodada só. Compare com o silêncio educado da v0, que aceitava tudo e deixava a bomba armada.

## Entrada ≠ saída

Por que duas classes, `UserCreate` e `UserOut`, para o "mesmo" usuário?

Porque são contratos de portas diferentes. Quem **chega** não tem `id` — é o servidor que o atribui; aceitar um `id` vindo de fora seria deixar o cliente escolher a própria chave. Quem **sai** tem `id` — o cliente precisa dele para buscar o usuário depois.

O `response_model=UserOut` faz o caminho da volta: tudo que a função retorna passa pelo filtro do schema de saída. Hoje ele parece redundante — devolvemos exatamente esses campos. Mas ele é um **filtro**, e filtros pagam quando algo tenta passar. Um dia esse usuário vai ter campos internos que não são da conta de ninguém, e essa linha vai ser a diferença entre "campo interno" e "vazamento". Guarde a frase: *um dia um campo interno vai tentar escapar.*

Abra o `/docs` de novo, aliás: a documentação do POST agora mostra o formato exato do corpo, exemplo incluído. Os schemas alimentam a documentação de graça — segundo pagamento dos type hints.

## O que o schema NÃO resolve

Experimente criar a Ana duas vezes:

```console
$ curl -s -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{"nome": "Ana", "email": "ana@example.com"}'
{"id":1,"nome":"Ana","email":"ana@example.com"}
$ curl -s -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{"nome": "Ana", "email": "ana@example.com"}'
{"id":2,"nome":"Ana","email":"ana@example.com"}
```

Duas Anas, mesmo email, tudo `201`. E o schema está *certo* em deixar passar: `ana@example.com` tem forma perfeita de email. "Este email já está cadastrado" não é uma pergunta sobre **forma** — é uma pergunta sobre **o estado do mundo**, e responder exige olhar os dados que já existem. Validação de forma mora na porta; regra de negócio mora em outro lugar, que ainda nem construímos. Essa distinção vai virar uma lição inteira (a 09). Por ora, grave: **schema valida forma, não fatos**.

(E sim: o FairFare continua com amnésia — reinicie o servidor e as duas Anas somem. A cura é a próxima lição.)

## O que você deve conseguir fazer agora

- Escrever de cabeça um schema `ResourceCreate` com `nome: str` — sem olhar o de usuário.
- Prever o status code destes três payloads no `POST /users`:
  - `{"nome": "Bia", "email": "bia@example.com"}` → ?
  - `{"nome": "Bia"}` → ?
  - `{"nome": "Bia", "email": "bia.example.com"}` → ?
- Ler um erro 422 e apontar campo e problema sem googlar.
- Explicar por que `UserCreate` e `UserOut` são classes separadas.
