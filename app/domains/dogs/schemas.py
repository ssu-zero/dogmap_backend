from pydantic import BaseModel

from app.domains.dogs.models import DogSize


class DogCreate(BaseModel):
    name: str
    size: DogSize
    age: int | None = None
    weight: float | None = None
    image_url: str | None = None


class DogResponse(BaseModel):
    dog_id: int
    name: str
    size: DogSize
    age: int | None
    weight: float | None
    image_url: str | None

    model_config = {"from_attributes": True}


class SignupCompleteResponse(BaseModel):
    """강아지 프로필 등록(회원가입 완료) 응답. 이후 요청은 이 access_token으로 인증한다."""

    access_token: str
    dog: DogResponse
