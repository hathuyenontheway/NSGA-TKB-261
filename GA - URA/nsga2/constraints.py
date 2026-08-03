from typing import Dict, Set, Tuple


VALID_DAYS: Set[int] = {2, 3, 4, 5, 6, 7}
VALID_LECTURE_START: range = range(1, 13)
VALID_PRACTICAL_STARTS: Set[int] = {2, 8}
LUNCH_BREAK_SLOT: int = 6
MIDTERM_WEEKS: Set[int] = {8}
HOLIDAY_WEEKS: Set[int] = set()
CAMPUS_GAP: int = 3


def normalize_session_type(session) -> str:
    return str(session.session_type).strip().upper()


def weeks_set(start_week: int, num_weeks: int) -> Set[int]:
    """Return the contiguous active weeks of a session."""
    return set(range(start_week, start_week + num_weeks))


def slots_set(start_slot: int, num_slots: int) -> Set[int]:
    return set(range(start_slot, start_slot + num_slots))


def sessions_overlap(g1, s1, g2, s2) -> bool:
    if g1.day != g2.day:
        return False

    weeks1 = weeks_set(g1.start_week, s1.total_weeks)
    weeks2 = weeks_set(g2.start_week, s2.total_weeks)
    if not weeks1.intersection(weeks2):
        return False

    slots1 = slots_set(g1.start_slot, s1.duration)
    slots2 = slots_set(g2.start_slot, s2.duration)
    return bool(slots1.intersection(slots2))


def check_valid_day(gene) -> bool:
    return gene.day in VALID_DAYS


def check_session_start(gene, session) -> bool:
    if normalize_session_type(session) in {"LAB", "PRACTICAL"}:
        return gene.start_slot in VALID_PRACTICAL_STARTS
    return gene.start_slot in VALID_LECTURE_START


def check_lunch_break(gene) -> bool:
    return gene.start_slot != LUNCH_BREAK_SLOT


def check_midterm_break(gene, session) -> bool:
    active_weeks = weeks_set(gene.start_week, session.total_weeks)
    return not active_weeks.intersection(MIDTERM_WEEKS)


def check_holiday_break(gene, session) -> bool:
    active_weeks = weeks_set(gene.start_week, session.total_weeks)
    return not active_weeks.intersection(HOLIDAY_WEEKS)


def check_lecture_duplicate(chromosome, sessions) -> int:
    seen: Set[str] = set()
    violations = 0
    for gene in chromosome.genes:
        session = sessions[gene.session_id]
        if normalize_session_type(session) != "LECTURE":
            continue
        if session.section_id in seen:
            violations += 1
        seen.add(session.section_id)
    return violations


def check_lab_duplicate(chromosome, sessions) -> int:
    seen: Set[str] = set()
    violations = 0
    for gene in chromosome.genes:
        session = sessions[gene.session_id]
        if normalize_session_type(session) not in {"LAB", "PRACTICAL"}:
            continue
        if session.section_id in seen:
            violations += 1
        seen.add(session.section_id)
    return violations


def check_linked_session_overlap(chromosome, sessions) -> int:
    gene_by_session_id = {
        gene.session_id: gene
        for gene in chromosome.genes
    }
    checked: set[tuple[int, int]] = set()
    overlaps = 0

    for gene in chromosome.genes:
        session = sessions[gene.session_id]
        parent_id = session.parent_session_id
        if parent_id is None:
            continue

        pair = tuple(sorted((gene.session_id, parent_id)))
        if pair in checked:
            continue
        checked.add(pair)

        parent_gene = gene_by_session_id.get(parent_id)
        if parent_gene is None:
            continue
        parent_session = sessions[parent_id]

        if sessions_overlap(gene, session, parent_gene, parent_session):
            overlaps += 1

    return overlaps


def check_lecture_before_lab(chromosome, sessions) -> int:
    gene_by_session_id = {
        gene.session_id: gene
        for gene in chromosome.genes
    }
    violations = 0

    for gene in chromosome.genes:
        session = sessions[gene.session_id]
        if (
            normalize_session_type(session) not in {"LAB", "PRACTICAL"}
            or session.parent_session_id is None
        ):
            continue

        lecture_gene = gene_by_session_id.get(session.parent_session_id)
        if lecture_gene is None:
            continue
        minimum_offset = int(session.min_lab_offset or 0)
        if gene.start_week < lecture_gene.start_week + minimum_offset:
            violations += 1

    return violations


def check_room_capacity(gene, session, rooms) -> bool:
    room = rooms.get(gene.room_id)
    if room is None:
        return False
    return room.capacity >= session.class_size


