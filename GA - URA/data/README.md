# Đặc tả dữ liệu

Tài liệu này mô tả các nguồn dữ liệu dùng cho bài toán mở lớp, phân sinh viên và xếp thời khóa biểu. Mọi pipeline phải giữ dữ liệu nguồn bất biến, tạo dữ liệu chuẩn hóa riêng và xuất báo cáo chất lượng trước khi tối ưu.

## 1. Danh mục nguồn

| Nguồn | Trạng thái | Vai trò |
|---|---|---|
| `KHGD(1).DBF` | Chưa được bổ sung | Xác định môn thuộc kế hoạch học kỳ và trạng thái bắt buộc/tự chọn. |
| `calendar.csv` | Chưa được bổ sung | Xác định tuần/ngày giảng dạy, nghỉ lễ và thi. |
| `mh.csv` | Có | Danh mục môn và khối lượng học tập. |
| `chmh.csv` | Có | Mẫu/cấu hình phân bổ tiết theo loại hoạt động. |
| `kq_nv.csv` | Có | Kết quả đăng ký môn của từng sinh viên. |
| `room261.csv` | Có | Danh mục phòng cụ thể, cơ sở, sức chứa và tính chất. |
| `ref_map252.csv` | Có | Quan hệ lịch sử môn–nhóm–tính chất phòng kỳ 252. |
| `ref_map261.csv` | Có | Quan hệ lịch sử môn–nhóm–tính chất phòng và thông tin lịch kỳ 261. |
| `TAM252.xlsx` | Có | Nguồn Excel của `ref_map252.csv`. |
| `TAM261.xlsx` | Có | Nguồn Excel của `ref_map261.csv`. |
| `main.ipynb` | Có | Notebook chuyển hai file Excel sang CSV; không phải dữ liệu nghiệp vụ. |
| `old/` | Có | Mapping cũ, chỉ dùng tham khảo/đối chiếu. |

Số dòng/cột dưới đây phản ánh phiên bản dữ liệu được kiểm tra ngày 02/08/2026 và có thể thay đổi khi nguồn mới được upload.

## 2. Quy ước chung

- Mã môn, phòng, sinh viên, nhóm và chương trình phải được đọc dạng chuỗi.
- Chuẩn hóa khóa bằng `strip()` và `uppercase`, nhưng giữ lại giá trị gốc để truy vết.
- CSV sử dụng UTF-8 hoặc UTF-8-SIG; DBF phải được đọc bằng code page thực tế của nguồn.
- Không ghi đè file nguồn.
- Loại cột `Unnamed:*` do quá trình xuất DataFrame tạo ra.
- Giá trị trống, `.`, `------`, số âm bất thường và mã không nối được phải đi vào data-quality report.
- Mỗi bảng chuẩn hóa phải có `source_file`, `source_row`, `load_timestamp` và `normalization_version`.
- Mọi quyết định fallback phải có cột `mapping_source` và `needs_review`.

## 3. `KHGD(1).DBF` — Kế hoạch giảng dạy

### 3.1. Vai trò

Đây là nguồn dùng để xác định tập môn thuộc học kỳ. `kq_nv.csv` không được dùng thay thế KHGD.

Tối thiểu cần trích xuất:

| Trường chuẩn hóa | Ý nghĩa |
|---|---|
| `course_id` | Mã môn. |
| `program_type` | Chương trình/loại hình đào tạo. |
| `semester_id` | Mã học kỳ. |
| `faculty_id` | Khoa/đơn vị phụ trách. |
| `is_mandatory` | Môn bắt buộc hay tự chọn. |
| `planned_groups` | Số nhóm kế hoạch nếu nguồn có. |
| `planned_capacity` | Sĩ số kế hoạch nếu nguồn có. |
| `status` | Đang áp dụng, hủy hoặc thay thế. |

Tên cột thực tế sẽ được lập mapping sau khi file được bổ sung.

### 3.2. Kiểm tra bắt buộc

- xác định và ghi code page của DBF;
- không trùng khóa `(semester_id, course_id, program_type)` ngoài các phiên bản có trạng thái rõ ràng;
- `is_mandatory` không được trống đối với bản ghi dùng để mở môn;
- mã môn phải nối được với `mh.csv` hoặc có bảng ngoại lệ;
- chương trình phải nối được với chương trình trong `kq_nv.csv`;
- báo cáo môn KHGD không có đăng ký và đăng ký không có trong KHGD.

