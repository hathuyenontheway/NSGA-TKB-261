# Tối ưu hóa mở lớp, phân sinh viên và xếp thời khóa biểu bằng NSGA-III

> Đặc tả hợp nhất sau các trao đổi với Phòng Đào tạo, cập nhật từ ngày 29/07/2026.

## 1. Bối cảnh

Hệ thống xây dựng phương án học kỳ từ ba nhóm thông tin chính:

- các môn thuộc chương trình/kế hoạch giảng dạy của học kỳ trong `KHGD(1).DBF`;
- kết quả đăng ký môn của từng sinh viên trong `data/kq_nv.csv`;
- phòng học, tính chất phòng và lịch học kỳ.

Ưu tiên cao nhất là giúp sinh viên học được nhiều nhất các môn hợp lệ đã đăng ký mà không trùng lịch. Vì lịch mở lớp và việc phân sinh viên phụ thuộc lẫn nhau, hai công việc này được giải trong **một bài toán tối ưu hợp nhất**, thay vì xếp lịch trước rồi mới phân sinh viên.

Giảng viên được xét sau quyền lợi sinh viên. Khi chưa có dữ liệu giảng viên chính thức, hệ thống sử dụng giảng viên tạm theo quy ước ở mục 10.

## 2. Phạm vi bài toán

### 2.1. Bài toán chính — Lập kế hoạch học kỳ hợp nhất

Bài toán chính đồng thời:

1. xác định môn bắt buộc và môn tự chọn được mở;
2. xác định số lớp học phần của từng môn và chương trình;
3. tạo các session lý thuyết, lab và thực hành;
4. xác định tập phòng hợp lệ của từng session;
5. xếp phòng, ngày, tiết và tuần học;
6. phân từng sinh viên vào một lớp cụ thể của mỗi môn đã đăng ký;
7. đánh giá số đăng ký được đáp ứng và chất lượng lịch của từng sinh viên;
8. tạo nhiều phương án đánh đổi bằng NSGA-III;
9. xếp hạng, giải thích vi phạm và hỗ trợ hiệu chỉnh thủ công.

### 2.2. Bài toán cập nhật sau công bố

Sau khi có lịch chính thức, hệ thống tiếp nhận thay đổi như sinh viên thêm/hủy môn, đổi lớp, mở/ghép/hủy lớp hoặc thay đổi giảng viên. Phương án mới phải hợp lệ và giữ ổn định tối đa so với baseline.

## 3. Nguyên tắc ưu tiên

Khi tài nguyên không đủ, áp dụng thứ tự:

1. Không vi phạm các ràng buộc cứng.
2. Mở và xếp 100% môn bắt buộc trong `KHGD(1).DBF`.
3. Tối đa hóa tổng số lượt đăng ký hợp lệ mà sinh viên có thể học.
4. Tối đa hóa số sinh viên học được toàn bộ các môn hợp lệ đã đăng ký và bảo đảm công bằng giữa sinh viên.
5. Mở môn tự chọn đủ ngưỡng theo mức nhu cầu giảm dần.
6. Hạn chế thứ Bảy và việc di chuyển giữa CS1–CS2.
7. Tối ưu phòng, phân bố lịch và tải giảng viên.

Không được dùng lợi ích về phòng hoặc giảng viên để bù cho vi phạm cứng hay làm giảm đáng kể khả năng học của sinh viên.

## 4. Pipeline mục tiêu

```text
KHGD(1).DBF                         kq_nv.csv
(môn của học kỳ)                    (đăng ký từng sinh viên)
          │                                      │
          └──────────────┬───────────────────────┘
                         ▼
       Chuẩn hóa và nối theo môn + chương trình
                         │
                         ▼
  Môn bắt buộc phải mở + môn tự chọn đạt ngưỡng
                         │
                         ▼
      Chia lớp + tạo session + xung đột sinh viên
                         │
                         ▼
 ref_map252/261 ─► tính chất phòng ─► room261.csv
                         │
                         ▼
       calendar.csv ─► miền thời gian hợp lệ
                         │
                         ▼
      NSGA-III: lịch lớp + phân sinh viên đồng thời
                         │
                         ▼
   Constraint report + objective vector + student impact
                         │
                         ▼
      Pareto/reference solutions + decision ranking
                         │
                         ▼
       Chọn phương án, hiệu chỉnh và đánh giá lại
```

