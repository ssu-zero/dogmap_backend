"""카카오 OAuth2 (인가 코드 방식) 연동 클라이언트.

프론트엔드가 카카오 로그인 화면에서 받은 인가 코드(code)를 백엔드로 넘겨주면,
이 클라이언트가 (1) 코드를 카카오 액세스 토큰으로 교환하고 (2) 그 토큰으로
카카오 사용자 정보(kakao_id)를 조회한다.
"""

from dataclasses import dataclass

import httpx

from app.common.exceptions import ExternalApiError
from app.core.config import settings

_DEFAULT_TIMEOUT = 5.0
_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
_USER_ME_URL = "https://kapi.kakao.com/v2/user/me"


class KakaoOAuthError(ExternalApiError):
    def __init__(self, endpoint: str, detail: str):
        self.endpoint = endpoint
        self.detail = detail
        super().__init__(f"{endpoint} 실패: {detail}")


@dataclass
class KakaoUserInfo:
    kakao_id: int
    nickname: str | None
    profile_image_url: str | None


class KakaoOAuthClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ):
        self._client_id = client_id if client_id is not None else settings.KAKAO_REST_API_KEY
        self._client_secret = (
            client_secret if client_secret is not None else settings.KAKAO_CLIENT_SECRET
        )
        self._redirect_uri = redirect_uri or settings.KAKAO_REDIRECT_URI
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> "KakaoOAuthClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_access_token(self, code: str) -> str:
        """인가 코드를 카카오 액세스 토큰으로 교환한다."""
        data = {
            "grant_type": "authorization_code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "code": code,
        }
        if self._client_secret:
            data["client_secret"] = self._client_secret

        try:
            response = await self._client.post(
                _TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            payload = response.json()
        except httpx.HTTPError as exc:
            raise KakaoOAuthError("oauth/token", str(exc)) from exc

        if response.status_code != 200 or "access_token" not in payload:
            detail = payload.get("error_description", payload.get("error", "알 수 없는 오류"))
            raise KakaoOAuthError("oauth/token", detail)

        return payload["access_token"]

    async def get_user_info(self, access_token: str) -> KakaoUserInfo:
        """카카오 액세스 토큰으로 사용자 식별값(id)과 프로필을 조회한다."""
        try:
            response = await self._client.get(
                _USER_ME_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            payload = response.json()
        except httpx.HTTPError as exc:
            raise KakaoOAuthError("user/me", str(exc)) from exc

        if response.status_code != 200 or "id" not in payload:
            detail = payload.get("msg", "알 수 없는 오류")
            raise KakaoOAuthError("user/me", detail)

        kakao_account = payload.get("kakao_account") or {}
        profile = kakao_account.get("profile") or {}

        return KakaoUserInfo(
            kakao_id=payload["id"],
            nickname=profile.get("nickname"),
            profile_image_url=profile.get("profile_image_url"),
        )
