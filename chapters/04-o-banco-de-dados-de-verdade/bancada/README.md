# Bancada do capítulo 4

Scripts para medir e quebrar o banco de propósito. Nenhum deles é código do app.
Todos falam com o PostgreSQL do `compose.yaml`: suba antes com `docker compose up -d --wait`.

| Script | Lição | O que mostra |
|---|---|---|
| `pool.py` | 05 | o pool do app estourando (`pool`) e a soma dos pools estourando o servidor (`servidor`) |
