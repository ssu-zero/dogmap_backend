from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.saves import repository
from app.domains.saves.schemas import SaveCreate, SaveResponse

router = APIRouter(prefix="/saves", tags=["saves"])


@router.post("", response_model=SaveResponse, status_code=201)
def create_save(save_in: SaveCreate, db: Session = Depends(get_db)) -> SaveResponse:
    return repository.create_save(db, save_in)


@router.get("", response_model=list[SaveResponse])
def list_saves(dog_id: int, db: Session = Depends(get_db)) -> list[SaveResponse]:
    return repository.list_saves_by_dog(db, dog_id)


@router.delete("", status_code=204)
def delete_save(course_id: int, dog_id: int, db: Session = Depends(get_db)) -> None:
    save = repository.get_save(db, course_id, dog_id)
    if save is None:
        raise HTTPException(status_code=404, detail="Save not found")
    repository.delete_save(db, save)
