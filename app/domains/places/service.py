from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.domains.places import repository
from app.domains.places.models import Place
from app.domains.places.schemas import PlaceCreate, PlaceUpdate


def get_place_or_404(db: Session, place_id: int) -> Place:
    place = repository.get_place(db, place_id)
    if place is None:
        raise NotFoundError("Place", place_id)
    return place


def list_places(db: Session) -> list[Place]:
    return repository.list_places(db)


def create_place(db: Session, place_in: PlaceCreate) -> Place:
    return repository.create_place(db, place_in)


def update_place(db: Session, place_id: int, place_in: PlaceUpdate) -> Place:
    place = get_place_or_404(db, place_id)
    return repository.update_place(db, place, place_in)


def delete_place(db: Session, place_id: int) -> None:
    place = get_place_or_404(db, place_id)
    repository.delete_place(db, place)
