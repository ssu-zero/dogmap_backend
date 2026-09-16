import json

import httpx
import pytest

from app.domains.places.external.tmap_client import TmapApiError, TmapClient


def _feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def _point(lng: float, lat: float, point_type: str, extra: dict | None = None) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {"pointType": point_type, **(extra or {})},
    }


def _line(coords: list[list[float]], distance: float, time: float) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {"distance": distance, "time": time},
    }


def _make_client(handler) -> TmapClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="https://apis.openapi.sk.com")
    return TmapClient(app_key="test-key", http_client=http_client)


async def test_pedestrian_route_without_waypoints_returns_single_segment():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_feature_collection(
                [
                    _point(127.0, 37.5, "SP", {"totalDistance": 300, "totalTime": 240}),
                    _line([[127.0, 37.5], [127.01, 37.51]], distance=300, time=240),
                    _point(127.01, 37.51, "EP"),
                ]
            ),
        )

    client = _make_client(handler)
    try:
        route = await client.pedestrian_route(
            start_lat=37.5, start_lng=127.0, end_lat=37.51, end_lng=127.01
        )
    finally:
        await client.aclose()

    assert route.distance_meters == 300
    assert route.duration_minutes == 4  # 240초 = 4분
    assert route.path[0] == (37.5, 127.0)
    assert route.path[-1] == (37.51, 127.01)
    assert len(route.segments) == 1
    assert route.segments[0].distance_meters == 300


async def test_pedestrian_route_with_waypoints_splits_segments_by_marker():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_feature_collection(
                [
                    _point(127.0, 37.5, "SP", {"totalDistance": 300, "totalTime": 180}),
                    _line([[127.0, 37.5], [127.005, 37.505]], distance=100, time=60),
                    _point(127.005, 37.505, "PP1"),
                    _line([[127.005, 37.505], [127.01, 37.51]], distance=200, time=120),
                    _point(127.01, 37.51, "EP"),
                ]
            ),
        )

    client = _make_client(handler)
    try:
        route = await client.pedestrian_route(
            start_lat=37.5,
            start_lng=127.0,
            end_lat=37.51,
            end_lng=127.01,
            waypoints=[(37.505, 127.005)],
        )
    finally:
        await client.aclose()

    assert route.distance_meters == 300
    assert len(route.segments) == 2
    assert route.segments[0].distance_meters == 100
    assert route.segments[0].duration_minutes == 1
    assert route.segments[1].distance_meters == 200
    assert route.segments[1].duration_minutes == 2


async def test_pedestrian_route_sends_passlist_for_waypoints():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(
            200,
            json=_feature_collection(
                [
                    _point(127.0, 37.5, "SP"),
                    _line([[127.0, 37.5], [127.01, 37.51]], distance=100, time=60),
                    _point(127.01, 37.51, "EP"),
                ]
            ),
        )

    client = _make_client(handler)
    try:
        await client.pedestrian_route(
            start_lat=37.5,
            start_lng=127.0,
            end_lat=37.52,
            end_lng=127.02,
            waypoints=[(37.505, 127.005), (37.51, 127.01)],
        )
    finally:
        await client.aclose()

    body = json.loads(captured["body"])
    assert body["passList"] == "127.005,37.505_127.01,37.51"


async def test_pedestrian_route_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = _make_client(handler)
    try:
        with pytest.raises(TmapApiError):
            await client.pedestrian_route(
                start_lat=37.5, start_lng=127.0, end_lat=37.51, end_lng=127.01
            )
    finally:
        await client.aclose()


async def test_pedestrian_route_raises_when_no_features():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"type": "FeatureCollection", "features": []})

    client = _make_client(handler)
    try:
        with pytest.raises(TmapApiError):
            await client.pedestrian_route(
                start_lat=37.5, start_lng=127.0, end_lat=37.51, end_lng=127.01
            )
    finally:
        await client.aclose()
