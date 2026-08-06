from app.domains.places.constants import PlaceSearchCategory
from app.domains.places.external.pet_tour_client import (
    DetailCommon,
    DetailIntro,
    DetailPetTour,
    LocationBasedItem,
)
from app.domains.places.service import get_buffer_size, select_places_for_category


class _FakeClient:
    """PetTourClient를 의존성 주입으로 대체하는 테스트용 더미 클라이언트."""

    def __init__(self, items_by_radius: dict[int, list[LocationBasedItem]]):
        self.items_by_radius = items_by_radius
        self.radii_called: list[int] = []
        self.closed = False

    async def location_based_list(
        self, *, map_x, map_y, radius, content_type_id, num_of_rows, cat1=None, cat2=None, cat3=None, arrange="E"
    ):
        self.radii_called.append(radius)
        return self.items_by_radius.get(radius, [])

    async def detail_intro(self, *, content_id, content_type_id):
        return DetailIntro(open_time="09:00-18:00", rest_day=None)

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
            overview="설명", homepage=None, tel=None, addr1=None, addr2=None, mapx=None, mapy=None
        )

    async def aclose(self):
        self.closed = True


def _item(content_id: str, dist: float = 100.0) -> LocationBasedItem:
    return LocationBasedItem(
        content_id=content_id,
        content_type_id="12",
        title=f"장소{content_id}",
        addr1="서울",
        mapx="127.1",
        mapy="37.5",
        dist=dist,
        first_image=None,
    )


def test_get_buffer_size():
    assert get_buffer_size(1) == 7
    assert get_buffer_size(2) == 11
    assert get_buffer_size(3) == 15
    assert get_buffer_size(10) == 15  # 상한
    assert get_buffer_size(0) == 6  # 하한


async def test_returns_k_candidates_when_enough_found():
    client = _FakeClient({2000: [_item("1"), _item("2"), _item("3")]})

    result = await select_places_for_category(
        PlaceSearchCategory.WALK, 2, 37.5, 127.1, client=client
    )

    assert len(result) == 2
    assert client.radii_called == [2000]
    # 외부에서 주입한 client는 서비스가 닫지 않는다
    assert client.closed is False


async def test_expands_radius_when_insufficient():
    client = _FakeClient(
        {
            2000: [_item("1")],
            4000: [_item("1"), _item("2"), _item("3")],
        }
    )

    result = await select_places_for_category(
        PlaceSearchCategory.WALK, 3, 37.5, 127.1, client=client
    )

    assert client.radii_called == [2000, 4000]
    assert len(result) == 3


async def test_radius_doubles_each_retry():
    client = _FakeClient({2000: [], 4000: [], 8000: []})

    result = await select_places_for_category(
        PlaceSearchCategory.WALK, 3, 37.5, 127.1, client=client, max_retries=2
    )

    assert client.radii_called == [2000, 4000, 8000]
    assert result == []


async def test_returns_fewer_than_k_after_max_retries_exhausted():
    client = _FakeClient({2000: [_item("1")], 4000: [_item("1")], 8000: [_item("1")]})

    result = await select_places_for_category(
        PlaceSearchCategory.WALK, 3, 37.5, 127.1, client=client, max_retries=2
    )

    assert client.radii_called == [2000, 4000, 8000]
    assert len(result) == 1
