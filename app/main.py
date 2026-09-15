from fastapi import FastAPI

from app.api.v1.routes import api_router

app = FastAPI(
    title="DogMap API",
    description="강아지 산책 코스 추천 서비스 DogMap의 백엔드 API",
)

app.include_router(api_router, prefix="/api")


@app.get("/health", summary="헬스체크")
def health_check():
    return {"status": "ok"}
