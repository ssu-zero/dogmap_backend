import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.common.base_model import Base
from app.common.exceptions import ExternalApiError
from app.core.database import get_db
from app.core.security import create_access_token
from app.domains.courses.models import Course, CoursePlace
from app.domains.likes.models import Like
from app.domains.places import router as places_router
from app.domains.places.schemas import PlaceCandidate
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


def _query() -> dict:
    return {"lat": 37.5, "lng": 127.0, "category": "산책"}


def _fake_candidate(content_id: str = "1") -> PlaceCandidate:
    return PlaceCandidate(
        content_id=content_id,
        title="공원",
        category="산책",
        address="서울",
        lat=37.5,
        lng=127.0,
        dist=10.0,
    )


def _patch_list_nearby_places(monkeypatch, candidates: list[PlaceCandidate]) -> None:
    async def fake(category, lat, lng, *, radius, limit):
        return candidates

    monkeypatch.setattr(places_router, "list_nearby_places", fake)


def test_get_nearby_places_returns_candidates_with_zero_likes_by_default(client, monkeypatch):
    _patch_list_nearby_places(monkeypatch, [_fake_candidate()])

    response = client.get("/api/places", params=_query())

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "공원"
    assert body[0]["like_count"] == 0
    assert body[0]["is_liked"] is False
    assert "place_id" in body[0]


def test_get_nearby_places_works_without_auth(client, monkeypatch):
    _patch_list_nearby_places(monkeypatch, [_fake_candidate()])

    response = client.get("/api/places", params=_query())

    assert response.status_code == 200


def test_get_nearby_places_reuses_existing_place_by_content_id(client, monkeypatch):
    _patch_list_nearby_places(monkeypatch, [_fake_candidate()])

    first = client.get("/api/places", params=_query())
    second = client.get("/api/places", params=_query())

    assert first.json()[0]["place_id"] == second.json()[0]["place_id"]


def test_get_nearby_places_counts_likes_via_courses_containing_the_place(
    client, monkeypatch, session_factory
):
    """장소 자체에 좋아요를 남기지 않는다 — 그 장소가 포함된 코스가 받은 좋아요를
    합산해서 보여준다."""
    _patch_list_nearby_places(monkeypatch, [_fake_candidate()])

    created = client.get("/api/places", params=_query(), headers=_auth_headers(dog_id=1))
    place_id = created.json()[0]["place_id"]

    db = session_factory()
    course = Course(title="코스", start_lat=37.5, start_lng=127.0, dog_id=3)
    db.add(course)
    db.flush()
    db.add(CoursePlace(course_id=course.course_id, place_id=place_id, sequence=1))
    db.add(Like(dog_id=1, course_id=course.course_id))
    db.commit()
    db.close()

    liked_by_liker = client.get("/api/places", params=_query(), headers=_auth_headers(dog_id=1))
    liked_by_other = client.get("/api/places", params=_query(), headers=_auth_headers(dog_id=2))

    assert liked_by_liker.json()[0]["is_liked"] is True
    assert liked_by_liker.json()[0]["like_count"] == 1
    assert liked_by_other.json()[0]["is_liked"] is False
    assert liked_by_other.json()[0]["like_count"] == 1


def test_get_nearby_places_maps_external_api_error_to_502(client, monkeypatch):
    async def fake_raise(category, lat, lng, *, radius, limit):
        raise ExternalApiError("업스트림 실패")

    monkeypatch.setattr(places_router, "list_nearby_places", fake_raise)

    response = client.get("/api/places", params=_query())

    assert response.status_code == 502
