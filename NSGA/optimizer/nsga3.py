"""
Pipeline: Sampling -> Evaluation -> Selection -> Crossover -> Mutation -> Repair.
Chromosome là biểu diễn chính, các mảng NumPy chỉ được dùng tạm để tính toán.
Evaluator trả objectives F cần tối thiểu hóa và hard constraints G, với G[i] <= 0 là hợp lệ.
"""

from __future__ import annotations  # Cho phép forward type annotation.

from collections.abc import Callable  # Kiểu của evaluator.
from dataclasses import dataclass
import random
from typing import Any

import numpy as np
from numpy.typing import NDArray  # Type hint cho mảng NumPy.
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.core.crossover import Crossover
from pymoo.core.mutation import Mutation
from pymoo.core.problem import ElementwiseProblem  # Đánh giá từng Chromosome.
from pymoo.core.repair import Repair
from pymoo.core.sampling import Sampling  # Lớp cha để sinh population ban đầu.
from pymoo.optimize import minimize  # Điều khiển vòng lặp tiến hóa.
from pymoo.util.ref_dirs import get_reference_directions  # Sinh reference directions.

from core.assignment import create_random_chromosome, expand_occurrences, is_alternating_session, occurrence_weeks, validate_chromosome_structure
from core.models import Chromosome, ProblemInstance, EvaluationResult
from core.evaluation import evaluate_fast

Evaluator = Callable[[ProblemInstance, Chromosome], EvaluationResult]
N_SOFT_CONSTRAINTS = 8
N_CONSTRAINT_OUTPUTS = 1
EVALUATOR: Evaluator = evaluate_fast

@dataclass(frozen=True, slots=True)
class NSGA3Config:
    n_partitions: int = 3  # Division parameter H
    population_size: int | None = None  # None = số reference directions.
    n_offsprings: int | None = None  # None = mặc định của pymoo.
    n_generations: int = 100  # Số thế hệ tối đa.
    seed: int | None = 42  # Seed để kết quả có thể tái lập.
    crossover_probability: float = 0.8  # Xác suất crossover mỗi cặp parent.
    mutation_probability: float = 0.2  # Xác suất mutation mỗi offspring.

    def __post_init__(self) -> None:
        if self.n_partitions < 1:
            raise ValueError("n_partitions must be positive")
        if self.population_size is not None and self.population_size < 2:
            raise ValueError("population_size must be at least 2")
        if self.n_offsprings is not None and self.n_offsprings < 1:
            raise ValueError("n_offsprings must be positive")
        if self.n_generations < 1:
            raise ValueError("n_generations must be positive")
        if not 0.0 <= self.crossover_probability <= 1.0:
            raise ValueError("crossover_probability must be between 0 and 1")
        if not 0.0 <= self.mutation_probability <= 1.0:
            raise ValueError("mutation_probability must be between 0 and 1")


class TimetableProblem(ElementwiseProblem):
    def __init__(self, instance: ProblemInstance, evaluator: Evaluator, *, n_objectives: int, n_constraints: int) -> None:
        if n_objectives < 2:
            raise ValueError("NSGA-III requires at least two objectives")
        if n_constraints < 0:
            raise ValueError("n_constraints cannot be negative")

        # Một decision variable object chứa toàn bộ Chromosome.
        # Ví dụ x có dạng np.array([chromosome], dtype=object) và shape (1,).
        super().__init__(n_var=1, n_obj=n_objectives, n_ieq_constr=n_constraints, xl=None, xu=None)
        self.instance = instance  # Dữ liệu dùng bởi sampling/mutation/evaluation.
        self.evaluator = evaluator

    def _evaluate(self, x: NDArray[np.object_], out: dict[str, Any], *args, **kwargs) -> None:
        chromosome = x[0]
        result = self.evaluator(self.instance, chromosome)
        objectives = np.asarray(result.raw_objectives, dtype=float) #F = [f1, f2, ..., f8]
        constraints = np.asarray([result.constraint_key[0]], dtype=float) #G = [Tổng số hard errors]
        expected_f_shape = (self.n_obj,)

        # Mỗi chromosome phải trả đúng một giá trị cho mỗi objective.
        if objectives.shape != expected_f_shape:
            raise ValueError(f"Evaluator returned F with shape {objectives.shape}; expected {expected_f_shape}")
        if not np.all(np.isfinite(objectives)):
            raise ValueError("Objective vector F contains NaN or infinity")

        out["F"] = objectives

        if self.n_ieq_constr == 0:
            return
        if constraints is None:
            raise ValueError("Evaluator must return G when constraints are configured")

        constraints = np.asarray(constraints, dtype=float) # Ví dụ G=[0.0, 2.0, -1.0]: constraint thứ hai đang vi phạm 2 đơn vị.
        expected_g_shape = (self.n_ieq_constr,)

        # Mỗi chromosome phải trả đúng một giá trị cho mỗi constraint.
        if constraints.shape != expected_g_shape:
            raise ValueError(f"Evaluator returned G with shape {constraints.shape}; expected {expected_g_shape}")
        if not np.all(np.isfinite(constraints)):
            raise ValueError("Constraint vector G contains NaN or infinity")

        out["G"] = constraints  # G[j] <= 0 là hợp lệ.


