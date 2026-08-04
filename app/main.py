from fastapi import FastAPI

from app.domains.courses.router import router as courses_router
from app.domains.dogs.router import router as dogs_router
from app.domains.likes.router import router as likes_router
from app.domains.logs.router import router as logs_router
from app.domains.places.router import router as places_router
from app.domains.saves.router import router as saves_router

app = FastAPI()

app.include_router(dogs_router)
app.include_router(courses_router)
app.include_router(places_router)
app.include_router(logs_router)
app.include_router(likes_router)
app.include_router(saves_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
