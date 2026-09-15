from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.domains.logs import repository
from app.domains.logs.models import Log


class NotLogOwnerError(Exception):
    """요청자가 해당 산책 기록의 소유자가 아닐 때(수정 API에서 사용)."""


def list_logs_for_dog(db: Session, dog_id: int) -> list[Log]:
    """내가 기록한 산책을 최신순으로 조회한다."""
    return repository.list_by_dog_id(db, dog_id)


def get_log_for_owner(db: Session, log_id: int, dog_id: int) -> Log | None:
    """산책 기록 상세조회. 존재하지 않거나 본인 것이 아니면 None을 반환해 존재 자체를
    숨긴다(라우터에서 404로 처리) — 산책 일지는 코스와 달리 공개 개념이 없다."""
    log = repository.get_by_id(db, log_id)
    if log is None or log.dog_id != dog_id:
        return None
    return log


def update_log(db: Session, log_id: int, dog_id: int, **fields: object) -> Log:
    """산책 기록을 수정한다(현재는 diary만). 본인 기록만 가능."""
    log = repository.get_by_id(db, log_id)
    if log is None:
        raise NotFoundError("Log", log_id)
    if log.dog_id != dog_id:
        raise NotLogOwnerError

    return repository.update(db, log, **fields)
