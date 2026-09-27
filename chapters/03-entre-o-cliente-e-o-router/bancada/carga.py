"""Bancada: dispara N requests e conta o que voltou, status por status.

Evolução do carga.py do capítulo 2. Além do tempo total, conta os códigos de
status um a um, aceita headers extras e sabe abrir uma conexão nova por request.

Uso:
  uv run python chapters/03-entre-o-cliente-e-o-router/bancada/carga.py <url> [n]
      [--header 'Nome: valor']... [--nova-conexao] [--em-serie]

No valor de um header, {i} vira o número da request (de 1 até n):
  --header 'X-Forwarded-For: 10.0.0.{i}'
"""

import argparse
import asyncio
import time
from collections import Counter

import httpx2


def ler_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url")
    parser.add_argument("n", nargs="?", type=int, default=10, help="quantas requests (default 10)")
    parser.add_argument(
        "--header",
        "-H",
        action="append",
        default=[],
        metavar="'Nome: valor'",
        help="header extra; pode repetir",
    )
    parser.add_argument(
        "--nova-conexao", action="store_true", help="abre (e fecha) uma conexão TCP por request"
    )
    parser.add_argument(
        "--em-serie", action="store_true", help="uma request de cada vez, em vez de todas juntas"
    )
    return parser.parse_args()


def headers_da_request(brutos: list[str], i: int) -> dict[str, str]:
    headers = {}
    for bruto in brutos:
        nome, _, valor = bruto.partition(":")
        headers[nome.strip()] = valor.strip().replace("{i}", str(i))
    return headers


async def uma(client: httpx2.AsyncClient, url: str, headers: dict[str, str]) -> httpx2.Response:
    return await client.get(url, headers=headers)


async def uma_com_conexao_nova(url: str, headers: dict[str, str]) -> httpx2.Response:
    async with httpx2.AsyncClient(timeout=120) as client:  # um cliente novo = uma conexão nova
        return await client.get(url, headers=headers)


async def main() -> None:
    args = ler_argumentos()

    async with httpx2.AsyncClient(timeout=120) as client:

        def disparo(i: int):
            headers = headers_da_request(args.header, i)
            if args.nova_conexao:
                return uma_com_conexao_nova(args.url, headers)
            return uma(client, args.url, headers)

        comeco = time.perf_counter()
        if args.em_serie:
            respostas = [await disparo(i) for i in range(1, args.n + 1)]
        else:
            respostas = await asyncio.gather(*(disparo(i) for i in range(1, args.n + 1)))
        total = time.perf_counter() - comeco

    contagem = Counter(resposta.status_code for resposta in respostas)
    resumo = "  ".join(f"{status}: {quantos}" for status, quantos in sorted(contagem.items()))
    linha = f"{args.n} requests em {total:.2f}s  status → {resumo}"

    retry_after = next(
        (r.headers["retry-after"] for r in respostas if "retry-after" in r.headers), None
    )
    if retry_after is not None:
        linha += f"  (Retry-After: {retry_after}s)"
    print(linha)


asyncio.run(main())