`KHGD(1).DBF` và `calendar.csv` chưa có trong repository và sẽ được bổ sung sau. Pipeline hiện tại chưa đủ điều kiện chạy chính thức khi thiếu hai nguồn này.

## 5. Dữ liệu đầu vào

Đặc tả chi tiết về ý nghĩa, schema, quy tắc nối, làm sạch và kiểm tra chất lượng dữ liệu nằm tại [`data/README.md`](data/README.md).

Các nguồn chính:

- `KHGD(1).DBF`: tập môn của kế hoạch học kỳ và trạng thái bắt buộc/tự chọn;
- `data/kq_nv.csv`: đăng ký của từng sinh viên;
- `data/mh.csv`, `data/chmh.csv`: danh mục môn và cấu hình số tiết;
- `data/ref_map252.csv`, `data/ref_map261.csv`: quan hệ môn/nhóm với tính chất phòng;
- `data/room261.csv`: danh mục phòng cụ thể;
- `calendar.csv`: ngày và tuần được phép giảng dạy.

## 6. Xác định môn và số lớp được mở

### 6.1. Tập môn hợp lệ của học kỳ

`KHGD(1).DBF` là nguồn xác định môn thuộc phạm vi học kỳ. `kq_nv.csv` chỉ cung cấp nhu cầu sinh viên, không thay thế KHGD.

Một đăng ký được đưa vào tối ưu khi:

- nối được mã môn với KHGD;
- loại chương trình của sinh viên tương thích;
- môn thuộc học kỳ hoặc có ngoại lệ được Phòng Đào tạo phê duyệt.

Đăng ký không nối được phải được báo cáo, không âm thầm tạo lớp hoặc loại bỏ.

### 6.2. Môn bắt buộc và môn tự chọn

Với mỗi `(course_id, program_type)`:

- môn bắt buộc theo KHGD phải được mở dù số đăng ký thấp hơn ngưỡng;
- môn tự chọn chỉ được mở khi số sinh viên duy nhất đăng ký đạt ngưỡng;
- nếu tài nguyên không đủ cho mọi môn tự chọn đạt ngưỡng, ưu tiên theo tỷ lệ vượt ngưỡng, số đăng ký và mã môn;
- không được hủy môn bắt buộc để nhường tài nguyên cho môn tự chọn.

### 6.3. Chia lớp

```text
number_of_sections = ceil(registered_students / maximum_section_capacity)
```

- Chia riêng theo chương trình/loại hình đào tạo.
- Các lớp cùng môn được chia gần đều và không vượt sức chứa.
- Tạo lớp lý thuyết trước, sau đó tạo lab/thực hành và liên kết với lớp cha.
- Môn bắt buộc chưa có đăng ký vẫn tạo một lớp với sĩ số dự báo và cờ `forecast`.
- Lab không có lớp lý thuyết cha hợp lệ phải được báo lỗi dữ liệu.

## 7. Nhu cầu và khả năng học của sinh viên

### 7.1. Biểu diễn đăng ký

Với mỗi sinh viên `s`, xây dựng tập môn hợp lệ đã đăng ký `R_s`. Từ đó tạo ma trận:

```text
conflict[c1, c2] = số sinh viên cùng đăng ký c1 và c2
```

Ma trận này giúp NSGA-III tránh xếp trùng các cặp môn có nhiều sinh viên chung, nhưng không đủ để chứng minh sinh viên học được. Mỗi chromosome còn phải được kiểm tra bằng việc phân sinh viên vào các lớp cụ thể.

### 7.2. Biến phân sinh viên

```text
x[s,l] = 1 nếu sinh viên s được xếp vào lớp l
y[s,c] = 1 nếu sinh viên s học được môn c đã đăng ký
```

Ràng buộc:

