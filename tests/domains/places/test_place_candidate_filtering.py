from app.domains.places.external.pet_tour_client import DetailPetTour
from app.domains.places.service import _is_pet_friendly, _is_valid_coordinate


def test_is_valid_coordinate():
    assert _is_valid_coordinate("127.123") is True
    assert _is_valid_coordinate("0") is False
    assert _is_valid_coordinate(None) is False
    assert _is_valid_coordinate("abc") is False


def _pet_tour(**overrides) -> DetailPetTour:
    defaults = dict(
        acmpy_type=None,
        acmpy_possible_pet="소형견",
        acmpy_need_materials=None,
        caution=None,
        facilities=None,
        etc_info=None,
    )
    defaults.update(overrides)
    return DetailPetTour(**defaults)


def test_is_pet_friendly_true_when_pet_tour_and_coordinates_valid():
    assert _is_pet_friendly(_pet_tour(), "37.5", "127.1") is True


def test_is_pet_friendly_false_without_pet_tour_detail():
    assert _is_pet_friendly(None, "37.5", "127.1") is False


def test_is_pet_friendly_false_when_pet_tour_has_no_possible_pet():
    assert _is_pet_friendly(_pet_tour(acmpy_possible_pet=None), "37.5", "127.1") is False


def test_is_pet_friendly_false_with_invalid_coordinate():
    assert _is_pet_friendly(_pet_tour(), "0", "0") is False
