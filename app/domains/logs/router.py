from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.core.database import get_db
from app.domains.logs import service
from app.domains.logs.schemas import LogCreate, LogResponse, LogUpdate

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("", response_model=LogResponse, status_code=201)
def create_log(log_in: LogCreate, db: Session = Depends(get_db)) -> LogResponse:
    return service.create_log(db, log_in)


@router.get("/{log_id}", response_model=LogResponse)
def get_log(log_id: int, db: Session = Depends(get_db)) -> LogResponse:
    try:
        return service.get_log_or_404(db, log_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[LogResponse])
def list_logs(dog_id: int, db: Session = Depends(get_db)) -> list[LogResponse]:
    return service.list_logs(db, dog_id)


@router.patch("/{log_id}", response_model=LogResponse)
def update_log(log_id: int, log_in: LogUpdate, db: Session = Depends(get_db)) -> LogResponse:
    try:
        return service.update_log(db, log_id, log_in)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{log_id}", status_code=204)
def delete_log(log_id: int, db: Session = Depends(get_db)) -> None:
    try:
        service.delete_log(db, log_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
