from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, TimestampMixin

if TYPE_CHECKING:
    from app.domains.courses.models import Course
    from app.domains.dogs.models import Dog


class Log(TimestampMixin, Base):
    """회원(Dog)의 산책 기록. date/start_time/end_time을 나누지 않고 started_at/ended_at
    timezone-aware datetime으로 관리한다 — 날짜와 시간을 분리하면 자정을 넘는 산책
    (예: 23:50 시작, 다음날 00:30 종료)의 종료 날짜가 불명확해지기 때문이다.
    """

    __tablename__ = "logs"

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    dog_id: Mapped[int] = mapped_column(
        ForeignKey("dogs.dog_id", ondelete="CASCADE"), nullable=False, index=True
    )
    dog: Mapped["Dog"] = relationship()

    # 자유 산책(코스 없이 산책 후 기록)을 허용하므로 nullable=True.
    # 코스가 삭제돼도 기록 자체는 남기기 위해 ondelete="SET NULL".
    course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.course_id", ondelete="SET NULL"), nullable=True, index=True
    )
    course: Mapped["Course | None"] = relationship()

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    diary: Mapped[str | None] = mapped_column(Text)
