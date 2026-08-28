# Bàn giao preprocessing cho NSGA-III

## 1. Mục đích

Tài liệu này chốt giao diện giữa hai phần:

1. **Preprocessing**: đọc và kiểm định CSV, chuẩn hóa dữ liệu, xác định tập môn có map, tạo section, session và miền giá trị của gene.
2. **NSGA-III**: nhận một `ProblemInstance` đã chuẩn bị, sinh/quản lý chromosome, repair, đánh giá constraint/objective và tiến hóa quần thể.

Workspace chính là `NSGA/`. Thư mục `GA - URA/preprocessing/` là draft cũ, chỉ dùng để tham khảo và **không phải API đầu vào của NSGA-III**.

Mốc hiện tại đã chạy thành công với cấu hình kiểm thử `HK_CHINH/HK1`:

| Chỉ số | Giá trị |
|---|---:|
| Môn trong KHGD | 696 |
| Môn KHGD có ít nhất một phòng hợp lệ | 589 |
| Môn KHGD chưa có phòng | 107 |
| Phòng trong danh mục | 496 |
| Tuần giảng dạy được chọn | 18 |
| Section kiểm thử | 589 |
| Session kiểm thử | 589 |
| Gene trong chromosome kiểm thử | 589 |

Lưu ý: 589 session là **mốc kiểm thử cấu trúc** theo quy ước một section/session cho mỗi môn có map, chưa phải số lớp chính thức của học kỳ. Khi có đăng ký sinh viên và quy tắc mở lớp chính thức, một môn có thể sinh nhiều section.

## 2. Cấu trúc file liên quan

```text
NSGA/
├── data/
│   ├── calendar.csv
│   ├── courses_khgd.csv
│   ├── courses_old.csv
│   ├── rooms.csv
│   ├── room_course_mapping_union.csv
│   ├── prepare_data.py
│   └── README.md
├── preprocessing/
│   └── README.md                  # tài liệu bàn giao này
├── core/
│   ├── models.py                 # cấu trúc dữ liệu dùng chung
│   ├── build_problem.py          # PreparedData -> ProblemInstance
│   └── assignment.py             # tạo/kiểm tra chromosome cơ bản
├── optimizer/
│   └── nsga3.py                  # team NSGA-III triển khai tại đây
├── tests/
│   ├── test_data.py
│   ├── test_problem.py
│   └── run_chromosome_smoke.py
└── requirements.txt
```

## 3. Nguồn và vai trò của dữ liệu

Các CSV trong `NSGA/data/` là sản phẩm preprocessing do team tạo từ KHGD, danh mục phòng và hai file TAM. Hai file TAM là dữ liệu lịch sử để tham khảo quan hệ môn–phòng; optimizer không đọc trực tiếp TAM.

### 3.1. `courses_khgd.csv`

Danh sách môn thuộc KHGD cần xem xét trong học kỳ. Đây là nguồn course chính khi dựng bài toán.

Khóa duy nhất: `course_id`.

| Cột | Kiểu sau khi load | Ý nghĩa |
|---|---|---|
| `course_id` | `str` | Mã môn; lecture và lab có mã môn khác nhau |
| `course_name` | `str` | Tên môn |
| `faculty_id` | `str` | Mã khoa phụ trách |
| `faculty_name` | `str` | Tên khoa |
| `credits` | `float` | Số tín chỉ |
| `total_hours` | `int` | Tổng số giờ |
| `lecture_hours` | `int` | Số giờ lý thuyết |
| `exercise_hours` | `int` | Số giờ bài tập |
| `lab_hours` | `int` | Số giờ thí nghiệm/lab |
| `project_hours` | `int` | Số giờ đồ án |
| `assignment_hours` | `int` | Số giờ bài tập lớn |
| `thesis_hours` | `int` | Số giờ luận văn |
| `course_type` | enum | `LECTURE`, `LAB`, `PRACTICAL` hoặc `UNKNOWN` |
| `companion_course_id` | `str | None` | Mã môn lecture/lab đi kèm nếu có |
| `resource_type` | `str` | Nhãn tài nguyên hiện tại |
| `resource_confidence` | `float` | Độ tin cậy của nhãn tài nguyên |

Trạng thái snapshot: 696 dòng, không trùng `course_id`.

Quy tắc khóa đăng ký vẫn là `(student_id, course_id)`. Vì lecture và lab có hai `course_id` khác nhau nên hai đăng ký không bị khử trùng lặp nhầm.

