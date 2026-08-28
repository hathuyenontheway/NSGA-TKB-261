"""Chromosome creation helpers. Student assignment is added here later."""
from __future__ import annotations

import random

from core.models import Chromosome, Gene, ProblemInstance


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