## 4. `calendar.csv` — Lịch học kỳ

### 4.1. Schema yêu cầu

File chưa được bổ sung. Schema tối thiểu đề xuất:

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `semester_id` | string | Học kỳ áp dụng. |
| `week` | integer | Tuần học kỳ. |
| `start_date` | date | Ngày đầu tuần. |
| `end_date` | date | Ngày cuối tuần. |
| `is_teaching` | boolean | Có được giảng dạy hay không. |
| `is_midterm` | boolean | Tuần thi giữa kỳ. |
| `is_final` | boolean | Tuần thi cuối kỳ. |
| `is_holiday` | boolean | Tuần/ngày nghỉ. |
| `holiday_dates` | list/string | Các ngày nghỉ cụ thể nếu tuần vẫn có ngày học. |

Nếu lịch có ngoại lệ theo ngày hoặc cơ sở, nên tách thêm `calendar_exceptions.csv` thay vì nhồi nhiều giá trị vào một ô.

### 4.2. Kiểm tra bắt buộc

- tuần là duy nhất trong một học kỳ;
- ngày bắt đầu/kết thúc không giao nhau;
- tuần thi/nghỉ phải có chính sách `is_teaching` rõ ràng;
- session chỉ được sinh trong các ngày/tuần hợp lệ;
- không dùng hằng số tuần giữa kỳ hoặc số tuần tối đa trong code.

## 5. `kq_nv.csv` — Đăng ký môn của sinh viên

### 5.1. Quy mô hiện tại

- 111.531 dòng;
- 15 cột;
- một dòng biểu diễn một đăng ký/sự xuất hiện của sinh viên đối với môn và chương trình.

### 5.2. Các cột quan trọng

| Cột nguồn | Trường chuẩn hóa | Vai trò |
|---|---|---|
| `F_MASV` | `student_id` | Mã sinh viên. |
| `F_MAMH` | `course_id` | Mã môn đăng ký. |
| `HTDT` | `program_type` | Loại hình/chương trình đào tạo. |
| `F_TENLOP` | `cohort_class` | Lớp sinh hoạt/nhóm sinh viên. |
| `KHOA` | `cohort_year` | Khóa học nếu giá trị hợp lệ. |
| `F_MAKH` | `faculty_plan_code` | Mã kế hoạch/khoa trong nguồn. |
| `KHGD` | `khgd_flag_raw` | Giá trị KHGD thô; không thay thế `KHGD(1).DBF`. |
| `LHMH` | `course_activity_raw` | Loại hoạt động/môn trong nguồn. |
| `MADCMH` | `curriculum_course_id_raw` | Mã chi tiết chương trình/môn. |
| `F_HIENDIEN` | `presence_status_raw` | Trạng thái hiện diện thô nếu có. |

Các cột còn lại phải được lưu trong staging cho tới khi xác nhận ý nghĩa.

### 5.3. Khóa và khử trùng lặp

#### Chức năng của khóa đăng ký

Khóa đăng ký dùng để xác định **một lượt đăng ký môn duy nhất của một sinh viên trong một học kỳ**. Khóa chuẩn hóa:

```text
(student_id, course_id, program_type, semester_id)
```

Ý nghĩa từng thành phần:

| Thành phần | Chức năng |
|---|---|
| `student_id` | Xác định sinh viên thực hiện đăng ký. |
| `course_id` | Xác định đúng mã môn được đăng ký. |
| `program_type` | Phân biệt cùng một môn nhưng thuộc các chương trình/loại hình đào tạo khác nhau. |
| `semester_id` | Phân biệt đăng ký của cùng sinh viên, cùng môn qua các học kỳ khác nhau. |

Ví dụ:

```text
(SV001, CO2013, CQ, 261)
```

là một đăng ký của sinh viên `SV001` đối với môn `CO2013`, chương trình `CQ`, trong học kỳ `261`.

Khóa này được dùng để:

- đếm chính xác số sinh viên duy nhất đăng ký từng môn;
- quyết định môn tự chọn có đạt ngưỡng mở lớp hay không;
- tính số lớp cần mở và sĩ số dự kiến;
- tạo tập môn đăng ký của từng sinh viên;
- xây ma trận xung đột giữa các môn;
- tính tổng lượt đăng ký hợp lệ và tỷ lệ được đáp ứng;
- tránh một dòng dữ liệu lặp làm tăng giả nhu cầu mở lớp hoặc làm sai objective của NSGA-III.

