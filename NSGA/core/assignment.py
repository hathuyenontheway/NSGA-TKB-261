"""Chromosome creation helpers. Student assignment is added here later."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
 
import random

from core.models import AssignmentResult, Chromosome, ProblemInstance, StudentAssignment, Violation

def create_random_chromosome(problem: ProblemInstance, rng: random.Random | None = None) -> Chromosome:
    """Sample each gene inside its domain; collisions are handled later."""
    rng = rng or random.Random()
    genes = []
    for domain in problem.gene_domains:
        if domain.is_empty:
            raise ValueError(f"Session {domain.session_id} has an empty gene domain")
        genes.append(Gene(domain.session_id, rng.choice(domain.room_ids), rng.choice(domain.days), rng.choice(domain.start_slots), rng.choice(domain.start_weeks)))
    return Chromosome(genes)


def validate_chromosome_structure(problem: ProblemInstance, chromosome: Chromosome) -> list[str]:
    if len(chromosome.genes) != len(problem.gene_domains):
        return ["gene count differs from session count"]
    errors = []
    for gene, domain in zip(chromosome.genes, problem.gene_domains):
        if gene.session_id != domain.session_id: errors.append(f"gene order mismatch at session {domain.session_id}")
        if gene.room_id not in domain.room_ids: errors.append(f"invalid room for session {gene.session_id}")
        if gene.day not in domain.days: errors.append(f"invalid day for session {gene.session_id}")
        if gene.start_slot not in domain.start_slots: errors.append(f"invalid slot for session {gene.session_id}")
        if gene.start_week not in domain.start_weeks: errors.append(f"invalid week for session {gene.session_id}")
    return errors

"""The overall flow: Chromosome genes → actual weekly class occurrences → group lecture + lab → detect schedule conflicts."""
"""Shared helpers to expand chromosome genes into weekly occurrences, group lecture/lab sections, and detect schedule conflicts for both assignment and evaluation."""
 
def session_by_id(problem: ProblemInstance) -> dict[int, "object"]:
    return {s.session_id: s for s in problem.sessions}
 
 
def section_by_id(problem: ProblemInstance) -> dict[str, "object"]:
    return {s.section_id: s for s in problem.sections}
 
 
def teaching_week_numbers(problem: ProblemInstance) -> list[int]:
    return sorted(w.week for w in problem.weeks if w.is_teaching)
 
 
def occurrence_weeks(problem: ProblemInstance, start_week: int, total_weeks: int, step: int = 1) -> list[int]:
    """Return the teaching weeks occupied by a session.
    `start_week`: first occurrence, `step`: interval between occurrences, `total_weeks`: how many times the session meets.
    Out-of-range occurrences are clipped to available weeks.
    """
    weeks = teaching_week_numbers(problem)
    if start_week not in weeks:
        return []
    idx = weeks.index(start_week)
    return weeks[idx: idx + step * total_weeks: step]
 
 
def is_alternating_session(problem: ProblemInstance, session) -> bool:
    """True if this session belongs to a lecture+lab pair that meets on alternating weeks."""
    if session.parent_session_id is not None:
        return True
    course = problem.courses.get(session.course_id)
    return bool(course and course.companion_course_id)
 
 
@dataclass(slots=True)
class Occurrence:
    """One (session, room, day, slot-range, week) instance, expanded from a gene."""
    session_id: int
    section_id: str
    course_id: str
    teacher_id: str | None
    room_id: str
    campus: int | None
    day: int
    start_slot: int
    end_slot: int  # inclusive
    week: int
 
 
def expand_occurrences(problem: ProblemInstance, chromosome: Chromosome) -> list[Occurrence]:
    """Turn every gene into its concrete weekly occurrences."""
    sessions = session_by_id(problem)
    sections = section_by_id(problem)
    occurrences: list[Occurrence] = []
    for gene in chromosome.genes:
        session = sessions.get(gene.session_id)
        if session is None:
            continue  # malformed gene; validate_chromosome_structure() catches this separately
        section = sections.get(session.section_id)
        room = problem.rooms.get(gene.room_id)
        campus = room.campus if room else None
        teacher_id = section.teacher_id if section else None
        end_slot = gene.start_slot + session.duration_slots - 1
        step = 2 if is_alternating_session(problem, session) else 1
        for week in occurrence_weeks(problem, gene.start_week, session.total_weeks, step):
            occurrences.append(Occurrence(
                session_id=session.session_id, section_id=session.section_id,
                course_id=session.course_id, teacher_id=teacher_id, room_id=gene.room_id,
                campus=campus, day=gene.day, start_slot=gene.start_slot, end_slot=end_slot, week=week,
            ))
    return occurrences
 
 
def group_by_key(occurrences: list[Occurrence], key_fn) -> dict:
    groups: dict = defaultdict(list)
    for occ in occurrences:
        groups[key_fn(occ)].append(occ)
    return groups
 
 
def slots_overlap(a: Occurrence, b: Occurrence) -> bool:
    return a.start_slot <= b.end_slot and b.start_slot <= a.end_slot
 
 
def occurrences_conflict(a: Occurrence, b: Occurrence) -> bool:
    """True if two occurrences happen in the same week+day and their slots overlap."""
    return a.week == b.week and a.day == b.day and slots_overlap(a, b)
 
 
@dataclass(slots=True)
class _ClassGroup:
    """A lecture section + its optional companion lab, treated as one enrollable unit."""
    course_id: str
    section_id: str          # the lecture section id — what StudentAssignment.section_id records
    lab_section_id: str | None
    capacity: int
    occurrences: list[Occurrence]
 
 
def _lecture_section_to_lab_section(problem: ProblemInstance) -> dict[str, str]:
    return {
        section.parent_section_id: section.section_id
        for section in problem.sections
        if section.parent_section_id is not None
    }
 
 
def _build_class_groups(
    problem: ProblemInstance, chromosome: Chromosome, occ_by_section: dict[str, list[Occurrence]],
) -> dict[str, list[_ClassGroup]]:
    """Get open course groups whose lecture is scheduled; keep lecture-only groups if lab gene is missing."""
    sessions_by_section = {s.section_id: s for s in problem.sessions}
    genes_by_session = {g.session_id: g for g in chromosome.genes}
    lab_by_lecture = _lecture_section_to_lab_section(problem)
 
    groups_by_course: dict[str, list[_ClassGroup]] = defaultdict(list)
    for section in problem.sections:
        if section.parent_section_id is not None:
            continue  # this is a lab section; it's folded into its lecture's group below
        lecture_session = sessions_by_section.get(section.section_id)
        if lecture_session is None or lecture_session.session_id not in genes_by_session:
            continue  # not scheduled by this chromosome — can't enroll anyone into it
 
        occs = list(occ_by_section.get(section.section_id, ()))
        lab_section_id = lab_by_lecture.get(section.section_id)
        if lab_section_id is not None:
            lab_session = sessions_by_section.get(lab_section_id)
            if lab_session is not None and lab_session.session_id in genes_by_session:
                occs += occ_by_section.get(lab_section_id, ())
            else:
                lab_section_id = None  # lab not actually scheduled; treat group as lecture-only
 
        groups_by_course[section.course_id].append(_ClassGroup(
            course_id=section.course_id, section_id=section.section_id,
            lab_section_id=lab_section_id, capacity=section.max_capacity, occurrences=occs,
        ))
    for groups in groups_by_course.values():
        groups.sort(key=lambda g: g.section_id)  # deterministic order
    return groups_by_course
 
 
def _has_conflict(busy: list[Occurrence], candidate_occs: list[Occurrence]) -> bool:
    return any(occurrences_conflict(a, b) for a in busy for b in candidate_occs)