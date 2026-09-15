from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.common.exceptions import ExternalApiError
from app.core.database import get_db
from app.core.security import get_current_dog_id_optional
from app.domains.likes.repository import count_by_place_ids, liked_place_ids
from app.domains.places.constants import PlaceSearchCategory
from app.domains.places.repository import get_or_create_places
from app.domains.places.schemas import PlaceListItem
from app.domains.places.service import list_nearby_places

router = APIRouter(prefix="/places", tags=["places"])


@router.get("", response_model=list[PlaceListItem], summary="주변 장소 목록 조회")
async def get_nearby_places(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    category: PlaceSearchCategory = Query(...),
    radius_m: int = Query(2000, ge=100, le=20000),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    dog_id: int | None = Depends(get_current_dog_id_optional),
) -> list[PlaceListItem]:
    """홈 화면의 '주변 장소' 카테고리별 목록. 공공데이터포털(KorPetTourService2)에서
    반려동물 동반 가능 장소를 조회하고, 우리 DB의 좋아요 정보만 얹어서 반환한다."""
    try:
        candidates = await list_nearby_places(category, lat, lng, radius=radius_m, limit=limit)
    except ExternalApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    places_by_content_id = get_or_create_places(db, candidates)
    db.commit()

    place_ids = [place.place_id for place in places_by_content_id.values()]
    like_counts = count_by_place_ids(db, place_ids)
    liked_ids = liked_place_ids(db, dog_id, place_ids) if dog_id is not None else set()

    items = []
    for candidate in candidates:
        place_id = places_by_content_id[candidate.content_id].place_id
        items.append(
            PlaceListItem(
                **candidate.model_dump(),
                place_id=place_id,
                like_count=like_counts.get(place_id, 0),
                is_liked=place_id in liked_ids,
            )
        )
    return items