def check_allowed_room(gene, session) -> bool:
    return gene.room_id in session.allowed_rooms


def check_campus_same_course(chromosome, sessions, rooms) -> bool:
    course_sessions: Dict[str, list] = {}
    for gene in chromosome.genes:
        session = sessions[gene.session_id]
        course_sessions.setdefault(
            session.course_id,
            [],
        ).append((gene, session))

    for items in course_sessions.values():
        items.sort(key=lambda item: (item[0].day, item[0].start_slot))

        for index, (gene1, session1) in enumerate(items):
            room1 = rooms.get(gene1.room_id)
            if room1 is None:
                return False

            for gene2, session2 in items[index + 1:]:
                if gene1.day != gene2.day:
                    break

                room2 = rooms.get(gene2.room_id)
                if room2 is None:
                    return False
                if room1.campus == room2.campus:
                    continue

                end_slot_1 = max(
                    slots_set(gene1.start_slot, session1.duration)
                )
                start_slot_2 = min(
                    slots_set(gene2.start_slot, session2.duration)
                )
                if start_slot_2 - end_slot_1 < CAMPUS_GAP:
                    return False

    return True


def check_room_conflicts(chromosome, sessions) -> int:
    genes_by_room: Dict[str, list] = {}
    for gene in chromosome.genes:
        genes_by_room.setdefault(gene.room_id, []).append(gene)

    conflicts = 0
    for room_genes in genes_by_room.values():
        for index, gene1 in enumerate(room_genes):
            session1 = sessions[gene1.session_id]
            for gene2 in room_genes[index + 1:]:
                session2 = sessions[gene2.session_id]
                if sessions_overlap(gene1, session1, gene2, session2):
                    conflicts += 1
    return conflicts


def evaluate_hard_violations(chromosome, sessions, rooms) -> int:
    total = 0

    for gene in chromosome.genes:
        session = sessions[gene.session_id]
        total += 0 if check_valid_day(gene) else 1
        total += 0 if check_session_start(gene, session) else 1
        total += 0 if check_lunch_break(gene) else 1
        total += 0 if check_midterm_break(gene, session) else 1
        total += 0 if check_holiday_break(gene, session) else 1
        total += 0 if check_room_capacity(gene, session, rooms) else 1
        total += 0 if check_allowed_room(gene, session) else 1

    total += check_lecture_duplicate(chromosome, sessions)
    total += check_lab_duplicate(chromosome, sessions)
    total += check_linked_session_overlap(chromosome, sessions)
    total += check_lecture_before_lab(chromosome, sessions)
    total += check_room_conflicts(chromosome, sessions)
    total += (
        0
        if check_campus_same_course(chromosome, sessions, rooms)
        else 1
    )
    return total


def schedule_saturday(chromosome) -> int:
    return sum(1 for gene in chromosome.genes if gene.day == 7)


def objective_capacity_waste(chromosome, sessions, rooms) -> int:
    waste = 0
    for gene in chromosome.genes:
        session = sessions[gene.session_id]
        room = rooms[gene.room_id]
        waste += room.capacity - session.class_size
    return waste


def objective_load_imbalance(chromosome) -> float:
    day_counts: Dict[int, int] = {
        day: 0
        for day in VALID_DAYS
    }
    for gene in chromosome.genes:
        if gene.day in day_counts:
            day_counts[gene.day] += 1

    counts = list(day_counts.values())
    mean = sum(counts) / len(counts)
    return sum((count - mean) ** 2 for count in counts) / len(counts)


def objective_room_idle(chromosome) -> int:
    used: Set[Tuple[str, int]] = {
        (gene.room_id, gene.day)
        for gene in chromosome.genes
    }
    all_rooms = {
        gene.room_id
        for gene in chromosome.genes
    }
    possible = len(all_rooms) * len(VALID_DAYS)
    return possible - len(used)


def evaluate_soft_constraints(
    chromosome,
    sessions,
    rooms,
) -> Tuple[float, ...]:
    return (
        schedule_saturday(chromosome),
        objective_capacity_waste(chromosome, sessions, rooms),
        objective_load_imbalance(chromosome),
        objective_room_idle(chromosome),
    )


def evaluate(
    chromosome,
    sessions,
    rooms,
    courses=None,
) -> None:
    """Evaluate a chromosome; courses is retained for caller compatibility."""
    chromosome.hard_constraint_violation = evaluate_hard_violations(
        chromosome,
        sessions,
        rooms,
    )
    chromosome.objectives = evaluate_soft_constraints(
        chromosome,
        sessions,
        rooms,
    )
