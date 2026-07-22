# Lição 01 — Ferramentas: uv e o esqueleto do projeto

No capítulo 0 você não instalou nada. Era proposital: HTTP se aprende com `curl` e um servidor de 200 linhas. Agora vamos construir um app de verdade, com dependências de verdade — e antes de escrever a primeira linha dele, precisamos resolver um problema clássico.

## A dor: "funciona na minha máquina"

O ritual antigo do Python é conhecido: cria um venv, ativa, `pip install fastapi`, torce. Ele falha de dois jeitos silenciosos:

1. **Versões de loteria.** `pip install fastapi` hoje instala uma versão; daqui a seis meses, outra. Você e um colega rodam "o mesmo projeto" com bibliotecas diferentes — e um bug aparece só na máquina de um de vocês. Sem um registro exato do que foi instalado, cada instalação é um sorteio.
2. **O Python errado.** Este curso usa Python 3.12. Seu sistema pode ter 3.10, 3.11, ou um 3.14 recém-saído. Venv nenhum resolve isso: ele embrulha o Python que você já tem, não o que o projeto pede.

"Funciona na minha máquina" não é azar. É o resultado natural de instalar dependências sem contrato.

## uv em uma frase

O **uv** é o gerenciador de projeto que usaremos o curso inteiro: ele resolve as dependências, cria o venv **e instala o próprio Python** se a versão certa não estiver na sua máquina.

Pense num despachante bom: você entrega uma pasta com o que precisa, ele volta com todos os documentos emitidos, na versão certa, sem você enfrentar fila nenhuma. Em termos técnicos: o uv substitui, de uma vez, o trio pip + venv + pyenv — instalar pacotes, isolar o ambiente e gerenciar versões do Python viram um comando só. (E é rápido. Você vai notar.)

Instalação, se ainda não tem: [docs.astral.sh/uv/getting-started/installation](https://docs.astral.sh/uv/getting-started/installation/). Confira com `uv --version`.

## Os três comandos do dia a dia

**`uv sync`** — materializa o projeto na sua máquina: lê o que o projeto declara, cria o `.venv` e instala tudo, na versão exata registrada. É o primeiro comando depois de clonar qualquer repo com uv — inclusive este. Se você não tiver o Python 3.12, a transcrição é esta:

```console
$ uv sync
Downloading cpython-3.12.12-linux-x86_64-gnu (download) (32.3MiB)
 Downloaded cpython-3.12.12-linux-x86_64-gnu (download)
Using CPython 3.12.12
Creating virtual environment at: .venv
Resolved 16 packages in 0.45ms
Installed 14 packages in 5ms
 + fastapi==0.139.0
 + pydantic==2.13.4
 + uvicorn==0.51.0
 ...
```

Repare na primeira linha: o uv **baixou um Python inteiro** porque o projeto pede 3.12. Nenhum sudo, nenhum tutorial de 40 minutos. É isso que o pyenv fazia — agora de brinde.

**`uv run <comando>`** — roda qualquer comando dentro do ambiente do projeto, sem precisar "ativar" nada:

```bash
uv run python --version
```

Sem o `uv run`, `python` é o Python do seu sistema, cego para as dependências do projeto. Com ele, é sempre o Python certo com as bibliotecas certas. Regra do curso: **todo comando Python passa por `uv run`**. Esqueça que `pip` e `activate` existem.

**`uv add <pacote>`** — adiciona uma dependência ao contrato do projeto e a instala. Foi o que rodamos para criar este capítulo:

```bash
uv add fastapi uvicorn
uv add --dev ruff
```

O `--dev` marca ferramentas que ajudam a *desenvolver* mas que o app não precisa para *rodar* — o ruff, logo abaixo, é o exemplo perfeito.

## O contrato e o carimbo: pyproject.toml vs uv.lock

Os comandos acima mexem em dois arquivos, e a diferença entre eles é a cura do "funciona na minha máquina":

- **`pyproject.toml`** é o **contrato**, escrito para humanos: "este projeto quer `fastapi>=0.139.0` e Python `>=3.12`". Declara intenção, com folga de versão.
- **`uv.lock`** é o **carimbo do cartório**, escrito pela máquina: "no dia tal, esse contrato foi resolvido para exatamente `fastapi==0.139.0`, `pydantic==2.13.4`, `starlette==1.3.1`..." — cada pacote, incluindo os que vieram de arrasto, com versão e checksum exatos.

O `uv sync` instala o que está no **lock**, não o que está no contrato. Por isso ele é reproduzível: a mesma versão de tudo, em qualquer máquina, em qualquer data.

E por isso **o `uv.lock` está versionado no git** deste repo. Num app (que é o nosso caso), o lockfile entra no repositório — é ele que garante que você, eu e o servidor de produção rodamos os mesmos bytes. Você nunca edita esse arquivo; o uv cuida dele.

Também fixamos o Python num arquivo próprio, o `.python-version` (conteúdo: `3.12`). É ele que o uv consulta antes de criar o venv — e que disparou aquele download na transcrição.

## ruff em cinco linhas

O **ruff** é nosso linter e formatador: aponta erros bobos (variável não usada, import esquecido) e formata o código num estilo único. Dois comandos:

```bash
uv run ruff check .
uv run ruff format .
```

O primeiro acusa problemas; o segundo arruma a formatação. Por que um formatador importa: ele **encerra discussões**. Ninguém mais gasta review debatendo aspas simples ou dupla — a máquina decide, todo mundo aceita, o diff só mostra o que mudou de verdade. Todo commit deste curso passa pelos dois antes de entrar.

## O que você deve conseguir fazer agora

- Clonar este repo e rodar `uv sync` — e explicar o que acabou de acontecer.
- `uv run python --version` mostrando `3.12.x`, mesmo que seu sistema tenha outro Python.
- `uv run ruff check .` saindo limpo.
- Explicar a diferença entre `pyproject.toml` e `uv.lock` em uma frase cada — e por que o lock está no git.
