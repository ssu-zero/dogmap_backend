import math

_EARTH_RADIUS_M = 6371000.0
_LAT_DEGREE_M = 111320.0  # 위도 1도의 대략적인 거리(m)


def haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 간 직선거리(m)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bounding_box(lat: float, lng: float, radius_m: float) -> tuple[float, float, float, float]:
    """중심 좌표에서 radius_m 반경을 넉넉히 덮는 위경도 사각 범위 (min_lat, max_lat, min_lng, max_lng).

    정확한 원이 아닌 SQL 사전 필터링용이다 — 실제 반경 판정은 haversine_distance_m으로
    한 번 더 거른다. 경도 1도의 거리는 위도에 따라 달라지므로(극지방에 가까울수록 짧아짐)
    cos(lat)로 보정한다.
    """
    delta_lat = radius_m / _LAT_DEGREE_M
    lng_degree_m = max(_LAT_DEGREE_M * math.cos(math.radians(lat)), 1.0)
    delta_lng = radius_m / lng_degree_m
    return lat - delta_lat, lat + delta_lat, lng - delta_lng, lng + delta_lng
