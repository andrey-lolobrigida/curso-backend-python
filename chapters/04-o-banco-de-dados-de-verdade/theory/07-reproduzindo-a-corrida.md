# Lição 07 — Reproduzindo a corrida

O FairFare tem uma dívida que é mais velha que o PostgreSQL dele. Ela nasceu no capítulo 1, ganhou nome no capítulo 2 e está escrita no `ERRATA.md` desde então. Esta lição para de falar dela e a **reproduz**: no seu terminal, com o app de verdade, quantas vezes você quiser.

Consertar fica para depois. Primeiro a gente precisa ver o defeito acontecer, e contar.

## A dívida mais antiga do curso

A entrada 2 da `ERRATA.md` lista três limitações do capítulo 1. A primeira:

> | 1 | `app/services/booking.py::BookingService.create` | Verifica conflito de horário e **depois** insere, sem transação nem lock. Duas requests simultâneas para o mesmo horário passam as duas pela verificação e gravam as duas (*check-then-act*). | capítulo 4 |

O capítulo 4 chegou. O código é este, igual ao que está no repositório:

```python
    async def create(self, data: BookingCreate) -> BookingOut:
        user = await self.users.get(data.user_id)
        resource = await self.resources.get(data.resource_id)
        if user is None or resource is None:
            raise RelatedNotFoundError
        overlapping = await self.bookings.find_overlapping(
            data.resource_id, data.starts_at, data.ends_at
        )
        if overlapping:
            raise BookingConflictError
        booking = await self.bookings.create(
            data.user_id, data.resource_id, data.starts_at, data.ends_at
        )
        return await self._to_out(booking)
```

Duas linhas importam. O `find_overlapping` é a **verificação** (*check*): "tem alguém nesse horário?". O `self.bookings.create` é a **ação** (*act*): "então grava". Entre uma e outra, o código **supõe** que a resposta da verificação continua valendo. É essa suposição que falha.

## A janela

Imagine o clube com uma agenda de papel no balcão. A Ana e o Bruno chegam juntos, cada um de um lado. Os dois olham a agenda ao mesmo tempo: quadra 3, sábado às 10h, livre. Os dois pegam a caneta e anotam. No sábado, duas turmas na mesma quadra.

Ninguém mentiu. A agenda estava livre quando cada um olhou. O problema é que "estava livre" é uma informação sobre o **passado**, e os dois agiram como se ela valesse para o momento da anotação.

No FairFare, com duas requests, A e B, pedindo o mesmo horário:

```
tempo ─────────────────────────────────────────────────────────────►

A:  find_overlapping ──► [] ──────────► create ──► 201
B:      find_overlapping ──► [] ──────────► create ──► 201
                            ▲
                            └── nenhuma das duas gravou ainda:
                                as duas veem a agenda vazia
```

A **janela** é o trecho entre a verificação e a gravação. Se a segunda request faz a verificação dela **dentro** da janela da primeira, as duas passam. O nome técnico disso é **condição de corrida** (*race condition*): o resultado depende de quem chega primeiro, numa ordem que ninguém controla.

A janela não é um descuido de uma linha. Ela é a forma do código. Qualquer "verifica, depois age", com o estado guardado em outro lugar, tem uma.

## Reproduzir, sem truque

A bancada tem um script para isso, `bancada/corrida.py`. Cada rodada faz três coisas:

1. cria um usuário e uma quadra **novos**, para começar com a agenda vazia;
2. monta um corpo de reserva, sempre o mesmo: essa quadra, 1º de junho de 2030, das 10h às 12h;
3. dispara **N** cópias desse `POST /bookings` ao mesmo tempo, com `asyncio.gather`, e conta as respostas.

O coração dele:

```python
    respostas = await asyncio.gather(
        *(http.post("/bookings", json=corpo, headers=cliente_novo()) for _ in range(n))
    )
    return Counter(r.status_code for r in respostas)
```

Se o app estivesse certo, cada rodada teria **um** `201` e N − 1 `409`.

### O rate limiter, e o `X-Forwarded-For`

Tem um detalhe no meio do caminho: o rate limiter do capítulo 3. Ele dá um balde de fichas para cada IP, e todas as requests do script saem de `127.0.0.1`. Com rodadas seguidas, o balde esvazia e os `429` sujariam a contagem.

