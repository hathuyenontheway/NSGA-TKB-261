from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
root_path = str(ROOT_DIR)
if root_path in sys.path:
    sys.path.remove(root_path)
sys.path.insert(0, root_path)

from builders.build_sections import build_sections
from builders.build_sessions import build_sessions
from models.chromosome import Chromosome
from models.gene import Gene
from models.session import SessionMetadata
from nsga2.constraints import (
    check_allowed_room,
    check_lecture_before_lab,
    check_room_capacity,
    check_room_conflicts,
    check_session_start,
    check_valid_day,
    evaluate,
)
from preprocessing.enrollments import load_enrollment_counts
from preprocessing.parse_courses import parse_courses
from preprocessing.parse_rooms import parse_rooms


PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
MAPPINGS_DIR = ROOT_DIR / "preprocessing" / "mappings"

COURSES_PATH = PROCESSED_DATA_DIR / "mh.csv"
ROOMS_PATH = PROCESSED_DATA_DIR / "room261.csv"
ENROLLMENTS_PATH = PROCESSED_DATA_DIR / "kq_nv.csv"
COURSE_MAPPING_PATH = MAPPINGS_DIR / "course_resource_mapping.csv"
ROOM_MAPPING_PATH = MAPPINGS_DIR / "room_resource_mapping.csv"

MAX_SLOT = 12

# Temporary compatibility for mappings generated before the inventory prompt
# was restricted. Re-run the classifier to replace these legacy labels.
LEGACY_RESOURCE_FALLBACK = {
    "BIOLOGY_LAB": "CHEMISTRY_LAB",
    "GEOLOGY_LAB": "OTHER_SPECIAL",
}


def load_mapping(
    path: Path,
    id_column: str,
) -> dict[str, str]:
    frame = pd.read_csv(path, dtype=str)
    mapping = (
        frame
        .dropna(subset=[id_column, "resource_type"])
        .assign(
            **{
                id_column: (
                    lambda df: df[id_column].str.strip().str.upper()
                ),
                "resource_type": (
                    lambda df: (
                        df["resource_type"].str.strip().str.upper()
                    )
                ),
            }
        )
        .drop_duplicates(subset=[id_column], keep="last")
        .set_index(id_column)["resource_type"]
        .to_dict()
    )
    return {
        item_id: LEGACY_RESOURCE_FALLBACK.get(
            resource_type,
            resource_type,
        )
        for item_id, resource_type in mapping.items()
    }


def build_test_data():
    courses = list(
        parse_courses(pd.read_csv(COURSES_PATH)).values()
    )
    rooms_by_id = parse_rooms(pd.read_csv(ROOMS_PATH))
    rooms = list(rooms_by_id.values())

    course_mapping = load_mapping(
        COURSE_MAPPING_PATH,
        "course_id",
    )
    room_mapping = load_mapping(
        ROOM_MAPPING_PATH,
        "room_id",
    )

    for room in rooms:
        normalized_id = str(room.room_id).strip().upper()
        room.resource_type = room_mapping.get(
            normalized_id,
            "UNKNOWN",
        )

    enrollments = load_enrollment_counts(ENROLLMENTS_PATH)
    sections = build_sections(
        courses=courses,
        enrollment_counts=enrollments,
        resource_mapping=course_mapping,
    )
    sessions = build_sessions(
        sections=sections,
        courses=courses,
        rooms=rooms,
        resource_mapping=course_mapping,
    )

    return (
        courses,
        {room.room_id: room for room in rooms},
        sections,
        sessions,
    )


def random_initialize(
    sessions: list[SessionMetadata],
    rng: random.Random,
) -> Chromosome:
    genes: list[Gene] = []

    for session in sessions:
        if not session.allowed_rooms:
            raise ValueError(
                f"Session {session.session_id} has no allowed room"
            )

        max_start_slot = max(
            1,
            MAX_SLOT - session.duration + 1,
        )
        session_type = session.session_type.upper()
        if session_type in {"LAB", "PRACTICAL"}:
            valid_starts = [
                slot
                for slot in (2, 8)
                if slot <= max_start_slot
            ]
        else:
            valid_starts = list(
                range(1, min(12, max_start_slot) + 1)
            )

        genes.append(
            Gene(
                session_id=session.session_id,
                room_id=rng.choice(
                    sorted(session.allowed_rooms)
                ),
                day=rng.randint(2, 7),
                start_slot=rng.choice(valid_starts),
                start_week=1,
                week_pattern=0,
            )
        )

    return Chromosome(genes=genes)


