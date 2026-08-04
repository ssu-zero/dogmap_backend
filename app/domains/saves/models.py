from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, CreatedAtMixin

if TYPE_CHECKING:
    from app.domains.courses.models import Course
    from app.domains.dogs.models import Dog


class Save(CreatedAtMixin, Base):
    __tablename__ = "saves"

    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.course_id"), primary_key=True
    )
    dog_id: Mapped[int] = mapped_column(Integer, ForeignKey("dogs.dog_id"), primary_key=True)

    course: Mapped["Course"] = relationship("Course", back_populates="saves")
    dog: Mapped["Dog"] = relationship("Dog", back_populates="saves")
