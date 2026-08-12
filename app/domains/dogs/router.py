from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_current_dog_id, get_signup_kakao_id
from app.domains.dogs import repository
from app.domains.dogs.schemas import DogCreate, DogResponse, DogUpdate, SignupCompleteResponse

router = APIRouter(prefix="/dogs", tags=["dogs"])


@router.post(
    "",
    response_model=SignupCompleteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="온보딩: 강아지 프로필 등록 (회원가입 완료)",
    description=(
        "카카오 로그인 직후 `signup_token`으로 인증해서 호출한다 (Authorize에 signup_token 입력).\n\n"
        "성공하면 이후 모든 인증 API에 쓸 `access_token`을 발급한다."
    ),
    responses={
        409: {"description": "이미 이 카카오 계정으로 등록된 회원인 경우"},
    },
)
def register_dog(
    body: DogCreate,
    kakao_id: int = Depends(get_signup_kakao_id),
    db: Session = Depends(get_db),
):
    if repository.get_by_kakao_id(db, kakao_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 등록된 회원입니다")

    dog = repository.create(db, kakao_id=kakao_id, **body.model_dump())
    return SignupCompleteResponse(
        access_token=create_access_token(dog.dog_id),
        dog=DogResponse.model_validate(dog),
    )


@router.get(
    "/me",
    response_model=DogResponse,
    summary="내 프로필 조회",
    description="`access_token`으로 인증해서 호출한다 (Authorize에 access_token 입력).",
    responses={
        404: {"description": "토큰은 유효하지만 대상 강아지가 DB에 없는 경우(탈퇴 등)"},
    },
)
def get_my_profile(
    dog_id: int = Depends(get_current_dog_id),
    db: Session = Depends(get_db),
):
    dog = repository.get_by_id(db, dog_id)
    if dog is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="강아지를 찾을 수 없습니다")
    return dog


@router.patch(
    "/me",
    response_model=DogResponse,
    summary="마이페이지: 내 프로필 수정",
    description=(
        "`access_token`으로 인증해서 호출한다. body에 보낸 필드만 수정되는 partial update — "
        "수정하지 않을 필드는 아예 생략하면 된다."
    ),
    responses={
        404: {"description": "토큰은 유효하지만 대상 강아지가 DB에 없는 경우(탈퇴 등)"},
    },
)
def update_my_profile(
    body: DogUpdate,
    dog_id: int = Depends(get_current_dog_id),
    db: Session = Depends(get_db),
):
    dog = repository.get_by_id(db, dog_id)
    if dog is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="강아지를 찾을 수 없습니다")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return dog

    return repository.update(db, dog, **update_data)
