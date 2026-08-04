from datetime import date, time

from pydantic import BaseModel, ConfigDict


class LogBase(BaseModel):
    date: date
    start_time: time
    end_time: time
    diary: str | None = None
    course_id: int
    dog_id: int


class LogCreate(LogBase):
    pass


class LogUpdate(BaseModel):
    diary: str | None = None
    end_time: time | None = None


class LogResponse(LogBase):
    model_config = ConfigDict(from_attributes=True)

    log_id: int
