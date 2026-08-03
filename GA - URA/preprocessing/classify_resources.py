from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any, Iterator, TypeVar

from llm_client import GeminiClient
from prompts import (
    RESOURCE_TYPES,
    build_course_batch_prompt,
    build_room_batch_prompt,
)


T = TypeVar("T")

DEFAULT_OUTPUT_DIR = Path(__file__).parent / "mappings"
DEFAULT_BATCH_SIZE = 25
DEFAULT_MAX_RETRIES = 3

BIOLOGY_KEYWORDS = {
    "SINH HOC",
    "VI SINH",
    "CONG NGHE TE BAO",
    "TE BAO",
    "SINH HOA",
    "CONG NGHE SINH HOC",
    "MOLECULAR BIOLOGY",
    "MICROBIOLOGY",
    "BIOTECHNOLOGY",
    "BIOCHEMISTRY",
}


def chunked(
    items: list[T],
    batch_size: int,
) -> Iterator[list[T]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    for start in range(0, len(items), batch_size):
        yield items[start:start + batch_size]


def normalize_resource_type(value: Any) -> str:
    resource_type = str(value).strip().upper()

    if resource_type not in RESOURCE_TYPES:
        raise ValueError(
            f"Invalid resource_type: {resource_type!r}"
        )

    return resource_type


def apply_inventory_fallback(
    course_name: Any,
    course_type: Any,
    predicted_type: Any,
) -> str:
    name = str(course_name).strip().upper()
    section_type = str(course_type).strip().upper()

    is_biology = any(
        keyword in name
        for keyword in BIOLOGY_KEYWORDS
    )
    if is_biology:
        if section_type in {"LAB", "PRACTICAL", "PRSN"}:
            return "CHEMISTRY_LAB"
        if section_type in {"LECTURE", "LEC", "LT"}:
            return "GENERAL"

    try:
        return normalize_resource_type(predicted_type)
    except ValueError:
        return "GENERAL"


def safe_attribute(
    obj: Any,
    *names: str,
    default: Any = "",
) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)

            if value is not None:
                return value

    return default


def load_existing_mapping(
    path: str | Path,
    id_column: str,
) -> dict[str, str]:
    path = Path(path)

    if not path.exists():
        return {}

    mapping: dict[str, str] = {}

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            item_id = str(row.get(id_column, "")).strip()
            raw_resource_type = row.get("resource_type", "")

            try:
                resource_type = normalize_resource_type(
                    raw_resource_type
                )
            except ValueError:
                continue

            if item_id:
                mapping[item_id] = resource_type

    return mapping


def save_course_mapping(
    courses: dict[str, Any],
    mapping: dict[str, str],
    output_path: str | Path,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "course_id",
                "course_name",
                "resource_type",
            ],
        )

        writer.writeheader()

        for course_id, course in courses.items():
            if course_id not in mapping:
                continue

            writer.writerow(
                {
                    "course_id": course_id,
                    "course_name": safe_attribute(
                        course,
                        "course_name",
                        "name",
                    ),
                    "resource_type": mapping[course_id],
                }
            )


def save_room_mapping(
    rooms: dict[str, Any],
    mapping: dict[str, str],
    output_path: str | Path,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "room_id",
                "room_description",
                "resource_type",
            ],
        )

        writer.writeheader()

        for room_id, room in rooms.items():
            if room_id not in mapping:
                continue

            writer.writerow(
                {
                    "room_id": room_id,
                    "room_description": safe_attribute(
                        room,
                        "description",
                        "room_type",
                        "room_property",
                        "room_type_raw",
                    ),
                    "resource_type": mapping[room_id],
                }
            )


