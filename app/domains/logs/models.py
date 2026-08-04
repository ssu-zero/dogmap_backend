from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base

if TYPE_CHECKING:
    from app.domains.courses.models import Course
    from app.domains.dogs.models import Dog


class Log(Base):
    __tablename__ = "logs"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    start_time: Mapped[Time] = mapped_column(Time, nullable=False)
    end_time: Mapped[Time] = mapped_column(Time, nullable=False)
    diary: Mapped[str | None] = mapped_column(Text, nullable=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id"), nullable=False)
    dog_id: Mapped[int] = mapped_column(Integer, ForeignKey("dogs.dog_id"), nullable=False)

    course: Mapped["Course"] = relationship("Course", back_populates="logs")
    dog: Mapped["Dog"] = relationship("Dog", back_populates="logs")
