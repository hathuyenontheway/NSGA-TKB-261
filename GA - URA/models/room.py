from dataclasses import dataclass

@dataclass(slots=True)
class Room:
    room_id: str
    campus: int
    capacity: int
    room_type: str
    
    resource_type: str = "GENERAL"
    