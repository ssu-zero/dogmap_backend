from collections import defaultdict

from sqlalchemy.orm import Session

from app.common.geo import bounding_box, haversine_distance_m
from app.domains.courses.models import Course, CoursePlace
from app.domains.courses.repository import (
    CoursePlaceEntry,
    add_course_places,
    create_course,
    get_course_places_by_course_ids,
    list_courses_within_bounding_box,
)
from app.domains.courses.schemas import CategoryTarget, CourseCategory, CourseCreateRequest, CourseSummary
from app.domains.places.constants import DEFAULT_STAY_MINUTES, PlaceSearchCategory
from app.domains.places.repository import get_or_create_places
from app.domains.places.schemas import WalkingCourseResult
from app.domains.places.service import create_walking_course

# 요청 스키마의 CourseCategory(영문, Swagger enum 노출용)를 places 파이프라인이 쓰는
# PlaceSearchCategory(한글)로 변환한다.
_PLACE_SEARCH_CATEGORY_BY_COURSE_CATEGORY: dict[CourseCategory, PlaceSearchCategory] = {
    CourseCategory.FOOD: PlaceSearchCategory.RESTAURANT,
    CourseCategory.CAFE: PlaceSearchCategory.CAFE,
    CourseCategory.WALK: PlaceSearchCategory.WALK,
    CourseCategory.ACTIVITY: PlaceSearchCategory.ACTIVITY,
}


def _default_title(request: CourseCreateRequest) -> str:
    return f"{request.target_duration_minutes}분 산책 코스"


def _to_place_search_category_targets(
    category_targets: list[CategoryTarget],
) -> dict[PlaceSearchCategory, int]:
    return {
        _PLACE_SEARCH_CATEGORY_BY_COURSE_CATEGORY[target.category]: target.count
        for target in category_targets
    }


async def create_course_with_places(
    db: Session, request: CourseCreateRequest
) -> tuple[Course, list[CoursePlace], WalkingCourseResult]:
    """코스 생성 파이프라인(places.service.create_walking_course)을 실행하고 결과를
    Course/CoursePlace로 영속화한다."""
    result = await create_walking_course(
        _to_place_search_category_targets(request.category_targets),
        request.start_lat,
        request.start_lng,
        request.target_duration_minutes,
    )

    try:
        places_by_content_id = get_or_create_places(db, result.stops)
        course = create_course(
            db,
            title=request.title or _default_title(request),
            start_lat=request.start_lat,
            start_lng=request.start_lng,
        )
        entries = [
            CoursePlaceEntry(
                place=places_by_content_id[stop.content_id],
                sequence=i + 1,
                stay_minutes=DEFAULT_STAY_MINUTES,
                travel_minutes=round(leg.duration_minutes),
                travel_distance_meters=round(leg.distance_meters),
            )
            for i, (stop, leg) in enumerate(zip(result.stops, result.legs, strict=True))
        ]
        course_places = add_course_places(db, course, entries)
    except Exception:
        db.rollback()
        raise

    db.commit()
    db.refresh(course)
    return course, course_places, result


def list_nearby_courses(
    db: Session, *, lat: float, lng: float, radius_m: int, limit: int, offset: int
) -> list[CourseSummary]:
    """반경(radius_m) 내 코스를 거리순으로 반환한다.

    Course/CoursePlace에는 총 거리/시간이 별도 저장돼 있지 않으므로, CoursePlace의
    stay_minutes/travel_minutes/travel_distance_meters를 코스별로 합산해서 만든다.
    """
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_m)
    candidates = list_courses_within_bounding_box(
        db, min_lat=min_lat, max_lat=max_lat, min_lng=min_lng, max_lng=max_lng
    )

    within_radius = [
        (course, haversine_distance_m(lat, lng, course.start_lat, course.start_lng))
        for course in candidates
    ]
    within_radius = [pair for pair in within_radius if pair[1] <= radius_m]
    within_radius.sort(key=lambda pair: pair[1])
    page = within_radius[offset : offset + limit]

    course_places = get_course_places_by_course_ids(db, [course.course_id for course, _ in page])
    places_by_course: dict[int, list[CoursePlace]] = defaultdict(list)
    for cp in course_places:
        places_by_course[cp.course_id].append(cp)

    summaries = []
    for course, distance in page:
        cps = places_by_course.get(course.course_id, [])
        summaries.append(
            CourseSummary(
                course_id=course.course_id,
                title=course.title,
                start_lat=course.start_lat,
                start_lng=course.start_lng,
                distance_meters=round(distance),
                total_distance_meters=sum(cp.travel_distance_meters or 0 for cp in cps),
                total_duration_minutes=sum(
                    (cp.stay_minutes or 0) + (cp.travel_minutes or 0) for cp in cps
                ),
                place_count=len(cps),
                thumbnail_image_url=cps[0].place.image_url if cps else None,
            )
        )
    return summaries
