from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.common.base_model import Base
from app.common.exceptions import NotFoundError
from app.domains.courses import service as courses_service
from app.domains.courses.models import Course, CoursePlace
from app.domains.courses.schemas import CategoryTarget, CourseCategory, CourseCreateRequest
from app.domains.courses.service import NotCourseOwnerError
from app.domains.places.constants import DEFAULT_STAY_MINUTES
from app.domains.places.models import Place, PlaceCategory
from app.domains.places.schemas import PlaceCandidate, WalkingCourseLeg, WalkingCourseResult


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def _stop(content_id: str, title: str, category: str = "산책") -> PlaceCandidate:
    return PlaceCandidate(
        content_id=content_id,
        title=title,
        category=category,
        address="서울",
        lat=37.51,
        lng=127.01,
        dist=0.0,
    )


def _fixed_result() -> WalkingCourseResult:
    stops = [_stop("1", "공원"), _stop("2", "카페", category="카페")]
    legs = [
        WalkingCourseLeg(from_title="출발", to_title="공원", distance_meters=100.4, duration_minutes=1.6),
        WalkingCourseLeg(from_title="공원", to_title="카페", distance_meters=200.6, duration_minutes=3.4),
    ]
    return WalkingCourseResult(
        stops=stops,
        legs=legs,
        total_distance_meters=301.0,
        total_duration_minutes=5.0,
        path=[(37.5, 127.0), (37.51, 127.01), (37.52, 127.02)],
        generation_duration_ms=1234,
    )


def _request() -> CourseCreateRequest:
    return CourseCreateRequest(
        start_lat=37.5,
        start_lng=127.0,
        target_duration_minutes=60,
        category_targets=[
            CategoryTarget(category=CourseCategory.WALK, count=1),
            CategoryTarget(category=CourseCategory.CAFE, count=1),
        ],
        walk_date=datetime(2026, 9, 20, 10, 0, tzinfo=UTC),
    )


async def test_creates_course_and_course_places_in_order(session, monkeypatch):
    async def fake_create_walking_course(*args, **kwargs):
        return _fixed_result()

    monkeypatch.setattr(courses_service, "create_walking_course", fake_create_walking_course)

    course, course_places, result = await courses_service.create_course_with_places(
        session, _request(), dog_id=1
    )

    assert course.course_id is not None
    assert course.title == "60분 산책 코스"
    assert course.start_lat == 37.5
    assert course.start_lng == 127.0
    assert course.dog_id == 1
    assert course.is_shared is False
    assert course.path == [[37.5, 127.0], [37.51, 127.01], [37.52, 127.02]]
    assert result.total_distance_meters == 301.0
    assert result.total_duration_minutes == 5.0

    ordered = sorted(course_places, key=lambda cp: cp.sequence)
    assert [cp.sequence for cp in ordered] == [1, 2]
    assert ordered[0].stay_minutes == DEFAULT_STAY_MINUTES
    assert ordered[0].travel_minutes == 2  # round(1.6)
    assert ordered[0].travel_distance_meters == 100  # round(100.4)
    assert ordered[1].travel_minutes == 3  # round(3.4)
    assert ordered[1].travel_distance_meters == 201  # round(200.6)

    places = session.scalars(select(Place)).all()
    assert {p.content_id for p in places} == {"1", "2"}


async def test_reuses_existing_place_across_course_creations(session, monkeypatch):
    async def fake_create_walking_course(*args, **kwargs):
        return _fixed_result()

    monkeypatch.setattr(courses_service, "create_walking_course", fake_create_walking_course)

    await courses_service.create_course_with_places(session, _request(), dog_id=1)
    await courses_service.create_course_with_places(session, _request(), dog_id=1)

    places = session.scalars(select(Place)).all()
    assert len(places) == 2  # 같은 content_id 재사용, 중복 생성 없음


async def test_uses_explicit_title_when_provided(session, monkeypatch):
    async def fake_create_walking_course(*args, **kwargs):
        return _fixed_result()

    monkeypatch.setattr(courses_service, "create_walking_course", fake_create_walking_course)

    request = _request()
    request.title = "우리 동네 산책"
    course, _, _ = await courses_service.create_course_with_places(session, request, dog_id=1)

    assert course.title == "우리 동네 산책"


