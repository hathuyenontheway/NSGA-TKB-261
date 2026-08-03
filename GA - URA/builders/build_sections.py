from __future__ import annotations

import argparse
import math
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd

from models.section import Section


DEFAULT_CAPACITY_BY_RESOURCE: dict[str, int] = {
    "GENERAL": 80,
    "COMPUTER_LAB": 40,
    "CHEMISTRY_LAB": 30,
    "PHYSICS_LAB": 30,
    "BIOLOGY_LAB": 30,
    "GEOLOGY_LAB": 30,
    "ELECTRICAL_LAB": 30,
    "MECHANICAL_WORKSHOP": 30,
    "STUDIO": 30,
    "OTHER_SPECIAL": 30,
}

LECTURE_TYPES = {"LECTURE", "LEC", "LT"}
LAB_TYPES = {"LAB", "TN", "TH", "TNG"}
PRACTICAL_TYPES = {"PRACTICAL", "PRSN"}
UNKNOWN_TYPES = {"UNKNOWN"}


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def normalize_course_type(value: object) -> str:
    text = (normalize_text(value) or "LECTURE").upper()
    if text in LECTURE_TYPES:
        return "LECTURE"
    if text in LAB_TYPES:
        return "LAB"
    if text in PRACTICAL_TYPES:
        return "PRACTICAL"
    if text in UNKNOWN_TYPES:
        return "UNKNOWN"
    raise ValueError(f"Unsupported course type: {value!r}")


def split_evenly(total_students: int, max_capacity: int) -> list[int]:
    """Split students into the minimum number of near-equal non-empty groups."""
    if total_students < 0:
        raise ValueError("total_students must be >= 0")
    if max_capacity <= 0:
        raise ValueError("max_capacity must be > 0")
    if total_students == 0:
        return []

    group_count = math.ceil(total_students / max_capacity)
    base, remainder = divmod(total_students, group_count)
    return [base + (1 if index < remainder else 0) for index in range(group_count)]


def load_enrollment_counts(
    enrollment_csv: str | Path,
    *,
    course_col: str = "F_MAMH",
    program_col: str = "HTDT",
    student_col: str = "F_MASV",
    eligible_col: str | None = None,
    eligible_values: set[str] | None = None,
) -> dict[tuple[str, str], int]:
    """Count distinct students by (course_id, program_type)."""
    usecols = [course_col, program_col, student_col]
    if eligible_col:
        usecols.append(eligible_col)

    df = pd.read_csv(enrollment_csv, dtype=str, usecols=usecols)
    df[course_col] = df[course_col].str.strip()
    df[program_col] = df[program_col].fillna("UNKNOWN").str.strip()
    df[student_col] = df[student_col].str.strip()

    df = df.dropna(subset=[course_col, student_col])
    df = df[(df[course_col] != "") & (df[student_col] != "")]

    if eligible_col and eligible_values:
        accepted = {value.upper() for value in eligible_values}
        df = df[df[eligible_col].fillna("").str.upper().isin(accepted)]

    counts = (
        df.groupby([course_col, program_col], dropna=False)[student_col]
        .nunique()
        .astype(int)
    )
    return {(str(course), str(program)): int(count) for (course, program), count in counts.items()}


def load_resource_mapping(path: str | Path) -> dict[str, str]:
    df = pd.read_csv(path, dtype=str)
    required = {"course_id", "resource_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Resource mapping is missing columns: {sorted(missing)}")

    return {
        str(row.course_id).strip(): str(row.resource_type).strip().upper()
        for row in df.itertuples(index=False)
        if normalize_text(row.course_id) and normalize_text(row.resource_type)
    }


