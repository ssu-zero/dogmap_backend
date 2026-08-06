import asyncio
import json
import logging
import math
import random

from app.common.exceptions import ExternalApiError
from app.domains.places.constants import CATEGORY_SEARCH_PARAMS, PlaceSearchCategory
from app.domains.places.external.llm_client import LLMApiError, LLMClient
from app.domains.places.external.pet_tour_client import (
    DetailPetTour,
    LocationBasedItem,
    PetTourApiError,
    PetTourClient,
)
from app.domains.places.external.tmap_client import TmapApiError, TmapClient
from app.domains.places.schemas import PlaceCandidate, WalkingCourseLeg, WalkingCourseResult

logger = logging.getLogger(__name__)

# --- 장소 후보 조회 & 선별 파이프라인 (코스 생성) ---
#
# places 도메인에는 사용자가 직접 쓰는 CRUD가 없다. 사용자는 "코스 생성" 버튼만 누르고,
# 그 요청을 받아 아래 순서로 장소를 확정한다.
#   1~3. 카테고리별로 공공데이터 API에서 위치 기반 후보를 조회하고 상세조회 → 반려동물 동반
#        가능 필터를 거친다 (extract_place_candidates_for_category).
#   4. 필터링을 통과한 후보 풀 전체를 LLM에 넘겨, 사용자가 원하는 산책 시간(의 약 70%)과
#      카테고리별 목표 개수에 맞는 최종 장소 조합을 고르게 한다 (finalize_places_with_ai).
#   5. 확정된 장소들을 방문 순서대로 T맵 보행자 경로 API에 넘겨 실제 도보 코스(구간별
#      거리/시간, 전체 폴리라인)를 만든다 (build_walking_course). 지도에 그리는 건 프론트
#      몫이라 여기서는 좌표 폴리라인만 반환한다.
# create_walking_course가 1~5단계를 전부 묶는 최상위 진입점이다.

_DEFAULT_RADIUS_M = 2000
_MAX_RETRIES = 2
_DETAIL_CONCURRENCY = 10
_FAILURE_RATE_THRESHOLD = 0.5

# 장소 최종 확정(4단계)에 쓰는 추정치. 실제 이동 순서/정밀 이동시간은 이후 카카오 도보
# 경유지 계산 단계에서 다시 계산되므로, 여기서는 대략적인 시간 배분 판단에만 쓴다.
_WALK_SPEED_M_PER_MIN = 67.0  # 시속 4km 도보 기준
_ROAD_DETOUR_FACTOR = 1.3  # 직선거리 대비 실제 도로 보정 계수
_DEFAULT_STAY_MINUTES = 15  # 체류시간 정보가 없을 때 쓰는 기본값
_TARGET_TIME_RATIO = 0.7  # 최종 조합의 예상 소요시간이 맞춰야 할 목표 시간 대비 비율


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


def select_random_sample(candidates: list[PlaceCandidate], k: int) -> list[PlaceCandidate]:
    """균등 랜덤으로 k개를 뽑는다.

    거리 기반 가중치를 두지 않는 이유: 최종 확정은 finalize_places_with_ai(LLM)가
    시간 예산/카테고리 구성을 보고 판단하므로, 이 단계에서 거리로 미리 편향시킬 필요가 없다.
    코스를 생성할 때마다 매번 같은 후보만 나오는 것만 막으면 충분하다.
    """
    if len(candidates) <= k:
        return candidates
    return random.sample(candidates, k)


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


