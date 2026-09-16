from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domains.saves.models import Save


def list_course_ids_by_dog_id(db: Session, dog_id: int) -> list[int]:
    """dog_id가 저장(북마크)한 course_id를 저장한 순서(최신순)로 반환한다.

    created_at은 DB의 now()(초 단위 정밀도)라 짧은 시간에 여러 번 저장하면 값이
    같을 수 있다 — save_id(자동증가)를 2차 정렬 기준으로 둬서 항상 삽입 순서를
    보장한다.
    """
    stmt = (
        select(Save.course_id)
        .where(Save.dog_id == dog_id)
        .order_by(Save.created_at.desc(), Save.save_id.desc())
    )
    return list(db.scalars(stmt).all())


def count_by_course_ids(db: Session, course_ids: list[int]) -> dict[int, int]:
    """course_id별 저장 개수(배치). 저장이 없는 course_id는 결과에 나타나지 않으므로
    호출부에서 dict.get(course_id, 0)으로 조회해야 한다."""
    if not course_ids:
        return {}
    stmt = (
        select(Save.course_id, func.count(Save.save_id))
        .where(Save.course_id.in_(course_ids))
        .group_by(Save.course_id)
    )
    return dict(db.execute(stmt).all())


def saved_course_ids(db: Session, dog_id: int, course_ids: list[int]) -> set[int]:
    """course_ids 중 dog_id가 저장한 course_id 집합(배치)."""
    if not course_ids:
        return set()
    stmt = select(Save.course_id).where(Save.dog_id == dog_id, Save.course_id.in_(course_ids))
    return set(db.scalars(stmt).all())


def get_by_dog_and_course(db: Session, dog_id: int, course_id: int) -> Save | None:
    stmt = select(Save).where(Save.dog_id == dog_id, Save.course_id == course_id)
    return db.scalars(stmt).one_or_none()


def count_by_course_id(db: Session, course_id: int) -> int:
    stmt = select(func.count(Save.save_id)).where(Save.course_id == course_id)
    return db.scalar(stmt) or 0


def create(db: Session, *, dog_id: int, course_id: int) -> Save:
    save = Save(dog_id=dog_id, course_id=course_id)
    db.add(save)
    db.commit()
    return save


def delete(db: Session, save: Save) -> None:
    db.delete(save)
    db.commit()
