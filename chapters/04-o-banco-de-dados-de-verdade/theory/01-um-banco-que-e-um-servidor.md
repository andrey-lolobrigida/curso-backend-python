# Lição 01 — Um banco que é um servidor

Três capítulos inteiros, e o banco do FairFare foi um arquivo: `fairfare.db`, na raiz do projeto. Funcionou. Vai continuar funcionando até o fim desta lição, porque nesta lição o app **não muda uma linha**.

O que muda é o que existe ao lado dele. Hoje sobe um PostgreSQL. A pergunta da lição é uma só: **o que muda quando o banco deixa de ser um arquivo e vira outro programa?**

## A planilha e o cartório

O SQLite é uma planilha no seu computador. Você abre, escreve, salva. Ninguém mais está mexendo nela. Não tem fila, não tem senha, não tem horário de funcionamento.

O PostgreSQL é um cartório. Ele fica do outro lado da rua, com as portas abertas para a cidade inteira. Você não mexe nos livros dele: você pede, e um funcionário mexe por você. Para ser atendido, você se identifica. Cada pessoa no balcão ocupa um funcionário. E o cartório tem um número de guichês. Quando todos estão ocupados, quem chega fica de fora.

Agora o rigor, que é a analogia peça por peça.

- **Processo separado.** O SQLite é uma biblioteca que roda **dentro** do seu processo Python. Ler o banco é ler um arquivo. O PostgreSQL é **outro programa**, com o próprio processo, a própria memória, e que continua vivo quando o seu app morre.
- **Protocolo de rede.** O seu app fala com ele por uma conexão TCP, na porta `5432`. Cada consulta vira mensagens indo e voltando por essa conexão. Mesmo com os dois na mesma máquina, existe um "do outro lado".
- **Autenticação.** Para abrir a conexão, você manda usuário e senha. Um arquivo não pergunta quem você é: quem consegue ler o arquivo, lê o banco.
- **Um processo por conexão.** Para cada conexão aberta, o PostgreSQL cria um processo novo do lado dele. É o funcionário do guichê. Você vai ver esses processos com os próprios olhos daqui a pouco.
- **Um limite de conexões.** Como cada conexão custa um processo, o servidor tem um teto: `max_connections`. É o número de guichês. Passou dele, a conexão nova é recusada.

Repare que nenhum desses cinco itens existe num arquivo. Esse é o capítulo inteiro, em resumo: o banco agora é um servidor, e servidor tem fila, tem regra e tem limite.

## As promessas que um arquivo não cumpre

Você já esbarrou nessa fronteira três vezes, e nas três o curso deixou um bilhete para o capítulo 4.

**As duas URLs** (capítulo 2, lição 08). O `database.py` ficou com uma URL para o app e outra para o Alembic, e o preço foi declarado ali mesmo:

> Quando o FairFare for para o PostgreSQL no capítulo 4, você não vai mexer numa string — vai mexer em duas. (...)

**O pool que não comprava nada** (capítulo 2, lição 09). O pool de conexões apareceu como gargalo, mas a conversa sobre o tamanho dele ficou para depois:

> Com SQLite, "conexão" é um handle para um arquivo local; aumentar o pool não compra quase nada, e o próprio SQLite serializa as escritas de qualquer jeito.

**Os quatro workers** (capítulo 3, lição 11). Cada processo do uvicorn tem o próprio pool de 5 + 10 conexões. Com `--workers 4`, são até 60. E o bilhete:

> Vai doer no capítulo 4, quando o FairFare for para o PostgreSQL — que tem um limite próprio de conexões, para o servidor inteiro (...)

Nenhuma das três pode ser cumprida num arquivo. Não existe "limite do servidor" quando não existe servidor. Por isso o primeiro passo do capítulo é ter um.

## O Docker, como caixa fechada

O PostgreSQL vai rodar dentro do **Docker**. Uma frase sobre o que é isso: um **container** é um programa empacotado junto com tudo de que ele precisa (o sistema de arquivos, as bibliotecas, a configuração), rodando isolado do resto da sua máquina.

