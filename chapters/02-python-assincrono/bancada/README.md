# A bancada

Isto é **instrumento, não produto**.

Todo o resto deste curso vive numa única base de código que cresce: o FairFare, em `app/`. Esta pasta é a exceção declarada. São aparelhos de medição — servidores de mentira, disparadores de carga, scripts que existem só para fazer um comportamento aparecer na tela.

Regras da bancada:

- **Nada daqui entra no FairFare.** Se um trecho parecer útil no app, ele volta pelo caminho normal: uma lição que o motive.
- **Nada daqui é exemplo de produção.** Alguns scripts fazem coisas propositalmente erradas (dormir dentro de uma rota `async`, travar o processo com CPU) porque errado é o que a gente veio medir.
- **Tudo aqui roda.** Os números que aparecem nas lições saíram destes arquivos, na máquina do autor. Rode você também: os seus vão ser parecidos, não idênticos, e o capítulo diz sempre o que importa — a ordem de grandeza.

## Os aparelhos

| Arquivo | O que é | Nasce na lição |
|---|---|---|
| `servidor.py` | Um FastAPI com duas rotas idênticas que dormem 1s — uma `def`, outra `async def` | 01 |
| `carga.py` | Dispara N requests ao mesmo tempo e cronometra o total | 01 |
| `loop.py` | O event loop em quatro cenas: `await` em série, `gather`, o sleep errado, corrotina sem `await` | 03 |
| `lazy_load.py` | Falha de propósito: o `MissingGreenlet` do lazy load no SQLAlchemy async | 05 |

*(A tabela cresce junto com o capítulo.)*

## Como usar

Sobe o servidor numa aba:

```bash
uv run uvicorn bancada.servidor:app --port 8123 --app-dir chapters/02-python-assincrono
```

Dispara a carga em outra:

```bash
uv run python chapters/02-python-assincrono/bancada/carga.py http://localhost:8123/sync 10
```

O segundo argumento é o número de requests simultâneas. O default é 10.
