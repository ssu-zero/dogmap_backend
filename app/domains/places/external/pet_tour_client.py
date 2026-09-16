"""공공데이터포털 반려동물 동반여행 서비스(KorPetTourService2) 호출 클라이언트.

이 API는 서버 측 필드 선택(fields=)을 지원하지 않는다. 따라서 "필요한 응답만 쓰기"는
매 응답을 이 클라이언트 안에서 바로 좁은 dataclass로 변환해서, 원본 JSON을 이 파일 밖으로
내보내지 않는 방식으로 처리한다 (뒤 단계인 service.py는 원본 dict를 다루지 않는다).
"""

from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

import httpx

from app.common.exceptions import ExternalApiError
from app.core.config import settings
from app.domains.places.constants import get_open_time_field, get_rest_date_field

_DEFAULT_TIMEOUT = 5.0


class PetTourApiError(ExternalApiError):
    def __init__(self, endpoint: str, result_code: str | None, result_msg: str | None):
        self.endpoint = endpoint
        self.result_code = result_code
        self.result_msg = result_msg
        super().__init__(f"{endpoint} 실패 (resultCode={result_code}): {result_msg}")


@dataclass
class LocationBasedItem:
    content_id: str
    content_type_id: str
    title: str
    addr1: str
    mapx: str
    mapy: str
    dist: float  # 조회 좌표로부터의 거리(m). arrange="E"일 때 응답에 포함된다.
    first_image: str | None


@dataclass
class DetailCommon:
    overview: str | None
    homepage: str | None
    tel: str | None
    addr1: str | None
    addr2: str | None
    mapx: str | None
    mapy: str | None


@dataclass
class DetailIntro:
    open_time: str | None
    rest_day: str | None
    # chkpet* 필드는 넣지 않는다: 실제 응답 샘플 62건(관광지/문화시설/레포츠/쇼핑/음식점 x
    # 여러 지역)을 조사한 결과 단 한 건도 값이 채워져 있지 않았다. 반면 같은 방식으로 검사한
    # chkbabycarriage/chkcreditcard류 형제 필드는 절반 이상 채워져 있어, 파싱 문제가 아니라
    # 이 API(KorPetTourService2)에서 사실상 쓰이지 않는 필드로 확인됨. 반려동물 동반 가능
    # 여부는 detailPetTour2(acmpyPsblCpam)만 신뢰 가능한 신호로 사용한다.


@dataclass
class DetailPetTour:
    acmpy_type: str | None
    acmpy_possible_pet: str | None
    acmpy_need_materials: str | None
    caution: str | None
    facilities: str | None
    etc_info: str | None


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    items = body.get("items")
    if not items:
        return []
    item = items.get("item") if isinstance(items, dict) else items
    if not item:
        return []
    if isinstance(item, dict):
        return [item]
    return list(item)


class PetTourClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        mobile_app: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ):
        self._api_key = api_key if api_key is not None else settings.PET_TOUR_API_KEY
        self._base_url = base_url or settings.PET_TOUR_BASE_URL
        self._mobile_app = mobile_app or settings.PET_TOUR_MOBILE_APP
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(base_url=self._base_url, timeout=timeout)

    async def __aenter__(self) -> "PetTourClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _common_params(self) -> dict[str, str]:
        # 공공데이터포털 serviceKey는 이미 URL-인코딩된 값으로 발급되는 경우가 많다.
        # httpx는 params 딕셔너리 값을 자체적으로 한 번 더 인코딩하므로, 그대로 넘기면
        # %2B/%3D 등이 %252B/%253D로 이중 인코딩되어 인증이 403으로 실패한다.
        # unquote로 먼저 원문으로 되돌려서 httpx가 정확히 한 번만 인코딩하게 한다.
        return {
            "serviceKey": unquote(self._api_key),
            "MobileOS": "ETC",
            "MobileApp": self._mobile_app,
            "_type": "json",
        }

    async def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        query = {**self._common_params(), **{k: v for k, v in params.items() if v is not None}}
        try:
            response = await self._client.get(endpoint, params=query)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise PetTourApiError(endpoint, None, str(exc)) from exc

        # data.go.kr류 API는 종종 응답을 {"response": {...}}로 한 번 더 감싸기도 한다.
        envelope = payload.get("response", payload) if isinstance(payload, dict) else {}
        header = envelope.get("header")
        if header is None:
            # 파라미터 오류 등은 header/body 없이 최상위에 곧바로
            # {"resultCode": ..., "resultMsg": ...}로 내려오기도 한다.
            header = envelope
        result_code = header.get("resultCode")
        if result_code != "0000":
            raise PetTourApiError(endpoint, result_code, header.get("resultMsg"))

        return envelope.get("body", {})

    async def location_based_list(
        self,
        *,
        map_x: float,
        map_y: float,
        radius: int,
        content_type_id: str,
        num_of_rows: int,
        cat1: str | None = None,
        cat2: str | None = None,
        cat3: str | None = None,
        arrange: str = "E",
    ) -> list[LocationBasedItem]:
        body = await self._get(
            "/locationBasedList2",
            {
                "mapX": map_x,
                "mapY": map_y,
                "radius": radius,
                "contentTypeId": content_type_id,
                "cat1": cat1,
                "cat2": cat2,
                "cat3": cat3,
                "arrange": arrange,
                "numOfRows": num_of_rows,
                "pageNo": 1,
            },
        )
        return [
            LocationBasedItem(
                content_id=str(raw.get("contentid")),
                content_type_id=str(raw.get("contenttypeid")),
                title=raw.get("title", ""),
                addr1=raw.get("addr1", ""),
                mapx=raw.get("mapx", ""),
                mapy=raw.get("mapy", ""),
                dist=_safe_float(raw.get("dist")),
                first_image=raw.get("firstimage") or None,
            )
            for raw in _extract_items(body)
        ]

    async def detail_common(self, *, content_id: str) -> DetailCommon:
        # overviewYN 등 TourAPI4.0의 YN 파라미터는 이 API 변형에서 지원하지 않는다
        # (넘기면 INVALID_REQUEST_PARAMETER_ERROR) — contentId만 넘기면 overview가 기본 포함된다.
        body = await self._get("/detailCommon2", {"contentId": content_id})
        items = _extract_items(body)
        raw = items[0] if items else {}
        return DetailCommon(
            overview=raw.get("overview") or None,
            homepage=raw.get("homepage") or None,
            tel=raw.get("tel") or None,
            addr1=raw.get("addr1") or None,
            addr2=raw.get("addr2") or None,
            mapx=raw.get("mapx") or None,
            mapy=raw.get("mapy") or None,
        )

    async def detail_intro(self, *, content_id: str, content_type_id: str) -> DetailIntro:
        body = await self._get(
            "/detailIntro2",
            {"contentId": content_id, "contentTypeId": content_type_id},
        )
        items = _extract_items(body)
        raw = items[0] if items else {}
        return DetailIntro(
            open_time=raw.get(get_open_time_field(content_type_id)) or None,
            rest_day=raw.get(get_rest_date_field(content_type_id)) or None,
        )

    async def detail_pet_tour(self, *, content_id: str) -> DetailPetTour | None:
        body = await self._get("/detailPetTour2", {"contentId": content_id})
        items = _extract_items(body)
        if not items:
            return None
        raw = items[0]
        return DetailPetTour(
            acmpy_type=raw.get("acmpyTypeCd") or None,
            acmpy_possible_pet=raw.get("acmpyPsblCpam") or None,
            acmpy_need_materials=raw.get("acmpyNeedMtr") or None,
            caution=raw.get("relaAcdntRiskMtr") or None,
            facilities=raw.get("relaPosesFclty") or None,
            etc_info=raw.get("etcAcmpyInfo") or None,
        )

    async def category_code(
        self, *, cat1: str | None = None, cat2: str | None = None
    ) -> list[dict[str, Any]]:
        """categoryCode2 조회 (카테고리 코드 확정용 1회성 디스커버리 도구).

        원본 dict 그대로 반환 — 서비스 파이프라인에서는 쓰지 않고
        scripts/discover_pet_tour_categories.py 에서만 사용한다.
        """
        body = await self._get(
            "/categoryCode2",
            {"cat1": cat1, "cat2": cat2, "numOfRows": 100},
        )
        return _extract_items(body)
