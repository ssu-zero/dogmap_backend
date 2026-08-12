import json

import pytest

from app.domains.places.constants import PlaceSearchCategory
from app.domains.places.external.llm_client import LLMApiError
from app.domains.places.external.pet_tour_client import DetailCommon, DetailIntro, DetailPetTour, LocationBasedItem
from app.domains.places.schemas import PlaceCandidate
from app.domains.places.service import (
    PlaceFinalizationError,
    _build_finalize_prompts,
    finalize_places_with_ai,
    select_places_for_course,
)

_CATEGORY_TARGETS = {PlaceSearchCategory.WALK: 1}


class _FakeLLMClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.closed = False

    async def chat_json(self, *, system_prompt, user_prompt):
        if self.error:
            raise self.error
        return self.response

    async def aclose(self):
        self.closed = True


def _candidate(content_id: str, category: str = "산책") -> PlaceCandidate:
    return PlaceCandidate(
        content_id=content_id,
        title=f"장소{content_id}",
        category=category,
        address="서울",
        lat=37.5,
        lng=127.1,
        dist=100.0,
    )


async def test_finalize_places_with_ai_returns_selected_candidates_in_order():
    candidates = [_candidate("1"), _candidate("2"), _candidate("3")]
    llm = _FakeLLMClient(response={"selected_content_ids": ["3", "1"]})

    result = await finalize_places_with_ai(
        candidates,
        start_lat=37.5,
        start_lng=127.1,
        target_duration_minutes=40,
        category_targets=_CATEGORY_TARGETS,
        client=llm,
    )

    assert [c.content_id for c in result] == ["3", "1"]
    # 외부에서 주입한 client는 서비스가 닫지 않는다
    assert llm.closed is False


async def test_finalize_places_with_ai_raises_when_no_candidates():
    with pytest.raises(PlaceFinalizationError):
        await finalize_places_with_ai(
            [],
            start_lat=37.5,
            start_lng=127.1,
            target_duration_minutes=40,
            category_targets=_CATEGORY_TARGETS,
            client=_FakeLLMClient(),
        )


async def test_finalize_places_with_ai_raises_on_invalid_response_shape():
    llm = _FakeLLMClient(response={"oops": "no key"})

    with pytest.raises(PlaceFinalizationError):
        await finalize_places_with_ai(
            [_candidate("1")],
            start_lat=37.5,
            start_lng=127.1,
            target_duration_minutes=40,
            category_targets=_CATEGORY_TARGETS,
            client=llm,
        )


async def test_finalize_places_with_ai_raises_when_selected_ids_dont_match_pool():
    llm = _FakeLLMClient(response={"selected_content_ids": ["does-not-exist"]})

    with pytest.raises(PlaceFinalizationError):
        await finalize_places_with_ai(
            [_candidate("1")],
            start_lat=37.5,
            start_lng=127.1,
            target_duration_minutes=40,
            category_targets=_CATEGORY_TARGETS,
            client=llm,
        )


async def test_finalize_places_with_ai_wraps_llm_api_error():
    llm = _FakeLLMClient(error=LLMApiError("boom"))

    with pytest.raises(PlaceFinalizationError):
        await finalize_places_with_ai(
            [_candidate("1")],
            start_lat=37.5,
            start_lng=127.1,
            target_duration_minutes=40,
            category_targets=_CATEGORY_TARGETS,
            client=llm,
        )


def test_build_finalize_prompts_includes_exact_category_targets():
    candidates = [_candidate("1", category="산책"), _candidate("2", category="식당")]

    _, user_prompt = _build_finalize_prompts(
        candidates,
        start_lat=37.5,
        start_lng=127.1,
        target_duration_minutes=60,
        category_targets={"산책": 1, "식당": 2},
    )

    payload = json.loads(user_prompt)
    assert payload["category_targets"] == {"산책": 1, "식당": 2}


class _FakePetTourClient:
    def __init__(self, items_by_content_type: dict[str, list[LocationBasedItem]]):
        self.items_by_content_type = items_by_content_type
        self.closed = False

    async def location_based_list(
        self, *, map_x, map_y, radius, content_type_id, num_of_rows, cat1=None, cat2=None, cat3=None, arrange="E"
    ):
        return self.items_by_content_type.get(content_type_id, [])

    async def detail_intro(self, *, content_id, content_type_id):
        return DetailIntro(open_time=None, rest_day=None)

    async def detail_pet_tour(self, *, content_id):
        return DetailPetTour(
            acmpy_type=None,
            acmpy_possible_pet="소형견",
            acmpy_need_materials=None,
            caution=None,
            facilities=None,
            etc_info=None,
        )

    async def detail_common(self, *, content_id):
        return DetailCommon(
            overview=None, homepage=None, tel=None, addr1=None, addr2=None, mapx=None, mapy=None
        )

    async def aclose(self):
        self.closed = True


async def test_select_places_for_course_merges_category_pools_and_finalizes():
    walk_item = LocationBasedItem(
        content_id="1", content_type_id="12", title="공원", addr1="서울",
        mapx="127.1", mapy="37.5", dist=50.0, first_image=None,
    )
    food_item = LocationBasedItem(
        content_id="2", content_type_id="39", title="식당", addr1="서울",
        mapx="127.2", mapy="37.6", dist=200.0, first_image=None,
    )
    pet_tour_client = _FakePetTourClient({"12": [walk_item], "39": [food_item]})
    llm_client = _FakeLLMClient(response={"selected_content_ids": ["1", "2"]})

    result = await select_places_for_course(
        {PlaceSearchCategory.WALK: 1, PlaceSearchCategory.RESTAURANT: 1},
        37.5,
        127.1,
        60,
        pet_tour_client=pet_tour_client,
        llm_client=llm_client,
    )

    assert {c.content_id for c in result} == {"1", "2"}
    # 외부에서 주입한 client는 서비스가 닫지 않는다
    assert pet_tour_client.closed is False