O `cliente_novo()` resolve isso com o truque da lição 08 do capítulo 3. Lá, a lição mostrou que o uvicorn, por padrão, confia no `X-Forwarded-For` de quem conecta a partir de `127.0.0.1`. E o script está em `127.0.0.1`. Então cada request leva um `X-Forwarded-For` diferente, e o rate limiter vê um cliente novo em cada uma:

```python
def cliente_novo() -> dict[str, str]:
    k = next(_ips)
    return {"X-Forwarded-For": f"10.0.{k // 250}.{k % 250 + 1}"}
```

Lá isso era uma brecha. Aqui é uma ferramenta de bancada, usada de propósito. O log do uvicorn confirma que o header foi aceito:

```console
INFO:     10.0.0.2:0 - "POST /users HTTP/1.1" 201 Created
INFO:     10.0.0.3:0 - "POST /resources HTTP/1.1" 201 Created
INFO:     10.0.0.4:0 - "POST /bookings HTTP/1.1" 201 Created
INFO:     10.0.0.5:0 - "POST /bookings HTTP/1.1" 201 Created
```

Nenhum `429` nas duas execuções abaixo.

### Os números

Num terminal, o app:

```bash
uv run uvicorn app.main:app --port 8000
```

Noutro, duas pessoas ao mesmo tempo, dez rodadas:

```console
$ B=chapters/04-o-banco-de-dados-de-verdade/bancada
$ uv run python $B/corrida.py --n 2 --rodadas 10
rodada  1: 201×2
rodada  2: 201×2
rodada  3: 201×2
rodada  4: 201×2
rodada  5: 201×2
rodada  6: 201×2
rodada  7: 201×2
rodada  8: 201×2
rodada  9: 201×2
rodada 10: 201×2

rodadas com mais de uma reserva criada: 10/10
```

Dez de dez. Agora cinco pessoas:

```console
$ uv run python $B/corrida.py --n 5 --rodadas 10
rodada  1: 201×2  409×3
rodada  2: 201×5
rodada  3: 201×5
rodada  4: 201×5
rodada  5: 201×5
rodada  6: 201×5
rodada  7: 201×5
rodada  8: 201×5
rodada  9: 201×5
rodada 10: 201×5

rodadas com mais de uma reserva criada: 10/10
```

Nove rodadas com **cinco** reservas para o mesmo horário. A primeira teve "só" duas: três requests chegaram depois que alguém já tinha gravado, e levaram `409`. A corrida é sobre tempo, e nem toda request cai dentro da janela. *(Não medi por que justo a primeira rodada. Minha suspeita é aquecimento: na primeira rodada o cliente ainda está abrindo as conexões, e as requests saem menos juntas. Nas rodadas seguintes, as conexões já existem.)*

Repare no que **não** foi preciso. Nenhum `sleep` plantado no service. Nenhum app modificado. A janela abre sozinha, porque entre a verificação e a gravação existe pelo menos um `await` de ida ao banco. Enquanto a request A espera a resposta do `find_overlapping`, o event loop vai atender a B, que chega à mesma pergunta e recebe a mesma resposta. É o capítulo 2 trabalhando contra você.

## E no SQLite?

Uma suspeita natural: o FairFare passou três capítulos no SQLite, e ninguém viu isso. Será que o SQLite protegia?

A lição 03 contou que o SQLite **serializa as escritas**: só uma por vez no arquivo. Parece que isso fecharia a janela. Medi, para não ficar no palpite: subi o app do fim do capítulo 3 (tag `v-chapter-03`, ainda no SQLite) num diretório à parte, na mesma porta 8000, e rodei o mesmo script.

```console
$ uv run python $B/corrida.py --n 2 --rodadas 10
...
rodadas com mais de uma reserva criada: 9/10
$ uv run python $B/corrida.py --n 5 --rodadas 10
...
rodadas com mais de uma reserva criada: 9/10
$ uv run python $B/corrida.py --n 10 --rodadas 20
...
rodadas com mais de uma reserva criada: 19/20
```

