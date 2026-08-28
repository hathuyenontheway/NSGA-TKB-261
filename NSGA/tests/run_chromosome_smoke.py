"""Run the 589-session acceptance test without requiring pytest."""
from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from core.assignment import create_random_chromosome, validate_chromosome_structure
from core.build_problem import BuildPolicy, build_problem_instance
from data.prepare_data import prepare_data


def main() -> None:
    prepared = prepare_data(
        PROJECT_DIR / "data", track="HK_CHINH", semester_id="HK1"
    )
    mapped_courses = frozenset(
        course_id
        for course_id in prepared.courses
        if prepared.course_to_rooms.get(course_id)
    )
    problem = build_problem_instance(
        prepared,
        BuildPolicy(mandatory_course_ids=mapped_courses),
    )
    chromosome = create_random_chromosome(problem, random.Random(42))
    structural_errors = validate_chromosome_structure(problem, chromosome)

    assert len(prepared.courses) == 696
    assert len(mapped_courses) == 589
    assert len(problem.sections) == 589
    assert len(problem.sessions) == 589
    assert len(problem.gene_domains) == 589
    assert len(chromosome.genes) == 589
    assert not any(domain.is_empty for domain in problem.gene_domains)
    assert not structural_errors

    issue_counts = Counter(issue.code for issue in prepared.issues)
    print("PASS: chromosome input is structurally valid")
    print(f"KHGD courses       : {len(prepared.courses)}")
    print(f"Mapped courses     : {len(mapped_courses)}")
    print(f"Teaching weeks     : {len(problem.weeks)}")
    print(f"Sections/sessions  : {len(problem.sessions)}")
    print(f"Chromosome genes   : {len(chromosome.genes)}")
    print(f"Data issue summary : {dict(sorted(issue_counts.items()))}")


if __name__ == "__main__":
    main()
