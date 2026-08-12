from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_signup_token
from app.domains.auth.external.kakao_client import KakaoOAuthClient
from app.domains.auth.schemas import KakaoLoginResponse, LoginStatus
from app.domains.dogs.repository import get_by_kakao_id


async def login_with_kakao(db: Session, code: str) -> KakaoLoginResponse:
    """인가 코드로 카카오 사용자를 확인하고, 기존 회원이면 access_token을,
    신규 회원이면 signup_token(강아지 프로필 등록용)을 발급한다.
    """
    async with KakaoOAuthClient() as client:
        kakao_access_token = await client.get_access_token(code)
        user_info = await client.get_user_info(kakao_access_token)

    dog = get_by_kakao_id(db, user_info.kakao_id)

    if dog is not None:
        return KakaoLoginResponse(
            status=LoginStatus.LOGIN,
            access_token=create_access_token(dog.dog_id),
            dog_id=dog.dog_id,
        )

    return KakaoLoginResponse(
        status=LoginStatus.SIGNUP_REQUIRED,
        signup_token=create_signup_token(user_info.kakao_id),
        kakao_nickname=user_info.nickname,
        kakao_profile_image_url=user_info.profile_image_url,
    )
