# `calendar.csv` — Chú thích dữ liệu

Nguồn: *Biểu đồ kế hoạch học tập năm học 2025-2026*, Trường ĐH Bách Khoa – ĐHQG TP.HCM. (https://hcmut.edu.vn/bai-viet/bieu-do-nam-hoc-2025-2026)

## 1. Cấu trúc cột

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `track` | string | Khối lịch (xem mục 2). |
| `semester_id` | string | `HK1`, `HK2`, hoặc `HE` (xem mục 3). |
| `week` | integer | Tuần đánh số theo tuần đầu được học  (xem mục 4). |
| `start_date` | date (Thứ Hai đầu tuần.) |
| `end_date` | date (Chủ Nhật cuối tuần.) |
| `is_teaching` | boolean | Tuần đó có giảng dạy không (xem mục 5). |
| `is_midterm` | boolean | Tuần có kiểm tra tập trung giữa kỳ (`K`). |
| `is_final` | boolean | Tuần có thi cuối kỳ (`Th`). |
| `is_holiday` | boolean | Tuần có ngày nghỉ lễ chính thức. |
| `holiday_dates` | string | Ngày nghỉ cụ thể (nếu tuần vẫn có ngày học bình thường xen giữa). |
| `notes` | string | Nhãn gốc trên biểu đồ: `Pb`, `Bv`, `Td`, `Av`, `CN` (tuần lễ KHCN), `GDQP-AN`, `TTNT`, lễ tốt nghiệp... |

## 2. `track`

| `track` | Áp dụng cho | 
|---|---|
| `HK_CHINH` | Chương trình chuẩn, đa số SV/HV/NCS (trừ SV CT đại trà HK1 năm 1) |
| `NAM_1` | Sinh viên năm nhất |
| `HK_NGOAI_GIO` | Lớp học ngoài giờ/cuối tuần (hệ CQ, VLVH...) mở trong các HK chính |
| `HK_HE` | Lớp mở riêng trong hè | 

## 3. `semester_id`

- **HK1**: tháng 8 – tháng 12 (khai giảng đến hết thi cuối kỳ 1).
- **HK2**: tháng 1 – tháng 5/6 (đến hết thi cuối kỳ 2).
- **HE**: tháng 6 – tháng 8 (TTNT/thực tập tốt nghiệp đối với `HK_CHINH`/`NAM_1`, hoặc lớp học hè đối với `HK_HE`).

## 4. Đánh số `week`

Biểu đồ gốc dùng số tuần theo chuẩn **ISO 8601**, đánh số lại từ 1 mỗi năm dương lịch — nên cùng một số tuần (VD: tuần 34, 35) xuất hiện **2 lần** trong 1 năm học (1 lần cuối 2025, 1 lần giữa 2026), dễ gây nhầm lẫn.

→ File này đánh lại `week` **tuần tự, liên tục, không lặp số**, bắt đầu từ `week = 1` tại tuần ISO 34/2025 (Thứ Hai 18/08/2025), cứ +1 mỗi tuần cho đến `week = 54` (24/08/2026).

## 5. Quy ước đọc ký hiệu → cột boolean

| Ký hiệu gốc | Ý nghĩa | Ánh xạ |
|---|---|---|
| `K` | Kiểm tra tập trung cuối tuần, **vẫn có lịch học trong tuần** | `is_midterm=True`, `is_teaching=True` |
| *`Th`*| Thi cuối kỳ, **vẫn có lịch học** | `is_final=True`, `is_teaching=True` |
| `Th` | Thi cuối kỳ, **không có lịch học** | `is_final=True`, `is_teaching=False` |
| `Pb`, `Bv` | Phản biện / bảo vệ đồ án, luận văn | ghi ở `notes`|
| `GDQP-AN` (2 đợt, `NAM_1`) | SV chia 2 đợt học GDQP-AN tập trung; **đợt nào đi thì đợt còn lại vẫn học bình thường trên trường** | `is_teaching=True` cho cả 2 đợt, `notes` ghi rõ đợt 1 (tuần 28–30) / đợt 2 (tuần 31–33) |
| `TTNT` (`HK_CHINH`, `NAM_1`) | Thực tập tốt nghiệp | `is_teaching=False`, ghi ở `notes` |
| `CN` | Tuần lễ Khoa học Công nghệ | `is_teaching=True`, ghi ở `notes` |
| Ngày lễ có ngày cụ thể (Quốc khánh, Tết DL, Giỗ Tổ, 30/4-1/5) | Nghỉ lễ nhưng tuần vẫn có ngày học khác | `is_teaching=True`, `is_holiday=True`, ngày cụ thể vào `holiday_dates` |
| Nghỉ Tết Nguyên Đán | Nghỉ trọn tuần | `is_teaching=False`, `is_holiday=True`|
