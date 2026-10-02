# Nhạc nền - bản đồ nghiên cứu

Chủ sách 01-10: nhạc nền mặc định BẬT, là một lớp riêng của cuốn sách (như phụ đề của video), máy tự làm hết, người dùng
chỉ can thiệp nếu muốn; "model phân tích nhạc, cảm xúc cảnh cũng phải nghiên cứu, phân tích kỹ lưỡng, có kế hoạch chứ
không phải cứ pick đại". File này là kế hoạch ấy - cùng cách làm với `ANALYSIS_RESEARCH.md`: câu hỏi, đáp án chuẩn, thước
đo, ứng viên, luật quyết định; kết quả từng lượt đo ghi ngay dưới mục của nó.

Trạng thái 01-10 23:xx: đã có BẢN THỬ (đường cơ sở) ở cả bốn khâu - CLAP zero-shot cho nhạc, công thức gộp cảm xúc câu
thành đoạn (`webui/music_scenes.py`), chọn bài gần nhất (`webui/music_select.py`), danh mục tĩnh (`LLM_Train/music/`).
Đường cơ sở là để có số đầu tiên, KHÔNG phải lựa chọn: mọi tham số trong đó sẽ được đo lại ở các pha dưới.

## Nền tảng (chủ sách chốt 01-10 23:xx-00:xx: không tên miền, không thẻ, không rủi ro chi phí)

- Dữ liệu phân tích + chỉ mục lướt/tìm/lọc: **Cloudflare Pages** (gói miễn phí, không thẻ - không thể phát sinh tiền; lượt
  tải file tĩnh không giới hạn; 20.000 file / 25 MB mỗi file). Chỉ mục bằng **Pagefind** (tìm kiếm tĩnh chia mảnh). Thử
  01-10: 1.607 bài -> 1.641 file, 3,3 MB; tìm + lọc + đếm theo bộ lọc + sắp xếp ~180 ms, ~85 KB tải.
- File nhạc: KHÔNG tự đặt kho (Pages không sinh ra cho kho media; R2 cần tên miền + thẻ). Lấy từ nguồn gốc khi cuốn sách
  dùng bài, đệm trên máy,  mang theo file; dự phòng khi nguồn gỡ bài = bản trên Internet Archive (kho công cộng cho
  nội dung giấy phép mở, miễn phí vĩnh viễn).
- Openverse chỉ là "tìm thêm ngoài danh mục" (vô danh, hạn mức theo IP từng người dùng); máy dựng danh mục lấy bài bằng
  API nguồn gốc (điều khoản Openverse cấm cào kho).
- Tài khoản (đã có từ 02-10): Cloudflare - Worker tĩnh `abook-music` (triển khai bằng `wrangler deploy` trong
  `LLM_Train/music`); archive.org - khoá S3 để đăng bản dự phòng.

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

**Kết quả (Film soundtracks, 470 trích đoạn, tương quan Pearson với điểm trung bình của người):**

| Model | Cách | vui/buồn | năng lượng | căng thẳng | 5 cảm xúc rời (chính xác, đoán bừa 20%) |
|---|---|---|---|---|---|
| LAION-CLAP htsat-unfused (01-10) | zero-shot (câu mô tả của analyze_clap.py) | 0,589 | 0,714 | 0,600 | - |
| LAION-CLAP htsat-unfused (01-10) | ridge trên vector nhúng, kiểm chéo 5 phần | **0,757** | **0,828** | **0,818** | 54,5% (hồi quy logistic, kiểm chéo) |

| LAION larger_clap_music (01-10) | qua transformers | -0,10 | -0,06 | -0,03 | - |

larger_clap_music qua `transformers` HỎNG, không phải model kém: nhúng của các trích đoạn khác nhau gần như trùng (cos 0,98 so với 0,82 ở htsat-unfused) - khớp LAION-AI/CLAP issue #126 (bản HTSAT-base chuyển sang Hugging Face sụt độ chính xác). Phải đo lại bằng thư viện gốc `laion_clap` + checkpoint .pt trước khi kết luận.

Đọc: vector nhúng của CLAP đã MANG thông tin cảm xúc ở mức ngang mốc tham khảo (0,67 / 0,81); cách zero-shot bằng câu mô
tả bỏ phí một phần. Nhưng ridge học và đo trên CÙNG bộ (kiểm chéo theo trích đoạn) - còn phải đo chéo bộ (học trên nhạc
phim, đoán Incompetech / DEAM) trước khi tin.

**Đo CHÉO BỘ (02-10 00:4x) - lật ngược kết luận trên.** Ridge học trên nhạc phim, đoán 635 bài Incompetech, so với
nhãn người gắn ("feel"); AUC = xác suất xếp đúng bài có nhãn lên trên bài không nhãn (0,5 = đoán bừa):

| Nhãn -> trục | ridge (học nhạc phim) | zero-shot |
|---|---|---|
| Somber -> vui/buồn thấp | **0,34 (ngược chiều)** | 0,76 |
| Dark -> vui/buồn thấp | 0,63 | 0,79 |
| Calming -> năng lượng thấp | 0,73 | 0,85 |
| Action -> năng lượng cao | 0,61 | 0,84 |
| Suspenseful -> căng thẳng | 0,76 | - |
| tương quan với toạ độ suy từ nhãn (vui/buồn, năng lượng) | 0,28 / 0,39 | 0,65 / 0,72 |

Đo theo từng đoạn rồi mới lấy trung bình cho đúng y như vậy -> không phải lỗi cách nhúng. Bài học: 470 trích đoạn nhạc
phim quá hẹp để học 512 chiều - ridge học được nét riêng của bộ ấy, không khái quát. Kiểm chéo TRONG một bộ đánh giá quá
cao. Hướng kế: học trên NHIỀU nguồn (DEAM + PMEmo + nhãn Incompetech), luôn đo trên bộ không dùng để học; zero-shot hiện
là ứng viên vững nhất cho kho thật.

