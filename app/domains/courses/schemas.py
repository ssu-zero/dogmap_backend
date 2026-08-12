import enum

from pydantic import BaseModel, ConfigDict

from app.domains.places.models import PlaceCategory


class CourseCategory(str, enum.Enum):
    """코스 생성 요청 API에서 쓰는 카테고리. places 도메인 내부의 PlaceSearchCategory(한글
    값)와 별개로 영문 값을 쓴다 — dict[PlaceSearchCategory, int]는 Swagger에서 키가
    "additionalProp1"로만 보이고 enum 드롭다운이 안 뜨는 문제가 있어서, category_targets를
    list[CategoryTarget]로 바꾸고 여기서 별도 enum을 쓴다. places 파이프라인 호출 직전에
    courses/service.py가 PlaceSearchCategory로 변환한다."""

    FOOD = "FOOD"
    CAFE = "CAFE"
    WALK = "WALK"
    ACTIVITY = "ACTIVITY"


class CategoryTarget(BaseModel):
    category: CourseCategory
    count: int


class CourseCreateRequest(BaseModel):
    """코스 생성 요청. category_targets는 카테고리별로 정확히 몇 곳을 원하는지 지정한 값이다."""

    start_lat: float
    start_lng: float
    target_duration_minutes: int
    category_targets: list[CategoryTarget]
    title: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_lat": 37.5665,
                "start_lng": 126.9780,
                "target_duration_minutes": 60,
                "category_targets": [
                    {"category": "WALK", "count": 1},
                    {"category": "CAFE", "count": 1},
                ],
                "title": "우리 동네 산책 코스",
            }
        }
    )


class CoursePlaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    place_id: int
    name: str
    category: PlaceCategory
    image_url: str | None
    lat: float
    lng: float
    sequence: int
    stay_minutes: int | None
    travel_minutes: int | None
    travel_distance_meters: int | None


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_id: int
    title: str
    start_lat: float
    start_lng: float
    total_distance_meters: float
    total_duration_minutes: float
    path: list[tuple[float, float]]
    places: list[CoursePlaceRead]


class CourseSummary(BaseModel):
    """코스 목록(주변 코스 조회) 카드용 요약. CoursePlace에 저장된 값을 합산해서
    총 거리/시간을 만든다 — Course/CoursePlace에는 폴리라인이 저장돼 있지 않으므로
    path는 포함하지 않는다 (상세 조회는 별도 API 몫)."""

    course_id: int
    title: str
    start_lat: float
    start_lng: float
    distance_meters: int  # 조회 좌표 기준 거리
    total_distance_meters: int
    total_duration_minutes: int
    place_count: int
    thumbnail_image_url: str | None
