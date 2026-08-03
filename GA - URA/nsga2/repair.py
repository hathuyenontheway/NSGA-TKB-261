import random

from models.population import Population
from models.chromosome import Chromosome
from models.gene import Gene
from models.room import Room
from models.session import SessionMetadata


MAX_SLOT_PER_DAY = 10
MAX_WEEKS = 15


def repair_population(
    population: Population,
    sessions: list[SessionMetadata],
    rooms: dict[str, Room]
) -> None:

    for chromosome in population.chromosomes:
        repair_chromosome(
            chromosome,
            sessions,
            rooms
        )


def repair_chromosome(
    chromosome: Chromosome,
    sessions: list[SessionMetadata],
    rooms: dict[str, Room]
) -> None:

    for gene in chromosome.genes:

        session = sessions[gene.session_id]

        repair_gene(
            gene,
            session,
            rooms
        )


def repair_gene(
    gene: Gene,
    session: SessionMetadata,
    rooms: dict[str, Room]
) -> None:

    candidates = [
        room_id
        for room_id in session.allowed_rooms
        if (
            room_id in rooms
            and rooms[room_id].campus == session.campus
            and rooms[room_id].capacity >= session.class_size
        )
    ]

    if not candidates:
        raise ValueError(
            f"No feasible room for session {session.session_id}"
        )

    if gene.room_id not in candidates:
        gene.room_id = random.choice(candidates)

    max_start_slot = (
        MAX_SLOT_PER_DAY
        - session.slots_per_week
        + 1
    )

    if gene.start_slot < 1:
        gene.start_slot = 1

    if gene.start_slot > max_start_slot:
        gene.start_slot = max_start_slot

    if gene.start_week < 1:
        gene.start_week = 1

    if gene.start_week > MAX_WEEKS:
        gene.start_week = MAX_WEEKS

    if gene.day < 2:
        gene.day = 2

    if gene.day > 7:
        gene.day = 7