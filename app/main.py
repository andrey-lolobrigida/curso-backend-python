from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import bookings, resources, users

app = FastAPI(title="FairFare")

# Ordem importa, e é invertida: o ÚLTIMO add_middleware é a camada de FORA.
# Rate limiter por dentro, CORS por fora. Assim o preflight (OPTIONS) é respondido
# pelo CORS sem gastar ficha, e um 429 atravessa o CORS e sai com os headers —
# senão o browser mostra "erro de CORS" e esconde o 429 de verdade.
app.add_middleware(RateLimitMiddleware, capacidade=20, recarga_por_segundo=5.0)

# A página da bancada mora em http://localhost:8080. Origem explícita: nada de "*".
# Content-Type já é permitido por padrão; quando a API pedir Authorization (cap. 6),
# ele entra em allow_headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["GET", "POST", "DELETE"],
)

app.include_router(users.router)
app.include_router(resources.router)
app.include_router(bookings.router)
