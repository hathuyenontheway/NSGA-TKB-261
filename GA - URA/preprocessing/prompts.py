from __future__ import annotations

import json
from typing import Any


RESOURCE_TYPES = (
    "GENERAL",
    "OTHER_SPECIAL",
    "COMPUTER_LAB",
    "PHYSICS_LAB",
    "STUDIO",
    "CHEMISTRY_LAB",
    "ELECTRICAL_LAB",
    "MECHANICAL_WORKSHOP",
)

ROOM_INVENTORY = {
    "GENERAL": 438,
    "OTHER_SPECIAL": 22,
    "COMPUTER_LAB": 15,
    "PHYSICS_LAB": 11,
    "STUDIO": 3,
    "CHEMISTRY_LAB": 3,
    "ELECTRICAL_LAB": 3,
    "MECHANICAL_WORKSHOP": 1,
}


RESOURCE_TYPE_DESCRIPTION = """
GENERAL:
- Ordinary lecture room.
- Lectures, tutorials, languages, mathematics, economics and law.
- Courses that do not require specialized physical equipment.

OTHER_SPECIAL:
- A specialized room is clearly required, but none of the available
  categories below is suitable.

COMPUTER_LAB:
- Programming, databases, artificial intelligence.
- Computer networks, operating systems, computer graphics.
- Software practice, simulation, CAD or data processing on computers.

CHEMISTRY_LAB:
- Chemistry and wet-lab experiments.
- Biology, biotechnology, microbiology, biochemistry, food chemistry
  and environmental wet-lab work when no biology laboratory exists.

PHYSICS_LAB:
- Physics experiments.
- Optics, mechanics, thermodynamics and measurement experiments.

ELECTRICAL_LAB:
- Electrical engineering and electronics experiments.
- Circuits, power systems, PLC, embedded systems.
- Oscilloscopes, electrical measurement and control equipment.

MECHANICAL_WORKSHOP:
- Welding, metalworking, machining, CNC and manufacturing.
- Mechanical workshop activities requiring industrial equipment.

STUDIO:
- Architecture, industrial design, drawing, art or multimedia studio.
""".strip()


def build_course_batch_prompt(
    courses: list[dict[str, Any]],
) -> str:
    course_data = json.dumps(
        courses,
        ensure_ascii=False,
        indent=2,
    )

    allowed_types = ", ".join(RESOURCE_TYPES)

    return f"""
You are classifying university courses according to the PHYSICAL ROOM
or FACILITY required to teach the course.

Classify based on facility requirements, not merely on words that look
similar to scientific terms.

Important rules:

1. "Tối ưu hóa" means mathematical optimization. It is not chemistry.
2. Electrical and electronics practice belongs to ELECTRICAL_LAB,
   not COMPUTER_LAB.
3. Welding and metalworking belong to MECHANICAL_WORKSHOP.
4. A practical course using only software and computers may use
   COMPUTER_LAB.
5. A theoretical course normally belongs to GENERAL.
6. Do not infer a specialized laboratory unless the course clearly
   requires specialized equipment.
7. Vietnamese course names may be written without accents.
8. Biology-related LECTURE courses normally belong to GENERAL.
9. Biology-related LAB/PRACTICAL courses normally belong to
   CHEMISTRY_LAB because no BIOLOGY_LAB exists in the inventory.
10. A course marked "(BT)" is not automatically a laboratory. Use
    GENERAL unless specialized equipment is clearly required.
11. If evidence is weak or ambiguous, choose GENERAL.
12. Never return BIOLOGY_LAB, GEOLOGY_LAB, LAB, UNKNOWN or a value
    outside the allowed list.
13. Abbreviations:
   - TH = thực hành
   - TT = thực tập
   - TN = thí nghiệm
   - HT = hệ thống
   - ĐT or DIEN TU = điện tử
   - CK = cơ khí
   - MÔ PHỎNG = simulation

Allowed resource types:

{allowed_types}

Definitions:

{RESOURCE_TYPE_DESCRIPTION}

Input courses:

{course_data}

Return only a valid JSON array. Return exactly one result for every
input course, preserving each course_id.

Required format:

[
  {{
    "course_id": "200001",
    "resource_type": "GENERAL"
  }},
  {{
    "course_id": "200002",
    "resource_type": "ELECTRICAL_LAB"
  }}
]

Do not include explanations, Markdown or additional fields.
""".strip()


def build_room_batch_prompt(
    rooms: list[dict[str, Any]],
) -> str:
    room_data = json.dumps(
        rooms,
        ensure_ascii=False,
        indent=2,
    )

    allowed_types = ", ".join(RESOURCE_TYPES)
    inventory = "\n".join(
        f"- {resource_type}: {count}"
        for resource_type, count in ROOM_INVENTORY.items()
    )

    return f"""
You are classifying university rooms according to their physical
facilities.

Allowed resource types:

{allowed_types}

No other value is allowed. In particular, never return BIOLOGY_LAB,
GEOLOGY_LAB, LAB or UNKNOWN.

Available room inventory:

{inventory}

Definitions:

{RESOURCE_TYPE_DESCRIPTION}

Classification rules:

1. Classify the room from its physical description, facilities and
   known room property, not from its room ID alone.
2. Use GENERAL for an ordinary classroom or when the evidence for a
   specialized facility is weak.
3. Use OTHER_SPECIAL only when the room is clearly specialized but
   none of the other available categories fits.
4. Return exactly one of the allowed resource types.

Input rooms:

{room_data}

Return only a valid JSON array. Return exactly one result for every
input room, preserving each room_id.

Required format:

[
  {{
    "room_id": "A101",
    "resource_type": "GENERAL"
  }},
  {{
    "room_id": "B201",
    "resource_type": "COMPUTER_LAB"
  }}
]

Do not include explanations, Markdown or additional fields.
""".strip()
