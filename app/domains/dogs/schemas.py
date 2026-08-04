from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.dogs.models import DogSize


class DogBase(BaseModel):
    name: str
    age: int
    weight: int
    size: DogSize
    image_url: str | None = None


class DogCreate(DogBase):
    kakao_id: int


class DogUpdate(BaseModel):
    name: str | None = None
    age: int | None = None
    weight: int | None = None
    size: DogSize | None = None
    image_url: str | None = None


class DogResponse(DogBase):
    model_config = ConfigDict(from_attributes=True)

    dog_id: int
    kakao_id: int
    created_at: datetime
    updated_at: datetime