#### Lecture và lab có mã môn khác nhau

Trong dữ liệu của bài toán, lecture và lab của cùng một môn học phần có **hai mã môn khác nhau**. Vì `course_id` là một thành phần của khóa nên hai đăng ký này được giữ thành hai bản ghi độc lập, không bị xem là trùng lặp.

Ví dụ giả định:

```text
(SV001, CO2013, CQ, 261)      # lecture
(SV001, CO2013L, CQ, 261)     # lab
```

Hai khóa khác nhau ở `course_id`, do đó cả hai đều được giữ lại và đều tạo nhu cầu mở lớp. Không cần thêm `session_type` vào khóa đăng ký chỉ để phân biệt lecture và lab.

Quan hệ lecture–lab là một quan hệ nghiệp vụ riêng, được xác định bằng dữ liệu môn kèm như `mh.csv.MAKEM` hoặc bảng mapping đã được xác nhận:

```text
lecture_course_id ↔ lab_course_id
```

Quan hệ này được dùng để:

- tạo lớp lecture và lab tương ứng;
- liên kết lớp lab với lớp lecture cha;
- buộc sinh viên được phân vào một cặp lecture–lab tương thích;
- kiểm tra lecture và lab không trùng lịch và đúng thứ tự tuần.

Không sử dụng khóa đăng ký để suy đoán hai mã môn có phải là cặp lecture–lab hay không.

#### Khi nào hai dòng được xem là trùng

Sau khi chuẩn hóa mã, hai hoặc nhiều dòng có cùng toàn bộ khóa:

```text
(student_id, course_id, program_type, semester_id)
```

được xem là các bản ghi trùng tiềm năng của cùng một lượt đăng ký. Ví dụ:

| Dòng nguồn | Sinh viên | Môn | Chương trình | Học kỳ |
|---:|---|---|---|---|
| 105 | SV001 | CO2013 | CQ | 261 |
| 108 | SV001 | CO2013 | CQ | 261 |

Khi tính nhu cầu, hai dòng này chỉ đóng góp **một sinh viên đăng ký**. Nếu đếm cả hai, hệ thống có thể mở thừa lớp, xác định sai ngưỡng môn tự chọn và tính sai số lượt đăng ký được đáp ứng.

#### Quy tắc xử lý trùng lặp

Nếu có nhiều dòng cùng khóa:

- không đếm nhiều lần khi tính nhu cầu;
- không xóa âm thầm khỏi staging;
- giữ danh sách `source_row`, số bản ghi và mọi trạng thái khác nhau trong audit;
- nếu có trạng thái đăng ký/hủy hoặc thời điểm cập nhật, chọn bản ghi hiệu lực theo quy tắc nghiệp vụ đã được xác nhận;
- nếu chưa đủ dữ liệu xác định bản ghi hiệu lực, đặt `needs_review=true` thay vì tự chọn tùy ý;
- xuất các khóa trùng vào `duplicate_registrations.csv` hoặc phần tương ứng của data-quality report.

Ví dụ bản ghi audit:

```json
{
  "registration_key": ["SV001", "CO2013", "CQ", "261"],
  "source_rows": [105, 108],
  "source_record_count": 2,
  "counted_registration": 1,
  "resolution": "DEDUPLICATED_IDENTICAL_ROWS",
  "needs_review": false
}
```

#### Phân biệt khóa đăng ký và các khóa khác

Khóa đăng ký không thay thế:

- khóa lớp học phần `section_id`;
- khóa session `session_id`;
- quan hệ lecture–lab qua `MAKEM`;
- khóa phân sinh viên vào lớp `(student_id, section_id)`;
- khóa kết quả học được môn `(student_id, course_id, semester_id)`.

Nói ngắn gọn: khóa ở mục này chỉ trả lời câu hỏi **“sinh viên này có một đăng ký hợp lệ cho mã môn này, trong chương trình và học kỳ này hay không?”**

### 5.4. Sản phẩm dẫn xuất

```text
student_registrations:
    student_id → tập course_id hợp lệ

enrollment_counts:
    (course_id, program_type) → số student_id duy nhất

course_conflict_matrix:
    (course_id_1, course_id_2) → số sinh viên đăng ký cả hai
```

