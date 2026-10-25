# Lição 02 — Senha não se guarda

A lição 01 terminou com uma pergunta: quem é você? A resposta mais velha da computação é uma senha. O usuário escolhe uma no cadastro, o servidor guarda, e no login confere se as duas batem.

"O servidor guarda." É aí que mora o problema desta lição. O FairFare ainda não tem senha nenhuma: a tabela `users` tem nome e email, e só. Antes de criar a coluna, vale decidir **o que** vai dentro dela.

Esta lição também não muda o app. Ela roda numa bancada nova, `bancada/senhas.py`, só com a biblioteca padrão do Python.

## A pergunta que ninguém faz

Quando se projeta um login, a pergunta de sempre é "como eu confiro a senha?". A que quase ninguém faz é outra: **se o banco vazar amanhã, o que o atacante leva?**

E vazar não é hipótese de filme. Backup esquecido num lugar público, injeção de SQL (a lição 10 do capítulo 5 mostrou uma ao vivo), funcionário com acesso demais: banco vaza, e com frequência.

E o atacante não vai usar as senhas só no seu app. Vai usá-las no email, no banco e onde mais a pessoa repetiu a senha. E as pessoas repetem.

A meta: **mesmo com a tabela inteira na mão, o atacante deve conseguir o mínimo de senhas, pagando o máximo por cada uma.**

A bancada guarda as senhas de três contas de quatro jeitos e, em cada um, faz o papel de quem roubou a tabela:

```bash
uv run python chapters/06-autenticacao-e-seguranca/bancada/senhas.py
```

## Ato 1: texto puro

O jeito ingênuo é guardar a senha como ela chegou:

```console
== 1. Texto puro ==
ana@example.com    senha = senha123
bruno@example.com  senha = senha123
carla@example.com  senha = flamengo
Vazou o banco, vazou tudo. Não há o que atacar: está escrito.
```

Nem tem ataque. É ler.

## Hash, não criptografia

A primeira ideia de muita gente é cifrar a senha: criptografia, com uma chave. Só que cifra tem volta. Quem tem a chave decifra. E a chave mora no servidor, ao lado do banco. Se o banco vazou, a chave tem boas chances de ter ido junto.

O pulo do gato é perceber que **ninguém precisa ler a senha de volta**. No login, o servidor não quer saber qual é a senha. Ele quer saber se a que chegou agora é a mesma do cadastro. Para conferir, não precisa de volta.

Para isso existe o **hash**. Pense num moedor de carne: entra a picanha, sai carne moída. A mesma picanha dá sempre a mesma carne moída, e ninguém remonta a picanha a partir dela.

Agora o rigor. Uma **função de hash** recebe uma entrada de qualquer tamanho e devolve um valor de tamanho fixo (o sha256 devolve 32 bytes, 64 caracteres em hexadecimal). A mesma entrada dá sempre o mesmo valor. E, para uma boa função de hash, não existe caminho conhecido do valor de volta para a entrada.

O login vira: calcule o hash da senha que chegou e compare com o hash guardado. Se baterem, é a mesma senha.

## Ato 2: sha256, e por que ele é rápido demais

O hash mais famoso é o sha256, e o Python o traz no `hashlib`. Primeiro, o script mede quantos ele calcula por segundo nesta máquina. Depois guarda as três senhas como sha256:

```console
== 2. sha256 puro ==
sha256 por segundo neste computador: 3.925.702

ana@example.com    55a5e9e78207b4df8699d60886fa070079463547b095d1a05bc719bb4e6cd251
bruno@example.com  55a5e9e78207b4df8699d60886fa070079463547b095d1a05bc719bb4e6cd251
carla@example.com  d58d736c7a967fb5f307951932734f8b0594725faa5011dbb66a8c538e635fb6
Ana e Bruno: mesmo hash. Quem vê um, sabe que os dois usam a mesma senha.
```

Repare na primeira coisa que vazou sem ataque nenhum. A Ana e o Bruno escolheram a mesma senha sem combinar, e o hash entrega isso. Quem descobrir a de um leva a do outro.

Mas o golpe de verdade vem agora. O atacante não precisa desfazer o hash. Ele precisa **adivinhar**: calcular o hash de muitas senhas prováveis e ver qual bate. Uma lista de senhas prováveis se chama **dicionário**. O da bancada é de brinquedo: `senha1` a `senha999` e um punhado de famosas, 1015 ao todo. Os de verdade têm milhões de entradas, tiradas de vazamentos antigos.

