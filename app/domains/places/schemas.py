from pydantic import BaseModel, ConfigDict

from app.domains.places.models import PlaceCategory


class LocationBase(BaseModel):
    lat: str
    lng: str


class LocationCreate(LocationBase):
    pass


class LocationResponse(LocationBase):
    model_config = ConfigDict(from_attributes=True)

    location_id: int


class PlaceBase(BaseModel):
    name: str
    content: str | None = None
    category: PlaceCategory
    image_url: str | None = None
    open_time: str | None = None
    rest_day: str | None = None


class PlaceCreate(PlaceBase):
    location: LocationCreate


class PlaceUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    category: PlaceCategory | None = None
    image_url: str | None = None
    open_time: str | None = None
    rest_day: str | None = None


class PlaceResponse(PlaceBase):
    model_config = ConfigDict(from_attributes=True)

    place_id: int
    location: LocationResponse
