from fastapi import APIRouter

from app.domains.courses.router import router as courses_router

api_router = APIRouter()
api_router.include_router(courses_router)