def _seed_place(session, content_id: str, name: str = "장소", image_url: str | None = None) -> Place:
    place = Place(
        content_id=content_id,
        name=name,
        category=PlaceCategory.PARK,
        image_url=image_url,
        latitude=37.5,
        longitude=127.0,
    )
    session.add(place)
    session.flush()
    return place


def _seed_course(
    session,
    *,
    title: str,
    start_lat: float,
    start_lng: float,
    course_places: list[tuple],
    dog_id: int | None = 1,
    is_shared: bool = True,
) -> Course:
    """course_places: (place, stay_minutes, travel_minutes, travel_distance_meters) 목록.

    is_shared 기본값을 True로 둔 이유: list_nearby_courses는 공개 코스만 보여주므로,
    비공개 관련 테스트가 아닌 이상 대부분의 기존 테스트는 공개 코스를 시딩해야 한다.
    """
    course = Course(
        title=title, start_lat=start_lat, start_lng=start_lng, dog_id=dog_id, is_shared=is_shared
    )
    session.add(course)
    session.flush()
    for i, (place, stay, travel_min, travel_dist) in enumerate(course_places, start=1):
        session.add(
            CoursePlace(
                course_id=course.course_id,
                place_id=place.place_id,
                sequence=i,
                stay_minutes=stay,
                travel_minutes=travel_min,
                travel_distance_meters=travel_dist,
            )
        )
    session.commit()
    return course


def test_list_nearby_courses_excludes_courses_outside_radius(session):
    place = _seed_place(session, "1")
    near = _seed_course(
        session, title="근처 코스", start_lat=37.501, start_lng=127.0, course_places=[(place, 15, 5, 300)]
    )
    _seed_course(
        session, title="먼 코스", start_lat=38.5, start_lng=127.0, course_places=[(place, 15, 5, 300)]
    )

    result = courses_service.list_nearby_courses(
        session, lat=37.5, lng=127.0, radius_m=3000, limit=20, offset=0
    )

    assert [c.course_id for c in result] == [near.course_id]


def test_list_nearby_courses_sorts_by_distance_ascending(session):
    place = _seed_place(session, "1")
    far = _seed_course(
        session, title="조금 먼 코스", start_lat=37.52, start_lng=127.0, course_places=[(place, 15, 5, 300)]
    )
    near = _seed_course(
        session, title="가까운 코스", start_lat=37.501, start_lng=127.0, course_places=[(place, 15, 5, 300)]
    )

    result = courses_service.list_nearby_courses(
        session, lat=37.5, lng=127.0, radius_m=10000, limit=20, offset=0
    )

    assert [c.course_id for c in result] == [near.course_id, far.course_id]
    assert result[0].distance_meters < result[1].distance_meters


def test_list_nearby_courses_aggregates_totals_and_thumbnail(session):
    park = _seed_place(session, "1", name="공원", image_url="park.jpg")
    cafe = _seed_place(session, "2", name="카페", image_url="cafe.jpg")
    course = _seed_course(
        session,
        title="코스",
        start_lat=37.501,
        start_lng=127.0,
        course_places=[(park, 15, 5, 300), (cafe, 20, 10, 400)],
    )

    result = courses_service.list_nearby_courses(
        session, lat=37.5, lng=127.0, radius_m=10000, limit=20, offset=0
    )

    summary = next(c for c in result if c.course_id == course.course_id)
    assert summary.place_count == 2
    assert summary.total_distance_meters == 700  # 300 + 400
    assert summary.total_duration_minutes == 50  # (15+5) + (20+10)
    assert summary.thumbnail_image_url == "park.jpg"  # sequence=1 장소


def test_list_nearby_courses_paginates_with_limit_and_offset(session):
    place = _seed_place(session, "1")
    lats = [37.501, 37.502, 37.503]
    courses = [
        _seed_course(
            session, title=f"코스{i}", start_lat=lat, start_lng=127.0, course_places=[(place, 15, 5, 300)]
        )
        for i, lat in enumerate(lats)
    ]

    page = courses_service.list_nearby_courses(
        session, lat=37.5, lng=127.0, radius_m=10000, limit=1, offset=1
    )

    assert [c.course_id for c in page] == [courses[1].course_id]


