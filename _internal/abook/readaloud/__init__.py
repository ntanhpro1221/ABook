"""Đọc to cho "Nghe ngay" (docs/LISTEN_ANYTHING.md mục 1 và 3): giọng máy đọc một đoạn chữ thành một "clip" - một file audio ở tốc độ 1,0
cộng mốc từng chữ (một cặp [bắt đầu_ms, kết thúc_ms] cho mỗi chữ `\\S+`, tính từ đầu clip) - rồi giao diện ghép các clip thành chương.

- `mapping`: mảnh từ của nhà cung cấp (WordBoundary) -> mốc của từng chữ hiện. MỘT hàm, điện thoại (Kotlin) cài lại đúng thuật toán ấy
  trên bộ ví dụ chung `tests/fixtures/readaloud/`.
- `websocket`, `edge`: giọng trực tuyến của dịch vụ đọc to Edge, chỉ dùng thư viện chuẩn (gói đóng sẵn không có websockets / aiohttp).
- `windows`: giọng của chính máy Windows (Windows.Media.SpeechSynthesis, nơi giọng tiếng Việt "An" nằm).
- `cache`: bộ nhớ đệm trên đĩa; `service`: ghép giọng + đệm + mốc chữ thành `ReadAloud.clip()` cho máy chủ giao diện.
"""