É só isso que você precisa saber por enquanto. O Docker aqui é uma **caixa fechada**: você aperta os botões, ela entrega um PostgreSQL. Como ela funciona por dentro (imagens, camadas, redes, o app também dentro de um container) é assunto do capítulo 11, quando o FairFare for colocado no ar.

E isso é uma **exceção**, dita em voz alta. A regra do curso é "infraestrutura só entra no capítulo que a motiva", e o capítulo que motiva o Docker é o 11. Ele entra antes por três motivos:

1. **É igual em todo sistema operacional.** Instalar o PostgreSQL direto no Linux, no Mac e no Windows são três tutoriais diferentes, com três jeitos diferentes de dar errado.
2. **A versão fica fixa.** Todo mundo roda o mesmo PostgreSQL 18, e as saídas desta apostila batem com as suas.
3. **Ele se destrói e se recria em segundos.** Os experimentos deste capítulo vão esgotar conexões, travar linhas e deixar o banco num estado que você vai querer jogar fora. Com o Docker, jogar fora é um comando.

Se você ainda não tem o Docker, instale pelo site oficial (docs.docker.com/get-docker). Você precisa do comando `docker compose`, que já vem junto nas instalações atuais.

## O `compose.yaml`, linha a linha

O **Docker Compose** lê um arquivo que descreve os containers de um projeto e sobe todos com um comando. O nosso descreve um container só. Ele está na raiz do repositório:

```yaml
# O PostgreSQL do curso, e só ele. O app continua rodando fora do Docker (cap. 4, lição 01).
# Credenciais fixas de desenvolvimento: uma limitação declarada (segredos: cap. 11).
services:
  postgres:
    image: postgres:18
    environment:
      POSTGRES_USER: fairfare
      POSTGRES_PASSWORD: fairfare
      POSTGRES_DB: fairfare
    ports:
      - "5432:5432"
    volumes:
      # No Postgres 18 o volume vai em /var/lib/postgresql (não mais em .../data).
      - pgdata:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fairfare -d fairfare"]
      interval: 1s
      timeout: 3s
      retries: 30
      start_period: 60s

volumes:
  pgdata:
```

Bloco a bloco.

**`services: postgres:`** Um serviço chamado `postgres`. É por esse nome que você vai se referir a ele nos comandos.

**`image: postgres:18`.** A imagem oficial do PostgreSQL, versão 18. A **imagem** é o pacote pronto; o **container** é esse pacote rodando. Fixar o `18` é o motivo 2 da seção anterior.

**`environment:`** Três variáveis que a imagem lê **na primeira vez** que sobe: cria o usuário `fairfare`, com a senha `fairfare`, e um banco chamado `fairfare`. "Na primeira vez" é literal. Se o banco já existe, mudar essas linhas não muda nada lá dentro.

**`ports: "5432:5432"`.** A porta da sua máquina, dois-pontos, a porta dentro do container. Sem essa linha, o PostgreSQL estaria rodando, mas trancado dentro da caixa. Com ela, `localhost:5432` na sua máquina chega no PostgreSQL. É por aí que o app vai entrar.

**`volumes: pgdata:/var/lib/postgresql`.** Um container é descartável. Tudo que ele escreve no próprio sistema de arquivos some quando ele é removido. O **volume** é um pedaço de disco que o Docker guarda **fora** do container, e o PostgreSQL grava os dados ali. O container morre, o volume fica.

O comentário em cima dessa linha existe porque o caminho mudou no PostgreSQL 18: antes era `/var/lib/postgresql/data`, agora é `/var/lib/postgresql`. Muito tutorial na internet ainda usa o caminho velho. Se você copiar de lá, os dados não vão parar onde você acha.

**`healthcheck:`** Um comando que o Docker roda dentro do container a cada segundo (`interval: 1s`), para saber se o serviço está pronto. Trinta falhas seguidas (`retries`) marcam o container como doente; no primeiro minuto (`start_period`), falhas não contam, porque o PostgreSQL pode demorar para se recuperar de um desligamento brusco. O `pg_isready` é uma ferramenta que vem com o PostgreSQL e responde exatamente isso: o servidor já está aceitando conexões? Isso importa porque **o container "subir" e o banco estar pronto são momentos diferentes**. O PostgreSQL leva alguns segundos inicializando depois que o processo nasce.

