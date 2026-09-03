from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

from core.assignment import (
    Occurrence as _Occurrence,
    assign_students,
    calculate_student_impact,
    expand_occurrences as _expand_occurrences,
    group_by_key as _group_by_key,
    is_alternating_session as _is_alternating_session,
    occurrence_weeks as _occurrence_weeks,
    section_by_id as _section_by_id,
    session_by_id as _session_by_id,
    slots_overlap as _slots_overlap,
    teaching_week_numbers as _teaching_week_numbers,
)
from core.models import AssignmentResult, Chromosome, EvaluationResult, ProblemInstance, Violation

# ---------------------------------------------------------------------------
# Violation-specific helpers (kept local — not generic occurrence handling)
# ---------------------------------------------------------------------------

def _pairwise_overlap_violations(
    group: list[_Occurrence], code: str, priority: str, message: str, entity_field: str,
) -> list[Violation]:
    """Flag overlapping session pairs that share the same day, week, and resource."""
    violations = []
    for occ_a, occ_b in combinations(group, 2):
        if occ_a.session_id == occ_b.session_id:
            continue
        if _slots_overlap(occ_a, occ_b):
            violations.append(Violation(
                code=code, priority=priority, severity="ERROR", message=message,
                location={"day": occ_a.day, "week": occ_a.week,
                          "slots": [occ_a.start_slot, occ_a.end_slot, occ_b.start_slot, occ_b.end_slot]},
                affected_entities={entity_field: getattr(occ_a, entity_field),
                                    "sessions": [occ_a.session_id, occ_b.session_id],
                                    "sections": [occ_a.section_id, occ_b.section_id]},
            ))
    return violations


# ---------------------------------------------------------------------------
# Evaluation context — computed ONCE per chromosome and threaded through every
# check/objective, instead of each one independently re-running
# `_expand_occurrences` (previously ~9 full re-expansions per evaluation, plus
# an extra re-expansion per lecture/lab pair inside check_lecture_lab).
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class _EvalContext:
    occurrences: list[_Occurrence]
    occ_by_session: dict[int, list[_Occurrence]] = field(default_factory=dict)
    occ_by_section: dict[str, list[_Occurrence]] = field(default_factory=dict)
    student_sections: dict[str, list[str]] = field(default_factory=dict)


def _build_context(
    problem: ProblemInstance, chromosome: Chromosome, assignment: AssignmentResult | None,
) -> _EvalContext:
    occurrences = _expand_occurrences(problem, chromosome)

    occ_by_session: dict[int, list[_Occurrence]] = defaultdict(list)
    occ_by_section: dict[str, list[_Occurrence]] = defaultdict(list)
    for occ in occurrences:
        occ_by_session[occ.session_id].append(occ)
        occ_by_section[occ.section_id].append(occ)

    student_sections: dict[str, list[str]] = defaultdict(list)
    if assignment is not None:
        for sa in assignment.assignments:
            if sa.section_id is not None:
                student_sections[sa.student_id].append(sa.section_id)

    return _EvalContext(
        occurrences=occurrences, occ_by_session=dict(occ_by_session),
        occ_by_section=dict(occ_by_section), student_sections=dict(student_sections),
    )


def _student_occurrences(ctx: _EvalContext, section_ids: list[str]) -> list[_Occurrence]:
    return [occ for sid in section_ids for occ in ctx.occ_by_section.get(sid, [])]


# ---------------------------------------------------------------------------
# Hard constraints — check_*() -> list[Violation]
# ---------------------------------------------------------------------------

def check_mandatory_courses(problem: ProblemInstance, chromosome: Chromosome, ctx: _EvalContext | None = None) -> list[Violation]:
    """Ensure every mandatory course has at least one session scheduled by the chromosome."""
    genes_by_session = {g.session_id: g for g in chromosome.genes}
    sessions = _session_by_id(problem)
    scheduled_courses = {
        sessions[sid].course_id for sid in genes_by_session if sid in sessions
    }
    violations: list[Violation] = []
    for course_id in problem.mandatory_course_ids:
        if course_id not in scheduled_courses:
            violations.append(Violation(
                code="MANDATORY_COURSE_NOT_SCHEDULED", priority="HARD", severity="ERROR",
                message="A mandatory course has no scheduled session in this chromosome.",
                location={}, affected_entities={"course_id": course_id},
                current_value=False, required_value=True,
            ))
    return violations


