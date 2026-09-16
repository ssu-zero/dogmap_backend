from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.core.database import get_db
from app.core.security import get_current_dog_id
from app.domains.logs.schemas import LogRead, LogUpdate
from app.domains.logs.service import (
    NotLogOwnerError,
    get_log_for_owner,
    list_logs_for_dog,
    update_log,
)

router = APIRouter(prefix="/logs", tags=["logs"])

_LOG_NOT_FOUND_DETAIL = "산책 기록을 찾을 수 없습니다"


@router.get("", response_model=list[LogRead], summary="내 산책 기록 목록 조회")
def list_logs_endpoint(
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> list[LogRead]:
    """내가 기록한 산책을 최신순으로 조회한다."""
    return list_logs_for_dog(db, dog_id)


@router.get("/{log_id}", response_model=LogRead, summary="산책 기록 상세 조회")
def get_log_endpoint(
    log_id: int,
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> LogRead:
    """산책 기록 하나를 조회한다(본인 기록만 — 존재하지 않거나 남의 기록이면 404)."""
    log = get_log_for_owner(db, log_id, dog_id)
    if log is None:
        raise HTTPException(status_code=404, detail=_LOG_NOT_FOUND_DETAIL)
    return log


@router.patch("/{log_id}", response_model=LogRead, summary="산책 일지 수정")
def update_log_endpoint(
    log_id: int,
    body: LogUpdate,
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> LogRead:
    """산책 일지(diary)를 작성/수정한다(본인 기록만 가능). body에 보낸 필드만 수정되는
    partial update — 수정하지 않을 필드는 아예 생략하면 된다."""
    update_data = body.model_dump(exclude_unset=True)
    try:
        return update_log(db, log_id, dog_id, **update_data)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=_LOG_NOT_FOUND_DETAIL) from exc
    except NotLogOwnerError as exc:
        raise HTTPException(status_code=403, detail="본인의 산책 기록만 수정할 수 있습니다") from exc
