from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.logs.models import Log


def get_by_id(db: Session, log_id: int) -> Log | None:
    return db.get(Log, log_id)


def list_by_dog_id(db: Session, dog_id: int) -> list[Log]:
    stmt = (
        select(Log).where(Log.dog_id == dog_id).order_by(Log.started_at.desc())
    )
    return list(db.scalars(stmt).all())


def create(
    db: Session, *, dog_id: int, course_id: int | None, started_at: datetime, ended_at: datetime | None
) -> Log:
    log = Log(dog_id=dog_id, course_id=course_id, started_at=started_at, ended_at=ended_at)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def update(db: Session, log: Log, **fields: object) -> Log:
    for key, value in fields.items():
        setattr(log, key, value)
    db.commit()
    db.refresh(log)
    return log
