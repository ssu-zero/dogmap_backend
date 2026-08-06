from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, CreatedAtMixin

if TYPE_CHECKING:
    from app.domains.courses.models import Course
    from app.domains.dogs.models import Dog


class Save(CreatedAtMixin, Base):
    """Dog-Course 저장. 생성/삭제만 하고 수정하지 않으므로 updated_at을 두지 않는다.

    course_id/dog_id 복합 PK 대신 save_id 단일 PK + UNIQUE(dog_id, course_id)를 쓴다.
    """

    __tablename__ = "saves"

    __table_args__ = (UniqueConstraint("dog_id", "course_id", name="uq_saves_dog_course"),)

    save_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    dog_id: Mapped[int] = mapped_column(
        ForeignKey("dogs.dog_id", ondelete="CASCADE"), nullable=False, index=True
    )
    dog: Mapped["Dog"] = relationship()

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False, index=True
    )
    course: Mapped["Course"] = relationship()
