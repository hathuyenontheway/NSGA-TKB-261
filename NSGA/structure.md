# Cấu trúc project đề xuất

## 1. Cấu trúc tổng thể

```text
NSGA/
├── README.md
├── structure.md
├── requirements.txt
├── config.yaml
├── main.py
│
├── data/
│   ├── README.md
│   ├── raw/
│   ├── processed/
│   └── prepare_data.py
│
├── core/
│   ├── models.py
│   ├── build_problem.py
│   ├── assignment.py
│   └── evaluation.py
│
├── optimizer/
│   └── nsga3.py
│
├── output/
│   └── reporting.py
│
└── tests/
    ├── test_data.py
    ├── test_problem.py
    ├── test_assignment.py
    └── test_optimizer.py
```

Cấu trúc này ưu tiên ít thư mục và ít file, nhưng vẫn tách được bốn phần chính: dữ liệu, xây bài toán, tối ưu và báo cáo.

## 2. Các file ở thư mục gốc

### `README.md`

Đặc tả nghiệp vụ và thuật toán:

- mục tiêu bài toán;
- quy tắc mở môn;
- ưu tiên sinh viên;
- constraint và objective;
- NSGA-III;
- ranking, violation và hiệu chỉnh thủ công.

### `structure.md`

Mô tả cấu trúc source code, trách nhiệm từng module và quan hệ phụ thuộc.

### `requirements.txt`

Các dependency tối thiểu:

```text
pandas
numpy
openpyxl
pyyaml
pymoo
ortools
pytest
```

`ortools` chỉ bắt buộc khi triển khai bộ phân sinh viên chính xác bằng CP-SAT.

### `config.yaml`

Chứa toàn bộ tham số thay đổi theo học kỳ. Không viết cứng các giá trị này trong source code.

```yaml
semester_id: "261"

course_opening:
  min_lecture_students: 15
  min_lab_students: 10
  mandatory_forecast_size: 15

calendar:
  allowed_days: [2, 3, 4, 5, 6, 7]
  max_slot: 12
  lab_start_slots: [2, 8]

campus:
  minimum_empty_slots: 2

student_priority:
  epsilon_f1: 0.0
  epsilon_f2: 0.0

nsga3:
  population_size: 128
  generations: 300
  reference_partitions: 3
  seed: 42
```

### `main.py`

Điểm chạy duy nhất của pipeline:

```python
def main() -> None:
    config = load_config("config.yaml")
    prepared_data = load_processed_data(config)
    problem = build_problem(prepared_data, config)
    solutions = run_nsga3(problem, config)
    ranked_solutions = rank_solutions(solutions, problem, config)
    export_results(ranked_solutions, config)
```

`main.py` chỉ điều phối, không chứa logic làm sạch, constraint hoặc thuật toán tiến hóa.

## 3. Thư mục `data/`

```text
data/
├── README.md
├── raw/
├── processed/
└── prepare_data.py
```

### `data/raw/`

Chứa file nguồn và không được chỉnh sửa trực tiếp:

```text
KHGD(1).DBF
calendar.csv
kq_nv.csv
mh.csv
chmh.csv
room261.csv
ref_map252.csv
ref_map261.csv
TAM252.xlsx
TAM261.xlsx
```

### `data/processed/`

Chứa snapshot dữ liệu đã chuẩn hóa:

```text
data/processed/<snapshot_id>/
├── metadata.json
├── courses.csv
├── khgd.csv
├── calendar.csv
├── registrations.csv
├── eligible_registrations.csv
├── rejected_registrations.csv
├── enrollment_counts.csv
├── student_registrations.csv
├── course_conflict_matrix.csv
├── rooms.csv
├── course_session_room_property.csv
├── course_allowed_rooms.csv
└── data_quality_report.json
```

### `data/prepare_data.py`

Chịu trách nhiệm toàn bộ pipeline dữ liệu:

```python
extract_data()

clean_khgd()
clean_calendar()
clean_courses()
clean_registrations()
clean_rooms()
clean_reference_maps()

deduplicate_registrations()
build_eligible_registrations()
build_enrollment_counts()
build_student_registrations()
build_course_conflict_matrix()
build_course_room_mapping()

validate_data()
export_processed_data()
```