def _lunch_break_violation(gene, session) -> Violation | None:
    """Check that the session does not occupy the lunch-break slot (slot 6).

    FIX: previously only checked `start_slot == 6`, so a 3-slot session
    starting at slot 5 (occupying 5-6-7) silently ran through lunch without
    being flagged. Now checks the whole occupied span.
    """
    LUNCH_SLOT = 6
    end_slot = gene.start_slot + session.duration_slots - 1
    if gene.start_slot <= LUNCH_SLOT <= end_slot:
        return Violation(
            code="LUNCH_BREAK_VIOLATION", priority="HARD", severity="ERROR",
            message="Session occupies the lunch break slot (slot 6).",
            location={"start_slot": gene.start_slot, "end_slot": end_slot},
            affected_entities={"session_id": gene.session_id},
            current_value=[gene.start_slot, end_slot], required_value="must not span slot 6",
        )
    return None


def check_calendar(problem: ProblemInstance, chromosome: Chromosome, ctx: _EvalContext | None = None) -> list[Violation]:
    """Check that every scheduled occurrence has valid weeks, days, and time slots."""
    violations: list[Violation] = []
    sessions = _session_by_id(problem)
    for gene in chromosome.genes:
        session = sessions.get(gene.session_id)
        if session is None:
            continue
        step = 2 if _is_alternating_session(problem, session) else 1
        weeks = _occurrence_weeks(problem, gene.start_week, session.total_weeks, step)
        if len(weeks) < session.total_weeks:
            violations.append(Violation(
                code="CALENDAR_INSUFFICIENT_WEEKS", priority="HARD", severity="ERROR",
                message="Not enough teaching weeks remain from the chosen start_week to cover total_weeks.",
                location={"start_week": gene.start_week}, affected_entities={"session_id": session.session_id},
                current_value=len(weeks), required_value=session.total_weeks,
            ))
        # FIX: gene.start_week was never checked against the session's own
        # allowed_start_weeks domain — only against the global teaching-week
        # calendar (via CALENDAR_INSUFFICIENT_WEEKS above). If a session's
        # domain is ever narrower than the full calendar this let invalid
        # start weeks through silently.
        if session.allowed_start_weeks and gene.start_week not in session.allowed_start_weeks:
            violations.append(Violation(
                code="CALENDAR_INVALID_START_WEEK", priority="HARD", severity="ERROR",
                message="Gene start_week is outside the session's allowed start weeks.",
                location={"start_week": gene.start_week}, affected_entities={"session_id": session.session_id},
                current_value=gene.start_week, required_value=list(session.allowed_start_weeks),
            ))
        if gene.day not in session.allowed_days:
            violations.append(Violation(
                code="CALENDAR_INVALID_DAY", priority="HARD", severity="ERROR",
                message="Gene day is outside the session's allowed days.",
                location={"day": gene.day}, affected_entities={"session_id": session.session_id},
                current_value=gene.day, required_value=list(session.allowed_days),
            ))
        if gene.start_slot not in session.allowed_start_slots:
            violations.append(Violation(
                code="CALENDAR_INVALID_SLOT", priority="HARD", severity="ERROR",
                message="Gene start_slot is outside the session's allowed start slots.",
                location={"start_slot": gene.start_slot}, affected_entities={"session_id": session.session_id},
                current_value=gene.start_slot, required_value=list(session.allowed_start_slots),
            ))
        lunch_violation = _lunch_break_violation(gene, session)
        if lunch_violation is not None:
            violations.append(lunch_violation)
    return violations


def check_lab_session_spacing(problem: ProblemInstance, chromosome: Chromosome, ctx: _EvalContext | None = None) -> list[Violation]:
    """LabSessionSpacingConstraint (spec doc 2): a lab must not meet in two
    consecutive teaching weeks. This was missing from the previous checks —
    in practice it's usually already implied by the alternating-week step
    used for lecture/lab pairs, but is validated explicitly here in case a
    lab session's step/domain is ever configured differently.
    """
    from core.models import CourseType  # local import to avoid unused import when unneeded elsewhere

    violations: list[Violation] = []
    sessions = _session_by_id(problem)
    teaching_weeks = _teaching_week_numbers(problem)
    week_index = {w: i for i, w in enumerate(teaching_weeks)}
    for gene in chromosome.genes:
        session = sessions.get(gene.session_id)
        if session is None or session.session_type != CourseType.LAB:
            continue
        step = 2 if _is_alternating_session(problem, session) else 1
        weeks = _occurrence_weeks(problem, gene.start_week, session.total_weeks, step)
        for w1, w2 in zip(weeks, weeks[1:]):
            idx1, idx2 = week_index.get(w1), week_index.get(w2)
            if idx1 is not None and idx2 is not None and idx2 - idx1 < 2:
                violations.append(Violation(
                    code="LAB_SESSION_SPACING", priority="HARD", severity="ERROR",
                    message="Lab meets in two consecutive teaching weeks.",
                    location={"weeks": [w1, w2]}, affected_entities={"session_id": session.session_id},
                    current_value=idx2 - idx1, required_value=">= 2",
                ))
    return violations


