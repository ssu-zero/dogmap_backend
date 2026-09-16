from pydantic import BaseModel


class CourseSaveStatus(BaseModel):
    course_id: int
    is_saved: bool
    save_count: int
