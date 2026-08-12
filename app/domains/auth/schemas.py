from enum import StrEnum

from pydantic import BaseModel


class KakaoLoginRequest(BaseModel):
    code: str  # 프론트엔드가 카카오 인가 코드 받기(redirect)로 얻은 인가 코드


class LoginStatus(StrEnum):
    LOGIN = "LOGIN"  # 기존 회원 — access_token으로 바로 이용 가능
    SIGNUP_REQUIRED = "SIGNUP_REQUIRED"  # 신규 회원 — signup_token으로 강아지 프로필 등록 필요


class KakaoLoginResponse(BaseModel):
    status: LoginStatus
    access_token: str | None = None  # status=LOGIN일 때만 존재
    signup_token: str | None = None  # status=SIGNUP_REQUIRED일 때만 존재
    dog_id: int | None = None
    kakao_nickname: str | None = None
    kakao_profile_image_url: str | None = None
