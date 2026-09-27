from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import bookings, resources, users

app = FastAPI(title="FairFare")

# A página da bancada mora em http://localhost:8080. Origem explícita: nada de "*".
# Content-Type já é permitido por padrão; quando a API pedir Authorization (cap. 5),
# ele entra em allow_headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["GET", "POST", "DELETE"],
)

app.include_router(users.router)
app.include_router(resources.router)
app.include_router(bookings.router)
