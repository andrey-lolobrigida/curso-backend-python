# Bancada do capítulo 4

Scripts para medir e quebrar o banco de propósito. Nenhum deles é código do app.
Todos falam com o PostgreSQL do `compose.yaml`: suba antes com `docker compose up -d --wait`.

| Script | Lição | O que mostra |
|---|---|---|
| `pool.py` | 05 | o pool do app estourando (`pool`) e a soma dos pools estourando o servidor (`servidor`) |
| `seed.sql` | 06 | um milhão de reservas com `generate_series`, sem sobreposição (~20 s nesta máquina; **apaga** os dados do banco de dev) |
| `explain.sql` | 06 | o plano da consulta do `find_overlapping` |
| `corrida.py` | 07, 10, 11 | N reservas idênticas ao mesmo tempo, pelo uvicorn de verdade; conta quantas passaram |
