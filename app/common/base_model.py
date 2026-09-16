from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CreatedAtMixin:
    """created_at만 가지는 테이블(Likes, Saves)용 믹스인 — 생성/삭제만 하고 수정하지 않는 엔티티."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    """created_at + updated_at을 모두 가지는 테이블(Dogs, Courses, Logs, CoursePlaces, Places)용 믹스인.

    onupdate=func.now()는 해당 테이블에 실제 UPDATE 쿼리가 수행될 때만 적용된다.
    예: CoursePlace만 수정하고 Course 행에 UPDATE가 없으면 Course.updated_at은 바뀌지 않는다.
    코스 구성 변경을 Course의 수정으로 간주한다면 서비스 계층에서 Course도 함께 갱신해야 한다.
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
