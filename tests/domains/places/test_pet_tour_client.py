from typing import Any

import httpx
import pytest

from app.domains.places.external.pet_tour_client import PetTourApiError, PetTourClient


def _envelope(items: Any, result_code: str = "0000") -> dict:
    return {
        "header": {"resultCode": result_code, "resultMsg": "OK"},
        "body": {"numOfRows": 1, "pageNo": 1, "totalCount": 1, "items": {"item": items}},
    }


def _make_client(handler) -> PetTourClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(
        transport=transport, base_url="https://apis.data.go.kr/B551011/KorPetTourService2"
    )
    return PetTourClient(api_key="test-key", http_client=http_client)


async def test_location_based_list_parses_list_items():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "contentid": "1",
                        "contenttypeid": "39",
                        "title": "테스트 식당",
                        "addr1": "서울",
                        "mapx": "127.0",
                        "mapy": "37.5",
                        "firstimage": "",
                    }
                ]
            ),
        )

    client = _make_client(handler)
    try:
        items = await client.location_based_list(
            map_x=127.0, map_y=37.5, radius=2000, content_type_id="39", num_of_rows=1
        )
    finally:
        await client.aclose()

    assert len(items) == 1
    assert items[0].content_id == "1"
    assert items[0].title == "테스트 식당"
    assert items[0].first_image is None


async def test_location_based_list_handles_single_item_as_dict():
    """totalCount가 1일 때 items.item이 배열이 아니라 단일 객체로 오는 케이스."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_envelope(
                {
                    "contentid": "1",
                    "contenttypeid": "39",
                    "title": "단일 결과",
                    "addr1": "서울",
                    "mapx": "127.0",
                    "mapy": "37.5",
                }
            ),
        )

    client = _make_client(handler)
    try:
        items = await client.location_based_list(
            map_x=127.0, map_y=37.5, radius=2000, content_type_id="39", num_of_rows=1
        )
    finally:
        await client.aclose()

    assert len(items) == 1
    assert items[0].title == "단일 결과"


async def test_location_based_list_handles_empty_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "header": {"resultCode": "0000", "resultMsg": "OK"},
                "body": {"numOfRows": 0, "pageNo": 1, "totalCount": 0, "items": ""},
            },
        )

    client = _make_client(handler)
    try:
        items = await client.location_based_list(
            map_x=127.0, map_y=37.5, radius=2000, content_type_id="39", num_of_rows=1
        )
    finally:
        await client.aclose()

    assert items == []


async def test_get_raises_on_flat_error_response_without_header_body():
    """일부 파라미터 오류는 header/body 없이 최상위에 곧바로 resultCode/resultMsg로 온다."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "responseTime": "2026-08-04T20:54:20.584",
                "resultCode": "10",
                "resultMsg": "INVALID_REQUEST_PARAMETER_ERROR(overviewYN)",
            },
        )

    client = _make_client(handler)
    try:
        with pytest.raises(PetTourApiError) as exc_info:
            await client.detail_common(content_id="1")
    finally:
        await client.aclose()

    assert exc_info.value.result_code == "10"
    assert "overviewYN" in exc_info.value.result_msg


async def test_location_based_list_raises_on_error_result_code():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "header": {"resultCode": "99", "resultMsg": "SERVICE ERROR"},
                "body": {},
            },
        )

    client = _make_client(handler)
    try:
        with pytest.raises(PetTourApiError):
            await client.location_based_list(
                map_x=127.0, map_y=37.5, radius=2000, content_type_id="39", num_of_rows=1
            )
    finally:
        await client.aclose()


async def test_detail_intro_picks_field_by_content_type():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_envelope(
                {
                    "opentimefood": "11:00-21:00",
                    "restdatefood": "매주 월요일",
                }
            ),
        )

    client = _make_client(handler)
    try:
        intro = await client.detail_intro(content_id="1", content_type_id="39")
    finally:
        await client.aclose()

    assert intro.open_time == "11:00-21:00"
    assert intro.rest_day == "매주 월요일"


async def test_detail_pet_tour_returns_none_when_no_items():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "header": {"resultCode": "0000", "resultMsg": "OK"},
                "body": {"numOfRows": 0, "pageNo": 1, "totalCount": 0, "items": ""},
            },
        )

    client = _make_client(handler)
    try:
        result = await client.detail_pet_tour(content_id="1")
    finally:
        await client.aclose()

    assert result is None
