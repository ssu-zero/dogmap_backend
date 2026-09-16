from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer_scheme = HTTPBearer(auto_error=False)


class TokenType(StrEnum):
    """ACCESS: 로그인 완료 후 발급되는 세션 토큰(dog_id 보유).
    SIGNUP: 카카오 로그인은 됐지만 아직 강아지 프로필이 없는 회원가입 중간 단계 토큰(kakao_id만 보유).
    두 토큰을 같은 알고리즘으로 서명하므로 type 클레임으로 반드시 용도를 구분해야 한다.
    """

    ACCESS = "access"
    SIGNUP = "signup"


def _create_token(claims: dict[str, Any], token_type: TokenType, expires_delta: timedelta) -> str:
    payload = {
        **claims,
        "type": token_type.value,
        "exp": datetime.now(UTC) + expires_delta,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(dog_id: int) -> str:
    return _create_token(
        {"dog_id": dog_id},
        TokenType.ACCESS,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_signup_token(kakao_id: int) -> str:
    return _create_token(
        {"kakao_id": kakao_id},
        TokenType.SIGNUP,
        timedelta(minutes=settings.SIGNUP_TOKEN_EXPIRE_MINUTES),
    )


def _decode(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰이 만료되었습니다"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다"
        ) from exc

    if payload.get("type") != expected_type.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="잘못된 토큰 종류입니다"
        )
    return payload


def _credentials(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization 헤더가 필요합니다"
        )
    return credentials.credentials


def get_current_dog_id(token: str = Depends(_credentials)) -> int:
    """일반 API 인증 의존성. Authorization: Bearer {access_token} 을 검증하고 dog_id를 반환한다."""
    payload = _decode(token, TokenType.ACCESS)
    return payload["dog_id"]


def get_current_dog_id_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> int | None:
    """비로그인도 허용하되 로그인 시엔 dog_id를 알아야 하는 API(코스 목록/상세 조회 등)용.
    헤더가 아예 없으면 None, 있는데 무효한 토큰이면 여전히 401을 낸다.
    """
    if credentials is None:
        return None
    payload = _decode(credentials.credentials, TokenType.ACCESS)
    return payload["dog_id"]


def get_signup_kakao_id(token: str = Depends(_credentials)) -> int:
    """강아지 프로필 등록(회원가입 완료) 전용 의존성. signup_token을 검증하고 kakao_id를 반환한다."""
    payload = _decode(token, TokenType.SIGNUP)
    return payload["kakao_id"]
