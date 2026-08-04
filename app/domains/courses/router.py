from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.core.database import get_db
from app.domains.courses import service
from app.domains.courses.schemas import (
    CourseCreate,
    CourseGenerateRequest,
    CourseResponse,
)

router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("", response_model=CourseResponse, status_code=201)
def create_course(course_in: CourseCreate, db: Session = Depends(get_db)) -> CourseResponse:
    return service.create_course(db, course_in)


@router.post("/generate", response_model=CourseResponse, status_code=201)
def generate_course(
    request: CourseGenerateRequest, db: Session = Depends(get_db)
) -> CourseResponse:
    return service.generate_course(db, request)


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: int, db: Session = Depends(get_db)) -> CourseResponse:
    try:
        return service.get_course_or_404(db, course_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[CourseResponse])
def list_courses(db: Session = Depends(get_db)) -> list[CourseResponse]:
    return service.list_courses(db)


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: int, db: Session = Depends(get_db)) -> None:
    try:
        service.delete_course(db, course_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