- một sinh viên được xếp tối đa một lớp cho mỗi môn;
- lớp phải đúng chương trình hoặc thuộc nhóm được phép học chung;
- không chọn hai lớp có thời gian giao nhau;
- không vượt sĩ số lớp hoặc sức chứa phòng;
- lecture và lab phải là cặp tương thích nếu môn yêu cầu;
- sinh viên phải có đủ thời gian di chuyển giữa hai cơ sở.

### 7.3. Chỉ số ưu tiên sinh viên

```text
fulfilled_registrations = Σ_s Σ_c y[s,c]

unfulfilled_registration_rate =
    1 - fulfilled_registrations / total_eligible_registrations
```

Đồng thời đo:

- số và tỷ lệ sinh viên học được toàn bộ môn hợp lệ đã đăng ký;
- số môn không học được theo từng sinh viên;
- nguyên nhân: trùng lịch, hết chỗ, môn không mở, thiếu phòng hoặc sai chương trình;
- tỷ lệ đáp ứng thấp nhất giữa các nhóm sinh viên.

Để giảm chi phí tính toán, có thể dùng ma trận xung đột để chấm nhanh quần thể, sau đó chạy bộ phân sinh viên chính xác cho các cá thể triển vọng. Kết quả công bố bắt buộc phải qua bước phân sinh viên chính xác.

## 8. Ánh xạ môn, loại session và phòng

Phòng là ràng buộc phụ thuộc đồng thời vào môn và loại session:

```text
(course_id, session_type)
        │
        ▼
ref_map252.csv + ref_map261.csv
        │  F_MAMH → F_TCPHONG
        ▼
required_room_property
        │
        ▼
room261.csv
        │  Tính chất phòng = required_room_property
        ▼
allowed_room_ids
```

- `F_MANH` là mã nhóm, không phải mã phòng.
- `F_TCPHONG` là tính chất phòng mà môn/loại session yêu cầu.
- `allowed_room_ids` chỉ gồm phòng đúng tính chất, đúng cơ sở nếu có yêu cầu, đủ sức chứa và còn hoạt động.
- Không mặc định lecture, lab và practical của cùng một môn dùng chung tính chất phòng.
- Không cho phép session dùng phòng ngoài tập `allowed_room_ids`.
- Không tự chuyển lab hoặc môn chuyên dụng sang `GENERAL` để tạo nghiệm.

Nếu 60 nhóm chỉ được phép sử dụng hai phòng, toàn bộ 60 nhóm phải được phân bố vào các slot khác nhau của hai phòng đó. Nếu không đủ slot, hệ thống báo `ROOM_BOTTLENECK`, gồm môn, loại session, tính chất phòng, số nhóm, nhu cầu slot, năng lực hai phòng và số nhóm chưa xếp được.

Quy tắc hợp nhất 252/261:

- nếu hai kỳ thống nhất, dùng tính chất đó;
- nếu chỉ một kỳ có dữ liệu hợp lệ, dùng kỳ đó và lưu nguồn;
- nếu mâu thuẫn, ưu tiên 261 nhưng đặt `needs_review=true`;
- nếu môn có nhiều `F_TCPHONG`, giữ quan hệ theo loại session/nhóm lịch sử;
- nếu không có tính chất hoặc không có phòng tương ứng, session không khả thi và phải được báo cáo.

## 9. Khung thời gian và cơ sở

### 9.1. Lịch học kỳ

- Ngày học: thứ Hai đến thứ Bảy, `D = {2, 3, 4, 5, 6, 7}`.
- Tiết học: `S = {1, 2, ..., 12}`.
- Tuần học: lấy từ `calendar.csv`.
- Ngày lễ, tuần thi và ngày không giảng dạy phải lấy từ `calendar.csv`, không viết cứng.
- Session không được vượt tiết cuối ngày hoặc tuần cuối học kỳ.
- Lab/thực hành tạm thời chỉ bắt đầu ở tiết 2 hoặc tiết 8 cho tới khi có cấu hình chính thức.

### 9.2. Thứ Bảy

Giải theo hai pha:

1. Pha A chỉ cho phép thứ Hai–thứ Sáu.
2. Nếu không có nghiệm khả thi trong ngân sách tìm kiếm đã cấu hình, pha B mở thứ Bảy và tối thiểu hóa số session thứ Bảy.