**Nhãn GEMS và phong cách zero-shot (02-10 01:0x, 634 bài Incompetech có nhãn người).** Khớp nhãn người (nhãn GEMS mạnh
nhất nằm trong tập suy từ "feel" của bài): thô 74,3%, đoán bừa ~38,6% - nhưng phân bố lệch (một câu mô tả "hút" mọi bài:
"power" 232/634). Hiệu chỉnh từng câu theo cả kho (z-score cột) -> 75,4% và phân bố cân ("power" 85). Phong cách sau hiệu
chỉnh: ambient 145, piano 87, mộc 81, giao hưởng hùng 70, giao hưởng nhẹ 65, trung cổ 59, jazz 42, u tối 33, điện tử 29,
rock 13, **cổ phong phương Đông 11** - thiếu hẳn cho truyện tiên hiệp / Tam quốc: phải tìm thêm nguồn nhạc cổ phương Đông
giấy phép mở trước khi bật nhạc cho các cuốn ấy. Phân loại (11 phong cách, 9 thể loại truyện với bảng tương thích, 9 nhãn
GEMS) ở `LLM_Train/music/taxonomy.py`; khung ở `MUSIC_SELECTION_MODEL.md`.

**Phong cách + nhịp (02-10 01:3x).** CLAP zero-shot (hiệu chỉnh) đúng phong cách 63,8% (3 nhãn đầu 88,8%, đoán bừa ~7%)
trên 260 bài Incompetech có thể loại người gắn; danh mục cộng thêm thể loại / nhạc cụ / feel do người gắn. Bộ phong cách
phải tách: pop / nhảy, hài hước, nhạc thế giới khác (sitar, santur...) khỏi cổ phong Trung Hoa, và bằng chứng NHỊP TRỐNG NỔI
(feel Grooving/Bouncy + drum kit/bass) - thiếu chúng thì "Derp Nugget", "Space 1990" lọt vào truyện kỳ ảo. Sau khi tách, lo18
(thế giới: dị giới phương Tây) ra Crusade, Royal Coupling, Goblin King, Minstrel Guild, Final Battle of the Dark Wizards...;
còn sót "Vadodora Chill Mix", "Zanzibar". Dò nhịp (librosa) so với BPM người nhập của 723 bài: đúng trong 8% 57,8%, kể cả
lệch đôi/nửa 76,2% - đủ cho nhóm nhanh / vừa / chậm, chưa đủ để so BPM chính xác.

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

### Kết quả Pha 2 (02-10, đang chạy - CHƯA ngã ngũ)

**Đáp án cảnh** (`scripts/model_eval/gold_scenes/`, hướng dẫn SCENE_GOLD_GUIDE.md): 7 chương, 4 truyện, 4 thể loại (Tam quốc
050, Tắt đèn 020/021/024, YMP 248, Lucien 351/381). Mỗi chương HAI người chấm độc lập (Claude + một agent chấm mù), phân xử
theo luật cố định. Độ đồng thuận = TRẦN cho máy: lượt 1 Pk 0,15, r V/E/T 0,46/0,73/0,79; lượt 2 (hướng dẫn bản 2) Pk 0,13,
r 0,66/0,79/0,78. Bộ chấm: `LLM_Train/music/eval_scenes.py` (Pk min có/không ranh giới soft, P/R dung sai 20 giây, đoạn/giờ,
r và sai số V/E/T trên từng câu theo thời lượng, và "oracle" = biết đúng ranh giới, chỉ đoán không khí).

| cách | Pk | đoạn/giờ (gold 27,7) | r V / E / T |
|---|---|---|---|
| cả chương một đoạn | 0,238 | 6 | - |
| chỉ ranh giới cứng (tiêu đề, dòng ngăn, nhảy thời gian) | 0,239 | 8 | 0,55 / 0,48 / 0,34 |
| app hiện tại (đổi không khí từ nhãn câu) | 0,239 | 8 - **chưa bao giờ cắt** | như trên |
| cắt đều 3 phút | 0,353 | 21 | 0,50 / 0,53 / 0,40 |
| TextTiling bge-m3 (c = 1) | 0,223 | 22 | 0,50 / 0,56 / 0,39 |
| LLM 9B v2 (chia cả chương) + gộp | 0,248 (4 chương) | 22 | thấp |
| LLM 9B v3 (nhãn từng khối 30 giây) | 0,274 | 27 | **0,62** / 0,34 / **0,48** |

Đọc: (1) nhãn cảm xúc từng câu KHÔNG thấy đổi cảnh trong lời kể (mọi ngưỡng đều kém "chỉ ranh giới cứng") - đổi cảnh nằm ở
bối cảnh / thời gian / hành động, lời kể gần như toàn "trung tính"; (2) chưa cách nào thắng đường cơ sở tầm thường về ranh
giới - TextTiling thắng ở 4 chương đầu (0,18) nhưng mất khi thêm LN (chia vụn); (3) LLM đọc chữ đoán SẮC THÁI tốt hơn nhãn câu
(V, T) nhưng kém về năng lượng, và 9B không suy nghĩ hay sai định dạng (bỏ cột, nhét chữ của trục này sang trục kia) - v1 còn
ĐẢO thang số; (4) LLM chia theo NHỊP truyện (mỗi trận phục kích, mỗi tràng cười một đoạn), đáp án coi đó là điểm nhấn.
Đang thử: chế độ suy nghĩ, model khác, lai (ranh giới cứng + không khí từ LLM).

**Thêm trên bộ phát triển (02-10 sáng):** LAI = ranh giới TextTiling bge-m3 (c = 1) + V, T từ nhãn khối LLM 9B v3 + E từ nhãn
câu: Pk 0,223, r 0,66 / 0,56 / 0,65 (T gần gấp đôi app 0,34). Chế độ suy nghĩ của 9B: không khí ngang (V 0,61, T 0,70), ranh
giới không hơn (0,26), tốn gấp nhiều lần -> không dùng. qwen3:8b v3 Pk 0,208 nhưng chỉ vì hầu như không nói "mới" (8,7 đoạn/giờ);
gemma4-e4b V r ~0 -> loại.

