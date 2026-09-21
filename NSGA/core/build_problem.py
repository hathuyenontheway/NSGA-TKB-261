"""Build the immutable search space consumed by chromosome operators."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from math import ceil

from core.models import CourseType, DataIssue, GeneDomain, PreparedData, ProblemInstance, Section, Session, frozen_mapping


@dataclass(frozen=True, slots=True)
class BuildPolicy:
    mandatory_course_ids: frozenset[str] | None = None
    min_elective_students: int = 15
    default_section_capacity: int = 60
    default_mandatory_students: int = 15
    allowed_days: tuple[int, ...] = (2, 3, 4, 5, 6, 7)
    slots_per_day: int = 12
    default_session_slots: int = 3
    dummy_teachers_per_faculty: int = 3 # Tạo 3 giáo viên giả cho mỗi khoa
    min_weeks_lecture_to_lab: int = 1
    minimum_empty_slots: int = 3
    f3_weight_pack: float = 0.5
    f3_weight_gap: float = 0.5

def _lab_course_ids_by_lecture(courses: dict) -> dict[str, str]:
    return {cid: course.companion_course_id for cid, course in courses.items() if course.course_type == CourseType.LECTURE and course.companion_course_id and course.companion_course_id in courses}

def _synthesize_dummy_teachers(
    sections: list[Section], courses: dict, dummy_teachers_per_faculty: int
) -> tuple[list[Section], frozenset[str]]:
    # Round-robin assign dummy_teacher_ids to sections, grouped by the section's course's faculty_id
    if dummy_teachers_per_faculty <= 0:
        return sections, frozenset()
 
    sections_by_faculty: dict[str, list[int]] = defaultdict(list)
    for idx, section in enumerate(sections):
        course = courses.get(section.course_id)
        faculty_id = course.faculty_id if course else "UNKNOWN"
        sections_by_faculty[faculty_id].append(idx)
 
    updated = list(sections)
    all_teachers: set[str] = set()
    for faculty_id, section_indices in sections_by_faculty.items():
        num_teachers = min(len(section_indices), dummy_teachers_per_faculty)
        faculty_teachers = [f"{faculty_id}-GV{n:02d}" for n in range(1, num_teachers + 1)]
        all_teachers.update(faculty_teachers)
        for i, section_idx in enumerate(section_indices):
            teacher_id = faculty_teachers[i % len(faculty_teachers)]
            updated[section_idx] = replace(updated[section_idx], teacher_id=teacher_id)
 
    return updated, frozenset(all_teachers)



def build_problem_instance(prepared: PreparedData, policy: BuildPolicy | None = None) -> ProblemInstance:
    policy = policy or BuildPolicy()
    student_to_courses, course_to_students = defaultdict(set), defaultdict(set)
    for registration in prepared.registrations:
        student_to_courses[registration.student_id].add(registration.course_id)
        course_to_students[registration.course_id].add(registration.student_id)
    enrollment = {cid: len(students) for cid, students in course_to_students.items()}
    mandatory = policy.mandatory_course_ids if policy.mandatory_course_ids is not None else frozenset(prepared.courses) # Thêm mandatory_course_ids khi return
    lab_by_lecture = _lab_course_ids_by_lecture(prepared.courses)
    lab_course_ids = set(lab_by_lecture.values())
    open_ids = sorted(cid for cid in prepared.courses if cid not in lab_course_ids and (cid in mandatory or enrollment.get(cid, 0) >= policy.min_elective_students))
    teaching_weeks = tuple(week for week in prepared.calendar if week.is_teaching)
    if not teaching_weeks:
        raise ValueError("Selected calendar contains no teaching weeks")
    sections, sessions, domains, issues = [], [], [], list(prepared.issues)
    for course_id in open_ids:
        course = prepared.courses[course_id]
        expected = enrollment.get(course_id, policy.default_mandatory_students)
        count = max(1, ceil(expected / policy.default_section_capacity))
        rooms = tuple(sorted(rid for rid in prepared.course_to_rooms.get(course_id, ()) if prepared.rooms[rid].capacity > 0))
        LUNCH_SLOT = 6
        slots = tuple(
            slot for slot in range(1, policy.slots_per_day - policy.default_session_slots + 2)
            if not (slot <= LUNCH_SLOT <= slot + policy.default_session_slots - 1)
        )
        weeks = tuple(week.week for week in teaching_weeks)
        is_alternating = (course.course_type == CourseType.LAB or bool(course.companion_course_id))
        week_step = 2 if is_alternating else 1
        occurrence_count = ceil(len(weeks) / week_step)
        valid_start_weeks = tuple(
            week for index, week in enumerate(weeks)
            if len(weeks[index::week_step]) >= occurrence_count)
        lab_course_id = lab_by_lecture.get(course_id)
        lab_course = prepared.courses[lab_course_id] if lab_course_id else None
        lab_rooms = (tuple(sorted(rid for rid in prepared.course_to_rooms.get(lab_course_id, ()) if prepared.rooms[rid].capacity > 0)) if lab_course_id else ())
        for number in range(1, count + 1):
            section_id, session_id = f"{course_id}-{number:02d}", len(sessions)
            size = min(policy.default_section_capacity, max(0, expected - (number - 1) * policy.default_section_capacity))
            sections.append(Section(section_id, course_id, course.course_type, size, policy.default_section_capacity))
            sessions.append(Session(session_id, section_id, course_id, course.course_type, policy.default_session_slots, occurrence_count, rooms, valid_start_weeks, policy.allowed_days, slots))
            domain = GeneDomain(session_id, rooms, policy.allowed_days, slots, valid_start_weeks)
            domains.append(domain)
            if domain.is_empty:
                issues.append(DataIssue("EMPTY_GENE_DOMAIN", "ERROR", "Session cannot be encoded because its domain is empty", section_id))
            if lab_course is not None:
                lab_section_id, lab_session_id = f"{lab_course_id}--{number:02d}", len(sessions)
                sections.append(Section(lab_section_id, lab_course_id, lab_course.course_type, size, policy.default_section_capacity, parent_section_id=section_id))
                sessions.append(Session(
                    lab_session_id, lab_section_id, lab_course_id, lab_course.course_type, policy.default_session_slots,
                    occurrence_count, lab_rooms, valid_start_weeks, policy.allowed_days, slots, parent_session_id=session_id,
                ))
                lab_domain = GeneDomain(lab_session_id, lab_rooms, policy.allowed_days, slots, valid_start_weeks)
                domains.append(lab_domain)
                if lab_domain.is_empty:
                    issues.append(DataIssue("EMPTY_GENE_DOMAIN", "ERROR", "Lab session cannot be encoded because its domain is empty", lab_section_id))
    sections, teachers = _synthesize_dummy_teachers(sections, prepared.courses, policy.dummy_teachers_per_faculty)
    if sections and not teachers:
        issues.append(DataIssue("NO_TEACHER_ROSTER", "WARNING", "Teacher roster is empty.", None))
    return ProblemInstance(
        prepared.courses, prepared.rooms, teaching_weeks, tuple(sections), tuple(sessions), tuple(domains),
        prepared.registrations,
        frozen_mapping({k: frozenset(v) for k, v in student_to_courses.items()}),
        frozen_mapping({k: frozenset(v) for k, v in course_to_students.items()}),
        tuple(issues), mandatory_course_ids=frozenset(mandatory), teachers=teachers,
        min_weeks_lecture_to_lab=policy.min_weeks_lecture_to_lab, minimum_empty_slots=policy.minimum_empty_slots,
        f3_weight_pack=policy.f3_weight_pack, f3_weight_gap=policy.f3_weight_gap,
    )
