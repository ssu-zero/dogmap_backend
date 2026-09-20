import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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


def _auth_headers(dog_id: int = 1) -> dict:
    return {"Authorization": f"Bearer {create_access_token(dog_id=dog_id)}"}


def _request_body() -> dict:
    return {
        "start_lat": 37.5,
        "start_lng": 127.0,
        "target_duration_minutes": 60,
        "category_targets": [{"category": "WALK", "count": 1}],
        "walk_date": "2026-09-20T10:00:00+09:00",
    }


def _fixed_result() -> WalkingCourseResult:
    stop = PlaceCandidate(
        content_id="1", title="공원", category="산책", address="서울", lat=37.51, lng=127.01, dist=0.0
    )
    leg = WalkingCourseLeg(from_title="출발", to_title="공원", distance_meters=100.0, duration_minutes=2.0)
    return WalkingCourseResult(
        stops=[stop], legs=[leg], total_distance_meters=100.0, total_duration_minutes=2.0,
        path=[(37.5, 127.0), (37.51, 127.01)],
        generation_duration_ms=999,
    )


def test_create_course_without_auth_header_is_rejected(client):
    response = client.post("/api/courses", json=_request_body())
    assert response.status_code == 401


def test_create_course_returns_persisted_course(client, monkeypatch):
    async def fake_create_walking_course(*args, **kwargs):
        return _fixed_result()

    monkeypatch.setattr(courses_service, "create_walking_course", fake_create_walking_course)

    response = client.post(
        "/api/courses", json=_request_body(), headers=_auth_headers()
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "60분 산책 코스"
    assert len(body["places"]) == 1
    assert body["places"][0]["name"] == "공원"
    assert body["total_distance_meters"] == 100.0
    assert body["is_owner"] is True
    assert body["is_shared"] is False
    assert body["generation_duration_ms"] == 999


def test_create_course_maps_external_api_error_to_502(client, monkeypatch):
    async def fake_create_walking_course(*args, **kwargs):
        raise ExternalApiError("업스트림 실패")

    monkeypatch.setattr(courses_service, "create_walking_course", fake_create_walking_course)

    response = client.post(
        "/api/courses", json=_request_body(), headers=_auth_headers()
    )

    assert response.status_code == 502


def _seed_nearby_course(session_factory, *, dog_id: int | None = 1, is_shared: bool = True) -> int:
    db = session_factory()
    place = Place(
        content_id="1", name="공원", category=PlaceCategory.PARK, latitude=37.5, longitude=127.0
    )
    db.add(place)
    db.flush()
    course = Course(
        title="코스", start_lat=37.501, start_lng=127.0, dog_id=dog_id, is_shared=is_shared
    )
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


def test_create_course_computes_visit_time_from_walk_date(client, monkeypatch):
    async def fake_create_walking_course(*args, **kwargs):
        return _fixed_result()

    monkeypatch.setattr(courses_service, "create_walking_course", fake_create_walking_course)

    response = client.post("/api/courses", json=_request_body(), headers=_auth_headers())

    assert response.status_code == 201
    place = response.json()["places"][0]
    # walk_date(10:00) + travel_minutes(round(2.0)=2분) = 10:02.
    # SQLite는 DateTime(timezone=True)도 naive로 왕복시키므로 오프셋 없이 비교한다.
    assert place["visit_time"].startswith("2026-09-20T10:02:00")


def test_get_nearby_courses_without_auth_header_is_allowed(client, session_factory):
    # 코스 목록 조회는 비로그인 사용자도 볼 수 있어야 하는 공개 API라 인증이 필요 없다.
    _seed_nearby_course(session_factory)

    response = client.get("/api/courses", params={"lat": 37.5, "lng": 127.0})
    assert response.status_code == 200


def test_get_nearby_courses_returns_courses_within_radius(client, session_factory):
    course_id = _seed_nearby_course(session_factory)

    response = client.get(
        "/api/courses",
        params={"lat": 37.5, "lng": 127.0, "radius_m": 3000},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["course_id"] == course_id
    assert body[0]["place_count"] == 1
    assert body[0]["total_distance_meters"] == 300
    assert body[0]["total_duration_minutes"] == 20


def test_get_nearby_courses_excludes_private_courses(client, session_factory):
    _seed_nearby_course(session_factory, is_shared=False)

    response = client.get("/api/courses", params={"lat": 37.5, "lng": 127.0})

    assert response.status_code == 200
    assert response.json() == []


def test_get_nearby_courses_marks_is_owner_when_authenticated(client, session_factory):
    _seed_nearby_course(session_factory, dog_id=1)

    response = client.get(
        "/api/courses", params={"lat": 37.5, "lng": 127.0}, headers=_auth_headers(dog_id=1)
    )

    assert response.json()[0]["is_owner"] is True


def test_get_nearby_courses_reflects_like_and_save_counts(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1, is_shared=True)
    client.post(f"/api/courses/{course_id}/like", headers=_auth_headers(dog_id=1))
    client.post(f"/api/courses/{course_id}/save", headers=_auth_headers(dog_id=2))

    as_liker = client.get(
        "/api/courses", params={"lat": 37.5, "lng": 127.0}, headers=_auth_headers(dog_id=1)
    ).json()[0]
    as_other = client.get(
        "/api/courses", params={"lat": 37.5, "lng": 127.0}, headers=_auth_headers(dog_id=2)
    ).json()[0]

    assert as_liker["like_count"] == 1
    assert as_liker["is_liked"] is True
    assert as_liker["save_count"] == 1
    assert as_liker["is_saved"] is False

    assert as_other["is_liked"] is False
    assert as_other["is_saved"] is True


def test_get_course_detail_returns_404_when_missing(client):
    response = client.get("/api/courses/999")
    assert response.status_code == 404


def test_get_course_detail_returns_404_for_private_course_and_non_owner(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1, is_shared=False)

    anonymous_response = client.get(f"/api/courses/{course_id}")
    other_response = client.get(
        f"/api/courses/{course_id}", headers=_auth_headers(dog_id=2)
    )

    assert anonymous_response.status_code == 404
    assert other_response.status_code == 404


def test_get_course_detail_allows_owner_for_private_course(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1, is_shared=False)

    response = client.get(f"/api/courses/{course_id}", headers=_auth_headers(dog_id=1))

    assert response.status_code == 200
    body = response.json()
    assert body["is_owner"] is True
    assert body["is_shared"] is False


def test_get_course_detail_allows_anyone_for_shared_course(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1, is_shared=True)

    response = client.get(f"/api/courses/{course_id}", headers=_auth_headers(dog_id=2))

    assert response.status_code == 200
    body = response.json()
    assert body["is_owner"] is False
    assert body["is_shared"] is True


def test_get_course_detail_reflects_like_and_save_counts(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1, is_shared=True)
    client.post(f"/api/courses/{course_id}/like", headers=_auth_headers(dog_id=2))

    response = client.get(f"/api/courses/{course_id}", headers=_auth_headers(dog_id=2))

    body = response.json()
    assert body["like_count"] == 1
    assert body["is_liked"] is True
    assert body["save_count"] == 0
    assert body["is_saved"] is False


def test_create_course_has_zero_engagement(client, monkeypatch):
    async def fake_create_walking_course(*args, **kwargs):
        return _fixed_result()

    monkeypatch.setattr(courses_service, "create_walking_course", fake_create_walking_course)

    response = client.post("/api/courses", json=_request_body(), headers=_auth_headers())

    body = response.json()
    assert body["like_count"] == 0
    assert body["is_liked"] is False
    assert body["save_count"] == 0
    assert body["is_saved"] is False


def _places_replace_body(place_id: int) -> dict:
    """places는 코스 생성/조회 응답(CoursePlaceRead)과 동일한 형식이다 — 프론트가 이미
    받은 응답 객체를 그대로 재사용해서 넘긴다고 가정한 형태."""
    return {
        "places": [
            {
                "place_id": place_id,
                "name": "공원",
                "category": "PARK",
                "image_url": None,
                "lat": 37.5,
                "lng": 127.0,
                "sequence": 1,
                "stay_minutes": 20,
                "travel_minutes": 8,
                "travel_distance_meters": 450,
            }
        ],
        "path": [[37.5, 127.0], [37.501, 127.0]],
    }


def test_replace_course_places_requires_auth(client, session_factory):
    course_id = _seed_nearby_course(session_factory)

    response = client.put(f"/api/courses/{course_id}/places", json=_places_replace_body(1))

    assert response.status_code == 401


def test_replace_course_places_rejects_non_owner(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1)

    response = client.put(
        f"/api/courses/{course_id}/places",
        json=_places_replace_body(1),
        headers=_auth_headers(dog_id=2),
    )

    assert response.status_code == 403


def test_replace_course_places_returns_404_when_missing(client):
    response = client.put(
        "/api/courses/999/places", json=_places_replace_body(1), headers=_auth_headers(dog_id=1)
    )
    assert response.status_code == 404


def test_replace_course_places_saves_frontend_recalculated_values(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1)
    db = session_factory()
    place_id = db.scalars(select(Place)).first().place_id
    db.close()

    response = client.put(
        f"/api/courses/{course_id}/places",
        json=_places_replace_body(place_id),
        headers=_auth_headers(dog_id=1),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["places"]) == 1
    assert body["places"][0]["place_id"] == place_id
    assert body["places"][0]["stay_minutes"] == 20
    assert body["places"][0]["travel_minutes"] == 8
    assert body["places"][0]["travel_distance_meters"] == 450
    assert body["total_distance_meters"] == 450
    assert body["total_duration_minutes"] == 28
    assert body["path"] == [[37.5, 127.0], [37.501, 127.0]]


def test_replace_course_places_removes_a_place(client, session_factory):
    park = Place(
        content_id="park-1", name="공원", category=PlaceCategory.PARK, latitude=37.5, longitude=127.0
    )
    cafe = Place(
        content_id="cafe-1", name="카페", category=PlaceCategory.CAFE, latitude=37.5, longitude=127.0
    )
    db = session_factory()
    db.add_all([park, cafe])
    db.flush()
    course = Course(title="코스", start_lat=37.5, start_lng=127.0, dog_id=1)
    db.add(course)
    db.flush()
    db.add_all(
        [
            CoursePlace(
                course_id=course.course_id,
                place_id=park.place_id,
                sequence=1,
                stay_minutes=15,
                travel_minutes=5,
                travel_distance_meters=300,
            ),
            CoursePlace(
                course_id=course.course_id,
                place_id=cafe.place_id,
                sequence=2,
                stay_minutes=20,
                travel_minutes=10,
                travel_distance_meters=400,
            ),
        ]
    )
    db.commit()
    course_id = course.course_id
    park_id = park.place_id
    db.close()

    # 카페(2번째 스팟)를 프론트에서 삭제하고 남은 공원만으로 재계산해서 넘긴 상황
    response = client.put(
        f"/api/courses/{course_id}/places",
        json=_places_replace_body(park_id),
        headers=_auth_headers(dog_id=1),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["places"]) == 1
    assert body["places"][0]["place_id"] == park_id


def test_replace_course_places_creates_log_with_ended_at(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1)
    db = session_factory()
    place_id = db.scalars(select(Place)).first().place_id
    db.close()

    body = _places_replace_body(place_id)
    body["ended_at"] = "2026-09-20T11:30:00+09:00"

    response = client.put(
        f"/api/courses/{course_id}/places", json=body, headers=_auth_headers(dog_id=1)
    )

    assert response.status_code == 200

    logs = client.get("/api/logs", headers=_auth_headers(dog_id=1)).json()
    assert len(logs) == 1
    assert logs[0]["course_id"] == course_id
    assert logs[0]["ended_at"].startswith("2026-09-20T11:30:00")


def test_replace_course_places_without_ended_at_creates_log_without_it(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1)
    db = session_factory()
    place_id = db.scalars(select(Place)).first().place_id
    db.close()

    response = client.put(
        f"/api/courses/{course_id}/places",
        json=_places_replace_body(place_id),
        headers=_auth_headers(dog_id=1),
    )

    assert response.status_code == 200

    logs = client.get("/api/logs", headers=_auth_headers(dog_id=1)).json()
    assert len(logs) == 1
    assert logs[0]["ended_at"] is None
    assert logs[0]["started_at"] is not None


def test_replacing_places_again_does_not_duplicate_the_walk_log(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1)
    db = session_factory()
    place_id = db.scalars(select(Place)).first().place_id
    db.close()

    body = _places_replace_body(place_id)
    body["ended_at"] = "2026-09-20T11:30:00+09:00"
    for _ in range(2):
        response = client.put(
            f"/api/courses/{course_id}/places", json=body, headers=_auth_headers(dog_id=1)
        )
        assert response.status_code == 200

    logs = client.get("/api/logs", headers=_auth_headers(dog_id=1)).json()
    assert len(logs) == 1
    assert logs[0]["course_id"] == course_id


def test_share_course_requires_auth(client, session_factory):
    course_id = _seed_nearby_course(session_factory, is_shared=False)

    response = client.post(f"/api/courses/{course_id}/share")

    assert response.status_code == 401


def test_share_course_rejects_non_owner(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1, is_shared=False)

    response = client.post(
        f"/api/courses/{course_id}/share", headers=_auth_headers(dog_id=2)
    )

    assert response.status_code == 403


def test_share_course_returns_404_when_missing(client):
    response = client.post("/api/courses/999/share", headers=_auth_headers(dog_id=1))
    assert response.status_code == 404


def test_share_course_marks_course_shared_for_owner(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1, is_shared=False)

    response = client.post(
        f"/api/courses/{course_id}/share", headers=_auth_headers(dog_id=1)
    )

    assert response.status_code == 200
    assert response.json()["is_shared"] is True

    # 공유된 코스는 이제 주변 코스 목록에서도 보여야 한다.
    listed = client.get("/api/courses", params={"lat": 37.5, "lng": 127.0})
    assert [c["course_id"] for c in listed.json()] == [course_id]


def test_update_course_requires_auth(client, session_factory):
    course_id = _seed_nearby_course(session_factory)

    response = client.patch(f"/api/courses/{course_id}", json={"title": "새 제목"})

    assert response.status_code == 401


def test_update_course_rejects_non_owner(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1)

    response = client.patch(
        f"/api/courses/{course_id}",
        json={"title": "새 제목"},
        headers=_auth_headers(dog_id=2),
    )

    assert response.status_code == 403


def test_update_course_returns_404_when_missing(client):
    response = client.patch(
        "/api/courses/999", json={"title": "새 제목"}, headers=_auth_headers(dog_id=1)
    )
    assert response.status_code == 404


def test_update_course_changes_title_for_owner(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1)

    response = client.patch(
        f"/api/courses/{course_id}",
        json={"title": "새 제목"},
        headers=_auth_headers(dog_id=1),
    )

    assert response.status_code == 200
    assert response.json()["title"] == "새 제목"

    follow_up = client.get(f"/api/courses/{course_id}", headers=_auth_headers(dog_id=1))
    assert follow_up.json()["title"] == "새 제목"


def test_update_course_without_fields_keeps_title_unchanged(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1)

    response = client.patch(
        f"/api/courses/{course_id}", json={}, headers=_auth_headers(dog_id=1)
    )

    assert response.status_code == 200
    assert response.json()["title"] == "코스"


def test_delete_course_requires_auth(client, session_factory):
    course_id = _seed_nearby_course(session_factory)

    response = client.delete(f"/api/courses/{course_id}")

    assert response.status_code == 401


def test_delete_course_rejects_non_owner(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1)

    response = client.delete(f"/api/courses/{course_id}", headers=_auth_headers(dog_id=2))

    assert response.status_code == 403


def test_delete_course_returns_404_when_missing(client):
    response = client.delete("/api/courses/999", headers=_auth_headers(dog_id=1))
    assert response.status_code == 404


def test_delete_course_removes_course_for_owner(client, session_factory):
    course_id = _seed_nearby_course(session_factory, dog_id=1)

    response = client.delete(f"/api/courses/{course_id}", headers=_auth_headers(dog_id=1))
    assert response.status_code == 204

    follow_up = client.get(f"/api/courses/{course_id}", headers=_auth_headers(dog_id=1))
    assert follow_up.status_code == 404
