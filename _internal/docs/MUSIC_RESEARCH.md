# Nhạc nền - bản đồ nghiên cứu

Chủ sách 01-10: nhạc nền mặc định BẬT, là một lớp riêng của cuốn sách (như phụ đề của video), máy tự làm hết, người dùng
chỉ can thiệp nếu muốn; "model phân tích nhạc, cảm xúc cảnh cũng phải nghiên cứu, phân tích kỹ lưỡng, có kế hoạch chứ
không phải cứ pick đại". File này là kế hoạch ấy - cùng cách làm với `ANALYSIS_RESEARCH.md`: câu hỏi, đáp án chuẩn, thước
đo, ứng viên, luật quyết định; kết quả từng lượt đo ghi ngay dưới mục của nó.

Trạng thái 01-10 23:xx: đã có BẢN THỬ (đường cơ sở) ở cả bốn khâu - CLAP zero-shot cho nhạc, công thức gộp cảm xúc câu
thành đoạn (`webui/music_scenes.py`), chọn bài gần nhất (`webui/music_select.py`), danh mục tĩnh (`LLM_Train/music/`).
Đường cơ sở là để có số đầu tiên, KHÔNG phải lựa chọn: mọi tham số trong đó sẽ được đo lại ở các pha dưới.

## Bốn câu hỏi

1. **Cảnh.** Truyện chia thành đoạn nào, mỗi đoạn mang không khí gì (vui/buồn, êm/dồn dập, căng thẳng, loại cảnh: chiến
   đấu, tang lễ, lãng mạn...)?
2. **Nhạc.** Mỗi bài mang cảm xúc gì, và có HỢP LÀM NỀN cho giọng đọc không (không lời, giai điệu không nổi, cường độ ổn
   định, lặp được)?
3. **Ghép.** Với một đoạn, bài nào hợp nhất; khi không có bài đúng thì "tương đương" là gì; khi nào nên im lặng?
4. **Trộn.** Nhạc to bao nhiêu, hạ bao nhiêu khi có giọng, chuyển cảnh bao lâu - để nhạc không làm khó nghe lời.

## Không có người nghe thì lấy đâu ra sự thật?

Chủ sách không nghe thử. Nên sự thật phải đến từ dữ liệu có nhãn của NGƯỜI có sẵn, và từ thước đo khách quan:

| Dùng cho | Dữ liệu | Vì sao |
|---|---|---|
| Cảm xúc nhạc, ĐÚNG MIỀN | **Film soundtracks** (Eerola & Vuoskoski 2011): 360 + 110 trích đoạn nhạc phim 15 giây-1 phút, điểm vui/buồn, năng lượng, căng thẳng + 6 cảm xúc rời, do 116 người chấm | Nhạc phim = nhạc nền cho câu chuyện - gần nhất với nhạc nền sách nói |
| Cảm xúc nhạc, chuẩn chung | DEAM (~1.800 bài, vui/buồn x dồn dập liên tục), PMEmo, EmoMusic; GlobalMood (2025, nhãn của 5 nền văn hoá - quan trọng vì người nghe Việt) | Thước chuẩn của ngành; GlobalMood cho biết model có lệch văn hoá không |
| Cảm xúc nhạc, ĐÚNG KHO | Incompetech: 1.443 bài có nhãn "feel" do người gắn (Dark, Calming, Somber, Epic, Suspenseful...) | Nhãn yếu nhưng là đúng kho mình dùng |
| Có lời / không lời | MTG-Jamendo (nhãn giọng), Incompetech (gần như toàn không lời) | Bài có lời phải loại tuyệt đối |
| Cảnh trong truyện | ĐÁP ÁN CẢNH làm theo nhu cầu (luật 20-09): vài chương mỗi thể loại trong bộ gold sẵn có - ranh giới đoạn + không khí + loại cảnh; Claude soạn, agent soát đối kháng (như gold phân vai) | Chưa có bộ dữ liệu cảnh nào cho truyện Việt / truyện dịch |
| Trộn | Chính dây chuyền: Whisper đo lỗi nhận dạng (WER) của chương có nhạc so với không nhạc | Khách quan: nhạc làm nhòe lời thì WER tăng |

Mốc tham khảo: tổng hợp các nghiên cứu 2014-2024 cho thấy model tốt nhất đoán vui/buồn tương quan r ~ 0,67 và dồn dập
r ~ 0,81 với người - vui/buồn khó hơn hẳn. Kỳ vọng đặt theo đó.

## Pha 1 - model cảm xúc nhạc (bake-off)

Ứng viên (GIẤY PHÉP là cổng đầu tiên - danh mục nhạc được phát hành công khai cùng app):

