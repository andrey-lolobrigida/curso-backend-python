# Lição 02 — Por que FastAPI (e a comparação que vale mais que a escolha)

## A dor você já sentiu

Lembra do `server.py` do capítulo 0? Você o viu por dentro: um `if/else` decidindo rota por rota, parse de JSON na mão, status code montado à mão, headers escritos um a um. Para um mini-servidor didático, ótimo. Agora projete aquilo para um app com dezenas de rotas, validação de dados em cada uma, documentação para quem consome a API, tratamento de erro consistente...

Você passaria meses construindo infraestrutura — e nenhum minuto construindo o *seu* produto.

Um **framework web** é a resposta industrializada para isso: roteamento, parsing de request, validação, serialização de resposta, erros padronizados e documentação vêm prontos. Sobra para você exatamente a parte que nenhum framework pode escrever: a lógica do seu negócio.

## Os três candidatos

No mundo Python, três nomes dominam a conversa. Cada um tem um cenário onde é a escolha certa — isso não é diplomacia, é o ponto central da lição.

**Django** é o pacote "baterias incluídas": ORM, painel de admin, autenticação, formulários — tudo pronto e integrado. *Quando ganha:* produto com formato conhecido (e-commerce, CMS, SaaS padrão) e prazo apertado; o admin gratuito, sozinho, já paga a escolha.

**Flask** é o microframework veterano: um núcleo pequeno que faz roteamento, e você escolhe cada peça do resto (ORM, validação, auth) a dedo. *Quando ganha:* serviços pequenos, ou times que querem controle total da stack e têm opinião formada sobre cada componente.

**FastAPI** é o mais novo dos três: usa type hints do Python como matéria-prima — os tipos que você declara viram validação automática dos dados e documentação interativa da API, sem trabalho extra. Async nativo desde o berço. *Quando ganha:* APIs (especialmente JSON), que é exatamente o que vamos construir.

## Por que FastAPI neste curso

A resposta honesta tem menos a ver com "qual é o melhor" e mais com o que este curso quer ensinar.

Este capítulo existe para **montar as camadas de um backend com as próprias mãos** — entender por que existe uma camada de validação, uma de regra de negócio, uma de acesso a dados. O Django já vem com todas elas prontas e fundidas entre si. Para entregar produto, isso é uma bênção. Para uma aula de anatomia, é como estudar o corpo humano num boneco já costurado: funciona, mas você não vê os órgãos.

O Flask serviria: ele também não impõe camadas. Mas nos deixaria escrever na mão validação, serialização e documentação — dor repetida que você já sentiu no capítulo 0 e que não traz lição nova.

O FastAPI acerta o meio-termo: dá a base industrializada (roteamento, validação, docs) e **não opina sobre o resto** — as camadas de negócio e de dados, que são o assunto deste capítulo, seremos nós que vamos construir. De quebra, o material de construção dele são os type hints, que você já conhece do Python. Você vai vê-los trabalhar já na próxima lição.

## O aviso de maturidade

Se um dia te perguntarem "qual framework é o melhor?", desconfie da pergunta. A escolha certa depende do produto, do prazo e do time. O que separa um profissional de um torcedor é conseguir dizer *quando a própria escolha perde* — e você acabou de ver o cenário em que o Django atropela o FastAPI sem dó.

A comparação vale mais que o vencedor. Guarde a comparação.

## O que você deve conseguir fazer agora

- Defender a escolha do FastAPI para este curso em três frases suas.
- Nomear um cenário concreto em que o Django seria a escolha melhor — e dizer por quê.
- Explicar o que um framework web faz por você, usando o `server.py` do capítulo 0 como contraexemplo.