def check_room_compatibility(problem: ProblemInstance, chromosome: Chromosome, ctx: _EvalContext | None = None) -> list[Violation]:
    """Check that each session is assigned to an allowed room with the correct resource type
    and, where recognizable, the correct physical room type (lecture hall vs lab)."""
    violations: list[Violation] = []
    sessions = _session_by_id(problem)
    # ASSUMPTION: room_type / session_type use the same vocabulary as CourseType
    # ("LECTURE"/"LAB"/...). If your data uses a different vocabulary for
    # Room.room_type (e.g. Vietnamese labels), adjust this mapping — the check
    # is skipped (not flagged) for any room_type value it doesn't recognize,
    # so it fails safe rather than raising false positives.
    _RECOGNIZED_ROOM_TYPES = {"LECTURE", "LAB"}
    for gene in chromosome.genes:
        session = sessions.get(gene.session_id)
        if session is None:
            continue
        if gene.room_id not in session.allowed_room_ids:
            violations.append(Violation(
                code="ROOM_NOT_ALLOWED", priority="HARD", severity="ERROR",
                message="Room is not in the session's allowed room list.",
                location={"room_id": gene.room_id}, affected_entities={"session_id": session.session_id},
                current_value=gene.room_id, required_value=list(session.allowed_room_ids),
            ))
            continue
        room = problem.rooms.get(gene.room_id)
        course = problem.courses.get(session.course_id)
        if room and course and course.resource_type != "GENERAL" and room.resource_type != course.resource_type:
            violations.append(Violation(
                code="ROOM_RESOURCE_MISMATCH", priority="HARD", severity="ERROR",
                message="Room resource_type does not match the course's required resource_type.",
                location={"room_id": gene.room_id}, affected_entities={"session_id": session.session_id},
                current_value=room.resource_type, required_value=course.resource_type,
            ))
        if room and room.room_type and room.room_type.upper() in _RECOGNIZED_ROOM_TYPES:
            expected = session.session_type.value if session.session_type.value in _RECOGNIZED_ROOM_TYPES else None
            if expected and room.room_type.upper() != expected:
                violations.append(Violation(
                    code="ROOM_TYPE_MISMATCH", priority="HARD", severity="ERROR",
                    message="Room's physical type (lecture hall vs lab) does not match the session type.",
                    location={"room_id": gene.room_id}, affected_entities={"session_id": session.session_id},
                    current_value=room.room_type, required_value=expected,
                ))
    return violations


def check_room_capacity(problem: ProblemInstance, chromosome: Chromosome, ctx: _EvalContext | None = None) -> list[Violation]:
    """Section's actual student count must not exceed the assigned room's capacity.

    FIX: previously compared `section.max_capacity` (a fixed default, e.g. 60)
    against room capacity — this could fail a section whose *real* enrollment
    (`expected_students`) fits comfortably in a smaller room, and it was
    inconsistent with the F6 soft objective which already uses
    `expected_students` for the same notion of "class size". Switched to
    `expected_students` so the hard constraint and the soft objective agree
    on what "sĩ số lớp" means. If the intent is actually to reserve room for
    later capacity growth up to `max_capacity`, swap the field back.
    """
    violations: list[Violation] = []
    sessions = _session_by_id(problem)
    sections = _section_by_id(problem)
    for gene in chromosome.genes:
        session = sessions.get(gene.session_id)
        room = problem.rooms.get(gene.room_id)
        if session is None or room is None:
            continue
        section = sections.get(session.section_id)
        if section and section.expected_students > room.capacity:
            violations.append(Violation(
                code="ROOM_CAPACITY_EXCEEDED", priority="HARD", severity="ERROR",
                message="Section's expected student count exceeds the assigned room's capacity.",
                location={"room_id": gene.room_id}, affected_entities={"section_id": section.section_id},
                current_value=section.expected_students, required_value=room.capacity,
            ))
    return violations