E sem nada que diferencie uma conta da outra, ele pode calcular o hash do dicionário inteiro **uma vez só** e guardar o resultado num dict de hash para senha. É a **tabela pronta** (em inglês, *precomputed table*; a versão compacta e famosa se chama *rainbow table*). Depois disso, cada hash vazado é uma consulta:

```console
dicionário: 1015 senhas
montar a tabela pronta (hash -> senha): 0,355 ms
consultar as 3 contas: 0,002 ms
ana@example.com    -> senha123
bruno@example.com  -> senha123
carla@example.com  -> flamengo
```

Um terço de milissegundo para montar, e três senhas descobertas.

O problema não é o sha256 ser fraco. É ele ser **rápido**. Ele foi feito para isso: conferir se um arquivo de 4 GB chegou inteiro, assinar documentos, coisas em que velocidade é virtude. Para senha, velocidade é defeito. A conta do atacante é simples: hashes por segundo × tamanho do dicionário. A 3,9 milhões por segundo, os 1015 da bancada saem em 0,26 ms.

E isso é um núcleo só, chamando o `hashlib` (que roda em C) de dentro de um laço Python. Quem ataca de verdade usa placa de vídeo, que calcula muitos hashes em paralelo, e o sha256 é justamente o tipo de conta em que ela brilha.

## Ato 3: o sal

A tabela pronta funciona porque `senha123` vira o mesmo hash em toda conta, em todo banco, no mundo inteiro. O remédio é fazer cada conta calcular um hash diferente.

O **sal** é isso: alguns bytes aleatórios, sorteados no cadastro, um por conta. O servidor calcula o hash do sal colado na senha, e guarda o sal **ao lado do hash, às claras**. O sal não é segredo. Ele não precisa ser. O trabalho dele é tornar cada conta única, não esconder nada. No login, o servidor lê o sal da conta, cola na senha que chegou e calcula de novo.

Na bancada, o sal vem de `os.urandom(16)`, 16 bytes do gerador aleatório do sistema operacional:

```console
== 3. sha256 com sal ==
ana@example.com    sal = 8df44c1e5962f0d9f7a48c69fced9e5b
                   hash = 7427c9bd4e8d0bafbf4d92429dc0586ddb509d646f1ea4cd98bf7ae81a175848
bruno@example.com  sal = 3aa880a14a228879825ae773298b2af6
                   hash = cf0656b1033bab9e78669524d4976d6103629313ad80a38bed94375ff3287227
carla@example.com  sal = 98dcd42694aa64b54b7c579c2b92ffb2
                   hash = 23b244afa38f7f1613cbf77f214d85cc351358e86dd1ccc4434e6159f4b26a87
Ana e Bruno: mesma senha, hashes diferentes.

a tabela pronta do ato 2 contra os hashes com sal: 0 de 3 achadas
```

Duas vitórias. A Ana e o Bruno deixaram de se denunciar. E a tabela pronta do ato 2 virou lixo: zero de três. Ela foi calculada sem sal, e nenhum desses hashes foi.

Agora a parte que costuma passar batida. O atacante tem o sal de cada conta, porque está ali, ao lado do hash. Então ele faz o óbvio: refaz o dicionário, conta a conta, com o sal de cada uma. Isso se chama **força bruta**: testar candidato por candidato até um bater.

```console
o mesmo dicionário, refeito para cada conta com o sal dela:
ana@example.com    -> senha123  (0,042 ms)
bruno@example.com  -> senha123  (0,040 ms)
carla@example.com  -> flamengo  (0,319 ms)
O sal matou a tabela pronta. A força bruta continua rápida, conta a conta.
```

O laço para quando acha. `senha123` está no começo da lista, e `flamengo` está no fim, entre as famosas: a Carla é a que pagou o dicionário inteiro. Um terço de milissegundo.

Então, o sal mata duas coisas: o hash igual para senha igual e a tabela pronta. Ele **não** mata a força bruta conta a conta. Com o sal, o atacante passa a pagar o dicionário uma vez por conta, em vez de uma vez para todas. Com o sha256 rápido, pagar uma vez por conta ainda sai barato.

## Ato 4: lento, de propósito

Falta atacar a velocidade. A saída é uma função feita para ser cara: uma **KDF**, sigla em inglês para *função de derivação de chave* (*key derivation function*). Ela também transforma senha e sal num valor fixo, como um hash. A diferença é que ela é lenta de propósito, e quanto ela custa é um **parâmetro**.

