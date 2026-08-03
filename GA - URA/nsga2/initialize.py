import random

from nsga2.population import Population
from models.chromosome import Chromosome
from models.gene import Gene
from models.room import Room
from models.session import SessionMetadata


MAX_SLOT_PER_DAY = 10
MAX_WEEKS = 15


def initialize_population(
    population_size: int,
    sessions: list[SessionMetadata],
    rooms: dict[str, Room]
) -> Population:

    population = Population()

    for _ in range(population_size):
        population.append(
            initialize_chromosome(
                sessions,
                rooms
            )
        )

    return population


def initialize_chromosome(
    sessions: list[SessionMetadata],
    rooms: dict[str, Room]
) -> Chromosome:

    chromosome = Chromosome()

    for session in sessions:

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

        max_start_slot = (
            MAX_SLOT_PER_DAY
            - session.slots_per_week
            + 1
        )

        chromosome.append(
            Gene(
                session_id=session.session_id,
                room_id=random.choice(candidates),
                day=random.randint(2, 7),
                start_slot=random.randint(
                    1,
                    max_start_slot
                ),
                start_week=random.randint(
                    1,
                    MAX_WEEKS
                )
            )
        )

    return chromosome