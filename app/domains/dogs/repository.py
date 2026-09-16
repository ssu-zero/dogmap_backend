from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.dogs.models import Dog, DogSize


def get_by_kakao_id(db: Session, kakao_id: int) -> Dog | None:
    return db.execute(select(Dog).where(Dog.kakao_id == kakao_id)).scalar_one_or_none()


def get_by_id(db: Session, dog_id: int) -> Dog | None:
    return db.get(Dog, dog_id)


def create(
    db: Session,
    *,
    kakao_id: int,
    name: str,
    size: DogSize,
    age: int | None = None,
    image_url: str | None = None,
) -> Dog:
    dog = Dog(
        kakao_id=kakao_id,
        name=name,
        size=size,
        age=age,
        image_url=image_url,
    )
    db.add(dog)
    db.commit()
    db.refresh(dog)
    return dog


def update(db: Session, dog: Dog, **fields: object) -> Dog:
    for key, value in fields.items():
        setattr(dog, key, value)
    db.commit()
    db.refresh(dog)
    return dog