async def extract_place_candidates_for_category(
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
    """카테고리 하나에 대해 반려동물 동반 가능 장소 후보 풀을 추출한다 (1~3단계).

    k는 최종 선택 개수가 아니라 버퍼 크기(get_buffer_size) 산정용 기준값이다 — 최종
    선택은 이 풀 전체를 넘겨받는 finalize_places_with_ai(4단계)가 담당한다.
    필터링 통과 후보가 k개 미만이면 radius를 두 배씩 늘려 max_retries회 재시도하고,
    그래도 부족하면 있는 만큼만 반환한다.

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

        return filtered
    finally:
        if owns_client:
            await client.aclose()


def _haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 간 직선거리(m)."""
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _estimate_travel_minutes(dist_m: float) -> float:
    return (dist_m * _ROAD_DETOUR_FACTOR) / _WALK_SPEED_M_PER_MIN


class PlaceFinalizationError(ExternalApiError):
    """LLM이 유효한 최종 장소 목록을 반환하지 못했을 때."""


def _build_finalize_prompts(
    candidates: list[PlaceCandidate],
    start_lat: float,
    start_lng: float,
    target_duration_minutes: int,
    category_targets: dict[str, int],
) -> tuple[str, str]:
    candidates_payload = []
    for c in candidates:
        dist_from_start = _haversine_distance_m(start_lat, start_lng, c.lat, c.lng)
        candidates_payload.append(
            {
                "content_id": c.content_id,
                "title": c.title,
                "category": c.category,
                "stay_minutes_estimate": _DEFAULT_STAY_MINUTES,
                "distance_from_start_m": round(dist_from_start),
                "estimated_travel_minutes_from_start": round(
                    _estimate_travel_minutes(dist_from_start), 1
                ),
            }
        )

    system_prompt = (
        "너는 반려견 산책 코스를 짜는 어시스턴트다. category_targets는 사용자가 카테고리별로 "
        "정확히 몇 곳을 원하는지 지정한 값이다 — 이 개수를 맞추는 것을 최우선 기준으로 삼는다. "
        "해당 카테고리의 candidates가 목표 개수보다 적으면 있는 만큼만 선택한다. "
        "그렇게 고른 조합의 예상 소요시간(이동시간 추정치 + 체류시간 합)이 "
        "target_duration_minutes의 target_time_ratio(약 "
        f"{int(_TARGET_TIME_RATIO * 100)}%) 근처가 되도록 각 카테고리 안에서 후보를 고른다. "
        "각 후보의 거리/이동시간은 출발점 기준 직선거리 추정치이며, 실제 도보 경로는 "
        "이후 별도 단계에서 정밀 계산되므로 여기서는 대략적인 시간 배분 판단에만 쓴다. "
        '다른 설명 없이 반드시 JSON으로만 답한다: {"selected_content_ids": ["...", ...]}'
    )
    user_prompt = json.dumps(
        {
            "target_duration_minutes": target_duration_minutes,
            "target_time_ratio": _TARGET_TIME_RATIO,
            "category_targets": category_targets,
            "candidates": candidates_payload,
        },
        ensure_ascii=False,
    )
    return system_prompt, user_prompt


async def finalize_places_with_ai(
    candidates: list[PlaceCandidate],
    *,
    start_lat: float,
    start_lng: float,
    target_duration_minutes: int,
    category_targets: dict[PlaceSearchCategory, int],
    client: LLMClient | None = None,
) -> list[PlaceCandidate]:
    """AI가 후보 풀에서 카테고리별 목표 개수와 산책 시간 예산에 맞는 최종 장소를 확정한다 (4단계)."""
    if not candidates:
        raise PlaceFinalizationError("최종 확정할 장소 후보가 없습니다.")

    owns_client = client is None
    client = client or LLMClient()

    try:
        system_prompt, user_prompt = _build_finalize_prompts(
            candidates,
            start_lat,
            start_lng,
            target_duration_minutes,
            {category.value: k for category, k in category_targets.items()},
        )
        try:
            result = await client.chat_json(system_prompt=system_prompt, user_prompt=user_prompt)
        except LLMApiError as exc:
            raise PlaceFinalizationError(f"LLM 호출 실패: {exc}") from exc

        selected_ids = result.get("selected_content_ids")
        if not isinstance(selected_ids, list) or not selected_ids:
            raise PlaceFinalizationError(f"LLM이 유효하지 않은 응답을 반환했습니다: {result}")

        by_id = {c.content_id: c for c in candidates}
        selected = [by_id[cid] for cid in selected_ids if cid in by_id]
        if not selected:
            raise PlaceFinalizationError("LLM이 선택한 content_id가 후보 목록과 일치하지 않습니다.")

        return selected
    finally:
        if owns_client:
            await client.aclose()


async def select_places_for_course(
    category_targets: dict[PlaceSearchCategory, int],
    lat: float,
    lng: float,
    target_duration_minutes: int,
    *,
    pet_tour_client: PetTourClient | None = None,
    llm_client: LLMClient | None = None,
) -> list[PlaceCandidate]:
    """카테고리별 후보 추출(1~3단계) + LLM 최종 확정(4단계)을 묶어 실행한다.

    category_targets: {카테고리: 사용자가 원하는 목표 개수}. 예) {WALK: 1, RESTAURANT: 2, CAFE: 1}
    추출 단계에서는 버퍼 크기(get_buffer_size) 산정에 쓰이고, 확정 단계에서는 LLM이 각
    카테고리에서 정확히 이 개수만큼 고르도록 하는 목표값으로 쓰인다 (후보가 부족하면 있는
    만큼만 선택됨).
    """
    owns_client = pet_tour_client is None
    pet_tour_client = pet_tour_client or PetTourClient()

    try:
        pools = await asyncio.gather(
            *(
                extract_place_candidates_for_category(
                    category, k, lat, lng, client=pet_tour_client
                )
                for category, k in category_targets.items()
            )
        )
    finally:
        if owns_client:
            await pet_tour_client.aclose()

    # 카테고리 매핑이 겹칠 수 있어(예: 식당/카페 모두 contentTypeId=39) content_id 기준 중복 제거
    merged: dict[str, PlaceCandidate] = {}
    for pool in pools:
        for candidate in pool:
            merged.setdefault(candidate.content_id, candidate)

    return await finalize_places_with_ai(
        list(merged.values()),
        start_lat=lat,
        start_lng=lng,
        target_duration_minutes=target_duration_minutes,
        category_targets=category_targets,
        client=llm_client,
    )


async def build_walking_course(
    stops: list[PlaceCandidate],
    start_lat: float,
    start_lng: float,
    *,
    client: TmapClient | None = None,
) -> WalkingCourseResult:
    """확정된 장소들을 방문 순서대로 묶어 T맵 보행자 경로로 실제 도보 코스를 만든다 (5단계).

    stops의 순서를 그대로 방문 순서로 쓴다 (finalize_places_with_ai가 반환한 순서).
    T맵 보행자 API가 passList로 다중 경유지를 한 번의 호출에 지원하는 것을 실제 키로
    검증했으므로(tmap_client.py 상단 참고), 구간마다 나눠 부르지 않고 한 번만 호출해서
    전체 경로를 계산하고, 응답의 SP/PPn/EP 마커로 구간별 거리·시간을 분리한다.
    """
    if not stops:
        raise TmapApiError("경유지가 없어 도보 코스를 만들 수 없습니다.")

    owns_client = client is None
    client = client or TmapClient()

    leg_titles = ["출발", *(s.title for s in stops)]

    try:
        route = await client.pedestrian_route(
            start_lat=start_lat,
            start_lng=start_lng,
            end_lat=stops[-1].lat,
            end_lng=stops[-1].lng,
            waypoints=[(s.lat, s.lng) for s in stops[:-1]],
            start_name="출발",
            end_name=stops[-1].title,
        )
    finally:
        if owns_client:
            await client.aclose()

    if len(route.segments) != len(leg_titles) - 1:
        raise TmapApiError(
            f"T맵 응답 구간 수({len(route.segments)})가 경유지 수({len(leg_titles) - 1})와 "
            "다릅니다 — 경유지가 통과되지 않고 생략됐을 수 있습니다."
        )

    legs = [
        WalkingCourseLeg(
            from_title=leg_titles[i],
            to_title=leg_titles[i + 1],
            distance_meters=segment.distance_meters,
            duration_minutes=segment.duration_minutes,
        )
        for i, segment in enumerate(route.segments)
    ]

    return WalkingCourseResult(
        stops=stops,
        legs=legs,
        total_distance_meters=route.distance_meters,
        total_duration_minutes=route.duration_minutes,
        path=route.path,
    )


async def create_walking_course(
    category_targets: dict[PlaceSearchCategory, int],
    lat: float,
    lng: float,
    target_duration_minutes: int,
    *,
    pet_tour_client: PetTourClient | None = None,
    llm_client: LLMClient | None = None,
    tmap_client: TmapClient | None = None,
) -> WalkingCourseResult:
    """1~4단계(장소 후보 조회·AI 확정)에 이어 5단계(T맵 보행자 경로로 실제 코스 생성)까지
    한 번에 실행하는 최상위 진입점."""
    places = await select_places_for_course(
        category_targets,
        lat,
        lng,
        target_duration_minutes,
        pet_tour_client=pet_tour_client,
        llm_client=llm_client,
    )
    return await build_walking_course(places, lat, lng, client=tmap_client)