**CHỐT TRƯỚC BỘ KIỂM GIỮ RIÊNG (02-10 07:0x, trước khi có đáp án của 3 chương LN Love Unseen 07, Yamiyo 141, HDST 062):**
cách được kiểm = `moodvt:qwen3.5:9b#v3|tile:bge-m3:1` (eval_scenes.py), so với `hard` và `app`. Không chỉnh tham số sau khi
thấy kết quả trên ba chương ấy.

**KẾT QUẢ BỘ KIỂM GIỮ RIÊNG (02-10 07:0x; 3 chương LN, hai người chấm mù, đồng thuận Pk 0,18, r V/E/T 0,93/0,76/0,89):**

| cách | Pk | P / R ranh giới | đoạn/giờ (gold 29,6) | r V / E / T |
|---|---|---|---|---|
| chỉ ranh giới cứng = app = cả chương | **0,222** | - / 0,00 | 3,6 | 0,43 / 0,42 / 0,29 |
| cắt đều 3 phút + nhãn câu | 0,354 | 0,47 / 0,15 | 21 | 0,76 / 0,44 / 0,58 |
| TextTiling bge-m3 + nhãn câu | 0,306 | **0,56 / 0,38** | 22 | **0,80** / 0,39 / 0,52 |
| ĐÃ CHỐT: TextTiling + V, T từ LLM | 0,306 | 0,56 / 0,38 | 22 | 0,62 / 0,39 / 0,58 |
| (chọn SAU khi xem) TextTiling + trung bình nhãn câu và LLM | 0,306 | 0,56 / 0,38 | 22 | 0,71 / 0,33 / 0,60 |

Đọc thẳng: (1) cách đã chốt KHÔNG thắng Pk - TextTiling thua "không cắt" trên chương mới; lợi thế ở bộ phát triển là chỉnh trên
chính nó. (2) Nhưng Pk phạt cắt lệch nặng hơn "không bao giờ đổi nhạc", trong khi điều người nghe nhận là nhạc HỢP từng lúc: chia
chương ~20 đoạn/giờ nâng r V từ 0,43 lên 0,76-0,80 - phần lớn nhờ CHIA NHỎ (cắt đều 3 phút cũng được 0,76), TextTiling thêm phần
đổi nhạc ĐÚNG lúc đổi cảnh (bắt 38% ranh giới thật so với 15%). (3) Không nguồn không khí nào thắng mọi nơi: LLM thắng ở bộ phát
triển (Tam quốc, Tắt đèn - văn kể nhiều), nhãn câu thắng ở LN nhiều thoại. Trung bình hai nguồn ổn định nhất ở cả hai bộ
(phát triển 0,69/0,58/0,63; kiểm 0,71/0,33/0,60) nhưng được chọn SAU khi thấy bộ kiểm -> cần một bộ kiểm mới trước khi tin.
**Thước chính từ nay:** r và sai số không khí theo thời gian + P/R ranh giới (dung sai 20 giây) + số đoạn/giờ gần gold; Pk là
thước phụ (nó thưởng việc không bao giờ đổi nhạc).

**Model phân tích 9B-v8 (LoRA người nói) làm bộ gắn nhãn cảnh: KHÔNG được** - bộ phát triển T r −0,19 (ngược thang), V 0,29;
tinh chỉnh cho người nói làm hỏng việc khác. Muốn một model cho cả hai thì phải đưa bài toán cảnh vào dữ liệu huấn luyện; hiện
phải dùng model gốc qwen3.5:9b (thêm ~6 GB cho người dùng) hoặc chỉ nhãn câu.

**GHI TRƯỚC cho BỘ KIỂM THỨ HAI (02-10 07:3x, trước khi có đáp án Tam quốc 052, Nageki 62, Two Childhood Friends 060):**
cách chính = `ens:qwen3.5:9b#v3|tile:bge-m3:1` (TextTiling bge-m3 c = 1, không khí = trung bình nhãn câu và nhãn khối LLM);
đối chứng = `tile:bge-m3:1` (chỉ nhãn câu), `moodvt:qwen3.5:9b#v3|tile:bge-m3:1`, `fixed3`, `hard`. Thước chính: r và sai số
V/E/T theo thời gian, P/R ranh giới dung sai 20 giây, đoạn/giờ; Pk phụ. Cách chính thắng nếu r trung bình ba trục hơn
`hard` và `tile:bge-m3:1` mà P ranh giới không thấp hơn `fixed3`.

**KẾT QUẢ BỘ KIỂM THỨ HAI (02-10 08:0x; Tam quốc 052, Nageki 62, Two Childhood Friends 060; đồng thuận Pk 0,21, r
0,63/0,74/0,63) - cách ghi trước THUA:**

| cách | P / R ranh giới | đoạn/giờ (gold 32) | r V / E / T |
|---|---|---|---|
| hard (= app) | 0,50 / 0,09 | 8 | 0,15 / 0,19 / 0,08 |
| **cắt đều 3 phút + nhãn câu** | 0,25 / 0,18 | 23 | **0,39 / 0,26 / 0,50** |
| TextTiling + nhãn câu | 0,14 / 0,18 | 26 | 0,35 / 0,09 / 0,37 |
| ghi trước: TextTiling + trung bình nhãn câu và LLM | 0,14 / 0,18 | 26 | 0,23 / 0,19 / 0,33 |

**Điều đứng vững qua cả ba bộ:** chia chương thành khúc ~2-3 phút làm nhạc bám không khí hơn hẳn một bài cả chương (bộ kiểm 1:
r V 0,43 -> 0,76; bộ kiểm 2: 0,15 -> 0,39; T 0,29 -> 0,58 và 0,08 -> 0,50). TextTiling KHÔNG ổn định (bộ phát triển và bộ kiểm
1 hơn cắt đều về P ranh giới, bộ kiểm 2 kém). LLM chỉ giúp ở truyện văn kể (Tam quốc, Tắt đèn), không giúp ở LN hài. Nhãn cảm
xúc từng câu (app có sẵn, không cần model thêm) là nguồn không khí ổn định nhất.
**Hệ quả cho app (đường cơ sở mới, chưa phải đích):** `music_scenes` hiện KHÔNG BAO GIỜ cắt trong chương (ngưỡng đổi không
khí 0,5 quá cao) -> đổi sang trần độ dài đoạn ~3 phút, không khí từ nhãn câu. Hướng còn mở: chọn CHỖ cắt tốt hơn cắt đều
(ranh giới cứng + đổi không khí cục bộ trong cửa sổ quanh mốc 3 phút), cần bộ kiểm thứ ba (thể loại mới: tiên hiệp, ngôn tình
Việt) trước khi tin.

