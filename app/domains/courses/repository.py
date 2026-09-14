from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domains.courses.models import Course, CoursePlace
from app.domains.places.models import Place


def create_course(
    db: Session,
    *,
    title: str,
    start_lat: float,
    start_lng: float,
    dog_id: int,
    path: list[tuple[float, float]],
) -> Course:
    course = Course(
        title=title, start_lat=start_lat, start_lng=start_lng, dog_id=dog_id, path=path
    )
    db.add(course)
    db.flush()
    return course


def get_course_by_id(db: Session, course_id: int) -> Course | None:
    return db.get(Course, course_id)


def delete_course(db: Session, course: Course) -> None:
    db.delete(course)
    db.flush()


@dataclass
class CoursePlaceEntry:
    place: Place
    sequence: int
    stay_minutes: int | None
    travel_minutes: int | None
    travel_distance_meters: int | None


def add_course_places(
    db: Session, course: Course, entries: list[CoursePlaceEntry]
) -> list[CoursePlace]:
    course_places = [
        CoursePlace(
            course_id=course.course_id,
            place_id=entry.place.place_id,
            sequence=entry.sequence,
            stay_minutes=entry.stay_minutes,
            travel_minutes=entry.travel_minutes,
            travel_distance_meters=entry.travel_distance_meters,
        )
        for entry in entries
    ]
    db.add_all(course_places)
    db.flush()
    return course_places


def list_courses_within_bounding_box(
    db: Session, *, min_lat: float, max_lat: float, min_lng: float, max_lng: float
) -> list[Course]:
    stmt = select(Course).where(
        Course.is_shared.is_(True),
        Course.start_lat.between(min_lat, max_lat),
        Course.start_lng.between(min_lng, max_lng),
    )
    return list(db.scalars(stmt).all())


def get_course_places_by_course_ids(db: Session, course_ids: list[int]) -> list[CoursePlace]:
    """course_id, sequence 순으로 정렬해서 반환. place는 즉시 로딩(selectinload)해서
    호출부(집계/썸네일)에서 N+1 쿼리가 나지 않게 한다."""
    if not course_ids:
        return []
    stmt = (
        select(CoursePlace)
        .where(CoursePlace.course_id.in_(course_ids))
        .options(selectinload(CoursePlace.place))
        .order_by(CoursePlace.course_id, CoursePlace.sequence)
    )
    return list(db.scalars(stmt).all())
