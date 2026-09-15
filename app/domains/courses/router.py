from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.common.exceptions import ExternalApiError, NotFoundError
from app.core.database import get_db
from app.core.security import get_current_dog_id, get_current_dog_id_optional
from app.domains.courses.models import Course, CoursePlace
from app.domains.courses.repository import CoursePlaceReplacement, get_course_places_by_course_ids
from app.domains.courses.schemas import (
    CourseCreateRequest,
    CoursePlaceRead,
    CoursePlacesReplaceRequest,
    CourseRead,
    CourseSummary,
    CourseUpdate,
)
from app.domains.courses.service import (
    NotCourseOwnerError,
    create_course_with_places,
    delete_course_by_id,
    get_course_detail,
    list_nearby_courses,
    save_course_places,
    share_course,
    update_course,
)
from app.domains.places.schemas import WalkingCourseResult

router = APIRouter(prefix="/courses", tags=["courses"])

_COURSE_NOT_FOUND_DETAIL = "코스를 찾을 수 없습니다"


def _compute_visit_times(
    walk_date: datetime | None, ordered_places: list[CoursePlace]
) -> list[datetime | None]:
    """Course.walk_date를 기준으로, 각 스팟까지 누적된 travel_minutes(+ 이전 스팟들의
    stay_minutes)를 더해 도착 예정 시각을 계산한다. DB에 저장하지 않고 매번 계산한다.
    walk_date가 없는(과거 방식으로 만들어진) 코스는 전부 None을 반환한다."""
    if walk_date is None:
        return [None] * len(ordered_places)

    visit_times: list[datetime | None] = []
    elapsed = timedelta()
    for cp in ordered_places:
        elapsed += timedelta(minutes=cp.travel_minutes or 0)
        visit_times.append(walk_date + elapsed)
        elapsed += timedelta(minutes=cp.stay_minutes or 0)
    return visit_times


def _to_course_place_read(cp: CoursePlace, visit_time: datetime | None) -> CoursePlaceRead:
    return CoursePlaceRead(
        place_id=cp.place.place_id,
        name=cp.place.name,
        category=cp.place.category,
        image_url=cp.place.image_url,
        lat=cp.place.latitude,
        lng=cp.place.longitude,
        sequence=cp.sequence,
        stay_minutes=cp.stay_minutes,
        travel_minutes=cp.travel_minutes,
        travel_distance_meters=cp.travel_distance_meters,
        visit_time=visit_time,
    )


def _to_course_read(
    course: Course,
    course_places: list[CoursePlace],
    result: WalkingCourseResult,
    *,
    is_owner: bool,
) -> CourseRead:
    """코스 생성 직후, 방금 계산한 WalkingCourseResult로 응답을 만든다."""
    ordered = sorted(course_places, key=lambda cp: cp.sequence)
    visit_times = _compute_visit_times(course.walk_date, ordered)
    return CourseRead(
        course_id=course.course_id,
        title=course.title,
        start_lat=course.start_lat,
        start_lng=course.start_lng,
        walk_date=course.walk_date,
        total_distance_meters=result.total_distance_meters,
        total_duration_minutes=result.total_duration_minutes,
        path=result.path,
        places=[
            _to_course_place_read(cp, vt) for cp, vt in zip(ordered, visit_times, strict=True)
        ],
        is_owner=is_owner,
        is_shared=course.is_shared,
        generation_duration_ms=result.generation_duration_ms,
    )


def _to_course_read_from_db(
    course: Course, course_places: list[CoursePlace], *, is_owner: bool
) -> CourseRead:
    """상세조회/공유 응답용. T맵을 다시 부르지 않고 DB에 저장된 값(path, CoursePlace 합산)만
    으로 구성한다."""
    ordered = sorted(course_places, key=lambda cp: cp.sequence)
    visit_times = _compute_visit_times(course.walk_date, ordered)
    return CourseRead(
        course_id=course.course_id,
        title=course.title,
        start_lat=course.start_lat,
        start_lng=course.start_lng,
        walk_date=course.walk_date,
        total_distance_meters=sum(cp.travel_distance_meters or 0 for cp in ordered),
        total_duration_minutes=sum(
            (cp.stay_minutes or 0) + (cp.travel_minutes or 0) for cp in ordered
        ),
        path=course.path or [],
        places=[
            _to_course_place_read(cp, vt) for cp, vt in zip(ordered, visit_times, strict=True)
        ],
        is_owner=is_owner,
        is_shared=course.is_shared,
    )


