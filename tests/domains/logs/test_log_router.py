from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.common.base_model import Base
from app.core.database import get_db
from app.core.security import create_access_token
from app.domains.courses.models import Course
from app.domains.logs.models import Log
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


def _seed_log(
    session_factory,
    *,
    dog_id: int = 1,
    course_id: int | None = None,
    started_at: datetime | None = None,
) -> int:
    db = session_factory()
    log = Log(
        dog_id=dog_id,
        course_id=course_id,
        started_at=started_at or datetime.now(UTC),
    )
    db.add(log)
    db.commit()
    log_id = log.log_id
    db.close()
    return log_id


def test_list_logs_requires_auth(client):
    response = client.get("/api/logs")
    assert response.status_code == 401


def test_list_logs_returns_only_my_logs_newest_first(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=1)
    first_id = _seed_log(
        session_factory, dog_id=1, course_id=course_id, started_at=datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
    )
    second_id = _seed_log(session_factory, dog_id=1, started_at=datetime(2026, 9, 20, 10, 0, tzinfo=UTC))
    _seed_log(session_factory, dog_id=2)  # 다른 회원 기록

    response = client.get("/api/logs", headers=_auth_headers(dog_id=1))

    assert response.status_code == 200
    log_ids = [log["log_id"] for log in response.json()]
    assert log_ids == [second_id, first_id]


def test_get_log_requires_auth(client):
    response = client.get("/api/logs/1")
    assert response.status_code == 401


def test_get_log_returns_404_when_missing(client):
    response = client.get("/api/logs/999", headers=_auth_headers(dog_id=1))
    assert response.status_code == 404


def test_get_log_returns_404_for_non_owner(client, session_factory):
    log_id = _seed_log(session_factory, dog_id=1)

    response = client.get(f"/api/logs/{log_id}", headers=_auth_headers(dog_id=2))

    assert response.status_code == 404


def test_get_log_returns_detail_for_owner(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=1)
    log_id = _seed_log(session_factory, dog_id=1, course_id=course_id)

    response = client.get(f"/api/logs/{log_id}", headers=_auth_headers(dog_id=1))

    assert response.status_code == 200
    assert response.json()["course_id"] == course_id


def test_update_log_requires_auth(client):
    response = client.patch("/api/logs/1", json={"diary": "즐거운 산책이었다"})
    assert response.status_code == 401


def test_update_log_returns_404_when_missing(client):
    response = client.patch(
        "/api/logs/999", json={"diary": "즐거운 산책이었다"}, headers=_auth_headers(dog_id=1)
    )
    assert response.status_code == 404


def test_update_log_rejects_non_owner(client, session_factory):
    log_id = _seed_log(session_factory, dog_id=1)

    response = client.patch(
        f"/api/logs/{log_id}", json={"diary": "즐거운 산책이었다"}, headers=_auth_headers(dog_id=2)
    )

    assert response.status_code == 403


def test_update_log_sets_diary_for_owner(client, session_factory):
    log_id = _seed_log(session_factory, dog_id=1)

    response = client.patch(
        f"/api/logs/{log_id}", json={"diary": "즐거운 산책이었다"}, headers=_auth_headers(dog_id=1)
    )

    assert response.status_code == 200
    assert response.json()["diary"] == "즐거운 산책이었다"
