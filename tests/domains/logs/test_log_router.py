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


def test_create_log_requires_auth(client):
    response = client.post("/api/logs", json={})
    assert response.status_code == 401


def test_create_log_for_course_selection(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=1)

    response = client.post(
        "/api/logs", json={"course_id": course_id}, headers=_auth_headers(dog_id=1)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["course_id"] == course_id
    assert body["dog_id"] == 1
    assert body["diary"] is None
    assert body["started_at"] is not None
    # 종료 시각은 나중에 코스 스팟 구성 저장(PUT /courses/{id}/places)에서 채워진다.
    assert body["ended_at"] is None


def test_create_log_without_course_is_free_walk(client):
    response = client.post("/api/logs", json={}, headers=_auth_headers(dog_id=1))

    assert response.status_code == 201
    assert response.json()["course_id"] is None


def test_list_logs_requires_auth(client):
    response = client.get("/api/logs")
    assert response.status_code == 401


def test_list_logs_returns_only_my_logs_newest_first(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=1)
    first = client.post(
        "/api/logs", json={"course_id": course_id}, headers=_auth_headers(dog_id=1)
    ).json()
    second = client.post("/api/logs", json={}, headers=_auth_headers(dog_id=1)).json()
    client.post("/api/logs", json={}, headers=_auth_headers(dog_id=2))  # 다른 회원 기록

    response = client.get("/api/logs", headers=_auth_headers(dog_id=1))

    assert response.status_code == 200
    log_ids = [log["log_id"] for log in response.json()]
    assert log_ids == [second["log_id"], first["log_id"]]


def test_get_log_requires_auth(client):
    response = client.get("/api/logs/1")
    assert response.status_code == 401


def test_get_log_returns_404_when_missing(client):
    response = client.get("/api/logs/999", headers=_auth_headers(dog_id=1))
    assert response.status_code == 404


def test_get_log_returns_404_for_non_owner(client):
    created = client.post("/api/logs", json={}, headers=_auth_headers(dog_id=1)).json()

    response = client.get(f"/api/logs/{created['log_id']}", headers=_auth_headers(dog_id=2))

    assert response.status_code == 404


def test_get_log_returns_detail_for_owner(client, session_factory):
    course_id = _seed_course(session_factory, dog_id=1)
    created = client.post(
        "/api/logs", json={"course_id": course_id}, headers=_auth_headers(dog_id=1)
    ).json()

    response = client.get(f"/api/logs/{created['log_id']}", headers=_auth_headers(dog_id=1))

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


def test_update_log_rejects_non_owner(client):
    created = client.post("/api/logs", json={}, headers=_auth_headers(dog_id=1))
    log_id = created.json()["log_id"]

    response = client.patch(
        f"/api/logs/{log_id}", json={"diary": "즐거운 산책이었다"}, headers=_auth_headers(dog_id=2)
    )

    assert response.status_code == 403


def test_update_log_sets_diary_for_owner(client):
    created = client.post("/api/logs", json={}, headers=_auth_headers(dog_id=1))
    log_id = created.json()["log_id"]

    response = client.patch(
        f"/api/logs/{log_id}", json={"diary": "즐거운 산책이었다"}, headers=_auth_headers(dog_id=1)
    )

    assert response.status_code == 200
    assert response.json()["diary"] == "즐거운 산책이었다"
