# Bancada do capítulo 5

Scripts para medir o app por dentro. Nenhum deles é código do app.
Quase todos falam com o PostgreSQL do `compose.yaml`: suba antes com `docker compose up -d --wait`.
A exceção está marcada na seção do script.

## `conta_consultas.py` — lição 03

Quantas consultas, e quanto tempo, custa um `GET /bookings`. O script fala com o FairFare
**em processo** (o `httpx2` com `ASGITransport`, sem uvicorn) e pendura na engine do app o
mesmo contador que o guardião dos testes usa (`tests/apoio.py::conta_consultas`).

Precisa de volume no banco de dev. O `seed.sql` do capítulo 4 cria 1 usuário, 50 quadras e
quantas reservas você pedir.

> **Atenção:** o seed **apaga** `users`, `resources` e `bookings` do banco de dev (e, via
> `CASCADE`, tudo o que depender deles).

```bash
docker compose exec -T postgres psql -U fairfare -d fairfare -v linhas=2000 \
  < chapters/04-o-banco-de-dados-de-verdade/bancada/seed.sql

# O endpoint de verdade: imprime reservas=<n> consultas=<n> tempo=<ms>
uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py

# A mesma listagem direto pelo ORM, com joinedload nas duas relações
uv run python chapters/05-relacoes-e-dinheiro/bancada/conta_consultas.py --joinedload
```

O tempo do `--joinedload` não passa por HTTP nem pelo JSON. Não compare com o do endpoint.

## `float.py` — lição 05

Seis desastres do `float` com dinheiro, um por seção, cada um com a conta e o resultado.
É Python puro: não fala com o banco nem com o app, e não precisa do compose de pé.
O `Decimal` aparece só como lupa: `Decimal(um_float)` mostra o número que o `float` guarda.

```bash
uv run python chapters/05-relacoes-e-dinheiro/bancada/float.py
```

O desastre 1 soma num laço de propósito. O `sum()` do Python 3.12 compensa o erro e daria `1.0`.

## `saldos.py` — lição 09

Três jeitos de calcular o saldo de cada membro, medidos lado a lado: (a) Python ingênuo, com
duas consultas por membro; (b) Python carregando tudo, com `selectinload(Expense.partes)`;
(c) o banco somando, com a consulta do app (`GroupRepository.balances`). Cada um roda 3 vezes,
numa sessão nova, e imprime consultas, linhas trazidas para o Python e tempo. No fim, o script
confere que os três dão o mesmo resultado.

> **Atenção:** o script escreve no banco de dev. Ele cria 10 usuários
> (`saldos01@bancada-l09.fairfare.dev` a `saldos10@...`), o grupo
> "bancada/saldos.py (lição 09)" e N despesas divididas entre os 10. No fim, apaga tudo isso.
> A limpeza só mira o que o script cria: grupos com esse nome cujos membros são todos
> usuários da bancada, e usuários da bancada que nada mais referencia. Se uma rodada morrer
> no meio, a próxima limpa a sobra. As sequências de id não voltam: os ids gastos ficam
> como buracos em `users`, `groups` e `expenses`. Sequência não é transacional, e
> devolvê-la à mão poderia fazer um insert concorrente reusar um id já em uso.

```bash
# 2000 despesas (padrão)
uv run python chapters/05-relacoes-e-dinheiro/bancada/saldos.py

# 20000 despesas: 200 mil linhas de partes
uv run python chapters/05-relacoes-e-dinheiro/bancada/saldos.py --despesas 20000
```

O (c) chama o repository direto, então conta **1** consulta. Pelo endpoint são 2: o service
confere antes se o grupo existe. É o número que o guardião dos testes cobra.
