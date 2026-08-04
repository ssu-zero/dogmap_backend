from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SaveCreate(BaseModel):
    course_id: int
    dog_id: int


class SaveResponse(SaveCreate):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
