# Công cụ phân tích kết quả đo (chép từ scratchpad các phiên 28-29/09)

Đọc kết quả `eval_models.py` dưới `D:/Novels/Audiobooks/_model_eval_v2` và đáp án `gold/` - chỉ đọc, không gọi model.

| script | làm gì |
|---|---|
| `ln_table.py` | bảng bộ LN gốc 6 chương (F1 giọng B-cubed, người nói chặt, cảm xúc) - thư viện cho các script dưới |
| `lnx_table.py` | bộ LN gộp (6 gốc + 6 mở rộng), `--pair A B`: hiệu có KTC95 bootstrap theo chương |
| `ln_categories.py` | người nói đúng theo LOẠI câu (『』, "tôi" nói, vô danh, đối đáp liền, có lời dẫn) |
| `bracket_flip.py` | câu 『』 của hai lượt model: đáp án vs nhãn từng bên - ai bị gán thành ai |
| `gates_table.py` | bốn cổng (TMA, YMP, Tam quốc, Tắt đèn) |
| `cast_absent.py` | câu có người nói không được nhắc tên trong chương (độ tin của thước LN, sổ nhân vật trống) |
| `choose_composition.py` | luật đặt trước của đối chứng v6b: ghi `composition.txt` cho hàng GPU |

Các đường dẫn (EVAL, `D:/Novels/ABook/_internal`) là của máy chủ sách. `choose_composition.py` ghi cạnh chính nó - bản
hàng GPU đang dùng nằm ở scratchpad của phiên.
