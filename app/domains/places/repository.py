from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.places.models import Location, Place
from app.domains.places.schemas import PlaceCreate, PlaceUpdate


def get_place(db: Session, place_id: int) -> Place | None:
    return db.get(Place, place_id)


def list_places(db: Session) -> list[Place]:
    return list(db.scalars(select(Place)))


def create_place(db: Session, place_in: PlaceCreate) -> Place:
    location = Location(**place_in.location.model_dump())
    place = Place(**place_in.model_dump(exclude={"location"}), location=location)
    db.add(place)
    db.commit()
    db.refresh(place)
    return place


def update_place(db: Session, place: Place, place_in: PlaceUpdate) -> Place:
    for field, value in place_in.model_dump(exclude_unset=True).items():
        setattr(place, field, value)
    db.commit()
    db.refresh(place)
    return place


def delete_place(db: Session, place: Place) -> None:
    db.delete(place)
    db.commit()
