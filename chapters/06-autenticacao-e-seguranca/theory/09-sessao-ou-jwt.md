# Lição 09 — Sessão ou JWT?

Lá na lição 09 do capítulo 0 ficou uma frase: como o crachá é emitido, verificado e revogado, "sessões vs JWTs", é o coração do capítulo 6. O capítulo 2 prometeu a mesma briga, "sessões contra tokens". As lições 04 a 07 montaram a sessão. A lição 08 montou o JWT. Agora os dois vão para a balança.

A lição 08 terminou com o ato 6: o cliente apagou o token, e a cópia continuou passando até o `exp`. E com uma pergunta: quem revoga um JWT?

## Quem revoga um JWT?

Volte à portaria da lição 07. Com sessão, o porteiro tem uma lista e risca o seu número. Com JWT, não há lista. O porteiro olha o selo do ingresso, e o selo continua legítimo. Para barrar um ingresso válido, ele precisaria lembrar de alguma coisa.

E é exatamente isso que as duas saídas conhecidas fazem. Cada uma tem um preço.

**Validade curta + refresh token.** O crachá do dia a dia (o *access token*) vale poucos minutos. Junto com ele, o login entrega um segundo token, de vida longa, o *refresh token*, que só serve para pedir um crachá novo quando o antigo vence. Para o logout funcionar, o servidor guarda o refresh token e o apaga no logout. Repare no que acabou de nascer: uma linha no servidor, consultada para renovar, apagada para revogar. É uma sessão com outro nome. E a janela não fecha, só encolhe: o access token copiado continua passando até o `exp` dele.

**Lista de revogados.** Cada JWT ganha um id próprio (o padrão prevê um campo para isso, o `jti`). No logout, o servidor anota o id numa lista. Em toda request, o verificador confere a assinatura e depois pergunta à lista se aquele id foi revogado. Uma consulta por request. É o mesmo `SELECT` que a sessão faz, só que de cabeça para baixo: em vez de "esse crachá está na lista dos válidos?", "esse crachá está na lista dos riscados?".

As duas saídas trazem o estado de volta para o servidor. O JWT era rápido justamente porque não tinha estado. Revogar exige lembrar, e lembrar é estado.

## Quando o JWT vale a pena

Então o JWT é inútil? Não. Ele é a ferramenta certa quando **quem verifica não pode, ou não deve, perguntar a quem emitiu.**

- **Vários serviços atrás de um login só.** Um sistema com dez serviços separados, cada um com o seu banco. Com sessão, todos teriam de consultar o serviço de login a cada request, e ele vira o gargalo de tudo. Com JWT, cada serviço confere a assinatura sozinho.
- **Outra empresa.** O "entrar com Google" (volta lá embaixo) entrega ao seu app um JWT assinado pelo Google. O seu app confere a assinatura no login e acredita no que está escrito, sem precisar ligar para o Google para conferir. O Google não vai abrir o banco de sessões dele para você.
- **Tokens de curta duração entre sistemas.** Um serviço que chama outro com um crachá que vale cinco minutos. Revogar quase não importa: o tempo revoga sozinho, logo.

Um detalhe que a bancada da lição 08 não fez. Com HS256, quem confere tem a mesma chave de quem emite, então pode emitir também. Entre empresas, isso não serve. Por isso existem os algoritmos de **chave pública**, como o RS256: o emissor assina com uma chave privada, que nunca sai de casa, e publica a chave pública, que só confere. Quem tem a pública verifica, mas não fabrica.

O fio comum: o JWT brilha quando o estado não pode morar num lugar só.

## Por que o FairFare ficou com sessão

O FairFare não é nenhum desses casos.

- **Um backend só.** Não há outro serviço querendo conferir crachá sem perguntar.
- **Um banco que já é consultado em toda request.** Toda rota do FairFare lê ou grava no Postgres. Uma ida a mais ao mesmo lugar não muda a natureza da request.
- **Revogação de graça.** O logout da lição 07 é um `DELETE`, e o token morre na hora. Sem refresh token, sem lista de revogados.
- **Nenhuma chave de assinatura.** A lição 08 já disse: não há chave que, vazada, fabrique um crachá. (A senha do banco no código é outra história, declarada no capítulo 4.)

E quanto custa? A lição 05 mediu. Os guardiões de consultas do capítulo 5 subiram: `GET /bookings` de 3 para 4, `GET /groups/{id}` de 3 para 4, os saldos de 2 para 3. Nas palavras dela: "subiu **um**, constante, sem depender de quantas reservas ou membros existem". Uma consulta por request, pelo índice da coluna `token_hash`. É o preço inteiro.

O JWT economizaria essa consulta. Em troca, o FairFare ganharia um segredo para guardar e um logout que não desloga. Para consertar o logout, voltaria a consultar o banco. Pagaria o mesmo preço por uma solução mais complicada.

## Lado a lado

| | Sessão (o FairFare) | JWT (a bancada) |
|---|---|---|
| **Onde mora o estado** | No servidor: uma linha na tabela `sessions`. | No próprio token. O servidor não guarda nada. |
| **Revogar** | Apagar a linha. Vale na hora (lição 07). | Só o `exp` derruba. Para mais que isso, o estado volta (refresh token ou lista). |
| **O que vaza se o banco vazar** | O sha256 dos tokens, que não vira crachá (lição 04). | Nenhum crachá: não há tabela de sessões. |
| **O que vaza se a chave vazar** | Não existe chave. | Tudo: com HS256, quem tem a chave emite crachá de qualquer um (lição 08). Com uma chave só, a saída é trocá-la, e isso invalida todos os crachás de uma vez. |
| **Custo por request** | Uma consulta ao banco (o +1 da lição 05). | Um HMAC na CPU, sem ir ao banco. Até alguém querer revogar. |
| **Chave de assinatura no servidor** | Nenhuma. | A chave. Com HS256, a mesma assina e confere. |

