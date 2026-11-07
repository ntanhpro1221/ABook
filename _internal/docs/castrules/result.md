CPU replay cùng snapshot, 07-11-2026. Sai gộp = sai speaker hoặc kind.

| Tập | Câu | Lỗi trước | Lỗi cuối | Sách tăng lỗi |
|---|---:|---:|---:|---:|
| Raw Qwen 4B/9B | 27726 | 3902 | 3887 | 12/47 |
| Envelope 9B | 9742 | 1603 | 1577 | 2/18 |
| Gold passthrough | 42142 | 2041 | 112 | 0/15 |

Đạt hai ngưỡng tổng, vẫn còn hồi quy từng sách. Raw speaker đúng riêng giảm 5; kind không đổi. Gold là nhãn model lưu có phần phân xử. Không coi gold passthrough là accuracy model hay kết luận về audio.

Lai stage gọi tên: khôi phục phase một neo sau khi chặn trả lời tên/tự giới thiệu/trích lồng và tên trong nhãn quan hệ. Các stage khác giữ hành vi mới. Bảng ablation số tổng trong aggregates.json. Parser/prompt/critic/ledger nằm ngoài đường accuracy replay đã đóng băng; kiểm bằng test.

Pytest 149 file, -rf: 3991 passed, 0 FAILED, 0 errors, 3 skipped. Báo cáo từng sách, 9 test DB và dữ liệu riêng nằm ngoài repo trong tác vụ castrules3. Các file báo cáo cũ đã được move ra thư mục tác vụ. Chưa commit.