### 3.2. `courses_old.csv`

Danh mục môn lịch sử dùng để tra cứu hoặc bổ sung metadata. File này không quyết định môn nào được mở trong học kỳ.

Schema giống `courses_khgd.csv`. Snapshot hiện có 10.560 môn và chứa toàn bộ 696 mã môn KHGD.

Quy tắc sử dụng:

- `courses_khgd.csv` quyết định phạm vi học kỳ.
- `courses_old.csv` chỉ là catalog/fallback.
- Không tự động đưa một môn từ `courses_old.csv` vào bài toán nếu môn đó không nằm trong KHGD hoặc không đạt quy tắc mở môn.

### 3.3. `rooms.csv`

Danh mục phòng chính thức.

Khóa duy nhất: `room_id`.

| Cột | Kiểu sau khi load | Ý nghĩa |
|---|---|---|
| `room_id` | `str` | Mã phòng |
| `campus` | `int` | Cơ sở 1 hoặc 2 |
| `capacity` | `int` | Sức chứa phòng |
| `room_type` | `str` | Tính chất/mã loại phòng từ dữ liệu nguồn |
| `resource_type` | `str` | Nhãn tài nguyên tổng quát |

Snapshot hiện có 496 phòng, không trùng `room_id`.

`resource_type` hiện chủ yếu là `GENERAL`, vì vậy quan hệ tương thích môn/session–phòng phải lấy từ map môn–phòng, không được suy ra chỉ bằng cột này.

### 3.4. `room_course_mapping_union.csv`

Sản phẩm hợp nhất quan hệ phòng–môn được suy ra từ KHGD, rooms và hai file TAM.

Ý nghĩa nghiệp vụ:

- `course -> rooms`: những phòng một môn/session có thể sử dụng.
- `room -> courses`: những môn có thể xếp vào một phòng.
- Đây là constraint miền của gene, không phải một objective mềm.

File hiện tại được xuất dạng fixed-width nhưng mang đuôi `.csv`. `prepare_data.py` có parser tương thích định dạng này. Loader cũng hỗ trợ định dạng chuẩn được khuyến nghị:

```csv
course_id,room_id
CH2053,B2-404
CH2111,B2-404
```

Nên chốt một bảng quan hệ chuẩn, mỗi dòng là một cặp `(course_id, room_id)`. Hai dictionary hai chiều phải được sinh từ cùng bảng này để không lệch dữ liệu.

Sau khi loại các phòng không tồn tại trong `rooms.csv`, snapshot có 589/696 môn KHGD có miền phòng hợp lệ.

### 3.5. `calendar.csv`

Lịch tuần của năm học. Một lần chạy chỉ chọn đúng một cặp `(track, semester_id)`.

Khóa logic: `(track, semester_id, week)`.

| Cột | Kiểu sau khi load | Ý nghĩa |
|---|---|---|
| `track` | `str` | Hệ lịch như `HK_CHINH`, `NAM_1`, `HK_NGOAI_GIO`, `HK_HE` |
| `semester_id` | `str` | `HK1`, `HK2` hoặc `HE` |
| `week` | `int` | Số tuần liên tục trong năm học |
| `start_date` | `date` | Ngày bắt đầu tuần |
| `end_date` | `date` | Ngày kết thúc tuần |
| `is_teaching` | `bool` | Tuần có giảng dạy |
| `is_midterm` | `bool` | Tuần giữa kỳ |
| `is_final` | `bool` | Tuần thi cuối kỳ |
| `is_holiday` | `bool` | Tuần có ngày nghỉ |
| `holiday_dates` | `tuple[date, ...]` | Các ngày nghỉ, hỗ trợ phân cách bằng `,` hoặc `;` |
| `notes` | `str` | Ghi chú |

Với test hiện tại, `track="HK_CHINH"` và `semester_id="HK1"` cho 18 tuần có `is_teaching=True`.

### 3.6. Dữ liệu đăng ký sinh viên

Snapshot hiện tại chưa có file đăng ký trong `NSGA/data/`. Loader đã chuẩn bị hai schema:

Schema rút gọn:

```csv
student_id,course_id
SV001,CO1001
SV001,CO1002
```

Schema nguồn:

```text
F_MASV -> student_id
F_MAMH -> course_id
```

