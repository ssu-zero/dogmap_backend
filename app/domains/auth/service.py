from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, create_signup_token
from app.domains.auth.external.kakao_client import KakaoOAuthClient
from app.domains.auth.schemas import KakaoLoginResponse, LoginStatus
from app.domains.dogs.repository import get_by_kakao_id


class KakaoRedirectUriError(ValueError):
    """클라이언트가 서버에 등록되지 않은 OAuth callback URI를 보냈다."""


def resolve_kakao_redirect_uri(redirect_uri: str | None) -> str:
    """OAuth 인가와 토큰 교환에 같은, 사전 등록된 URI만 사용한다."""
    if redirect_uri is None:
        return settings.KAKAO_REDIRECT_URI

    allowed_uris = {
        settings.KAKAO_REDIRECT_URI.rstrip("/"),
        *(
            uri.strip().rstrip("/")
            for uri in settings.KAKAO_ALLOWED_REDIRECT_URIS.split(",")
            if uri.strip()
        ),
    }
    normalized_redirect_uri = redirect_uri.rstrip("/")
    if normalized_redirect_uri not in allowed_uris:
        raise KakaoRedirectUriError("허용되지 않은 카카오 로그인 callback 주소입니다.")

    return redirect_uri


async def login_with_kakao(
    db: Session, code: str, redirect_uri: str | None = None
) -> KakaoLoginResponse:
    """인가 코드로 카카오 사용자를 확인하고, 기존 회원이면 access_token을,
    신규 회원이면 signup_token(강아지 프로필 등록용)을 발급한다.
    """
    async with KakaoOAuthClient(
        redirect_uri=resolve_kakao_redirect_uri(redirect_uri)
    ) as client:
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
