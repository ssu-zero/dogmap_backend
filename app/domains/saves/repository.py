from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.saves.models import Save
from app.domains.saves.schemas import SaveCreate


def get_save(db: Session, course_id: int, dog_id: int) -> Save | None:
    return db.get(Save, {"course_id": course_id, "dog_id": dog_id})


def list_saves_by_dog(db: Session, dog_id: int) -> list[Save]:
    stmt = select(Save).where(Save.dog_id == dog_id)
    return list(db.scalars(stmt))


def create_save(db: Session, save_in: SaveCreate) -> Save:
    save = Save(**save_in.model_dump())
    db.add(save)
    db.commit()
    db.refresh(save)
    return save


def delete_save(db: Session, save: Save) -> None:
    db.delete(save)
    db.commit()
