from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LikeCreate(BaseModel):
    course_id: int
    dog_id: int


class LikeResponse(LikeCreate):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