**`volumes: pgdata:`** lá no fim declara o volume pelo nome, para o Compose criá-lo.

E as credenciais, `fairfare`/`fairfare`, escritas no arquivo, num repositório público. Isso é uma **limitação declarada**: senha em texto puro só serve porque esse banco vive na sua máquina, só para desenvolvimento. Como segredos de verdade são guardados e entregues ao app é assunto do capítulo 11.

## Mexendo nele

Da raiz do repositório:

```bash
docker compose up -d --wait
```

O `up` sobe o que o `compose.yaml` descreve. O `-d` (*detached*) devolve o terminal em vez de prender você no log do banco. E o `--wait` é o par do `healthcheck`: o comando só termina quando o serviço está **saudável**, e não apenas quando o container nasceu. Sem ele, você poderia rodar o próximo comando com o banco ainda acordando.

Na primeira vez, o Docker baixa a imagem antes de tudo, e isso demora. Depois, sobe em segundos:

```console
 Volume python-backend-course_pgdata Creating
 Volume python-backend-course_pgdata Created
 Network python-backend-course_default Creating
 Network python-backend-course_default Created
 Container python-backend-course-postgres-1 Creating
 Container python-backend-course-postgres-1 Created
 Container python-backend-course-postgres-1 Starting
 Container python-backend-course-postgres-1 Started
 Container python-backend-course-postgres-1 Waiting
 Container python-backend-course-postgres-1 Healthy
```

*(No seu terminal isso aparece animado, linha atualizando no lugar. Aqui está a versão em texto, sem as linhas repetidas.)*

Leia as duas últimas: `Waiting` e `Healthy`. É o `--wait` esperando o `pg_isready` dizer que sim.

Quem está de pé:

```console
$ docker compose ps
NAME                               IMAGE         COMMAND                  SERVICE    CREATED         STATUS                   PORTS
python-backend-course-postgres-1   postgres:18   "docker-entrypoint.s…"   postgres   8 seconds ago   Up 6 seconds (healthy)   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp
```

O `(healthy)` é o healthcheck. A coluna `PORTS` é a linha do `ports:`: a 5432 da sua máquina aponta para a 5432 do container. Guarde essa coluna, ela vai salvar você mais para baixo.

### Conversando com o banco

O `psql` é o cliente de linha de comando do PostgreSQL. Ele já vem dentro da imagem, então você não precisa instalar nada:

```bash
docker compose exec postgres psql -U fairfare
```

O `exec` roda um comando **dentro** de um container que já está de pé. Esse abre um prompt `fairfare=#`, onde você digita SQL. Para sair, `\q`.

Dá também para mandar um comando só, com `-c`, que é como as saídas abaixo foram tiradas:

```console
$ docker compose exec postgres psql -U fairfare -c "SELECT version();"
                                                      version
--------------------------------------------------------------------------------------------------------------------
 PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
(1 row)
```

PostgreSQL 18.6. O seu pode ter um número depois do ponto diferente: o `18` da imagem acompanha as correções da versão 18.

Agora o número de guichês:

```console
$ docker compose exec postgres psql -U fairfare -c "SHOW max_connections;" -c "SHOW \"TimeZone\";"
 max_connections
-----------------
 100
(1 row)

 TimeZone
----------
 Etc/UTC
(1 row)
```

**`max_connections = 100`.** Cem conexões, para o servidor inteiro, somando todo mundo que conectar nele. Guarde esse número. A lição 05 vai fazer as contas dos pools e dos workers contra ele.

**`TimeZone = Etc/UTC`.** O fuso em que o servidor pensa. Esse aqui vai importar na lição 04.

### Os funcionários do cartório

Quem está conectado agora? O PostgreSQL mantém uma visão chamada `pg_stat_activity`, com uma linha por processo do servidor:

```console
$ docker compose exec postgres psql -U fairfare -c "SELECT count(*) FROM pg_stat_activity;"
 count
-------
     9
(1 row)
```

Nove. E o FairFare nem está conectado. Quem são?

