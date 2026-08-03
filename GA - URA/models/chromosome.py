from dataclasses import dataclass, field

from models.gene import Gene


@dataclass(slots=True)
class Chromosome:
    genes: list[Gene] = field(default_factory=list)

    rank: int = 0
    crowding_distance: float = 0.0

    objectives: tuple[float, ...] = field(default_factory=tuple)

    hard_constraint_violation: int = 0

    def __len__(self) -> int:
        return len(self.genes)

    def __getitem__(self, index: int) -> Gene:
        return self.genes[index]

    def append(self, gene: Gene) -> None:
        self.genes.append(gene)

    def copy(self) -> "Chromosome":
        return Chromosome(
            genes=[
                Gene(
                    session_id=g.session_id,
                    room_id=g.room_id,
                    day=g.day,
                    start_slot=g.start_slot,
                    start_week=g.start_week,
                )
                for g in self.genes
            ],
            rank=self.rank,
            crowding_distance=self.crowding_distance,
            objectives=self.objectives,
            hard_constraint_violation=self.hard_constraint_violation,
        )