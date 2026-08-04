from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.dogs.models import Dog
from app.domains.dogs.schemas import DogCreate, DogUpdate


def get_dog(db: Session, dog_id: int) -> Dog | None:
    return db.get(Dog, dog_id)


def list_dogs_by_kakao_id(db: Session, kakao_id: int) -> list[Dog]:
    stmt = select(Dog).where(Dog.kakao_id == kakao_id)
    return list(db.scalars(stmt))


def create_dog(db: Session, dog_in: DogCreate) -> Dog:
    dog = Dog(**dog_in.model_dump())
    db.add(dog)
    db.commit()
    db.refresh(dog)
    return dog


def update_dog(db: Session, dog: Dog, dog_in: DogUpdate) -> Dog:
    for field, value in dog_in.model_dump(exclude_unset=True).items():
        setattr(dog, field, value)
    db.commit()
    db.refresh(dog)
    return dog


def delete_dog(db: Session, dog: Dog) -> None:
    db.delete(dog)
    db.commit()
