from pydantic import BaseModel, Field

from app.domains.dogs.models import DogSize


class DogCreate(BaseModel):
    name: str = Field(description="반려견 이름", examples=["강강이"])
    size: DogSize = Field(
        description="크기 — SMALL(10kg 이하) / MEDIUM(10~25kg) / LARGE(25kg 이상)",
        examples=["MEDIUM"],
    )
    age: int = Field(description="나이(세)", examples=[3])
    weight: float | None = Field(
        default=None, description="체중(kg). 이 온보딩 화면에서는 입력받지 않는 선택 항목"
    )
    image_url: str | None = Field(
        default=None,
        description="프로필 이미지 URL. 파일 업로드는 아직 미지원 — 업로드된 이미지의 URL만 받는다",
    )


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

    access_token: str = Field(description="이후 모든 인증 API에 Bearer 토큰으로 사용")
    dog: DogResponse