def build_sections(
    courses: Sequence[object],
    enrollment_counts: Mapping[tuple[str, str], int],
    resource_mapping: Mapping[str, str],
    *,
    capacity_by_resource: Mapping[str, int] = DEFAULT_CAPACITY_BY_RESOURCE,
    default_program_type: str = "UNKNOWN",
) -> list[Section]:
    """
    Build lecture sections first, then attach lab sections to parent lectures.

    Required Course attributes:
      course_id, course_type, companion_course_id
    """
    course_by_id = {str(course.course_id): course for course in courses}
    sections: list[Section] = []
    lecture_sections: dict[tuple[str, str], list[Section]] = defaultdict(list)

    def course_program_counts(course_id: str) -> list[tuple[str, int]]:
        result = [
            (program, count)
            for (mapped_course, program), count in enrollment_counts.items()
            if mapped_course == course_id and count > 0
        ]
        return sorted(result) or [(default_program_type, 0)]

    # Pass 1: lecture courses.
    for course in courses:
        course_id = str(course.course_id)
        if normalize_course_type(getattr(course, "course_type", "LECTURE")) != "LECTURE":
            continue

        resource_type = resource_mapping.get(course_id, "GENERAL")
        max_capacity = int(capacity_by_resource.get(resource_type, capacity_by_resource["GENERAL"]))

        for program_type, total_students in course_program_counts(course_id):
            for index, class_size in enumerate(split_evenly(total_students, max_capacity), start=1):
                section = Section(
                    section_id=f"{course_id}_{program_type}_L{index:02d}",
                    course_id=course_id,
                    program_type=program_type,
                    section_type="LECTURE",
                    expected_students=class_size,
                    max_capacity=max_capacity,
                    parent_section_id=None,
                )
                sections.append(section)
                lecture_sections[(course_id, program_type)].append(section)

    # Pass 2: lab/practical courses. They may point back to a lecture via companion_course_id.
    for course in courses:
        course_id = str(course.course_id)
        section_type = normalize_course_type(
            getattr(course, "course_type", "LECTURE")
        )
        if section_type not in {"LAB", "PRACTICAL"}:
            continue

        resource_type = resource_mapping.get(course_id, "OTHER_SPECIAL")
        max_capacity = int(capacity_by_resource.get(resource_type, capacity_by_resource["OTHER_SPECIAL"]))
        lecture_id = normalize_text(getattr(course, "companion_course_id", None))

        for program_type, total_students in course_program_counts(course_id):
            parents = lecture_sections.get((lecture_id, program_type), []) if lecture_id else []

            # Data sometimes has no enrollment rows for the companion lab code.
            if total_students == 0 and parents:
                total_students = sum(parent.expected_students for parent in parents)

            group_sizes = split_evenly(total_students, max_capacity)
            if not group_sizes:
                continue

            if parents:
                # Assign each practical group to a parent lecture while respecting population.
                remaining = {parent.section_id: parent.expected_students for parent in parents}
                for index, class_size in enumerate(group_sizes, start=1):
                    parent = max(parents, key=lambda item: remaining[item.section_id])
                    remaining[parent.section_id] -= class_size
                    section_code = "B" if section_type == "LAB" else "P"
                    sections.append(
                        Section(
                            section_id=f"{course_id}_{program_type}_{section_code}{index:02d}",
                            course_id=course_id,
                            program_type=program_type,
                            section_type=section_type,
                            expected_students=class_size,
                            max_capacity=max_capacity,
                            parent_section_id=parent.section_id,
                        )
                    )
            else:
                # Keep the section usable, but mark it unlinked for validation/reporting.
                for index, class_size in enumerate(group_sizes, start=1):
                    section_code = "B" if section_type == "LAB" else "P"
                    sections.append(
                        Section(
                            section_id=f"{course_id}_{program_type}_{section_code}{index:02d}",
                            course_id=course_id,
                            program_type=program_type,
                            section_type=section_type,
                            expected_students=class_size,
                            max_capacity=max_capacity,
                            parent_section_id=None,
                        )
                    )

    validate_sections(sections)
    return sections


def validate_sections(sections: Iterable[Section]) -> None:
    sections = list(sections)
    ids = [section.section_id for section in sections]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate section_id detected")

    id_set = set(ids)
    for section in sections:
        if section.expected_students <= 0:
            raise ValueError(f"Section {section.section_id} has no students")
        if section.expected_students > section.max_capacity:
            raise ValueError(f"Section {section.section_id} exceeds capacity")
        if section.parent_section_id and section.parent_section_id not in id_set:
            raise ValueError(
                f"Section {section.section_id} references missing parent "
                f"{section.parent_section_id}"
            )


def write_sections_csv(sections: Iterable[Section], output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(asdict(section) for section in sections).to_csv(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build sections from parsed courses and enrollment counts")
    parser.add_argument("--enrollments", required=True)
    parser.add_argument("--course-mapping", required=True)
    parser.add_argument("--courses-pickle", required=True, help="Pickle containing list[Course]")
    parser.add_argument("--output", default="data/processed/sections.csv")
    args = parser.parse_args()

    courses = pd.read_pickle(args.courses_pickle)
    counts = load_enrollment_counts(args.enrollments)
    mapping = load_resource_mapping(args.course_mapping)
    sections = build_sections(courses, counts, mapping)
    write_sections_csv(sections, args.output)

    print(f"Built {len(sections)} sections -> {args.output}")
    print(pd.Series([section.section_type for section in sections]).value_counts().to_string())


if __name__ == "__main__":
    main()
