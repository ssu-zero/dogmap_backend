from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_current_dog_id, get_signup_kakao_id
from app.domains.dogs import repository
from app.domains.dogs.schemas import DogCreate, DogResponse, SignupCompleteResponse

router = APIRouter(prefix="/dogs", tags=["dogs"])


@router.post("", response_model=SignupCompleteResponse, status_code=status.HTTP_201_CREATED)
def register_dog(
    body: DogCreate,
    kakao_id: int = Depends(get_signup_kakao_id),
    db: Session = Depends(get_db),
):
    """카카오 로그인 직후(SIGNUP_REQUIRED) 강아지 프로필을 등록해 회원가입을 완료한다."""
    if repository.get_by_kakao_id(db, kakao_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 등록된 회원입니다")

    dog = repository.create(db, kakao_id=kakao_id, **body.model_dump())
    return SignupCompleteResponse(
        access_token=create_access_token(dog.dog_id),
        dog=DogResponse.model_validate(dog),
    )


@router.get("/me", response_model=DogResponse)
def get_my_profile(
    dog_id: int = Depends(get_current_dog_id),
    db: Session = Depends(get_db),
):
    dog = repository.get_by_id(db, dog_id)
    if dog is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="강아지를 찾을 수 없습니다")
    return dog
