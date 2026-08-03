from dataclasses import dataclass
from models.session import SessionPattern

@dataclass(slots=True)
class Course:
    course_id: str
    course_name: str
    faculty_id: str
    faculty_name: str

    credits: int
    total_hours: int
    lecture_hours: int
    exercise_hours: int
    lab_hours: int
    project_hours: int
    assignment_hours: int
    thesis_hours: int

    course_type: str
    companion_course_id: str | None

    resource_type: str = "GENERAL"
    resource_confidence: float = 1.0