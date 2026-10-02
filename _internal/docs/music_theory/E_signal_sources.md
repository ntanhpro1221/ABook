# E. Nguồn tín hiệu - rà soát (Lead, 02-10 tối)

Câu hỏi bản A-D bỏ sót: **mỗi phía có những dữ liệu gì về một bài nhạc / một đoạn truyện, và ta đang dùng bao nhiêu trong
số đó?** A-D đào sâu cách BIỂU DIỄN cảm xúc và cách model nghe, nhưng ngầm coi bài nhạc là "file âm thanh trần" và đoạn
truyện là "đoạn chữ trần". Chủ sách chỉ ra hai lần (văn bản quanh bài; đặc trưng âm học). Bản này rà có hệ thống cả hai phía
để không còn lần thứ ba.

Nguồn: khảo sát MMER (Rashini et al. 2025, arXiv 2504.18799), khoảng cách phân phối trong MER (arXiv 2510.04688),
LLM gắn nhãn cảm xúc nhạc (arXiv 2508.12626), TTMR++ (Doh et al. 2024, arXiv 2410.03264), M2M-Gen (arXiv 2410.09928),
hệ thống tự gắn nhạc cho sách nói (Chen et al., Interspeech 2022).

## 1. Phía bài nhạc

Khảo sát MMER liệt kê 7 loại nguồn: âm thanh, lời, hình (video), ký hiệu (MIDI), sinh lý, văn bản người dùng (bình luận,
review), siêu dữ liệu + ngữ cảnh. Với danh mục nhạc nền không lời của ta, áp được 5:

| Nguồn | Có gì | Ta đang dùng (02-10) | Việc |
|---|---|---|---|
| Âm thanh qua model nhúng | CLAP, (MERT/MuQ/Jukebox - NC, dùng được) | CLAP + đầu dò học từ feel Incompetech | thêm MERT/MuQ vào ablation; học đầu dò trên NHIỀU bộ dữ liệu (dưới) |
| Âm học đo trực tiếp | nhịp, trưởng/thứ, âm vực, nghịch tai, articulation, đường bao to-nhỏ, MFCC, chroma | 6 đặc trưng, chỉ chép vào danh mục | Music đang làm ~50 đặc trưng (acoustic_features2.py) |
| Mô tả của model nghe | Omni/Music Flamingo mô tả từng clip | 310 chú thích Omni chỉ dùng cho E1 | đưa chú thích vào kênh chữ như một văn bản nữa (ghi rõ là máy viết) |
| Văn bản quanh bài | tên, tác giả, mô tả, ghi chú, tag, nhạc cụ, BPM người nhập, bình luận, tên album/game/phim | tag feel Incompetech làm NHÃN | kênh chữ (Claude theo lô) - đang chạy |
| Ngữ cảnh web | bài viết cho game/phim nào, tác giả nổi tiếng với thể loại gì | không | sau ablation kênh chữ |

Kết quả nghiên cứu đáng dùng ngay:
- **Gộp nhúng sâu + đặc trưng kinh điển thắng từng cái riêng** khi đổi bộ dữ liệu: Jukebox + chroma là tổ hợp tổng quát nhất
  (2510.04688); đặc trưng kinh điển riêng chỉ đạt R² ~0,54 trên EmoMusic. Tức là (A)+(B) không phải thừa.
- **Huấn luyện trên nhiều bộ dữ liệu gộp** (EmoMusic + PMEmo + WTC) tổng quát tốt hơn một bộ (2510.04688). Đầu dò hiện chỉ học
  từ feel Incompetech -> thêm DEAM, PMEmo, EmoMusic, và nhất là **Soundtracks (Eerola & Vuoskoski 2011, 360 đoạn nhạc phim,
  nhãn rời rạc + chiều)** - miền gần nhất với nhạc nền cho truyện.
- **Đa nguồn hơn đơn nguồn rõ rệt**: ví dụ 79,2% đa nguồn so 70,6% chỉ âm thanh, 62,9% chỉ lời (khảo sát MMER). Gộp muộn
  (late fusion, stacking) là cách phổ biến và bền khi thiếu nguồn - hợp với ta vì nhiều bài không có chữ.
