"""Load the team's processed CSV products into canonical domain structures."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
import re
from typing import Iterable

import pandas as pd

from core.models import AcademicWeek, Course, CourseType, DataIssue, PreparedData, Registration, Room, frozen_mapping

COURSE_COLUMNS = {"course_id", "course_name", "faculty_id", "faculty_name", "credits", "total_hours", "lecture_hours", "exercise_hours", "lab_hours", "project_hours", "assignment_hours", "thesis_hours", "course_type", "companion_course_id", "resource_type", "resource_confidence"}
ROOM_COLUMNS = {"room_id", "campus", "capacity", "room_type", "resource_type"}
CALENDAR_COLUMNS = {"track", "semester_id", "week", "start_date", "end_date", "is_teaching", "is_midterm", "is_final", "is_holiday", "holiday_dates", "notes"}


class DataValidationError(ValueError):
    pass


def _require(frame: pd.DataFrame, columns: set[str], path: Path) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise DataValidationError(f"{path.name} missing columns: {missing}")


def _text(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _int(value: object) -> int:
    return 0 if pd.isna(value) else int(float(value))


def _bool(value: object) -> bool:
    return value if isinstance(value, bool) else _text(value).lower() in {"1", "true", "yes", "y"}


def load_courses(path: Path) -> dict[str, Course]:
    frame = pd.read_csv(path, dtype={"course_id": str, "companion_course_id": str})
    _require(frame, COURSE_COLUMNS, path)
    if frame.course_id.isna().any() or frame.course_id.duplicated().any():
        raise DataValidationError(f"{path.name}: course_id must be non-null and unique")
    result = {}
    for row in frame.to_dict("records"):
        value = _text(row["course_type"]).upper() or "UNKNOWN"
        kind = CourseType(value) if value in CourseType._value2member_map_ else CourseType.UNKNOWN
        course_id = _text(row["course_id"])
        result[course_id] = Course(
            course_id, _text(row["course_name"]), _text(row["faculty_id"]),
            _text(row["faculty_name"]), float(row["credits"] or 0),
            *[_int(row[name]) for name in ("total_hours", "lecture_hours", "exercise_hours", "lab_hours", "project_hours", "assignment_hours", "thesis_hours")],
            kind, _text(row["companion_course_id"]) or None,
            _text(row["resource_type"]) or "GENERAL", float(row["resource_confidence"] or 0),
        )
    return result


def load_rooms(path: Path) -> dict[str, Room]:
    frame = pd.read_csv(path, dtype={"room_id": str})
    _require(frame, ROOM_COLUMNS, path)
    if frame.room_id.isna().any() or frame.room_id.duplicated().any():
        raise DataValidationError(f"{path.name}: room_id must be non-null and unique")
    return {_text(r["room_id"]): Room(_text(r["room_id"]), _int(r["campus"]), _int(r["capacity"]), _text(r["room_type"]), _text(r["resource_type"]) or "GENERAL") for r in frame.to_dict("records")}


def load_calendar(path: Path, track: str, semester_id: str) -> tuple[AcademicWeek, ...]:
    frame = pd.read_csv(path)
    _require(frame, CALENDAR_COLUMNS, path)
    selected = frame[(frame.track.astype(str) == track) & (frame.semester_id.astype(str) == semester_id)]
    if selected.empty:
        available = sorted({(str(r.track), str(r.semester_id)) for r in frame.itertuples()})
        raise DataValidationError(f"Calendar {track}/{semester_id} not found; available={available}")
    if selected.week.duplicated().any():
        raise DataValidationError("calendar week must be unique within track/semester")
    result = []
    for r in selected.sort_values("week").to_dict("records"):
        holidays = tuple(
            date.fromisoformat(value)
            for raw in re.split(r"[,;]", _text(r["holiday_dates"]))
            if (value := raw.strip())
        )
        result.append(AcademicWeek(track, semester_id, _int(r["week"]), date.fromisoformat(_text(r["start_date"])), date.fromisoformat(_text(r["end_date"])), _bool(r["is_teaching"]), _bool(r["is_midterm"]), _bool(r["is_final"]), _bool(r["is_holiday"]), holidays, _text(r["notes"])))
    return tuple(result)


def _read_fixed_width_union(path: Path) -> Iterable[tuple[str, str]]:
    """Support the current fixed-width team export despite its .csv suffix."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        return
    separators = [i for i, char in enumerate(lines[0]) if char == ","]
    if len(separators) != 6 or len(set(map(len, lines))) != 1:
        raise DataValidationError(f"Unsupported mapping format: {path.name}")
    for line in lines[1:]:
        fields, start = [], 0
        for end in separators + [len(line)]:
            fields.append(line[start:end].strip().strip('"'))
            start = end + 1
        courses = [_text(v) for v in fields[5].split(",") if _text(v)]
        if len(courses) != _int(fields[6]):
            raise DataValidationError(f"Mapping count mismatch for room {fields[0]}")
        yield from ((course_id, fields[0]) for course_id in courses)


