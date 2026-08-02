# Dữ liệu đăng ký sinh viên

## Nguồn: `kq_nv.csv`

File cho biết sinh viên nào đăng ký những môn nào.

Các cột cần dùng:

- `F_MASV`: mã sinh viên;
- `F_MAMH`: mã môn đăng ký;
- `HTDT`: loại chương trình đào tạo;
- học kỳ: lấy từ cấu hình hoặc nguồn học kỳ tương ứng.

## Đầu ra sau khi clean

Chỉ cần tạo một file:

```text
data/processed/registrations.csv
```

Schema:

```csv
student_id,course_id,program_type,semester_id
```

Ví dụ:

```csv
SV001,CO2013,CQ,261
SV001,CO2013L,CQ,261
SV002,CO2003,CQ,261
```

## Khóa đăng ký

Mỗi đăng ký được xác định bằng khóa:

```text
(student_id, course_id, program_type, semester_id)
```

Nếu nhiều dòng có cùng khóa, chỉ tính là một đăng ký. Trước khi tạo khóa cần loại khoảng trắng và chuẩn hóa mã thành chữ hoa.

Lecture và lab có mã môn khác nhau nên tạo hai khóa khác nhau và đều được giữ lại. Quan hệ lecture–lab được xử lý riêng qua `MAKEM` hoặc mapping môn kèm.

Không cần tạo trước enrollment count hoặc conflict matrix thành các file riêng. Khi cần, chương trình sẽ tính trực tiếp từ `registrations.csv`.

## Mapping môn và phòng

Sử dụng hai file:

```text
ref_map252.csv
ref_map261.csv
```

Trong đó:

- `F_MAMH`: mã môn;
- `F_MANH`: mã nhóm lớp, không phải mã phòng;
- `F_TCPHONG`: tính chất phòng môn/nhóm đã sử dụng.

Nối `F_TCPHONG` với cột `Tính chất phòng` trong `room261.csv` để lấy các `Mã Phòng` cụ thể.

`session_type` không được suy ra chỉ từ `F_TCPHONG`; cần lấy từ thông tin loại môn trong `mh.csv`, quan hệ `MAKEM` hoặc mapping đã được xác nhận.

### Bạn 1 — Map môn sang phòng

Tạo file:

```text
data/processed/course_rooms.csv
```

Schema:

```csv
course_id,session_type,room_property,room_id
```

File trả lời câu hỏi: **một môn và loại session được phép học ở những phòng nào?**

### Bạn 2 — Map phòng sang môn

Tạo file:

```text
data/processed/room_courses.csv
```

Schema:

```csv
room_id,room_property,course_id,session_type
```

File trả lời câu hỏi: **một phòng có thể dùng để xếp những môn và loại session nào?**

### Quy tắc chung

- Chuẩn hóa mã bằng cách loại khoảng trắng và chuyển thành chữ hoa.
- Loại `Unnamed:*`, giá trị trống và `.`.
- Nếu 252 và 261 giống nhau thì giữ một mapping.
- Nếu chỉ một kỳ có mapping thì dùng mapping của kỳ đó.
- Nếu hai kỳ khác nhau thì ưu tiên 261 và đánh dấu để kiểm tra.
- Không tự gán phòng khác tính chất khi không tìm được phòng phù hợp.
- Hai file đầu ra phải thể hiện cùng một quan hệ theo hai chiều và có thể kiểm tra chéo với nhau.
