import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.common.base_model import Base
from app.core.database import get_db
from app.core.security import create_access_token
from app.domains.courses.models import Course
from app.main import app


@pytest.fixture
def app_client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, TestingSession
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def client(app_client):
    return app_client[0]


@pytest.fixture
def session_factory(app_client):
    return app_client[1]


def _auth_headers(dog_id: int = 1) -> dict:
    return {"Authorization": f"Bearer {create_access_token(dog_id=dog_id)}"}


def _seed_course(session_factory, *, dog_id: int, is_shared: bool = False) -> int:
    db = session_factory()
    course = Course(title="코스", start_lat=37.5, start_lng=127.0, dog_id=dog_id, is_shared=is_shared)
    db.add(course)
    db.commit()
    course_id = course.course_id
    db.close()
    return course_id


def test_get_my_courses_requires_auth(client):
    response = client.get("/api/dogs/me/courses")
    assert response.status_code == 401


def test_get_my_courses_includes_private_courses(client, session_factory):
    _seed_course(session_factory, dog_id=1, is_shared=False)

    response = client.get("/api/dogs/me/courses", headers=_auth_headers(dog_id=1))

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_my_courses_excludes_other_dogs_courses(client, session_factory):
    _seed_course(session_factory, dog_id=2, is_shared=True)

    response = client.get("/api/dogs/me/courses", headers=_auth_headers(dog_id=1))

    assert response.json() == []


def test_get_my_courses_returns_newest_first(client, session_factory):
    first_id = _seed_course(session_factory, dog_id=1)
    second_id = _seed_course(session_factory, dog_id=1)

    response = client.get("/api/dogs/me/courses", headers=_auth_headers(dog_id=1))

    course_ids = [c["course_id"] for c in response.json()]
    assert course_ids == [second_id, first_id]


def test_get_my_courses_has_no_distance_meters_and_marks_ownership(client, session_factory):
    _seed_course(session_factory, dog_id=1)

    response = client.get("/api/dogs/me/courses", headers=_auth_headers(dog_id=1))

    body = response.json()[0]
    assert body["distance_meters"] is None
    assert body["is_owner"] is True


def test_get_my_courses_reflects_like_and_save_counts(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=1, is_shared=True)
    client.post(f"/api/courses/{course_id}/like", headers=_auth_headers(dog_id=2))
    client.post(f"/api/courses/{course_id}/save", headers=_auth_headers(dog_id=1))

    response = client.get("/api/dogs/me/courses", headers=_auth_headers(dog_id=1))

    body = response.json()[0]
    assert body["like_count"] == 1
    assert body["is_liked"] is False  # 좋아요는 dog_id=2가 눌렀다
    assert body["save_count"] == 1
    assert body["is_saved"] is True
