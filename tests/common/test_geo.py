from app.common.geo import bounding_box, haversine_distance_m


def test_haversine_distance_is_zero_for_same_point():
    assert haversine_distance_m(37.5, 127.0, 37.5, 127.0) == 0


def test_haversine_distance_is_symmetric():
    a = haversine_distance_m(37.5, 127.0, 37.51, 127.01)
    b = haversine_distance_m(37.51, 127.01, 37.5, 127.0)
    assert a == b
    assert a > 0


def test_haversine_distance_known_1_degree_latitude_is_about_111km():
    distance = haversine_distance_m(37.0, 127.0, 38.0, 127.0)
    assert 110_000 < distance < 112_000


def test_bounding_box_contains_points_within_radius():
    lat, lng, radius_m = 37.5, 127.0, 3000
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_m)

    # 반경 안쪽으로 살짝 들어온 점은 박스 안에 있어야 한다
    near_lat = lat + (radius_m * 0.9) / 111320.0
    assert min_lat < near_lat < max_lat
    assert min_lng < lng < max_lng


def test_bounding_box_excludes_points_far_outside_radius():
    lat, lng, radius_m = 37.5, 127.0, 1000
    min_lat, max_lat, _, _ = bounding_box(lat, lng, radius_m)

    far_lat = lat + 1.0  # 약 111km 떨어진 위도
    assert not (min_lat < far_lat < max_lat)