Loader chỉ giữ các khóa `(student_id, course_id)` duy nhất. Các cột khác của `kq_nv.csv` không cần thiết cho bước xây ma trận đăng ký cơ bản.

Khi chưa có file đăng ký, `registrations=()` và builder dùng sĩ số tạm cho môn bắt buộc.

## 4. Nội dung các module preprocessing

### 4.1. `data/prepare_data.py`

Đây là entry point đọc CSV. Hàm chính:

```python
prepare_data(
    data_dir,
    track="HK_CHINH",
    semester_id="HK1",
    registrations_file=None,
) -> PreparedData
```

Các bước thực hiện:

1. Kiểm tra schema và khóa `course_id` của hai file course.
2. Kiểm tra schema và khóa `room_id` của rooms.
3. Chọn calendar theo `track/semester_id` và sắp xếp theo tuần.
4. Đọc map chuẩn hoặc map fixed-width hiện tại.
5. Sinh `course_to_rooms` và `room_to_courses`.
6. Loại khỏi miền gene những phòng không tồn tại trong `rooms.csv`.
7. Đọc và khử trùng lặp đăng ký nếu file được cung cấp.
8. Tạo danh sách `DataIssue` để không làm mất thông tin lỗi dữ liệu.

Loader không xếp lịch, không sinh quần thể và không tính objective.

### 4.2. `core/build_problem.py`

Chuyển `PreparedData` thành `ProblemInstance`:

```python
build_problem_instance(prepared, policy) -> ProblemInstance
```

`BuildPolicy` hiện có:

| Thuộc tính | Mặc định | Ý nghĩa |
|---|---:|---|
| `mandatory_course_ids` | toàn bộ KHGD | Tập môn bắt buộc phải mở |
| `min_elective_students` | 15 | Ngưỡng mở môn tự chọn |
| `default_section_capacity` | 60 | Sức chứa section tạm |
| `default_mandatory_students` | 15 | Sĩ số dự báo khi chưa có đăng ký |
| `allowed_days` | 2–7 | Các thứ được phép |
| `slots_per_day` | 12 | Số tiết trong ngày |
| `default_session_slots` | 3 | Độ dài session tạm |

Luồng builder:

1. Sinh `student_to_courses` và `course_to_students` từ đăng ký.
2. Xác định môn mở: môn bắt buộc hoặc môn tự chọn đạt ngưỡng.
3. Tính số section bằng `ceil(enrollment / section_capacity)`.
4. Sinh `Section` và `Session`.
5. Gắn tập phòng hợp lệ từ `course_to_rooms`.
6. Sinh một `GeneDomain` cùng vị trí với từng session.
7. Báo `EMPTY_GENE_DOMAIN` nếu session không có phòng/ngày/tiết/tuần hợp lệ.

### 4.3. `core/assignment.py`

Phần hiện có chỉ phục vụ kiểm tra ranh giới preprocessing:

```python
create_random_chromosome(problem, rng) -> Chromosome
validate_chromosome_structure(problem, chromosome) -> list[str]
```

`create_random_chromosome` lấy ngẫu nhiên một giá trị trong mỗi `GeneDomain`. Hàm này chỉ đảm bảo gene thuộc miền; chưa đảm bảo không trùng phòng hoặc không trùng lịch.

`validate_chromosome_structure` kiểm tra:

- số gene bằng số session;
- thứ tự `session_id` đúng;
- room/day/start_slot/start_week nằm trong miền tương ứng.

## 5. Cấu trúc dữ liệu bàn giao

Các dataclass nằm trong `core/models.py`.

### 5.1. `Course`

Đại diện một mã môn độc lập. Lecture và lab là hai `Course` khác nhau nếu có hai mã môn khác nhau; `companion_course_id` dùng để liên kết nghiệp vụ giữa chúng.

### 5.2. `Room`

Chứa mã phòng, cơ sở, sức chứa và loại phòng. `Room` không tự chứa danh sách môn; quan hệ nhiều–nhiều nằm trong hai map của `PreparedData`.

### 5.3. `AcademicWeek`

Đại diện một tuần của đúng track/học kỳ, giữ cả ngày bắt đầu/kết thúc và các cờ teaching/midterm/final/holiday.

### 5.4. `Registration`

```python
Registration(student_id, course_id)
```

Khóa duy nhất là `(student_id, course_id)`.

### 5.5. `Section`

```python
Section(
    section_id,
    course_id,
    section_type,
    expected_students,
    max_capacity,
    parent_section_id=None,
    teacher_id=None,
)
```

