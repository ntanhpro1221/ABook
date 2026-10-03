# Bộ ví dụ chung của "đọc to" (Nghe ngay)

Python (`abook/readaloud/mapping.py`, `tests/test_readaloud.py`) và Kotlin (điện thoại) đọc CÙNG các file này. Mỗi file `*.json` là một ca:

```json
{
  "note": "một dòng nói ca này thử gì",
  "text": "Xin chào — các bạn.",
  "durationMs": 2000,
  "boundaries": [ { "text": "Xin", "start": 0, "end": 400, "char": 0 }, ... ],
  "words": [ [0, 400], [400, 900], [900, 1000], [1000, 1300], [1300, 1900] ]
}
```

- `text`: đoạn chữ đem đọc (một đoạn của chương, `paragraphsOf`). **Chữ hiện** = từng đoạn `\S+` (như `words.ts countTokens`, `word_timing.tokens`).
- `durationMs`: độ dài clip audio.
- `boundaries`: các mảnh nhà cung cấp báo, theo thứ tự đọc. `text` mảnh chữ; `start` / `end` ms tính từ đầu clip (Edge báo tick 100 ns: chia 10 000, làm tròn xuống);
  `char` (có thể vắng) vị trí ký tự (code point, đếm từ 0) của mảnh trong `text` - Windows có, Edge không.
- `words`: kết quả đúng: đúng một cặp `[start, end]` cho mỗi chữ hiện.

## Thuật toán `map_boundaries(text, boundaries, durationMs) -> words` (mọi phép toán là số nguyên, chia là chia nguyên làm tròn xuống)

1. `fold(s)`: NFC, chữ thường, chỉ giữ ký tự thuộc nhóm Unicode **L\*** và **N\*** (Kotlin: `Character.getType` thuộc LETTER hay NUMBER).
   Mỗi chữ hiện có `fold` riêng (có thể rỗng: chữ chỉ có dấu câu).
2. Con trỏ `(t, c)`: chữ `t`, đã dùng `c` ký tự đầu của `fold` chữ ấy. Ban đầu `(0, 0)`.
3. Với mỗi mảnh theo thứ tự (bỏ mảnh có `fold` rỗng):
   - Nếu có `char`: `g` = chữ chứa ký tự thứ `char` (rơi vào khoảng trắng thì chữ kế sau, quá cuối thì chữ cuối). Nếu `g > t` thử tìm mảnh bắt đầu từ `(g, 0)` trước.
   - Không thì (hay không thấy) tìm mảnh từ `(t, c)`: nối `fold` của chữ `t` (bỏ `c` ký tự đầu) với các chữ sau; chỉ nhận chỗ khớp **bắt đầu** trong `LOOKAHEAD = 8` chữ đầu
     (chữ `t` .. `t + 8`). Ưu tiên chỗ khớp đầu tiên bắt đầu đúng đầu một chữ hay đúng `(t, c)`; không có thì chỗ khớp đầu tiên giữa chữ. Mảnh có thể trải qua nhiều chữ.
   - Không thấy: bỏ mảnh (không đổi con trỏ).
   - Thấy, phủ chữ `first..last` (chữ `first` từ ký tự `offset`, chữ `last` tới ký tự `stop`): chia `[start, end]` cho các chữ phủ theo số ký tự `fold` mỗi chữ được phủ
     (`lo = start + (end-start) * trước // tổng`, `hi = start + (end-start) * (trước+size) // tổng`). Chữ chưa có mốc nhận `lo` làm bắt đầu; kết thúc luôn là `hi` mới nhất.
     Con trỏ chuyển tới `(last, stop)`.
4. Chữ chưa có mốc (dấu câu trơ, số được đọc thành lời...): mỗi cụm liên tiếp nhận khoảng từ `left` = kết thúc của chữ có mốc trước nó (0 nếu không có) tới `right` = bắt đầu của chữ có mốc
   sau nó (`durationMs` nếu không có; không nhỏ hơn `left`), chia theo độ dài chữ (số ký tự của chính chữ hiện, kể cả dấu câu), cùng công thức chia nguyên như trên.
5. Làm sạch theo thứ tự chữ: `start = min(max(start, startTrước), durationMs)`, `end = min(max(end, start), durationMs)`; rồi `end[i] = min(end[i], start[i+1])`.

Thêm ca mới: viết file `*.json` với `words` tính tay (đừng chép kết quả của chương trình), chạy `tests/test_readaloud.py`.