```console
$ docker compose exec postgres psql -U fairfare -c "SELECT pid, backend_type, state FROM pg_stat_activity;"
 pid |         backend_type         | state
-----+------------------------------+--------
 175 | client backend               | active
 106 | autovacuum launcher          |
 107 | logical replication launcher |
  99 | io worker                    |
 102 | checkpointer                 |
 103 | background writer            |
 101 | io worker                    |
 100 | io worker                    |
 105 | walwriter                    |
(9 rows)
```

Oito deles são o próprio servidor trabalhando: gravando em disco, fazendo faxina, organizando o log. Você não pediu nenhum. É o cartório com as luzes acesas antes de abrir as portas.

O nono é o `client backend`, e esse é você: o processo que o PostgreSQL criou para atender **este** `psql`. Ele está `active` porque está rodando a própria consulta que o listou.

"Um processo por conexão" não é figura de linguagem. Abri duas conexões que ficam paradas oito segundos (`SELECT pg_sleep(8)`) e, enquanto elas esperavam, listei os processos do container por fora, com `docker compose top`:

```console
  PID    PPID   CMD
42675  42649   postgres
42894  42675   postgres: io worker 0
42895  42675   postgres: io worker 2
42896  42675   postgres: io worker 1
42897  42675   postgres: checkpointer
42898  42675   postgres: background writer
42900  42675   postgres: walwriter
42901  42675   postgres: autovacuum launcher
42902  42675   postgres: logical replication launcher
43697  42649   /usr/lib/postgresql/18/bin/psql -U fairfare -c SELECT pg_sleep(8);
43698  42649   /usr/lib/postgresql/18/bin/psql -U fairfare -c SELECT pg_sleep(8);
43710  42675   postgres: fairfare fairfare [local] SELECT
43711  42675   postgres: fairfare fairfare [local] SELECT
```

*(Cortei as colunas que não interessam aqui, como usuário e horário. O resto é literal.)*

As duas últimas linhas. Duas conexões, **dois processos novos**, os dois filhos do `postgres` principal (o `PPID` deles é o `42675`). O nome conta a história: usuário `fairfare`, banco `fairfare`, rodando um `SELECT`. Quando as conexões fecham, os processos morrem.

Agora junte com o `max_connections`. Cada conexão é um processo de verdade, com memória de verdade. É por isso que existe um teto. Cem conexões são cem processos. Um arquivo SQLite não tem teto porque não tem processo nenhum do outro lado: cada conexão é só o seu próprio programa abrindo um arquivo.

### A senha, e o `[local]`

Repare no `[local]` daquelas linhas. O `psql` está **dentro** do container, e conversa com o servidor por um arquivo especial do sistema (um *socket Unix*), não pela rede. E a imagem oficial confia em quem já está dentro da caixa: daí, a senha nem é pedida.

O FairFare vai entrar pelo outro caminho: pela porta 5432, vindo de fora. Por lá a senha é cobrada. Testei com uma senha errada, num script descartável, com um driver que só entra no projeto na lição 02:

```console
FATAL:  password authentication failed for user "fairfare"
```

Com `fairfare`, conectou. É o cartório pedindo documento no balcão.

### Desligando, e o que sobrevive

Para provar que o volume funciona, criei uma tabela de recado:

```bash
docker compose exec postgres psql -U fairfare -c "CREATE TABLE recado (texto text);" -c "INSERT INTO recado VALUES ('sobrevivi ao down');"
```

Derrubei tudo e subi de novo:

```console
$ docker compose down
 Container python-backend-course-postgres-1 Stopping
 Container python-backend-course-postgres-1 Stopped
 Container python-backend-course-postgres-1 Removing
 Container python-backend-course-postgres-1 Removed
 Network python-backend-course_default Removing
 Network python-backend-course_default Removed
$ docker compose up -d --wait
(...)
$ docker compose exec postgres psql -U fairfare -c "SELECT * FROM recado;"
       texto
-------------------
 sobrevivi ao down
(1 row)
```

Leia o `down` com atenção: o container foi **removido**, não só parado. E mesmo assim o recado estava lá. É o volume. O container é o funcionário. O volume são os livros do cartório.

Se você rodou isso também, apague o recado com `DROP TABLE recado;`. A partir da lição 02, esse banco é do FairFare.