def check_room_conflicts(problem: ProblemInstance, chromosome: Chromosome, ctx: _EvalContext | None = None) -> list[Violation]:
    """No room may host two overlapping sessions at the same day+week."""
    ctx = ctx or _build_context(problem, chromosome, None)
    groups = _group_by_key(ctx.occurrences, lambda o: (o.room_id, o.day, o.week))
    violations: list[Violation] = []
    for group in groups.values():
        if len(group) > 1:
            violations += _pairwise_overlap_violations(
                group, "ROOM_CONFLICT", "HARD", "Two sessions overlap in the same room.", "room_id")
    return violations


def check_section_conflicts(problem: ProblemInstance, chromosome: Chromosome, ctx: _EvalContext | None = None) -> list[Violation]:
    """No section may have two overlapping occurrences of its own sessions."""
    ctx = ctx or _build_context(problem, chromosome, None)
    groups = _group_by_key(ctx.occurrences, lambda o: (o.section_id, o.day, o.week))
    violations: list[Violation] = []
    for group in groups.values():
        if len(group) > 1:
            violations += _pairwise_overlap_violations(
                group, "SECTION_CONFLICT", "HARD", "A section has overlapping sessions.", "section_id")
    return violations


def check_student_assignment(
    problem: ProblemInstance, chromosome: Chromosome, assignment: AssignmentResult | None = None,
    ctx: _EvalContext | None = None,
) -> list[Violation]:
    """A student must not be assigned to two sections whose occurrences overlap."""
    if assignment is None:
        return []
    ctx = ctx or _build_context(problem, chromosome, assignment)
    violations: list[Violation] = []
    for student_id, section_ids in ctx.student_sections.items():
        occs = _student_occurrences(ctx, section_ids)
        groups = _group_by_key(occs, lambda o: (o.day, o.week))
        for group in groups.values():
            if len(group) > 1:
                violations += _pairwise_overlap_violations(
                    group, "STUDENT_CONFLICT", "HARD", "Student has overlapping sections.", "section_id")
    return violations


def _lecture_lab_time_conflict_violations(session, parent, ctx: _EvalContext) -> list[Violation]:
    """Check that lecture and companion lab sessions do not overlap."""
    combined = ctx.occ_by_session.get(session.session_id, []) + ctx.occ_by_session.get(parent.session_id, [])
    groups = _group_by_key(combined, lambda o: (o.day, o.week))
    violations: list[Violation] = []
    for group in groups.values():
        if len(group) > 1:
            violations += _pairwise_overlap_violations(
                group, "LECTURE_LAB_TIME_CONFLICT", "HARD",
                "Lecture and its companion lab overlap in day/slot/week.", "section_id")
    return violations


def check_lecture_lab(
    problem: ProblemInstance, chromosome: Chromosome, min_weeks_lecture_to_lab: int | None = None,
    ctx: _EvalContext | None = None,
) -> list[Violation]:
    """Checks whether the Lecture and Lab sessions of the same course are scheduled compatibly.

    PERF FIX: previously called `_expand_occurrences` (a full expansion of the
    whole chromosome) inside the per-session loop, i.e. once per lecture/lab
    pair — O(pairs x total genes). Now expands once via the shared context and
    just looks up each session's precomputed occurrences.
    """
    if min_weeks_lecture_to_lab is None:
        min_weeks_lecture_to_lab = problem.min_weeks_lecture_to_lab
    ctx = ctx or _build_context(problem, chromosome, None)
    violations: list[Violation] = []
    sessions = _session_by_id(problem)
    teaching_weeks = _teaching_week_numbers(problem)
    genes_by_session = {g.session_id: g for g in chromosome.genes}
    for session in problem.sessions:
        if session.parent_session_id is None:
            continue
        parent = sessions.get(session.parent_session_id)
        child_gene = genes_by_session.get(session.session_id)
        parent_gene = genes_by_session.get(session.parent_session_id) if parent else None
        if not (parent and child_gene and parent_gene):
            continue
        violations += _lecture_lab_time_conflict_violations(session, parent, ctx)
        if parent_gene.start_week not in teaching_weeks or child_gene.start_week not in teaching_weeks:
            continue  # invalid week already caught by check_calendar
        parent_week_index = teaching_weeks.index(parent_gene.start_week)
        child_week_index = teaching_weeks.index(child_gene.start_week)
        if child_week_index - parent_week_index < min_weeks_lecture_to_lab:
            violations.append(Violation(
                code="LECTURE_LAB_ORDER", priority="HARD", severity="ERROR",
                message=(
                    f"Lab must start at least {min_weeks_lecture_to_lab} teaching week(s) "
                    "after its lecture (GLOBAL default k — real per-course k not yet in data)."
                ),
                location={}, affected_entities={"session_id": session.session_id, "parent_session_id": parent.session_id},
                current_value=child_week_index - parent_week_index, required_value=f">= {min_weeks_lecture_to_lab}",
            ))
    return violations


