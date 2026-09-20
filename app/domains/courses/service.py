from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.common.geo import bounding_box, haversine_distance_m
from app.domains.courses.models import Course, CoursePlace
from app.domains.courses.repository import (
    CoursePlaceEntry,
    CoursePlaceReplacement,
    add_course_places,
    create_course,
    delete_course,
    get_course_by_id,
    get_course_places_by_course_ids,
    get_courses_by_ids,
    list_courses_by_dog_id,
    list_courses_within_bounding_box,
    replace_course_places,
)
from app.domains.courses.schemas import CategoryTarget, CourseCategory, CourseCreateRequest, CourseSummary
from app.domains.likes import repository as likes_repository
from app.domains.logs.models import Log
from app.domains.places.constants import DEFAULT_STAY_MINUTES, PlaceSearchCategory
from app.domains.places.repository import get_or_create_places
from app.domains.places.schemas import WalkingCourseResult
from app.domains.places.service import create_walking_course
from app.domains.saves import repository as saves_repository


class NotCourseOwnerError(Exception):
    """요청자가 해당 코스의 소유자가 아닐 때(공유/삭제 API에서 사용)."""


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
    db: Session, request: CourseCreateRequest, dog_id: int
) -> tuple[Course, list[CoursePlace], WalkingCourseResult]:
    """코스 생성 파이프라인(places.service.create_walking_course)을 실행하고 결과를
    Course/CoursePlace로 영속화한다. dog_id는 코스 생성자(소유자)로 저장된다."""
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
            dog_id=dog_id,
            path=result.path,
            walk_date=request.walk_date,
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


def _to_course_summary(
    course: Course,
    course_places: list[CoursePlace],
    *,
    distance_meters: int | None,
    requester_dog_id: int | None,
    like_count: int,
    is_liked: bool,
    save_count: int,
    is_saved: bool,
) -> CourseSummary:
    return CourseSummary(
        course_id=course.course_id,
        title=course.title,
        start_lat=course.start_lat,
        start_lng=course.start_lng,
        distance_meters=distance_meters,
        total_distance_meters=sum(cp.travel_distance_meters or 0 for cp in course_places),
        total_duration_minutes=sum(
            (cp.stay_minutes or 0) + (cp.travel_minutes or 0) for cp in course_places
        ),
        place_count=len(course_places),
        thumbnail_image_url=course_places[0].place.image_url if course_places else None,
        is_owner=requester_dog_id is not None and course.dog_id == requester_dog_id,
        like_count=like_count,
        is_liked=is_liked,
        save_count=save_count,
        is_saved=is_saved,
    )


def _engagement_lookup(
    db: Session, course_ids: list[int], requester_dog_id: int | None
) -> tuple[dict[int, int], set[int], dict[int, int], set[int]]:
    """course_ids에 대한 좋아요/저장 카운트와, requester_dog_id가 좋아요/저장한
    course_id 집합을 배치 조회한다(목록 크기와 무관하게 쿼리 4번 고정 — N+1 방지)."""
    like_counts = likes_repository.count_by_course_ids(db, course_ids)
    save_counts = saves_repository.count_by_course_ids(db, course_ids)
    liked_ids = (
        likes_repository.liked_course_ids(db, requester_dog_id, course_ids)
        if requester_dog_id is not None
        else set()
    )
    saved_ids = (
        saves_repository.saved_course_ids(db, requester_dog_id, course_ids)
        if requester_dog_id is not None
        else set()
    )
    return like_counts, liked_ids, save_counts, saved_ids