E quando você **quiser** começar do zero? Existe um `-v`:

```bash
docker compose down -v
```

Ele derruba o container **e apaga o volume**. O próximo `up` encontra o disco vazio e inicializa um banco novinho, lendo de novo as variáveis do `environment`. Você vai querer isso de vez em quando neste capítulo. Só não rode no automático: tudo que estava no banco vai junto, e não tem lixeira.

## Se a porta 5432 já estiver ocupada

Se você já tem um PostgreSQL instalado direto na máquina, ele provavelmente está na 5432. Dois programas não escutam na mesma porta. Simulei isso deixando outro programa na 5432 e rodando o `up`:

```console
$ docker compose up -d --wait
(...)
 Container python-backend-course-postgres-1 Starting
Error response from daemon: failed to set up container networking: driver failed programming external connectivity on endpoint python-backend-course-postgres-1 (ee5f511a5d90e8e69ec13f8978a10d4b10950c312cc988ef28d946752fa4fe54): failed to bind host port 0.0.0.0:5432/tcp: address already in use
```

O que importa está no fim: `failed to bind host port 0.0.0.0:5432/tcp: address already in use`. Alguém chegou antes. Para descobrir quem, no Linux:

```bash
ss -ltnp | grep 5432
```

Dois caminhos.

**Parar o outro.** Se é um PostgreSQL instalado que você não está usando, pare o serviço dele e suba o do curso.

**Mudar de porta.** Troque a linha do `ports:` para `"5433:5432"`. O container continua escutando na 5432 lá dentro; a sua máquina passa a encaminhar a 5433 para ele. Só que aí **as URLs do banco precisam dizer 5433 também**. Elas chegam ao FairFare na lição 02. Se você mudou a porta aqui, mude lá.

### A armadilha depois do conserto

Medi uma coisa que você não espera. Liberei a porta e rodei o `up` de novo. Ele subiu, e o healthcheck disse que estava tudo bem:

```console
$ docker compose ps --format '{{.Status}} | {{.Ports}}'
Up 1 second (healthy) |
```

Olhe depois da barra: **a coluna de portas está vazia.** O container que tinha falhado foi reaproveitado, sem a porta publicada. O `(healthy)` não ajuda, porque o `pg_isready` roda **dentro** do container, e lá dentro está tudo certo. Quem está de fora não entra:

```console
ConnectionRefusedError: [Errno 111] Connection refused
```

*(Isso é uma conexão TCP crua na `localhost:5432`, de um Python na minha máquina.)*

O conserto: depois de liberar a porta, derrube e suba de novo.

```bash
docker compose down && docker compose up -d --wait
```

Aí a coluna `PORTS` volta a mostrar `0.0.0.0:5432->5432/tcp`. É por isso que eu disse para guardar aquela coluna.

Uma ressalva: tudo nesta lição foi rodado no Linux, com Docker 29.8 e Compose 5.5. Os comandos são os mesmos no Mac e no Windows, mas **não foram verificados nesta bancada**. Em especial, o `ss` é do Linux; nos outros sistemas, a ferramenta para achar quem está numa porta é outra.

## O que fica declarado

- **O Docker é uma caixa fechada** até o capítulo 11. Só o banco roda nele. O FairFare continua rodando fora, do jeito de sempre.
- **As credenciais estão fixas e em texto puro** no `compose.yaml`. Serve para desenvolvimento local, e só. Segredos de verdade: capítulo 11.
- **Mac e Windows não foram verificados** com estes comandos.
- **O app ainda usa o SQLite.** Esta lição só pôs o servidor de pé. A mudança é a lição 02.

## O que você deve conseguir fazer agora

- Subir o banco com `docker compose up -d --wait`, conferir com `docker compose ps` e derrubar com `docker compose down`, sabendo a diferença entre `down` e `down -v`.
- Abrir um `psql` dentro do container e perguntar ao servidor a versão e o `max_connections`.
- Explicar por que um banco-servidor tem limite de conexões e um arquivo SQLite não, usando o que você viu no `pg_stat_activity` e no `docker compose top`.
- Resolver a porta 5432 ocupada, incluindo o detalhe de derrubar e subir de novo depois.
