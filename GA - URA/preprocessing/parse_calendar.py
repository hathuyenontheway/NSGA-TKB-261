from __future__ import annotations
import sys
sys.path.append('../')
import pandas as pd

from models.calendar import AcademicWeek


_REQUIRED_COLUMNS = {
    "WEEK",
    "TEACHING",
    "MIDTERM",
    "FINAL",
    "HOLIDAY",
}


def _require_bool(value: object) -> bool:

    if pd.isna(value):
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    text = str(value).strip().lower()

    return text in {
        "1",
        "true",
        "yes",
        "y",
        "x",
    }


def parse_calendar(
    df: pd.DataFrame,
) -> dict[int, AcademicWeek]:

    missing_columns = _REQUIRED_COLUMNS.difference(df.columns)

    if missing_columns:
        raise ValueError(
            "calendar.csv is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    calendar: dict[int, AcademicWeek] = {}

    for row in df.itertuples(index=False):

        week = int(row.WEEK)

        if week in calendar:
            raise ValueError(f"Duplicate week {week}")

        calendar[week] = AcademicWeek(
            week=week,
            is_teaching=_require_bool(row.TEACHING),
            is_midterm=_require_bool(row.MIDTERM),
            is_final=_require_bool(row.FINAL),
            is_holiday=_require_bool(row.HOLIDAY),
        )

    return calendar