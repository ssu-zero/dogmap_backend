import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.common.base_model import Base
from app.domains.places.models import Place, PlaceCategory
from app.domains.places.repository import get_or_create_places
from app.domains.places.schemas import PlaceCandidate


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def _candidate(content_id: str, title: str = "공원", category: str = "산책") -> PlaceCandidate:
    return PlaceCandidate(
        content_id=content_id,
        title=title,
        category=category,
        address="서울",
        lat=37.5,
        lng=127.0,
        dist=0.0,
    )


def test_creates_new_place_for_unseen_content_id(session):
    result = get_or_create_places(session, [_candidate("1")])

    assert set(result.keys()) == {"1"}
    assert result["1"].category == PlaceCategory.PARK  # 산책 -> PARK 매핑
    assert session.scalars(select(Place)).all()[0].content_id == "1"


def test_reuses_existing_place_by_content_id(session):
    first = get_or_create_places(session, [_candidate("1")])
    session.commit()

    second = get_or_create_places(session, [_candidate("1")])

    assert second["1"].place_id == first["1"].place_id
    assert len(session.scalars(select(Place)).all()) == 1


def test_mixes_existing_and_new_content_ids(session):
    get_or_create_places(session, [_candidate("1")])
    session.commit()

    result = get_or_create_places(session, [_candidate("1"), _candidate("2", title="카페", category="카페")])

    assert set(result.keys()) == {"1", "2"}
    assert len(session.scalars(select(Place)).all()) == 2