Tập đăng ký hợp lệ phải là kết quả nối với `KHGD(1).DBF`. Cần xuất riêng:

- đăng ký hợp lệ;
- đăng ký không có trong KHGD;
- mã môn không nối được;
- chương trình không tương thích;
- đăng ký trùng lặp.

## 6. `mh.csv` — Danh mục môn

### 6.1. Quy mô hiện tại

- 13.426 dòng;
- 19 cột.

### 6.2. Schema chính

| Cột | Ý nghĩa |
|---|---|
| `MAMH` | Mã môn. |
| `TENMH`, `TENMH_ENG` | Tên tiếng Việt/Anh. |
| `MAKEM` | Mã môn đi kèm, dùng nối lecture–lab nếu phù hợp. |
| `MASUBJECTAREA` | Lĩnh vực/khoa phụ trách. |
| `SOTC`, `SOTC_HP` | Số tín chỉ. |
| `SOTIET`, `SOTIET_XEPTKB` | Tổng số tiết và số tiết cần xếp TKB. |
| `loai_mh` | Loại môn nguồn. |
| `f_lt` | Tiết lý thuyết. |
| `f_bt` | Tiết bài tập. |
| `f_tn` | Tiết thí nghiệm. |
| `f_btl` | Khối lượng bài tập lớn. |
| `f_da` | Khối lượng đồ án. |
| `f_la` | Khối lượng luận án/hoạt động tương ứng trong nguồn. |
| `f_tq` | Khối lượng khác/tham quan theo nguồn. |
| `f_makh`, `mau` | Mã phân loại/mẫu thô. |

### 6.3. Chuẩn hóa loại session

Mapping hiện hành:

```text
LEC, LECTURE, LT       → LECTURE
LAB, TN, TH, TNG       → LAB
PRSN, PRACTICAL        → PRACTICAL
```

Giá trị không nhận diện phải được báo cáo. Không mặc định `UNKNOWN` thành lecture trong dữ liệu chính thức.

### 6.4. Kiểm tra

- `MAMH` duy nhất sau chuẩn hóa;
- `SOTIET_XEPTKB > 0` đối với môn cần xếp;
- số tiết là số nguyên không âm;
- `MAKEM` nếu có phải nối được hoặc được đánh dấu ngoại lệ;
- tổng thành phần giờ phải được đối chiếu với tổng giờ theo quy tắc nghiệp vụ.

## 7. `chmh.csv` — Cấu hình/mẫu môn

### 7.1. Quy mô hiện tại

- 81 dòng;
- 28 cột.

### 7.2. Nhóm cột

- định danh: `ID`, `STT`, `DANGMON`, `MAU`, `MAU_OLD`;
- mô tả: `CHUTHICH`;
- số tiết: `PBSOTIET_*`;
- số tín chỉ/thành phần: `PBSOTC_*`.

`CHUTHICH` có thể mô tả mẫu như số tiết/tuần nhân số tuần. Parser phải ưu tiên các cột có cấu trúc; chỉ parse văn bản khi cần và phải lưu độ tin cậy.

### 7.3. Kiểm tra

- mã `MAU` không trùng hoặc có phiên bản rõ ràng;
- tổng các thành phần phù hợp `PBSOTIET_TONG`/`PBSOTC_TONG` theo sai số cho phép;
- mapping từ `mh.csv.mau` sang `chmh.csv.MAU` phải được báo cáo tỷ lệ phủ;
- không dùng dòng `TEST` làm cấu hình chính thức.

## 8. `room261.csv` — Danh mục phòng

### 8.1. Quy mô hiện tại

- 751 dòng thô;
- 8 cột.

### 8.2. Schema

| Cột | Trường chuẩn hóa | Vai trò |
|---|---|---|
| `Mã Phòng` | `room_id` | Mã phòng cụ thể. |
| `Cơ sở` | `campus` | CS1/CS2. |
| `Sức chứa` | `capacity` | Sức chứa tối đa. |
| `Tính chất phòng` | `room_property` | Mã tính chất dùng nối `F_TCPHONG`. |
| `Dãy` | `building` | Dãy/tòa nhà. |
| `Tên phòng` | `room_name` | Tên mô tả. |
| `Tên PH cũ` | `old_room_name` | Tên/mã cũ để đối chiếu. |
| `Chú thích` | `note` | Thông tin bổ sung. |

### 8.3. Lọc bản ghi

