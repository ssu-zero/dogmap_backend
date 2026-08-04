from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.likes.models import Like
from app.domains.likes.schemas import LikeCreate


def get_like(db: Session, course_id: int, dog_id: int) -> Like | None:
    return db.get(Like, {"course_id": course_id, "dog_id": dog_id})


def list_likes_by_dog(db: Session, dog_id: int) -> list[Like]:
    stmt = select(Like).where(Like.dog_id == dog_id)
    return list(db.scalars(stmt))


def create_like(db: Session, like_in: LikeCreate) -> Like:
    like = Like(**like_in.model_dump())
    db.add(like)
    db.commit()
    db.refresh(like)
    return like


def delete_like(db: Session, like: Like) -> None:
    db.delete(like)
    db.commit()
