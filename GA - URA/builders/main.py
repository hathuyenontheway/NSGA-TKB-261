import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
MAPPINGS_DIR = ROOT_DIR / "preprocessing" / "mappings"

COURSES_PATH = PROCESSED_DATA_DIR / "mh.csv"
ROOMS_PATH = PROCESSED_DATA_DIR / "room261.csv"
ENROLLMENTS_PATH = PROCESSED_DATA_DIR / "kq_nv.csv"
COURSE_RESOURCE_MAPPING_PATH = MAPPINGS_DIR / "course_resource_mapping.csv"
ROOM_RESOURCE_MAPPING_PATH = MAPPINGS_DIR / "room_resource_mapping.csv"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from builders.build_sections import build_sections
from builders.build_sessions import build_sessions
from preprocessing.enrollments import load_enrollment_counts
from preprocessing.parse_courses import parse_courses
from preprocessing.parse_rooms import parse_rooms


def main():
    print("Loading courses...")
    courses_df = pd.read_csv(COURSES_PATH)
    courses_by_id = parse_courses(courses_df)
    courses = list(courses_by_id.values())

    print(f"Loaded {len(courses)} courses")
    unknown_courses = [
        course for course in courses if course.course_type == "UNKNOWN"
    ]
    print(f"Skipped {len(unknown_courses)} UNKNOWN courses")

    print("Loading rooms...")
    rooms_df = pd.read_csv(ROOMS_PATH)
    rooms_by_id = parse_rooms(rooms_df)
    rooms = list(rooms_by_id.values())

    print(f"Loaded {len(rooms)} rooms")

    print("Loading course resource mapping...")
    course_resource_mapping_df = pd.read_csv(
        COURSE_RESOURCE_MAPPING_PATH,
        dtype=str,
    )
    resource_mapping = (
        course_resource_mapping_df
        .dropna(subset=["course_id", "resource_type"])
        .assign(
            course_id=lambda df: df["course_id"].str.strip().str.upper(),
            resource_type=lambda df: df["resource_type"].str.strip().str.upper(),
        )
        .drop_duplicates(subset=["course_id"], keep="last")
        .set_index("course_id")["resource_type"]
        .to_dict()
    )

    print(f"Loaded {len(resource_mapping)} course mappings")

    print("Loading room resource mapping...")
    room_resource_mapping_df = pd.read_csv(
        ROOM_RESOURCE_MAPPING_PATH,
        dtype=str,
    )
    room_resource_mapping = (
        room_resource_mapping_df
        .dropna(subset=["room_id", "resource_type"])
        .assign(
            room_id=lambda df: df["room_id"].str.strip().str.upper(),
            resource_type=lambda df: df["resource_type"].str.strip().str.upper(),
        )
        .drop_duplicates(subset=["room_id"], keep="last")
        .set_index("room_id")["resource_type"]
        .to_dict()
    )

    unmapped_rooms = []
    for room in rooms:
        room_id = str(room.room_id).strip().upper()
        mapped_resource = room_resource_mapping.get(room_id)
        if mapped_resource is None:
            unmapped_rooms.append(room_id)
            room.resource_type = "UNKNOWN"
        else:
            room.resource_type = mapped_resource

    print(f"Loaded {len(room_resource_mapping)} room mappings")
    print(f"Unmapped rooms: {len(unmapped_rooms)}")

    print("Loading enrollments...")
    enrollments = load_enrollment_counts(ENROLLMENTS_PATH)

    print(f"Loaded {len(enrollments)} enrollment records")

    print("\n========== BUILD SECTIONS ==========")

    sections = build_sections(
        courses=courses,
        enrollment_counts=enrollments,
        resource_mapping=resource_mapping,
    )

    print(f"Generated {len(sections)} sections")

    print("\n========== BUILD SESSIONS ==========")
    for course_id in ["AS1001", "AS1002"]:
        course = next(
            (
                course
                for course in courses
                if str(course.course_id).strip().upper() == course_id
            ),
            None,
        )

        print(f"\n{course_id}")
        print(course)

        if course is not None:
            print("course_id:", course.course_id)
            print("companion:", course.companion_course_id)
            print("type:", course.course_type)
            print("lecture_hours:", course.lecture_hours)
            print("exercise_hours:", course.exercise_hours)
            print("lab_hours:", course.lab_hours)
            print("project_hours:", course.project_hours)
            print("assignment_hours:", course.assignment_hours)
            print("thesis_hours:", course.thesis_hours)
    sessions = build_sessions(
        sections=sections,
        courses=courses,
        rooms=rooms,
        resource_mapping=resource_mapping,
    )

    print(f"Generated {len(sessions)} sessions")

    print("\n========== SAMPLE ==========")

    print("\nFirst 5 Sections")
    for s in sections[:5]:
        print(s)

    print("\nFirst 5 Sessions")
    for s in sessions[:5]:
        print(s)

    lecture = sum(x.session_type == "LECTURE" for x in sessions)
    lab = sum(x.session_type == "LAB" for x in sessions)
    practical = sum(x.session_type == "PRACTICAL" for x in sessions)

    print("\n========== SUMMARY ==========")
    print(f"Courses  : {len(courses)}")
    print(f"Sections : {len(sections)}")
    print(f"Sessions : {len(sessions)}")
    print(f"Lecture  : {lecture}")
    print(f"Lab      : {lab}")
    print(f"Practical: {practical}")


if __name__ == "__main__":
    main()