`Section` là lớp học phần được mở. Một course có thể có nhiều section. `parent_section_id` dành cho liên kết lecture–lab; `teacher_id` hiện cho phép dùng giảng viên giả.

### 5.6. `Session`

```python
Session(
    session_id,
    section_id,
    course_id,
    session_type,
    duration_slots,
    total_weeks,
    allowed_room_ids,
    allowed_start_weeks,
    allowed_days,
    allowed_start_slots,
    parent_session_id=None,
)
```

Session là đơn vị được mã hóa thành một gene. `allowed_room_ids` phụ thuộc trực tiếp vào map môn–phòng.

### 5.7. `GeneDomain`

```python
GeneDomain(
    session_id,
    room_ids,
    days,
    start_slots,
    start_weeks,
)
```

Đây là search space cục bộ của một gene. Thứ tự `gene_domains` phải giống chính xác thứ tự `sessions`.

### 5.8. `Gene` và `Chromosome`

```python
Gene(
    session_id,
    room_id,
    day,
    start_slot,
    start_week,
)

Chromosome(
    genes,
    rank=None,
    objectives=(),
    constraint_violation=0.0,
)
```

Quy ước quan trọng:

- Một session tương ứng đúng một gene.
- Gene ở vị trí `i` phải thuộc `gene_domains[i]` và tham chiếu `sessions[i]`.
- Crossover/mutation không được thêm, mất hoặc đổi `session_id`.
- Thay đổi lịch chỉ được thay `room_id`, `day`, `start_slot`, `start_week` trong miền.
- `rank`, `objectives` và `constraint_violation` là metadata do evaluator/NSGA-III cập nhật.

### 5.9. `PreparedData`

Đầu ra của loader:

```python
PreparedData(
    courses,
    catalog_courses,
    rooms,
    calendar,
    course_to_rooms,
    room_to_courses,
    registrations,
    issues,
)
```

Các mapping được đóng bằng `MappingProxyType`; NSGA-III không được sửa dữ liệu nền trong khi tiến hóa.

### 5.10. `ProblemInstance`

Contract chính giao cho optimizer:

```python
ProblemInstance(
    courses,
    rooms,
    weeks,
    sections,
    sessions,
    gene_domains,
    registrations,
    student_to_courses,
    course_to_students,
    issues,
)
```

`ProblemInstance.__post_init__` kiểm tra `session_id` duy nhất và thứ tự session–domain khớp nhau.

Team NSGA-III chỉ nên nhận `ProblemInstance`; không đọc CSV trực tiếp trong `optimizer/nsga3.py`.

## 6. DataIssue và trạng thái chất lượng dữ liệu

| Code | Severity hiện tại | Ý nghĩa |
|---|---|---|
| `ORPHAN_MAPPING_ROOM` | `ERROR` | Map tham chiếu phòng không tồn tại trong rooms |
| `COURSE_WITHOUT_ROOM` | `ERROR` | Môn KHGD không có phòng hợp lệ |
| `ROOM_BOTTLENECK` | `WARNING` | Môn chỉ có 1–2 phòng hợp lệ |
| `EMPTY_GENE_DOMAIN` | `ERROR` | Không thể mã hóa session do ít nhất một miền rỗng |

Kết quả snapshot hiện tại:

```text
COURSE_WITHOUT_ROOM : 107
ORPHAN_MAPPING_ROOM : 44
ROOM_BOTTLENECK     : 35
```

Các issue phải được giữ để báo cáo. Không tự động gán mọi phòng cho môn thiếu map vì sẽ phá constraint môn/session phụ thuộc phòng.

## 7. Luồng dữ liệu hoàn chỉnh

```text
CSV sản phẩm của preprocessing
        │
        ▼
prepare_data(...)
        │
        ├── kiểm tra schema/khóa
        ├── chọn calendar
        ├── tạo map hai chiều
        ├── loại quan hệ phòng mồ côi khỏi miền
        └── ghi DataIssue
        │
        ▼
PreparedData
        │
        ▼
build_problem_instance(...)
        │
        ├── mở môn
        ├── chia section
        ├── tạo session
        └── tạo GeneDomain
        │
        ▼
ProblemInstance
        │
        ▼
create_random_chromosome(...)
        │
        ▼
Chromosome gồm đúng một gene/session
        │
        ▼
NSGA-III: repair → evaluate → select → crossover/mutation
```

