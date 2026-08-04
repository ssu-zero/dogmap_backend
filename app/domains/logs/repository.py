from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.logs.models import Log
from app.domains.logs.schemas import LogCreate, LogUpdate


def get_log(db: Session, log_id: int) -> Log | None:
    return db.get(Log, log_id)


def list_logs_by_dog(db: Session, dog_id: int) -> list[Log]:
    stmt = select(Log).where(Log.dog_id == dog_id)
    return list(db.scalars(stmt))


def create_log(db: Session, log_in: LogCreate) -> Log:
    log = Log(**log_in.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def update_log(db: Session, log: Log, log_in: LogUpdate) -> Log:
    for field, value in log_in.model_dump(exclude_unset=True).items():
        setattr(log, field, value)
    db.commit()
    db.refresh(log)
    return log


def delete_log(db: Session, log: Log) -> None:
    db.delete(log)
    db.commit()
