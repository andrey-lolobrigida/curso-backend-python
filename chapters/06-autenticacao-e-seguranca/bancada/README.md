# Bancada do capítulo 6

Scripts para ver a segurança por dentro. **Nada daqui faz parte do FairFare.**
Eles montam à mão o que o app entrega a uma biblioteca, para o mecanismo aparecer na tela.
Nenhum deles é exemplo de produção: alguns fazem errado de propósito, porque errado é o que a
gente veio medir.

| Script | Lição | Comando | O que mostra |
|---|---|---|---|
| `senhas.py` | 02 | `uv run python chapters/06-autenticacao-e-seguranca/bancada/senhas.py` | quatro jeitos de guardar senha (texto puro, sha256, sha256 com sal, scrypt) e o ataque de dicionário contra cada um, com sha256 por segundo e ms por scrypt medidos |
| `argon2_no_loop.py` | 03 | `uv run python chapters/06-autenticacao-e-seguranca/bancada/argon2_no_loop.py` | quanto custa um `hash` e um `verify` (relógio × CPU); oito `verify` do argon2 chamados no loop × numa thread, com um batimento medindo quanto o loop travou; e 20 `verify` em sequência × em 4 threads, para ver o argon2 soltar o GIL |
| `enumeracao.py` | 06 | `uv run python chapters/06-autenticacao-e-seguranca/bancada/enumeracao.py` (com o uvicorn de pé na porta 8000) | 30 logins de email inexistente × 30 de senha errada, intercalados, contra o app de verdade: mediana, mínimo e máximo de cada grupo, a diferença e a razão entre as medianas |

*(A tabela cresce junto com o capítulo.)*

O `senhas.py` é só biblioteca padrão: não fala com o banco nem com o app, e não precisa do
compose de pé. Os sais e os hashes do ato 3 mudam a cada execução. Os tempos são de um
núcleo só, chamando o `hashlib` (que roda em C) de um laço Python: os seus vão ser outros, e o
que importa é a distância entre os esquemas.

O `argon2_no_loop.py` também não fala com o banco nem com o app. Ele usa o `argon2-cffi`, que
já vem com o projeto desde a lição 03. Os atrasos dançam de uma rodada para outra: o que
importa é a ordem de grandeza, centenas de ms com o `verify` no loop e poucas dezenas (ou
menos) com ele numa thread.

O `enumeracao.py` é o único daqui que fala com o app. Suba o FairFare antes
(`uv run uvicorn app.main:app --port 8000`; em outra porta, passe `--url http://localhost:PORTA`). Ele cria, uma vez só, o usuário
`bancada.cap06@example.com` no banco de dev; da segunda vez em diante o cadastro responde 409, e
tudo bem. Entre uma request e outra ele espera 0,25 s, para não esvaziar o balde do rate limiter
(20 fichas, 5 por segundo). Leva uns 20 s. O número que importa é a diferença entre as medianas:
uns 85 ms antes do hash fantasma, quase zero depois. A razão muda bastante com o quanto a
máquina descansa entre as requests.
Para ver o "antes" na sua máquina, comente a linha `await confere_senha(HASH_FANTASMA, senha)`
no `app/services/auth.py`, reinicie o uvicorn e rode de novo. Depois descomente. Enquanto ela
estiver comentada, o `ruff` reclama do `HASH_FANTASMA` sem uso; é esperado.