| Ứng viên | Cách dùng | Giấy phép trọng số |
|---|---|---|
| LAION-CLAP (htsat-unfused, music, music_speech) | zero-shot bằng câu mô tả; hay nhúng + đầu hồi quy học trên DEAM/Soundtracks | Apache-2.0 - dùng được |
| MS-CLAP 2023 | như trên | phải kiểm |
| MuQ / MuQ-MuLan (Tencent) | nhúng + đầu hồi quy; MuLan zero-shot | CC BY-NC 4.0 - chỉ để so, không dùng cho danh mục |
| MERT-v1 (95M/330M) | nhúng + đầu hồi quy (tốt nhất trong nhiều benchmark) | thẻ model mâu thuẫn (MIT / CC BY-NC) - phải kiểm trước khi dùng |
| Essentia (musicnn, Discogs-EffNet + đầu mood) | dùng thẳng | CC BY-NC-ND - chỉ để so |
| Đặc trưng âm học cổ điển (độ to, độ sáng phổ, nhịp, điệu trưởng/thứ) | hồi quy nhỏ | tự làm |
| Audio-LLM (Qwen2.5-Omni...) | "nghe" rồi mô tả | phải kiểm; nặng - chỉ làm giám khảo |

Giao thức: đầu hồi quy học trên DEAM + PMEmo, đo trên Film soundtracks và Incompetech (KHÔNG cùng nguồn với lúc học - đo khả
năng khái quát), kiểm chéo theo nguồn. Thước: tương quan (Pearson, CCC) cho vui/buồn và dồn dập; ROC-AUC từng nhãn feel
của Incompetech; độ lệch theo văn hoá trên GlobalMood. Luật nhận: model có giấy phép dùng được, tốt nhất trên Film
soundtracks, không kém đường cơ sở CLAP zero-shot ở Incompetech.

"Hợp làm nền" đo riêng, khách quan: xác suất có lời (kiểm trên MTG-Jamendo), độ nổi của giai điệu, độ ổn định cường độ
(phương sai độ to theo cửa sổ), có lặp liền được không (ghép đuôi-đầu theo phách).

## Pha 2 - cảm xúc cảnh

Ứng viên:
- **A (đường cơ sở, đã có):** gộp cảm xúc từng câu, ranh giới từ dòng ngăn cảnh / mốc thời gian / không khí đổi và giữ.
- **B:** model đọc hiểu đọc CẢ ĐOẠN và nói: ranh giới cảnh, không khí, độ căng, loại cảnh, bối cảnh (trong nhà / chiến
  trường / cung điện...). Bằng chính model phân tích truyện hay một model lớn hơn.
- **C:** lai - A cho ranh giới thô, B gắn nhãn đoạn.

Thước: ranh giới đoạn bằng Pk và WindowDiff (thước chuẩn của bài toán chia đoạn văn bản); không khí bằng sai số trên hai
trục và độ đúng loại cảnh so với đáp án cảnh; độ ổn định (số lần đổi nhạc mỗi giờ - đổi quá dày là lỗi người nghe ghét
nhất). Đo theo từng truyện, báo từng truyện (luật đa thể loại 27-09).

## Pha 3 - ghép đoạn với nhạc

Ứng viên: (1) gần nhất trên hai trục (đường cơ sở); (2) truy hồi chữ-nhạc: model đọc hiểu viết mô tả nhạc cho đoạn ("tiếng
đàn tranh chậm, buồn, đêm mưa"), CLAP tìm bài gần câu mô tả nhất; (3) kết hợp hai điểm. Thước khi không có người nghe:
độ khớp giữa không khí đoạn (đáp án cảnh) và nhãn người gắn của bài được chọn (Incompetech feel, Film soundtracks); giám
khảo audio-LLM trên mẫu nhỏ, chỉ tin khi nó đồng ý với nhãn người ở các ca đã biết. Trang nghe thử A/B vẫn có, là tuỳ chọn.

## Pha 4 - trộn

Đo bằng chính dây chuyền: Whisper trên chương có nhạc ở nhiều mức (nền thấp hơn giọng 15 / 18 / 21 / 24 / 27 LU, có / không
hạ khi có giọng), lấy mức to nhất mà WER tăng không quá một ngưỡng nhỏ so với bản không nhạc; kiểm thêm độ to toàn chương
và trần đỉnh như luật cân mức hiện có (AGENTS.md). Thời gian chuyển cảnh, độ dài vào/ra đặt theo cùng phép đo.

## Thứ tự và tài nguyên

0. Dữ liệu (đang chạy): Incompetech 1.443 bài (đọc 3 đoạn từ máy chủ), Jamendo CC BY 665 bài; tải Film soundtracks,
   DEAM, PMEmo, GlobalMood (kiểm giấy phép từng bộ - chỉ để đo, không phát hành).
1. Bake-off model nhạc - CPU / hàng GPU nhà ngoài giờ êm; tín dụng Modal khi cần nhiều.
2. Đáp án cảnh: 2-3 chương mỗi thể loại (LN Nhật, tiên hiệp, Tam quốc / Đông Chu, truyện Việt) rồi đo A / B / C.
3. Ghép, 4. trộn - sau khi 1 và 2 có kết quả.

Mỗi pha xong: ghi số vào đây, đổi tham số trong app theo kết quả, nói rõ cái gì đã đo và cái gì còn là đường cơ sở.