File này không quyết định lịch và không chứa thuật toán NSGA-III.

## 4. Thư mục `core/`

### `core/models.py`

Chứa toàn bộ dataclass và cấu trúc trao đổi giữa các module:

```python
Student
Course
Registration
Room
AcademicWeek
Section
Session
Teacher

Gene
Chromosome
StudentAssignment
Violation
EvaluationResult
ProblemInstance
```

Một `Violation` tối thiểu cần có:

```python
@dataclass
class Violation:
    code: str
    priority: str
    severity: str
    message: str
    location: dict
    affected_entities: dict
    current_value: object | None
    required_value: object | None
    suggested_actions: list[str]
```

Một `EvaluationResult` tối thiểu cần có:

```python
@dataclass
class EvaluationResult:
    raw_objectives: tuple[float, ...]
    normalized_objectives: tuple[float, ...]
    violations: list[Violation]
    constraint_key: tuple[int, ...]
    student_assignment: list[StudentAssignment]
    student_impact: dict
```

### `core/build_problem.py`

Chuyển dữ liệu đã clean thành đầu vào cho optimizer:

```python
select_open_courses()
build_sections()
link_lecture_lab()
build_sessions()
build_allowed_rooms()
detect_room_bottlenecks()
build_problem_instance()
```

Đầu ra duy nhất:

```python
ProblemInstance(
    students,
    courses,
    registrations,
    rooms,
    sections,
    sessions,
    calendar,
    course_conflict_matrix,
)
```

### `core/assignment.py`

Phân sinh viên vào lớp cho một chromosome:

```python
assign_students_fast()
assign_students_exact()
validate_assignment()
calculate_student_impact()
```

`assign_students_fast()` dùng heuristic trong quá trình tiến hóa.

`assign_students_exact()` dùng CP-SAT cho:

- các nghiệm elite;
- nghiệm thuộc tập kết quả cuối;
- phương án sau hiệu chỉnh thủ công.

Interface chung:

```python
def assign_students(
    problem: ProblemInstance,
    chromosome: Chromosome,
    exact: bool = False,
) -> AssignmentResult:
    ...
```

### `core/evaluation.py`

Chứa toàn bộ constraint, objective và violation report.

#### Constraint

```python
check_mandatory_courses()
check_calendar()
check_room_compatibility()
check_room_capacity()
check_room_conflicts()
check_section_conflicts()
check_student_assignment()
check_lecture_lab()
check_campus_travel()
check_lecturer_conflicts()
check_saturday_policy()
```

Mỗi hàm trả về `list[Violation]`.

#### Objective

```python
calculate_unfulfilled_registration_rate()  # F1
calculate_incomplete_student_rate()        # F2
calculate_student_schedule_penalty()       # F3
calculate_saturday_session_rate()          # F4
calculate_campus_movement_penalty()        # F5
calculate_room_capacity_waste_rate()       # F6
calculate_room_load_imbalance()            # F7
calculate_lecturer_schedule_penalty()      # F8
```

#### Điều phối đánh giá

```python
evaluate_fast(problem, chromosome)
evaluate_exact(problem, chromosome)
normalize_objectives(population)
build_constraint_key(violations)
```

Constraint quyết định tính khả thi. Objective chỉ được dùng để đánh đổi giữa các nghiệm có cùng mức khả thi.

## 5. Thư mục `optimizer/`

### `optimizer/nsga3.py`

Chứa toàn bộ logic tiến hóa:

```python
generate_reference_directions()
initialize_population()
repair_chromosome()
crossover()
mutate()
apply_constraint_domination()
associate_reference_directions()
environmental_selection()
run_nsga3()
```

Nên sử dụng `pymoo` cho non-dominated sorting, reference directions và NSGA-III environmental selection. Code của project tập trung vào:

- cách biểu diễn chromosome;
- initialization phù hợp miền phòng/thời gian;
- crossover và mutation;
- repair;
- kết nối evaluator với `pymoo`;
- checkpoint và seed.

