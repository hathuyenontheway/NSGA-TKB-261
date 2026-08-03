from dataclasses import dataclass


@dataclass(slots=True)
class Section:
    section_id: str
    course_id: str
    
    program_type: str
    
    expected_students: int
    max_capacity: int

    section_type: str # LECTURE / LAB / PRACTICAL
    parent_section_id: str | None = None 