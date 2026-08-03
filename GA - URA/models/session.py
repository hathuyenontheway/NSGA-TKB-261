from dataclasses import dataclass

@dataclass(slots=True)
class SessionPattern:
    slots_per_week: int
    total_weeks: int
    min_lab_offset: int = 0
    has_midterm: bool = False

@dataclass(slots=True)
class SessionMetadata:
    session_id: int
    course_id: str
    section_id: str

    session_type: str         # LECTURE / LAB / PRACTICAL
    class_size: int

    duration: int
    total_weeks: int
    min_lab_offset: int
    has_midterm: bool

    allowed_rooms: frozenset[str]
    required_room_type: str
    campus: int | None

    parent_session_id: int | None = None
