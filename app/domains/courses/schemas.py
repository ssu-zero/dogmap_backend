import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

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
    walk_date: datetime = Field(description="산책을 시작할 예정 일시")

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
                "walk_date": "2026-09-20T10:00:00+09:00",
            }
        }
    )


class CourseUpdate(BaseModel):
    """코스 메타데이터 수정(소유자만 가능). 보낸 필드만 수정되는 partial update —
    수정하지 않을 필드는 아예 생략하면 된다."""

    title: str | None = Field(default=None, description="코스 제목", examples=["우리 동네 산책 코스"])
    walk_date: datetime | None = Field(default=None, description="산책을 시작할 예정 일시")


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
    # Course.walk_date에 이전 스팟들의 travel_minutes/stay_minutes를 누적해서 계산한 도착
    # 예정 시각. DB에 저장하지 않고 응답 생성 시점에 매번 계산한다(courses/router.py 참고).
    visit_time: datetime | None = None


class CoursePlacesReplaceRequest(BaseModel):
    """코스 생성(POST) 후 프론트에서 스팟을 삭제/재구성해 코스를 확정할 때 호출한다
    (소유자만 가능). places는 코스 생성/조회 응답과 동일한 형식(CoursePlaceRead)을 그대로
    받는다 — 프론트가 이미 갖고 있는 응답 객체를 그대로 재사용하면 된다. 서버는 거리/시간을
    다시 계산하지 않고 넘어온 값을 그대로 신뢰해서 저장하며, 이 확정과 함께 산책 기록
    (Log)도 새로 만든다."""

    places: list[CoursePlaceRead]
    path: list[tuple[float, float]]
    ended_at: datetime | None = Field(
        default=None, description="산책 종료 예정 시각(최종 스팟의 종료 시간). 새로 만들 산책 기록의 ended_at으로 쓰인다"
    )


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_id: int
    title: str
    start_lat: float
    start_lng: float
    walk_date: datetime | None
    total_distance_meters: float
    total_duration_minutes: float
    path: list[tuple[float, float]]
    places: list[CoursePlaceRead]
    is_owner: bool
    is_shared: bool
    like_count: int
    is_liked: bool
    save_count: int
    is_saved: bool
    # 코스 생성 파이프라인 소요시간(ms). 생성 응답에서만 채워지고, 상세조회/공유
    # 응답에서는 그 시점에 다시 생성한 게 아니므로 None.
    generation_duration_ms: int | None = None


class CourseSummary(BaseModel):
    """코스 목록(주변 코스 조회, 저장한 코스 조회) 카드용 요약. CoursePlace에 저장된 값을
    합산해서 총 거리/시간을 만든다 — 목록 카드에는 폴리라인이 필요 없으므로 path는
    포함하지 않는다(상세조회 API인 CourseRead에서 Course.path를 반환한다)."""

    course_id: int
    title: str
    start_lat: float
    start_lng: float
    # 조회 좌표 기준 거리. 좌표 기준 조회(주변 코스)가 아닌 목록(저장한 코스 등)에서는
    # 기준 좌표 자체가 없으므로 None.
    distance_meters: int | None = None
    total_distance_meters: int
    total_duration_minutes: int
    place_count: int
    thumbnail_image_url: str | None
    is_owner: bool
    like_count: int
    is_liked: bool
    save_count: int
    is_saved: bool