Báo cáo phải nêu lý do mở pha B, lớp bị xếp thứ Bảy và tài nguyên gây nghẽn.

### 9.3. Di chuyển cơ sở

Tối thiểu hóa số lần sinh viên và giảng viên phải di chuyển giữa CS1 và CS2 trong cùng ngày.

Ghi nhận vi phạm cứng `CAMPUS_TRAVEL_TIME_VIOLATION` nếu cùng một sinh viên, nhóm sinh viên hoặc giảng viên có hai session trong cùng ngày tại hai cơ sở khác nhau và:

- hai session diễn ra liên tiếp; hoặc
- giữa hai session chỉ có một tiết trống.

Chỉ phương án có ít nhất hai tiết trống giữa hai session ở hai cơ sở mới hợp lệ. Mỗi lỗi phải chỉ rõ đối tượng, session, cơ sở, ngày và khoảng tiết.

## 10. Giảng viên tạm thời

Khi chưa có ma trận giảng viên–môn và lịch rảnh:

- ID tạm có dạng `TEMP_<faculty_id>_<sequence>`;
- mỗi lớp lý thuyết có một giảng viên tạm;
- lab có thể cùng hoặc khác giảng viên theo cấu hình;
- nếu chỉ có một giảng viên thật đủ điều kiện, gán cứng người đó;
- giảng viên thật hoặc tạm không được dạy trùng lịch;
- tải tạm mặc định tối đa 3 session/tuần;
- gán giảng viên không được làm giảm ưu tiên sinh viên.

## 11. Ràng buộc cứng

Đầu ra chính thức phải có tổng vi phạm cứng bằng 0:

1. Tất cả môn bắt buộc trong KHGD được mở và có lịch.
2. Mọi session nằm trong ngày, tiết và tuần hợp lệ của `calendar.csv`.
3. Một phòng không phục vụ hai session giao nhau.
4. Phòng thuộc `allowed_room_ids`, đúng tính chất và đủ sức chứa.
5. Một lớp/nhóm sinh viên không có hai session giao nhau.
6. Sinh viên không được phân vào hai lớp giao nhau.
7. Một sinh viên có tối đa một lớp cho mỗi môn.
8. Sĩ số lớp không vượt sức chứa.
9. Lecture và lab không trùng nhau; lab bắt đầu sau lecture ít nhất `k` tuần.
10. Session không lặp quá số buổi/tuần quy định.
11. Giảng viên không dạy hai session giao nhau.
12. Không vi phạm thời gian di chuyển CS1–CS2.
13. Thứ Bảy chỉ được dùng theo chiến lược hai pha.

Các constraint phải trả về bản ghi vi phạm có cấu trúc, không chỉ trả về một tổng penalty.

## 12. Mô hình tối ưu NSGA-III

### 12.1. Vì sao dùng NSGA-III

Bài toán có nhiều mục tiêu độc lập về sinh viên, thứ Bảy, cơ sở, phòng và giảng viên. NSGA-III duy trì nghiệm đa dạng theo các reference direction tốt hơn cơ chế crowding distance của NSGA-II trong bài toán many-objective.

Không biến mỗi constraint thành một objective. Constraint quyết định tính khả thi; objective dùng để đánh đổi giữa các nghiệm khả thi; diagnostic giải thích nơi cần sửa.

### 12.2. Biểu diễn chromosome

Mỗi gene biểu diễn lịch của một session:

```python
Gene(
    session_id,
    room_id,
    day,
    start_slot,
    start_week,
    week_pattern,
)
```

Chromosome chứa toàn bộ gene và kết quả đánh giá:

```python
ChromosomeEvaluation(
    raw_objectives,
    normalized_objectives,
    total_constraint_violation,
    violations,
    student_assignment,
    student_impact,
    reference_direction,
    distance_to_reference,
)
```

Phân sinh viên có thể là biến nội bộ của evaluator thay vì gene tiến hóa, nhưng phải được giải lại cho mỗi lịch cần đánh giá chính xác.

### 12.3. Vector mục tiêu

Tất cả objective được chuyển về dạng tối thiểu hóa:

| Mã | Objective | Ý nghĩa |
|---|---|---|
| `F1` | `unfulfilled_registration_rate` | Tỷ lệ lượt đăng ký hợp lệ không được đáp ứng; ưu tiên cao nhất. |
| `F2` | `incomplete_student_rate` | Tỷ lệ sinh viên không học được toàn bộ môn hợp lệ đã đăng ký. |
| `F3` | `student_schedule_penalty` | Lịch quá dày, thời gian chờ dài và bất tiện của sinh viên. |
| `F4` | `saturday_session_rate` | Tỷ lệ session phải xếp thứ Bảy. |
| `F5` | `campus_movement_penalty` | Số lần di chuyển cơ sở không cần thiết. |
| `F6` | `room_capacity_waste_rate` | Chênh lệch sĩ số và sức chứa phòng. |
| `F7` | `room_load_imbalance` | Mất cân bằng sử dụng phòng/ngày/buổi. |
| `F8` | `lecturer_schedule_penalty` | Mất cân bằng tải và lịch giảng viên bị phân mảnh. |

Khi dữ liệu giảng viên chưa đáng tin cậy, `F8` có thể tắt bằng cấu hình; không đưa một mục tiêu giả vào đánh giá chính thức.

### 12.4. Ưu tiên sinh viên trong NSGA-III

NSGA-III mặc định coi các objective ngang hàng, nên áp dụng ưu tiên theo tầng:

1. constraint-domination;
2. ưu tiên `F1` và `F2` trong một khoảng dung sai quanh giá trị tốt nhất;
3. dùng NSGA-III và reference directions để cân bằng `F3`–`F8` trong tập còn lại.

Có thể lọc:

```text
F1 ≤ best_F1 + epsilon_1
F2 ≤ best_F2 + epsilon_2
```

Các epsilon phải là cấu hình nghiệp vụ và xuất hiện trong metadata kết quả.

### 12.5. Constraint handling

Áp dụng constraint-domination:

```text
khả thi > không khả thi

nếu cùng không khả thi:
    so sánh vector vi phạm theo thứ tự ưu tiên

nếu cùng khả thi:
    dùng NSGA-III environmental selection
```

Khóa vi phạm đề xuất:

```python
constraint_key = (
    mandatory_courses_unscheduled,
    invalid_calendar_sessions,
    room_conflicts,
    invalid_room_assignments,
    capacity_violations,
    student_assignment_conflicts,
    campus_travel_violations,
    lecturer_conflicts,
    other_hard_violations,
)
```

### 12.6. Chuẩn hóa và reference directions

NSGA-III sử dụng objective chuẩn hóa để liên kết nghiệm với reference directions:

```text
normalized_Fi = (Fi - ideal_i) / (nadir_i - ideal_i + epsilon)
```

Lưu đồng thời giá trị gốc để giải thích và giá trị chuẩn hóa để chọn cá thể. Với 8 mục tiêu và 3 phân hoạch có 120 reference directions; population ban đầu có thể dùng 120 hoặc 128 và phải được hiệu chỉnh theo chi phí đánh giá thực tế.

### 12.7. Quy trình tiến hóa

1. Khởi tạo gene trong miền phòng và thời gian hợp lệ.
2. Repair theo thứ tự: biên thời gian, phòng, xung đột, lecture–lab, cơ sở.
3. Đánh giá constraint và ghi violation chi tiết.
4. Phân sinh viên và tính `F1`–`F3`.
5. Tính các objective vận hành còn lại.
6. Chuẩn hóa objective và liên kết reference directions.
7. Selection, crossover, mutation và environmental selection theo NSGA-III.
8. Dừng theo số thế hệ, thời gian hoặc không cải thiện.
9. Chỉ xuất nghiệm khả thi; nếu không có, xuất nghiệm gần khả thi kèm nhãn rõ ràng và chẩn đoán.

## 13. Xếp hạng và giải thích chromosome

### 13.1. Ba lớp xếp hạng

- `feasibility_tier`: `FEASIBLE`, `REPAIRABLE`, `INFEASIBLE`.
- thông tin NSGA-III: front, reference direction, khoảng cách và niche count.
- `decision_rank`: thứ hạng tuyến tính phục vụ Phòng Đào tạo.

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

