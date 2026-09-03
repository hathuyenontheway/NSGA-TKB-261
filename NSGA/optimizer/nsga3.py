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

from core.assignment import create_random_chromosome, validate_chromosome_structure
from core.models import Chromosome, ProblemInstance
from core.evaluation import evaluator

FloatVector = NDArray[np.float64]  # Vector objective hoặc constraint.
Evaluator = Callable[[ProblemInstance, Chromosome], tuple[FloatVector, FloatVector | None]]  # (F, G).
N_HARD_CONSTRAINTS = 10
N_SOFT_CONSTRAINTS = 8
EVALUATOR: Evaluator = evaluator


@dataclass(slots=True)
class ChromosomeArrays:
    room_ids: NDArray[np.object_]   # Phòng của từng Gene.
    days: NDArray[np.int64]         # Ngày học của từng Gene.
    start_slots: NDArray[np.int64]  # Tiết bắt đầu của từng Gene.
    start_weeks: NDArray[np.int64]  # Tuần bắt đầu của từng Gene.

    # Ví dụ 3 Gene:
    # room_ids=["A1-101", "B1-203", "C4-401"], days=[2, 3, 5], start_slots=[1, 4, 7], start_weeks=[1, 1, 2]. 
    # Mỗi mảng có shape (3,).

    @property
    def size(self) -> int:
        return len(self.days)


def chromosome_to_arrays(chromosome: Chromosome) -> ChromosomeArrays:
    # VD: Gene("A1-101", day=2, slot=1, week=1)
    return ChromosomeArrays(
        room_ids=np.asarray([gene.room_id for gene in chromosome.genes], dtype=object),
        days=np.asarray([gene.day for gene in chromosome.genes], dtype=np.int64),
        start_slots=np.asarray([gene.start_slot for gene in chromosome.genes], dtype=np.int64),
        start_weeks=np.asarray([gene.start_week for gene in chromosome.genes], dtype=np.int64)
    )


def arrays_to_chromosome(template: Chromosome, arrays: ChromosomeArrays) -> Chromosome:
    # Ví dụ 589 Gene -> expected_shape=(589,).
    expected_shape = (len(template.genes),)
    actual_shapes = {arrays.room_ids.shape, arrays.days.shape, arrays.start_slots.shape, arrays.start_weeks.shape}
    # Nếu cả bốn mảng có shape (589,), set trên rút gọn thành {(589,)}.
    # Nếu days chỉ có 588 phần tử, kết quả thành {(589,), (588,)} và báo lỗi.

    if actual_shapes != {expected_shape}:
        raise ValueError(f"Every chromosome array must have shape {expected_shape}; Received {sorted(actual_shapes)}")

    chromosome = template.copy()
    for index, gene in enumerate(chromosome.genes):
        gene.room_id = str(arrays.room_ids[index])
        gene.day = int(arrays.days[index])
        gene.start_slot = int(arrays.start_slots[index])
        gene.start_week = int(arrays.start_weeks[index])

    return chromosome


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
        objectives, constraints = self.evaluator(self.instance, chromosome)

        objectives = np.asarray(objectives, dtype=float) # Ví dụ ba objective: F=[12.0, 4.0, 90.0], shape=(3,).
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
class DomainRestrictedRoomMutation(Mutation):
    def __init__(self, probability: float) -> None:
        super().__init__(prob=probability)

    # Ví dụ 120 offspring -> X có shape (120, 1).
    def _do(self, problem: TimetableProblem, X: NDArray[np.object_], *args, random_state: np.random.Generator | None = None, **kwargs) -> NDArray[np.object_]:
        if random_state is None:
            raise RuntimeError("pymoo did not provide random_state")

        offspring = np.empty_like(X, dtype=object)
        domains = problem.instance.gene_domains  # ProblemInstance.gene_domains

        for i in range(X.shape[0]):
            chromosome = X[i, 0].copy() # Chromosome.copy()
            chromosome.rank = None
            chromosome.objectives = ()
            chromosome.constraint_violation = 0.0

            if len(chromosome.genes) != len(domains):
                raise ValueError("Gene count does not match the GeneDomain count")

            # VD: candidates (7, ("A1-101", "B1-203")) nghĩa là Gene index 7 có thể đổi sang một trong hai phòng này.
            candidates: list[tuple[int, tuple[str, ...]]] = []
            for g_index, (gene, domain) in enumerate(zip(chromosome.genes, domains, strict=True)):
                if gene.session_id != domain.session_id:
                    raise ValueError("GeneDomain order does not match gene order")

                alt_rooms = tuple(room_id for room_id in domain.room_ids if room_id != gene.room_id)
                if alt_rooms:
                    candidates.append((g_index, alt_rooms))

            if candidates:
                candidate_i = int(random_state.integers(0, len(candidates)))
                gene_i, alt_rooms = candidates[candidate_i]
                new_room_i = int(random_state.integers(0, len(alt_rooms)))
                chromosome.genes[gene_i].room_id = alt_rooms[new_room_i]
            offspring[i, 0] = chromosome

        return offspring


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
        ref_dirs=reference_directions,
        pop_size=population_size,
        n_offsprings=config.n_offsprings,
        sampling=sampling,
        crossover=crossover if crossover is not None else GeneBasedCrossover(config.crossover_probability),
        mutation=mutation if mutation is not None else DomainRestrictedRoomMutation(config.mutation_probability),
        repair=repair,
        eliminate_duplicates=False)


def run_nsga3(*, problem_instance: ProblemInstance, n_objectives: int,
              n_constraints: int = 0, evaluator: Evaluator = EVALUATOR,
              config: NSGA3Config | None = None,
              repair: Repair | None = None, verbose: bool = False, save_history: bool = False):
    config = NSGA3Config()
    problem = TimetableProblem(problem_instance, evaluator, n_objectives=n_objectives, n_constraints=n_constraints)
    sampling = ChromosomeSampling()
    algorithm = create_nsga3(n_objectives=n_objectives, config=config, sampling=sampling, repair=repair)

    return minimize(
        problem,
        algorithm,
        termination=("n_gen", config.n_generations),
        seed=config.seed,
        verbose=verbose,
        save_history=save_history)
