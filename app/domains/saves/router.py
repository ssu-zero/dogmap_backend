from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_dog_id
from app.domains.courses.repository import get_course_by_id
from app.domains.courses.schemas import CourseSummary
from app.domains.courses.service import list_saved_courses
from app.domains.saves import repository
from app.domains.saves.schemas import CourseSaveStatus

# /courses/{id}/save(토글)와 /saves(내 저장 목록)를 함께 쓰기 때문에 고정 prefix
# 대신 경로마다 전체 경로를 명시한다.
router = APIRouter(tags=["saves"])

_COURSE_NOT_FOUND_DETAIL = "코스를 찾을 수 없습니다"


@router.get("/saves", response_model=list[CourseSummary], summary="내가 저장한 코스 목록 조회")
def list_saved_courses_endpoint(
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> list[CourseSummary]:
    """내가 저장(북마크)한 코스를 저장한 순서(최신순)로 조회한다."""
    return list_saved_courses(db, dog_id)


@router.post("/courses/{course_id}/save", response_model=CourseSaveStatus, summary="코스 저장(북마크)")
def save_course_endpoint(
    course_id: int,
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> CourseSaveStatus:
    """코스를 저장(북마크)한다. 이미 저장했다면 그대로 idempotent하게 처리한다."""
    if get_course_by_id(db, course_id) is None:
        raise HTTPException(status_code=404, detail=_COURSE_NOT_FOUND_DETAIL)

    if repository.get_by_dog_and_course(db, dog_id, course_id) is None:
        repository.create(db, dog_id=dog_id, course_id=course_id)

    return CourseSaveStatus(
        course_id=course_id, is_saved=True, save_count=repository.count_by_course_id(db, course_id)
    )


@router.delete("/courses/{course_id}/save", response_model=CourseSaveStatus, summary="코스 저장 취소")
def unsave_course_endpoint(
    course_id: int,
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> CourseSaveStatus:
    """코스 저장(북마크)을 취소한다. 저장한 적 없어도 idempotent하게 처리한다."""
    if get_course_by_id(db, course_id) is None:
        raise HTTPException(status_code=404, detail=_COURSE_NOT_FOUND_DETAIL)

    save = repository.get_by_dog_and_course(db, dog_id, course_id)
    if save is not None:
        repository.delete(db, save)

    return CourseSaveStatus(
        course_id=course_id, is_saved=False, save_count=repository.count_by_course_id(db, course_id)
    )
