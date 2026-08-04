import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base

if TYPE_CHECKING:
    from app.domains.courses.models import CoursePlace


class PlaceCategory(str, enum.Enum):
    """TODO: 실제 카테고리 목록은 기획 확정 후 조정."""

    PARK = "PARK"
    CAFE = "CAFE"
    RESTAURANT = "RESTAURANT"
    HOSPITAL = "HOSPITAL"
    PET_SHOP = "PET_SHOP"
    ETC = "ETC"


class Location(Base):
    __tablename__ = "locations"

    location_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lat: Mapped[str] = mapped_column(String(32), nullable=False)
    lng: Mapped[str] = mapped_column(String(32), nullable=False)

    place: Mapped["Place"] = relationship("Place", back_populates="location", uselist=False)


class Place(Base):
    __tablename__ = "places"

    place_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[PlaceCategory] = mapped_column(Enum(PlaceCategory), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # TODO: 시간대/휴무일 표현 형식은 기획 확정 후 조정 (예: "09:00-21:00", "매주 월요일")
    open_time: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rest_day: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("locations.location_id"), nullable=False, unique=True
    )

    location: Mapped["Location"] = relationship("Location", back_populates="place")
    course_places: Mapped[list["CoursePlace"]] = relationship(
        "CoursePlace", back_populates="place", cascade="all, delete-orphan"
    )
