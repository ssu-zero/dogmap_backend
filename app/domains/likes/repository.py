from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domains.courses.models import CoursePlace
from app.domains.likes.models import Like


def count_by_place_ids(db: Session, place_ids: list[int]) -> dict[int, int]:
    """place_id별 좋아요 개수. 장소 자체에 좋아요가 있는 게 아니라, 그 장소가 등록된
    코스들이 받은 좋아요를 합산한 값이다 — 코스 좋아요는 그 코스의 모든 장소가 함께
    받는 것으로 취급한다. 좋아요가 하나도 없는 place_id는 결과에 나타나지 않으므로,
    호출부에서 dict.get(place_id, 0)으로 조회해야 한다."""
    if not place_ids:
        return {}
    stmt = (
        select(CoursePlace.place_id, func.count(Like.like_id))
        .join(Like, Like.course_id == CoursePlace.course_id)
        .where(CoursePlace.place_id.in_(place_ids))
        .group_by(CoursePlace.place_id)
    )
    return dict(db.execute(stmt).all())


def liked_place_ids(db: Session, dog_id: int, place_ids: list[int]) -> set[int]:
    """place_ids 중 dog_id가 좋아요한 코스에 등록된 place_id 집합."""
    if not place_ids:
        return set()
    stmt = (
        select(CoursePlace.place_id)
        .join(Like, Like.course_id == CoursePlace.course_id)
        .where(CoursePlace.place_id.in_(place_ids), Like.dog_id == dog_id)
        .distinct()
    )
    return set(db.scalars(stmt).all())


def count_by_course_ids(db: Session, course_ids: list[int]) -> dict[int, int]:
    """course_id별 좋아요 개수(배치). 좋아요가 없는 course_id는 결과에 나타나지 않으므로
    호출부에서 dict.get(course_id, 0)으로 조회해야 한다."""
    if not course_ids:
        return {}
    stmt = (
        select(Like.course_id, func.count(Like.like_id))
        .where(Like.course_id.in_(course_ids))
        .group_by(Like.course_id)
    )
    return dict(db.execute(stmt).all())


def liked_course_ids(db: Session, dog_id: int, course_ids: list[int]) -> set[int]:
    """course_ids 중 dog_id가 좋아요한 course_id 집합(배치)."""
    if not course_ids:
        return set()
    stmt = select(Like.course_id).where(Like.dog_id == dog_id, Like.course_id.in_(course_ids))
    return set(db.scalars(stmt).all())


def get_by_dog_and_course(db: Session, dog_id: int, course_id: int) -> Like | None:
    stmt = select(Like).where(Like.dog_id == dog_id, Like.course_id == course_id)
    return db.scalars(stmt).one_or_none()


def count_by_course_id(db: Session, course_id: int) -> int:
    stmt = select(func.count(Like.like_id)).where(Like.course_id == course_id)
    return db.scalar(stmt) or 0


def create(db: Session, *, dog_id: int, course_id: int) -> Like:
    like = Like(dog_id=dog_id, course_id=course_id)
    db.add(like)
    db.commit()
    return like


def delete(db: Session, like: Like) -> None:
    db.delete(like)
    db.commit()
