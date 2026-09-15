from fastapi import APIRouter

from app.domains.auth.router import router as auth_router
from app.domains.courses.router import router as courses_router
from app.domains.dogs.router import router as dogs_router
from app.domains.logs.router import router as logs_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(dogs_router)
api_router.include_router(courses_router)
api_router.include_router(logs_router)