Loại khỏi tập phòng khả dụng nếu:

- `Mã Phòng` trống hoặc bằng `------`;
- sức chứa trống, không phải số hoặc không dương;
- không nhận diện được cơ sở;
- phòng ngừng hoạt động theo nguồn bổ sung.

Mã phòng trùng phải được đối chiếu; không âm thầm giữ dòng đầu nếu sức chứa/tính chất khác nhau.

### 8.4. Chỉ mục cần tạo

```text
rooms_by_id:
    room_id → Room

rooms_by_property:
    room_property → tập room_id

rooms_by_property_campus:
    (room_property, campus) → tập room_id
```

## 9. `ref_map252.csv` và `ref_map261.csv`

### 9.1. Vai trò

Hai file được dùng để ánh xạ môn/loại session sang tính chất phòng, không phải ánh xạ trực tiếp sang mã phòng:

```text
(course_id, session_type) → F_TCPHONG → room261.Tính chất phòng → room_id
```

`F_MANH` là mã nhóm, không phải mã phòng.

### 9.2. Quy mô

`ref_map252.csv`:

- 6.420 dòng;
- 5 cột sau khi xuất CSV, gồm một cột chỉ mục `Unnamed: 0` cần loại;
- 1.835 mã môn khác nhau trong phiên bản đã kiểm tra.

Các cột nghiệp vụ:

| Cột | Ý nghĩa |
|---|---|
| `F_MAMH` | Mã môn. |
| `F_MANH` | Mã nhóm. |
| `F_SISO` | Sĩ số lịch sử. |
| `F_TCPHONG` | Tính chất phòng. |

`ref_map261.csv`:

- 6.336 dòng;
- 319 cột sau khi xuất CSV;
- 2.265 mã môn khác nhau trong phiên bản đã kiểm tra;
- có nhiều cột `Unnamed:*` và cột rỗng cần loại trong bảng mapping.

Các cột mapping cốt lõi:

| Cột | Ý nghĩa |
|---|---|
| `F_MAMH` | Mã môn. |
| `F_MANH` | Mã nhóm. |
| `F_SISO` | Sĩ số. |
| `F_DAXEP` | Trạng thái/số liệu đã xếp cần xác nhận ý nghĩa. |
| `F_TCPHONG` | Tính chất phòng. |

Các cột tuần/tiết khác của 261 chỉ được dùng sau khi xác nhận ý nghĩa; không kéo toàn bộ 319 cột vào bảng mapping phòng.

### 9.3. Làm sạch `F_TCPHONG`

- trim và uppercase;
- loại trống và `.`;
- đối chiếu với tập `room261.Tính chất phòng`;
- mã không tồn tại trong danh mục phòng phải được báo cáo;
- giữ số lần xuất hiện theo môn, nhóm và học kỳ;
- không gộp nhiều tính chất của một môn nếu chưa xác định loại session tương ứng.

### 9.4. Hợp nhất hai học kỳ

Với `(course_id, session_type)`:

1. ưu tiên mapping gán cứng đã được xác nhận;
2. nếu 252 và 261 thống nhất, dùng giá trị đó;
3. nếu chỉ một kỳ có dữ liệu hợp lệ, dùng kỳ đó;
4. nếu mâu thuẫn, ưu tiên 261 và đặt `needs_review=true`;
5. nếu có nhiều giá trị, giữ phân phối lịch sử và yêu cầu quy tắc xác định session type;
6. không có mapping thì session không khả thi, trừ lecture được phép fallback `GENERAL` theo phê duyệt.

### 9.5. Sản phẩm chuẩn hóa

```text
course_session_room_property.csv
```

Schema đề xuất:

| Cột | Ý nghĩa |
|---|---|
| `course_id` | Mã môn. |
| `session_type` | LECTURE/LAB/PRACTICAL. |
| `room_property` | Tính chất phòng yêu cầu. |
| `source_semester` | 252, 261, BOTH hoặc MANUAL. |
| `evidence_count` | Số dòng lịch sử hỗ trợ. |
| `confidence` | Độ tin cậy mapping. |
| `needs_review` | Cờ cần duyệt. |

Sau đó nối với `room261.csv` để tạo:

```text
session_allowed_rooms.csv
```

## 10. `TAM252.xlsx`, `TAM261.xlsx` và `main.ipynb`

