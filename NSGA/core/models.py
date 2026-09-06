"""Canonical models shared by data preparation and chromosome operators."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from types import MappingProxyType
from typing import Mapping, TypeVar


class CourseType(str, Enum):
    LECTURE = "LECTURE"
    LAB = "LAB"
    PRACTICAL = "PRACTICAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Course:
    course_id: str
    course_name: str
    faculty_id: str
    faculty_name: str
    credits: float
    total_hours: int
    lecture_hours: int
    exercise_hours: int
    lab_hours: int
    project_hours: int
    assignment_hours: int
    thesis_hours: int
    course_type: CourseType
    companion_course_id: str | None = None
    resource_type: str = "GENERAL"
    resource_confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class Room:
    room_id: str
    campus: int
    capacity: int
    room_type: str
    resource_type: str = "GENERAL"


@dataclass(frozen=True, slots=True)
class AcademicWeek:
    track: str
    semester_id: str
    week: int
    start_date: date
    end_date: date
    is_teaching: bool
    is_midterm: bool
    is_final: bool
    is_holiday: bool
    holiday_dates: tuple[date, ...] = ()
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Registration:
    student_id: str
    course_id: str

    @property
    def key(self) -> tuple[str, str]:
        # LEC/LAB remain distinct because they have different course IDs.
        return self.student_id, self.course_id


@dataclass(frozen=True, slots=True)
class Section:
    section_id: str
    course_id: str
    section_type: CourseType
    expected_students: int
    max_capacity: int
    parent_section_id: str | None = None
    teacher_id: str | None = None


@dataclass(frozen=True, slots=True)
class Session:
    session_id: int
    section_id: str
    course_id: str
    session_type: CourseType
    duration_slots: int
    total_weeks: int
    allowed_room_ids: tuple[str, ...]
    allowed_start_weeks: tuple[int, ...]
    allowed_days: tuple[int, ...]
    allowed_start_slots: tuple[int, ...]
    parent_session_id: int | None = None


@dataclass(frozen=True, slots=True)
class GeneDomain:
    """Allowed values for the gene at the same position as its session."""
    session_id: int
    room_ids: tuple[str, ...]
    days: tuple[int, ...]
    start_slots: tuple[int, ...]
    start_weeks: tuple[int, ...]

    @property
    def is_empty(self) -> bool:
        return not all((self.room_ids, self.days, self.start_slots, self.start_weeks))


@dataclass(slots=True)
class Gene:
    session_id: int
    room_id: str
    day: int
    start_slot: int
    start_week: int


@dataclass(slots=True)
class Chromosome:
    genes: list[Gene]
    rank: int | None = None
    objectives: tuple[float, ...] = ()
    constraint_violation: float = 0.0

    def copy(self) -> "Chromosome":
        return Chromosome(
            [Gene(g.session_id, g.room_id, g.day, g.start_slot, g.start_week) for g in self.genes],
            self.rank, self.objectives, self.constraint_violation,
        )


@dataclass(frozen=True, slots=True)
class DataIssue:
    code: str
    severity: str
    message: str
    entity_id: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedData:
    courses: Mapping[str, Course]
    catalog_courses: Mapping[str, Course]
    rooms: Mapping[str, Room]
    calendar: tuple[AcademicWeek, ...]
    course_to_rooms: Mapping[str, frozenset[str]]
    room_to_courses: Mapping[str, frozenset[str]]
    registrations: tuple[Registration, ...] = ()
    issues: tuple[DataIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class ProblemInstance:
    courses: Mapping[str, Course]
    rooms: Mapping[str, Room]
    weeks: tuple[AcademicWeek, ...]
    sections: tuple[Section, ...]
    sessions: tuple[Session, ...]
    gene_domains: tuple[GeneDomain, ...]
    registrations: tuple[Registration, ...]
    student_to_courses: Mapping[str, frozenset[str]]
    course_to_students: Mapping[str, frozenset[str]]
    issues: tuple[DataIssue, ...] = ()
    mandatory_course_ids: frozenset[str] = frozenset()  # dùng cho check_mandatory_courses (core/evalution.py)
    teachers: frozenset[str] = frozenset() # tạo giáo viên giả để check
    min_weeks_lecture_to_lab: int = 1 # Kiểu lab cách lecture 1 buổi í
    minimum_empty_slots: int = 3 # Khoảng cách giữa 2 campus là 3*50 = 150 phút > 2 giờ
    f3_weight_pack: float = 0.5 # Để cân bằng giữa việc không dồn môn vào 1 ngày và các môn được chia đều trong tuần
    f3_weight_gap: float = 0.5 # Để cân bằng giữa việc không dồn môn vào 1 ngày và các môn được chia đều trong tuần

    def __post_init__(self) -> None:
        ids = [session.session_id for session in self.sessions]
        if len(ids) != len(set(ids)):
            raise ValueError("session_id must be unique")
        if ids != [domain.session_id for domain in self.gene_domains]:
            raise ValueError("gene_domains must follow the exact session order")


K = TypeVar("K")
V = TypeVar("V")


def frozen_mapping(values: Mapping[K, V]) -> Mapping[K, V]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class Violation:
    code: str
    priority: str          # e.g. "HARD"
    severity: str          # e.g. "ERROR" | "WARNING"
    message: str
    location: dict
    affected_entities: dict
    current_value: object | None = None
    required_value: object | None = None
    suggested_actions: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class StudentAssignment:
    student_id: str
    course_id: str
    section_id: str | None  # None if unfulfilled


@dataclass(frozen=True, slots=True)
class AssignmentResult:
    """Proposed shape for core/assignment.py output. Not implemented there yet."""
    assignments: tuple[StudentAssignment, ...]
    unfulfilled: tuple[StudentAssignment, ...]  # student_id/course_id with section_id=None


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    raw_objectives: tuple[float, ...]
    normalized_objectives: tuple[float, ...]
    violations: tuple[Violation, ...]
    constraint_key: tuple[int, ...]
    student_assignment: tuple[StudentAssignment, ...]
    student_impact: dict