class ChromosomeSampling(Sampling):
    # n_samples là số chromosome pymoo yêu cầu tạo.
    def _do(self, problem: TimetableProblem, n_samples: int, *args, random_state: np.random.Generator | None = None, **kwargs) -> NDArray[np.object_]:
        if random_state is None:
            raise RuntimeError("pymoo did not provide random_state")
        
        factory_rng = random.Random(int(random_state.integers(0, np.iinfo(np.int64).max)))
        population = np.empty((n_samples, 1), dtype=object)

        for i in range(n_samples):
            population[i, 0] = create_random_chromosome(problem.instance, factory_rng)   
        return population


class GeneBasedCrossover(Crossover):
    def __init__(self, probability: float) -> None:
        super().__init__(n_parents=2, n_offsprings=2, prob=probability)

    # Ví dụ 60 cặp mating -> X có shape (2, 60, 1).
    def _do(self, problem: TimetableProblem, X: NDArray[np.object_], *args, random_state: np.random.Generator | None = None, **kwargs) -> NDArray[np.object_]:
        if random_state is None:
            raise RuntimeError("pymoo did not provide random_state")

        # Output giữ cùng dạng (2 offspring, n_matings, 1 Chromosome).
        offspring = np.empty((2, X.shape[1], 1), dtype=object)

        for mating in range(X.shape[1]):
            parent_a = X[0, mating, 0]
            parent_b = X[1, mating, 0]

            testA = validate_chromosome_structure(problem.instance, parent_a)
            testB = validate_chromosome_structure(problem.instance, parent_b)
            if testA or testB:
                raise ValueError(f"Invalid parents: parent_a={testA}; parent_b={testB}")

            child_a = parent_a.copy() # Chromosome.copy()
            child_b = parent_b.copy()
            for c in (child_a, child_b):
                c.rank = None
                c.objectives = ()
                c.constraint_violation = 0.0

            for i in range(len(parent_a.genes)):
                if random_state.random() >= 0.5:
                    child_a.genes[i], child_b.genes[i] = child_b.genes[i], child_a.genes[i]

            offspring[0, mating, 0] = child_a
            offspring[1, mating, 0] = child_b

        return offspring


"""VD:
    GeneDomain(
    session_id=15,
    room_ids=("A1-101", "A1-102"),
    days=(2, 4, 6),
    start_slots=(1, 4, 7),
    start_weeks=(1, 2))
"""
class GeneDomainMutation(Mutation):
    def __init__(self, probability: float) -> None:
        super().__init__(prob=probability)

    def _do(
        self, problem: TimetableProblem,
        X: NDArray[np.object_], *args,
        random_state: np.random.Generator | None = None,
        **kwargs) -> NDArray[np.object_]:

        if random_state is None:
            raise RuntimeError("pymoo did not provide random_state")

        offspring = np.empty_like(X, dtype=object)
        domains = problem.instance.gene_domains
        for index in range(X.shape[0]):
            chromosome = X[index, 0].copy()
            chromosome.rank = None
            chromosome.objectives = ()
            chromosome.constraint_violation = 0.0

            if len(chromosome.genes) != len(domains):
                raise ValueError("Gene count does not match GeneDomain count")

            candidates: list[tuple[int, str, tuple[Any, ...]]] = []
            for gene_index, (gene, domain) in enumerate(zip(chromosome.genes, domains, strict=True)):
                if gene.session_id != domain.session_id:
                    raise ValueError("GeneDomain order does not match gene order")

                attributes = (
                    ("room_id", gene.room_id, domain.room_ids),
                    ("day", gene.day, domain.days),
                    ("start_slot", gene.start_slot, domain.start_slots),
                    ("start_week", gene.start_week, domain.start_weeks))

                for attribute, current_value, allowed_values in attributes:
                    alternatives = tuple(value for value in allowed_values if value != current_value)

                    if alternatives:
                        candidates.append((gene_index, attribute, alternatives))

            if candidates:
                candidate_index = int(random_state.integers(0, len(candidates)))
                gene_index, attribute, alternatives = candidates[candidate_index]
                value_index = int(random_state.integers(0, len(alternatives)))
                new_value = alternatives[value_index]
                setattr(chromosome.genes[gene_index], attribute, new_value)

            offspring[index, 0] = chromosome

        return offspring

