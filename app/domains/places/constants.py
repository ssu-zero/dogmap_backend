import enum


class PlaceSearchCategory(str, enum.Enum):
    """코스 생성 시 사용자가 고를 수 있는 UI 카테고리."""

    RESTAURANT = "식당"
    CAFE = "카페"
    WALK = "산책"
    ACTIVITY = "액티비티"


# KorPetTourService2 contentTypeId
CONTENT_TYPE_ID_TOUR_SPOT = "12"  # 관광지
CONTENT_TYPE_ID_CULTURE = "14"  # 문화시설
CONTENT_TYPE_ID_LEPORTS = "28"  # 레포츠
CONTENT_TYPE_ID_FOOD = "39"  # 음식점

# categoryCode2 실제 호출 결과로 확정한 값 (scripts/discover_pet_tour_categories.py 실행 결과).
CATEGORY_SEARCH_PARAMS: dict[PlaceSearchCategory, dict[str, str | None]] = {
    PlaceSearchCategory.RESTAURANT: {
        # cat1=A05(음식) cat2=A0502(음식점)까지만 지정 — 카페(A05020900)도 포함해서 조회된다.
        # 카페와 겹치는 후보는 파이프라인의 content_id dedup에서 정리됨.
        "content_type_id": CONTENT_TYPE_ID_FOOD,
        "cat1": "A05",
        "cat2": "A0502",
    },
    PlaceSearchCategory.CAFE: {
        "content_type_id": CONTENT_TYPE_ID_FOOD,
        "cat1": "A05",
        "cat2": "A0502",
        "cat3": "A05020900",  # 카페/전통찻집
    },
    PlaceSearchCategory.WALK: {
        "content_type_id": CONTENT_TYPE_ID_TOUR_SPOT,
    },
    PlaceSearchCategory.ACTIVITY: {
        "content_type_id": CONTENT_TYPE_ID_LEPORTS,
    },
}

# detailIntro2 응답에서 opentime/restdate 필드명은 contentTypeId마다 다르다.
# 아래 매핑에 없는 contentTypeId는 기본값(관광지 기준 필드명)을 사용한다.
_DEFAULT_OPEN_TIME_FIELD = "usetime"
_OPEN_TIME_FIELD_BY_CONTENT_TYPE: dict[str, str] = {
    CONTENT_TYPE_ID_FOOD: "opentimefood",
    CONTENT_TYPE_ID_CULTURE: "usetimeculture",
    CONTENT_TYPE_ID_LEPORTS: "usetimeleports",
}

_DEFAULT_REST_DATE_FIELD = "restdate"
_REST_DATE_FIELD_BY_CONTENT_TYPE: dict[str, str] = {
    CONTENT_TYPE_ID_FOOD: "restdatefood",
    CONTENT_TYPE_ID_CULTURE: "restdateculture",
    CONTENT_TYPE_ID_LEPORTS: "restdateleports",
}

# chkpet* 필드는 의도적으로 다루지 않는다: 관광지/문화시설/레포츠/쇼핑/음식점 x 6개 지역,
# 총 62건을 실제 호출로 조사한 결과 단 한 건도 값이 채워져 있지 않았다 (반면 같은 방식의
# chkbabycarriage/chkcreditcard류 필드는 절반 이상 채워짐 — 파싱 문제가 아니라 이 API에서
# 사실상 쓰이지 않는 필드로 확인됨). 반려동물 동반 가능 여부는 detailPetTour2만 사용한다.


def get_open_time_field(content_type_id: str) -> str:
    return _OPEN_TIME_FIELD_BY_CONTENT_TYPE.get(content_type_id, _DEFAULT_OPEN_TIME_FIELD)


def get_rest_date_field(content_type_id: str) -> str:
    return _REST_DATE_FIELD_BY_CONTENT_TYPE.get(content_type_id, _DEFAULT_REST_DATE_FIELD)