def check_campus_travel(
    problem: ProblemInstance, chromosome: Chromosome, assignment: AssignmentResult | None = None,
    minimum_empty_slots: int | None = None, ctx: _EvalContext | None = None,
) -> list[Violation]:
    """Checks whether a student has enough travel time when moving between different campuses on the same day"""
    if minimum_empty_slots is None:
        minimum_empty_slots = problem.minimum_empty_slots
    if assignment is None:
        return []
    ctx = ctx or _build_context(problem, chromosome, assignment)

    violations: list[Violation] = []
    for student_id, section_ids in ctx.student_sections.items():
        occs = _student_occurrences(ctx, section_ids)
        for (day, week), day_occs in _group_by_key(occs, lambda o: (o.day, o.week)).items():
            ordered = sorted(day_occs, key=lambda o: o.start_slot)
            campus_moves = 0
            for prev, nxt in zip(ordered, ordered[1:]):
                if prev.campus is None or nxt.campus is None or prev.campus == nxt.campus:
                    continue
                campus_moves += 1
                gap = nxt.start_slot - prev.end_slot - 1
                if gap < minimum_empty_slots:
                    violations.append(Violation(
                        code="CAMPUS_TRAVEL_GAP_TOO_SHORT", priority="HARD", severity="ERROR",
                        message="Student does not have enough empty slots to travel between campuses.",
                        location={"day": day, "week": week,
                                  "slots": [prev.start_slot, prev.end_slot, nxt.start_slot, nxt.end_slot]},
                        affected_entities={"student_id": student_id,
                                            "sections": [prev.section_id, nxt.section_id],
                                            "campuses": [prev.campus, nxt.campus]},
                        current_value=gap, required_value=f">= {minimum_empty_slots}",
                    ))
            if campus_moves > 1:
                violations.append(Violation(
                    code="CAMPUS_TRAVEL_TOO_MANY_MOVES", priority="HARD", severity="ERROR",
                    message="Student crosses campuses more than once on the same day.",
                    location={"day": day, "week": week}, affected_entities={"student_id": student_id},
                    current_value=campus_moves, required_value="<= 1",
                ))
    return violations


# Cache for `_lecturer_load_violations`: it depends only on `problem.sections`
# / `problem.teachers`, both fixed at build time — not on the chromosome. It
# was previously recomputed from scratch on every single evaluate_fast() call
# (i.e. every chromosome, every generation). Memoized here by identity since
# a ProblemInstance is built once and reused for the life of a GA run.
_lecturer_load_cache: dict[int, list[Violation]] = {}


def _lecturer_load_violations(problem: ProblemInstance) -> list[Violation]:
    """Ensure every teacher must be assigned at least one class."""
    if not problem.teachers:
        return []  # no teacher roster
    cache_key = id(problem)
    cached = _lecturer_load_cache.get(cache_key)
    if cached is not None:
        return cached
    assigned_teachers = {section.teacher_id for section in problem.sections if section.teacher_id is not None}
    violations: list[Violation] = []
    for teacher_id in sorted(problem.teachers):
        if teacher_id not in assigned_teachers:
            violations.append(Violation(
                code="LECTURER_ZERO_LOAD", priority="HARD", severity="ERROR",
                message="A teacher has zero assigned sections.",
                location={}, affected_entities={"teacher_id": teacher_id},
                current_value=0, required_value=">= 1",
            ))
    _lecturer_load_cache[cache_key] = violations
    return violations


def check_lecturer_conflicts(problem: ProblemInstance, chromosome: Chromosome, ctx: _EvalContext | None = None) -> list[Violation]:
    """Check whether teachers are assigned valid classes."""
    ctx = ctx or _build_context(problem, chromosome, None)
    occurrences = [o for o in ctx.occurrences if o.teacher_id]
    groups = _group_by_key(occurrences, lambda o: (o.teacher_id, o.day, o.week))
    violations: list[Violation] = []
    for group in groups.values():
        if len(group) > 1:
            violations += _pairwise_overlap_violations(
                group, "LECTURER_CONFLICT", "HARD", "A teacher has overlapping sessions.", "teacher_id")
    violations += _lecturer_load_violations(problem)
    return violations


