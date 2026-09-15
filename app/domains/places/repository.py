from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.places.constants import PlaceSearchCategory
from app.domains.places.models import Place, PlaceCategory
from app.domains.places.schemas import PlaceCandidate

# 코스 생성 시 쓰는 UI 카테고리(PlaceSearchCategory)를 Place 도메인 카테고리로 매핑.
# WALK/ACTIVITY는 Place 쪽에 대응 카테고리가 없어 각각 PARK/ETC로 근사한다.
PLACE_CATEGORY_BY_SEARCH_CATEGORY: dict[PlaceSearchCategory, PlaceCategory] = {
    PlaceSearchCategory.RESTAURANT: PlaceCategory.RESTAURANT,
    PlaceSearchCategory.CAFE: PlaceCategory.CAFE,
    PlaceSearchCategory.WALK: PlaceCategory.PARK,
    PlaceSearchCategory.ACTIVITY: PlaceCategory.ETC,
}


def get_or_create_places(db: Session, candidates: list[PlaceCandidate]) -> dict[str, Place]:
    """content_id 기준으로 Place를 조회하고, 없는 것만 새로 만든다.

    영업시간은 저장하지 않는다 — PlaceCandidate.open_time은 "09:00~18:00" 같은 자유
    텍스트라 Place.open_time/close_time에 저장하려면 별도 파싱이 필요하다.
    """
    if not candidates:
        return {}

    content_ids = [c.content_id for c in candidates]
    existing = db.scalars(select(Place).where(Place.content_id.in_(content_ids))).all()
    by_content_id: dict[str, Place] = {p.content_id: p for p in existing}

    for candidate in candidates:
        if candidate.content_id in by_content_id:
            continue
        place = Place(
            content_id=candidate.content_id,
            name=candidate.title,
            content=candidate.overview,
            category=PLACE_CATEGORY_BY_SEARCH_CATEGORY[PlaceSearchCategory(candidate.category)],
            image_url=candidate.image_url,
            rest_day=candidate.rest_day,
            latitude=candidate.lat,
            longitude=candidate.lng,
        )
        db.add(place)
        by_content_id[candidate.content_id] = place

    db.flush()
    return by_content_id
