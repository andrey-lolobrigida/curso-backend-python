"""Bancada: um app ASGI sem framework nenhum.

É isso que o uvicorn chama. O FastAPI, por baixo, é uma função com esta mesma
assinatura — só que com muito mais coisa dentro.

Sobe com:
  uv run uvicorn asgi_cru:app --app-dir chapters/03-entre-o-cliente-e-o-router/bancada
"""


async def acompanhar_lifespan(receive, send) -> None:
    """O servidor avisa quando nasce e quando morre. A gente só responde 'ok'."""
    while True:
        mensagem = await receive()
        if mensagem["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif mensagem["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


async def app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        await acompanhar_lifespan(receive, send)
        return

    # A partir daqui, scope["type"] == "http": uma request chegou.
    # (ip, porta) de quem conectou — guarde essa linha; a lição 08 volta nela
    cliente = scope["client"]
    corpo = f"{scope['method']} {scope['path']} — você é {cliente}\n".encode()

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send({"type": "http.response.body", "body": corpo})
