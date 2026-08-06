import pytest

from app.domains.places.external.tmap_client import PedestrianRoute, RouteSegment, TmapApiError
from app.domains.places.schemas import PlaceCandidate
from app.domains.places.service import build_walking_course


class _FakeTmapClient:
    def __init__(self):
        self.calls: list[dict] = []
        self.closed = False

    async def pedestrian_route(
        self, *, start_lat, start_lng, end_lat, end_lng, waypoints=None, start_name="출발", end_name="도착"
    ):
        self.calls.append(
            {
                "start": (start_lat, start_lng),
                "end": (end_lat, end_lng),
                "waypoints": waypoints or [],
            }
        )
        num_legs = len(waypoints or []) + 1
        return PedestrianRoute(
            distance_meters=100.0 * num_legs,
            duration_minutes=2.0 * num_legs,
            path=[(start_lat, start_lng), (end_lat, end_lng)],
            segments=[RouteSegment(distance_meters=100.0, duration_minutes=2.0) for _ in range(num_legs)],
        )

    async def aclose(self):
        self.closed = True


def _stop(content_id: str, title: str, lat: float, lng: float) -> PlaceCandidate:
    return PlaceCandidate(
        content_id=content_id, title=title, category="산책", address="서울", lat=lat, lng=lng, dist=0.0
    )


async def test_build_walking_course_calls_tmap_once_with_all_waypoints():
    stops = [
        _stop("1", "공원", 37.51, 127.01),
        _stop("2", "카페", 37.52, 127.02),
    ]
    client = _FakeTmapClient()

    result = await build_walking_course(stops, 37.5, 127.0, client=client)

    assert len(client.calls) == 1  # 구간마다 나눠 부르지 않고 한 번만 호출
    call = client.calls[0]
    assert call["start"] == (37.5, 127.0)
    assert call["end"] == (37.52, 127.02)  # 마지막 stop이 도착지
    assert call["waypoints"] == [(37.51, 127.01)]  # 마지막을 제외한 stop들이 경유지

    assert len(result.legs) == 2
    assert result.legs[0].from_title == "출발"
    assert result.legs[0].to_title == "공원"
    assert result.legs[1].from_title == "공원"
    assert result.legs[1].to_title == "카페"
    assert result.total_distance_meters == 200.0
    assert result.total_duration_minutes == 4.0
    assert result.stops == stops
    # 외부에서 주입한 client는 서비스가 닫지 않는다
    assert client.closed is False


async def test_build_walking_course_single_stop_has_no_waypoints():
    stops = [_stop("1", "공원", 37.51, 127.01)]
    client = _FakeTmapClient()

    result = await build_walking_course(stops, 37.5, 127.0, client=client)

    assert client.calls[0]["waypoints"] == []
    assert len(result.legs) == 1


async def test_build_walking_course_raises_when_no_stops():
    with pytest.raises(TmapApiError):
        await build_walking_course([], 37.5, 127.0, client=_FakeTmapClient())


async def test_build_walking_course_raises_when_segment_count_mismatches_stops():
    class _MismatchedClient(_FakeTmapClient):
        async def pedestrian_route(self, **kwargs):
            route = await super().pedestrian_route(**kwargs)
            return PedestrianRoute(
                distance_meters=route.distance_meters,
                duration_minutes=route.duration_minutes,
                path=route.path,
                segments=route.segments[:-1],  # 일부러 구간 하나 누락
            )

    stops = [_stop("1", "공원", 37.51, 127.01), _stop("2", "카페", 37.52, 127.02)]

    with pytest.raises(TmapApiError):
        await build_walking_course(stops, 37.5, 127.0, client=_MismatchedClient())
