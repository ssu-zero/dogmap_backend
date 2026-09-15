from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LogCreate(BaseModel):
    """산책 기록 생성 요청. 코스를 선택해서 산책을 시작하면 호출한다. course_id를
    생략하면 코스 없는 자유 산책으로 기록된다."""

    course_id: int | None = Field(default=None, description="선택한 코스 id. 자유 산책이면 생략")


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