def test_individual_constraints(
    chromosome: Chromosome,
    sessions: list[SessionMetadata],
    rooms: dict,
) -> None:
    gene = chromosome.genes[0]
    session = sessions[gene.session_id]

    assert check_valid_day(gene)
    assert check_session_start(gene, session)
    assert check_allowed_room(gene, session)
    assert check_room_capacity(gene, session, rooms)

    invalid_room_gene = Gene(
        session_id=gene.session_id,
        room_id="ABC",
        day=gene.day,
        start_slot=gene.start_slot,
        start_week=gene.start_week,
        week_pattern=gene.week_pattern,
    )
    assert not check_allowed_room(invalid_room_gene, session)

    print("Individual constraints: OK")
    print("Invalid allowed-room case: OK")


def make_synthetic_sessions(room_id: str) -> list[SessionMetadata]:
    lecture = SessionMetadata(
        session_id=0,
        course_id="TEST101",
        section_id="TEST101_L01",
        session_type="LECTURE",
        class_size=10,
        duration=3,
        total_weeks=5,
        min_lab_offset=0,
        has_midterm=False,
        allowed_rooms=frozenset({room_id}),
        required_room_type="GENERAL",
        campus=None,
        parent_session_id=None,
    )
    lab = SessionMetadata(
        session_id=1,
        course_id="TEST101",
        section_id="TEST101_B01",
        session_type="LAB",
        class_size=10,
        duration=3,
        total_weeks=3,
        min_lab_offset=2,
        has_midterm=False,
        allowed_rooms=frozenset({room_id}),
        required_room_type="GENERAL",
        campus=None,
        parent_session_id=0,
    )
    return [lecture, lab]


def test_room_conflict(room_id: str) -> None:
    sessions = make_synthetic_sessions(room_id)
    chromosome = Chromosome(
        genes=[
            Gene(0, 2, 1, room_id, 1, 0),
            Gene(1, 2, 1, room_id, 1, 0),
        ]
    )
    conflicts = check_room_conflicts(chromosome, sessions)
    assert conflicts == 1, conflicts
    print("Intentional room conflict: OK (1 violation)")


def test_lecture_before_lab(room_id: str) -> None:
    sessions = make_synthetic_sessions(room_id)

    invalid = Chromosome(
        genes=[
            Gene(0, 2, 5, room_id, 1, 0),
            Gene(1, 3, 4, room_id, 2, 0),
        ]
    )
    assert check_lecture_before_lab(invalid, sessions) == 1

    valid = Chromosome(
        genes=[
            Gene(0, 2, 1, room_id, 1, 0),
            Gene(1, 3, 4, room_id, 2, 0),
        ]
    )
    assert check_lecture_before_lab(valid, sessions) == 0
    print("Lecture-before-lab cases: OK")


def stress_test(
    iterations: int,
    sessions: list[SessionMetadata],
    rooms: dict,
    rng: random.Random,
) -> None:
    for index in range(iterations):
        chromosome = random_initialize(sessions, rng)
        evaluate(chromosome, sessions, rooms)
        print(
            f"{index + 1:03d}: "
            f"hard={chromosome.hard_constraint_violation}, "
            f"objectives={chromosome.objectives}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke and stress tests for NSGA-II constraints"
    )
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    courses, rooms, sections, sessions = build_test_data()

    print(f"Courses: {len(courses)}")
    print(f"Rooms: {len(rooms)}")
    print(f"Sections: {len(sections)}")
    print(f"Sessions: {len(sessions)}")
    print(
        "Session types:",
        dict(Counter(s.session_type for s in sessions)),
    )

    chromosome = random_initialize(sessions, rng)
    evaluate(chromosome, sessions, rooms)
    print(
        "Initial chromosome:",
        chromosome.hard_constraint_violation,
        chromosome.objectives,
    )

    test_individual_constraints(chromosome, sessions, rooms)
    test_room_conflict(next(iter(rooms)))
    test_lecture_before_lab(next(iter(rooms)))

    stress_test(
        iterations=args.iterations,
        sessions=sessions,
        rooms=rooms,
        rng=rng,
    )
    print(f"Completed {args.iterations} evaluations without exception.")


if __name__ == "__main__":
    main()
