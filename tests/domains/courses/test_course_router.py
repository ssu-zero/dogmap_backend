import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.common.base_model import Base
from app.common.exceptions import ExternalApiError
from app.core.database import get_db
from app.core.security import create_access_token
from app.domains.courses import service as courses_service
from app.domains.courses.models import Course, CoursePlace
from app.domains.places.models import Place, PlaceCategory
from app.domains.places.schemas import PlaceCandidate, WalkingCourseLeg, WalkingCourseResult
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


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {create_access_token(dog_id=1)}"}


def _request_body() -> dict:
    return {
        "start_lat": 37.5,
        "start_lng": 127.0,
        "target_duration_minutes": 60,
        "category_targets": [{"category": "WALK", "count": 1}],
    }


def _fixed_result() -> WalkingCourseResult:
    stop = PlaceCandidate(
        content_id="1", title="공원", category="산책", address="서울", lat=37.51, lng=127.01, dist=0.0
    )
    leg = WalkingCourseLeg(from_title="출발", to_title="공원", distance_meters=100.0, duration_minutes=2.0)
    return WalkingCourseResult(
        stops=[stop], legs=[leg], total_distance_meters=100.0, total_duration_minutes=2.0,
        path=[(37.5, 127.0), (37.51, 127.01)],
    )


def test_create_course_without_auth_header_is_rejected(client):
    response = client.post("/api/v1/courses", json=_request_body())
    assert response.status_code == 401


def test_create_course_returns_persisted_course(client, monkeypatch):
    async def fake_create_walking_course(*args, **kwargs):
        return _fixed_result()

    monkeypatch.setattr(courses_service, "create_walking_course", fake_create_walking_course)

    response = client.post(
        "/api/v1/courses", json=_request_body(), headers=_auth_headers()
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "60분 산책 코스"
    assert len(body["places"]) == 1
    assert body["places"][0]["name"] == "공원"
    assert body["total_distance_meters"] == 100.0


def test_create_course_maps_external_api_error_to_502(client, monkeypatch):
    async def fake_create_walking_course(*args, **kwargs):
        raise ExternalApiError("업스트림 실패")

    monkeypatch.setattr(courses_service, "create_walking_course", fake_create_walking_course)

    response = client.post(
        "/api/v1/courses", json=_request_body(), headers=_auth_headers()
    )

    assert response.status_code == 502


def _seed_nearby_course(session_factory) -> int:
    db = session_factory()
    place = Place(
        content_id="1", name="공원", category=PlaceCategory.PARK, latitude=37.5, longitude=127.0
    )
    db.add(place)
    db.flush()
    course = Course(title="코스", start_lat=37.501, start_lng=127.0)
    db.add(course)
    db.flush()
    db.add(
        CoursePlace(
            course_id=course.course_id,
            place_id=place.place_id,
            sequence=1,
            stay_minutes=15,
            travel_minutes=5,
            travel_distance_meters=300,
        )
    )
    db.commit()
    course_id = course.course_id
    db.close()
    return course_id


def test_get_nearby_courses_without_auth_header_is_rejected(client):
    response = client.get("/api/v1/courses", params={"lat": 37.5, "lng": 127.0})
    assert response.status_code == 401


def test_get_nearby_courses_returns_courses_within_radius(client, session_factory):
    course_id = _seed_nearby_course(session_factory)

    response = client.get(
        "/api/v1/courses",
        params={"lat": 37.5, "lng": 127.0, "radius_m": 3000},
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["course_id"] == course_id
    assert body[0]["place_count"] == 1
    assert body[0]["total_distance_meters"] == 300
    assert body[0]["total_duration_minutes"] == 20