def list_nearby_courses(
    db: Session,
    *,
    lat: float,
    lng: float,
    radius_m: int,
    limit: int,
    offset: int,
    requester_dog_id: int | None = None,
) -> list[CourseSummary]:
    """반경(radius_m) 내 공개(is_shared=True) 코스를 거리순으로 반환한다.

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

    course_ids = [course.course_id for course, _ in page]
    course_places = get_course_places_by_course_ids(db, course_ids)
    places_by_course: dict[int, list[CoursePlace]] = defaultdict(list)
    for cp in course_places:
        places_by_course[cp.course_id].append(cp)

    like_counts, liked_ids, save_counts, saved_ids = _engagement_lookup(
        db, course_ids, requester_dog_id
    )

    return [
        _to_course_summary(
            course,
            places_by_course.get(course.course_id, []),
            distance_meters=round(distance),
            requester_dog_id=requester_dog_id,
            like_count=like_counts.get(course.course_id, 0),
            is_liked=course.course_id in liked_ids,
            save_count=save_counts.get(course.course_id, 0),
            is_saved=course.course_id in saved_ids,
        )
        for course, distance in page
    ]


def list_saved_courses(db: Session, dog_id: int) -> list[CourseSummary]:
    """내가 저장(북마크)한 코스를 저장한 순서(최신순)로 반환한다. 좌표 기준 조회가
    아니므로 distance_meters는 없다(None)."""
    course_ids = saves_repository.list_course_ids_by_dog_id(db, dog_id)
    courses_by_id = {course.course_id: course for course in get_courses_by_ids(db, course_ids)}

    course_places = get_course_places_by_course_ids(db, course_ids)
    places_by_course: dict[int, list[CoursePlace]] = defaultdict(list)
    for cp in course_places:
        places_by_course[cp.course_id].append(cp)

    like_counts, liked_ids, save_counts, saved_ids = _engagement_lookup(db, course_ids, dog_id)

    return [
        _to_course_summary(
            courses_by_id[course_id],
            places_by_course.get(course_id, []),
            distance_meters=None,
            requester_dog_id=dog_id,
            like_count=like_counts.get(course_id, 0),
            is_liked=course_id in liked_ids,
            save_count=save_counts.get(course_id, 0),
            is_saved=course_id in saved_ids,
        )
        for course_id in course_ids
    ]


def list_my_courses(db: Session, dog_id: int) -> list[CourseSummary]:
    """내가 만든 코스 전부(공개 여부 무관)를 최신순으로 반환한다. 좌표 기준 조회가
    아니므로 distance_meters는 없다(None)."""
    courses = list_courses_by_dog_id(db, dog_id)
    course_ids = [course.course_id for course in courses]

    course_places = get_course_places_by_course_ids(db, course_ids)
    places_by_course: dict[int, list[CoursePlace]] = defaultdict(list)
    for cp in course_places:
        places_by_course[cp.course_id].append(cp)

    like_counts, liked_ids, save_counts, saved_ids = _engagement_lookup(db, course_ids, dog_id)

    return [
        _to_course_summary(
            course,
            places_by_course.get(course.course_id, []),
            distance_meters=None,
            requester_dog_id=dog_id,
            like_count=like_counts.get(course.course_id, 0),
            is_liked=course.course_id in liked_ids,
            save_count=save_counts.get(course.course_id, 0),
            is_saved=course.course_id in saved_ids,
        )
        for course in courses
    ]


def get_course_detail(
    db: Session, course_id: int, requester_dog_id: int | None
) -> tuple[Course, list[CoursePlace], bool] | None:
    """코스 상세조회. 존재하지 않거나, 비공개인데 요청자가 소유자가 아니면 None을 반환해
    존재 자체를 숨긴다(라우터에서 404로 처리)."""
    course = get_course_by_id(db, course_id)
    if course is None:
        return None

    is_owner = requester_dog_id is not None and course.dog_id == requester_dog_id
    if not course.is_shared and not is_owner:
        return None

    course_places = get_course_places_by_course_ids(db, [course_id])
    return course, course_places, is_owner


def share_course(db: Session, course_id: int, dog_id: int) -> Course:
    """코스를 전체 공개로 전환한다. 소유자만 호출 가능."""
    course = get_course_by_id(db, course_id)
    if course is None:
        raise NotFoundError("Course", course_id)
    if course.dog_id != dog_id:
        raise NotCourseOwnerError

    course.is_shared = True
    db.commit()
    db.refresh(course)
    return course


def update_course(db: Session, course_id: int, dog_id: int, **fields: object) -> Course:
    """코스 메타데이터(현재는 title만)를 수정한다. 소유자만 호출 가능."""
    course = get_course_by_id(db, course_id)
    if course is None:
        raise NotFoundError("Course", course_id)
    if course.dog_id != dog_id:
        raise NotCourseOwnerError

    for key, value in fields.items():
        setattr(course, key, value)

    db.commit()
    db.refresh(course)
    return course


def save_course_places(
    db: Session,
    course_id: int,
    dog_id: int,
    entries: list[CoursePlaceReplacement],
    path: list[tuple[float, float]],
    *,
    ended_at: datetime | None = None,
) -> Course:
    """코스 스팟 구성을 저장한다(소유자만 가능). 서버는 프론트가 계산한 거리/시간을
    그대로 믿는다. 첫 확정 때만 산책 기록을 만들고, 이후 편집에서는 기존 기록과
    일기를 유지한다.
    """
    course = get_course_by_id(db, course_id)
    if course is None:
        raise NotFoundError("Course", course_id)
    if course.dog_id != dog_id:
        raise NotCourseOwnerError

    replace_course_places(db, course_id, entries)
    course.path = path

    # The first replacement finalizes a newly generated course. Later edits
    # must not create another walk record (or overwrite an existing diary).
    existing_log_id = db.scalar(select(Log.log_id).where(Log.course_id == course_id).limit(1))
    if existing_log_id is None:
        db.add(
            Log(
                dog_id=dog_id,
                course_id=course_id,
                started_at=course.walk_date or datetime.now(UTC),
                ended_at=ended_at,
            )
        )

    db.commit()
    db.refresh(course)
    return course


def delete_course_by_id(db: Session, course_id: int, dog_id: int) -> None:
    """코스를 삭제한다. 소유자만 호출 가능. 자식 테이블(CoursePlace/Save/Like)은 FK
    ondelete=CASCADE로, Log.course_id는 ondelete=SET NULL로 DB가 알아서 정리한다."""
    course = get_course_by_id(db, course_id)
    if course is None:
        raise NotFoundError("Course", course_id)
    if course.dog_id != dog_id:
        raise NotCourseOwnerError

    delete_course(db, course)
    db.commit()
