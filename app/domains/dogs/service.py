from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.domains.dogs import repository
from app.domains.dogs.models import Dog
from app.domains.dogs.schemas import DogCreate, DogUpdate


def get_dog_or_404(db: Session, dog_id: int) -> Dog:
    dog = repository.get_dog(db, dog_id)
    if dog is None:
        raise NotFoundError("Dog", dog_id)
    return dog


def list_dogs(db: Session, kakao_id: int) -> list[Dog]:
    return repository.list_dogs_by_kakao_id(db, kakao_id)


def create_dog(db: Session, dog_in: DogCreate) -> Dog:
    return repository.create_dog(db, dog_in)


def update_dog(db: Session, dog_id: int, dog_in: DogUpdate) -> Dog:
    dog = get_dog_or_404(db, dog_id)
    return repository.update_dog(db, dog, dog_in)


def delete_dog(db: Session, dog_id: int) -> None:
    dog = get_dog_or_404(db, dog_id)
    repository.delete_dog(db, dog)
