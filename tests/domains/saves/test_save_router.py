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


def _seed_course(session_factory, *, dog_id: int = 1) -> int:
    db = session_factory()
    course = Course(title="코스", start_lat=37.5, start_lng=127.0, dog_id=dog_id)
    db.add(course)
    db.commit()
    course_id = course.course_id
    db.close()
    return course_id


def test_save_course_requires_auth(client, session_factory):
    course_id = _seed_course(session_factory)
    response = client.post(f"/api/courses/{course_id}/save")
    assert response.status_code == 401


def test_save_course_returns_404_when_missing(client):
    response = client.post("/api/courses/999/save", headers=_auth_headers())
    assert response.status_code == 404


def test_save_course_sets_is_saved_and_increments_count(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=2)

    response = client.post(f"/api/courses/{course_id}/save", headers=_auth_headers(dog_id=1))

    assert response.status_code == 200
    body = response.json()
    assert body["course_id"] == course_id
    assert body["is_saved"] is True
    assert body["save_count"] == 1


def test_save_course_is_idempotent(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=2)

    client.post(f"/api/courses/{course_id}/save", headers=_auth_headers(dog_id=1))
    response = client.post(f"/api/courses/{course_id}/save", headers=_auth_headers(dog_id=1))

    assert response.status_code == 200
    assert response.json()["save_count"] == 1


def test_save_course_counts_saves_from_multiple_dogs(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=3)

    client.post(f"/api/courses/{course_id}/save", headers=_auth_headers(dog_id=1))
    response = client.post(f"/api/courses/{course_id}/save", headers=_auth_headers(dog_id=2))

    assert response.json()["save_count"] == 2


def test_unsave_course_requires_auth(client, session_factory):
    course_id = _seed_course(session_factory)
    response = client.delete(f"/api/courses/{course_id}/save")
    assert response.status_code == 401


def test_unsave_course_returns_404_when_missing(client):
    response = client.delete("/api/courses/999/save", headers=_auth_headers())
    assert response.status_code == 404


def test_unsave_course_removes_save(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=2)
    client.post(f"/api/courses/{course_id}/save", headers=_auth_headers(dog_id=1))

    response = client.delete(f"/api/courses/{course_id}/save", headers=_auth_headers(dog_id=1))

    assert response.status_code == 200
    body = response.json()
    assert body["is_saved"] is False
    assert body["save_count"] == 0


def test_unsave_course_is_idempotent_when_never_saved(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=2)

    response = client.delete(f"/api/courses/{course_id}/save", headers=_auth_headers(dog_id=1))

    assert response.status_code == 200
    assert response.json()["save_count"] == 0


def test_list_saved_courses_requires_auth(client):
    response = client.get("/api/saves")
    assert response.status_code == 401


def test_list_saved_courses_excludes_unsaved_courses(client, session_factory):
    _seed_course(session_factory, dog_id=2)  # 저장하지 않음

    response = client.get("/api/saves", headers=_auth_headers(dog_id=1))

    assert response.status_code == 200
    assert response.json() == []


def test_list_saved_courses_returns_newest_saved_first(client, session_factory):
    first_course_id = _seed_course(session_factory, dog_id=2)
    second_course_id = _seed_course(session_factory, dog_id=2)

    client.post(f"/api/courses/{first_course_id}/save", headers=_auth_headers(dog_id=1))
    client.post(f"/api/courses/{second_course_id}/save", headers=_auth_headers(dog_id=1))

    response = client.get("/api/saves", headers=_auth_headers(dog_id=1))

    assert response.status_code == 200
    course_ids = [c["course_id"] for c in response.json()]
    assert course_ids == [second_course_id, first_course_id]


def test_list_saved_courses_excludes_other_dogs_saves(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=2)
    client.post(f"/api/courses/{course_id}/save", headers=_auth_headers(dog_id=1))

    response = client.get("/api/saves", headers=_auth_headers(dog_id=2))

    assert response.json() == []


def test_list_saved_courses_has_no_distance_meters(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=2)
    client.post(f"/api/courses/{course_id}/save", headers=_auth_headers(dog_id=1))

    response = client.get("/api/saves", headers=_auth_headers(dog_id=1))

    assert response.json()[0]["distance_meters"] is None
