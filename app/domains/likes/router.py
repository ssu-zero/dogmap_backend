from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_dog_id
from app.domains.courses.repository import get_course_by_id
from app.domains.likes import repository
from app.domains.likes.schemas import CourseLikeStatus

router = APIRouter(prefix="/courses", tags=["likes"])

_COURSE_NOT_FOUND_DETAIL = "코스를 찾을 수 없습니다"


@router.post("/{course_id}/like", response_model=CourseLikeStatus, summary="코스 좋아요")
def like_course_endpoint(
    course_id: int,
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> CourseLikeStatus:
    """코스에 좋아요를 남긴다. 이미 눌렀다면 그대로 idempotent하게 처리한다."""
    if get_course_by_id(db, course_id) is None:
        raise HTTPException(status_code=404, detail=_COURSE_NOT_FOUND_DETAIL)

    if repository.get_by_dog_and_course(db, dog_id, course_id) is None:
        repository.create(db, dog_id=dog_id, course_id=course_id)

    return CourseLikeStatus(
        course_id=course_id, is_liked=True, like_count=repository.count_by_course_id(db, course_id)
    )


@router.delete("/{course_id}/like", response_model=CourseLikeStatus, summary="코스 좋아요 취소")
def unlike_course_endpoint(
    course_id: int,
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> CourseLikeStatus:
    """코스 좋아요를 취소한다. 좋아요를 누른 적 없어도 idempotent하게 처리한다."""
    if get_course_by_id(db, course_id) is None:
        raise HTTPException(status_code=404, detail=_COURSE_NOT_FOUND_DETAIL)

    like = repository.get_by_dog_and_course(db, dog_id, course_id)
    if like is not None:
        repository.delete(db, like)

    return CourseLikeStatus(
        course_id=course_id, is_liked=False, like_count=repository.count_by_course_id(db, course_id)
    )
