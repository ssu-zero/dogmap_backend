from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.domains.logs import repository
from app.domains.logs.models import Log
from app.domains.logs.schemas import LogCreate, LogUpdate


def get_log_or_404(db: Session, log_id: int) -> Log:
    log = repository.get_log(db, log_id)
    if log is None:
        raise NotFoundError("Log", log_id)
    return log


def list_logs(db: Session, dog_id: int) -> list[Log]:
    return repository.list_logs_by_dog(db, dog_id)


def create_log(db: Session, log_in: LogCreate) -> Log:
    return repository.create_log(db, log_in)


def update_log(db: Session, log_id: int, log_in: LogUpdate) -> Log:
    log = get_log_or_404(db, log_id)
    return repository.update_log(db, log, log_in)


def delete_log(db: Session, log_id: int) -> None:
    log = get_log_or_404(db, log_id)
    repository.delete_log(db, log)
