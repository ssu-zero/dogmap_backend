import asyncio
import logging
import random

from app.common.exceptions import ExternalApiError
from app.domains.places.constants import CATEGORY_SEARCH_PARAMS, PlaceSearchCategory
from app.domains.places.external.pet_tour_client import (
    DetailPetTour,
    LocationBasedItem,
    PetTourApiError,
    PetTourClient,
)
from app.domains.places.schemas import PlaceCandidate

logger = logging.getLogger(__name__)

# --- 장소 후보 조회 & 선별 파이프라인 (코스 생성 1~4단계) ---
#
# places 도메인에는 사용자가 직접 쓰는 CRUD가 없다. 사용자는 "코스 생성" 버튼만 누르고,
# 그 요청을 받아 공공데이터 API로 위치 기반 장소를 찾아 추리는 것이 이 파이프라인의 역할이다.
# 5단계(T-map 이동시간 계산)와 6단계(LLM 방문 순서 결정)는 이 파이프라인 밖,
# courses 도메인의 별도 이슈에서 이어서 구현한다.

_DEFAULT_RADIUS_M = 2000
_MAX_RETRIES = 2
_DETAIL_CONCURRENCY = 10
_FAILURE_RATE_THRESHOLD = 0.5


class PlaceCandidateServiceUnavailable(ExternalApiError):
    """공공데이터 API 실패율이 너무 높아 코스 후보를 만들 수 없을 때."""


def _is_valid_coordinate(value: str | None) -> bool:
    if not value:
        return False
    try:
        return float(value) != 0.0
    except ValueError:
        return False


def _is_pet_friendly(pet_tour: DetailPetTour | None, lat: str | None, lng: str | None) -> bool:
    # chkpet* 필드는 쓰지 않는다 (app/domains/places/constants.py 상단 설명 참고) —
    # detailPetTour2 존재 + acmpyPsblCpam(동반 가능 반려동물) 값 유무만으로 판단한다.
    if pet_tour is None or not pet_tour.acmpy_possible_pet:
        return False
    if not _is_valid_coordinate(lat) or not _is_valid_coordinate(lng):
        return False
    return True


def get_buffer_size(k: int) -> int:
    """필터링 전 조회할 후보 수(N). 가중 랜덤이 의미 있으려면 k보다 충분히 커야 한다.

    k=1 -> 7, k=2 -> 11, k=3 -> 15(상한) 수준. 상한 15는 공공데이터 API 호출 부담을
    고려한 값 — 통과율을 보며 조정 가능.
    """
    return min(max(k * 4 + 3, 6), 15)


def select_top_k_weighted_random(candidates: list[PlaceCandidate], k: int) -> list[PlaceCandidate]:
    """거리 역수를 가중치로 하는 비복원 가중 랜덤 샘플링으로 k개를 뽑는다.

    가까운 후보일수록 뽑힐 확률이 높지만 결정론적이지는 않다 — 코스를 생성할 때마다
    거리순 top-k만 반복해서 나오는 것을 막기 위함. candidates는 이미 반려동물 동반
    가능 필터를 통과한 상태로 전달된다고 가정한다.
    """
    if len(candidates) <= k:
        return candidates

    pool = list(candidates)
    # +1은 dist=0일 때 0으로 나누기 방지용.
    weights = [1 / (c.dist + 1) for c in pool]
    selected: list[PlaceCandidate] = []

    for _ in range(k):
        idx = random.choices(range(len(pool)), weights=weights, k=1)[0]
        selected.append(pool.pop(idx))
        weights.pop(idx)

    return selected