class TimetableRepair(Repair):
    """
    Sửa chữa chromosome theo thứ tự:
    1. Chuẩn hóa giá trị ngoài domain về trong domain.
    2. Phát hiện xung đột phòng và giảng viên.
    3. Thử tìm phương án thay thế trong domain để giải phóng xung đột.
    4. Giới hạn số lần thử (max_trials) tránh vòng lặp vô tận.
    """
    def __init__(self, max_trials: int = 10) -> None:
        super().__init__()
        self.max_trials = max_trials

    def _repair_chromosome(self, problem: ProblemInstance, chromosome: Chromosome, rng: np.random.Generator) -> Chromosome:
        domains = problem.gene_domains
        if len(chromosome.genes) != len(domains):
            raise ValueError("Gene count does not match GeneDomain count")

        gene_index_by_session = {gene.session_id: index for index, gene in enumerate(chromosome.genes)}

        # 1. Kiểm tra cấu trúc và đưa các giá trị ngoài domain về hợp lệ
        for gene, domain in zip(chromosome.genes, domains, strict=True):
            if gene.session_id != domain.session_id:
                raise ValueError("GeneDomain order does not match gene order")
            if gene.room_id not in domain.room_ids and domain.room_ids:
                gene.room_id = domain.room_ids[0]
            if gene.day not in domain.days and domain.days:
                gene.day = domain.days[0]
            if gene.start_slot not in domain.start_slots and domain.start_slots:
                gene.start_slot = domain.start_slots[0]
            if gene.start_week not in domain.start_weeks and domain.start_weeks:
                gene.start_week = domain.start_weeks[0]

        sections = {s.section_id: s for s in problem.sections}
        sessions = {s.session_id: s for s in problem.sessions}

        # 2. Vòng lặp sửa xung đột với giới hạn số lần thử
        for _ in range(self.max_trials):
            occs = expand_occurrences(problem, chromosome)
            room_grid: dict[tuple[str, int, int, int], int] = {}
            teacher_grid: dict[tuple[str, int, int, int], int] = {}
            conflicts: set[int] = set()

            for occ in occs:
                for slot in range(occ.start_slot, occ.end_slot + 1):
                    rk = (occ.room_id, occ.week, occ.day, slot)
                    if rk in room_grid and room_grid[rk] != occ.session_id:
                        conflicts.add(occ.session_id)
                        conflicts.add(room_grid[rk])
                    else:
                        room_grid[rk] = occ.session_id

                    if occ.teacher_id:
                        tk = (occ.teacher_id, occ.week, occ.day, slot)
                        if tk in teacher_grid and teacher_grid[tk] != occ.session_id:
                            conflicts.add(occ.session_id)
                            conflicts.add(teacher_grid[tk])
                        else:
                            teacher_grid[tk] = occ.session_id

            if not conflicts:
                break

            target_sid = int(rng.choice(sorted(conflicts)))
            target_index = gene_index_by_session[target_sid]
            gene = chromosome.genes[target_index]
            domain = domains[target_index]
            session = sessions[target_sid]
            teacher_id = sections[session.section_id].teacher_id
            step = 2 if is_alternating_session(problem, session) else 1

            candidate_slots = list(domain.start_slots); rng.shuffle(candidate_slots)
            candidate_days = list(domain.days); rng.shuffle(candidate_days)
            candidate_rooms = list(domain.room_ids); rng.shuffle(candidate_rooms)
            candidate_weeks = list(domain.start_weeks); rng.shuffle(candidate_weeks)

            best_choice = None
            found_free = False
            for w in candidate_weeks:
                weeks_occ = occurrence_weeks(problem, w, session.total_weeks, step)
                for d in candidate_days:
                    for sl in candidate_slots:
                        for r in candidate_rooms:
                            clash = False
                            for wk in weeks_occ:
                                for s_offset in range(session.duration_slots):
                                    cur_s = sl + s_offset
                                    rk = (r, wk, d, cur_s)
                                    if rk in room_grid and room_grid[rk] != target_sid:
                                        clash = True; break
                                    if teacher_id:
                                        tk = (teacher_id, wk, d, cur_s)
                                        if tk in teacher_grid and teacher_grid[tk] != target_sid:
                                            clash = True; break
                                if clash: break
                            if not clash:
                                best_choice = (r, d, sl, w)
                                found_free = True
                                break
                        if found_free: break
                    if found_free: break
                if found_free: break

            if best_choice:
                gene.room_id, gene.day, gene.start_slot, gene.start_week = best_choice

        return chromosome

    def _do(
        self,
        problem,
        X: NDArray[np.object_],
        *args,
        random_state: np.random.Generator | None = None,
        **kwargs,
    ) -> NDArray[np.object_]:
        instance = getattr(problem, "instance", problem)
        rng = random_state if random_state is not None else np.random.default_rng()
        repaired = np.empty_like(X, dtype=object)
        for index in range(X.shape[0]):
            chromosome = X[index, 0].copy()
            chromosome.rank = None
            chromosome.objectives = ()
            chromosome.constraint_violation = 0.0
            repaired[index, 0] = self._repair_chromosome(instance, chromosome, rng)
        return repaired

