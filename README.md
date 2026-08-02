# NSGA-III University Timetabling

Repository phát triển hệ thống mở lớp, phân sinh viên và xếp thời khóa biểu bằng NSGA-III.

## Cấu trúc repository

```text
NSGAII/
├── README.md
├── NSGA/       # Không gian làm việc chính
└── GA - URA/   # Bản draft cũ, chỉ dùng để tham khảo
```

## `NSGA/`

Đây là **không gian làm việc chính** của project. Mọi code, cấu hình, kiểm thử và tài liệu đang được phát triển phải đặt trong thư mục này.

```text
NSGA/
├── data/          # Dữ liệu nguồn, dữ liệu đã xử lý và pipeline chuẩn bị dữ liệu
├── core/          # Mô hình, xây bài toán, phân sinh viên và đánh giá nghiệm
├── optimizer/     # Thuật toán NSGA-III
├── output/        # Ranking, báo cáo và xuất kết quả
├── tests/         # Kiểm thử dữ liệu, bài toán, assignment và optimizer
├── config.yaml    # Tham số học kỳ và thuật toán
└── main.py        # Điểm chạy chính của pipeline
```

## `GA - URA/`

Đây là bản draft cũ được giữ lại để tham khảo:

- cách đọc và xử lý dữ liệu ban đầu;
- các model và constraint đã thử nghiệm;
- mã NSGA-II cũ;
- tài liệu đặc tả và kết quả thử nghiệm trước đây.

Không tiếp tục phát triển tính năng mới trực tiếp trong `GA - URA/`. Khi cần tái sử dụng, hãy kiểm tra lại tính đúng đắn rồi chuyển phần phù hợp sang `NSGA/`.

## Quy ước làm việc

- Phát triển mới trong `NSGA/`.
- Không sửa dữ liệu nguồn trực tiếp.
- Không import code runtime từ `GA - URA/` vào project chính.
- Chỉ dùng `GA - URA/` để đối chiếu hoặc tham khảo khi triển khai lại.
