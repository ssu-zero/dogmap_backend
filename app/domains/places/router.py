from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.core.database import get_db
from app.domains.places import service
from app.domains.places.schemas import PlaceCreate, PlaceResponse, PlaceUpdate

router = APIRouter(prefix="/places", tags=["places"])


@router.post("", response_model=PlaceResponse, status_code=201)
def create_place(place_in: PlaceCreate, db: Session = Depends(get_db)) -> PlaceResponse:
    return service.create_place(db, place_in)


@router.get("/{place_id}", response_model=PlaceResponse)
def get_place(place_id: int, db: Session = Depends(get_db)) -> PlaceResponse:
    try:
        return service.get_place_or_404(db, place_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[PlaceResponse])
def list_places(db: Session = Depends(get_db)) -> list[PlaceResponse]:
    return service.list_places(db)


@router.patch("/{place_id}", response_model=PlaceResponse)
def update_place(
    place_id: int, place_in: PlaceUpdate, db: Session = Depends(get_db)
) -> PlaceResponse:
    try:
        return service.update_place(db, place_id, place_in)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{place_id}", status_code=204)
def delete_place(place_id: int, db: Session = Depends(get_db)) -> None:
    try:
        service.delete_place(db, place_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
