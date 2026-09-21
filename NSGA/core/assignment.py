"""Chromosome creation helpers. Student assignment is added here later."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from core.models import AssignmentResult, Chromosome, CourseType, Gene, ProblemInstance, StudentAssignment, Violation
 
import random

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
    """Lecture có companion và các LAB session học cách tuần."""
    course = problem.courses.get(session.course_id)
    return bool(
        session.parent_session_id is not None
        or session.session_type == CourseType.LAB
        or (course and course.companion_course_id)
    )
 
 
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

        # ADDITIONAL CAPACITY CHECK: The actual capacity of a class group is the minimum of the lecture's max capacity and the smallest room capacity among its occurrences.
        min_room_capacity = section.max_capacity
        for occ in occs:
            room = problem.rooms.get(occ.room_id)
            if room and room.capacity > 0:
                min_room_capacity = min(min_room_capacity, room.capacity)
        
        actual_capacity = min(section.max_capacity, min_room_capacity)
        # END OF ADDITIONAL CAPACITY CHECK

        groups_by_course[section.course_id].append(_ClassGroup(
            course_id=section.course_id, section_id=section.section_id,
            lab_section_id=lab_section_id, capacity=actual_capacity, occurrences=occs,
        ))
    for groups in groups_by_course.values():
        groups.sort(key=lambda g: g.section_id)  # deterministic order
    return groups_by_course
 
 
def _has_conflict(busy: list[Occurrence], candidate_occs: list[Occurrence]) -> bool:
    return any(occurrences_conflict(a, b) for a in busy for b in candidate_occs)

def _has_campus_conflict(busy_occs: list[Occurrence], candidate_occs: list[Occurrence], min_gap: int) -> bool:
    """Check the travel time between 2 campuses within the same day."""
    if min_gap <= 0:
        return False
    for c in candidate_occs:
        for b in busy_occs:
            if c.week == b.week and c.day == b.day and c.campus != b.campus:
                if c.campus is None or b.campus is None:
                    continue
                # Calculate the gap between the two occurrences
                if c.start_slot > b.start_slot:
                    gap = c.start_slot - b.end_slot - 1
                else:
                    gap = b.start_slot - c.end_slot - 1
                
                if gap < min_gap:
                    return True
    return False

def assign_students(
    problem: ProblemInstance, 
    chromosome: Chromosome, 
    exact: bool = False
) -> AssignmentResult:
    """
    Select the way to assign students based on the `exact` flag.
    exact == True: use assign_students_exact() #More acreurate but slower, suitable for final evaluation.
    exact == False: use assign_students_fast() #Faster but less accurate, suitable for GA iterations.
    """
    if exact:
        return assign_students_exact(problem, chromosome)
    return assign_students_fast(problem, chromosome)

def assign_students_fast(problem: ProblemInstance, chromosome: Chromosome) -> AssignmentResult:
    """This function is used to assign students based on the given chromosome. It is used while GA is running."""
    
    occ_by_section = group_by_key(expand_occurrences(problem, chromosome), lambda o: o.section_id)
    groups_by_course = _build_class_groups(problem, chromosome, occ_by_section)
    
    enrolled_count = defaultdict(int)
    student_busy_occs = defaultdict(list)
    assignments = []
    unfulfilled = []
    
    # Pre-calculate the number of available class groups for each course
    course_group_count = {cid: len(groups) for cid, groups in groups_by_course.items()}
    
    def student_priority_key(sid: str) -> tuple[int, int]:
        requested = problem.student_to_courses[sid]
        # Count how many requested courses are "bottlenecks" (<= 2 groups available)
        bottleneck_count = sum(1 for cid in requested if course_group_count.get(cid, 0) <= 2)
        return (bottleneck_count, len(requested))
    
    # Sort students: Priority 1 = Bottlenecks, Priority 2 = Total requested courses
    students = sorted(
        problem.student_to_courses.keys(),
        key=student_priority_key,
        reverse=True
    )
    
    for student_id in students:
        requested_courses = problem.student_to_courses[student_id]
        for course_id in requested_courses:
            assigned = False
            available_groups = groups_by_course.get(course_id, [])
            
            # Sort groups: Prioritize filling classes that are already partially full
            available_groups.sort(
                key=lambda g: enrolled_count[g.section_id] / g.capacity if g.capacity > 0 else 0,
                reverse=True
            )
            
            for group in available_groups:
                if enrolled_count[group.section_id] >= group.capacity:
                    continue
                if _has_conflict(student_busy_occs[student_id], group.occurrences):
                    continue
                if _has_campus_conflict(student_busy_occs[student_id], group.occurrences, problem.minimum_empty_slots):
                    continue
                    
                enrolled_count[group.section_id] += 1
                student_busy_occs[student_id].extend(group.occurrences)
                assignments.append(StudentAssignment(student_id, course_id, group.section_id))
                assigned = True
                break
                
            if not assigned:
                unfulfilled.append(StudentAssignment(student_id, course_id, None))
                
    return AssignmentResult(tuple(assignments), tuple(unfulfilled))

def assign_students_exact(problem: ProblemInstance, chromosome: Chromosome) -> AssignmentResult:
    """
    Sử dụng OR-Tools (CP-SAT) để tối ưu hóa việc phân bổ sinh viên cho các nghiệm Elite.
    Được mồi sẵn nghiệm từ assign_students_fast để hội tụ nhanh.
    """
    from ortools.sat.python import cp_model

    occ_by_section = group_by_key(expand_occurrences(problem, chromosome), lambda o: o.section_id)
    groups_by_course = _build_class_groups(problem, chromosome, occ_by_section)
    
    fast_result = assign_students_fast(problem, chromosome)
    fast_assignments = {(a.student_id, a.course_id): a.section_id for a in fast_result.assignments}
    
    model = cp_model.CpModel()
    x = {}  # dict: (student_id, course_id, section_id) -> cp_model.BoolVar
    
    for student_id, courses in problem.student_to_courses.items():
        for course_id in courses:
            student_course_vars = []
            for group in groups_by_course.get(course_id, []):
                if group.capacity <= 0:
                    continue
                var = model.NewBoolVar(f"x_{student_id}_{course_id}_{group.section_id}")
                x[(student_id, course_id, group.section_id)] = var
                student_course_vars.append(var)
                
                if fast_assignments.get((student_id, course_id)) == group.section_id:
                    model.AddHint(var, 1)
                else:
                    model.AddHint(var, 0)
            
            if student_course_vars:
                model.AddAtMostOne(student_course_vars)

    for course_id, groups in groups_by_course.items():
        for group in groups:
            if group.capacity <= 0:
                continue
            group_vars = []
            for student_id in problem.course_to_students.get(course_id, []):
                var = x.get((student_id, course_id, group.section_id))
                if var is not None:
                    group_vars.append(var)
            if group_vars:
                model.Add(sum(group_vars) <= group.capacity)

    for student_id, courses in problem.student_to_courses.items():
        student_vars = []
        for course_id in courses:
            for group in groups_by_course.get(course_id, []):
                var = x.get((student_id, course_id, group.section_id))
                if var is not None:
                    student_vars.append((var, group))
        
        for i in range(len(student_vars)):
            var1, group1 = student_vars[i]
            for j in range(i + 1, len(student_vars)):
                var2, group2 = student_vars[j]
                
                if _has_conflict(group1.occurrences, group2.occurrences):
                    model.AddImplication(var1, var2.Not())

                elif _has_campus_conflict(group1.occurrences, group2.occurrences, problem.minimum_empty_slots):
                    model.AddImplication(var1, var2.Not())

    model.Maximize(sum(x.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0  # Set a time limit for the solver, can change as needed or turn off 
    status = solver.Solve(model)

    assignments = []
    unfulfilled = []
    assigned_pairs = set()

    # If the solver finds an optimal or feasible solution, we extract the assignments from the solution, else we reuse the fast result.
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (student_id, course_id, section_id), var in x.items():
            if solver.Value(var):
                assignments.append(StudentAssignment(student_id, course_id, section_id))
                assigned_pairs.add((student_id, course_id))
    else:
        return fast_result

    for student_id, courses in problem.student_to_courses.items():
        for course_id in courses:
            if (student_id, course_id) not in assigned_pairs:
                unfulfilled.append(StudentAssignment(student_id, course_id, None))

    return AssignmentResult(tuple(assignments), tuple(unfulfilled))

def calculate_student_impact(problem: ProblemInstance, chromosome: Chromosome, assignment: AssignmentResult) -> dict:
    """Count the number of fulfilled and unfulfilled course requests for each student based on the assignment result. The result is used as a optimized objective."""
    impact = {}
    
    for student_id, courses in problem.student_to_courses.items():
        impact[student_id] = {
            "fulfilled": 0,
            "unfulfilled": 0,
            "total_requested": len(courses)
        }
        
    for req in assignment.assignments:
        impact[req.student_id]["fulfilled"] += 1
        
    for req in assignment.unfulfilled:
        impact[req.student_id]["unfulfilled"] += 1
        
    return impact

 