Ngoài thứ hạng tổng thể, gắn nhãn các phương án tiêu biểu:

- `BEST_FOR_STUDENTS`;
- `LEAST_SATURDAY`;
- `LEAST_CAMPUS_MOVEMENT`;
- `BEST_ROOM_UTILIZATION`;
- `BEST_COMPROMISE`.

### 13.2. Violation report

Mỗi violation tối thiểu gồm:

```python
Violation(
    violation_id,
    constraint_code,
    priority,
    severity,
    message,
    location,
    affected_entities,
    current_value,
    required_value,
    suggested_actions,
)
```

Phân cấp:

| Cấp | Ví dụ |
|---|---|
| `HARD` | Môn bắt buộc chưa xếp, trùng phòng, sai phòng, quá sức chứa. |
| `P1_STUDENT` | Đăng ký không được đáp ứng, lịch sinh viên bất tiện. |
| `P2_OPENING` | Môn tự chọn đủ ngưỡng chưa mở. |
| `P3_SATURDAY` | Session phải học thứ Bảy. |
| `P4_CAMPUS_ROOM` | Đổi cơ sở, lãng phí hoặc mất cân bằng phòng. |
| `P5_LECTURER` | Tải hoặc lịch giảng viên chưa tốt. |

Mỗi lỗi phải trả lời được: vi phạm gì, ở đâu, ảnh hưởng ai, mức độ bao nhiêu và có thể sửa theo hướng nào.

### 13.3. Hiệu chỉnh thủ công

Người dùng có thể khóa hoặc thay đổi phòng, ngày, tiết, tuần, lớp hoặc giảng viên. Mỗi thao tác được lưu dưới dạng operation có giá trị trước/sau, lý do và người thực hiện.

Sau mỗi chỉnh sửa:

1. kiểm tra lại constraint cục bộ;
2. chạy lại phân sinh viên;
3. tính lại toàn bộ objective;
4. cập nhật violation report và decision rank;
5. hiển thị so sánh tác động trước/sau.

Không coi phương án chỉnh tay là hợp lệ cho đến khi đánh giá lại hoàn tất.

## 14. Đầu ra

Mỗi lần chạy tạo:

```text
output/<run_id>/
├── run_metadata.json
├── chromosome_ranking.csv
├── chromosome_<id>_schedule.csv
├── chromosome_<id>_student_assignment.csv
├── chromosome_<id>_student_impact.csv
├── chromosome_<id>_summary.json
├── chromosome_<id>_violations.csv
└── manual_changes.json
```

Mỗi session trong schedule gồm tối thiểu:

- `section_id`, `course_id`, `session_type`, `program_type`;
- `room_id`, `campus`, `day`, `start_slot`, `duration`;
- `start_week`, `week_pattern`, `total_weeks`;
- `capacity`, `parent_section_id`, `lecturer_id`;
- `opening_reason`, `mapping_source`, `needs_review`.

`chromosome_ranking.csv` phải cho phép so sánh nhanh trạng thái khả thi, F1–F8, số sinh viên học đủ môn, số lỗi theo cấp, reference direction và decision rank.

## 15. Cập nhật sau công bố

Đầu vào là baseline đã chọn cùng các sự kiện mới. Phương án cập nhật phải giữ các constraint và ưu tiên sinh viên như bài toán chính, đồng thời:

```text
stability = unchanged_sessions / baseline_sessions
```

Mục tiêu giữ tối thiểu 80% baseline và thay đổi không quá 20%. Một session không đổi khi giữ nguyên phòng, ngày, tiết và mẫu tuần; thay đổi giảng viên được theo dõi riêng.

Đầu ra bổ sung danh sách sinh viên chuyển lớp, lớp mở/ghép/hủy, session đổi lịch và giảng viên thay đổi.

## 16. Quy ước tạm thời

| Tham số | Giá trị tạm |
|---|---:|
| `min_enrollment_lecture` | 15 |
| `min_enrollment_lab` | 10 |
| `forecast_mandatory_size` | 15 |
| `general_room_capacity` | 80 |
| `computer_lab_capacity` | 40 |
| `other_special_capacity` | 30 |
| `temp_lecturer_max_sessions` | 3 |
| `min_lab_offset` | 1 tuần |
| `campus_min_empty_slots` | 2 tiết trống |
| `baseline_stability_target` | 80% |

