"""DB 제약조건(유니크) 검증 — SQLite in-memory에 스키마를 만들어 테스트한다.

실제 MySQL 마이그레이션은 develop 병합 후 별도로 진행하므로, 여기서는 Alembic이나
프로젝트 공용 스크립트에 의존하지 않고 테스트 안에서만 쓰는 임시 스키마를 만든다.

SQLite는 PK 컬럼이 정확히 "INTEGER" 타입일 때만 rowid-alias autoincrement가 동작한다.
BigInteger는 SQLite에서 BIGINT로 매핑되어 이 규칙에 해당하지 않으므로(실제 MySQL에서는
문제없이 AUTO_INCREMENT가 동작함), 테스트에서는 PK 값을 직접 지정해서 우회한다.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.base_model import Base
from app.domains.courses.models import Course, CoursePlace
from app.domains.dogs.models import Dog, DogSize
from app.domains.likes.models import Like
from app.domains.logs.models import Log  # noqa: F401 (Base.metadata 등록용)
from app.domains.places.models import Place, PlaceCategory
from app.domains.saves.models import Save


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def _make_dog(session: Session, dog_id: int, kakao_id: int, name: str = "바둑이") -> Dog:
    dog = Dog(dog_id=dog_id, kakao_id=kakao_id, name=name, size=DogSize.SMALL)
    session.add(dog)
    session.commit()
    return dog


def _make_course(session: Session, course_id: int, title: str = "코스") -> Course:
    course = Course(course_id=course_id, title=title, start_lat=37.5, start_lng=127.0)
    session.add(course)
    session.commit()
    return course


def _make_place(session: Session, place_id: int, name: str = "장소") -> Place:
    place = Place(
        place_id=place_id,
        content_id=f"cid-{place_id}",
        name=name,
        category=PlaceCategory.PARK,
        latitude=37.5,
        longitude=127.0,
    )
    session.add(place)
    session.commit()
    return place


def test_duplicate_kakao_id_raises_integrity_error(session):
    _make_dog(session, dog_id=1, kakao_id=42, name="A")
    session.add(Dog(dog_id=2, kakao_id=42, name="B", size=DogSize.SMALL))

    with pytest.raises(IntegrityError):
        session.commit()


def test_duplicate_like_raises_integrity_error(session):
    dog = _make_dog(session, dog_id=1, kakao_id=1001)
    course = _make_course(session, course_id=1)
    session.add(Like(like_id=1, dog_id=dog.dog_id, course_id=course.course_id))
    session.commit()

    session.add(Like(like_id=2, dog_id=dog.dog_id, course_id=course.course_id))
    with pytest.raises(IntegrityError):
        session.commit()


def test_duplicate_save_raises_integrity_error(session):
    dog = _make_dog(session, dog_id=1, kakao_id=1001)
    course = _make_course(session, course_id=1)
    session.add(Save(save_id=1, dog_id=dog.dog_id, course_id=course.course_id))
    session.commit()

    session.add(Save(save_id=2, dog_id=dog.dog_id, course_id=course.course_id))
    with pytest.raises(IntegrityError):
        session.commit()


def test_duplicate_course_place_sequence_raises_integrity_error(session):
    course = _make_course(session, course_id=1)
    place1 = _make_place(session, place_id=1, name="장소1")
    place2 = _make_place(session, place_id=2, name="장소2")
    session.add(
        CoursePlace(
            course_place_id=1, course_id=course.course_id, place_id=place1.place_id, sequence=1
        )
    )
    session.commit()

    session.add(
        CoursePlace(
            course_place_id=2, course_id=course.course_id, place_id=place2.place_id, sequence=1
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_same_place_can_be_visited_twice_with_different_sequence(session):
    """course_id+place_id 유니크는 기본적으로 걸지 않는다 — 동일 장소 재방문(예: 공원 입구 →
    카페 → 공원 입구)을 허용해야 하므로 sequence만 다르면 성공해야 한다."""
    course = _make_course(session, course_id=1)
    place = _make_place(session, place_id=1)

    session.add(
        CoursePlace(
            course_place_id=1, course_id=course.course_id, place_id=place.place_id, sequence=1
        )
    )
    session.add(
        CoursePlace(
            course_place_id=2, course_id=course.course_id, place_id=place.place_id, sequence=2
        )
    )
    session.commit()  # 예외 없이 성공해야 함
