# Bancada do capítulo 6

Scripts para ver a segurança por dentro. **Nada daqui faz parte do FairFare.**
Eles montam à mão o que o app entrega a uma biblioteca, para o mecanismo aparecer na tela.
Nenhum deles é exemplo de produção: alguns fazem errado de propósito, porque errado é o que a
gente veio medir.

| Script | Lição | Comando | O que mostra |
|---|---|---|---|
| `senhas.py` | 02 | `uv run python chapters/06-autenticacao-e-seguranca/bancada/senhas.py` | quatro jeitos de guardar senha (texto puro, sha256, sha256 com sal, scrypt) e o ataque de dicionário contra cada um, com sha256 por segundo e ms por scrypt medidos |

*(A tabela cresce junto com o capítulo.)*

O `senhas.py` é só biblioteca padrão: não fala com o banco nem com o app, e não precisa do
compose de pé. Os sais e os hashes do ato 3 mudam a cada execução. Os tempos são de um
núcleo só, chamando o `hashlib` (que roda em C) de um laço Python: os seus vão ser outros, e o
que importa é a distância entre os esquemas.
