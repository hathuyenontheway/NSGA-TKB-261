# Mô tả dữ liệu bổ sung

## `KHGD (1).DBF`

Kế hoạch giảng dạy/chương trình đào tạo của học kỳ.

File này được dùng để:

- xác định các môn thuộc kế hoạch học kỳ;
- xác định môn bắt buộc và môn tự chọn;
- lấy thông tin chương trình, khóa, học kỳ và khối lượng giảng dạy;
- bảo đảm các môn bắt buộc trong kế hoạch được mở và xếp đầy đủ.

`kq_nv.csv` cung cấp nhu cầu đăng ký của sinh viên, nhưng không thay thế `KHGD (1).DBF` khi xác định tập môn của học kỳ.

## `TAM252.xlsx`

Dữ liệu tham khảo do Phòng Đào tạo cung cấp cho học kỳ 252.

File được dùng để tham khảo quan hệ:

```text
môn học/nhóm lớp → tính chất phòng
```

Các cột chính:

- `F_MAMH`: mã môn;
- `F_MANH`: mã nhóm lớp, không phải mã phòng;
- `F_SISO`: sĩ số tham khảo;
- `F_TCPHONG`: tính chất phòng được sử dụng.

## `TAM261.xlsx`

Dữ liệu tham khảo do Phòng Đào tạo cung cấp cho học kỳ 261.

Tác dụng chính giống `TAM252.xlsx`: tham khảo cách Phòng Đào tạo ánh xạ môn/nhóm lớp với tính chất phòng. Vì đây là học kỳ gần hơn nên có thể ưu tiên dữ liệu 261 khi hai kỳ khác nhau, nhưng cần đánh dấu để kiểm tra.

Các cột chính:

- `F_MAMH`: mã môn;
- `F_MANH`: mã nhóm lớp;
- `F_SISO`: sĩ số;
- `F_TCPHONG`: tính chất phòng;
- `F_DAXEP`: thông tin đã xếp, cần xác nhận ý nghĩa khi sử dụng.

## Cách sử dụng hai file TAM

Hai file TAM không cung cấp trực tiếp danh sách phòng cho mỗi môn. Chúng được dùng theo pipeline:

```text
(mã môn, loại session)
→ F_TCPHONG trong TAM252/TAM261
→ Tính chất phòng trong room261.csv
→ danh sách Mã Phòng có thể sử dụng
```

Ví dụ, nếu một môn có 60 nhóm nhưng tính chất phòng tương ứng chỉ có hai phòng trong `room261.csv`, tất cả nhóm của môn đó chỉ được xếp vào hai phòng này. Nếu không đủ thời gian sử dụng phòng, hệ thống phải báo thiếu tài nguyên, không tự chuyển sang phòng khác tính chất.

## Các cập nhật so với đặc tả ban đầu

- `KHGD (1).DBF` là nguồn xác định tập môn của học kỳ.
- Môn bắt buộc phải được mở; môn tự chọn chỉ mở khi số sinh viên đăng ký trong `kq_nv.csv` đạt ngưỡng.
- Mở lớp, xếp lịch và phân sinh viên được giải trong cùng một bài toán để ưu tiên sinh viên học được nhiều môn nhất.
- Lecture và lab có mã môn khác nhau; quan hệ giữa chúng lấy từ `MAKEM` hoặc mapping đã xác nhận.
- Phòng phụ thuộc đồng thời vào môn và loại session.
- Tối thiểu việc di chuyển giữa CS1 và CS2; báo lỗi nếu hai session khác cơ sở liên tiếp hoặc chỉ cách nhau một tiết.
- Thứ Bảy chỉ được dùng khi không thể tìm được phương án khả thi từ thứ Hai đến thứ Sáu.
- Thuật toán mục tiêu là NSGA-III; mỗi chromosome cần có ranking và danh sách vi phạm để hỗ trợ chỉnh thủ công.
