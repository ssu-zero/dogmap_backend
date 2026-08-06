"""T맵(SK Open API) 보행자 경로안내 API 호출 클라이언트.

실제 TMAP_APP_KEY로 호출해서 검증 완료:
  - 엔드포인트: POST /tmap/routes/pedestrian?version=1, 요청은 JSON body
  - 요청 필드명: startX/startY/endX/endY/startName/endName/reqCoordType/resCoordType/searchOption
  - 응답은 GeoJSON FeatureCollection. 시작 Point(pointType="SP")의 properties에
    totalDistance/totalTime(초)이 들어있고, 이는 모든 LineString 구간의 distance/time
    합과 정확히 일치한다.
  - 다중 경유지는 passList="lng1,lat1_lng2,lat2_..." (언더스코어 구분)로 한 번의 호출에
    다 넣을 수 있다. 이때 각 경유지를 통과하는 지점이 Point.properties.pointType에
    "PP1", "PP2", ... 순서로 표시되고(시작은 "SP", 끝은 "EP"), 이 마커들 사이의 누적
    거리/시간 차이로 구간(레그)별 거리/시간을 정확히 분리할 수 있다 (직접 호출해서 검증함).
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.common.exceptions import ExternalApiError
from app.core.config import settings

_DEFAULT_TIMEOUT = 10.0
_ROUTE_MARKER_PREFIXES = ("SP", "EP", "PP")


class TmapApiError(ExternalApiError):
    pass


@dataclass
class RouteSegment:
    """경유지 마커(SP/PPn/EP) 사이 한 구간의 거리/시간."""

    distance_meters: float
    duration_minutes: float


@dataclass
class PedestrianRoute:
    distance_meters: float
    duration_minutes: float
    path: list[tuple[float, float]]  # (lat, lng) 순서의 전체 폴리라인
    segments: list[RouteSegment]  # SP->PP1, PP1->PP2, ..., PPn->EP 순서


class TmapClient:
    def __init__(
        self,
        app_key: str | None = None,
        base_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ):
        self._app_key = app_key if app_key is not None else settings.TMAP_APP_KEY
        base_url = base_url or settings.TMAP_BASE_URL
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def __aenter__(self) -> "TmapClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def pedestrian_route(
        self,
        *,
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
        waypoints: list[tuple[float, float]] | None = None,
        start_name: str = "출발",
        end_name: str = "도착",
    ) -> PedestrianRoute:
        """출발지 → (경유지들) → 도착지 보행자 경로를 한 번의 호출로 계산한다.

        waypoints: 방문 순서대로의 (lat, lng) 목록. 도착지는 end_lat/end_lng로 따로 넘긴다.
        """
        body: dict[str, Any] = {
            "startX": str(start_lng),
            "startY": str(start_lat),
            "endX": str(end_lng),
            "endY": str(end_lat),
            "startName": start_name,
            "endName": end_name,
            "reqCoordType": "WGS84GEO",
            "resCoordType": "WGS84GEO",
            "searchOption": "0",
        }
        if waypoints:
            body["passList"] = "_".join(f"{lng},{lat}" for lat, lng in waypoints)

        try:
            response = await self._client.post(
                "/tmap/routes/pedestrian",
                params={"version": "1"},
                headers={"appKey": self._app_key, "Content-Type": "application/json"},
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise TmapApiError(f"T맵 보행자 경로 API 호출 실패: {exc}") from exc

        return self._parse_pedestrian_response(payload)

    def _parse_pedestrian_response(self, payload: dict[str, Any]) -> PedestrianRoute:
        features = payload.get("features")
        if not features:
            raise TmapApiError(f"T맵 응답에 features가 없습니다: {payload}")

        running_distance = 0.0
        running_time = 0.0
        markers: list[tuple[float, float]] = []  # 각 SP/PPn/EP 지점에서의 누적 (거리, 시간)
        path: list[tuple[float, float]] = []

        for feature in features:
            geometry = feature.get("geometry", {})
            properties = feature.get("properties", {})
            geom_type = geometry.get("type")
            coordinates = geometry.get("coordinates")
            if not coordinates:
                continue

            if geom_type == "Point":
                lng, lat = coordinates
                path.append((lat, lng))
                point_type = properties.get("pointType") or ""
                if point_type.startswith(_ROUTE_MARKER_PREFIXES):
                    markers.append((running_distance, running_time))
            elif geom_type == "LineString":
                running_distance += float(properties.get("distance", 0) or 0)
                running_time += float(properties.get("time", 0) or 0)
                path.extend((lat, lng) for lng, lat in coordinates)

        if not path:
            raise TmapApiError(f"T맵 응답에서 경로 좌표를 찾지 못했습니다: {payload}")
        if len(markers) < 2:
            raise TmapApiError(f"T맵 응답에서 시작/도착 지점 마커를 찾지 못했습니다: {payload}")

        segments = [
            RouteSegment(
                distance_meters=markers[i][0] - markers[i - 1][0],
                duration_minutes=(markers[i][1] - markers[i - 1][1]) / 60,
            )
            for i in range(1, len(markers))
        ]

        return PedestrianRoute(
            distance_meters=running_distance,
            duration_minutes=running_time / 60,
            path=path,
            segments=segments,
        )