def test_list_nearby_courses_excludes_private_courses(session):
    place = _seed_place(session, "1")
    _seed_course(
        session,
        title="비공개 코스",
        start_lat=37.501,
        start_lng=127.0,
        course_places=[(place, 15, 5, 300)],
        is_shared=False,
    )

    result = courses_service.list_nearby_courses(
        session, lat=37.5, lng=127.0, radius_m=10000, limit=20, offset=0
    )

    assert result == []


def test_list_nearby_courses_marks_is_owner_for_requester(session):
    place = _seed_place(session, "1")
    course = _seed_course(
        session,
        title="코스",
        start_lat=37.501,
        start_lng=127.0,
        course_places=[(place, 15, 5, 300)],
        dog_id=1,
    )

    result = courses_service.list_nearby_courses(
        session, lat=37.5, lng=127.0, radius_m=10000, limit=20, offset=0, requester_dog_id=1
    )
    other = courses_service.list_nearby_courses(
        session, lat=37.5, lng=127.0, radius_m=10000, limit=20, offset=0, requester_dog_id=2
    )

    assert next(c for c in result if c.course_id == course.course_id).is_owner is True
    assert next(c for c in other if c.course_id == course.course_id).is_owner is False


def test_get_course_detail_returns_none_for_private_course_and_non_owner(session):
    place = _seed_place(session, "1")
    course = _seed_course(
        session,
        title="비공개 코스",
        start_lat=37.5,
        start_lng=127.0,
        course_places=[(place, 15, 5, 300)],
        dog_id=1,
        is_shared=False,
    )

    assert courses_service.get_course_detail(session, course.course_id, None) is None
    assert courses_service.get_course_detail(session, course.course_id, 2) is None

    detail = courses_service.get_course_detail(session, course.course_id, 1)
    assert detail is not None
    assert detail[2] is True  # is_owner


def test_get_course_detail_returns_none_for_missing_course(session):
    assert courses_service.get_course_detail(session, 999, None) is None


def test_get_course_detail_allows_anyone_for_shared_course(session):
    place = _seed_place(session, "1")
    course = _seed_course(
        session,
        title="공개 코스",
        start_lat=37.5,
        start_lng=127.0,
        course_places=[(place, 15, 5, 300)],
        dog_id=1,
        is_shared=True,
    )

    detail = courses_service.get_course_detail(session, course.course_id, None)
    assert detail is not None
    assert detail[2] is False  # is_owner


def test_share_course_sets_is_shared_for_owner(session):
    place = _seed_place(session, "1")
    course = _seed_course(
        session,
        title="코스",
        start_lat=37.5,
        start_lng=127.0,
        course_places=[(place, 15, 5, 300)],
        dog_id=1,
        is_shared=False,
    )

    updated = courses_service.share_course(session, course.course_id, 1)

    assert updated.is_shared is True


def test_share_course_raises_for_non_owner(session):
    place = _seed_place(session, "1")
    course = _seed_course(
        session,
        title="코스",
        start_lat=37.5,
        start_lng=127.0,
        course_places=[(place, 15, 5, 300)],
        dog_id=1,
        is_shared=False,
    )

    with pytest.raises(NotCourseOwnerError):
        courses_service.share_course(session, course.course_id, 2)


def test_share_course_raises_not_found_for_missing_course(session):
    with pytest.raises(NotFoundError):
        courses_service.share_course(session, 999, 1)


def test_delete_course_by_id_removes_course_for_owner(session):
    place = _seed_place(session, "1")
    course = _seed_course(
        session,
        title="코스",
        start_lat=37.5,
        start_lng=127.0,
        course_places=[(place, 15, 5, 300)],
        dog_id=1,
    )

    courses_service.delete_course_by_id(session, course.course_id, 1)

    assert session.get(Course, course.course_id) is None


def test_delete_course_by_id_raises_for_non_owner(session):
    place = _seed_place(session, "1")
    course = _seed_course(
        session,
        title="코스",
        start_lat=37.5,
        start_lng=127.0,
        course_places=[(place, 15, 5, 300)],
        dog_id=1,
    )

    with pytest.raises(NotCourseOwnerError):
        courses_service.delete_course_by_id(session, course.course_id, 2)

    assert session.get(Course, course.course_id) is not None


def test_delete_course_by_id_raises_not_found_for_missing_course(session):
    with pytest.raises(NotFoundError):
        courses_service.delete_course_by_id(session, 999, 1)