## Pha 3 - ghép đoạn với nhạc

Ứng viên: (1) gần nhất trên hai trục (đường cơ sở); (2) truy hồi chữ-nhạc: model đọc hiểu viết mô tả nhạc cho đoạn ("tiếng
đàn tranh chậm, buồn, đêm mưa"), CLAP tìm bài gần câu mô tả nhất; (3) kết hợp hai điểm. Thước khi không có người nghe:
độ khớp giữa không khí đoạn (đáp án cảnh) và nhãn người gắn của bài được chọn (Incompetech feel, Film soundtracks); giám
khảo audio-LLM trên mẫu nhỏ, chỉ tin khi nó đồng ý với nhãn người ở các ca đã biết. Trang nghe thử A/B vẫn có, là tuỳ chọn.

### Kết quả Pha 3 đầu tiên (02-10 08:3x, `LLM_Train/music/eval_matching.py`)

Tách riêng khâu CHỌN BÀI: đầu vào = không khí ĐÚNG của 77 đoạn đáp án (16 chương, bỏ đoạn im lặng) + thế giới của cuốn;
mỗi cách chọn 5 bài trong 440 bài Incompetech có nhãn feel; bài được chấm bằng nhãn NGƯỜI gắn (FEEL_VA / FEEL_TENSION) -
cách chọn chỉ thấy số đo CLAP thuần, không thấy nhãn người.

| cách chọn | khoảng cách (thấp = hợp) | r V / E / T |
|---|---|---|
| ngẫu nhiên (trong phong cách hợp thế giới) | 0,861 | 0,01 / -0,05 / -0,17 |
| CLAP gần nhất ba trục (cách của app) | 0,590 | **0,84 / 0,83** / 0,64 |
| nhãn GEMS của CLAP | 0,632 | 0,53 / 0,65 / 0,68 |
| CLAP + GEMS (tổng thứ hạng) | **0,585** | 0,74 / 0,82 / **0,70** |
| trần: gần nhất theo chính nhãn người | 0,255 | 0,94 / 0,95 / 0,94 |

Đọc: khâu chọn bài đã TỐT - CLAP xếp đúng hướng cả ba trục; khoảng cách còn xa trần vì nhãn người thô (vài chữ "feel") và
CLAP chỉ nghe 3 cửa sổ 10 giây. Khâu yếu nhất của cả chuỗi là đoán không khí ĐOẠN từ chữ (Pha 2, r 0,3-0,7), không phải
chọn bài. Việc kế của Pha 3: thử truy hồi chữ-nhạc (mô tả cảnh -> CLAP văn bản -> bài) và cân trục T (GEMS giúp T).

**Pha 3 tiếp (02-10 09:0x):** truy hồi chữ-nhạc - câu mô tả nhạc từ nhãn GEMS + mức V/E/T bằng chữ -> bộ mã hoá văn bản
CLAP -> bài có vector âm thanh gần nhất. Một mình kém (khoảng cách 0,641; r 0,57/0,70/0,63); GHÉP với khớp ba trục (tổng thứ
hạng, `textmix`) tốt nhất: 0,560, r 0,84/0,76/**0,75**. Bootstrap ghép cặp theo đoạn: textmix - clap = −0,031 [−0,063;
+0,001], hơn ở 7/9 cuốn - ỨNG VIÊN, chưa chắc. Đưa vào app KHÔNG cần chở CLAP: danh mục tính sẵn độ khớp của mỗi bài với một
lưới câu mô tả cố định (9 GEMS x 3 V x 3 E x 3 T), app tra theo ô của đoạn.

**Pha 2b - học ánh xạ nhãn câu -> không khí đoạn (eval_scene_mood.py): KHÔNG hơn bảng viết tay.** 77 đoạn / 9 cuốn, ridge
kiểm chéo giữ từng cuốn: tốt nhất r 0,48/0,53/0,43 so với bảng tay 0,51/0,61/0,50 - quá ít dữ liệu để học; giữ bảng tay.

**CẢ CHUỖI (02-10 09:1x):** đầu vào = không khí MÁY ĐOÁN (bảng tay từ nhãn câu, trên ranh giới đáp án; nhãn GEMS = nhãn
gần nhất trên ba trục), chấm bằng nhãn người so với không khí ĐÚNG: ngẫu nhiên 0,861 / clap 0,752 / mix 0,730 / **textmix
0,688** / trần 0,255. Với đầu vào nhiễu, textmix hơn clap rõ hơn (−0,064) so với khi đầu vào đúng (−0,031) - câu mô tả chữ
"cứu" một phần sai số của ba trục. Bootstrap: theo đoạn −0,064 [−0,116; −0,009], nhưng THEO CUỐN [−0,180; +0,017], chỉ hơn 4/9 cuốn.

**BỘ KIỂM THỨ BA cho textmix (02-10 09:5x; ghi trước: thắng nếu độ lệch cả chuỗi thấp hơn clap VÀ hơn >= 3/4 cuốn mới):**
Tam quốc 051, Nise 132, Nageki 65, Love Unseen 10 (32 đoạn) - ngẫu nhiên 0,855 / **clap 0,736** / textmix 0,757 (+0,022, hơn
2/4 cuốn) -> textmix BỊ BÁC; app giữ cách chọn ba trục CLAP. Đáp án bộ này: hai người chấm mù (agent Opus + agent Sonnet),
phân xử TỰ ĐỘNG theo luật (`LLM_Train/music/adjudicate_scenes.py`); đồng thuận Opus-Sonnet Pk 0,185, r 0,91/0,76/0,90 - ngang
các cặp người chấm trước (Pk 0,13-0,21), nên người chấm Sonnet dùng được.

## Pha 4 - trộn

Đo bằng chính dây chuyền: Whisper trên chương có nhạc ở nhiều mức (nền thấp hơn giọng 15 / 18 / 21 / 24 / 27 LU, có / không
hạ khi có giọng), lấy mức to nhất mà WER tăng không quá một ngưỡng nhỏ so với bản không nhạc; kiểm thêm độ to toàn chương
và trần đỉnh như luật cân mức hiện có (AGENTS.md). Thời gian chuyển cảnh, độ dài vào/ra đặt theo cùng phép đo.

### Kết quả Pha 4 (02-10, phiên Music)

**Lỗi có thật trong app:** trình phát (máy tính `musicBed.ts`, Android `MusicBed.kt`) đặt âm lượng nhạc = 10^(levelDb/20)
CỐ ĐỊNH cho mọi bài, không bù độ to riêng của bài. Giọng mọi chương ở −20,3 LUFS (đo 6 chương, 2 cuốn), còn LUFS tích hợp
(BS.1770) của 1.826 bài danh mục mới trải −27,3..−9,5 (p5..p95; Incompetech ước từ 3 đoạn 10 s, hiệu chỉnh trên 150 bài đo
cả bài: lệch +0,71 dB, SD 1,5). Nên khoảng cách độ to giọng − nhạc (LD) người nghe nhận dao động ~10..27 LU tuỳ bài máy
chọn: bài to lấn lời (6% bài dưới 10 LU, 38% dưới 15), bài nhỏ gần như không nghe thấy.

**Người nghe muốn bao nhiêu (nghiên cứu, không cần tự nghe):** Torcoli và cộng sự 2019 (JAES 67(12), 22 người): lời bình
trên NHẠC cần LD tối thiểu ~10 LU, trên tiếng nền 15 LU; người không chuyên thích LD cao hơn chuyên gia ~4 LU; sở thích
từng người rất khác (IQR ~5,7 LU, Torcoli 2023). Người trên 65 tuổi chọn LD lớn hơn bản phát sóng gốc. WCAG G56: nền thấp
hơn lời ít nhất 20 dB. Kinh nghiệm sách nói / podcast: nhạc thấp hơn giọng 18-24 dB.

**Đo khách quan trên giọng thật (`LLM_Train/music/mix_intelligibility.py`):** 6 đoạn 120 s giọng đã xuất bản (2 cuốn,
nhiều nhân vật) trộn với 18 bài rải đều theo độ lấn dải tiếng nói (speechBand 0,03..0,96), LD 0..25 LU; ESTOI (Jensen &
Taal 2016) giữa giọng sạch và bản trộn:

| LD (LU) | 0 | 5 | 10 | 15 | 20 | 25 |
|---|---|---|---|---|---|---|
| ESTOI trung bình | 0,56 | 0,69 | 0,80 | 0,88 | 0,94 | 0,97 |
| ESTOI p10 | 0,43 | 0,56 | 0,69 | 0,81 | 0,89 | 0,94 |

LD cần để ESTOI ≥ 0,9: trung vị 16,9, p90 21,0; bài càng lấn dải tiếng nói càng cần thêm (LD ≈ 12,3 + 8,1 × speechBand,
r 0,48). Luật "LD của bài = LD cuốn + 8 × (speechBand − 0,30)", phần bù kẹp ±6 dB (trung vị danh mục 0,30 -> bù p10..p90 =
−2..+3,9 dB):

| LD cuốn | ESTOI ≥ 0,9 (cố định / có bù) | ESTOI tệ nhất (cố định / có bù) |
|---|---|---|
| 16 | 44% / 57% | 0,75 / 0,83 |
| 18 | 67% / 76% | 0,79 / 0,86 |
| **20** | 82% / **94%** | 0,82 / **0,89** |

**Quyết định:** mặc định LD 20 LU (trùng WCAG, nằm trong 18-24 của sách nói, chừa chỗ cho người không chuyên / lớn tuổi /
nghe nơi ồn) + bù theo speechBand từng bài; người dùng chỉnh mức trong Studio (nghĩa mới của `levelDb` = −LD so với giọng).
Mỗi bài trong danh mục mang `lufs` và `speechBand`. Whisper WER (sàn an toàn, cùng bộ trộn) chờ khe GPU - Whisper chịu nhạc
tốt hơn tai người nên không dùng để chọn mức. Chưa đo: hạ nhạc khi có giọng (sách nói gần như liền giọng, lợi nhỏ), độ dài
chuyển cảnh.

**Danh mục dựng lại (02-10, chưa triển khai):** thêm Freesound (313 ứng viên CC0/CC BY -> 69 bài qua lọc; cổ phong phương
Đông 27 -> 47 bài); bộ lọc mới cho bản thu ngoài trời (thẻ / tên người đăng: field-recording, ambience, street, crowd,
festival... + điểm CLAP "tạp âm" vượt phân vị 99 của Incompetech, `probe_noise.py`) bỏ 58 bài mà bộ lọc "có lời" không bắt
(đàn tranh có tiếng người lao xao, múa lân, phố xá). 1.826 bài (bản triển khai 01:08 có 955 - lúc ấy phân tích chưa xong kho).

**Nguồn và điều khoản - QUYẾT ĐỊNH CỦA CHỦ SÁCH (02-10, đã chốt, đừng hỏi lại):** danh mục công khai giữ CẢ BA nguồn
(Incompetech + Jamendo + Freesound; revision 356f77aa5bcc, 1.826 bài = 1.443 / 314 / 69). Điều khoản đã đọc trước khi quyết:
Freesound API (freesound.org/help/tos_api) mục 4(a) cấm "Distribute, publish, or allow access or linking to ... Content from
any location or source other than your Application", 4(f) cấm "build similar databases"; Jamendo API (sửa 17-09-2013) chỉ
miễn phí phi thương mại, "must not be specifically designed to cache the content nor offering an offline access", phải ghi
Jamendo + "a direct backlink from each Content"; trang Jamendo cấp quyền tải "for private and personal use only"; Openverse
ToS: cấm cào, phải ghi "made using Openverse but is not endorsed". Lý do chủ sách: dùng cá nhân, phi thương mại, mã mở, ghi
công đủ; danh sách của các nguồn vốn công khai, ta chỉ gắn số đo tự làm và không để app gọi API của họ (giảm tải cho họ).
Danh mục ghi công CC BY từng bài + `landing` (trang gốc từng bài) + notice nêu Openverse / Jamendo / Freesound.
Tải nhạc: `link` gốc TRƯỚC; hỏng (mạng / 404 / gỡ bài) mới sang `mirrors` = bản sao archive.org (DỰ PHÒNG, chậm hơn gốc), và
bản sao phải khớp `sha1` (+ `bytes`) của file gốc tải từ `link` - danh mục mang cả hai trường. Bản sao chỉ cho bài có giấy
phép cho phân phối lại (CC0 / CC BY); KHÔNG cho nguồn tự cấm tải lên lại (vd Scott Buckley: "cannot be ... redistributed/
reuploaded ... must be synchronised with other media" - dùng được làm nền đồng bộ trong .abook, không bản sao).

**Một cách đo độ to (02-10, Lead duyệt, app main f25ea91d):** BS.1770 tích hợp, có gating, 48 kHz, cả file, CỘNG HAI KÊNH như
khi phát; file mono tính là dual-mono (= LUFS mono + 3,01). Đo 8 bài Incompetech tải trọn: cách cũ của app ((L+R)/sqrt2 mono)
thấp hơn 0,45..2,83 dB (lệch nhiều khi hai kênh ít tương quan); số danh mục Incompetech ước từ 3 đoạn lệch -1,7..+0,5. Chương
giọng là file MONO cân -20 LUFS -> phát hai kênh = -17 LUFS; mốc LD 20 LU (Pha 4) hiểu theo cách đo này. Incompetech đang được
tải trọn để đo lại cả bài.

**Văn bản cho bộ kiểm cảnh:** docln.sbs (Hako) nay mã hoá nội dung chương (`chapter-c-protected`, `data-s="xor_shuffle"`,
giải bằng JavaScript) - không tải được bằng requests, và giải mã là vượt biện pháp bảo vệ -> không làm; LN Nhật mới cần chủ
sách đưa văn bản.

**Pha 2c - chọn chỗ cắt (dời mốc 3 phút tới chỗ không khí đổi mạnh nhất từ nhãn câu, `snap:W` trong eval_scenes.py): KHÔNG
giúp** trên cả 17 chương (số phát triển - thiết kế sau khi đã thấy mọi đáp án): W 30/60/90 s không hơn chia đều về ranh giới,
r không khí kém hơn. Khớp kết luận cũ: nhãn cảm xúc câu không thấy đổi cảnh. Chia đều trong đoạn (app) và cắt mỗi 180 s từ
đầu chương (fixed3) khác nhau trong mức nhiễu (mỗi bên thắng một số chương).

**GHI TRƯỚC cho BỘ KIỂM THỨ TƯ (02-10 tối, trước khi có phân tích và đáp án; thay bản văn Việt 1930 đã huỷ - chủ sách
gần như chỉ đọc LN Nhật, rồi Hàn, Trung):** Corpus không còn LN Nhật nào chưa dùng, nên Nhật / Hàn lấy chương MỚI của truyện
đã có (luật cắt của app không chỉnh theo truyện, chương chưa thấy vẫn là dữ liệu giữ riêng): Nise Seiken 147 (chương dài
nhất trong 145-157 - mọi chương Nise chỉ ~10 KB), Yamiyo no Hotaru 160, Hướng dẫn sinh tồn trong học viện 090 (Hàn); Trung,
truyện CHƯA dùng: "Đã bảo là cùng nhau tự sát..." 060 (đô thị), "Năng lực bá đạo của tôi trong game tử thần..." 0100 (kinh dị
hệ thống - thể loại mới cho nhạc u tối). Câu hỏi: luật app hiện tại (ranh giới cứng + chia đều đoạn dài hơn 3 phút, không khí
từ nhãn câu) có giữ lợi thế "chia nhỏ" không. So `app` với `hard` (không chia nhỏ) và `fixed3`. App GIỮ nếu r trung bình ba
trục V/E/T của `app` hơn `hard` ít nhất 0,05 VÀ hơn ở >= 7/10 chương (sau khi thêm 5 chương LN Nhật mới dưới đây); `app` so `fixed3` chỉ ghi lại (kỳ vọng ngang). Đáp án:
hai người chấm mù Sonnet + phân xử tự động (`adjudicate_scenes.py`). Tu tiên bỏ (chủ sách đọc ít, không có văn bản).
BỔ SUNG TRƯỚC KHI CÓ ĐÁP ÁN (02-10 trưa): 5 chương LN Nhật MỚI hẳn (chủ sách tự tải - docln nay mã hoá chương, không
tải tự động), chọn bằng luật cố định chỉ đọc dòng tiêu đề - 2 chương truyện đầu tiên từ file 03, 15-60 KB, tiêu đề "Chương"
(truyện mọi chương < 15 KB: 2 chương đầu tiên >= 8 KB): Make Heroine ga Oosugiru 017 (file 018 là lời bạt nên chỉ một
chương), Rokujouma no Shinryakusha 014, 015, Shimotsuki wa Mob ga Suki 029, 032. Tổng bộ 4 = 10 chương. Lưu ý: Hướng dẫn
sinh tồn 090 nằm trong dữ liệu huấn luyện 9B-v8 (nhãn câu có thể đẹp hơn thật) - báo thêm kết quả khi bỏ chương này.
QUY ƯỚC CHẤM (02-10 chiều, khi mới có đáp án 2/10 chương, chưa đọc kết quả): "hơn ở >= 7/10 chương" so r trung bình ba
trục TRONG từng chương; `hard` thường chỉ một đoạn mỗi chương nên dự đoán hằng và r không xác định - tính 0 (không mang
thông tin), cùng quy ước cho mọi cách. Khi bỏ HDST 090 còn 9 chương: cần >= 7/9. Chấm bằng `score_set4.py` (Corpus
research/music).

**KẾT QUẢ BỘ KIỂM 4 (02-10 16:2x; 10 chương, phân tích 9B-v8, hai người chấm mù Sonnet + phân xử tự động; dữ liệu
Corpus research/music/scene_set4):**

| | r V | r E | r T | r tb VET | thắng `hard` | Pk | P / R ranh giới | đoạn/giờ (đáp án 31,7) |
|---|---|---|---|---|---|---|---|---|
| `app` | 0,32 | 0,41 | 0,20 | **0,310** | **7/10** | 0,451 | 0,30 / 0,21 | 21,5 |
| `hard` | 0,31 | 0,22 | 0,23 | 0,253 | - | 0,361 | - / 0 | 3,8 |
| `fixed3` | 0,33 | 0,42 | 0,21 | 0,321 | | 0,452 | 0,19 / 0,12 | 21,5 |
| đúng ranh giới, máy đoán không khí (oracle) | 0,39 | 0,45 | 0,29 | | | | | |
| người chấm A so B (trần) | 0,86 | 0,83 | 0,91 | | | 0,125 | 0,82 / 0,88 | |

- Theo luật ghi trước: **`app` GIỮ** - hơn `hard` +0,057 (ngưỡng 0,05) và thắng đúng 7/10 chương. Đạt SÁT MÉP.
- Kiểm thêm đã ghi trước, bỏ HDST 090 (nằm trong dữ liệu huấn luyện 9B-v8): +0,007, thắng 6/9 - **KHÔNG đạt**. Lợi thế
  của "chia nhỏ" dựa phần lớn vào một chương mà model đã học; trên 9 chương còn lại nó ngang `hard`.
- Lợi thế ở đâu: gần như chỉ trục E (+0,19); V ngang, T kém hơn chút. Ranh giới: `hard` có Pk tốt hơn (ít ranh giới sai);
  `app` chỉ trúng 21% ranh giới bắt buộc.
- `app` so `fixed3` (chỉ ghi lại): ngang trong mức nhiễu (0,310 / 0,321; `fixed3` hơn ở 7/10 chương) - khớp Pha 2c: chia
  theo nhãn câu không thấy đổi cảnh tốt hơn cắt đều mỗi 3 phút.
- Hai người chấm đồng thuận cao (r 0,83-0,91, Pk 0,125) - đáp án đáng tin; khoảng cách tới máy là thật. Ngay cả khi biết
  ĐÚNG ranh giới, đoán không khí từ nhãn câu chỉ đạt r 0,29-0,45: **nút thắt là đoán không khí đoạn, không phải chia đoạn**.
- Quyết định theo luật: giữ luật chia của app (không đổi code). Bằng chứng yếu (đạt sát mép, không bền khi bỏ chương đã
  học). Việc kế có lợi nhất: đoán không khí đoạn tốt hơn (vd LLM đọc cả đoạn, không cộng nhãn câu) - đo trên chính bộ 4 này
  với đáp án đã có, bằng thí nghiệm ghi trước riêng.

**GHI TRƯỚC - "LLM ĐỌC CẢ ĐOẠN ĐOÁN KHÔNG KHÍ" (02-10 16:4x, Lead duyệt; trước mọi lần chạy model):** khác `moodvt` cũ
(nhãn khối 30 giây rồi cộng): mỗi ĐOẠN gửi nguyên văn cho LLM, LLM chấm MỘT bộ V/E/T cho cả đoạn theo đúng thang của người
chấm. Script `segment_mood_llm.py` (Corpus research/music, 24edc4a; prompt nằm trong script, không sửa sau khi chạy).
Model `qwen3.5:9b` gốc (chạy được trên card 8 GB; không dùng LoRA 9B-v8 vì nó ĐẢO thang T khi gắn nhãn cảnh - mục trên),
think=false, temperature 0, ra JSON. Dữ liệu: đáp án bộ 4 (10 chương, đã có). Đoạn LLM trả hỏng định dạng giữ nhãn câu và
báo số lượng.
- CHÍNH: cách chia của app, không khí từ LLM (`app+llm`) so không khí từ nhãn câu (`app`). LLM THẮNG nếu r trung bình V/E/T
  hơn ít nhất 0,05 VÀ hơn ở >= 7/10 chương, VÀ vẫn đúng như vậy khi bỏ HDST 090 (hơn >= 0,05, >= 7/9) - đòi cả hai vì bộ 4
  cho thấy một chương đã học đủ lật kết luận (nhãn câu lấy từ 9B-v8, đã học HDST 090).
- Chỉ ghi lại, không dùng để quyết: `oracle+llm` so `oracle` (ranh giới đáp án - tách lỗi đoán không khí), và `+llmVT`
  (V, T từ LLM, E từ nhãn câu - lần trước LLM kém ở E).
- Thắng thì việc kế là quyết định sản phẩm (model gốc thêm ~6 GB cho người dùng, hay đưa bài toán vào dữ liệu huấn luyện);
  thua thì ghi lại và giữ nhãn câu.

**GHI TRƯỚC - KHÔNG KHÍ LÀ TỈ LỆ GEMS-9 (02-10 21:xx, đề xuất chủ sách qua Lead; trước mọi số):** một điểm V/E/T gộp đoạn
"vừa buồn vừa ấm" về giữa; tỉ lệ trên 9 nhãn GEMS giữ được pha trộn. Bài: phân phối GEMS-9 của CLAP (đã hiệu chỉnh, có sẵn).
Đoạn: LLM chia 100 điểm cho 9 nhãn - lượt gọi RIÊNG trong `segment_mood_llm.py` (cùng hàng GPU với segllm; prompt V/E/T đã
ghi trước KHÔNG đổi). Hai người chấm mù Sonnet cũng chia điểm GEMS trên chính các đoạn đáp án bộ 4 (chỉ thấy ranh giới, không
thấy V/E/T) - để biết LLM gần người tới đâu (Jensen-Shannon) và làm trần `humandist`.
- Đo: `eval_matching_dist.py` (Corpus research/music) - CẢ CHUỖI trên bộ 4, ranh giới đáp án, đầu vào máy đoán; 5 bài / đoạn
  trong phong cách hợp thể loại; bài chấm bằng nhãn NGƯỜI Incompetech như eval_matching (khoảng cách V, E, 0,6 T so đáp án) +
  "trúng GEMS" (feel -> GEMS theo bảng cố định trong script, định nghĩa trước khi có số; đoạn tenderness / nostalgia không
  tính vì không feel nào tương ứng). Thể loại các cuốn bộ 4 cũng định nghĩa trong script trước khi có số.
- ỨNG VIÊN CHÍNH `distmix` (tổng thứ hạng: ba trục CLAP gần V/E/T nhãn câu + Jensen-Shannon giữa phân phối LLM và phân phối
  bài) THẮNG `clap` (cách của app) nếu: khoảng cách thấp hơn, VÀ thấp hơn ở >= 6/8 cuốn, VÀ trúng GEMS không thấp hơn - VÀ
  vẫn đúng khi bỏ HDST 090 (>= 6/7 cuốn). `dist` (chỉ tỉ lệ), `humandist` (tỉ lệ của người - trần nhánh) chỉ ghi lại.
- Kiểm khô với phân phối NGẪU NHIÊN (trước khi có số thật): clap 0,862, distmix 0,863, dist 0,870, ngẫu nhiên 0,922, trần
  0,264 -> luật trả KHÔNG ĐẠT như phải thế; cũng cho thấy trên bộ 4 khâu cả chuỗi của app chỉ hơn ngẫu nhiên một chút (đầu vào
  máy đoán yếu - khớp kết quả bộ 4 ở trên).
- Số của NGƯỜI CHẤM (02-10 22:xx, trước khi có số LLM; chỉ ghi lại, không đổi luật): hai người chấm mù đồng thuận cao về tỉ lệ
  GEMS (Jensen-Shannon A-B 0,032; xáo đoạn 0,266; nhãn đầu trùng 80%, 84 đoạn). Ghép bằng tỉ lệ của người (`humandist`)
  0,691, trúng GEMS 0,73 - so `clap` đầu vào máy 0,862 / 0,53. Đối chứng cùng đầu vào người: ba trục V/E/T của đáp án 0,692,
  ba trục + tỉ lệ (tổng thứ hạng) 0,669. Đọc: tỉ lệ GEMS là cách biểu diễn NGANG ba trục khi đầu vào tốt, ghép cả hai nhỉnh
  hơn; khoảng 0,86 -> 0,69 nằm ở CHẤT LƯỢNG ĐẦU VÀO. Nên câu hỏi thật của lượt LLM sáng mai là: LLM đoán tỉ lệ có gần người
  hơn nhãn câu đoán ba trục không.

**Trọng số ghép GEMS (02-10 23:xx, sau quyết định Lead + chủ sách lấy phân phối GEMS-9 làm biểu diễn chính - code app ở nhánh
`dev/music-gems`, CHỜ bản tổng hợp lý thuyết trước khi gộp):** điểm = khoảng cách V/E/T (như cũ, vẫn quyết ngưỡng im lặng) +
W x Jensen-Shannon(đoạn, bài); đường nhãn câu suy phân phối đoạn từ V/E/T: softmax(-khoảng cách² tới toạ độ nhãn / TAU).
Lưới trên bộ 3 (đầu vào đáp án, 32 đoạn): mọi ô 0,607-0,621, W = 0 (cách cũ) 0,608 - PHẲNG; ô tốt nhất W 2, TAU 0,1 (0,607).
Kiểm cả chuỗi bộ 4 (đầu vào máy, không dùng để chọn): 0,862 -> 0,825, hơn 5/8 cuốn (bỏ HDST: 0,854 -> 0,822, 4/7). Script
`tune_gems_weight.py` (Corpus research/music).

**CLAP với nhạc cụ Đông Á (02-10 23:xx, Lead hỏi vì AudioSet / MTG-Jamendo không có nhãn guzheng / erhu / koto):** bộ kiểm
155 bài nêu ĐÍCH DANH nhạc cụ trong tên / tag (koto 39, taiko 33, erhu 29, guzheng 20, dizi 14, pipa 14, guqin 11, xiao /
shamisen / shakuhachi 6; Freesound 120, OGA 26, Incompetech 8) so 300 bài không có yếu tố Đông Á nào: điểm phong cách
`eastern_ancient` của CLAP tách hai nhóm AUC 0,994; nhãn đầu đúng 77% dương / 1% âm; từng nhạc cụ vượt phân vị 90 của nhóm âm
92-100%. Chú ý: nhóm dương nghiêng về bản thu nhạc cụ đơn (dễ). Kết luận: CLAP NHẬN được nhạc cụ Đông Á; vấn đề là SỐ LƯỢNG
- danh mục thử 2.016 bài chỉ có 67 bài cổ phong (dồn dập 9, buồn 14) - và taxonomy chưa tách Trung / Nhật. Việc kế: tìm nguồn
CC0 / CC-BY nhạc Đông Á.

## Thứ tự và tài nguyên

0. Dữ liệu (đang chạy): Incompetech 1.443 bài (đọc 3 đoạn từ máy chủ), Jamendo CC BY 665 bài; tải Film soundtracks,
   DEAM, PMEmo, GlobalMood (kiểm giấy phép từng bộ - chỉ để đo, không phát hành).
1. Bake-off model nhạc - CPU / hàng GPU nhà ngoài giờ êm; tín dụng Modal khi cần nhiều.
2. Đáp án cảnh: 2-3 chương mỗi thể loại (LN Nhật, tiên hiệp, Tam quốc / Đông Chu, truyện Việt) rồi đo A / B / C.
3. Ghép, 4. trộn - sau khi 1 và 2 có kết quả.

Mỗi pha xong: ghi số vào đây, đổi tham số trong app theo kết quả, nói rõ cái gì đã đo và cái gì còn là đường cơ sở.
