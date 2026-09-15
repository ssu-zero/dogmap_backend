from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LogUpdate(BaseModel):
    """산책 일지 수정. 지금은 diary만 수정 가능하다 — 보낸 필드만 반영되는 partial update."""

    diary: str | None = Field(default=None, description="산책 일지 내용")


class LogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: int
    dog_id: int
    course_id: int | None
    started_at: datetime
    ended_at: datetime | None
    diary: str | None
