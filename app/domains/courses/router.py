from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.common.exceptions import ExternalApiError
from app.core.database import get_db
from app.core.security import get_current_dog_id
from app.domains.courses.models import Course, CoursePlace
from app.domains.courses.schemas import (
    CourseCreateRequest,
    CoursePlaceRead,
    CourseRead,
    CourseSummary,
)
from app.domains.courses.service import create_course_with_places, list_nearby_courses
from app.domains.places.schemas import WalkingCourseResult

router = APIRouter(prefix="/courses", tags=["courses"])


def _to_course_read(
    course: Course, course_places: list[CoursePlace], result: WalkingCourseResult
) -> CourseRead:
    return CourseRead(
        course_id=course.course_id,
        title=course.title,
        start_lat=course.start_lat,
        start_lng=course.start_lng,
        total_distance_meters=result.total_distance_meters,
        total_duration_minutes=result.total_duration_minutes,
        path=result.path,
        places=[
            CoursePlaceRead(
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
            )
            for cp in sorted(course_places, key=lambda cp: cp.sequence)
        ],
    )


@router.get("", response_model=list[CourseSummary])
async def get_nearby_courses(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(3000, ge=100, le=20000),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[CourseSummary]:
    return list_nearby_courses(db, lat=lat, lng=lng, radius_m=radius_m, limit=limit, offset=offset)


@router.post("", response_model=CourseRead, status_code=201)
async def create_course(
    request: CourseCreateRequest,
    db: Session = Depends(get_db),
    _dog_id: int = Depends(get_current_dog_id),
) -> CourseRead:
    try:
        course, course_places, result = await create_course_with_places(db, request)
    except ExternalApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _to_course_read(course, course_places, result)