Môn bắt buộc không chịu ngưỡng đăng ký. Các tham số phải nằm trong tệp cấu hình học kỳ và được ghi vào `run_metadata.json`.

## 17. Tiêu chí nghiệm thu

- 100% môn bắt buộc được mở và xếp hợp lệ.
- Tổng vi phạm cứng bằng 0 đối với phương án chính thức.
- Không trùng phòng, lớp, sinh viên hoặc giảng viên.
- Mọi phòng đúng tính chất và đủ sức chứa.
- `fulfilled_registrations` được tối đa hóa và báo cáo theo tổng thể, sinh viên, môn và chương trình.
- Môn tự chọn mở đúng ngưỡng.
- Không có di chuyển cơ sở liên tiếp hoặc chỉ cách một tiết.
- Thứ Bảy chỉ được dùng sau khi pha thứ Hai–thứ Sáu không có nghiệm khả thi.
- Mỗi chromosome có objective vector, ranking và violation report truy vết được.
- Kết quả tái lập được từ seed, cấu hình và phiên bản dữ liệu.
- Phương án chỉnh tay được đánh giá lại và có báo cáo tác động trước/sau.

## 18. Trạng thái triển khai hiện tại

Repository đã có parser môn/phòng/lịch, builder lớp/session, biểu diễn gene/chromosome và một số constraint. Tuy nhiên:

- code hiện tại là khung NSGA-II, chưa phải NSGA-III;
- các operator và environmental selection chưa hoàn thiện;
- chưa có parser cho `KHGD(1).DBF` và chưa có `calendar.csv`;
- chưa nối KHGD với đăng ký từng sinh viên;
- chưa có bộ phân sinh viên bên trong evaluator;
- chưa sử dụng `ref_map252/261` theo pipeline tính chất phòng hoàn chỉnh;
- chưa có reference directions, normalization hay priority-tier selection;
- chưa có violation report, decision ranking và quy trình hiệu chỉnh thủ công;
- smoke test hiện chỉ chứng minh hàm đánh giá chạy, chưa tạo được thời khóa biểu khả thi.

Thứ tự triển khai đề xuất:

1. hoàn thiện đặc tả và parser dữ liệu;
2. thêm `KHGD(1).DBF` và `calendar.csv`;
3. xây course opening, student conflict và room dependency;
4. hoàn thiện constraint evaluator và violation report;
5. xây bộ phân sinh viên;
6. triển khai NSGA-III;
7. thêm decision ranking và hiệu chỉnh thủ công;
8. kiểm thử trên một khoa/học kỳ trước khi mở rộng.

## 19. Cấu trúc repository

```text
GA - URA/
├── builders/          # Tạo lớp học phần và session
├── data/              # Dữ liệu và đặc tả dữ liệu
├── models/            # Mô hình miền và chromosome
├── nsga2/             # Mã tối ưu hiện tại, cần chuyển sang NSGA-III
├── preprocessing/     # Parser, đăng ký và ánh xạ tài nguyên
├── requirements.txt
└── README.md
```

## 20. Các điểm cần xác nhận

1. Ngưỡng mở lớp chính thức theo môn, chương trình và loại session.
2. Trường/cờ trong `KHGD(1).DBF` xác định môn bắt buộc và tự chọn.
3. Quy tắc suy ra `session_type` tương ứng với từng `F_TCPHONG` khi một môn có nhiều tính chất phòng.
4. Danh mục chuẩn của `F_TCPHONG` và quan hệ với `Tính chất phòng` trong `room261.csv`.
5. Khung tiết, nghỉ trưa, tuần thi và ngày lễ trong `calendar.csv`.
6. Dữ liệu năng lực, lịch rảnh và tải chính thức của giảng viên.
7. Ngân sách tìm kiếm để kết luận pha thứ Hai–thứ Sáu không khả thi.
8. Ngưỡng `epsilon_1`, `epsilon_2` dùng để ưu tiên F1/F2 trước các objective còn lại.
