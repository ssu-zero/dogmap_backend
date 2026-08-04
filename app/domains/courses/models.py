from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, CreatedAtMixin

if TYPE_CHECKING:
    from app.domains.likes.models import Like
    from app.domains.logs.models import Log
    from app.domains.places.models import Place
    from app.domains.saves.models import Save


class Course(CreatedAtMixin, Base):
    __tablename__ = "courses"

    course_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    start_lat: Mapped[str] = mapped_column(String(32), nullable=False)
    start_lng: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)

    logs: Mapped[list["Log"]] = relationship(
        "Log", back_populates="course", cascade="all, delete-orphan"
    )
    likes: Mapped[list["Like"]] = relationship(
        "Like", back_populates="course", cascade="all, delete-orphan"
    )
    saves: Mapped[list["Save"]] = relationship(
        "Save", back_populates="course", cascade="all, delete-orphan"
    )
    course_places: Mapped[list["CoursePlace"]] = relationship(
        "CoursePlace",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CoursePlace.sequence",
    )


class CoursePlace(Base):
    """Course_Place: 코스별 장소(방문 순서) 조인 테이블."""

    __tablename__ = "course_place"

    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.course_id"), primary_key=True
    )
    place_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("places.place_id"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    stay_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # TODO: 단위는 기획 확정 후 조정 (현재 travel_time=초, travel_distance=미터 가정)
    travel_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    travel_distance: Mapped[float | None] = mapped_column(Float, nullable=True)

    course: Mapped["Course"] = relationship("Course", back_populates="course_places")
    place: Mapped["Place"] = relationship("Place", back_populates="course_places")