def call_with_retry(
    client: GeminiClient,
    prompt: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            result = client.generate_json(prompt)

            if not isinstance(result, list):
                raise ValueError(
                    "Expected Gemini to return a JSON array."
                )

            if not all(isinstance(item, dict) for item in result):
                raise ValueError(
                    "Every batch result must be a JSON object."
                )

            return result

        except Exception as exc:
            last_error = exc

            if attempt == max_retries:
                break

            wait_seconds = 2 ** attempt

            print(
                f"  Request failed: {exc}\n"
                f"  Retrying in {wait_seconds} seconds..."
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        f"Gemini request failed after {max_retries} attempts."
    ) from last_error


def course_to_prompt_data(
    course_id: str,
    course: Any,
) -> dict[str, Any]:
    companion_id = safe_attribute(
        course,
        "companion_course_id",
        default=None,
    )

    if str(companion_id).strip().lower() in {
        "",
        "none",
        "nan",
    }:
        companion_id = None

    return {
        "course_id": course_id,
        "course_name": safe_attribute(
            course,
            "course_name",
            "name",
        ),
        "faculty_name": safe_attribute(
            course,
            "faculty_name",
            "faculty",
        ),
        "faculty_id": safe_attribute(
            course,
            "faculty_id",
            default="",
        ),
        "course_type": safe_attribute(
            course,
            "course_type",
            default="",
        ),
        "lecture_hours": safe_attribute(
            course,
            "lecture_hours",
            "f_lt",
            default=0,
        ),
        "exercise_hours": safe_attribute(
            course,
            "exercise_hours",
            "f_bt",
            default=0,
        ),
        "lab_hours": safe_attribute(
            course,
            "lab_hours",
            "f_tn",
            default=0,
        ),
        "project_hours": safe_attribute(
            course,
            "project_hours",
            "f_da",
            default=0,
        ),
        "assignment_hours": safe_attribute(
            course,
            "assignment_hours",
            "f_btl",
            default=0,
        ),
        "thesis_hours": safe_attribute(
            course,
            "thesis_hours",
            "f_la",
            default=0,
        ),
        "companion_course_id": companion_id,
    }


def room_to_prompt_data(
    room_id: str,
    room: Any,
) -> dict[str, Any]:
    return {
        "room_id": room_id,
        "description": safe_attribute(
            room,
            "description",
            "room_type",
            "room_property",
            "room_type_raw",
        ),
        "campus": safe_attribute(
            room,
            "campus",
            default="",
        ),
        "capacity": safe_attribute(
            room,
            "capacity",
            "max_capacity",
            default=0,
        ),
    }


def parse_batch_results(
    results: list[dict[str, Any]],
    expected_ids: set[str],
    id_column: str,
) -> dict[str, str]:
    parsed: dict[str, str] = {}

    for item in results:
        item_id = str(item.get(id_column, "")).strip()

        if not item_id:
            continue

        if item_id not in expected_ids:
            print(
                f"  Warning: unexpected {id_column}: {item_id}"
            )
            continue

        try:
            resource_type = normalize_resource_type(
                item.get("resource_type")
            )
        except ValueError as exc:
            print(
                f"  Warning: {item_id}: {exc}; "
                "using GENERAL"
            )
            resource_type = "GENERAL"

        parsed[item_id] = resource_type

    return parsed


def classify_course_batches(
    courses: dict[str, Any],
    mapping: dict[str, str],
    client: GeminiClient,
    output_path: Path,
    batch_size: int,
) -> None:
    pending_ids = [
        course_id
        for course_id in courses
        if course_id not in mapping
    ]

    total_pending = len(pending_ids)
    total_batches = (
        total_pending + batch_size - 1
    ) // batch_size

    for batch_number, batch_ids in enumerate(
        chunked(pending_ids, batch_size),
        start=1,
    ):
        batch_data = [
            course_to_prompt_data(
                course_id,
                courses[course_id],
            )
            for course_id in batch_ids
        ]

        print(
            f"[Course batch {batch_number}/{total_batches}] "
            f"{len(batch_ids)} courses"
        )

        prompt = build_course_batch_prompt(batch_data)
        results = call_with_retry(client, prompt)

        parsed = parse_batch_results(
            results=results,
            expected_ids=set(batch_ids),
            id_column="course_id",
        )
        prompt_data_by_id = {
            str(item["course_id"]): item
            for item in batch_data
        }
        parsed = {
            course_id: apply_inventory_fallback(
                prompt_data_by_id[course_id].get("course_name"),
                prompt_data_by_id[course_id].get("course_type"),
                resource_type,
            )
            for course_id, resource_type in parsed.items()
        }

        mapping.update(parsed)

        missing_ids = [
            course_id
            for course_id in batch_ids
            if course_id not in parsed
        ]

        if missing_ids:
            print(
                "  Missing classifications: "
                + ", ".join(missing_ids)
            )

            # Không gán OTHER_SPECIAL tự động vì có thể che mất lỗi API.
            # Các ID thiếu sẽ được xử lý lại khi chạy chương trình lần sau.

        for course_id in batch_ids:
            if course_id in parsed:
                print(
                    f"  {course_id} -> {parsed[course_id]}"
                )

        save_course_mapping(
            courses,
            mapping,
            output_path,
        )


def classify_room_batches(
    rooms: dict[str, Any],
    mapping: dict[str, str],
    client: GeminiClient,
    output_path: Path,
    batch_size: int,
) -> None:
    pending_ids = [
        room_id
        for room_id in rooms
        if room_id not in mapping
    ]

    total_pending = len(pending_ids)
    total_batches = (
        total_pending + batch_size - 1
    ) // batch_size

    for batch_number, batch_ids in enumerate(
        chunked(pending_ids, batch_size),
        start=1,
    ):
        batch_data = [
            room_to_prompt_data(
                room_id,
                rooms[room_id],
            )
            for room_id in batch_ids
        ]

        print(
            f"[Room batch {batch_number}/{total_batches}] "
            f"{len(batch_ids)} rooms"
        )

        prompt = build_room_batch_prompt(batch_data)
        results = call_with_retry(client, prompt)

        parsed = parse_batch_results(
            results=results,
            expected_ids=set(batch_ids),
            id_column="room_id",
        )

        mapping.update(parsed)

        missing_ids = [
            room_id
            for room_id in batch_ids
            if room_id not in parsed
        ]

        if missing_ids:
            print(
                "  Missing classifications: "
                + ", ".join(missing_ids)
            )

        for room_id in batch_ids:
            if room_id in parsed:
                print(
                    f"  {room_id} -> {parsed[room_id]}"
                )

        save_room_mapping(
            rooms,
            mapping,
            output_path,
        )


def classify_resources(
    courses: dict[str, Any],
    rooms: dict[str, Any],
    client: GeminiClient,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    course_batch_size: int = 25,
    room_batch_size: int = 25,
) -> tuple[dict[str, str], dict[str, str]]:
    output_dir = Path(output_dir)

    course_output = (
        output_dir / "course_resource_mapping.csv"
    )
    room_output = (
        output_dir / "room_resource_mapping.csv"
    )

    course_mapping = load_existing_mapping(
        course_output,
        id_column="course_id",
    )

    room_mapping = load_existing_mapping(
        room_output,
        id_column="room_id",
    )

    print(
        f"Loaded {len(course_mapping)} existing course mappings."
    )
    print(
        f"Loaded {len(room_mapping)} existing room mappings."
    )

    classify_course_batches(
        courses=courses,
        mapping=course_mapping,
        client=client,
        output_path=course_output,
        batch_size=course_batch_size,
    )

    classify_room_batches(
        rooms=rooms,
        mapping=room_mapping,
        client=client,
        output_path=room_output,
        batch_size=room_batch_size,
    )

    return course_mapping, room_mapping