async def _fetch_and_filter(
    client: PetTourClient,
    category: PlaceSearchCategory,
    lat: float,
    lng: float,
    radius: int,
    n: int,
) -> tuple[list[PlaceCandidate], int, int]:
    """radius 한 번 기준으로 1~3단계(조회 → 상세조회 → 필터링) 실행.

    (필터링 통과 후보, 상세조회 성공 수, 실패 수)를 반환한다.
    """
    params = CATEGORY_SEARCH_PARAMS[category]
    try:
        # mapX=경도(lng), mapY=위도(lat)
        items = await client.location_based_list(
            map_x=lng, map_y=lat, radius=radius, num_of_rows=n, **params
        )
    except PetTourApiError:
        logger.warning("locationBasedList2 실패: category=%s", category, exc_info=True)
        return [], 0, 0

    semaphore = asyncio.Semaphore(_DETAIL_CONCURRENCY)

    async def _fetch_detail(item: LocationBasedItem):
        async with semaphore:
            try:
                intro, pet_tour, common = await asyncio.gather(
                    client.detail_intro(content_id=item.content_id, content_type_id=item.content_type_id),
                    client.detail_pet_tour(content_id=item.content_id),
                    client.detail_common(content_id=item.content_id),
                )
                return item, intro, pet_tour, common.overview, True
            except PetTourApiError:
                logger.warning("상세조회 실패: content_id=%s", item.content_id, exc_info=True)
                return item, None, None, None, False

    results = await asyncio.gather(*(_fetch_detail(item) for item in items))

    success = sum(1 for *_rest, ok in results if ok)
    failed = len(results) - success

    filtered: list[PlaceCandidate] = []
    for item, intro, pet_tour, overview, ok in results:
        if not ok or not _is_pet_friendly(pet_tour, item.mapy, item.mapx):
            continue
        filtered.append(
            PlaceCandidate(
                content_id=item.content_id,
                title=item.title,
                category=category.value,
                address=item.addr1,
                lat=float(item.mapy),
                lng=float(item.mapx),
                dist=item.dist,
                image_url=item.first_image,
                overview=overview,
                open_time=intro.open_time if intro else None,
                rest_day=intro.rest_day if intro else None,
                pet_accompany_type=pet_tour.acmpy_type if pet_tour else None,
                pet_need_materials=pet_tour.acmpy_need_materials if pet_tour else None,
                pet_caution=pet_tour.caution if pet_tour else None,
                pet_facilities=pet_tour.facilities if pet_tour else None,
            )
        )

    return filtered, success, failed


async def select_places_for_category(
    category: PlaceSearchCategory,
    k: int,
    lat: float,
    lng: float,
    *,
    radius: int = _DEFAULT_RADIUS_M,
    max_retries: int = _MAX_RETRIES,
    client: PetTourClient | None = None,
    exclude_ids: set[str] | None = None,
) -> list[PlaceCandidate]:
    """카테고리 하나에 대해 반려동물 동반 가능 장소를 k개 선별한다 (1~4단계).

    필터링 통과 후보가 k개 미만이면 radius를 두 배씩 늘려 max_retries회 재시도하고,
    그래도 부족하면 있는 만큼만 골라서 반환한다 — 부족 여부 판단은 호출부의 몫이다.

    exclude_ids: TODO(다시 추천 기능) — 이전에 뽑힌 content_id를 제외하는 로직은
    별도 이슈에서 구현 예정. 현재는 인자만 받고 사용하지 않는다.
    """
    del exclude_ids  # TODO: 다시 추천 기능 이슈에서 사용 예정

    owns_client = client is None
    client = client or PetTourClient()

    n = get_buffer_size(k)
    filtered: list[PlaceCandidate] = []
    total_success = 0
    total_failed = 0

    try:
        for attempt in range(max_retries + 1):
            filtered, success, failed = await _fetch_and_filter(client, category, lat, lng, radius, n)
            total_success += success
            total_failed += failed
            if len(filtered) >= k or attempt == max_retries:
                break
            radius *= 2

        total_calls = total_success + total_failed
        if total_calls > 0 and total_failed / total_calls > _FAILURE_RATE_THRESHOLD:
            raise PlaceCandidateServiceUnavailable(
                f"공공데이터 API 실패율이 너무 높습니다 ({total_failed}/{total_calls} 실패)"
            )

        return select_top_k_weighted_random(filtered, k)
    finally:
        if owns_client:
            await client.aclose()