## 8. Cách chạy kiểm thử bàn giao

Từ thư mục repository:

```powershell
cd D:\URA\NSGAII\NSGA
```

Test nhanh, không cần pytest:

```powershell
D:\URA\NSGAII\venv\Scripts\python.exe tests\run_chromosome_smoke.py
```

Kết quả đạt yêu cầu:

```text
PASS: chromosome input is structurally valid
KHGD courses       : 696
Mapped courses     : 589
Teaching weeks     : 18
Sections/sessions  : 589
Chromosome genes   : 589
```

Chạy test suite:

```powershell
D:\URA\NSGAII\venv\Scripts\python.exe -m pip install -r requirements.txt
D:\URA\NSGAII\venv\Scripts\python.exe -m pytest -q
```

## 9. Tiêu chí chốt preprocessing

Preprocessing được xem là bàn giao được khi:

- [x] Course và room có khóa duy nhất.
- [x] Calendar chọn được đúng track/học kỳ.
- [x] Map sinh được hai chiều từ cùng một nguồn.
- [x] Phòng mồ côi không đi vào `GeneDomain`.
- [x] Mỗi session có đúng một domain cùng `session_id`.
- [x] Tạo được chromosome 589 gene cho 589 môn KHGD có map trong snapshot.
- [x] Chromosome kiểm thử chỉ chứa giá trị thuộc domain.
- [ ] Team nghiệp vụ xác nhận cách xử lý 107 môn chưa có phòng.
- [ ] Team nghiệp vụ cung cấp/chốt file đăng ký sinh viên.
- [ ] Chốt cờ môn bắt buộc/tự chọn trong KHGD.
- [ ] Chốt ngưỡng mở môn tự chọn.
- [ ] Chốt sức chứa section và cách chia nhiều section.
- [ ] Chốt cách suy ra `duration_slots` và `total_weeks` từ số giờ.
- [ ] Chốt liên kết section/session lecture–lab qua `companion_course_id`.
- [ ] Chốt lịch áp dụng cho từng chương trình nếu có nhiều `track`.

Các mục chưa chốt đang dùng giá trị tạm trong `BuildPolicy`. Không nên coi chúng là quy tắc chính thức.

## 10. Contract dành cho team NSGA-III

Team optimizer có thể bắt đầu code các phần không phụ thuộc quy tắc nghiệp vụ chưa chốt:

1. Population là danh sách `Chromosome`.
2. Initialization lấy mẫu theo `problem.gene_domains`.
3. Mutation chỉ chọn giá trị mới trong domain của cùng `session_id`.
4. Crossover giữ nguyên số gene và thứ tự session.
5. Repair xử lý xung đột phòng/thời gian nhưng không được đưa gene ra ngoài domain.
6. Evaluator đọc metadata từ `problem.sessions`, `problem.rooms`, registrations và các index sinh viên.
7. Không sửa trực tiếp `ProblemInstance` hoặc các mapping bất biến.
8. Mỗi chromosome sau operator phải qua `validate_chromosome_structure` trước khi đánh giá constraint nghiệp vụ.

Các phần optimizer nên chờ dữ liệu đăng ký/quy tắc được chốt:

- objective tối đa môn sinh viên được học;
- incomplete-student rate;
- phân sinh viên vào nhiều section;
- conflict matrix chính thức;
- mở môn tự chọn theo ngưỡng;
- số section thực tế của từng môn.

## 11. Phạm vi chưa được test ở mốc hiện tại

Test 589 session chỉ xác nhận cấu trúc. Nó chưa chứng minh chromosome là thời khóa biểu khả thi. Các kiểm tra sau thuộc evaluator/repair:

- hai session không chiếm cùng phòng cùng thời gian;
- phòng đủ sức chứa section;
- sinh viên không học hai môn trùng lịch;
- lecture và lab liên kết đúng;
- không xếp hai cơ sở liên tiếp hoặc cách nhau một tiết;
- ưu tiên tránh thứ Bảy, chỉ dùng khi cần;
- ràng buộc giảng viên;
- tuần nghỉ và ngày nghỉ cụ thể;
- ranking, objectives và violation report.

Đây là ranh giới bàn giao: preprocessing cung cấp dữ liệu và miền gene nhất quán; NSGA-III chịu trách nhiệm tìm, sửa và xếp hạng các chromosome theo constraint/objective.
