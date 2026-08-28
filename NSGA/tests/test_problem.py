import random
from pathlib import Path
from core.assignment import create_random_chromosome, validate_chromosome_structure
from core.build_problem import BuildPolicy, build_problem_instance
from data.prepare_data import prepare_data

DATA = Path(__file__).parents[1] / "data"


def test_problem_and_chromosome_for_mapped_courses():
    prepared = prepare_data(DATA, track="HK_CHINH", semester_id="HK1")
    mapped = frozenset(cid for cid in prepared.courses if prepared.course_to_rooms.get(cid))
    problem = build_problem_instance(prepared, BuildPolicy(mandatory_course_ids=mapped))
    assert len(mapped) == 589
    assert len(problem.sections) == 589
    assert len(problem.sessions) == 589
    assert len(problem.gene_domains) == 589
    assert not any(domain.is_empty for domain in problem.gene_domains)
    chromosome = create_random_chromosome(problem, random.Random(42))
    assert len(chromosome.genes) == 589
    assert validate_chromosome_structure(problem, chromosome) == []
