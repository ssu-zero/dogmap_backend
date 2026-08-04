from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.core.database import get_db
from app.domains.dogs import service
from app.domains.dogs.schemas import DogCreate, DogResponse, DogUpdate

router = APIRouter(prefix="/dogs", tags=["dogs"])


@router.post("", response_model=DogResponse, status_code=201)
def create_dog(dog_in: DogCreate, db: Session = Depends(get_db)) -> DogResponse:
    return service.create_dog(db, dog_in)


@router.get("/{dog_id}", response_model=DogResponse)
def get_dog(dog_id: int, db: Session = Depends(get_db)) -> DogResponse:
    try:
        return service.get_dog_or_404(db, dog_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[DogResponse])
def list_dogs(kakao_id: int, db: Session = Depends(get_db)) -> list[DogResponse]:
    return service.list_dogs(db, kakao_id)


@router.patch("/{dog_id}", response_model=DogResponse)
def update_dog(dog_id: int, dog_in: DogUpdate, db: Session = Depends(get_db)) -> DogResponse:
    try:
        return service.update_dog(db, dog_id, dog_in)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{dog_id}", status_code=204)
def delete_dog(dog_id: int, db: Session = Depends(get_db)) -> None:
    try:
        service.delete_dog(db, dog_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
