import pytest

from app.core.config import settings
from app.domains.auth import service
from app.domains.auth.external.kakao_client import KakaoUserInfo
from app.domains.auth.service import KakaoRedirectUriError, resolve_kakao_redirect_uri


def test_resolve_kakao_redirect_uri_accepts_configured_client_uri(monkeypatch):
    monkeypatch.setattr(
        settings, "KAKAO_REDIRECT_URI", "https://dogmap.store/auth/kakao/callback"
    )
    monkeypatch.setattr(
        settings,
        "KAKAO_ALLOWED_REDIRECT_URIS",
        "https://preview.dogmap.store/auth/kakao/callback",
    )

    assert (
        resolve_kakao_redirect_uri("https://preview.dogmap.store/auth/kakao/callback")
        == "https://preview.dogmap.store/auth/kakao/callback"
    )


def test_resolve_kakao_redirect_uri_rejects_unregistered_uri(monkeypatch):
    monkeypatch.setattr(
        settings, "KAKAO_REDIRECT_URI", "https://dogmap.store/auth/kakao/callback"
    )
    monkeypatch.setattr(settings, "KAKAO_ALLOWED_REDIRECT_URIS", "")

    with pytest.raises(KakaoRedirectUriError):
        resolve_kakao_redirect_uri("https://attacker.example/auth/kakao/callback")


@pytest.mark.asyncio
async def test_login_uses_the_client_redirect_uri_for_token_exchange(monkeypatch):
    captured: dict[str, str] = {}

    class FakeKakaoOAuthClient:
        def __init__(self, *, redirect_uri: str):
            captured["redirect_uri"] = redirect_uri

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return None

        async def get_access_token(self, code: str) -> str:
            assert code == "kakao-code"
            return "kakao-access-token"

        async def get_user_info(self, access_token: str) -> KakaoUserInfo:
            assert access_token == "kakao-access-token"
            return KakaoUserInfo(kakao_id=7, nickname="보호자", profile_image_url=None)

    monkeypatch.setattr(
        settings, "KAKAO_REDIRECT_URI", "https://dogmap.store/auth/kakao/callback"
    )
    monkeypatch.setattr(settings, "KAKAO_ALLOWED_REDIRECT_URIS", "")
    monkeypatch.setattr(service, "KakaoOAuthClient", FakeKakaoOAuthClient)
    monkeypatch.setattr(service, "get_by_kakao_id", lambda *_: None)

    result = await service.login_with_kakao(
        db=object(),
        code="kakao-code",
        redirect_uri="https://dogmap.store/auth/kakao/callback",
    )

    assert captured["redirect_uri"] == "https://dogmap.store/auth/kakao/callback"
    assert result.status.value == "SIGNUP_REQUIRED"