Nenhuma das colunas ganha em todas as linhas. A escolha depende de qual linha pesa mais no seu sistema. No FairFare, pesam o "revogar" e a "chave de assinatura".

## E o OAuth2?

A lição 04 deu ao login a resposta `{"access_token": ..., "token_type": "bearer"}` e disse que esses nomes vêm do OAuth2. É hora de dizer o que o OAuth2 é. E, principalmente, o que ele não é.

Pense na chave de manobrista. Alguns carros vêm com uma chave especial para o valet: ela liga o motor, mas não abre o porta-malas nem o porta-luvas. Você empresta o carro sem emprestar tudo.

O OAuth2 é isso para APIs. É um protocolo de **delegação**: deixar um app agir em seu nome num outro serviço, sem entregar a sua senha a ele. Um app de fotos quer ler a sua pasta num serviço de armazenamento. Em vez de pedir a sua senha, ele manda você ao próprio serviço. Lá, você faz login e autoriza aquele acesso, e só ele. O serviço entrega ao app um access token com esse escopo. O app nunca vê a sua senha, e você revoga o acesso sem trocar senha nenhuma.

Repare: o OAuth2 responde "o que este app pode fazer em seu nome?". Ele não responde "quem é você?". Para isso existe o **OpenID Connect**, uma camada de identidade construída por cima do OAuth2. É ele que entrega o JWT do "entrar com Google" da seção anterior, que diz quem você é. O "entrar com Google" é OAuth2 + OpenID Connect.

### Por que o FastAPI fala tanto em OAuth2

O pacote de segurança do FastAPI tem vários helpers com o nome:

```console
$ uv run python -c "import fastapi.security as s; print([n for n in dir(s) if 'OAuth' in n])"
['OAuth2', 'OAuth2AuthorizationCodeBearer', 'OAuth2PasswordBearer', 'OAuth2PasswordRequestForm', 'OAuth2PasswordRequestFormStrict']
```

A especificação do OAuth2 prevê vários fluxos para conseguir um token. Um deles é o "usuário e senha em troca de token": o cliente manda as credenciais direto e recebe o access token. É um login comum, com cara de OAuth2. O `OAuth2PasswordBearer` e o `OAuth2PasswordRequestForm` foram feitos para esse fluxo, e por isso têm esse nome. (As recomendações de segurança mais recentes do próprio OAuth mandam não usar esse fluxo. Ele aparece muito em tutoriais porque é o jeito mais curto de ter um login com cara de OAuth2.)

O FairFare não usa nenhum dos dois. Usa o `HTTPBearer`, que lê o mesmo header `Authorization: Bearer`. Do OAuth2, ficou só o **formato** da resposta: `access_token` e `token_type: "bearer"`. Clientes e ferramentas já esperam esse formato, e ele não custa nada.

Por que não o `OAuth2PasswordRequestForm`? Ele lê usuário e senha como formulário HTML (*form data*), não como JSON. E form data no FastAPI exige uma dependência a mais. Para ver, escrevi um arquivo descartável, fora do repositório, com uma rota só:

```python
from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordRequestForm

app = FastAPI()


@app.post("/token")
async def token(form: OAuth2PasswordRequestForm = Depends()):
    return {}
```

Rodei com `uv run python <arquivo>.py`, de dentro do repositório, para usar o FastAPI do FairFare. Nem chega a subir servidor. A rota estoura já na definição, e o traceback termina assim:

```console
RuntimeError: Form data requires "python-multipart" to be installed.
You can install "python-multipart" with:

pip install python-multipart
```

Uma dependência nova só para o botão de login do Swagger. O FairFare já tem o botão Authorize, onde se cola o token (lição 05). Não vale.

E por que não um provedor de verdade, um "entrar com Google" no FairFare? Porque exige um serviço externo, uma conta registrada e um vaivém pelo browser. Nada disso ensina o que este capítulo precisa. A pergunta "quem é você?" o FairFare responde sozinho, e a parte difícil (guardar senha, emitir, conferir e revogar crachá) você já fez à mão.

Falta uma pergunta: no browser, onde o cliente guarda o crachá? É a lição 10.

## O que fica declarado

- **O app não muda.** O FairFare continua com o token opaco e a tabela `sessions`.
- **Não há refresh token nem lista de revogados.** Nem precisa: a sessão já revoga. E a sessão não se renova com o uso, como a lição 07 já declarou. É escolha deste capítulo.
- **O OAuth2 fica como conceito.** Nenhum provedor, nenhum "entrar com Google". Do protocolo, o FairFare usa só o formato da resposta do login.

## O que você deve conseguir fazer agora

- Escolher sessão ou JWT, e justificar pela tabela, para três sistemas: (1) uma loja online com um backend e um banco, (2) uma empresa com vinte serviços que precisam saber quem fez cada request, (3) um link de download que um serviço gera e outro aceita por cinco minutos.
- Explicar por que um refresh token traz o estado de volta, e por que o access token copiado continua passando mesmo com ele.
- Dizer o que é o OAuth2 (delegação), o que ele não é (login, identidade), e o que o FairFare pegou emprestado dele.
