from app.domains.places.schemas import PlaceCandidate
from app.domains.places.service import select_random_sample


def _candidate(content_id: str, dist: float = 100.0) -> PlaceCandidate:
    return PlaceCandidate(
        content_id=content_id,
        title=f"장소{content_id}",
        category="산책",
        address="서울",
        lat=37.5,
        lng=127.1,
        dist=dist,
    )


def test_returns_all_candidates_when_not_more_than_k():
    candidates = [_candidate("1", 100), _candidate("2", 200)]

    result = select_random_sample(candidates, 5)

    assert result == candidates


def test_selects_exactly_k_candidates():
    candidates = [_candidate(str(i), dist=i * 100) for i in range(1, 11)]

    result = select_random_sample(candidates, 4)

    assert len(result) == 4


def test_selects_without_duplicates():
    candidates = [_candidate(str(i), dist=i * 100) for i in range(1, 11)]

    result = select_random_sample(candidates, 6)

    ids = [c.content_id for c in result]
    assert len(ids) == len(set(ids))


def test_result_is_not_always_identical_across_calls():
    candidates = [_candidate(str(i)) for i in range(1, 11)]

    outcomes = {
        tuple(sorted(c.content_id for c in select_random_sample(candidates, 3))) for _ in range(30)
    }

    assert len(outcomes) > 1
