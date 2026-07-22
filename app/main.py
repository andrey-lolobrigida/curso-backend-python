from fastapi import FastAPI

from app.routers import bookings, resources, users

app = FastAPI(title="FairFare")

app.include_router(users.router)
app.include_router(resources.router)
app.include_router(bookings.router)
