# Lição 02 — Concorrência não é paralelismo

Esta é a lição mais curta do capítulo, e é de propósito. Ela não ensina a fazer nada. Ela só ajusta cinco palavras que o resto do capítulo vai usar sem parar — e que quase todo mundo usa trocadas.

## Um cozinheiro, quatro panelas

Você está sozinho na cozinha com quatro panelas no fogo. Mexe uma, tampa, vira o bife, volta na primeira, escorre o macarrão. As quatro coisas estão acontecendo. Você está fazendo **uma** de cada vez.

Isso é **concorrência**: lidar com várias coisas ao mesmo tempo, revezando.

Agora chame três amigos. Cada um pega uma panela. Quatro pares de mãos, quatro coisas sendo feitas de verdade no mesmo instante.

Isso é **paralelismo**: fazer várias coisas ao mesmo tempo, de fato.

A versão precisa: **concorrência é uma forma de estruturar o trabalho** — várias tarefas em andamento, intercaladas numa mesma linha de execução. **Paralelismo é uma propriedade da execução** — várias tarefas rodando no mesmo instante, o que exige mais de um núcleo de CPU.

Um programa pode ser concorrente sem ser paralelo (o cozinheiro sozinho — e é exatamente isso que o event loop faz). Pode ser paralelo sem ser muito concorrente. E pode ser os dois.

E feche a porta do outro lado também: concorrência **não** quer dizer "uma thread só". O event loop faz concorrência com uma; o threadpool da lição 01 fez com dez. As dez threads que dormiram juntas o segundo delas não eram os três amigos cozinhando — eram dez pessoas paradas em frente a dez panelas, esperando a água ferver. Dez corpos, zero cozimento: muitas esperas se sobrepondo, nenhum trabalho acontecendo no mesmo instante. Concorrência dos dois jeitos; paralelismo em nenhum.

Guarde a assimetria: **concorrência é sobre esperar bem; paralelismo é sobre trabalhar mais.**

## As duas naturezas de uma tarefa

Toda operação lenta do seu backend é lenta por um de dois motivos. Distinguir os dois é a régua mais útil deste capítulo inteiro.

**I/O-bound** — o processo está **esperando alguém**. O banco responder, a API do gateway de pagamento voltar, o disco entregar o arquivo, o cliente terminar de mandar o upload. Enquanto espera, sua CPU está de braços cruzados. `I/O` é *input/output*: qualquer conversa com o mundo fora do processo.

**CPU-bound** — o processo está **trabalhando**. Redimensionar uma imagem, calcular hash de senha, ordenar uma lista gigante, gerar um relatório. A CPU está a mil, não há ninguém para esperar.

A régua, em forma de pergunta: *neste segundo, meu processo está esperando alguém ou está trabalhando?*

E a consequência, que é a frase mais importante desta lição:

> **Async resolve o caso I/O-bound. Ele não faz absolutamente nada pelo CPU-bound.**

Faz sentido quando você olha pela cozinha: revezar entre panelas ajuda porque cozinhar é, em grande parte, esperar. Se a tarefa fosse picar cinquenta cebolas, revezar não picaria nenhuma cebola mais rápido — só faria você trocar de tábua o tempo todo. Para cebola, você precisa de mais mãos.

Essa frase volta na lição 10, quando a gente for falar do GIL e de por que "mais mãos" em Python é uma conversa mais complicada do que parece.

## "Bloquear", com precisão

A palavra apareceu quatro vezes na lição 01 e merece uma definição exata, porque o uso solto dela é fonte de confusão sem fim.

**Bloquear é ocupar a linha de execução sem devolver o controle.**

Não é o mesmo que ser lento. Não é o mesmo que demorar. Uma operação pode demorar dez segundos e não bloquear nada — se durante esses dez segundos ela avisar "estou esperando, usem a thread". E uma operação instantânea pode bloquear, se ela segurar o controle enquanto roda.

Volte ao `time.sleep(1)` da lição 01. Ele não estava trabalhando. Ele nem tinha trabalho para fazer — a função dele é literalmente *não fazer nada por um segundo*. Mesmo assim ele congelou o servidor inteiro. Não porque fosse lento; porque não devolvia o controle.

Esse é o crime: não a lentidão, o egoísmo.

E note que a mesma linha, `time.sleep(1)`, foi inofensiva na rota `def` e catastrófica na rota `async def`. Bloquear não é propriedade só do código — é a relação entre o código e onde ele roda. Uma thread do threadpool existe justamente para ser bloqueada; o event loop existe justamente para não ser.

## Onde o seu backend cai nisso tudo

Pense no que uma request do FairFare faz de verdade:

1. Recebe bytes da rede — espera.
2. Consulta o banco para ver se o horário está livre — espera.
3. Compara duas datas — trabalha (por microssegundos).
4. Grava a reserva — espera.
5. Devolve JSON pela rede — espera.

Quatro esperas e um trabalho, e o trabalho é o item mais barato da lista. **Isso não é um acidente do nosso app; é a forma de quase todo backend.** Um servidor web passa a vida esperando por outros computadores.

É por isso que async é um assunto central em backend e uma nota de rodapé em muitas outras áreas da programação. A ferramenta encaixa na natureza do problema: nosso gargalo é espera, e async é a técnica de esperar muitas coisas com uma thread só.

Também é por isso que a resposta certa para "devo usar async?" nunca é uma preferência de estilo. É uma pergunta sobre a natureza da tarefa — e você agora tem a régua para responder.

## O que você deve conseguir fazer agora

- Explicar a diferença entre concorrência e paralelismo sem usar a palavra "async".
- Classificar como I/O-bound ou CPU-bound: consultar o banco, redimensionar uma foto, chamar a API dos Correios, calcular o hash de uma senha, ler um arquivo de 2 GB, somar uma coluna de um milhão de números que já estão na memória.
- Dizer, para cada uma dessas, se async ajudaria.
- Definir "bloquear" sem usar a palavra "lento".
- Explicar por que o mesmo `time.sleep(1)` foi inofensivo numa rota e desastroso na outra.
