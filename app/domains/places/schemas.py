from pydantic import BaseModel


class PlaceCandidate(BaseModel):
    """코스 생성 파이프라인의 장소 후보. 다음 단계(T-map 이동시간 + LLM 순서 결정)로 전달된다."""

    content_id: str
    title: str
    category: str  # UI 카테고리(식당/산책/카페/액티비티)로 정규화
    address: str
    lat: float
    lng: float
    dist: float  # 조회 좌표로부터의 거리(m) — 거리 가중 랜덤 선별에 사용
    image_url: str | None = None
    overview: str | None = None
    open_time: str | None = None
    rest_day: str | None = None
    pet_accompany_type: str | None = None
    pet_need_materials: str | None = None
    pet_caution: str | None = None
    pet_facilities: str | None = None