Quy trình:

```text
initialize
    │
    ▼
repair
    │
    ▼
evaluate_fast
    │
    ▼
constraint-domination
    │
    ▼
normalize objectives
    │
    ▼
associate reference directions
    │
    ▼
environmental selection
    │
    ▼
crossover + mutation
    │
    └──────────── lặp theo generation
```

Các nghiệm cuối phải được đánh giá lại bằng `evaluate_exact()`.

## 6. Thư mục `output/`

### `output/reporting.py`

Chứa ranking và xuất kết quả:

```python
assign_feasibility_tier()
calculate_decision_rank()
label_special_solutions()
compare_solutions()

export_ranking()
export_schedule()
export_student_assignment()
export_student_impact()
export_violations()
export_run_metadata()
```

Khóa decision rank:

```python
decision_key = (
    feasibility_tier,
    mandatory_courses_unscheduled,
    unfulfilled_registration_rate,
    incomplete_student_rate,
    saturday_session_rate,
    campus_movement_penalty,
    room_capacity_waste_rate,
    room_load_imbalance,
    lecturer_schedule_penalty,
)
```

Output:

```text
outputs/<run_id>/
├── metadata.json
├── ranking.csv
├── schedules/
│   └── chromosome_<id>.csv
├── assignments/
│   └── chromosome_<id>.csv
├── student_impact/
│   └── chromosome_<id>.csv
└── violations/
    └── chromosome_<id>.csv
```

Chỉ cần xuất chi tiết cho các chromosome tốt nhất hoặc được người dùng chọn, không xuất toàn bộ quần thể.

## 7. Thư mục `tests/`

### `test_data.py`

- schema và encoding;
- khóa đăng ký;
- khử trùng;
- nối KHGD–đăng ký;
- ánh xạ `F_TCPHONG`–phòng.

### `test_problem.py`

- mở môn bắt buộc;
- ngưỡng môn tự chọn;
- số lớp cần mở;
- lecture–lab;
- allowed rooms;
- room bottleneck.

### `test_assignment.py`

- một lớp/môn/sinh viên;
- không trùng lịch;
- không vượt sĩ số;
- lecture–lab tương thích;
- di chuyển cơ sở;
- F1 và F2.

### `test_optimizer.py`

- initialization hợp lệ;
- crossover/mutation không làm mất session;
- repair;
- constraint-domination;
- objective normalization;
- reference-direction association;
- cùng seed cho cùng kết quả;
- chạy end-to-end trên fixture nhỏ.

## 8. Quan hệ phụ thuộc

Các module chỉ phụ thuộc theo một chiều:

```text
data.prepare_data
        │
        ▼
core.models
        │
        ▼
core.build_problem
        │
        ├─────────────┐
        ▼             ▼
core.assignment   core.evaluation
        │             │
        └──────┬──────┘
               ▼
       optimizer.nsga3
               │
               ▼
       output.reporting
               │
               ▼
             main
```

Quy tắc:

- `data/` không import optimizer;
- `core/` không import reporting;
- `optimizer/` chỉ nhận `ProblemInstance` và gọi evaluator;
- `reporting.py` không thay đổi chromosome;
- `main.py` không chứa nghiệp vụ.

## 9. Luồng chạy

Chuẩn bị dữ liệu:

```text
python data/prepare_data.py --config config.yaml
```

Chạy tối ưu:

```text
python main.py --config config.yaml
```

Chạy kiểm thử:

```text
pytest
```

## 10. Phạm vi MVP

MVP chỉ cần:

- một học kỳ;
- một khoa hoặc nhóm chương trình;
- lecture và lab;
- giảng viên tạm;
- heuristic student assignment trong evolution;
- exact assignment cho nghiệm cuối;
- F1–F8;
- ranking, violation report và CSV/JSON output;
- hiệu chỉnh thủ công bằng cách sửa chromosome hoặc file operation rồi đánh giá lại.

Chưa cần giao diện kéo-thả, tối ưu nhiều học kỳ, phân tán nhiều máy hoặc cập nhật thời gian thực.