# ---------------------------------------------------------------------------
# Soft objectives — calculate_*() -> float (lower is better, unless noted)
# ---------------------------------------------------------------------------

def calculate_unfulfilled_registration_rate(
    problem: ProblemInstance, assignment: AssignmentResult | None = None,
) -> float:
    """F1: share of (student, course) registrations that did not get a section."""
    if assignment is None:
        raise NotImplementedError("F1: TODO-ASSIGNMENT, needs AssignmentResult")
    total = len(assignment.assignments) + len(assignment.unfulfilled)
    if total == 0:
        return 0.0
    return len(assignment.unfulfilled) / total


def calculate_incomplete_student_rate(
    problem: ProblemInstance, assignment: AssignmentResult | None = None,
) -> float:
    """F2: share of students who have at least one unfulfilled registration."""
    if assignment is None:
        raise NotImplementedError("F2: TODO-ASSIGNMENT, needs AssignmentResult")
    students_with_registrations = set(problem.student_to_courses)
    students_incomplete = {sa.student_id for sa in assignment.unfulfilled}
    if not students_with_registrations:
        return 0.0
    return len(students_incomplete) / len(students_with_registrations)


def calculate_student_schedule_penalty(
    problem: ProblemInstance, chromosome: Chromosome, assignment: AssignmentResult | None = None,
    weight_pack: float | None = None, weight_gap: float | None = None, ctx: _EvalContext | None = None,
) -> float:
    """F3: penalizes gaps/idle slots or overly packed days in each student's schedule."""
    if assignment is None:
        raise NotImplementedError

    if weight_pack is None:
        weight_pack = problem.f3_weight_pack
    if weight_gap is None:
        weight_gap = problem.f3_weight_gap

    ctx = ctx or _build_context(problem, chromosome, assignment)

    pack_ratios: list[float] = []
    idle_ratios: list[float] = []
    for student_id, section_ids in ctx.student_sections.items():
        occs = _student_occurrences(ctx, section_ids)
        by_day_week = _group_by_key(occs, lambda o: (o.day, o.week))

        # F_pack: group further by week, count classes per day that week.
        counts_by_week: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        for (day, week), day_occs in by_day_week.items():
            counts_by_week[week][day] = len(day_occs)
        for week, counts_by_day in counts_by_week.items():
            total = sum(counts_by_day.values())
            if total > 0:
                pack_ratios.append(max(counts_by_day.values()) / total)

        # F_gap: unchanged from V1.
        for (day, week), day_occs in by_day_week.items():
            if len(day_occs) < 2:
                continue  # nothing to measure a gap against
            span = max(o.end_slot for o in day_occs) - min(o.start_slot for o in day_occs) + 1
            busy = sum(o.end_slot - o.start_slot + 1 for o in day_occs)
            if span > 0:
                idle_ratios.append((span - busy) / span)

    f_pack = float(np.mean(pack_ratios)) if pack_ratios else 0.0
    f_gap = float(np.mean(idle_ratios)) if idle_ratios else 0.0
    return weight_pack * f_pack + weight_gap * f_gap


def calculate_saturday_session_rate(problem: ProblemInstance, chromosome: Chromosome) -> float:
    """F4: share of genes scheduled on Saturday."""
    SATURDAY = 7
    if not chromosome.genes:
        return 0.0
    saturday_count = sum(1 for g in chromosome.genes if g.day == SATURDAY)
    return saturday_count / len(chromosome.genes)


def calculate_campus_movement_penalty(
    problem: ProblemInstance, chromosome: Chromosome, assignment: AssignmentResult | None = None,
    ctx: _EvalContext | None = None,
) -> float:
    """F5: penalizes same-day cross-campus movement without enough gap."""
    if assignment is None:
        raise NotImplementedError

    minimum_empty_slots = problem.minimum_empty_slots
    ctx = ctx or _build_context(problem, chromosome, assignment)

    shortfall_ratios: list[float] = []
    for student_id, section_ids in ctx.student_sections.items():
        occs = _student_occurrences(ctx, section_ids)
        for (day, week), day_occs in _group_by_key(occs, lambda o: (o.day, o.week)).items():
            ordered = sorted(day_occs, key=lambda o: o.start_slot)
            for prev, nxt in zip(ordered, ordered[1:]):
                if prev.campus is None or nxt.campus is None or prev.campus == nxt.campus:
                    continue
                if minimum_empty_slots <= 0:
                    shortfall_ratios.append(0.0)
                    continue
                gap = nxt.start_slot - prev.end_slot - 1
                shortfall_ratios.append(max(0.0, minimum_empty_slots - gap) / minimum_empty_slots)

    if not shortfall_ratios:
        return 0.0
    return float(np.mean(shortfall_ratios))


