from __future__ import annotations
import sys
sys.path.append('../')
import pandas as pd

from models.course import Course


_REQUIRED_COLUMNS = {
    "MAKEM",
    "MAMH",
    "TENMH",
    "MASUBJECTAREA",
    "SOTC",
    "SOTIET",
    "SOTIET_XEPTKB",
    "f_lt",
    "f_bt",
    "f_tn",
    "f_btl",
    "f_da",
    "f_la",
}

COURSE_TYPE_MAPPING = {
    "LEC": "LECTURE",
    "LECTURE": "LECTURE",
    "LT": "LECTURE",
    "LAB": "LAB",
    "TN": "LAB",
    "TH": "LAB",
    "TNG": "LAB",
    "PRSN": "PRACTICAL",
    "PRACTICAL": "PRACTICAL",
}


def _parse_course_type(value: object) -> str:
    if pd.isna(value) or not str(value).strip():
        return "UNKNOWN"

    raw_type = str(value).strip().upper()
    try:
        return COURSE_TYPE_MAPPING[raw_type]
    except KeyError as error:
        raise ValueError(f"Unsupported course type: {value!r}") from error


def _integer(value: object, column: str, course_id: str) -> int:
    if pd.isna(value):
        raise ValueError(f"Missing {column!r} for course {course_id!r}")

    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid {column!r} value {value!r} for course {course_id!r}"
        ) from error

    if not number.is_integer():
        raise ValueError(
            f"Expected an integer {column!r} value for course {course_id!r}, "
            f"got {value!r}"
        )
    return int(number)


def parse_courses(df: pd.DataFrame) -> dict[str, Course]:

    missing_columns = _REQUIRED_COLUMNS.difference(df.columns)
    if missing_columns:
        raise ValueError(
            "mh.csv is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    courses: dict[str, Course] = {}
    for _, row in df.iterrows():
        course_id = str(row["MAMH"]).strip()
        if not course_id or course_id.lower() == "nan":
            raise ValueError("mh.csv contains a row without a MAMH course code")
        if course_id in courses:
            raise ValueError(f"Duplicate course code in mh.csv: {course_id!r}")

        timetable_hours = _integer(row["SOTIET_XEPTKB"], "SOTIET_XEPTKB", course_id)
        if timetable_hours <= 0:
            continue

        subject_area = "" if pd.isna(row["MASUBJECTAREA"]) else str(row["MASUBJECTAREA"]).strip()
        companion_course_id = (
            None
            if pd.isna(row["MAKEM"]) or not str(row["MAKEM"]).strip()
            else str(row["MAKEM"]).strip()
        )
        courses[course_id] = Course(
            course_id=course_id,
            course_name=str(row["TENMH"]).strip(),
            faculty_id=subject_area,
            faculty_name="",
            
            credits=_integer(row["SOTC"], "SOTC", course_id),
            total_hours=_integer(row["SOTIET"], "SOTIET", course_id),
            lecture_hours=_integer(row["f_lt"], "f_lt", course_id),
            exercise_hours=_integer(row["f_bt"], "f_bt", course_id),
            lab_hours=_integer(row["f_tn"], "f_tn", course_id),
            project_hours=_integer(row["f_da"], "f_da", course_id),
            assignment_hours=_integer(row["f_btl"], "f_btl", course_id),
            thesis_hours=_integer(row["f_la"], "f_la", course_id),
            
            course_type=_parse_course_type(row["loai_mh"]),
            companion_course_id=companion_course_id,
        )

    return courses