- Hai file Excel là nguồn gốc của `ref_map252.csv` và `ref_map261.csv`.
- Notebook hiện chỉ đọc sheet và gọi `to_csv`.
- Khi tái tạo CSV phải dùng `index=False` để tránh `Unnamed: 0`.
- Cần ghi checksum, sheet, số dòng/cột và thời gian chuyển đổi.
- CSV dẫn xuất không được coi là nguồn độc lập nếu khác checksum/nội dung Excel.

## 11. Mapping trong `preprocessing/mappings/`

### `course_resource_mapping.csv`

Phân loại loại tài nguyên tổng quát theo môn, ví dụ `GENERAL`, `COMPUTER_LAB`, `CHEMISTRY_LAB`. Đây là nguồn fallback/tham khảo, không được ghi đè mapping chính thức từ `F_TCPHONG`.

### `room_resource_mapping.csv`

Phân loại tài nguyên tổng quát theo phòng. Dùng để kiểm tra chéo hoặc fallback được phê duyệt.

Các mapping trong `old/` không được dùng mặc định.

## 12. Pipeline dữ liệu chuẩn hóa

```text
raw sources
    │
    ▼
staging tables giữ nguyên giá trị nguồn
    │
    ▼
normalize identifiers + types + encoding
    │
    ├── KHGD normalized
    ├── registrations normalized
    ├── courses normalized
    ├── rooms normalized
    └── historical room properties normalized
    │
    ▼
validate joins and produce quality reports
    │
    ├── eligible registrations
    ├── course opening demand
    ├── student conflict matrix
    ├── course/session → room property
    └── session → allowed room ids
    │
    ▼
optimizer input snapshot
```

Optimizer không được đọc trực tiếp nhiều file thô và tự áp dụng fallback khác nhau ở các module.

## 13. Data-quality report bắt buộc

Mỗi lần chuẩn bị dữ liệu phải xuất:

```text
data/processed/<snapshot_id>/
├── snapshot_metadata.json
├── courses.csv
├── khgd.csv
├── calendar.csv
├── registrations.csv
├── eligible_registrations.csv
├── rejected_registrations.csv
├── rooms.csv
├── course_session_room_property.csv
├── session_allowed_rooms.csv
├── student_conflict_matrix.csv
└── data_quality_report.json
```

`data_quality_report.json` tối thiểu gồm:

- số dòng đọc, giữ, loại theo từng nguồn;
- mã môn/phòng/sinh viên trống hoặc trùng;
- đăng ký không nối được với KHGD;
- môn KHGD không nối được với danh mục môn;
- `F_TCPHONG` không nối được với tính chất phòng;
- môn/session không có phòng hợp lệ;
- phòng trùng mã nhưng khác thuộc tính;
- mapping dùng fallback và mapping cần duyệt;
- checksum và phiên bản mọi file nguồn.

## 14. Điều kiện chặn trước tối ưu

Không chạy tối ưu chính thức nếu:

- thiếu `KHGD(1).DBF` hoặc `calendar.csv`;
- không xác định được học kỳ;
- môn bắt buộc thiếu thông tin session hoặc không có chính sách xử lý;
- tỷ lệ đăng ký không nối được vượt ngưỡng cấu hình;
- có mã tính chất phòng quan trọng không nối được;
- session bắt buộc không có phòng hợp lệ;
- khóa định danh không ổn định hoặc dữ liệu nguồn bị thay đổi sau khi tạo snapshot.

Có thể cho phép chạy thử nghiệm với cờ `allow_incomplete_data=true`, nhưng kết quả phải gắn nhãn `EXPERIMENTAL_NOT_FOR_PUBLICATION`.

## 15. Các điểm cần xác nhận khi nhận file mới

1. Code page và schema thực tế của `KHGD(1).DBF`.
2. Cột phân biệt môn bắt buộc/tự chọn và chương trình áp dụng.
3. Schema chính thức của `calendar.csv`, đặc biệt ngoại lệ theo ngày.
4. Quan hệ giữa `LHMH`, `loai_mh`, `MAKEM` và loại session.
5. Danh mục chuẩn của `F_TCPHONG`.
6. Quy tắc xác định loại session khi một môn có nhiều `F_TCPHONG`.
7. Ý nghĩa và giá trị âm trong `F_SISO` của dữ liệu 252.
8. Ý nghĩa các cột lịch cần sử dụng trong `ref_map261.csv`.