def calculate_room_capacity_waste_rate(problem: ProblemInstance, chromosome: Chromosome) -> float:
    """F6: average unused capacity ratio across all scheduled sections
    (1 - expected_students / room.capacity), only counting valid room genes."""
    sessions = _session_by_id(problem)
    sections = _section_by_id(problem)
    waste_ratios = []
    for gene in chromosome.genes:
        session = sessions.get(gene.session_id)
        room = problem.rooms.get(gene.room_id)
        if session is None or room is None or room.capacity <= 0:
            continue
        section = sections.get(session.section_id)
        if section is None:
            continue
        waste_ratios.append(max(0.0, 1.0 - section.expected_students / room.capacity))
    if not waste_ratios:
        return 0.0
    return float(np.mean(waste_ratios))


def calculate_room_load_imbalance(problem: ProblemInstance, chromosome: Chromosome) -> float:
    """F7: how unevenly sessions are spread across rooms. 0 = perfectly balanced.

    FIX: previously only counted rooms that appear in at least one gene, so a
    room that's never used (load=0, arguably the worst-case imbalance) was
    silently excluded from the mean/std instead of dragging the imbalance
    score up. Now includes every room in `problem.rooms`, defaulting unused
    rooms to a load of 0.
    """
    sessions = _session_by_id(problem)
    load_per_room: dict[str, int] = {rid: 0 for rid in problem.rooms}
    for gene in chromosome.genes:
        session = sessions.get(gene.session_id)
        if session is None:
            continue
        load_per_room[gene.room_id] = load_per_room.get(gene.room_id, 0) + session.duration_slots
    if not load_per_room:
        return 0.0
    loads = np.array(list(load_per_room.values()), dtype=float)
    mean = loads.mean()
    if mean == 0:
        return 0.0
    return float(loads.std() / mean)


def calculate_lecturer_schedule_penalty(problem: ProblemInstance, chromosome: Chromosome, ctx: _EvalContext | None = None) -> float:
    """F8: how balanced a teacher's workload is across different days"""
    ctx = ctx or _build_context(problem, chromosome, None)
    per_teacher_day: dict[tuple[str, int], int] = defaultdict(int)
    for occ in ctx.occurrences:
        if occ.teacher_id is None:
            continue
        per_teacher_day[(occ.teacher_id, occ.day)] += occ.end_slot - occ.start_slot + 1
    by_teacher: dict[str, list[int]] = defaultdict(list)
    for (teacher_id, _day), load in per_teacher_day.items():
        by_teacher[teacher_id].append(load)
    if not by_teacher:
        return 0.0
    cvs = []
    for loads in by_teacher.values():
        arr = np.array(loads, dtype=float)
        if arr.mean() > 0:
            cvs.append(arr.std() / arr.mean())
    if not cvs:
        return 0.0
    return float(np.mean(cvs))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

_HARD_CHECKS = (
    check_mandatory_courses,
    check_calendar,
    check_lab_session_spacing,
    check_room_compatibility,
    check_room_capacity,
    check_room_conflicts,
    check_section_conflicts,
    check_lecture_lab,
    check_lecturer_conflicts,
    check_student_assignment,
    check_campus_travel,
)