Com N=2 e N=5, as rodadas 2 a 10 deram `201×2` e `201×5`, como no PostgreSQL. Nessas execuções, a primeira rodada deu um `201` só, de novo a primeira. Rodando de novo, nem sempre: com N=2, já deu `201×2` logo na primeira. **O SQLite não protegia nada.** A corrida estava lá desde o capítulo 1, como a ERRATA diz.

Por que "uma escrita por vez" não basta? Pedi ao `sqlite3` para imprimir cada comando que ele recebe, numa reserva só:

```console
SQLITE> SELECT bookings.id, bookings.user_id, bookings.resource_id, bookings.s
--- check feito, agora o create
SQLITE> BEGIN
SQLITE> INSERT INTO bookings (user_id, resource_id, starts_at, ends_at) VALUES
SQLITE> COMMIT
```

*(Esse rastreamento foi um script de bancada, rodado uma vez e jogado fora. Ele não está no repositório.)*

O `BEGIN` só aparece **depois** do `SELECT`. A verificação roda fora de qualquer transação, e a fila do SQLite só começa na gravação. Na agenda do clube, é como ter uma caneta só no balcão. Ana e Bruno fazem fila para **anotar**, sim. Mas os dois já **olharam** a agenda antes de entrar na fila. A caneta única organiza as anotações, não as decisões.

Então o que escondia a corrida não era o banco. Era a suíte. Nenhum teste do FairFare manda duas requests ao mesmo tempo. Todos fazem uma, esperam a resposta, fazem a próxima. É o "teste que passava no banco errado" da lição 03, outra vez, com uma diferença: lá o teste olhava o banco errado. Aqui ele nem olhava. Um teste que só manda uma request por vez **não tem como ver** uma corrida, em banco nenhum.

## As duplicatas ficam no banco

As reservas que o script criou estão gravadas. Dá para ver, direto no `psql`:

```console
$ docker compose exec postgres psql -U fairfare -c "SELECT resource_id, count(*) FROM bookings WHERE starts_at = '2030-06-01 10:00+00' GROUP BY 1 HAVING count(*) > 1 ORDER BY 1;"
 resource_id | count 
-------------+-------
          51 |     2
          52 |     2
          53 |     2
          54 |     2
          55 |     2
          56 |     2
          57 |     2
          58 |     2
          59 |     2
          60 |     2
          61 |     2
          62 |     5
          63 |     5
          64 |     5
          65 |     5
          66 |     5
          67 |     5
          68 |     5
          69 |     5
          70 |     5
(20 rows)
```

As quadras 51 a 60 são da execução com N=2. Da 61 à 70, da execução com N=5. A 61 é aquela primeira rodada, com duas. *(O `HAVING count(*) > 1` está aí porque as quadras 1 a 50 do seed da lição 06 também têm uma reserva nesse horário, cada uma. Uma só, então não é duplicata.)*

**Não apague.** Isso não é sujeira de bancada: é exatamente o estado que um banco de produção teria depois de meses com esse defeito. A lição 11 vai tentar pôr uma regra no banco que proíbe sobreposição, e essas linhas vão estar no caminho. De propósito.

## O que fica declarado

- **A corrida continua aberta no app.** Esta lição só a reproduziu. As lições 08 a 11 a fecham.
- **Os números são desta máquina**, com um processo uvicorn só. Mais rodadas ou outro N mudam a contagem, mas não o veredito: uma janela que abre em dez de dez rodadas não é azar.
- **A medição no SQLite** foi feita com o app da tag `v-chapter-03`, num diretório temporário que já não existe. O script foi o mesmo `corrida.py`.
- **O `X-Forwarded-For` funciona porque o uvicorn confia em `127.0.0.1`**, o padrão que a lição 08 do capítulo 3 mostrou. Se você subiu o app com `--forwarded-allow-ips` apontando para outro endereço, vai ver `429`.

## O que você deve conseguir fazer agora

- Desenhar a linha do tempo da corrida com duas requests, e marcar nela onde fica a janela.
- Subir o FairFare e reproduzir a reserva dupla com o `corrida.py`.
- Explicar por que o `await` entre o `find_overlapping` e o `create` basta para a janela abrir.
- Explicar por que "verificar antes" não basta, e por que "uma escrita por vez" também não.
- Achar as duplicatas no banco com um `GROUP BY ... HAVING`.
