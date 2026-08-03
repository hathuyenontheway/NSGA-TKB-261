from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd


EnrollmentKey = tuple[str, str]


def _normalize_text(value: object, default: str = "") -> str:
    if pd.isna(value):
        return default

    return str(value).strip()


def load_enrollment_counts(
    csv_path: str | Path,
    *,
    course_column: str = "F_MAMH",
    program_column: str = "HTDT",
    student_column: str = "F_MASV",
    default_program_type: str = "CQ",
) -> dict[EnrollmentKey, int]:
    """
    Đếm số sinh viên duy nhất theo:

        (course_id, program_type) -> student_count

    Các cột mặc định:
        F_MAMH: mã môn học
        HTDT: loại chương trình đào tạo
        F_MASV: mã sinh viên
    """

    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file enrollment: {csv_path}"
        )

    dataframe = pd.read_csv(
        csv_path,
        dtype=str,
        low_memory=False,
    )

    required_columns = {
        course_column,
        program_column,
        student_column,
    }

    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise ValueError(
            "File enrollment thiếu các cột: "
            f"{sorted(missing_columns)}. "
            f"Các cột hiện có: {list(dataframe.columns)}"
        )

    enrollment_students: dict[EnrollmentKey, set[str]] = defaultdict(set)

    for row in dataframe.itertuples(index=False):
        row_data = row._asdict()

        course_id = _normalize_text(
            row_data.get(course_column)
        )

        program_type = _normalize_text(
            row_data.get(program_column),
            default=default_program_type,
        )

        student_id = _normalize_text(
            row_data.get(student_column)
        )

        if not course_id or not student_id:
            continue

        if not program_type:
            program_type = default_program_type

        key = (
            course_id.upper(),
            program_type.upper(),
        )

        enrollment_students[key].add(student_id.upper())

    return {
        key: len(student_ids)
        for key, student_ids in enrollment_students.items()
    }