from dataclasses import dataclass

@dataclass
class Teacher:
    teacher_id: int
    faculty: str
    available_days: list
    available_slots: list