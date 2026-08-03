from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd

from models.section import Section
from models.session import SessionMetadata


DEFAULT_WEEKS = 15


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def load_sections_csv(path: str | Path) -> list[Section]:
    df = pd.read_csv(path, dtype={"section_id": str, "course_id": str, "program_type": str})
    required = {
        "section_id", "course_id", "program_type", "section_type",
        "expected_students", "max_capacity", "parent_section_id",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Sections CSV is missing columns: {sorted(missing)}")

    return [
        Section(
            section_id=str(row.section_id),
            course_id=str(row.course_id),
            program_type=str(row.program_type),
            section_type=str(row.section_type).upper(),
            expected_students=int(row.expected_students),
            max_capacity=int(row.max_capacity),
            parent_section_id=normalize_text(row.parent_section_id),
        )
        for row in df.itertuples(index=False)
    ]


def load_resource_mapping(path: str | Path) -> dict[str, str]:
    df = pd.read_csv(path, dtype=str)
    required = {"course_id", "resource_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Course mapping is missing columns: {sorted(missing)}")
    return {
        str(row.course_id).strip(): str(row.resource_type).strip().upper()
        for row in df.itertuples(index=False)
        if normalize_text(row.course_id) and normalize_text(row.resource_type)
    }


def build_room_index(
    rooms: Sequence[object],
) -> dict[str, list[object]]:
    index: dict[str, list[object]] = {}
    for room in rooms:
        resource_type = str(
            getattr(room, "resource_type", "UNKNOWN")
        ).strip().upper()
        index.setdefault(resource_type, []).append(room)
    return index


def hours_to_session_pattern(total_hours: int) -> tuple[int, int]:
    """Convert total scheduled hours to (duration per session, total weeks)."""
    if total_hours <= 0:
        raise ValueError("total_hours must be greater than 0")
    if total_hours % DEFAULT_WEEKS == 0:
        return total_hours // DEFAULT_WEEKS, DEFAULT_WEEKS
    if total_hours % 10 == 0:
        return total_hours // 10, 10
    return 3, max(1, round(total_hours / 3))


def get_pattern(course: object, section_type: str) -> tuple[int, int]:
    section_type = str(section_type).strip().upper()

    if section_type == "LECTURE":
        total_hours = int(course.lecture_hours or 0) + int(
            course.exercise_hours or 0
        )
    elif section_type == "LAB":
        total_hours = int(course.lab_hours or 0)
    elif section_type == "PRACTICAL":
        total_hours = int(course.project_hours or 0) + int(
            course.thesis_hours or 0
        )
        if total_hours <= 0:
            total_hours = int(course.exercise_hours or 0)
    else:
        raise ValueError(
            f"Unsupported section type {section_type!r} "
            f"for course {getattr(course, 'course_id', '?')}"
        )

    if total_hours <= 0:
        raise ValueError(
            f"Course {getattr(course, 'course_id', '?')} has no hours "
            f"for section type {section_type}"
        )

    return hours_to_session_pattern(total_hours)


def build_sessions(
    sections: Sequence[Section],
    courses: Sequence[object],
    rooms: Sequence[object],
    resource_mapping: Mapping[str, str],
    *,
    default_campus: int | None = None,
) -> list[SessionMetadata]:
    """Build one immutable SessionMetadata object for each Section."""
    course_by_id = {str(course.course_id): course for course in courses}
    room_index = build_room_index(rooms)

    session_id_by_section = {
        section.section_id: session_id
        for session_id, section in enumerate(sections)
    }

    sessions: list[SessionMetadata] = []
    for session_id, section in enumerate(sections):
        course = course_by_id.get(str(section.course_id).strip().upper())
        if course is None:
            raise ValueError(f"Missing Course for section {section.section_id}: {section.course_id}")

        duration, total_weeks = get_pattern(course, section.section_type)
        required_room_type = resource_mapping.get(
            section.course_id,
            "GENERAL" if section.section_type == "LECTURE" else "OTHER_SPECIAL",
        )

        compatible_rooms = {
            str(room.room_id)
            for room in room_index.get(required_room_type, [])
            if int(room.capacity) >= section.expected_students
            and (default_campus is None or int(room.campus) == default_campus)
        }

        parent_session_id = (
            session_id_by_section.get(section.parent_section_id)
            if section.parent_section_id
            else None
        )

        sessions.append(
            SessionMetadata(
                session_id=session_id,
                course_id=section.course_id,
                section_id=section.section_id,
                session_type=section.section_type,
                class_size=section.expected_students,
                duration=duration,
                total_weeks=total_weeks,
                min_lab_offset=1 if section.section_type == "LAB" else 0,
                has_midterm=False,
                allowed_rooms=frozenset(compatible_rooms),
                required_room_type=required_room_type,
                parent_session_id=parent_session_id,
                campus=default_campus,
            )
        )

    validate_sessions(sessions)
    return sessions


def validate_sessions(sessions: Iterable[SessionMetadata]) -> None:
    sessions = list(sessions)
    ids = [session.session_id for session in sessions]
    if ids != list(range(len(sessions))):
        raise ValueError("session_id values must be contiguous from 0 to M-1")

    section_ids = [session.section_id for session in sessions]
    if len(section_ids) != len(set(section_ids)):
        raise ValueError("A Section produced more than one SessionMetadata")

    missing_rooms = [session.section_id for session in sessions if not session.allowed_rooms]
    if missing_rooms:
        preview = ", ".join(missing_rooms[:10])
        raise ValueError(
            f"{len(missing_rooms)} sessions have no compatible room. First: {preview}"
        )

    by_id = {session.session_id: session for session in sessions}
    for session in sessions:
        if session.parent_session_id is None:
            continue
        parent = by_id.get(session.parent_session_id)
        if parent is None:
            raise ValueError(f"Session {session.session_id} references a missing parent")
        if (
            session.session_type not in {"LAB", "PRACTICAL"}
            or parent.session_type != "LECTURE"
        ):
            raise ValueError(
                "Only LAB/PRACTICAL -> LECTURE parent links are valid"
            )


def write_sessions_csv(sessions: Iterable[SessionMetadata], output_path: str | Path) -> None:
    rows = []
    for session in sessions:
        row = asdict(session)
        row["allowed_rooms"] = "|".join(sorted(session.allowed_rooms))
        rows.append(row)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_path, index=False)


def print_session_report(sessions: Sequence[SessionMetadata]) -> None:
    print(f"Total sessions: {len(sessions)}")
    print("By type:", dict(Counter(session.session_type for session in sessions)))
    print("By resource:", dict(Counter(session.required_room_type for session in sessions)))
    print(
        "Linked labs/practicals:",
        sum(
            session.parent_session_id is not None
            and session.session_type in {"LAB", "PRACTICAL"}
            for session in sessions
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SessionMetadata from Sections")
    parser.add_argument("--sections", required=True)
    parser.add_argument("--courses-pickle", required=True)
    parser.add_argument("--rooms-pickle", required=True)
    parser.add_argument("--course-mapping", required=True)
    parser.add_argument("--output", default="data/processed/sessions.csv")
    args = parser.parse_args()

    sections = load_sections_csv(args.sections)
    courses = pd.read_pickle(args.courses_pickle)
    rooms = pd.read_pickle(args.rooms_pickle)
    mapping = load_resource_mapping(args.course_mapping)

    sessions = build_sessions(sections, courses, rooms, mapping)
    write_sessions_csv(sessions, args.output)
    print_session_report(sessions)
    print(f"Saved -> {args.output}")


if __name__ == "__main__":
    main()
