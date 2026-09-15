from fastapi import FastAPI

from app.api.v1.routes import api_router

app = FastAPI()

app.include_router(api_router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok"}
