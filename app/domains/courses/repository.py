from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
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
    walk_date: datetime | None = None,
) -> Course:
    course = Course(
        title=title,
        start_lat=start_lat,
        start_lng=start_lng,
        dog_id=dog_id,
        path=path,
        walk_date=walk_date,
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


@dataclass
class CoursePlaceReplacement:
    place_id: int
    sequence: int
    stay_minutes: int | None
    travel_minutes: int | None
    travel_distance_meters: int | None


def replace_course_places(
    db: Session, course_id: int, entries: list[CoursePlaceReplacement]
) -> list[CoursePlace]:
    """기존 course_places를 전부 지우고 넘어온 구성으로 교체한다. 코스 편집 화면에서
    프론트가 스팟 삭제/재계산까지 마친 최종 값을 그대로 신뢰해서 저장한다(서버는
    재계산하지 않음)."""
    db.execute(delete(CoursePlace).where(CoursePlace.course_id == course_id))
    course_places = [
        CoursePlace(
            course_id=course_id,
            place_id=entry.place_id,
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
