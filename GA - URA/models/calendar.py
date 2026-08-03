from dataclasses import dataclass

@dataclass(slots=True)
class AcademicWeek:
    week: int
    is_teaching: bool
    is_midterm: bool
    is_final: bool
    is_holiday: bool
    