def _evaluate(
    problem: ProblemInstance, chromosome: Chromosome, assignment: AssignmentResult,
    min_weeks_lecture_to_lab: int | None, minimum_empty_slots: int | None,
    include_student_impact: bool = False,
) -> EvaluationResult:
    """Shared body for evaluate_fast/evaluate_exact once an AssignmentResult
    is already in hand — the only difference between the two is *how* that
    assignment was produced (assign_students_fast vs assign_students_exact).
    """
    ctx = _build_context(problem, chromosome, assignment)

    extra_kwargs: dict = {
        check_lecture_lab: {"min_weeks_lecture_to_lab": min_weeks_lecture_to_lab},
        check_student_assignment: {"assignment": assignment},
        check_campus_travel: {"assignment": assignment, "minimum_empty_slots": minimum_empty_slots},
    }

    violations: list[Violation] = []
    for check in _HARD_CHECKS:
        violations.extend(check(problem, chromosome, ctx=ctx, **extra_kwargs.get(check, {})))

    raw = (
        calculate_unfulfilled_registration_rate(problem, assignment),
        calculate_incomplete_student_rate(problem, assignment),
        calculate_student_schedule_penalty(problem, chromosome, assignment, ctx=ctx),
        calculate_saturday_session_rate(problem, chromosome),
        calculate_campus_movement_penalty(problem, chromosome, assignment, ctx=ctx),
        calculate_room_capacity_waste_rate(problem, chromosome),
        calculate_room_load_imbalance(problem, chromosome),
        calculate_lecturer_schedule_penalty(problem, chromosome, ctx=ctx),
    )
    student_impact = calculate_student_impact(problem, chromosome, assignment) if include_student_impact else {}
    return EvaluationResult(
        raw_objectives=raw, normalized_objectives=(), violations=tuple(violations),
        constraint_key=build_constraint_key(violations),
        student_assignment=assignment.assignments,
        student_impact=student_impact,
    )


def evaluate_fast(
    problem: ProblemInstance, chromosome: Chromosome,
    min_weeks_lecture_to_lab: int | None = None, minimum_empty_slots: int | None = None,
) -> EvaluationResult:
    """Cheap evaluation used inside the evolutionary loop.

    CHANGE: no longer takes `assignment` from the caller — it now calls
    `assign_students_fast()` internally (per the structure.md interface and
    the TODO that used to sit here), so `assignment` is never `None` for the
    checks/objectives below. This removes the old asymmetry where
    assignment-dependent hard checks quietly returned `[]` (looking
    "feasible") while the matching soft objectives returned `NaN` ("unknown")
    for the exact same not-yet-assigned case.

    `student_impact` is intentionally left empty here (not computed) — this
    function runs for every chromosome every generation, and nothing in the
    GA loop consumes per-student impact yet. Computing it here would be pure
    wasted work; it's computed in `evaluate_exact` instead, which only runs
    for elite/final chromosomes.
    """
    assignment = assign_students(problem, chromosome, exact=False)
    return _evaluate(problem, chromosome, assignment, min_weeks_lecture_to_lab, minimum_empty_slots)


def evaluate_exact(
    problem: ProblemInstance, chromosome: Chromosome,
    min_weeks_lecture_to_lab: int | None = None, minimum_empty_slots: int | None = None,
) -> EvaluationResult:
    """Full evaluation for elite/final chromosomes using the exact-assignment heuristic.

    NOTE: `assign_students_exact` is currently a stronger heuristic, not yet a
    real CP-SAT solve — see core/assignment.py docstring. Unlike
    `evaluate_fast`, this also populates `EvaluationResult.student_impact`
    since it only runs for elite/final chromosomes (cheap enough here, and
    reporting/output needs it).
    """
    assignment = assign_students(problem, chromosome, exact=True)
    return _evaluate(
        problem, chromosome, assignment, min_weeks_lecture_to_lab, minimum_empty_slots,
        include_student_impact=True,
    )


def normalize_objectives(population_raw_objectives: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
    """Min-max normalize each of the 8 objective columns across the population.
    NaN entries (blocked objectives) are passed through unchanged."""
    if not population_raw_objectives:
        return []
    arr = np.array(population_raw_objectives, dtype=float)  # shape (pop_size, 8)
    mins = np.nanmin(arr, axis=0)
    maxs = np.nanmax(arr, axis=0)
    ranges = np.where(maxs - mins == 0, 1.0, maxs - mins)
    normalized = (arr - mins) / ranges
    return [tuple(row) for row in normalized]


def build_constraint_key(violations: list[Violation]) -> tuple[int, ...]:
    """
    Builds a feasibility key by counting ERROR violations by priority tier.
    More severe tiers come first; same key means equally infeasible.
    """
    hard_errors = sum(1 for v in violations if v.priority == "HARD" and v.severity == "ERROR")
    other_errors = sum(1 for v in violations if v.priority != "HARD" and v.severity == "ERROR")
    warnings = sum(1 for v in violations if v.severity == "WARNING")
    return (hard_errors, other_errors, warnings)