from dataclasses import dataclass, field

from models.chromosome import Chromosome


@dataclass(slots=True)
class Population:
    chromosomes: list[Chromosome] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.chromosomes)

    def __getitem__(self, index: int) -> Chromosome:
        return self.chromosomes[index]

    def append(self, chromosome: Chromosome) -> None:
        self.chromosomes.append(chromosome)

    def extend(self, chromosomes: list[Chromosome]) -> None:
        self.chromosomes.extend(chromosomes)