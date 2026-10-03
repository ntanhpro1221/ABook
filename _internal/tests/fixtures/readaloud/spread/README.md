# Bộ ví dụ chung: chia mốc theo âm tiết (giọng không báo mốc)

Python (`abook/readaloud/spread.py`, `tests/test_readaloud_byok.py`) và Kotlin (`SyllableSpread.kt`, `SyllableSpreadTest`) đọc CÙNG các
file này. Mỗi file `*.json` một ca: `text` (một đoạn), `durationMs` (độ dài clip), `words` (kết quả đúng sau khi đi qua `map_boundaries` -
xem `../README.md`). Tính `words` bằng tay, đừng chép kết quả của chương trình.

## Thuật toán `boundaries(text, durationMs)` (số nguyên, chia nguyên làm tròn xuống)

1. Chữ hiện = từng đoạn `\S+`. Với mỗi chữ: `w = 4 * syllable_count(NFC(chữ))` (`word_timing.syllable_count`):
   - bỏ các ký tự `"'“”‘’()[]«»—–-…,.!?:;` ở hai đầu, chữ thường; rỗng -> 0;
   - cả chữ là số (`\d+(\.\d{3})*`, chấm ngăn nhóm ba) -> số âm tiết khi đọc thành lời (`read_number`: "2.500" = hai nghìn năm trăm = 4);
   - không thì tách ở mọi ký tự không phải chữ cái / chữ số / `_`; phần toàn chữ số (thập phân) đọc thành lời, phần khác là một âm tiết;
   - nhiều hơn một âm tiết -> số ấy; đúng một và toàn `a-z` (tên ngoại) -> số cụm nguyên âm `[aeiouy]+` (ít nhất 1); còn lại 1.
2. Ngắt sau chữ (trừ chữ cuối): bỏ `"'”’)]»` ở cuối; ký tự cuối thuộc `.!?…` -> 8; thuộc `,;:—–` -> 4; không thì 0.
3. `U` = tổng `w` + tổng ngắt. `U` = 0 hay `durationMs` <= 0 -> không mảnh nào.
4. `trước` = 0; với mỗi chữ: nếu `w > 0` thì mảnh `[durationMs * trước // U, durationMs * (trước + w) // U]`, `char` = vị trí chữ; rồi
   `trước += w + ngắt`.
5. Các mảnh đi qua `map_boundaries` như mọi giọng.

Đọc số (`read_number`) theo nhóm ba chữ số từ phải sang: nhóm 0 bỏ; mỗi nhóm `đọc_ba(nhóm, đủ = không phải nhóm cao nhất)` rồi thêm
"nghìn" / "triệu" / "tỷ" cho nhóm thứ 1 / 2 / 3 (nhóm cao hơn không thêm). Toàn số 0 = "không" (1). `đọc_ba`: trăm (2 âm tiết) nếu `đủ` hay
hàng trăm khác 0; hàng chục 0: "linh" + đơn vị (2) nếu đơn vị khác 0 và (đủ hay có trăm), chỉ đơn vị (1) nếu đơn vị khác 0; hàng chục 1:
"mười" (1) + đơn vị (1) nếu khác 0; hàng chục khác: chục + "mươi" (2) + đơn vị (1) nếu khác 0.