def load_course_room_mapping(path: Path) -> tuple[dict[str, frozenset[str]], dict[str, frozenset[str]]]:
    try:
        frame = pd.read_csv(path, dtype=str)
        if {"course_id", "room_id"} <= set(frame.columns):
            pairs = ((_text(r["course_id"]), _text(r["room_id"])) for r in frame.to_dict("records"))
        elif {"room_id", "courses"} <= set(frame.columns):
            pairs = ((_text(c), _text(r["room_id"])) for r in frame.to_dict("records") for c in _text(r["courses"]).split(",") if _text(c))
        else:
            raise DataValidationError("Unsupported mapping columns")
    except (pd.errors.ParserError, DataValidationError):
        pairs = _read_fixed_width_union(path)
    c2r, r2c = defaultdict(set), defaultdict(set)
    for course_id, room_id in pairs:
        if course_id and room_id:
            c2r[course_id].add(room_id); r2c[room_id].add(course_id)
    return ({k: frozenset(sorted(v)) for k, v in c2r.items()}, {k: frozenset(sorted(v)) for k, v in r2c.items()})


def load_registrations(path: Path | None) -> tuple[Registration, ...]:
    if path is None or not path.exists():
        return ()
    frame = pd.read_csv(path, dtype=str)
    if {"student_id", "course_id"} <= set(frame.columns):
        student, course = "student_id", "course_id"
    elif {"F_MASV", "F_MAMH"} <= set(frame.columns):
        student, course = "F_MASV", "F_MAMH"
    else:
        raise DataValidationError(f"Registration columns not recognized in {path.name}")
    keys = {(_text(r[student]), _text(r[course])) for r in frame.to_dict("records") if _text(r[student]) and _text(r[course])}
    return tuple(Registration(*key) for key in sorted(keys))


def prepare_data(data_dir: str | Path, *, track: str, semester_id: str, registrations_file: str | None = None) -> PreparedData:
    base = Path(data_dir)
    courses, catalog, rooms = load_courses(base / "courses_khgd.csv"), load_courses(base / "courses_old.csv"), load_rooms(base / "rooms.csv")
    calendar = load_calendar(base / "calendar.csv", track, semester_id)
    raw_c2r, raw_r2c = load_course_room_mapping(base / "room_course_mapping_union.csv")
    registrations = load_registrations(base / registrations_file if registrations_file else None)
    issues = [DataIssue("ORPHAN_MAPPING_ROOM", "ERROR", "Map references unknown room", rid) for rid in sorted(set(raw_r2c) - set(rooms))]
    issues += [DataIssue("COURSE_WITHOUT_ROOM", "ERROR", "KHGD course has no eligible room", cid) for cid in sorted(set(courses) - set(raw_c2r))]
    valid_c2r = {cid: frozenset(sorted(set(rids) & set(rooms))) for cid, rids in raw_c2r.items()}
    for cid, rids in valid_c2r.items():
        if cid in courses and 0 < len(rids) <= 2:
            issues.append(DataIssue("ROOM_BOTTLENECK", "WARNING", f"Course has only {len(rids)} eligible room(s)", cid))
    valid_r2c = defaultdict(set)
    for cid, rids in valid_c2r.items():
        for rid in rids: valid_r2c[rid].add(cid)
    return PreparedData(frozen_mapping(courses), frozen_mapping(catalog), frozen_mapping(rooms), calendar, frozen_mapping(valid_c2r), frozen_mapping({k: frozenset(v) for k, v in valid_r2c.items()}), registrations, tuple(issues))
