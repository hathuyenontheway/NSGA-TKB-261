"""Build the immutable search space consumed by chromosome operators."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import ceil

from core.models import DataIssue, GeneDomain, PreparedData, ProblemInstance, Section, Session, frozen_mapping


@dataclass(frozen=True, slots=True)
class BuildPolicy:
    mandatory_course_ids: frozenset[str] | None = None
    min_elective_students: int = 15
    default_section_capacity: int = 60
    default_mandatory_students: int = 15
    allowed_days: tuple[int, ...] = (2, 3, 4, 5, 6, 7)
    slots_per_day: int = 12
    default_session_slots: int = 3


def build_problem_instance(prepared: PreparedData, policy: BuildPolicy | None = None) -> ProblemInstance:
    policy = policy or BuildPolicy()
    student_to_courses, course_to_students = defaultdict(set), defaultdict(set)
    for registration in prepared.registrations:
        student_to_courses[registration.student_id].add(registration.course_id)
        course_to_students[registration.course_id].add(registration.student_id)
    enrollment = {cid: len(students) for cid, students in course_to_students.items()}
    mandatory = policy.mandatory_course_ids if policy.mandatory_course_ids is not None else frozenset(prepared.courses)
    open_ids = sorted(cid for cid in prepared.courses if cid in mandatory or enrollment.get(cid, 0) >= policy.min_elective_students)
    teaching_weeks = tuple(week for week in prepared.calendar if week.is_teaching)
    if not teaching_weeks:
        raise ValueError("Selected calendar contains no teaching weeks")
    sections, sessions, domains, issues = [], [], [], list(prepared.issues)
    for course_id in open_ids:
        course = prepared.courses[course_id]
        expected = enrollment.get(course_id, policy.default_mandatory_students)
        count = max(1, ceil(expected / policy.default_section_capacity))
        rooms = tuple(sorted(rid for rid in prepared.course_to_rooms.get(course_id, ()) if prepared.rooms[rid].capacity > 0))
        slots = tuple(range(1, policy.slots_per_day - policy.default_session_slots + 2))
        weeks = tuple(week.week for week in teaching_weeks)
        for number in range(1, count + 1):
            section_id, session_id = f"{course_id}-{number:02d}", len(sessions)
            size = min(policy.default_section_capacity, max(0, expected - (number - 1) * policy.default_section_capacity))
            sections.append(Section(section_id, course_id, course.course_type, size, policy.default_section_capacity))
            sessions.append(Session(session_id, section_id, course_id, course.course_type, policy.default_session_slots, len(teaching_weeks), rooms, weeks, policy.allowed_days, slots))
            domain = GeneDomain(session_id, rooms, policy.allowed_days, slots, weeks)
            domains.append(domain)
            if domain.is_empty:
                issues.append(DataIssue("EMPTY_GENE_DOMAIN", "ERROR", "Session cannot be encoded because its domain is empty", section_id))
    return ProblemInstance(prepared.courses, prepared.rooms, teaching_weeks, tuple(sections), tuple(sessions), tuple(domains), prepared.registrations, frozen_mapping({k: frozenset(v) for k, v in student_to_courses.items()}), frozen_mapping({k: frozenset(v) for k, v in course_to_students.items()}), tuple(issues))
