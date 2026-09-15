from pydantic import BaseModel


class CourseLikeStatus(BaseModel):
    course_id: int
    is_liked: bool
    like_count: int
