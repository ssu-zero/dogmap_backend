from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CoursePlaceBase(BaseModel):
    place_id: int
    sequence: int
    stay_minutes: int
    travel_time: int | None = None
    travel_distance: float | None = None


class CoursePlaceCreate(CoursePlaceBase):
    pass


class CoursePlaceResponse(CoursePlaceBase):
    model_config = ConfigDict(from_attributes=True)

    course_id: int


class CourseBase(BaseModel):
    title: str
    start_lat: str
    start_lng: str


class CourseCreate(CourseBase):
    places: list[CoursePlaceCreate] = []


class CourseGenerateRequest(BaseModel):
    """카카오/T맵/LLM 연동을 통한 자동 코스 생성 요청."""

    dog_id: int
    start_lat: str
    start_lng: str
    duration_minutes: int


class CourseResponse(CourseBase):
    model_config = ConfigDict(from_attributes=True)

    course_id: int
    created_at: datetime
    places: list[CoursePlaceResponse] = []