A biblioteca padrão traz uma, o `hashlib.scrypt`. Ela tem três parâmetros. O `r` é o tamanho do bloco que ela embaralha na memória, e o `p` é quantas cópias independentes da conta ela faz; os dois ficam fixos aqui, em 8 e 1. O `n` é o botão do custo:

```console
== 4. scrypt (r=8, p=1) ==
n=2^14: 24,5 ms por hash (41 por segundo), 16 MiB de memória (128·r·n)
n=2^15: 58,6 ms por hash (17 por segundo), 32 MiB de memória (128·r·n)
```

De 3,9 milhões por segundo para 41. E dobrar o `n` dobrou a memória e mais que dobrou o tempo.

A memória é a outra metade do truque. O scrypt não gasta só CPU: cada hash exige `128·r·n` bytes de RAM, 16 MiB no `n=2^14` (MiB é o mebibyte, 2^20 bytes: o megabyte contado em potências de 2). Quem ataca com placa de vídeo tem milhares de núcleos, mas pouca memória para cada um, e isso freia o paralelismo dele. O argon2, que o FairFare vai usar, segue a mesma ideia.

A memória cobra até de quem defende. A primeira versão do script, sem o `maxmem`, morreu no `n=2^15`:

```console
ValueError: [digital envelope routines] memory limit exceeded
```

O OpenSSL, que faz a conta por baixo do `hashlib`, tem um teto de memória padrão, e os 32 MiB passam dele. O `maxmem` do script sobe o teto.

E a conta do atacante, de novo:

```console
o dicionário de 1015 senhas, contra UMA conta:
  sha256 com sal: 1015 ÷ 3.925.702/s = 0,26 ms
  scrypt n=2^14:  1015 × 24,5 ms = 24.867,5 ms (~24,9 s)
  o scrypt sai 24,5 ms × 3.925.702/s = 96.180 vezes mais caro
e o login de quem sabe a senha: um hash só, 24,5 ms
```

O mesmo dicionário de brinquedo, que custava um quarto de milissegundo, agora custa 25 segundos **por conta**. E quem sabe a senha paga um hash só, 24,5 ms no login, coisa que ninguém percebe.

É essa assimetria que a KDF compra. Quem sabe a senha calcula uma vez. Quem não sabe calcula milhões. Encarecer cada cálculo quase não incomoda o primeiro e arruína o segundo.

E a KDF não faz milagre. `senha123` continua no topo de qualquer dicionário, e cai logo no começo da lista, lenta ou não. O custo compra tempo contra a lista longa, não contra a senha óbvia.

## Não escreva o seu

A bancada montou tudo à mão, e foi de propósito: para ver o mecanismo. Mas no app ninguém deve fazer assim. Onde guardar o sal, em que formato, qual `n` escolher, como subir o custo daqui a dois anos sem invalidar quem já tem conta: cada uma é uma decisão em que errar é fácil e o erro não aparece em teste nenhum. A lição 03 entrega essas decisões a uma biblioteca feita para isso, o argon2, e mostra que o hash dele carrega o sal e os parâmetros dentro de si.

## O que fica declarado

- **O app não muda nesta lição.** O FairFare segue sem senha. Ela chega na lição 03.
- **O sha256 com sal e o scrypt da bancada são o mecanismo, não a escolha do app.** O FairFare vai usar argon2, por uma biblioteca, na lição 03.
- **Os números são de um núcleo só, nesta máquina, chamando o `hashlib` de um laço Python.** Servem para comparar os esquemas entre si. Quem ataca usa placa de vídeo, e ela ajuda bem mais no sha256 do que no scrypt, que fica preso à memória. A distância medida aqui é um piso.
- **Os seus números vão ser outros**, e os sais e hashes do ato 3 mudam a cada execução (são aleatórios). Os hashes do ato 2 não mudam: sha256 de `senha123` é o mesmo em qualquer máquina.

## O que você deve conseguir fazer agora

- Explicar por que guardar a senha cifrada não resolve, e por que hash resolve.
- Dizer o que o sal protege e o que ele não protege, e por que ele pode ficar às claras ao lado do hash.
- Explicar por que sha256 com sal ainda não basta para guardar senha.
- Usando os números da bancada (os seus ou os desta lição), estimar quanto tempo um dicionário de **1 milhão** de senhas leva contra uma conta com cada esquema: sha256 puro, sha256 com sal e scrypt `n=2^14`. E contra mil contas?
