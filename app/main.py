from fastapi import FastAPI

from app.domains.auth.router import router as auth_router
from app.domains.dogs.router import router as dogs_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(dogs_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
