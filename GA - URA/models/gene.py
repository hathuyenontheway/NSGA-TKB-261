from dataclasses import dataclass

@dataclass(slots=True)
class Gene:
    session_id: int
    day: int
    start_week: int
    room_id: str
    start_slot: int
    week_pattern: int
    