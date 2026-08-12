from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.auth.external.kakao_client import KakaoOAuthError
from app.domains.auth.schemas import KakaoLoginRequest, KakaoLoginResponse
from app.domains.auth.service import login_with_kakao

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/kakao/login",
    response_model=KakaoLoginResponse,
    summary="카카오 로그인",
    description=(
        "카카오 인가 코드 받기(redirect)로 얻은 code를 받아 로그인 처리한다.\n\n"
        "- 기존 회원: status=LOGIN, access_token 반환 → 바로 서비스 이용.\n"
        "- 신규 회원: status=SIGNUP_REQUIRED, signup_token 반환 → "
        "프론트는 강아지 프로필 입력 화면으로 이동 후 그 토큰으로 POST /dogs 호출."
    ),
    responses={
        400: {"description": "인가 코드가 만료/재사용됐거나 카카오 client 설정이 잘못된 경우"},
    },
)
async def kakao_login(body: KakaoLoginRequest, db: Session = Depends(get_db)):
    try:
        return await login_with_kakao(db, body.code)
    except KakaoOAuthError as exc:
        # 인가 코드 만료/재사용 등 클라이언트가 고칠 수 있는 문제이므로 400으로 내려
        # 원인을 그대로 보여준다 (500 "Internal Server Error"로 뭉개지 않는다).
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
