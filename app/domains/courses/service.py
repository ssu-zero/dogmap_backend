from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.domains.courses import repository
from app.domains.courses.models import Course
from app.domains.courses.schemas import CourseCreate, CourseGenerateRequest


def get_course_or_404(db: Session, course_id: int) -> Course:
    course = repository.get_course(db, course_id)
    if course is None:
        raise NotFoundError("Course", course_id)
    return course


def list_courses(db: Session) -> list[Course]:
    return repository.list_courses(db)


def create_course(db: Session, course_in: CourseCreate) -> Course:
    return repository.create_course(db, course_in)


def delete_course(db: Session, course_id: int) -> None:
    course = get_course_or_404(db, course_id)
    repository.delete_course(db, course)


def _search_nearby_places(start_lat: str, start_lng: str) -> list[dict]:
    """TODO: Kakao Local API 연동 — 출발지 주변 강아지 동반 가능 장소 검색."""
    raise NotImplementedError


def _build_route(waypoints: list[dict]) -> dict:
    """TODO: T-map API 연동 — 경유지 기반 도보 경로/이동시간/거리 계산."""
    raise NotImplementedError


def _recommend_sequence(places: list[dict], duration_minutes: int) -> list[dict]:
    """TODO: LLM 연동 — 소요 시간/강아지 특성을 고려한 방문 순서 및 체류시간 추천."""
    raise NotImplementedError


def generate_course(db: Session, request: CourseGenerateRequest) -> Course:
    """Kakao Local API로 장소를 찾고, LLM으로 방문 순서를 정한 뒤,
    T-map으로 경로를 계산해 코스를 생성하는 파이프라인.

    TODO: 아래 3단계 연동 구현 후 CourseCreate로 조립하여 repository.create_course 호출.
    """
    raise NotImplementedError
