from enum import StrEnum

from pydantic import AnyHttpUrl, BaseModel, Field


class KakaoLoginRequest(BaseModel):
    code: str = Field(description="카카오 인가 코드 받기(redirect) 완료 후 리다이렉트 URL의 code 파라미터 값")
    redirect_uri: AnyHttpUrl | None = Field(
        default=None,
        description=(
            "인가 코드를 발급받을 때 사용한 callback URI. "
            "서버의 KAKAO_REDIRECT_URI 또는 KAKAO_ALLOWED_REDIRECT_URIS에 등록된 값만 허용."
        ),
    )


class LoginStatus(StrEnum):
    LOGIN = "LOGIN"  # 기존 회원 — access_token으로 바로 이용 가능
    SIGNUP_REQUIRED = "SIGNUP_REQUIRED"  # 신규 회원 — signup_token으로 강아지 프로필 등록 필요


class KakaoLoginResponse(BaseModel):
    status: LoginStatus = Field(
        description=(
            "LOGIN: 기존 회원, access_token 바로 사용. "
            "SIGNUP_REQUIRED: 신규 회원, signup_token으로 POST /dogs 호출해 회원가입 완료 필요"
        )
    )
    access_token: str | None = Field(default=None, description="status=LOGIN일 때만 존재")
    signup_token: str | None = Field(
        default=None, description="status=SIGNUP_REQUIRED일 때만 존재. POST /dogs 호출 시 Bearer 토큰으로 사용"
    )
    dog_id: int | None = Field(default=None, description="status=LOGIN일 때만 존재")
    kakao_nickname: str | None = Field(default=None, description="카카오 프로필 닉네임 (동의 항목 미설정 시 없을 수 있음)")
    kakao_profile_image_url: str | None = Field(
        default=None, description="카카오 프로필 이미지 URL (동의 항목 미설정 시 없을 수 있음)"
    )
