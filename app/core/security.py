from fastapi import Header, HTTPException, status


def get_current_kakao_id(x_kakao_id: int = Header(..., alias="X-Kakao-Id")) -> int:
    """카카오 로그인 연동 전 임시 인증 의존성.

    TODO: 카카오 OAuth 액세스 토큰 검증 로직으로 교체.
    """
    if x_kakao_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Kakao-Id header"
        )
    return x_kakao_id