@router.get("", response_model=list[CourseSummary], summary="주변 코스 목록 조회")
async def get_nearby_courses(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(3000, ge=100, le=20000),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    dog_id: int | None = Depends(get_current_dog_id_optional),
) -> list[CourseSummary]:
    return list_nearby_courses(
        db, lat=lat, lng=lng, radius_m=radius_m, limit=limit, offset=offset, requester_dog_id=dog_id
    )


@router.post("", response_model=CourseRead, status_code=201, summary="코스 생성")
async def create_course(
    request: CourseCreateRequest,
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> CourseRead:
    try:
        course, course_places, result = await create_course_with_places(db, request, dog_id)
    except ExternalApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _to_course_read(course, course_places, result, is_owner=True)


@router.get("/{course_id}", response_model=CourseRead, summary="코스 상세 조회")
async def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    dog_id: int | None = Depends(get_current_dog_id_optional),
) -> CourseRead:
    """코스 상세조회. 공개(is_shared) 코스는 누구나, 비공개 코스는 소유자만 볼 수 있다 —
    그 외에는 존재 여부를 숨기기 위해 404를 반환한다."""
    detail = get_course_detail(db, course_id, dog_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=_COURSE_NOT_FOUND_DETAIL)
    course, course_places, is_owner = detail
    return _to_course_read_from_db(course, course_places, is_owner=is_owner)


@router.patch("/{course_id}", response_model=CourseRead, summary="코스 수정")
async def update_course_endpoint(
    course_id: int,
    body: CourseUpdate,
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> CourseRead:
    """코스 메타데이터(제목)를 수정한다(소유자만 가능). body에 보낸 필드만 수정되는
    partial update — 수정하지 않을 필드는 아예 생략하면 된다."""
    update_data = body.model_dump(exclude_unset=True)
    try:
        course = update_course(db, course_id, dog_id, **update_data)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=_COURSE_NOT_FOUND_DETAIL) from exc
    except NotCourseOwnerError as exc:
        raise HTTPException(status_code=403, detail="본인이 만든 코스만 수정할 수 있습니다") from exc

    course_places = get_course_places_by_course_ids(db, [course_id])
    return _to_course_read_from_db(course, course_places, is_owner=True)


@router.put(
    "/{course_id}/places",
    response_model=CourseRead,
    summary="코스 스팟 구성 저장",
)
async def replace_course_places_endpoint(
    course_id: int,
    body: CoursePlacesReplaceRequest,
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> CourseRead:
    """코스 생성(POST) 후 프론트에서 스팟을 삭제/재구성해 코스를 확정할 때 호출한다
    (소유자만 가능). 서버는 거리/시간을 다시 계산하지 않고 넘어온 값을 그대로 신뢰해서
    저장하며, 이 확정과 함께 산책 기록(Log)도 새로 만든다."""
    entries = [
        CoursePlaceReplacement(
            place_id=p.place_id,
            sequence=p.sequence,
            stay_minutes=p.stay_minutes,
            travel_minutes=p.travel_minutes,
            travel_distance_meters=p.travel_distance_meters,
        )
        for p in body.places
    ]
    try:
        course = save_course_places(db, course_id, dog_id, entries, body.path, ended_at=body.ended_at)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=_COURSE_NOT_FOUND_DETAIL) from exc
    except NotCourseOwnerError as exc:
        raise HTTPException(status_code=403, detail="본인이 만든 코스만 수정할 수 있습니다") from exc

    course_places = get_course_places_by_course_ids(db, [course_id])
    return _to_course_read_from_db(course, course_places, is_owner=True)


@router.post("/{course_id}/share", response_model=CourseRead, summary="코스 공유(전체 공개)")
async def share_course_endpoint(
    course_id: int,
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> CourseRead:
    """코스를 전체 공개로 전환한다(소유자만 가능). 이미 공개된 코스에 다시 호출해도
    안전하다(idempotent)."""
    try:
        course = share_course(db, course_id, dog_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=_COURSE_NOT_FOUND_DETAIL) from exc
    except NotCourseOwnerError as exc:
        raise HTTPException(status_code=403, detail="본인이 만든 코스만 공유할 수 있습니다") from exc

    course_places = get_course_places_by_course_ids(db, [course_id])
    return _to_course_read_from_db(course, course_places, is_owner=True)


@router.delete("/{course_id}", status_code=204, summary="코스 삭제")
async def delete_course_endpoint(
    course_id: int,
    db: Session = Depends(get_db),
    dog_id: int = Depends(get_current_dog_id),
) -> None:
    """코스를 삭제한다(소유자만 가능)."""
    try:
        delete_course_by_id(db, course_id, dog_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=_COURSE_NOT_FOUND_DETAIL) from exc
    except NotCourseOwnerError as exc:
        raise HTTPException(status_code=403, detail="본인이 만든 코스만 삭제할 수 있습니다") from exc
