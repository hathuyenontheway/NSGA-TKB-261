"""Command-line entry point for the NSGA-III timetable optimizer.

Run from this directory with ``python main.py`` or from the repository root
with ``python NSGA/main.py``. Configuration paths are resolved relative to
this file so both invocation styles behave the same way.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Iterable


PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from core.assignment import expand_occurrences  # noqa: E402
from core.build_problem import BuildPolicy, build_problem_instance  # noqa: E402
from data.prepare_data import prepare_data  # noqa: E402
from optimizer.nsga3 import NSGA3Config, run_nsga3  # noqa: E402


OBJECTIVE_COLUMNS = (
    "f1_unfulfilled_registration_rate",
    "f2_incomplete_student_rate",
    "f3_student_schedule_penalty",
    "f4_saturday_session_rate",
    "f5_campus_movement_penalty",
    "f6_room_capacity_waste_rate",
    "f7_room_load_imbalance",
    "f8_lecturer_schedule_penalty"
)

DEFAULT_CONFIG: dict[str, Any] = {
    "data": {
        "directory": "data",
        "track": "HK_CHINH",
        "semester_id": "HK1",
        "registrations_file": None
    },
    "problem": {
        # Keep the same 589 mapped courses used by run_chromosome_smoke.py.
        "open_all_mapped_courses": True,
        "mandatory_course_ids": None,
        "min_elective_students": 15,
        "default_section_capacity": 60,
        "default_mandatory_students": 15,
        "allowed_days": [2, 3, 4, 5, 6, 7],
        "slots_per_day": 12,
        "default_session_slots": 3,
        "dummy_teachers_per_faculty": 3,
        "min_weeks_lecture_to_lab": 1,
        "minimum_empty_slots": 3,
        "f3_weight_pack": 0.5,
        "f3_weight_gap": 0.5
    },
    "optimizer": {
        # Short initial run, raise these after confirming the data and output.
        "n_partitions": 1,
        "population_size": 8,
        "n_offsprings": 8,
        "n_generations": 2,
        "seed": 42,
        "crossover_probability": 0.8,
        "mutation_probability": 0.2,
        "verbose": False
    },
    "output": {
        "directory": "outputs",
        "max_schedule_solutions": 10,
        "timing_report": False
    }
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_config(config_path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "PyYAML is required to read config.yaml, install dependencies with "
            "'python -m pip install -r requirements.txt'."
        ) from exc

    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Configuration root must be a YAML mapping: {config_path}")
    return _deep_merge(DEFAULT_CONFIG, raw)


def _resolve_path(value: str | Path, *, relative_to: Path = PROJECT_DIR) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = relative_to / path
    return path.resolve()


def _build_policy(prepared, settings: dict[str, Any]) -> BuildPolicy:
    configured_ids = settings.get("mandatory_course_ids")
    if configured_ids is not None:
        mandatory_ids = frozenset(str(course_id) for course_id in configured_ids)
    elif settings.get("open_all_mapped_courses", True):
        mandatory_ids = frozenset(cid for cid in prepared.courses if prepared.course_to_rooms.get(cid))
    else:
        mandatory_ids = None

    return BuildPolicy(
        mandatory_course_ids=mandatory_ids,
        min_elective_students=int(settings["min_elective_students"]),
        default_section_capacity=int(settings["default_section_capacity"]),
        default_mandatory_students=int(settings["default_mandatory_students"]),
        allowed_days=tuple(int(day) for day in settings["allowed_days"]),
        slots_per_day=int(settings["slots_per_day"]),
        default_session_slots=int(settings["default_session_slots"]),
        dummy_teachers_per_faculty=int(settings["dummy_teachers_per_faculty"]),
        min_weeks_lecture_to_lab=int(settings["min_weeks_lecture_to_lab"]),
        minimum_empty_slots=int(settings["minimum_empty_slots"]),
        f3_weight_pack=float(settings["f3_weight_pack"]),
        f3_weight_gap=float(settings["f3_weight_gap"])
    )


def _as_float_tuple(value: Any) -> tuple[float, ...]:
    if value is None:
        return ()
    return tuple(float(item) for item in value)


def _constraint_violation(individual: Any) -> float:
    value = getattr(individual, "CV", None)
    if value is None:
        return 0.0
    if hasattr(value, "__iter__"):
        return float(sum(float(item) for item in value))
    return float(value)


def _individual_rows(collection: Any) -> list[dict[str, Any]]:
    if collection is None:
        return []
    try:
        individuals = list(collection)
    except TypeError:
        individuals = [collection]

    rows = []
    for individual in individuals:
        objectives = _as_float_tuple(getattr(individual, "F", None))
        chromosome_container = getattr(individual, "X", None)
        if not objectives or chromosome_container is None:
            continue
        chromosome = chromosome_container[0]
        rank = individual.get("rank") if hasattr(individual, "get") else None
        row = {
            "chromosome": chromosome,
            "constraint_violation": _constraint_violation(individual),
            "rank": None if rank is None else int(rank)
        }
        row.update({name: value for name, value in zip(OBJECTIVE_COLUMNS, objectives)})
        rows.append(row)
    return rows


def _solution_rows(result) -> tuple[list[dict[str, Any]], str]:
    rows = _individual_rows(getattr(result, "opt", None))
    if rows:
        source = "pymoo_optimum"
    else:
        # With hard constraints, pymoo may leave opt empty when no candidate is
        # feasible. Preserve useful output by exporting the least-violating
        # members of the final population instead.
        rows = _individual_rows(getattr(result, "pop", None))
        source = "least_violation_final_population"

    rows.sort(key=lambda row: (row["constraint_violation"], *(row[name] for name in OBJECTIVE_COLUMNS)))
    return rows, source


def _write_csv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _save_outputs(
    output_dir: Path, *, problem, prepared, result, solution_rows: list[dict[str, Any]],
    solution_source: str, config: dict[str, Any], dry_run: bool
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)

    issue_counts = Counter(issue.code for issue in problem.issues)
    issue_rows = (
        {"code": issue.code, "severity": issue.severity, "message": issue.message, "entity_id": issue.entity_id or ""}
        for issue in problem.issues
    )
    _write_csv(output_dir / "data_issues.csv", ("code", "severity", "message", "entity_id"), issue_rows)

    objective_rows = []
    for solution_id, row in enumerate(solution_rows, start=1):
        objective_rows.append({
            "solution_id": solution_id,
            "constraint_violation": row["constraint_violation"],
            "rank": "" if row["rank"] is None else row["rank"],
            **{name: row[name] for name in OBJECTIVE_COLUMNS}
        })
    objective_columns = ("solution_id", "constraint_violation", "rank", *OBJECTIVE_COLUMNS)
    _write_csv(output_dir / "candidate_objectives.csv", objective_columns, objective_rows)

    schedule_rows = []
    max_solutions = max(0, int(config["output"]["max_schedule_solutions"]))
    sessions = {session.session_id: session for session in problem.sessions}
    sections = {section.section_id: section for section in problem.sections}
    scheduled_rows = solution_rows[:max_solutions]
    for solution_id, row in enumerate(scheduled_rows, start=1):
        for occurrence in expand_occurrences(problem, row["chromosome"]):
            session = sessions[occurrence.session_id]
            section = sections.get(occurrence.section_id)
            course = problem.courses.get(occurrence.course_id)
            schedule_rows.append({
                "solution_id": solution_id,
                "session_id": occurrence.session_id,
                "section_id": occurrence.section_id,
                "course_id": occurrence.course_id,
                "course_name": course.course_name if course else "",
                "session_type": session.session_type.value,
                "teacher_id": occurrence.teacher_id or "",
                "room_id": occurrence.room_id,
                "campus": "" if occurrence.campus is None else occurrence.campus,
                "week": occurrence.week,
                "day": occurrence.day,
                "start_slot": occurrence.start_slot,
                "end_slot": occurrence.end_slot,
                "expected_students": "" if section is None else section.expected_students
            })
    schedule_columns = (
        "solution_id", "session_id", "section_id", "course_id", "course_name", "session_type", "teacher_id",
        "room_id", "campus", "week", "day", "start_slot", "end_slot", "expected_students"
    )
    _write_csv(output_dir / "schedule_occurrences.csv", schedule_columns, schedule_rows)

    algorithm = getattr(result, "algorithm", None)
    evaluator = getattr(algorithm, "evaluator", None)
    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "data": {
            "course_count": len(prepared.courses),
            "room_count": len(prepared.rooms),
            "teaching_week_count": len(problem.weeks),
            "registration_count": len(problem.registrations),
            "section_count": len(problem.sections),
            "session_count": len(problem.sessions),
            "gene_count": len(problem.gene_domains),
            "data_issue_counts": dict(sorted(issue_counts.items()))
        },
        "optimizer": config["optimizer"],
        "n_evaluations": getattr(evaluator, "n_eval", None),
        "generations_completed": getattr(algorithm, "n_gen", None),
        "pareto_solution_count": len(solution_rows) if solution_source == "pymoo_optimum" else 0,
        "candidate_count": len(solution_rows),
        "candidate_selection_source": solution_source,
        "schedule_solution_count": len(scheduled_rows),
        "objective_columns": list(OBJECTIVE_COLUMNS),
        "final_assignment_evaluation": "not run, objective values come from the fast evolutionary evaluator"
    }
    _write_json(output_dir / "run_summary.json", metadata)
    return metadata


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the NSGA-III timetable optimizer.")
    parser.add_argument("--config", type=Path, default=PROJECT_DIR / "config.yaml", help="YAML configuration")
    parser.add_argument("--data-dir", type=Path, help="Override data.directory")
    parser.add_argument("--track", help="Override data.track")
    parser.add_argument("--semester-id", help="Override data.semester_id")
    parser.add_argument("--registrations", type=Path, help="Optional student registration CSV")
    parser.add_argument("--population-size", type=int, help="Override optimizer.population_size")
    parser.add_argument("--generations", type=int, help="Override optimizer.n_generations")
    parser.add_argument("--seed", type=int, help="Override optimizer.seed")
    parser.add_argument("--output-dir", type=Path, help="Override output.directory")
    parser.add_argument("--verbose", action="store_true", help="Show pymoo generation output")
    parser.add_argument("--timing", action=argparse.BooleanOptionalAction, help="Override output.timing_report")
    parser.add_argument("--dry-run", action="store_true", help="Load data and build the problem without optimization")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    working_directory = Path.cwd()
    config_path = _resolve_path(args.config, relative_to=working_directory)
    config = _load_config(config_path)

    if args.data_dir is not None:
        config["data"]["directory"] = str(_resolve_path(args.data_dir, relative_to=working_directory))
    if args.track is not None:
        config["data"]["track"] = args.track
    if args.semester_id is not None:
        config["data"]["semester_id"] = args.semester_id
    if args.registrations is not None:
        config["data"]["registrations_file"] = str(_resolve_path(args.registrations, relative_to=working_directory))
    if args.population_size is not None:
        config["optimizer"]["population_size"] = args.population_size
    if args.generations is not None:
        config["optimizer"]["n_generations"] = args.generations
    if args.seed is not None:
        config["optimizer"]["seed"] = args.seed
    if args.output_dir is not None:
        config["output"]["directory"] = str(_resolve_path(args.output_dir, relative_to=working_directory))
    if args.verbose:
        config["optimizer"]["verbose"] = True

    timing_enabled = args.timing if args.timing is not None else config["output"]["timing_report"]
    if not isinstance(timing_enabled, bool):
        raise ValueError("output.timing_report must be true or false")

    timings: dict[str, float | None] | None = {"optimization": None} if timing_enabled else None
    pipeline_started = perf_counter() if timings is not None else 0.0
    data_config = config["data"]
    data_dir = _resolve_path(data_config["directory"])
    track = str(data_config["track"])
    semester_id = str(data_config["semester_id"])
    registrations_value = data_config.get("registrations_file")
    registrations_path = _resolve_path(registrations_value, relative_to=data_dir) if registrations_value else None
    if registrations_path is not None and not registrations_path.is_file():
        raise FileNotFoundError(f"Registrations file not found: {registrations_path}")

    registrations_file = str(registrations_path) if registrations_path else None
    prepared = prepare_data(data_dir, track=track, semester_id=semester_id, registrations_file=registrations_file)
    policy = _build_policy(prepared, config["problem"])
    problem = build_problem_instance(prepared, policy)
    if timings is not None:
        timings["data_preparation_and_problem_build"] = round(perf_counter() - pipeline_started, 6)

    print(
        f"Loaded {len(prepared.courses)} courses, {len(prepared.rooms)} rooms, "
        f"{len(problem.weeks)} teaching weeks, {len(problem.sessions)} sessions, {len(problem.registrations)} registrations."
    )
    if not problem.registrations:
        print("WARNING: no registration CSV was loaded, student-based objectives and assignments are not representative.")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output_root = _resolve_path(config["output"]["directory"])
    output_dir = output_root / run_id

    result = None
    solution_rows: list[dict[str, Any]] = []
    solution_source = "none"
    if not args.dry_run:
        optimizer_cfg = config["optimizer"]
        population_size = optimizer_cfg.get("population_size")
        n_offsprings = optimizer_cfg.get("n_offsprings")
        seed = optimizer_cfg.get("seed")
        nsga_config = NSGA3Config(
            n_partitions=int(optimizer_cfg["n_partitions"]),
            population_size=int(population_size) if population_size is not None else None,
            n_offsprings=int(n_offsprings) if n_offsprings is not None else None,
            n_generations=int(optimizer_cfg["n_generations"]),
            seed=int(seed) if seed is not None else None,
            crossover_probability=float(optimizer_cfg["crossover_probability"]),
            mutation_probability=float(optimizer_cfg["mutation_probability"])
        )
        verbose = bool(optimizer_cfg.get("verbose", False))
        optimization_started = perf_counter() if timings is not None else 0.0
        result = run_nsga3(problem_instance=problem, config=nsga_config, verbose=verbose)
        if timings is not None:
            timings["optimization"] = round(perf_counter() - optimization_started, 6)
        solution_rows, solution_source = _solution_rows(result)

    output_started = perf_counter() if timings is not None else 0.0
    metadata = _save_outputs(
        output_dir, problem=problem, prepared=prepared, result=result, solution_rows=solution_rows,
        solution_source=solution_source, config=config, dry_run=args.dry_run
    )
    if timings is not None:
        finished_at = perf_counter()
        timings["output_writing"] = round(finished_at - output_started, 6)
        timings["total"] = round(finished_at - pipeline_started, 6)
        timing_path = output_dir / "timing_report.json"
        _write_json(timing_path, {
            "run_id": run_id,
            "dry_run": args.dry_run,
            "data": {"track": track, "semester_id": semester_id, **metadata["data"]},
            "optimizer": metadata["optimizer"],
            "n_evaluations": metadata["n_evaluations"],
            "timings_seconds": timings
        })

        print(f"Data/build time     : {timings['data_preparation_and_problem_build']:.3f} s")
        optimization_seconds = timings["optimization"]
        if optimization_seconds is not None:
            print(f"Optimization time   : {optimization_seconds:.3f} s")
        print(f"Total elapsed       : {timings['total']:.3f} s")
        print(f"Timing report       : {timing_path}")

    print(f"Run directory       : {output_dir}")
    print(f"Candidates exported : {len(solution_rows)} ({solution_source})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error
