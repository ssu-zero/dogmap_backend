from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.courses.models import Course, CoursePlace
from app.domains.courses.schemas import CourseCreate


def get_course(db: Session, course_id: int) -> Course | None:
    return db.get(Course, course_id)


def list_courses(db: Session) -> list[Course]:
    return list(db.scalars(select(Course)))


def create_course(db: Session, course_in: CourseCreate) -> Course:
    course = Course(
        title=course_in.title,
        start_lat=course_in.start_lat,
        start_lng=course_in.start_lng,
        course_places=[
            CoursePlace(**place_in.model_dump()) for place_in in course_in.places
        ],
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def delete_course(db: Session, course: Course) -> None:
    db.delete(course)
    db.commit()