- **LLM gắn nhãn cảm xúc nhạc**: GPT-4o tự nhất quán cao (385/400 trùng cả 3 lần), đúng 85% ở mẫu chuyên gia đồng thuận nhưng
  chỉ 54% ở mẫu chuyên gia chia rẽ (2508.12626) -> kênh chữ cần ĐỘ TIN CẬY, và gộp theo độ tin cậy là đúng hướng.
- **TTMR++**: sinh mô tả giàu từ tag + siêu dữ liệu bằng LLM rồi mới nhúng làm tìm nhạc bằng câu chữ tốt hơn hẳn. Áp cho ta:
  mỗi bài có một **đoạn mô tả tổng hợp** (từ chữ quanh bài + chú thích model nghe + đặc trưng âm học đọc thành lời).

### Model nghe (so 02-10)

| Model | Số đo nhạc | Ghi chú |
|---|---|---|
| Music Flamingo (NVIDIA, ICLR 2026) | MuChoMusic 74,6; MMAU-Pro-Music 65,6 (hơn Gemini 2.5 Flash 64,9); MMAU-Music 76,8 | chuyên nhạc, ~8B; ứng viên chính E1b |
| Qwen3-Omni 30B-A3B | MuChoMusic 52,1 | quá to cho card 8 GB / Mac 16 GB -> Modal nếu cần |
| Qwen2.5-Omni 7B | MMAU-Music ~69 | đang có; so cặp hỏng (thiên vị vị trí), chấm từng clip đang xếp hàng |
| Audio Flamingo 3, Step-Audio 2, Kimi-Audio, MiDashengLM | đa năng | thay thế nếu cần |
| Essentia (DEAM/emoMusic/MuSe V-A; MTG-Jamendo mood/theme) | model chuyên, không LLM | CPU, rẻ; nguồn (A') trong ablation |

## 2. Phía đoạn truyện

| Nguồn | Có gì | Ta đang dùng | Việc |
|---|---|---|---|
| Chữ của cảnh | lời kể, thoại, nhãn câu (cảm xúc, loại câu) | nhãn câu -> V/E/T + 13 cường độ (quá thô, theo kiểm hồi quy) | segllm cho cảnh (đang xếp hàng) |
| Ngữ cảnh truyện | cung truyện, chương trước/sau, tên chương, nhân vật có mặt | ít | segllm đọc tóm tắt chương trước + tên chương |
| Thẻ thể loại của cuốn | hako có thẻ: Action, Horror, Romance, Psychological... | không | Lớp 4 (phong cách cuốn) + tiên nghiệm cho cảnh: sách Horror kéo trục căng thẳng |
| Tranh minh hoạ | trang "Minh họa" của tập | không (bị lọc khi tải) | về sau: model nhìn ảnh cho không khí tập |
| Bình luận người đọc theo chương | hako có bình luận từng chương | không | về sau: người đọc nói "chương này buồn quá" là nhãn tự nhiên |
| **Bản chuyển thể có nhạc** | nhiều LN có anime / drama CD: nhạc phim do người chọn cho đúng các cảnh ấy | không | mạnh nhất cho Lớp 4: phong cách nhạc của cuốn học theo OST của anime (dụng cụ, thể loại), không dùng bài OST |

## 3. Sợi dây (ghép hai phía)

Hiện: khoảng cách trên Lớp 1 (+ Lớp 2 đang tắt). Nghiên cứu cho thêm hai đường:
- **"Chỉ thị nhạc" bằng lời (M2M-Gen)**: LLM đọc cảnh -> một câu mô tả nhạc cần ("piano chậm, buồn, có hi vọng, không trống").
  Ghép với **mô tả tổng hợp** của bài (mục 1) bằng nhúng chữ-chữ / chữ-âm (CLAP text). Mang theo thông tin mà 13 cường độ làm
  mất (nhạc cụ, nhịp, kết cấu).
- **LLM xếp lại** (rerank): lấy K bài tốt nhất theo Lớp 1-2 + chỉ thị, đưa tóm tắt cảnh + mô tả K bài cho LLM chọn. Đúng việc
  "chất keo" chủ sách nói; chỉ làm trên K nhỏ nên rẻ.
Đo cả hai bằng máy chấm kiểu E1 (Claude chấm mù + model nghe chấm từng clip), ghi trước.

## 4. Chấm / đo

- Không người chấm: chủ sách KHÔNG chấm gì; trọng số Bradley-Terry học từ máy chấm (E1: Claude mù ổn định 0,80-0,87, κ 0,81
  giữa hai người chấm; Omni so cặp hỏng vì thiên vị vị trí -> chuyển chấm từng clip).
- Bài kiểm ngoài: Soundtracks (nhạc phim có nhãn), IncompeBench (tìm nhạc trên chính Incompetech).

## 5. Thứ tự làm (theo lợi / công)

1. segllm cho cảnh (đang xếp hàng GPU) - nút thắt số 1 theo E1.
2. Kênh chữ + âm học phía bài, ablation (Music đang chạy).
3. Thẻ thể loại hako -> tiên nghiệm cuốn (rẻ: đã có thẻ khi tải).
4. Mô tả tổng hợp mỗi bài + chỉ thị nhạc mỗi cảnh + ghép chữ-chữ.
5. LLM xếp lại top-K.
6. Đầu dò học trên nhiều bộ dữ liệu (Soundtracks, DEAM, PMEmo, EmoMusic).
7. Về sau: OST anime cho phong cách cuốn, bình luận chương, tranh minh hoạ.

## 6. Thầy - trò: bài có ngữ cảnh dạy model chỉ-nghe (chủ sách 02-10)

Danh mục của ta có ngữ cảnh đầy đủ (chữ quanh bài, tag người gắn, tác giả), nên nhãn suy từ đó khá đáng tin. Nhưng app còn
phân tích **âm thanh người dùng tự nhập**, không có ngữ cảnh: lúc ấy model nghe quyết định 100%. Hướng đúng là **học với
thông tin đặc quyền** (Vapnik & Vashist 2009, LUPI) / **chưng cất chéo kênh**: ngữ cảnh chỉ có lúc học, lúc dùng chỉ có âm
thanh.

1. **Thầy** = gộp mọi nguồn (kênh chữ + tag người gắn + âm học + model nghe lớn) -> 13 cường độ + V/E/T + độ tin cậy cho mỗi
   bài có ngữ cảnh.
2. **Trò** = model NHỎ chỉ nhận âm thanh (đầu dò / tinh chỉnh nhẹ trên nhúng CLAP / MERT / MuQ + đặc trưng âm học), học bắt
   chước nhãn thầy, mất mát nhân trọng số theo độ tin cậy của thầy.
3. **Thêm dữ liệu cho trò**: thầy gán nhãn cho kho nhạc mở có siêu dữ liệu (MTG-Jamendo ~55k bài có tag mood/theme, FMA có
   tag/thể loại) -> hàng chục nghìn bài thay vì 2.000.
4. **Kiểm**: (a) giữ ngoài một phần danh mục, GIẤU ngữ cảnh, đo trò so nhãn thầy; (b) bài kiểm có nhãn người: DEAM,
   Soundtracks; (c) máy chấm kiểu E1 trên chọn nhạc cuối. Ghi trước.
5. **Chạy ở đâu**: trò phải chạy trên máy người dùng (card 8 GB hoặc CPU). Model nghe lớn (Music Flamingo, Qwen3-Omni) chỉ
   làm thầy / giám khảo khi phát triển, không đi theo app.
6. Âm thanh người dùng nhập vẫn có thể mang chút ngữ cảnh (tên file, thẻ ID3 tên bài / nghệ sĩ / thể loại): dùng nếu có, như
   thầy, nhưng không trông vào.
7. Chỗ cắm trong app: `abook/webui/music_local.py` - `set_analyzer(hàm)` nhận `analyze(path) -> {valence, arousal, tension, sd,
   emotions{13}, confidence, fitsUnderNarration, loudness}`; chưa cắm thì bài nhập ở trạng thái "chưa phân tích" (không bịa số).
   Xem `docs/MUSIC_IMPORT.md`.
