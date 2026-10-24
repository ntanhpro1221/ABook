# Kiểm chạm thật trước phát hành

Từ `_internal/ui`, dựng chính cây hiện tại bằng `node node_modules/vite/bin/vite.js build`
(dùng dependency sẵn có). Từ `_internal`:

```text
python scripts/tap_audit/run.py
python scripts/tap_audit/run.py --inject-fault
python -m pytest -p no:cacheprovider -rf scripts/tap_audit/test_tap_audit.py
```

Lượt đầu phải PASS 9/9, exit 0. Đối chứng âm phải FAIL, exit 1: đặt
`pointer-events:none` trên lớp đang mở khi body bị khóa, mô phỏng lỗi 0.4.134.
Exit 2 nghĩa là không tìm thấy Edge/Chrome; có thể truyền `--edge PATH`.
`--only "Add book"` lọc theo tên (không khớp thì FAIL), `--json` chỉ in JSON,
`--output report.json` lưu bằng chứng đầy đủ; `--static-dir PATH` đè bản UI.

Server fixture dùng backend của cây chứa script, cổng hệ điều hành cấp và FakeRunner.
Sách/SQLite/preferences giả nằm trong thư mục tạm mới; không chạy model hay tạo audio.
Edge/Chrome headless có profile tạm mới và các cờ riêng tư; kết thúc chỉ thu hồi cây PID
do audit mở, rồi xóa profile và dữ liệu fixture. Giới hạn affinity tối đa bốn CPU logic,
các pool tính toán tối đa bốn luồng, tắt GPU. Trình duyệt vẫn có các luồng quản lý riêng.

Audit dùng CDP để bấm tọa độ bằng chuột và touch, kiểm trusted click, nhập chữ,
đóng lớp, giải phóng khóa body và hit-test nút nền. Không gọi DOM `.click()`.
Control disabled được ghi SKIP_DISABLED. Body `pointer-events:none` của Radix là hợp lệ
khi lớp phục hồi hit-testing; kiểm tổ tiên bị chặn bên trong lớp và `elementFromPoint`.

Phạm vi: chín kịch bản ở mobile 412×915 và desktop 1280×900; hit-test tại tâm
control đang hiện, một probe vô hại mỗi lớp bằng cả chuột/touch. Không chứng minh
Android/WebView vật lý, hộp chọn file native, audio, toàn diện tích chạm hay mọi lớp UI.
Pytest chỉ kiểm schema kịch bản, cổng rảnh và phân tích báo cáo; không mở trình duyệt.
