# Nguồn mẫu nhỏ

- `pytest-passed.txt`: stdout thật ngày 05-11-2026, lệnh `PY -X utf8 -m pytest -o addopts= -q -rf _internal/tests/test_release_script.py`, tại worktree relgate (11 passed).
- `vitest-a90a.txt`: nguyên dòng summary Vitest được lưu trong `docs/TEST_REPORT.md`, đoạn “Đợt a90a (C1/C2/V3)” (1354 passed, 1 skipped). Chỉ trích dòng parser cần, không coi đây là bằng chứng chạy Vitest hiện tại.
- `gradle/TEST-AutoRewind.xml`: XML thật từ `mobile/android/app/build/test-results/testDebugUnitTest/TEST-vn.abook.player.AutoRewindTest.xml` của full gate 05-11-2026; chỉ thay hostname và giờ tuyệt đối bằng dữ liệu trung tính. Giữ số đếm, testcase và định dạng. Toàn lượt có 3303 passed, 7 skipped, 377 suite, 0 failed/error.
- Các XML lỗi khác do bài thử dựng để kiểm đủ đường lỗi và đối chiếu testcase.
