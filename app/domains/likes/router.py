from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.likes import repository
from app.domains.likes.schemas import LikeCreate, LikeResponse

router = APIRouter(prefix="/likes", tags=["likes"])


@router.post("", response_model=LikeResponse, status_code=201)
def create_like(like_in: LikeCreate, db: Session = Depends(get_db)) -> LikeResponse:
    return repository.create_like(db, like_in)


@router.get("", response_model=list[LikeResponse])
def list_likes(dog_id: int, db: Session = Depends(get_db)) -> list[LikeResponse]:
    return repository.list_likes_by_dog(db, dog_id)


@router.delete("", status_code=204)
def delete_like(course_id: int, dog_id: int, db: Session = Depends(get_db)) -> None:
    like = repository.get_like(db, course_id, dog_id)
    if like is None:
        raise HTTPException(status_code=404, detail="Like not found")
    repository.delete_like(db, like)
