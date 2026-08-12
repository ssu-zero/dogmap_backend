"""OpenAI Chat Completions 형식(OpenAI 호환 엔드포인트) 호출 클라이언트.

기본값은 Gemini의 OpenAI 호환 엔드포인트(app/core/config.py의 LLM_BASE_URL 참고)를
가리키지만, OpenAI Chat Completions와 동일한 요청/응답 스펙을 따르는 엔드포인트라면
base_url/model/api_key만 바꿔서 그대로 재사용할 수 있다 (코드가 특정 벤더에 묶여있지 않음).

places 도메인에서 "장소 후보 풀 중 사용자가 원하는 산책 시간에 맞는 최종 조합을 고르는"
용도로만 사용한다. 프롬프트 구성/응답 해석은 이 클라이언트가 아니라 service.py가 담당하고,
이 클라이언트는 순수하게 "system+user 프롬프트를 보내고 JSON 응답을 받는" HTTP 통신만 맡는다.
"""

import json
from typing import Any

import httpx

from app.common.exceptions import ExternalApiError
from app.core.config import settings

_DEFAULT_TIMEOUT = 60.0  # Gemini는 응답 전에 내부적으로 "생각"(thinking)하는 시간이 붙어서
# 가끔 30초를 넘길 때가 있다 — 실제 후보 7개짜리 프롬프트가 30초 타임아웃에 걸린 적이 있음.


class LLMApiError(ExternalApiError):
    pass


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ):
        self._api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self._model = model or settings.LLM_MODEL
        base_url = base_url or settings.LLM_BASE_URL
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def chat_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Chat Completions를 JSON 모드로 호출하고 파싱된 응답 객체를 반환한다."""
        try:
            response = await self._client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise LLMApiError(f"LLM 호출 실패: {exc}") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMApiError(f"예상치 못한 LLM 응답 형식: {payload}") from exc

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMApiError(f"LLM 응답 JSON 파싱 실패: {content}") from exc