def create_reference_directions(n_objectives: int, n_partitions: int) -> NDArray[np.float64]:
    # Tạo n = C(H + M - 1, M - 1) reference directions với H=n_partitions và M=n_objectives, shape (n, M).
    if n_objectives < 2:
        raise ValueError("n_objectives must be at least 2")
    if n_partitions < 1:
        raise ValueError("n_partitions must be positive")
    return get_reference_directions("das-dennis", n_dim=n_objectives, n_partitions=n_partitions)


def create_nsga3(*, n_objectives: int = N_SOFT_CONSTRAINTS, config: NSGA3Config, sampling: Sampling,
                 crossover: Crossover | None = None, mutation: Mutation | None = None,
                 repair: Repair | None = None) -> NSGA3:
    reference_directions = create_reference_directions(n_objectives, config.n_partitions)
    population_size = config.population_size or len(reference_directions)

    # Population nhỏ hơn số direction sẽ để nhiều direction không có đại diện.
    if population_size < len(reference_directions):
        raise ValueError(f"population_size must be at least {len(reference_directions)}")

    return NSGA3(
        ref_dirs=reference_directions, pop_size=population_size,
        n_offsprings=config.n_offsprings, sampling=sampling,
        crossover=crossover if crossover is not None else GeneBasedCrossover(config.crossover_probability),
        mutation=mutation if mutation is not None else GeneDomainMutation(config.mutation_probability),
        repair=repair if repair is not None else TimetableRepair(), eliminate_duplicates=False)

def _sync_chromosome_metadata(collection) -> None:
    if collection is None:
        return

    for individual in collection:
        chromosome = individual.X[0]

        if individual.F is not None:
            chromosome.objectives = tuple(float(value) for value in individual.F)

        if individual.CV is not None:
            chromosome.constraint_violation = float(individual.CV[0])

        rank = individual.get("rank")
        chromosome.rank = None if rank is None else int(rank)

def run_nsga3(*, problem_instance: ProblemInstance, n_objectives: int = N_SOFT_CONSTRAINTS,
              n_constraints: int = N_CONSTRAINT_OUTPUTS, evaluator: Evaluator = EVALUATOR,
              config: NSGA3Config | None = None, repair: Repair | None = None,
              verbose: bool = False, save_history: bool = False):
    config = config or NSGA3Config()
    problem = TimetableProblem(problem_instance, evaluator, n_objectives=n_objectives, n_constraints=n_constraints)
    sampling = ChromosomeSampling()
    algorithm = create_nsga3(n_objectives=n_objectives, config=config, sampling=sampling, repair=repair)
    result = minimize(
        problem, algorithm, 
        termination=("n_gen", config.n_generations),
        seed=config.seed, verbose=verbose,
        save_history=save_history)
    
    _sync_chromosome_metadata(result.pop)
    _sync_chromosome_metadata(result.opt)

    return result
