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
Mỗi bài trong danh mục mang `lufs` và `speechBand`.

Whisper WER (sàn an toàn, cùng bộ trộn; 03-10 00:18, `results/pha4_whisper.jsonl`, 216 dòng = 6 giọng × 6 bài × 6 LD).
WER trung vị so bản sạch theo LD:

| LD | 0 | 5 | 10 | 15 | 20 | 25 |
|---|---|---|---|---|---|---|
| WER trung vị | 0,102 | 0,044 | 0,026 | 0,019 | 0,016 | 0,015 |

- Từ 20 LU, WER chạm sàn: mặc định 20 LU an toàn cả theo máy nhận dạng.
- Trung bình bị kéo bởi 11 dòng WER ~0,94 KHÔNG đổi theo LD. Tất cả cùng một mẫu giọng (`lo18_…/00003_726`), với 3 bài.
  Đó là Whisper hỏng trên mẫu ấy (đoán sai ngôn ngữ / ảo giác), không phải nhạc che lời.
- Whisper chịu nhạc tốt hơn tai người nên không dùng để chọn mức; ESTOI (trên) vẫn là thước chính. Chưa đo: hạ nhạc khi có giọng (sách nói gần như liền giọng, lợi nhỏ), độ dài
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

**GHI TRƯỚC - TỈ LỆ CỘNG 1 hay 9 ĐIỂM ĐỘC LẬP (02-10 23:xx, rà soát tâm lý học của Lead: Emotify cho chọn tới 3/9 cảm xúc
mỗi bài, nhãn là tỉ lệ tán thành ĐỘC LẬP; ép cộng 1 làm mất pha trộn):** thêm lượt LLM thứ ba trong `segment_mood_llm.py`
(9 điểm 0-1 độc lập; hai prompt đã ghi trước không đổi) và hai người chấm mù chấm 9 điểm độc lập trên chính 84 đoạn bộ 4.
`compare_gems_reps.py` báo r Pearson theo từng nhãn (trung bình 9 nhãn), JS, BCE, trần = người A so B. CHỈ GHI LẠI - bộ nhãn
còn chờ bản tổng hợp lý thuyết (đề xuất 13 nhãn độc lập + V/E/T có độ trải). Phía bài hiện là softmax trên z-score cột của
CLAP (cộng 1); bản độc lập lấy được bằng sigmoid của chính z-score ấy nếu chốt dùng điểm độc lập.
Kết quả phía người (02-10 23:xx): người chấm A so B - tỉ lệ r 0,938, độc lập r 0,942 (hai cách tin được như nhau); tỉ lệ so
độc lập r 0,856; trung bình 1,5 nhãn >= 0,5 mỗi đoạn.

**GHI TRƯỚC - E1 MÁY CHẤM (02-10 22:xx, Lead: chủ sách KHÔNG chấm; trước mọi lượt chấm):** E1 giữ nguyên bộ đã dựng:
100 đoạn (82 bộ 4, 18 bộ 3) × 6 vai (`app` = music_select main, `vet` = gần V/E/T đáp án nhất, `gems` = nhánh GEMS,
`mid`, `far`, `calm`), 330 lượt cặp (30 lượt lặp). Khoảng cách tới đáp án lúc dựng: vet 0,13 < app 0,73 ≈ gems 0,74 < calm
1,05 ≈ mid 1,06 < far 1,70.
Có ba người chấm máy, không ai được biết vai:
- **J-omni:** Qwen2.5-Omni-7B Q4_K_M (llama.cpp, máy nhà qua hàng GPU) nghe thật 30 giây đầu của hai clip, kèm cả đoạn truyện.
  Câu hỏi: bài nào hợp làm nhạc nền dưới giọng đọc. Mỗi lượt chấm cả hai thứ tự. Điểm là P("1") / (P("1") + P("2")) từ
  logprob, lấy trung bình hai thứ tự. Thiên vị vị trí = P(chọn bài đứng trước) trung bình.
- **J-c1, J-c2:** hai người chấm mù Claude Sonnet, mỗi người một thứ tự xáo riêng. Họ đọc đoạn truyện cùng mô tả giàu của
  từng clip: chú thích do J-omni nghe rồi viết (prompt mô tả riêng, không thấy đoạn truyện); nhãn CLAP về không khí,
  phong cách, nhạc cụ, có lời, nền/nổi; nhịp, mật độ nốt, độ sáng, biên độ, xu hướng, bộ gõ. Mô tả đo trên cùng 30 giây
  (`describe_clips.py`). Họ không thấy tên bài hay nguồn. Kết quả là chọn 1/2 kèm độ chắc 1-5.

Trần đo bằng hai thứ:
(a) Độ ổn định của từng người chấm trên 30 lượt lặp; riêng J-omni thêm độ khớp giữa hai thứ tự trên 300 lượt.
(b) Kappa Cohen giữa từng cặp người chấm trên 300 lượt không lặp.

Một người chấm DÙNG ĐƯỢC khi ổn định ≥ 0,75 và kappa với ít nhất một người khác ≥ 0,20. Phán quyết chung là đa số người
chấm dùng được (hoà thì bỏ lượt).

Câu hỏi, kèm dự đoán ghi trước:
- **H1 (kiểm tỉnh):** vet thắng far ≥ 70% (19 lượt). Không đạt thì máy chấm không bám tín hiệu V/E/T. Khi đó báo cả hai
  khả năng (máy chấm kém, hoặc V/E/T không phải điều quyết định) và không xếp hạng vai.
- **H2:** xếp hạng vai bằng Bradley-Terry, so với thứ tự khoảng cách lúc dựng bằng Spearman. Dự đoán ρ ≥ 0,6.
- **H3:** app so gems trên 50 lượt, báo tỉ lệ thắng kèm KTC 95% Wilson. KTC chứa 0,5 nghĩa là không khác.
- **H4:** độ khớp J-omni với J-c so với độ khớp J-c1 với J-c2. Câu hỏi là mô tả chữ có giữ được điều model nghe thấy không.

Không chọn lại prompt sau khi thấy số. Lỗi định dạng thì chạy lại đúng lượt ấy và đếm riêng.
Các mức trên đều ghi trước. Đây là trần MÁY: nó trả lời "các cách chọn khác nhau tới đâu theo máy nghe" chứ không thay được
tai chủ sách. Chủ sách góp ý khi nào thích thì xếp lên trên mọi thứ.
Chi tiết cách chạy (khi chấm, không đổi luật):
- J-omni đọc logprob qua llama-server (`omni_judge.py`).
- Mô tả giàu của clip ghép thêm chú thích J-omni (`describe_clips.py`, `build_e1_judge_packs.py`).
- Lượt lặp nằm ở gói khác lượt gốc, mỗi gói một người chấm Sonnet riêng.
- Chấm bằng `score_e1.py`.

**KẾT QUẢ E1 MÁY CHẤM (02-10 22:4x, `score_e1.py`, số đầy đủ ở Corpus research/music/results/e1_score.txt):**

Người chấm:
- **J-omni KHÔNG dùng được.** Hai thứ tự chỉ khớp ở 6% lượt; P(chọn bài đứng trước) là 0,66. Qwen2.5-Omni-7B Q4 nghe hai
  clip 30 giây gần như chọn theo vị trí. Kappa với người chấm Claude là 0,16-0,17. Chú thích từng clip của nó vẫn dùng làm
  mô tả.
- **J-c1, J-c2 dùng được:**

| | J-c1 | J-c2 |
|---|---|---|
| Ổn định lượt lặp | 0,80 | 0,87 |
| Kappa giữa hai người | 0,81 (đồng ý 91%) | |

- **Giới hạn phải nhớ:** hai người chấm Claude đọc CÙNG một mô tả, và mô tả có nhãn không khí CLAP. Vai `vet` chọn theo
  V/E/T của danh mục, mà V/E/T này một phần cũng từ CLAP. Vì vậy độ khớp cao và H1/H2 có một phần vòng tròn: chúng nói
  "mô tả bài hợp đoạn tới đâu", chưa phải "nghe hợp tới đâu".

Phán quyết chung (c1 + c2, bỏ lượt hai người khác nhau, còn 272 lượt):
- **Bradley-Terry:** vet +0,59 > calm +0,35 > gems +0,08 > mid −0,10 > app −0,13 > far −0,79.
- **H1 ĐẠT:** vet thắng far 13/17 = 0,76 (KTC 0,53-0,90).
- **H2 vừa chạm mức:** Spearman 0,60 so dự đoán ≥ 0,6.
- **H3 không khác:** app thắng gems 23/45 = 0,51 (KTC 0,37-0,65). Nhánh GEMS không hơn cách cũ, khớp kiểm hồi quy ở
  trên.
- **app thua vet:** 11/43 = 0,26 (KTC 0,15-0,40). Cùng danh mục và cùng bộ lọc mà chọn theo V/E/T ĐÁP ÁN thắng rõ chọn theo
  V/E/T máy đoán. Nút thắt vẫn là ĐOÁN không khí đoạn, như bộ 4.
- **calm đứng thứ hai:** nền êm trung tính thắng far 0,82, ngang mid, hơn app. Đây là bằng chứng máy chấm cho lý thuyết
  §5.6 "không chắc thì êm".
  - Việc kế (ghi trước riêng): ngưỡng "đoạn không chắc thì nền êm" chặt hơn hiện nay. Hiện chỉ kéo về CALM_TARGET khi
    confidence < 0,2.

**GHI TRƯỚC - E1b "NGHE THẬT" TỪNG CLIP (02-10 23:xx, Lead duyệt; trước mọi lượt chấm):**
Cách chấm:
- Mỗi cặp (đoạn, clip) của E1 (600 cặp) được chấm độc lập. Không đưa hai clip cùng lúc, nên không có thiên vị vị trí.
- Model nghe 30 giây đầu kèm cả đoạn truyện, rồi cho điểm hợp 1-7. Điểm là kỳ vọng theo xác suất bảy chữ số (logprob).
- Có hai cách hỏi khác chữ (a, b), mỗi cách chạy một lượt.
- Phán quyết lượt cặp: bài có điểm trung bình (a+b)/2 cao hơn thắng; chênh dưới 0,02 thì bỏ.

Người chấm và luật dùng được:
- **J-omni1** = Qwen2.5-Omni-7B Q4 (`omni_judge.py rate`).
- **J-af3** = Audio Flamingo 3 (NVIDIA, giấy phép NC dùng được), cùng giao thức. Đo VRAM trước; không vừa 8 GB thì chạy Mac.
  - SỬA TRƯỚC KHI CÓ SỐ (02-10 23:xx): dùng **Music Flamingo 2601** (`nvidia/music-flamingo-2601-hf`). Đây là bản NVIDIA
    dựng trên AF3, chuyên hiểu nhạc, cùng giấy phép NC, tải 16,5 GB thay vì 33 GB của AF3. Model nạp 4-bit NF4, riêng bộ
    mã hoá âm thanh giữ bf16 (`mf_rate.py`). Cùng hai cách hỏi, cùng thang 1-7.
- **Độ ổn định:** lượt lặp của E1 cho cùng đầu vào nên tầm thường. Thay vào đó dùng độ khớp phán quyết giữa cách hỏi a và b
  trên 300 lượt.
- **Dùng được** khi ổn định ≥ 0,75 và kappa với phán quyết chung của c1 + c2 (E1) ≥ 0,20.
- Không có người chấm nghe nào dùng được thì mới tính Qwen3-Omni trên Modal (hạn mức miễn phí).

Câu hỏi:
- H1-H4 như E1, tính lại với người chấm nghe dùng được.
- Thêm: phán quyết "nghe" có xếp `calm` thứ hai và `app` dưới `vet` như người chấm đọc mô tả không?

**KẾT QUẢ E1b - J-omni1 (03-10 00:1x, `score_e1.py`, `results/e1_score.txt`):**
- Đã chấm 1.200 điểm clip.
- Ổn định a/b là 0,82, đạt ngưỡng ≥ 0,75.
- Kappa với phán quyết chung của c1 + c2 chỉ 0,044 (253 lượt; đồng ý 52%), dưới ngưỡng 0,20. **KHÔNG dùng được.**
- Omni nghe nhất quán với chính nó, nhưng chọn gần như ngẫu nhiên so với người chấm đọc mô tả. Xếp hạng BT riêng của nó là
  gems > vet > app > mid > far > calm. Nó xếp `calm` cuối, ngược với E1.
- Sửa script trước khi đọc kết luận: bản cũ áp luật dùng được của E1 (kappa với BẤT KỲ người chấm nào). Luật đó cho omni1
  qua nhờ kappa 0,355 với chính Omni bản E1. Nay áp đúng luật E1b đã ghi trước.
- Phán quyết chung vẫn là c1 + c2: vet > calm > gems > mid > app > far.
- **J-mf (Music Flamingo 2601, 03-10 01:19):** ổn định a/b 0,66 (< 0,75), kappa với chung c1 + c2 0,113 (< 0,20) → **KHÔNG
  dùng được**. Xếp hạng BT riêng: gems > vet > app > far > calm > mid.
- **Cả hai người chấm nghe đều trượt. Theo luật, bước kế là Qwen3-Omni.** Modal tháng 10 đã hết nên chạy Kaggle 2×T4 (Lead), khi
  Model xếp lịch.
- **Quan sát (không dùng để quyết):**
  - Hai người chấm nghe độc lập khớp NHAU hơn khớp người đọc: kappa omni1-mf 0,236, so với 0,04-0,11 với c1 / c2.
  - Cả hai cùng xếp `gems` đầu và `calm` gần cuối.
  - Hai cách hiểu: (i) model nghe 7B chưa đủ sức hiểu đoạn truyện tiếng Việt; hoặc (ii) người chấm đọc mô tả có thiên lệch riêng.
    Mô tả có nhãn CLAP, mà CLAP cũng tham gia dựng các vai, nên phán quyết "đọc" có phần vòng tròn (đã nêu ở E1).
  - Qwen3-Omni là phép phân xử. Nếu nó cũng xếp gần hai model nghe, phải ghi trước một phép kiểm vòng tròn của người chấm đọc
    (vd bỏ nhãn CLAP khỏi mô tả) trước khi tiếp tục dùng E1 làm thước.

**GHI TRƯỚC - KIỂM THƯỚC E1 (03-10 01:4x, Lead: làm NGAY, trước Qwen3-Omni; hai phép song song):**

Ký hiệu:
- R_cũ = phán quyết chung c1 + c2 (E1).
- L = phán quyết chung hai model nghe: các lượt omni1 và mf cùng ý.
- Kappa tính trên các lượt không lặp, chỉ những lượt cả hai bên có phán quyết.

**(1) Vòng tròn - người đọc KHÔNG có nhãn CLAP.**
- Mô tả mới mỗi clip chỉ gồm chữ thô và đặc trưng âm học đọc thành lời:
  - tên bài, tác giả, nguồn;
  - tag gốc và mô tả gốc của trang nguồn (`text_meta` / `text_fetch`);
  - âm học `acoustic2` đọc thành lời: nhịp, độ ổn định nhịp, trưởng / thứ, âm vực, độ to, độ sáng, mật độ, độ nghịch tai.
- KHÔNG có nhãn CLAP, xác suất CLAP, chú thích Omni hay số V/E/T dẫn xuất.
- Cùng 330 lượt và cùng đoạn truyện. Gói và khoá mới; người chấm Sonnet n1, n2 theo đúng giao thức E1.
- R_mới = chung n1 + n2.
- **Kết luận:**
  - **"E1 vững"** nếu kappa(R_mới, R_cũ) ≥ 0,40 VÀ kappa(R_mới, L) < 0,20.
  - **"E1 vòng tròn"** nếu kappa(R_mới, R_cũ) < 0,20. Khi đó E1 thôi làm thước chính; R_mới làm thước đọc thay, chờ (2) và
    Qwen3-Omni.
  - Còn lại là "không phân định": giữ cả hai, báo đủ.
- Báo kèm thứ hạng BT của R_mới.

**(2) Ngôn ngữ - model nghe đọc tóm tắt TIẾNG ANH.**
- Tập con cố định: các đoạn E1 ở vị trí chẵn khi xếp theo mã đoạn (~nửa), với mọi clip của các đoạn ấy.
- Tóm tắt tiếng Anh 120-200 từ mỗi đoạn:
  - Do một agent Claude viết MỘT lần, chỉ thấy đoạn truyện, không thấy clip.
  - Nội dung: sự việc, bối cảnh, không khí, nhịp, và tone hài / nghiêm nếu có.
  - Chốt trong file trước khi chạy model.
- Omni-7B và MF chấm lại đúng prompt rate a / b, chỉ thay đoạn tiếng Việt bằng tóm tắt tiếng Anh. Prompt cũng dịch sang tiếng
  Anh, giữ thang 1-7.
- **Kết luận cho mỗi model:**
  - **"ngôn ngữ là rào"** nếu, trên cùng tập con, kappa với R_cũ (và với R_mới nếu (1) đã có) tăng ≥ 0,10 so với bản tiếng Việt
    VÀ đạt ≥ 0,20.
  - Có model qua thì Qwen3-Omni (nếu vẫn chạy) dùng tóm tắt tiếng Anh. Không model nào qua thì ngôn ngữ không phải nguyên nhân
    chính.

Sau cả hai: báo Lead trước khi tốn Kaggle cho Qwen3-Omni.

**KẾT QUẢ (1) VÒNG TRÒN (03-10 04:xx, `score_e1_checks.py`, `results/e1_checks.txt`):**
- Hai người chấm mới n1 / n2 (mô tả không CLAP, `describe_noclap.py`), 330 lượt mỗi người: đồng thuận cao, kappa n1-n2 0,740
  (87%).
- kappa(R_mới, R_cũ) = 0,300 (237 lượt; đồng ý 65%) và kappa(R_mới, L) = 0,120 → theo luật: **KHÔNG PHÂN ĐỊNH**.
- Thứ hạng BT:

| Thước | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| R_cũ (đọc mô tả CÓ CLAP) | vet | calm | gems | mid | app | far |
| R_mới (đọc mô tả KHÔNG CLAP) | gems | calm | app | vet | mid | far |
| L (hai model nghe) | gems | vet | app | far | mid | calm |

- Đọc (không phải luật):
  - `vet` (dựng bằng V/E/T suy từ CLAP) tụt từ hạng 1 xuống hạng 4 khi bỏ chữ CLAP khỏi mô tả. Lợi thế `vet` ở E1 phần lớn
    là vòng tròn.
  - `gems` đứng đầu ở cả hai thước không vòng tròn.
  - `far` gần cuối ở mọi thước.
  - `calm` vẫn hạng 2 với người đọc, nhưng cuối với model nghe. Bất đồng này chưa giải được; chờ phép (2).
- Hệ quả: kết luận E1 "app thua vet" (dùng để định hướng việc đoán V/E/T đoạn) không đứng vững khi bỏ CLAP. Kết luận nào dựa
  trên R_cũ phải được đo lại bằng R_mới trước khi dùng.

**GHI TRƯỚC - ĐO LẠI MỌI QUYẾT ĐỊNH DỰA TRÊN R_CŨ (03-10 04:xx, Lead; KHÔNG đảo quyết định nào trước khi đo lại):**

Quyết định / kết luận đã dựa trên người chấm đọc mô tả CÓ CLAP, và phép đo lại:
1. **E1 H1 / H2 / H3 + "app thua vet" + "calm hạng 2"** (định hướng "nút thắt là đoán không khí đoạn"; mở thí nghiệm nền êm).
   - Đo lại trên dữ liệu đã có: cùng bảng H1-H3 và các cặp phụ, phán quyết = R_mới.
   - Luật giữ nguyên như E1: H1 ≥ 0,70; H3 theo KTC Wilson.
   - Riêng "nút thắt là đoán không khí đoạn" còn có bằng chứng độc lập từ bộ 4 (đáp án cảnh chỉ đọc chữ: oracle r 0,29-0,45 so
     người 0,83-0,91). Kết luận ấy đứng hay đổ theo bộ 4, không theo E1.
2. **H3 "nhánh GEMS không hơn app"** (một lý do không đưa phân phối GEMS / Lớp 2 vào chọn bài).
   - Đo lại: `gems` thắng `app` theo R_mới.
   - Nếu tỉ lệ ≥ 0,60 VÀ cận dưới Wilson > 0,5: ghi trước thí nghiệm "bật lại Lớp 2" trên bộ 5, thước R_mới.
     - Bật lại = `EMOTION_WEIGHT` > 0 với 13 cường độ. Vai `gems` của E1 là GEMS-9 + JS, không phải bản 13 cường độ hiện tại,
       nên không áp thẳng.
     - Không đổi code trước thí nghiệm ấy.
3. **Ngưỡng nền êm giữ 0,2** (52 lượt `calm/`, người chấm đọc mô tả có CLAP + chú thích Omni).
   - Đo lại: hai người chấm Sonnet mới đọc mô tả KHÔNG CLAP (`describe_noclap.py` đã có cả 17 clip nền êm), gói
     `PACK_SET=calm DESC=noclap`.
   - Luật thắng y như cũ (`score_calm.py`). Kết quả lần đo lại là quyết định; nếu khác lần cũ thì theo lần đo lại.
   - Ghi trước "đo lại 0,5 trên bộ 5" SỬA trước khi có dữ liệu: dùng mô tả KHÔNG CLAP.
4. **E1b "omni1 / mf không dùng được"** (luật: kappa với R_cũ ≥ 0,20).
   - Đo lại: kappa với R_mới, cùng ngưỡng 0,20.

Không dính R_cũ (giữ nguyên, không đo lại):
- Kiểm hồi quy Lớp 1-2 / `EMOTION_WEIGHT = 0`: thước là feel do người gắn (Incompetech) so đáp án cảnh chỉ đọc chữ.
  - Mục 2 có thể mở lại câu hỏi bằng thí nghiệm riêng.
- Bộ 4 / segllm / bộ 5: đáp án cảnh do Sonnet đọc chữ truyện, không mô tả nhạc.
- Gộp ba nguồn, thầy, trò: nhãn feel người gắn.
- Độ to 20 LU: ESTOI + Whisper.

**KẾT QUẢ ĐO LẠI mục 1, 2, 4 (03-10 04:xx, dữ liệu có sẵn, `score_e1_checks.py`):**

Mục 1 - E1 theo R_mới:

| Kiểm | R_cũ | R_mới |
|---|---|---|
| H1 vet thắng far | 0,76 ĐẠT | 11/17 = 0,65 [0,41-0,83] KHÔNG ĐẠT |
| H2 Spearman | 0,60 | 0,49 |
| app thắng vet | 0,26 | 21/44 = 0,48 [0,34-0,62] - hết thua |
| calm thắng far | 0,82 | 30/32 = 0,94 [0,80-0,98] |
| calm thắng mid | 0,53 | 21/31 = 0,68 [0,50-0,81] |

- "app thua vet" KHÔNG còn. "nền êm hợp" MẠNH hơn với người đọc không CLAP. Nhưng hai model nghe xếp calm cuối; chờ phép (2).

Mục 2:
- gems thắng app 25/41 = 0,61 [0,46-0,74]. Cận dưới không > 0,5 → **không đạt**, chưa mở thí nghiệm bật lại Lớp 2.
- Đây là ứng viên mạnh nhất cho thí nghiệm kế khi bộ 5 có đáp án.

Mục 4:
- Kappa với R_mới: omni1 0,030, mf 0,150 → cả hai **vẫn không dùng được**. Kết luận E1b không đổi.

Mục 3 - nền êm chấm lại bằng mô tả không CLAP (`DESC=noclap score_calm.py`, `results/calm_noclap.txt`):
- Hai người chấm mới cùng ý 40/52.
- 0,35 thắng 0,2: 5/11 = 0,45 [0,21-0,72]. 0,5 thắng 0,2: 17/29 = 0,59 [0,41-0,74].
- **Giữ WEAK_MOOD = 0,2**, CÙNG kết luận với lần đầu. Quyết định này không dựa vào vòng tròn CLAP.

**KẾT QUẢ (2) NGÔN NGỮ (03-10 03:54, `score_e1_checks.py`):**
- Tập con: 50 đoạn ở vị trí chẵn, 150 lượt không lặp. Tóm tắt tiếng Anh do agent viết một lần (Corpus 1195a41).
- Cả hai model: **NGÔN NGỮ LÀ RÀO**.

| Model | so R_cũ: Việt → Anh | so R_mới: Việt → Anh | Ổn định a/b: Việt → Anh |
|---|---|---|---|
| Omni-7B | −0,02 → **0,23** | 0,00 → **0,26** | 0,87 → **0,81** |
| Music Flamingo | −0,01 → 0,22 | 0,13 → 0,29 | 0,72 → **0,55** |

- Omni-7B đọc tiếng Anh: ổn định ≥ 0,75 và kappa ≥ 0,20 → theo đúng luật E1b là **người chấm nghe DÙNG ĐƯỢC**. Chỉ trên tập con,
  và vừa qua ngưỡng.
- MF đọc tiếng Anh khớp người hơn nhưng không ổn định (0,55) → vẫn không dùng được.
- BT của Omni tiếng Anh: gems > vet > app > mid > calm > far. far vẫn cuối, nhưng calm vẫn dưới mức người đọc xếp.
- Hệ quả:
  - Mọi người chấm nghe về sau nhận đoạn truyện qua tóm tắt tiếng Anh, không nhận nguyên văn tiếng Việt.
  - Qwen3-Omni (nếu chạy) cũng vậy.
  - Omni-7B tiếng Anh có thể làm thước nghe thứ ba bên cạnh R_mới; mở rộng ra mọi đoạn cần ~600 lượt GPU nữa (~40 phút).

**GHI TRƯỚC - THƯỚC NGHE TIẾNG ANH (03-10 04:xx, Lead; trước mọi số của phần mở rộng):**
- **Luật chung:** từ nay mọi người chấm nghe nhận đoạn truyện qua tóm tắt tiếng Anh. Tóm tắt cố định, agent Claude viết một lần,
  chỉ thấy đoạn truyện, lưu ở `e1/en_summaries.json`.
- **(i) Omni-7B-EN mở rộng ra cả 100 đoạn E1:**
  - 50 tóm tắt còn lại (vị trí lẻ) viết cùng prompt; chấm từng clip a / b như trước.
  - DÙNG ĐƯỢC nếu trên cả 300 lượt không lặp: ổn định a/b ≥ 0,75 VÀ kappa với R_mới ≥ 0,20.
  - Báo kèm kappa với R_cũ.
  - Dùng được thì gọi là **L_min**, thước nghe TỐI THIỂU (vừa chạm luật). Mọi kết luận về nhạc báo theo R_mới và L_min.
  - Khi hai thước nghịch nhau thì ghi "bất đồng", không chọn bên.
- **(ii) Qwen3-Omni-30B-A3B-EN trên Kaggle 2×T4:**
  - Model xếp vào ngân sách 30 giờ sau bộ Hàn.
  - Cùng giao thức: 30 giây đầu clip, tóm tắt tiếng Anh, prompt rate a / b, điểm = kỳ vọng xác suất 7 chữ số, nạp 4-bit.
  - Cùng luật dùng được.
  - Dùng được thì thay L_min làm thước nghe chính. Nếu cả hai dùng được: phán quyết nghe chung = lượt hai model cùng ý.

**KẾT QUẢ (i) Omni-7B-EN cả E1 (03-10 04:38):**
- Ổn định a/b 0,809 (278 lượt); kappa với R_mới 0,258 (251 lượt; đồng ý 63%); với R_cũ 0,243.
- → **L_min DÙNG ĐƯỢC.**

Thứ hạng BT (R_cũ có CLAP, không dùng để quyết):

| Thước | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| R_mới (đọc, không CLAP) | gems | calm | app | vet | mid | far |
| L_min (nghe, tóm tắt Anh) | vet | gems | app | calm | mid | far |

So từng cặp (L_min):
- vet thắng far 15/19 = 0,79 [0,57-0,91].
- app thắng vet 19/54 = 0,35 [0,24-0,49].
- gems thắng app 31/56 = 0,55 [0,42-0,68].
- calm thắng far 27/34 = 0,79 [0,63-0,90].
- calm thắng mid 19/36 = 0,53.

Hai thước:
- **Đồng ý:** far cuối, mid gần cuối, gems cao, app giữa, calm thắng far rõ.
- **BẤT ĐỒNG:**
  - `vet`: đọc xếp 4, nghe xếp 1. "app thua vet" đúng theo thước NGHE (0,35, cận trên 0,49), không đúng theo thước ĐỌC (0,48).
  - `calm`: đọc xếp 2, nghe xếp 4.
  - Theo luật: ghi bất đồng, không chọn bên. Qwen3-Omni-EN (Kaggle) là phép phân xử kế.
- Hệ quả tạm:
  - "Nút thắt là đoán không khí đoạn" có thêm bằng chứng từ thước nghe (vet thắng app), cộng bộ 4 / bộ 5 (oracle + LLM 0,607).
  - "Nền êm hợp" chỉ vững ở mức "hơn far / mid".

**KẾT QUẢ (ii) QWEN3-OMNI-30B-A3B-EN (03-10 19:xx, Kaggle 2×T4, `results/qwen3omni_score.txt`): DÙNG ĐƯỢC → thước nghe
chính.**
- Cách chạy:
  - 4-bit AWQ, giải nén mỗi lượt (vá OOM của compressed-tensors 0.11), lô 4, 133 phút cho 1.200 lượt.
  - Kiểm lô trên hai mục khác độ dài: lệch 0,059 (ngưỡng 0,15).
- Số:
  - ổn định a/b **0,906** (287 lượt);
  - kappa với R_mới **0,345** (251 lượt; đồng ý 0,67);
  - với R_cũ 0,511; với L_min 0,418.
  - Mạnh hơn L_min trên cả hai điều kiện (0,809 / 0,258).
- Theo luật: thay L_min làm thước nghe chính. Cả hai dùng được → phán quyết nghe chung = lượt hai model cùng ý (196 lượt).

| Thước | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| R_mới (đọc) | gems | calm | app | vet | mid | far |
| Qwen3-Omni (nghe) | calm | vet | gems | mid | app | far |
| nghe chung (Qwen3-Omni = L_min) | vet | gems | calm | app | mid | far |

Từng cặp, Qwen3-Omni (nghe chung trong ngoặc):
- vet thắng far 17/20 = 0,85 [0,64-0,95] (13/14);
- **gems thắng app 41/59 = 0,69 [0,57-0,80]** (24/33 = 0,73 [0,56-0,85]);
- app thắng vet 16/56 = 0,29 [0,18-0,41] (7/28);
- calm thắng far 33/34 = 0,97; calm thắng mid 25/37 = 0,68 [0,51-0,80]; mid thắng far 24/29 = 0,83.

Phân xử bất đồng của đoạn trên:
- `calm`: Qwen3-Omni xếp 1, đứng về phía thước đọc (2). Bằng chứng "nền êm hợp" mạnh hơn.
- `vet` thắng `app`: Qwen3-Omni đứng về phía L_min (app thắng chỉ 0,29). Thước đọc vẫn 0,48 → còn bất đồng giữa nghe và
  đọc, nhưng hai thước nghe nay cùng ý.
- **Mục 2 (gems so app):**
  - Theo thước nghe chính, gems thắng app 0,69 với cận dưới 0,57. Đạt đúng tiêu chí M2: ≥ 0,60 và cận dưới > 0,5.
  - Theo R_mới thì không (0,61 [0,46-0,74]). Ghi BẤT ĐỒNG, không chọn bên.
  - Đây là ứng viên mạnh nhất cho thí nghiệm "bật lại Lớp 2". Nhắc lại: Lớp 2 cần 13 cường độ của đoạn từ LLM, mà đường LLM
    trượt ở bộ 5B. Mở lại phải ghi trước riêng, Lead / chủ sách quyết.
- Qwen3-Omni 30B không chạy được trên máy người dùng. Nó chỉ là THƯỚC đo, không phải tính năng.


**GHI TRƯỚC - NỚI NGƯỠNG NỀN ÊM (02-10 23:xx, Lead duyệt; từ E1: calm đứng thứ hai, hơn app):**
- **Giả thuyết:** kéo về nền êm (CALM_TARGET) cho nhiều đoạn hơn làm nhạc hợp hơn. Hiện chỉ kéo khi confidence < WEAK_MOOD
  0,2, và kéo tuyến tính.
- **Cách làm:** thử WEAK_MOOD 0,2 (hiện tại) / 0,35 / 0,5 trên chương thật của bộ 3 và bộ 4, mỗi bản tự chia đoạn, cùng danh
  mục và cùng bảng phong cách (`compare_rankers.py`). Cặp so sánh là những đoạn mà hai ngưỡng chọn KHÁC bài (0,2 so 0,35;
  0,2 so 0,5).
- **Thước chính:** hai người chấm mù Claude theo giao thức E1. Họ đọc đoạn truyện cùng mô tả giàu của clip 30 giây, clip
  −23 LUFS, gồm số đo, CLAP và chú thích J-omni. Dựng thêm clip cho bài mới. Phán quyết chung lấy đa số của hai người.
- **Thước phụ:** khoảng cách nhãn người tới đáp án như kiểm hồi quy ở trên.
- **Cỡ mẫu:** mọi đoạn khác bài. Có dưới 20 đoạn thì thêm chương bộ 2 / bộ dev đã có đáp án.
- **Luật thắng:** ngưỡng mới THẮNG nếu bài của nó thắng ≥ 60% số đoạn khác bài theo phán quyết chung, cận dưới KTC 95%
  Wilson > 0,5, và thước phụ không kém quá 0,02. Nhiều ngưỡng cùng thắng thì chọn ngưỡng nhỏ nhất đạt luật (đổi ít nhất).
  Không ngưỡng nào thắng thì giữ 0,2.

**KẾT QUẢ NỚI NGƯỠNG NỀN ÊM (03-10, `score_calm.py`, chấm ngày 03-10):**
- 52 lượt (đoạn khác bài, bộ 3 + 4 + các bộ có đáp án), 17 clip mới có chú thích J-omni. Hai người chấm mù Sonnet cùng ý
  45/52 (87%); độ tin cậy 1: 8 và 4 lượt.
- 0,35 so 0,2: thắng 6/14 = 0,43 [KTC95 0,21-0,67], thước phụ +0,015 → không thắng.
- 0,5 so 0,2: thắng 19/31 = 0,61 [KTC95 0,44-0,76], thước phụ +0,020 → không thắng (đạt 60% nhưng cận dưới < 0,5; thước phụ
  vừa chạm trần 0,02).
- **QUYẾT: giữ WEAK_MOOD = 0,2.** Nghiêng về 0,5 nhưng chưa đủ bằng chứng; nếu sau này có bộ cảnh lớn hơn (bộ 5) thì đo lại
  0,5 một lần, ghi trước, không gộp mẫu cũ.
- **GHI TRƯỚC - ĐO LẠI 0,5 TRÊN BỘ 5 (03-10 00:0x, Lead duyệt):**
  - Chỉ so 0,5 với 0,2, trên các chương bộ 5 (cả 5b nếu đã có trước lượt chấm). Dùng phân tích 9B-v8 của bộ 5, cùng danh mục
    `catalog_e4test`.
  - Giao thức như trên: `compare_rankers.py` + `build_calm.py` + hai người chấm mù Sonnet + `score_calm.py`.
  - Luật thắng giữ nguyên: ≥ 60%, cận dưới Wilson > 0,5, thước phụ ≤ 0,02 (đáp án cảnh bộ 5).
  - Không gộp 31 lượt cũ.
  - Thắng thì đổi `WEAK_MOOD` = 0,5 trên nhánh dev, Lead gộp.
- **KẾT QUẢ ĐO LẠI 0,5 TRÊN BỘ 5 (03-10 05:4x):** **giữ 0,2**, lần thứ ba.
  - Chạy: 9 chương bộ 5, 5b chưa có. `GOLD_SETS=set5`, `CALM_SET=calm5`.
  - Người đọc: không CLAP (n1, n2), theo bổ sung về mô tả.
  - Thể loại cuốn: chốt trước khi chọn bài (`compare_rankers.BOOK_GENRE`).
    - Dị giới: western_fantasy.
    - CotE: modern.
    - Otonari: romance.
  - Cùng bài ở 46/66 đoạn.
  - 20 đoạn khác bài; cả hai người cùng ý 10. 0,5 thắng 4/10 = 0,40 (KTC 0,17–0,69).
  - Thước phụ: khoảng cách nhãn người tới đáp án 0,720 ở 0,2, 0,751 ở 0,5, tức +0,031 (mốc ≤ 0,02).
  - Hỏng cả hai điều kiện.

**GHI TRƯỚC - PHÍA BÀI GỘP BA NGUỒN: CLAP + ÂM HỌC + VĂN BẢN (02-10 23:xx, Lead + chủ sách; trước mọi số):**
Ba nguồn:
- **(A) CLAP:** vector 512 chiều đã lưu (đầu dò như trên).
- **(B) Âm học đo trực tiếp:** `acoustic_features2.py`, khoảng 50 đặc trưng kinh điển (Juslin & Lindström, MIRtoolbox): nhịp
  + độ ổn định, trưởng / thứ + độ rõ giọng, âm vực + tầm, độ nghịch tai, articulation, độ to + đường bao, âm sắc MFCC, độ
  phức tạp hoà âm, mật độ. Trung bình ba cửa sổ 30 giây.
- **(C) Văn bản:** `collect_text_meta.py`.
  - Chữ gồm tên, tác giả, mô tả, tag, nhạc cụ, bình luận / ghi chú trang gốc, album FMA.
  - Một người đọc Claude (Sonnet, theo lô) đọc toàn bộ chữ của từng bài, cho 13 cường độ + V/E/T + độ tin cậy (theo lượng
    và độ rõ của chữ).
  - Feel người gắn của Incompetech là NHÃN đo, không bao giờ vào chữ.

Đo trên 1.381 bài Incompetech có feel:
- 10 lớp ánh xạ được (bảng `FEEL` của `derive_emotions.py`), AUC kiểm chéo 5 phần (StratifiedKFold, seed 7, chia theo bài),
  dự đoán ngoài phần học.
- Mỗi tổ hợp nguồn là MỘT hồi quy logistic L2 (C = 1, đặc trưng chuẩn hoá z) trên khối đặc trưng nối lại. A = 512 chiều;
  B = các đặc trưng âm học; C = 16 số của người đọc (13 + V/E/T + độ tin cậy). Riêng C còn báo AUC của chính cường độ lớp ấy,
  không học.
- Tổ hợp: A, B, C, A+B, A+C, A+B+C.

Luật GIỮ một nguồn:
- Thêm nguồn ấy vào tổ hợp tốt nhất chưa có nó làm AUC trung bình 10 lớp tăng ≥ 0,01 VÀ thắng ≥ 6/10 lớp.
- Thắng thì danh mục dùng tổ hợp ấy. Ba lớp không có nhãn (tenderness / nostalgia / moved) lấy từ người đọc chữ nếu C được giữ,
  không thì giữ zero-shot.

Thước phụ ghi trước: phán quyết máy chấm kiểu E1. Chọn bài bằng phía bài gộp so với phía bài chỉ CLAP, trên các đoạn bộ 3 + 4
chọn khác bài; luật thắng như thí nghiệm nền êm.

Giới hạn: chỉ Incompetech có nhãn người. Nguồn khác chữ ít hơn nhiều (OGA / FreePD / Scott Buckley trung vị 4-10 chữ), nên độ tin
cậy của C phải hạ trọng số khi gộp ở các nguồn ấy; điều này chưa đo được ở đây.

**KẾT QUẢ SEGLLM - LLM ĐỌC CẢ ĐOẠN (02-10 23:20, qwen3.5:9b, bộ 4; `results/segllm_*.txt`; chấm theo các luật ghi trước):**

r trung bình V/E/T theo chương:

| Cách | Đủ 10 chương | Bỏ HDST (9) | Ghi chú |
|---|---|---|---|
| app (nhãn câu) | 0,310 (V 0,32 / E 0,41 / T 0,20) | 0,276 | |
| app+llm | 0,330 (V 0,29 / E 0,17 / T 0,53) | 0,345 | |
| app+llmVT (THĂM DÒ) | 0,410 | 0,402 | LLM cho V/T, nhãn câu cho E |
| oracle | 0,378 | 0,346 | |
| oracle+llm | 0,509 | 0,512 | |

- **Luật CHÍNH KHÔNG ĐẠT:** đủ bộ +0,020, thắng 9/10; bỏ HDST thì +0,069, thắng 9/9; luật đòi cả hai.
- **Luật phụ ĐẠT:** oracle+llm so oracle +0,131, thắng 9/10.
- **LLM khác hẳn theo trục:** độ CĂNG T 0,20 → 0,53 (rất mạnh), NĂNG LƯỢNG E 0,41 → 0,17 (kém). Khớp với lý thuyết: LLM 8-9B chấm
  energy kém (r ≈ 0,2).
- Tổ hợp V/T của LLM + E của nhãn câu (+0,10) chỉ là thăm dò sau khi thấy số. Phải ghi trước rồi đo trên đoạn MỚI.

Ghép theo GEMS (`segllm_matching.txt`):
- [CHÍNH] distmix so clap: −0,035, hơn 5/8 cuốn, KHÔNG ĐẠT.
- [phụ] dist: −0,066, hơn 6/8, ĐẠT trên đủ bộ; bỏ HDST thì 5/7, KHÔNG ĐẠT.
- JS LLM-người 0,138 (người A-B 0,032).

Biểu diễn (`segllm_gems_reps.txt`):
- LLM 9 cường độ ĐỘC LẬP khớp người r 0,705, dạng tỉ lệ r 0,605 (trần người 0,94). Ủng hộ Lớp 2 độc lập.
- Nhưng LLM gắn 2,86 nhãn ≥ 0,5 mỗi đoạn, người chỉ 1,48. Cần hiệu chỉnh ngưỡng / độ nhọn trước khi dùng cho cosine Lớp 2.

**GHI TRƯỚC - BỘ KIỂM 5: KHÔNG KHÍ ĐOẠN TRÊN CHƯƠNG MỚI (02-10 23:4x, Lead duyệt (a)(b)(c); trước khi chọn chương, trước
mọi phân tích / đáp án / số):**

Chọn chương. Luật cố định, chỉ đọc tên file, cỡ file và dòng đầu; chạy bằng script, không đọc nội dung trước khi chọn.
- **Truyện:**
  - LN Nhật trong bộ tải mới của chủ sách: thư mục `Tools/Text_Tmp <tên>` tạo từ 02-10 22:00, chưa có chương nào trong bộ
    nhạc 1-4.
  - Theo tên đã thấy: Re Zero, Kumo Desu ga, Otonari no Tenshi, Mushoku Tensei, Overlord, Kage no Jitsuryokusha, Maou Gakuin,
    Arafoo Kenja, Classroom of the Elite, Kuma Kuma Kuma Bear.
  - Truyện Hàn cùng điều kiện: hiện có Childhood Friend of the Zenith.
  - Trung không lấy: chủ sách gần như không đọc.
  - Danh sách chốt lúc chạy script chọn, sau khi các lượt tải đã xong.
- **Số chương:** mỗi truyện Nhật 1 chương, mỗi truyện Hàn 2 chương (trọng số Nhật + Hàn).
  - Truyện Hàn về SAU lúc chốt thành bộ 5b, có báo cáo riêng.
  - Bộ 5b không bao giờ gộp vào số của bộ 5 sau khi bộ 5 đã có số.
- **Chương trong truyện** (luật bộ 4 mở rộng): xếp file theo tên, bắt đầu từ vị trí 25% danh sách, lấy file đầu tiên (Hàn: hai
  file đầu tiên) thoả cả bốn điều kiện:
  - cỡ 15-60 KB;
  - dòng đầu không chứa Lời bạt / Minh hoạ / Lời tác giả / Mục lục / Phụ lục / Tái bút / Thông báo;
  - số chương không cách quá ±1 so với chương nào của truyện ấy trong `Corpus/<truyện>/` (đáp án thoại của Model; so cả hậu
    tố a/b);
  - không có trong danh sách chương Model báo đang dùng.
- Danh sách chương chọn được gửi Model để họ tránh khi làm đáp án thoại sau này: hai bộ đáp án không dính nhau.

Máy và đáp án:
- **Phân tích:** 9B-v8 như bộ 4, qua hàng GPU của Model. Dừng giữa pha phân tích thì làm lại project mới (AGENTS.md).
- **Đáp án cảnh:** hai người chấm mù Sonnet theo SCENE_GOLD_GUIDE như bộ 4 (V/E/T, ranh giới, gems), cộng `adjudicate_scenes.py`.
  - THÊM: mỗi người chấm cho 13 cường độ độc lập 0-1 mỗi đoạn (danh sách Lớp 2).
  - Người chấm chỉ thấy `seq<TAB>chữ`.
- **Chấm:** r theo chương rồi lấy trung bình, quy ước r không xác định = 0 như bộ 4. Thắng ở X/N chương = so r trung bình các
  trục liên quan trong từng chương.

**(a) llmVT - V, T từ LLM đọc cả đoạn, E từ nhãn câu** (thăm dò ở bộ 4 cho +0,10).
- Prompt `segment_mood_llm.py` giữ nguyên, `qwen3.5:9b` gốc, think=false, temperature 0.
- CHÍNH: `app+llmVT` so `app`, r trung bình V/E/T, ranh giới của app. THẮNG nếu hơn ≥ 0,05 VÀ hơn ở ≥ 70% số chương (làm
  tròn lên).
- Ghi lại, không dùng để quyết: `app+llm` (cả ba trục từ LLM) và `oracle+llmVT`.

**(b) Hiệu chỉnh Lớp 2 - độ nhọn 13 cường độ của LLM.**
- LLM (cùng model, lượt gọi riêng, prompt 13 cường độ chốt trong script trước khi chạy) cho 13 cường độ mỗi đoạn trên ranh
  giới đáp án.
- Hiệu chỉnh: mỗi lớp một hàm mũ p^γ_c, γ_c chọn trong {0,5 … 4} (bước 0,25) để số đoạn ≥ 0,5 khớp người.
  - Học bằng kiểm chéo 2 phần theo TRUYỆN, chia cố định theo thứ tự tên: nửa đầu học, nửa sau đo, rồi đổi.
- CHÍNH: cosine 13 chiều LLM-người trung bình mỗi đoạn, trên phần đo (ngoài phần học).
  - Hiệu chỉnh THẮNG nếu cosine hơn ≥ 0,03 VÀ số nhãn ≥ 0,5 mỗi đoạn lệch người ≤ 30%.
- Ghi lại: r theo từng lớp, JS.
- Thắng thì γ học trên cả bộ 5 vào `music_scenes`. Bật lại `EMOTION_WEIGHT` > 0 là thí nghiệm ghi trước riêng sau đó.

**(c) E bằng SO SÁNH trong chương (MUSIC_THEORY §4.2)** - LLM 8-9B chấm thẳng energy kém (bộ 4: r E 0,17).
- Mỗi chương: Best-Worst Scaling nhóm 4 đoạn (ranh giới của app). Mỗi đoạn xuất hiện trong 6 nhóm; thiết kế ngẫu nhiên cân
  bằng, hạt giống 7, chốt trong script.
- LLM được hỏi: đoạn nào năng lượng / độ kích động CAO nhất và THẤP nhất. Định nghĩa E lấy đúng câu của SCENE_GOLD_GUIDE.
- Điểm = Bradley-Terry trên các cặp suy ra (đoạn "cao nhất" hơn 3 đoạn kia; 3 đoạn kia hơn đoạn "thấp nhất"), rồi đưa về
  z trong chương.
- Chương ít hơn 4 đoạn: dùng cặp đủ mọi tổ hợp.
- CHÍNH: r của E so đáp án, `app+bwsE` so `app` (E nhãn câu). THẮNG nếu r E hơn ≥ 0,05 VÀ hơn ở ≥ 70% chương.
- Ghi lại: `oracle+bwsE` và tổ hợp cuối `app + llmVT + bwsE` (r trung bình V/E/T).

**KẾT QUẢ BỘ 5 - LLM (03-10 04:28, qwen3.5:9b, `set5_llm.py`, `results/set5_score.txt`; 0 lượt hỏng định dạng):**

r trung bình theo chương:

| Cách | V | E | T | VET |
|---|---|---|---|---|
| app (nhãn câu) | 0,389 | 0,319 | 0,260 | 0,323 |
| app + llmVT | 0,358 | 0,319 | 0,350 | 0,343 |
| app + bwsE | 0,389 | 0,394 | 0,260 | 0,348 |
| app + llmVT + bwsE | 0,358 | 0,394 | 0,350 | 0,367 |
| oracle | 0,417 | 0,429 | 0,250 | 0,365 |
| oracle + llmVT + bwsE | 0,671 | 0,562 | 0,589 | **0,607** |

- **(a) KHÔNG THẮNG:** app + llmVT hơn app +0,020, thắng 6/9 (cần +0,05 và 7/9).
- **(c) KHÔNG THẮNG:** E từ BWS hơn +0,075 nhưng chỉ thắng 5/9 chương (cần 7/9).
- **(b) THẮNG (sát mép):**
  - Kiểm chéo 2 phần theo truyện: cosine 13 chiều 0,740 → 0,771 (+0,031, ngưỡng 0,03).
  - Số nhãn ≥ 0,5 mỗi đoạn: người 1,38, LLM thô 3,99, sau hiệu chỉnh 1,59 (lệch 15%, ngưỡng 30%).
  - γ học trên cả bộ (80 đoạn), theo đúng luật:
    - peacefulness 3,25; tenderness 3,25; nostalgia 2,5; sadness 2,5; joy 2,0; playful 1,25; power 3,25;
    - wonder 3,25; tension 1,5; fear 2,0; anger 1,5; mystery 2,0; moved 3,25.
  - Chỉ có tác dụng khi đoạn lấy 13 cường độ từ LLM. App hiện lấy từ nhãn câu, nên KHÔNG đổi code bây giờ. Bật lại Lớp 2 là
    thí nghiệm ghi trước riêng.
- **Đọc (không phải luật):**
  - Trên ranh giới ĐÁP ÁN, LLM (V/T cả đoạn + E so sánh) đạt 0,607 so với oracle nhãn câu 0,365. Không khí đoạn mà LLM đọc
    là tốt.
  - Đường LLM thua ở app vì ranh giới của app sai (Pk 0,40). Nút thắt kế tiếp của đường LLM là CHIA ĐOẠN, không phải đoán
    không khí.
  - Gợi ý thí nghiệm kế (cần ghi trước): LLM chia đoạn, hoặc chia theo thay đổi V/E/T của LLM trên cửa sổ trượt, rồi dùng
    llmVT + bwsE.

**GHI TRƯỚC - CHIA ĐOẠN CHO ĐƯỜNG LLM (03-10 05:xx, Lead duyệt; trước mọi số):**

Câu hỏi: ranh giới tốt hơn có đưa đường LLM (llmVT + bwsE) vượt nhãn câu của app không? Nếu có, nhánh nào đáng chi phí?

Ba nhánh chia đoạn:
- **(1) LLM chia trực tiếp:**
  - qwen3.5:9b đọc cả chương (`seq<TAB>câu`; chương dài hơn 6.000 tiếng thì chia hai nửa chồng 300 tiếng).
  - Trả danh sách seq mở đầu đoạn theo luật SCENE_GOLD_GUIDE (đoạn ≥ ~1 phút, đổi LOẠI không khí mới cắt).
  - Prompt chốt trong script, không chỉnh.
- **(2) Điểm đổi trên V/E/T của LLM:**
  - Cửa sổ trượt W tiếng, bước W/2. LLM chấm V/E/T mỗi cửa sổ, prompt `segment_mood_llm.PROMPT` không đổi.
  - Cắt ở chỗ khoảng cách V/E/T giữa hai nửa kề vượt ngưỡng θ, đoạn tối thiểu 200 tiếng.
- **(3) Nền rẻ, nhúng câu kiểu TextTiling:**
  - qwen3-embedding:0.6b (nhúng câu qua Ollama). Khối k câu, cắt ở chỗ "độ sâu" tương đồng vượt ngưỡng c, đoạn tối thiểu 200 tiếng.

Tham số:
- W, θ (nhánh 2) và k, c (nhánh 3) chọn trên **bộ 4** (10 chương, đáp án có sẵn) để Pk nhỏ nhất.
- Nhánh 1 không có tham số. Nó vẫn chạy trên bộ 4 để báo cáo.
- **Bộ 5 chỉ đo MỘT lần** với tham số đã chốt.

Không khí mỗi đoạn của mọi nhánh = llmVT + bwsE (như `set5_llm.py`: V / T từ LLM đọc cả đoạn, E từ BWS nhóm 4 trong chương).

Thước trên bộ 5:
- **CHÍNH:** r VET trung bình theo chương, so `app` (nhãn câu + ranh giới app).
- **Luật như (a):** nhánh THẮNG nếu hơn ≥ 0,05 VÀ thắng ≥ 7/9 chương.
- **Phụ (báo, không quyết):** Pk và WindowDiff so ranh giới đáp án; đoạn / giờ; số lượt gọi LLM mỗi chương.
- **Nhiều nhánh cùng thắng:** chọn nhánh RẺ nhất (3 < 2 < 1). Nhánh đắt hơn chỉ được chọn nếu hơn nhánh rẻ ≥ 0,03 r VET.
- **Không nhánh nào thắng:** ghi lại và giữ nhãn câu.
- **Chi tiết chốt trong script trước lượt chạy đầu** (`split_experiment.py`, Corpus f91231b):
  - **Nhánh 2:**
    - Ranh giới ở câu đầu cửa sổ m. Điểm = khoảng cách TB V/E/T của cửa sổ m−3, m−2 với m, m+1.
    - Cửa sổ cuối nuốt phần đuôi.
  - **Đoạn tối thiểu 200 tiếng áp cả đoạn cuối:**
    - Nhánh 1 gộp ngược.
    - Nhánh 2 / 3 cắt tham lam theo điểm giảm dần.
  - **Nhánh 1:**
    - Chương LLM trả hỏng thì dùng ranh giới app (có báo số).
    - Vùng chồng: bỏ đầu đoạn cách đầu trước ≤ 150 tiếng.
  - **Nhánh 3:**
    - Viết mới theo Hearst: khối k câu, độ sâu tuyệt đối ≥ c, không giữ ranh giới cứng.
    - `tile_scenes` cũ dùng khối theo giây nên không khớp ghi trước.
  - **Pk / WindowDiff:** k = max(2, round(độ dài đoạn đáp án TB / 2)); chọn tham số theo Pk TB theo chương; hoà thì θ / c lớn hơn.
  - **Chống đo lần hai:**
    - `tune` không ghi đè tham số đã chốt.
    - `score` từ chối chạy lại khi đã có `split_score.txt`.

**KẾT QUẢ CHIA ĐOẠN (03-10 10:10, `results/split_score.txt`, `results/split_params.json`):** **không nhánh nào thắng → giữ
nhãn câu (app).**
- Lần chạy đầu hỏng 09:06 vì Ollama nhà chưa có qwen3-embedding:0.6b. Đã kéo model rồi chạy lại; nhánh 1 / 2 dùng cache, không
  đo lại gì.
- Tham số chốt trên bộ 4 (theo Pk TB): nhánh 2 W = 120, θ = 1,5 (Pk 0,382); nhánh 3 k = 8, c = 0,2 (Pk 0,348).
  Nhánh 1 trên bộ 4: Pk 0,389.
- Bộ 5 đo MỘT lần (9 chương, 3,01 giờ):

| Cách | V | E | T | r VET | hơn app | thắng |
|---|---|---|---|---|---|---|
| app (nhãn câu + ranh giới app) | 0,389 | 0,319 | 0,260 | 0,323 | | |
| (1) LLM chia trực tiếp | 0,385 | 0,322 | 0,415 | 0,374 | +0,052 | 5/9 |
| (2) điểm đổi V/E/T | 0,404 | 0,330 | 0,353 | 0,363 | +0,040 | 5/9 |
| (3) TextTiling | 0,517 | 0,257 | 0,304 | 0,359 | +0,037 | 5/9 |
| tham chiếu: ranh giới app + llmVT + bwsE | 0,358 | 0,394 | 0,350 | 0,367 | | |
| tham chiếu: ranh giới đáp án + llmVT + bwsE | 0,671 | 0,562 | 0,589 | 0,607 | | |

- Thước phụ (so ranh giới đáp án): Pk app 0,402; (1) 0,307; (2) 0,330; (3) 0,292.
  - Số đoạn mỗi giờ: app 21,9; (1) 19,9; (2) 17,6; (3) 15,9. Đáp án 26,6.
  - Lượt LLM mỗi chương: (1) 18,1; (2) 80,8; (3) 13,2 + 3,6 lô nhúng.
  - Không chương / đoạn nào hỏng định dạng.

Đọc kết quả:
- Ba nhánh khớp ranh giới tốt hơn app rõ (Pk 0,29–0,33 so 0,40), nhưng r VET không hơn ranh giới app khi cùng dùng đường LLM
  (0,36–0,37 so 0,367).
- Phần hơn app (+0,04–0,05) đến từ đường đoán không khí (llmVT + bwsE), không phải từ ranh giới.
- Trần khi có ranh giới đáp án là 0,607. Khoảng cách tới đó nằm ở chỗ khớp ranh giới THẬT (Pk 0,29 vẫn xa trần người
  chấm 0,167), không phải ở chỗ tốt hơn app một chút.
- Từng chương dao động mạnh, ví dụ Kage 33: app 0,145, (1) 0,756. Chín chương còn ít để thấy nhánh nào ổn định.
- Bộ 5b (3 chương) không đo lại phép này: luật là đo bộ 5 một lần.
- Lead: câu "phần hơn đến từ cách đoán không khí, không phải ranh giới" là giả thuyết MỚI, rút ra SAU khi nhìn số bộ 5.
  Chưa được nhận; phải đo trên bộ mới (ghi trước dưới đây).

**GHI TRƯỚC - BỘ 5B: MỘT ỨNG VIÊN DUY NHẤT `app + llmVT + bwsE` (03-10 10:3x, Lead giao; trước khi có phân tích 5b):**
- Bộ 5b:
  - chương: Kuma 112, Zenith 049 + 050 (`scene_set5b.json`, Corpus 8ee1f17);
  - phân tích 9B-v8: run 03-10-music5-9bv8-kuma / -zenith;
  - đáp án cảnh: hai người chấm Sonnet A / B + `adjudicate_scenes.py`, như bộ 5 → `gold_scene5b`.
- **Ứng viên DUY NHẤT:** ranh giới app + llmVT (V, T từ LLM đọc cả đoạn) + bwsE (E từ BWS trong chương). So với `app`
  (nhãn câu + ranh giới app). Không thêm ứng viên nào khác cho 5b.
- **Luật** như bộ 5 (`set5_llm.py score`, mốc thắng = ⌈0,7·n⌉): THẮNG nếu r VET TB theo chương hơn app ≥ 0,05 VÀ thắng ≥ 3/3
  chương (cùng tỉ lệ 7/9).
- **Chi phí trên máy người dùng** (báo kèm, đo trên chính lượt chạy 5b ở card 8 GB máy nhà, qwen3.5:9b qua Ollama):
  - số lượt gọi LLM thêm mỗi chương: lượt V/T đoạn + lượt BWS nhóm, chỉ trên đoạn app;
  - thời gian: tổng giây mỗi chương, quy ra giây trên mỗi giờ sách nói;
  - VRAM: `size_vram` của `/api/ps` trong lúc chạy.
- THẮNG → đề xuất đưa vào app, kèm chi phí ấy, để Lead / chủ sách quyết. Trượt → giữ nhãn câu, ghi số.

**KẾT QUẢ BỘ 5B (03-10 13:49, `results/set5b_score.txt`):** **KHÔNG THẮNG → giữ nhãn câu.**
- Hỏng định dạng: 0 (V/E/T 0, BWS 0).
- `app + llmVT + bwsE` so `app`: r VET TB **+0,070** (0,139 so 0,069), nhưng chỉ thắng **2/3** chương. Luật cần 3/3.
- Chi phí đo trên lượt này (card 8 GB máy nhà, qwen3.5:9b Q4_K_M):
  - 36 lượt gọi cho 3 chương (Kuma 112: 4 V/T + 6 BWS; Zenith 049 / 050: 5 + 8 mỗi chương);
  - 151 giây cho 39,8 phút sách, tức ≈ **227 giây và 54 lượt mỗi giờ sách nói** (lượt đầu 14 giây gồm nạp model);
  - VRAM `size_vram` 5,50 GB (5,12 GiB), ngữ cảnh 16k.
- Ghi lại, KHÔNG phải thước (3 chương, nhìn sau khi có số):
  - `app + llmVT` +0,126, thắng 3/3;
  - `app + bwsE` riêng E −0,165, thắng 1/3.
  - Hai bộ đảo chiều nhau: ở bộ 5, bwsE +0,075 E còn llmVT chỉ +0,020; ở 5b ngược lại. Chưa thành phần nào ổn định.
  - Nếu muốn thử `llmVT` riêng thì phải ghi trước trên bộ mới, không lấy số này làm bằng chứng.

ĐÁP ÁN BỘ 5 (03-10 05:xx, Corpus `scene_set5/`; mô tả, chưa phải phép thử):
- 9 chương, 86 đoạn sau phân xử (26,6 đoạn/giờ).
- Hai người chấm mù Sonnet A so B: Pk 0,167, P / R ranh giới 0,73 / 0,86, r V/E/T 0,92 / 0,88 / 0,89. Đó là trần.
- Nhãn câu 9B-v8 trên đáp án chung (r gộp, `eval_scenes.py`):

| Cách | V | E | T | Pk |
|---|---|---|---|---|
| `app` | 0,46 | 0,50 | 0,40 | 0,402 |
| `hard` | 0,27 | 0,47 | 0,35 | 0,262 |
| `fixed3` | 0,50 | 0,47 | 0,42 | 0,459 |
| oracle | 0,48 | 0,54 | 0,43 | |

- Chương mới cao hơn bộ 4 (app 0,32 / 0,41 / 0,20) nhưng vẫn xa trần.

Chung:
- Đoạn LLM trả hỏng định dạng thì giữ nhãn câu, có báo số lượng.
- Mọi script và prompt commit vào Corpus TRƯỚC lượt chạy đầu; không sửa sau khi thấy số.
- Nếu (a) và (c) cùng thắng: đề xuất sản phẩm là tổ hợp `llmVT + bwsE`. Chi phí: model gốc ~6 GB và số lượt gọi.
  - Chủ sách / Lead quyết qua thí nghiệm tiếp theo trên bộ 5b hoặc bộ mới; không quyết thẳng từ bộ 5 vì tổ hợp chưa được ghi
    làm thước chính.

**KẾT QUẢ GỘP BA NGUỒN (02-10 23:5x, `eval_fusion.py`, `results/fusion_ablation.txt`; 1.381 bài Incompetech, AUC TB 10 lớp):**

| Tổ hợp | C=1 cố định (GHI TRƯỚC) | C chọn bằng CV lồng (THĂM DÒ) |
|---|---|---|
| A CLAP 512 chiều | 0,814 | 0,849 |
| B âm học (42 đặc trưng) | 0,811 | 0,813 |
| C người đọc chữ (16 số) | 0,871 | 0,871 |
| A+B (chỉ âm thanh = trần của trò) | 0,819 | 0,856 |
| B+C | **0,876** | 0,885 |
| A+B+C | 0,851 | **0,886** |
| C đọc thẳng, không học | 0,799 | |

Cột thăm dò không được ghi trước: `eval_fusion_tuned.py`, Cs 0,003-1, 4 phần bên trong.

- **Luật ghi trước:** GIỮ C (+0,033 trên A+B, thắng 10/10 lớp). KHÔNG giữ A (−0,025 trên B+C) và KHÔNG giữ B (+0,005, thắng 7/10,
  dưới ngưỡng +0,01).
- **Chữ là nguồn mạnh nhất ở nơi có chữ.** Người đọc Claude đọc mô tả của Kevin MacLeod mà không có feel, vẫn đạt 0,87.
- **A thua ở cột ghi trước là do điều chuẩn.** C=1 trên 512 chiều đã chuẩn hoá thì quá khớp; chọn C bằng CV lồng thì A lên
  0,849, ngang đầu dò cũ 0,85. Thầy tốt nhất (thăm dò) là A+B+C 0,886, gần như bằng B+C 0,885.
- **Giới hạn (Lead):** feel và mô tả đều do CHÍNH Kevin MacLeod viết, cùng một nguồn, nên AUC của chữ có thể lạc quan hơn thực.
  Phép kiểm thật là máy chấm kiểu E1 trên lựa chọn cuối, cộng AUC theo TỪNG nguồn khác khi có nhãn người.
- **Sửa trước khi dựng trò (Lead):** trò dùng logistic có C chọn bằng CV lồng (cấu hình 0,856), không dùng C=1.
- **Trò chỉ nghe (A+B, thăm dò) đạt 0,856, tức 97% thầy, trong cùng miền Incompetech.** Mốc ghi trước của trò (≥ 90% thầy trên
  phần GIỮ NGOÀI, giấu ngữ cảnh) sẽ đo đúng cách khi dựng trò.

Thầy cho danh mục (thiết kế theo kết quả này, sẽ đo bằng máy chấm trước khi dùng):
- Mỗi lớp p = w · p_chữ + (1 − w) · p_âm. p_chữ là logistic trên 16 số của người đọc; p_âm là logistic A+B. Cả hai học trên
  Incompetech với C chọn bằng CV lồng.
- w = độ tin cậy của người đọc. Bài ít chữ (OGA / FreePD / Scott Buckley thường < 0,2) vì thế dựa vào âm.
- tenderness / nostalgia / moved chưa có nhãn người: dùng cường độ người đọc pha zero-shot theo cùng w.

**GHI TRƯỚC - THẦY → TRÒ CHO NHẠC NGƯỜI DÙNG TỰ NHẬP (02-10 23:xx, hướng chủ sách qua Lead; E_signal_sources.md §6):**

Thầy và trò:
- **Thầy** = tổ hợp nguồn thắng ablation "GỘP BA NGUỒN" (có ngữ cảnh: chữ, tag người gắn, âm học, model nghe). Thầy cho mỗi
  bài danh mục 13 cường độ + V/E/T + độ tin cậy.
- **Trò** = chỉ nghe, chạy trên máy người dùng: tháp âm thanh CLAP htsat-unfused (ONNX 116 MB, CPU 0,5 giây/bài) + âm học
  librosa (khoảng 1 giây/bài) + đầu dò nhỏ (logistic / MLP 1 lớp ẩn).
- **Cách học:** trò học bắt chước thầy. Mất mát là BCE trên cường độ mềm và MSE trên V/E/T, nhân độ tin cậy của thầy.
- **Giao diện** theo Lead: `analyze(path) -> {valence, arousal, tension, sd, emotions{13}, confidence, fitsUnderNarration,
  loudness}`.

Hai bậc:
1. Máy tính: CPU.
2. Điện thoại: thử ONNX int8. Nhanh hơn 3 giây/bài và trong 50 MB thì chạy trên điện thoại; không thì điện thoại gửi file sang
   máy tính phân tích.

Dữ liệu:
- Tập học: các bài danh mục; sau đó mở rộng bằng MTG-Jamendo (tag mood/theme, thầy gán nhãn) và FMA nếu bước 1 cho thấy thiếu dữ
  liệu (đường cong học theo số bài).
- Giữ ngoài: 20% bài danh mục (chia theo bài, seed 7), GIẤU ngữ cảnh. Trò chỉ thấy âm thanh; thầy thấy đủ.

Thước (ghi trước):
- **(a)** AUC so feel người gắn trên phần Incompetech giữ ngoài. Trò ĐẠT nếu ≥ 90% AUC của thầy trên cùng phần.
- **(b)** r Pearson V/E/T trên bộ ngoài: Soundtracks (Eerola 360, nhạc phim) và DEAM. Báo kèm đầu dò CLAP cũ để so.
- **(c)** Máy chấm kiểu E1 trên đoạn bộ 3 + 4. Chọn bài bằng mô tả của TRÒ so với mô tả của THẦY, chỉ trên các đoạn chọn khác bài.
  Trò không được thua quá 5 điểm phần trăm (phán quyết chung, KTC Wilson báo kèm).
- **(d)** Kích thước và thời gian/bài trên CPU máy tính, và trên điện thoại nếu thử.

Trò không đạt (a) thì thêm dữ liệu (MTG-Jamendo) hoặc đổi nhúng (MuQ / MERT, NC dùng được) rồi đo lại. Mỗi lần đổi ghi một dòng
ở đây trước khi đo.

**KẾT QUẢ THẦY + TRÒ (03-10 03:48, `build_teacher.py` + `build_student.py`, `results/student_eval.txt`):**

Thầy:
- Có chữ của người đọc cho mọi nguồn: Incompetech, Jamendo / Freesound, OGA, FMA, FreePD, Scott Buckley, ccMixter, 魔王魂,
  Silverman. Tổng 4.763 bài.
- AUC thầy ngoài phần học trên 1.381 bài Incompetech có feel, TB 10 lớp 0,895:
  - peacefulness 0,904; sadness 0,937; joy 0,898; playful 0,918; power 0,913;
  - wonder 0,834; tension 0,874; fear 0,898; anger 0,957; mystery 0,821.
- 835 bài mới (FMA / ccMixter / OGA BY-SA…) chưa có âm học lúc chạy, nên âm học điền trung bình. Đang đo bù; thầy chạy lại
  khi xong.

Trò:
- CLAP 512 + 42 âm học, ridge trên logit thầy, alpha chọn CV lồng.
- Học trên 1.657 bài không lời, giữ ngoài 331 bài (hạt giống 7). Trò chỉ thấy âm thanh.
- **(a) ĐẠT:** AUC trên Incompetech giữ ngoài (202 bài có feel): trò 0,863, thầy 0,880, tức **98,0%** (mốc ≥ 90%).
  - Lớp hụt nhiều nhất: sadness 0,867 so 0,912; playful 0,882 so 0,926.
  - r trò-thầy V/E/T trên phần giữ ngoài: 0,83 / 0,93 / 0,86.
- **(b)** r Pearson trên bộ ngoài (trò | zero-shot CLAP cũ):

| Bộ | V | E | T |
|---|---|---|---|
| Soundtracks (Eerola, 470) | 0,646 \| 0,594 | 0,745 \| 0,714 | 0,771 |
| DEAM (1.802) | 0,348 \| 0,271 | 0,691 \| 0,644 | |

  Trò hơn zero-shot cũ ở mọi trục.
- **(d)** Đầu trò 8.880 tham số (0,04 MB). Tháp âm thanh CLAP fp16 56,8 MB; cosine với bản đầy đủ 0,999998. Gói ~57 MB.
  App đã có torch / transformers / librosa, nên không thêm thư viện. sd V/E/T (RMSE giữ ngoài) 0,22 / 0,18 / 0,21.
- **(c)** máy chấm kiểu E1 (trò so thầy) chưa chạy. Theo bài học E1 phải dùng người đọc mô tả KHÔNG CLAP (thước R_mới).
- Việc kế:
  - cắm vào `music_local.set_analyzer` (nhánh `dev/music-student`), gói đăng Hugging Face `NGDtuanh/abook-music-student`;
  - MTG-Jamendo không lời dùng làm dữ liệu thêm khi cần (hiện chưa cần, (a) đã đạt).
- 03-10 04:xx: bản cuối (đủ âm học, 1.736 bài không lời) 97,4% (0,880 / 0,904); Soundtracks 0,65 / 0,74 / 0,77; DEAM
  0,32 / 0,69. Gói HF `NGDtuanh/abook-music-student` @ c6e1485f; Lead đã gộp vào main (đường torch, máy có Studio).

**GHI TRƯỚC - TRÒ (c): TRÒ CHỌN BÀI CÓ TỆ HƠN THẦY KHÔNG (03-10 05:3x, trước khi tính bài nào được chọn):**

Câu hỏi: nhạc người dùng nhập chỉ có số của trò. Nếu cả kho chỉ có số của trò, bài app chọn cho đoạn có tệ hơn không?

Đoạn:
- 100 đoạn của E1 (bộ 4: 82, bộ 3: 18).
- Không khí đoạn = số MÁY như vai `app` của E1: V/E/T, độ tin cậy 1, không có cảm xúc đoạn.

Kho:
- Các bài của `catalog_e1` qua lọc phong cách của cuốn + dài ≥ 60 s, có file âm thanh, như E1.
- Thêm điều kiện: bài KHÔNG LỜI, đủ đặc trưng của trò.

Hai điều kiện, khác nhau DUY NHẤT ở số của từng bài:
- **THẦY:** V/E/T + sd như danh mục (`catalog_e1`).
- **TRÒ:** V/E/T dự đoán CHÉO 5 phần (chia theo bài, hạt giống 7). Mỗi bài được đoán bởi một trò không học bài ấy, như bài
  người dùng nhập.
  - Công thức như `build_student.py`: CLAP 512 + 42 âm học, RidgeCV cùng dãy alpha.
  - sd = `vet_sd` của trò.
  - Biến thể trò-A (chỉ CLAP) báo kèm, không quyết định.

Bài chọn:
- Hạng 1 của `music_select.rank` (code main), giống hệt nhau ở hai bên trừ số của bài.
- Hai bên chọn cùng bài: hoà, không đem chấm. Báo tỉ lệ trùng.

Chấm, trên các đoạn hai bên chọn KHÁC bài:
- Người đọc n1, n2 (agent Claude) đọc mô tả không CLAP như phép (1) của E1, mù vai, trái / phải xáo theo hạt giống.
- Thêm 10% cặp lặp, đảo bên.
- Gói và đề như E1 (`build_e1_judge_packs.py`, `PACK_SET=studentc`, `DESC=noclap`).

Thước:
- Phán quyết chung n1 + n2: cùng chọn thì bên ấy thắng; khác nhau thì nửa - nửa.
- p_trò = (thắng + 0,5 × nửa) / số cặp khác bài.
- **Trò ĐẠT nếu p_trò ≥ 0,45**, tức không thua quá 5 điểm phần trăm. Báo kèm KTC Wilson 95%.
- Báo thêm trên cả 100 đoạn (trùng bài = hoà).
- Dùng được chỉ khi: ổn định a/b trên cặp lặp ≥ 0,75 VÀ kappa n1-n2 ≥ 0,20. Không đạt thì báo "không kết luận", không phán.

Thiên lệch biết trước:
- Mô tả không CLAP mang chữ trang nguồn (tag, mô tả, feel) mà THẦY đã đọc. Thước vì thế nghiêng về thầy.
- Trò đạt dưới thước này thì kết luận càng chắc. Trò trượt thì phải đo lại bằng thước nghe L_min trước khi bỏ trò.
- L_min (Omni-7B-EN) chạy kèm nếu hàng GPU có chỗ. Chỉ báo, không quyết định.

**BỔ SUNG GHI TRƯỚC (03-10 05:2x, SAU khi tính bài chọn, TRƯỚC mọi lượt chấm):**

Đã thấy khi tính bài chọn:
- Hai bên chọn trùng bài 0/100 đoạn.
- Trò bị CO so với danh mục. Danh mục V/E/T là hạng đổi ra −1..1. Trên 1.646 bài:

| Trục | sd danh mục | sd trò | r |
|---|---|---|---|
| V | 0,46 | 0,33 | 0,90 |
| E | 0,50 | 0,43 | 0,94 |
| T | 0,47 | 0,34 | 0,91 |

- Hệ quả trong kho trộn (danh mục + nhạc nhập): bài nhập luôn bị đặt gần giữa.

Thêm điều kiện **TRÒ-q**:
- Số của trò ánh xạ phân vị về phân bố danh mục, đơn điệu từng trục, 101 mốc.
- Mốc ghép trên chính dự đoán chéo, không nhìn bài nào được chọn.
- sd nhân tỉ lệ sd danh mục / sd trò.

Chấm hai loại cặp, cùng người đọc, cùng gói:
- **thầy–trò:** quyết theo ghi trước ở trên.
- **thầy–trò-q:** cùng thước p ≥ 0,45, quyết cho ĐỀ XUẤT đưa ánh xạ phân vị vào app (lưu mốc trong đầu trò).

Đoạn hai bên trùng bài thì không chấm, như trên.

**KẾT QUẢ TRÒ (c) (03-10 05:3x):**
- Code: `build_student.py` CROSSFIT=1, `build_student_c.py`, `score_student_c.py`, `results/student_c_score.txt`.
- Dự đoán chéo: r trò–thầy V/E/T 0,82 / 0,92 / 0,85 (trò-A 0,81 / 0,92 / 0,84).
- Bài chọn không trải đều: qua 100 đoạn, thầy dùng 23 bài khác nhau, trò 34, trò-q 25 (`rank` hạng 1, không phạt lặp).
- Người đọc n1, n2: mỗi gói một agent Sonnet riêng, 212 / 212 lượt.
  - **Dùng được:** ổn định a/b 0,89 / 0,95, kappa 0,70.

| So với thầy | Cặp khác bài | Cả hai chọn bên kia | Cả hai chọn thầy | Khác ý | p | KTC 95% | Mốc ≥ 0,45 |
|---|---|---|---|---|---|---|---|
| trò | 100 | 44 | 39 | 17 | **0,525** | 0,43–0,62 | **ĐẠT** |
| trò-q | 93 | 34 | 47 | 12 | 0,430 | 0,33–0,53 | trượt |

Kết luận:
- **Trò ĐẠT (c):** bài trò chọn không kém bài thầy chọn, đo bằng thước vốn nghiêng về thầy. Trò đạt cả (a), (b), (c), (d).
- **Ánh xạ phân vị KHÔNG vào app:** trò-q kém hơn trò thô (0,43 so với 0,525).
- Việc trò bị co về giữa trong kho trộn vẫn có thật nhưng chưa đo. Phép này so kho toàn trò với kho toàn thầy, không phải kho
  trộn. Muốn đo thì cần ghi trước riêng.

**GHI TRƯỚC - KHO TRỘN: NHẠC NHẬP CÓ BỊ CHỌN LỆCH KHÔNG (03-10 05:4x, Lead giao; trước mọi số):**

Câu hỏi:
- Trong kho thật, bài danh mục mang số thầy, bài người dùng nhập mang số trò.
- Trò co về giữa, nên một bài nhập có thể được chọn nhiều hơn hay ít hơn chính nó khi mang số thầy. Đây là chuyện công bằng
  cho nhạc của người dùng.

Cách đo (chỉ tính, không cần người chấm):
- Đoạn: 100 đoạn E1, không khí máy, như (c). Kho: như (c).
- 50 lượt. Mỗi lượt lấy ngẫu nhiên 20% bài làm "bài nhập" (hạt giống 1..50).
  - Bài nhập mang số trò dự đoán chéo + sd trò; bài còn lại mang số thầy.
  - Đối chứng: cùng các bài ấy mang số thầy.
- Mỗi đoạn lấy danh sách `rank` 6 bài (danh sách "Đổi bài"). Hạng 1 báo riêng.
- Vùng của bài theo vị trí THẦY:
  - "giữa": khoảng cách V/E/T tới tâm thuộc tam phân vị thấp;
  - "vừa": tam phân vị giữa;
  - "rìa": tam phân vị cao.

Thước:
- Tỉ lệ phơi bày theo vùng = (số lần bài nhập vào danh sách khi mang số trò) / (số lần khi mang số thầy), cộng dồn 50 lượt.
- KTC 95% bootstrap theo đoạn.
- **LỆCH** nếu ở vùng nào đó tỉ lệ nằm ngoài [0,8; 1,25] và cả KTC nằm ngoài khoảng ấy. Không thì **CÔNG BẰNG**.

Nếu LỆCH:
- Thử cách sửa: giãn tuyến tính quanh trung bình danh mục, hệ số = tỉ lệ sd danh mục / sd trò từng trục, mốc ghép trên
  dự đoán chéo.
- Báo lại cùng thước.
- Cách sửa chỉ được vào app khi đo lại (c) bằng người đọc với cách sửa ấy vẫn ≥ 0,45, vì ánh xạ phân vị đã trượt (c).

**KẾT QUẢ KHO TRỘN (03-10 05:25, `mixed_library.py`, `results/mixed_library.txt`):** **LỆCH**, nhưng theo chiều ƯU ÁI nhạc
nhập, không phải thiệt cho nó.
- 1.299 bài, 100 đoạn, 50 lượt × 20% bài nhập. Tam phân vị khoảng cách tới tâm cắt ở 0,61 / 0,84.

| Vùng (vị trí thầy) | Vào 6 bài: mang số trò / mang số thầy | Tỉ lệ | Sau khi giãn |
|---|---|---|---|
| giữa | 10.463 / 6.761 | 1,55 (KTC 1,44–1,66) | 1,35 (1,26–1,44) |
| vừa | 1.182 / 115 | 10,3 | 6,5 |
| rìa | 461 / 0 | (thầy không bao giờ vào) | 477 / 0 |

Đọc kết quả:
- Mang số thầy, bài ở vùng vừa / rìa gần như không bao giờ vào danh sách: đoạn E1 có không khí máy ôn hoà, còn danh
  mục trải đều tới ±1.
- Mang số trò, bài bị kéo vào giữa (co + nhiễu dự đoán), nên được chọn cho đoạn mà chính nó không hợp.
- Không phải do sd: sd trò 0,22 / 0,17 / 0,21 gần mặc định 0,2 của bài danh mục.
- Cách sửa đã ghi trước (giãn hệ số 1,39 / 1,18 / 1,37) giảm lệch nhưng vẫn ngoài [0,8; 1,25], nên không đưa vào app.

Hệ quả:
- Nhạc người dùng không bị thiệt. Nó được chọn NHIỀU hơn, kể cả cho đoạn chỉ hợp vừa phải.
- (c) cho thấy bài trò chọn không kém bài thầy chọn trong kho toàn trò. Phần kho trộn cần người đọc thì chưa đo.
- Muốn sửa tiếp phải có ghi trước mới, đo kho trộn bằng người đọc. Ứng viên:
  - trò v2 (MTG) nếu bớt co;
  - nới phạt riêng cho bài nhập.

**GHI TRƯỚC - SỬA KHO TRỘN F1: KỲ VỌNG KHOẢNG CÁCH (03-10 05:5x, Lead: lệch phải hết, "máy chọn theo độ hợp, không vì bài
là nhạc nhập"; trước khi chạy):**

Vì sao không làm theo gợi ý "bài trò sd lớn hơn":
- Trong `z_distance`, sd của bài nằm ở MẪU số (độ khoan dung). Tăng sd thì khoảng cách nhỏ đi, bài nhập càng được chọn
  nhiều.

Cách sửa F1, cho bài mang số trò:
- **Trung bình:** E[thầy | trò] = a + b × trò từng trục. Hồi quy tuyến tính thầy trên trò, ghép trên dự đoán chéo.
  - b = r × sd thầy / sd trò, nhỏ hơn hệ số giãn 1,39.
- **Phạt:** cộng Var(thầy | trò) (phương sai phần dư của hồi quy ấy) vào TỬ số từng trục: (m − t)² + v. Mẫu số giữ nguyên.
- **sd của bài:** = mặc định 0,2 như bài danh mục, không khoan dung thêm.
- Đây là khoảng cách bình phương KỲ VỌNG tới vị trí thật của bài.
- Trong app: thêm `vetVar` cho bài nhập, `z_distance` cộng nó. Bài danh mục không có `vetVar`, không đổi gì.

Đo:
- Cùng `mixed_library.py`, cùng 50 lượt.
- F1 áp cho trò v1, và cho trò v2 nếu v2 xong.
- ĐẠT nếu cả ba vùng nằm trong [0,8; 1,25] hoặc KTC chạm khoảng ấy.
- Vùng mà mang số thầy < 30 lần qua 50 lượt thì báo số, không xét (mẫu số quá nhỏ).
- ĐẠT thì mới đo (c) bằng người đọc trên kho trộn trước khi vào app.

**KẾT QUẢ F1 (03-10 05:29, `results/mixed_library_f1.txt`):** **LỆCH theo chiều ngược lại**, sửa quá tay.
- Hồi quy thầy trên trò:

| Trục | a | b | var |
|---|---|---|---|
| V | −0,055 | 1,25 | 0,040 |
| E | 0,002 | 1,10 | 0,031 |
| T | 0,009 | 1,24 | 0,040 |

- Bài nhập vào 6 bài:
  - vùng giữa: 361 / 6.761 = 0,05;
  - vùng vừa: 60 / 115 = 0,52;
  - hạng 1: 0.
- Lý do: var cộng vào tử thành một khoản phạt gần cố định (~0,86 trong z²). Sáu bài đứng đầu trên ~900 bài đều có z rất nhỏ,
  nên khoản ấy đủ loại bài nhập.
- Gốc rễ: F1 coi số thầy là sự thật không nhiễu. Thật ra số thầy cũng chỉ là một ước lượng.

**GHI TRƯỚC - F2: TRUNG BÌNH HIỆU CHỈNH + λ·var, λ CHỌN TRÊN NỬA KIA (03-10 05:3x, trước khi chạy):**
- Bài nhập: trung bình = a + b·trò như F1; tử cộng λ·var; sd = 0,2.
- Chia 100 đoạn E1 thành hai nửa THEO CHƯƠNG: xếp tên chương, xen kẽ.
- Chọn λ trên nửa A, hạt giống 1–25, lưới λ ∈ {0; 0,05; 0,1; 0,15; 0,2; 0,3; 0,4; 0,5; 0,7; 1}.
  - Tiêu chí: nhỏ nhất max |log tỉ lệ| qua các vùng mà mang số thầy ≥ 30 lần.
- Kiểm trên nửa B, hạt giống 26–50, với λ đã chọn. Luật ĐẠT như F1.
- ĐẠT thì chấm người đọc trên kho trộn (Lead đã duyệt), rồi mới vào app.

**KẾT QUẢ F2 (03-10 05:31, `results/mixed_library_f2.txt`):** **TRƯỢT thước vùng.**
- Trên nửa A, λ = 0,1 tốt nhất (max |log tỉ lệ| 0,036). λ = 0 cho 0,24; λ ≥ 0,3 làm bài nhập bị bỏ rơi.
- Trên nửa B (47 đoạn, hạt 26–50):

| Vùng | Vào 6 bài: trò / thầy | Tỉ lệ | Hạng 1 |
|---|---|---|---|
| giữa | 1.732 / 1.597 | **1,08** (KTC 0,98–1,19) | 0,63 (0,44–0,84) |
| vừa | 176 / 32 | 5,5 (KTC 2,7–27) | |
| rìa | 79 / 0 | | |

- Gộp mọi vùng: 1.987 / 1.629 = 1,22.

**ĐỔI THƯỚC SAU KHI THẤY SỐ (03-10 05:4x, Lead duyệt):**
- Thước vùng đã TRƯỢT với cả F1 lẫn F2. Thước mới dưới đây được chọn SAU khi thấy các số ấy, không phải có từ đầu.
- Lý do đổi:
  - Ở vùng vừa / rìa, bài mang số thầy gần như không bao giờ vào danh sách (mẫu số ~0).
  - Mọi bộ đoán có sai số (r ~0,9) sẽ thỉnh thoảng đưa một bài xa vào gần, nên tỉ lệ ấy nổ.
  - Ép về 1 cần phạt nặng như F1, khi ấy vùng giữa sập.
  - F2 đã bỏ phần ưu ái có hệ thống ở vùng giữa. Phần còn lại là nhiễu của bộ đoán, không còn là thiên lệch dịch / giãn được.
- **Thước mới: độ hợp của bài được chọn.**
  - 100 đoạn E1. So bài chọn từ kho TOÀN THẦY với bài chọn từ kho TRỘN F2.
  - Kho trộn: 20% bài nhập, hạt giống 1, λ = 0,1, a / b như F1.
  - Người đọc n1, n2 không CLAP, cặp lặp 10%, luật như (c).
- **Vào app nếu p_trộn ≥ 0,45** và người đọc dùng được.
  - App: thêm `vetVar` + hiệu chỉnh a, b (lưu trong đầu trò) + λ = 0,1 trong `z_distance`.
  - Bài danh mục không đổi.
- `build_mixed_c.py`, `score_student_c.py` với `SET=mixedc`.

**KẾT QUẢ KHO TRỘN F2 BẰNG NGƯỜI ĐỌC, LƯỢT 1 (03-10 05:5x, `results/mixedc_score.txt`):** **không kết luận.**
- 34 / 100 đoạn khác bài; ở 9 đoạn bài kho trộn là bài nhập.
- p = 0,515 (KTC 0,35–0,67); tính cả 100 đoạn: 0,505. Kappa n1-n2 0,59.
- Ổn định a/b: mỗi người 2 / 3. Chỉ có 3 cặp lặp nên dưới mốc 0,75 theo luật. Ba cặp không đo được gì.

**GHI TRƯỚC - LƯỢT 2 (trước khi chạy):**
- Cùng 34 cặp, LẶP 100%: mỗi cặp có bản đảo bên ở gói kia. Người chấm mới (agent mới), bộ `mixedc2`.
- Lượt 2 QUYẾT theo luật cũ: dùng được (ổn định ≥ 0,75 trên 34 cặp lặp, kappa ≥ 0,20) và p ≥ 0,45.
- p tính trên bản gốc. Lượt 1 chỉ báo.

**KẾT QUẢ LƯỢT 2 (03-10 06:0x, `results/mixedc2_score.txt`):** **F2 ĐẠT → vào app.**
- Dùng được: ổn định a/b 27 / 34 = 0,79 và 30 / 34 = 0,88; kappa 0,58.
- 34 cặp khác bài. Cả hai chọn bài kho trộn 16, cả hai chọn bài kho toàn thầy 11, khác ý 7.
- **p = 0,574** (KTC 0,41–0,72) ≥ 0,45. Từng người 0,59 / 0,56. Tính cả 100 đoạn: 0,525.
- **Chưa chắc chắn:** ĐẠT theo luật điểm ước lượng, nhưng cận dưới KTC 0,41 < 0,45 (chỉ 34 cặp). Khi có bộ 5b, đo lại MỘT lần
  cùng giao thức trên các đoạn mới. Lần ấy trượt thì gỡ F2 khỏi app.
- Lead gộp vào main 165a3e16 (03-10 06:1x).

**ĐO LẠI F2 TRÊN BỘ 5B (chi tiết chốt 03-10 11:1x, trước mọi lượt chấm):**
- Đoạn: đáp án 5b (21 đoạn có nhạc). Không khí máy trên đúng ranh giới đáp án, như bộ 3 của E1.
- Thể loại: Kuma `western_fantasy`, Zenith `xianxia` (võ hiệp; cùng bộ phong cách phía Đông với `chinese_history`).
- Kho, λ, hạt giống bài nhập như lượt 2. `build_mixed_c.py` với `SET5B=1` → `mixedc5b`.
- Khác bài 12 / 21 đoạn; ở 8 đoạn bài kho trộn là bài nhập.
- Lặp 100% như lượt 2: 24 lượt mỗi người, 2 gói. Luật như lượt 2.
- Chỉ 12 cặp nên KTC sẽ rất rộng. Đây là lần đo lại duy nhất đã hẹn: TRƯỢT (p < 0,45 khi dùng được) thì gỡ F2.

**KẾT QUẢ ĐO LẠI F2 TRÊN 5B (03-10 11:2x, `results/mixedc5b_score.txt`):** **ĐẠT sát mốc → GIỮ F2.**
- Dùng được: ổn định a/b 11 / 12 cả hai người; kappa 0,83.
- 12 cặp khác bài. Cả hai chọn kho trộn 5, cả hai chọn kho toàn thầy 6, khác ý 1.
- **p = 0,458** (KTC 0,22–0,71) ≥ 0,45. Từng người 0,50 / 0,42. Tính cả 21 đoạn: 0,476.
- Gộp hai lần có người đọc dùng được (lượt 2 E1 + 5b, 46 cặp): 21 / 17 / 8 → p ≈ 0,54. Báo kèm, không phải thước ghi trước.
- Đọc kết quả: F2 không làm bài chọn tệ hơn rõ rệt, nhưng cũng chưa chứng minh tốt hơn. Đủ để giữ, chưa đủ để nói chắc.
  Không còn lần đo lại nào đã hẹn.

Vào app (nhánh `dev/music-mixed-f2`), chỉ cho bài nhập:
- Hiệu chỉnh a + b·trò từng trục.
- Bỏ sd của trò; bài dùng mặc định 0,2.
- Thêm `vetVar`; `z_distance` cộng 0,1 × vetVar vào tử.
- Hằng số riêng cho đầu A (ONNX), ghép cùng cách trên dự đoán chéo của A. Đầu A không chấm người đọc riêng: cách làm giống
  hệt, số gần như trùng.

| Trục | a | b | var |
|---|---|---|---|
| V | −0,055 | 1,251 | 0,041 |
| E | 0,002 | 1,096 | 0,031 |
| T | 0,009 | 1,277 | 0,041 |

**KẾT QUẢ TRÒ v2 + MTG (03-10 05:3x, `results/student_eval_v2.txt`):** **KHÔNG THAY v1**, trượt cả ba điều kiện.

| | v1 | v2 |
|---|---|---|
| (a) AUC trò / thầy | 0,880 / 0,904 (97,4%) | 0,826 / 0,904 (91,4%) |
| Soundtracks V / E / T | 0,65 / 0,74 / 0,77 | 0,59 / 0,71 / 0,72 |
| DEAM V / E | 0,32 / 0,69 | 0,32 / 0,70 |
| Độ co (sd chéo / sd danh mục, TB) | 0,755 | 0,536 |

- Phụ: AUC tag MTG giữ ngoài 0,769 (29 cặp tag-lớp, 1.145 bài).
- Vì sao kém:
  - Nhãn MTG chỉ từ tag: 79% bài có tag ánh xạ, nhưng tag nói ít thì V/E/T bị kéo về trung tính.
  - 6.489 bài như thế lấn 1.389 bài danh mục, nên trò co thêm và AUC trên Incompetech giảm.
- Giữ v1. Dữ liệu MTG chỉ dùng lại được nếu có nhãn tốt hơn (người đọc từng bài, hay nghe), và phải ghi trước riêng.

**GHI TRƯỚC - TRÒ v2 HỌC THÊM MTG (03-10 05:4x, Lead giao; bổ sung ghi trước MTG 02-10):**

Dữ liệu:
- 7.634 bài MTG không lời (có lời ≤ 0,5). Mỗi bài có CLAP 3 cửa sổ + 42 âm học, tính y như danh mục.
- Phần giữ ngoài MTG: 15% bài, chia theo hoán vị hạt giống 7 trên mã bài. split-0 của bộ là theo nghệ sĩ cho mọi bài;
  sau khi lọc không lời, chia theo mã cho đơn giản, ghi rõ ở đây.

Nhãn thầy MTG (đổi so với 02-10 để rẻ):
- Bảng tag như ghi trước 02-10, làm mức sàn.
- Người đọc chữ đọc TỔ HỢP TAG (1.641 tổ hợp khác nhau), không đọc tên bài. Tên bài Jamendo hiếm khi nói không khí, mà đọc
  theo bài thì đắt gấp 5.
  - Cùng định dạng ra như `text_llm`: 13 cường độ + valence / energy / tension + độ tin cậy.
  - Agent Claude Sonnet, lô ~250 tổ hợp.
  - **Thực tế (ghi trước khi học):** agent lô 0 không đọc từng tổ hợp. Nó cho HỒ SƠ từng tag (59 tag) rồi gộp bằng luật cố
    định (`mtg_reader/tag_profiles.py`):
    - cảm xúc = max qua các tag;
    - V/E/T = trung bình theo tin cậy;
    - tin cậy = 1 − ∏(1 − c), ×0,7 khi tag trái chiều, trần 0,9;
    - tin cậy < 0,3 thì kéo về trung tính.
  - Tôi giữ cách ấy và áp CÙNG một luật cho cả 1.641 tổ hợp (lô 0 khớp 275 / 275), thay vì 6 lô đọc rời. Thông tin đầu vào
    chỉ có tag, nên hồ sơ từng tag gần như là tất cả những gì một người đọc rút ra được.
- Cảm xúc = max(bảng, người đọc × tin cậy). V/E/T = của người đọc.
- Trọng số mẫu: 0,6 nếu có ≥ 1 tag ánh xạ, không thì 0,2.

Học:
- Công thức như trò v1 (ridge trên logit thầy, RidgeCV cùng dãy alpha).
- Tập học = phần học danh mục (như v1) + phần học MTG.
- Giữ ngoài danh mục giống hệt v1.

Thước:
- (a) AUC trên Incompetech giữ ngoài.
- (b) r Soundtracks V/E/T + DEAM V/E.
- Độ co: sd trò / sd danh mục từng trục, dự đoán chéo trên danh mục như (c).
- Phụ, chỉ để định vị: AUC 56 tag MTG trên phần giữ ngoài MTG.

**v2 THAY v1 nếu cả ba:**
- Trung bình 5 số r (b) tăng ≥ 0,01.
- AUC (a) giảm không quá 0,005.
- Độ co không tệ hơn: tỉ lệ sd trung bình 3 trục ≥ của v1.

Thay thì: đăng revision HF mới (cả đầu A cho ONNX), đo lại parity, nâng `REVISION` trong app. Không thay thì ghi số rồi dừng.

**GHI TRƯỚC - TRÒ ĐƯỜNG ONNX cho máy chỉ player + điện thoại (03-10 05:xx, Lead; trước khi làm):**

Bản torch hiện có là CHUẨN. Đường ONNX phải khớp nó, đo trên 20 bài danh mục cố định (20 mã đầu của `embedding_ids.json` có
audio, xếp theo mã):
- **Nhúng CLAP:** cosine(ONNX, torch) ≥ 0,999 ở mọi bài.
- **Đầu ra:** |ΔV|, |ΔE|, |ΔT| ≤ 0,02 và mọi |Δ cường độ| ≤ 0,02 ở mọi bài; `family` trùng ở ≥ 19/20 bài.
- **Mel:** phổ mel tự tính (numpy cho máy tính, Kotlin cho điện thoại) so `ClapFeatureExtractor` trên cùng mẫu: sai số tuyệt đối
  TB ≤ 1e-3 dB, tối đa ≤ 0,05 dB.

Âm học (42 đặc trưng, librosa: beat_track, chroma…) có thể không có ở máy chỉ player / điện thoại. Khi đó:
- **Biến thể "trò-A"**: đầu chỉ học trên CLAP 512 chiều, cùng cách học, cùng phần giữ ngoài.
- Dùng được nếu (a) ≥ 90% AUC thầy VÀ (b) r V/E/T bộ ngoài không kém zero-shot cũ ở trục nào.
- Không đạt thì máy đó gửi file sang máy có Studio để phân tích (mạng trạm), không dùng số kém hơn.

Điện thoại: onnxruntime-android + mel Kotlin, cùng ngưỡng. Kích thước: tháp fp16 ONNX ~58 MB, đầu < 0,1 MB.

**KẾT QUẢ trò-A (03-10 05:xx, `STUDENT_A=1 build_student.py`, `results/student_eval_A.txt`): DÙNG ĐƯỢC.**
- (a) AUC trò-A 0,873, thầy 0,904 → 96,5% (≥ 90%). Thêm âm học chỉ lên 97,4%.
- (b) Soundtracks 0,642 / 0,733 / 0,762, DEAM V / A 0,308 / 0,675. Hơn zero-shot cũ ở mọi trục (0,594 / 0,714; 0,271 / 0,644).
- Hệ quả: máy chỉ player và điện thoại dùng trò-A (mel + tháp CLAP ONNX + đầu 0,03 MB). Không cần librosa hay port âm học sang
  Kotlin. Máy có Studio giữ bản đủ âm học.

**KẾT QUẢ ĐƯỜNG ONNX (03-10 04:47, Corpus `research/music/onnx_student/`, `results/onnx_parity.txt`): ĐẠT MỌI NGƯỠNG.**
- 20 bài cố định ("8bit Dungeon Boss" … "Agnus Dei X").
- Đường ONNX: mel numpy + tháp fp16 + đầu trò-A. Bản torch dùng cùng đầu trò-A.

| Tiêu chí | Ngưỡng | Đo được |
|---|---|---|
| Cosine nhúng | ≥ 0,999 mọi bài | min 0,999999 |
| \|ΔV / ΔE / ΔT\| tối đa | ≤ 0,02 | 0,00026 / 0,00024 / 0,00038 |
| \|Δ cường độ\| tối đa | ≤ 0,02 | 0,00044 |
| family trùng | ≥ 19/20 | 20/20 |
| Mel lệch TB / tối đa | ≤ 1e-3 / 0,05 dB | 9,6e-8 / 7,6e-6 dB |

- Mel float32 thuần cũng đạt (TB 4e-6, tối đa 2,3e-3 dB). Kotlin không cần double.
- Kích thước: tháp ONNX fp16 59,0 MB, đầu trò-A 54 KB. Thời gian CPU ~0,21 giây / bài (mel 30 ms + tháp 183 ms).
- Gói HF `NGDtuanh/abook-music-student` @ 60e11bce đã thêm `clap_audio_fp16.onnx` + `student_head_A.npz`. README trong
  `onnx_student/` ghi mọi hằng số mel, luật cửa sổ và công thức đầu trò cho bản Android.
- Lưu ý: phép so dùng cùng bộ giải mã ffmpeg ở hai đường. Máy khác giải mã khác thì mẫu lệch nhẹ; cần đo lại trên chính máy đó
  khi port.

**GHI TRƯỚC - MTG-JAMENDO LÀM DỮ LIỆU HỌC CHO TRÒ (02-10 23:xx, Lead + chủ sách):**

Bộ dữ liệu:
- autotagging_moodtheme: 18.486 bài, 56 tag mood/theme. Metadata CC BY-NC-SA, audio CC từng bài.
- Bản audio đầy đủ, xử lý cuốn chiếu trần ~20 GB mỗi máy (`mtg_rolling.py`). Gói 00-57 chạy máy nhà, 58-99 chạy Mac.
- Mỗi bài lưu nhúng CLAP + có lời / nền + âm học `acoustic_features2`. Chỉ giữ audio bài không lời (ứng viên danh mục).
- Sổ gói: `done_tars.txt` mỗi máy.
- **Sửa 03-10 (chủ sách qua Lead: "nhạc có lời không bao giờ dùng làm nhạc nền thì quan tâm làm gì?"):** chỉ bài KHÔNG LỜI
  (có lời ≤ 0,5) vào danh mục LẪN tập học của trò; trò chỉ phải phân tích nhạc nền không lời, học trên bài có lời là lệch
  miền. Bài có lời chỉ qua bộ dò lời (CLAP 3 cửa sổ, cần cho chính việc loại) rồi bỏ: không âm học, không lưu nhúng, chỉ ghi
  `{id, có lời, kept=false}`. Số đã tính của bài có lời ở gói 00-01 / 58 đã xoá. Gói đầu: 43-45% bài không lời. Áp như
  nhau cho FMA.
- **Nhạc NGƯỜI DÙNG tự nhập (chủ sách, sau đó):** KHÔNG dò lời, không gắn nhãn "có lời", không chặn - bài có lời là lựa chọn
  của người dùng, và máy không được cấm người dùng dựa trên phán đoán của máy. Bộ dò lời chỉ dùng để lọc danh mục máy tự gom
  và dữ liệu học của trò.
- Hệ quả cho thước phụ: AUC 56 tag MTG đo trên phần test KHÔNG LỜI, nên không so thẳng được với baseline công bố (đo trên mọi
  bài); chỉ dùng để định vị.

Nhãn thầy từ tag (ghi trước, cường độ 1 hoặc 0,5; lấy max khi nhiều tag cùng lớp; bài không có tag nào ánh xạ thì không có
nhãn lớp ấy):

| Lớp | Tag cường độ 1 | Tag cường độ 0,5 |
|---|---|---|
| peacefulness | calm, relaxing, meditative, nature | soft |
| tenderness | love, romantic | ballad, soft |
| nostalgia | | retro, melancholic |
| sadness | sad, melancholic | emotional |
| joy | happy, fun, positive, upbeat, party, summer, holiday | christmas |
| playful | funny, children | fun |
| power | epic, powerful, heavy, action, trailer, sport | motivational, energetic |
| wonder | space | dream, inspiring, epic |
| tension | | dramatic, dark, action, drama |
| fear | dark | |
| anger | | heavy |
| mystery | dream, deep | space, soundscape |
| moved | emotional, inspiring | hopeful, uplifting |

Gộp với kênh chữ:
- Người đọc chữ đọc tag MTG cộng tên bài theo cùng prompt; bảng trên là mức sàn.
- Nhãn thầy MTG = max(bảng, người đọc chữ × độ tin cậy). Độ tin cậy nhãn = 0,6 nếu có ≥ 1 tag ánh xạ, không thì 0,2.

Giữ ngoài:
- 15% bài MTG (theo split-0 của bộ, phần test).
- Thước phụ của trò: AUC từng tag MTG (56 tag) trên phần test, so với baseline đã công bố cho mood/theme (PR-AUC
  ~0,12-0,15, ROC-AUC ~0,75-0,77 cho effnet/musicnn) để biết trò đứng đâu.

**TẢI XONG (03-10 03:45):**
- Đã tải đủ 100 gói moodtheme: máy nhà gói 0–57, Mac gói 58–99 (`feats.jsonl` 7.512 dòng, CLAP npz theo gói).
- Phần của Mac đã chép về `C:/abook_data/mtg_jamendo/mac/`. Audio không lời giữ trên Mac (~22 GB).
- Bài có lời chỉ còn dòng tối thiểu, không có đặc trưng.
- Chưa đem học: trò đã đạt (a) không cần thêm dữ liệu. Đây là kho dự trữ cho lần đổi trò kế tiếp.
- Essentia trên Mac (chỉ để so, CC BY-NC-ND) xong 3.927 bài danh mục: `essentia_out.jsonl` + `essentia_effnet.npy`.

**LỚP 2 PHÍA BÀI - 13 cường độ độc lập (02-10 22:xx, `derive_emotions.py`):**
- **Zero-shot CLAP** (3 câu mô tả mỗi lớp, z theo cả kho, sigmoid): AUC so feel người gắn của Incompetech (1.381 bài)
  trung bình 0,69. Có lớp còn kém bản GEMS-9 cũ, như joy 0,46 so với 0,74.
- **Đầu dò logistic trên vector CLAP đóng băng** (lý thuyết §3.3), nhãn là feel người gắn, kiểm chéo 5 phần chia theo bài:
  AUC 0,73-0,92, trung bình 0,85. Cụ thể: anger 0,92, sadness 0,88, playful 0,88, power 0,87, joy 0,86,
  peacefulness 0,85, fear 0,85, tension 0,82, wonder 0,79, mystery 0,73.
- **Chọn nguồn từng lớp:** đầu dò thắng ở cả 10 lớp có nhãn nên dùng đầu dò. Bài có nhãn lấy dự đoán ngoài phần học.
  Ba lớp tenderness / nostalgia / moved không có feel tương ứng nên giữ zero-shot.
- **Cùng một thang:** logit được chuẩn hoá z rồi đưa qua cùng một sigmoid, nên mỗi lớp có khoảng 11-14% bài >= 0,5
  (trung bình 1,6 lớp mỗi bài, gần mức người chấm gắn cho đoạn là 1,5).
- **Giới hạn:** chỉ học trên Incompetech; với nguồn khác là chuyển miền, chưa đo.

**KIỂM HỒI QUY LỚP 1-2 TRƯỚC KHI GỘP (02-10 22:xx; KHÔNG ghi trước, chỉ để chặn hồi quy, `compare_rankers.py`):**
- **Cách làm:** chạy `choose` của main và của nhánh `dev/music-gems` trên 10 chương bộ 4, mỗi bản tự chia đoạn (57 đoạn).
  Cùng danh mục thử 2.016 bài có `emotions`, cùng bảng phong cách theo thể loại.
- **Thước:** khoảng cách nhãn người của bài chọn (chỉ bài Incompetech có feel, 40-52 đoạn) tới đáp án V/E/T của đoạn đáp án
  chứa giữa đoạn app; thấp là hợp.

| Cách chọn | Khoảng cách | Cùng bài với main |
|---|---|---|
| Lớp 1 (σ, trọng số 1,0 / 0,8 / 0,6) | 0,824 | 74% |
| main | 0,845 | - |
| Lớp 1 + Lớp 2 trọng số 1 | 0,859 | 49% |
| Lớp 1 + Lớp 2 trọng số 3 | 0,936 | 28% |

- Không bản nào có đoạn im lặng hay lặp bài.
- **Kết luận:** số hạng Lớp 2 làm kém đi theo đúng liều. Cảm xúc của ĐOẠN đang suy từ nhãn câu (`LINE_EMOTIONS`) và còn quá
  thô; phía bài thì đã có đầu dò AUC 0,85.
- **Quyết định trên nhánh:** `EMOTION_WEIGHT = 0`, giữ cơ chế. Bật lại khi đường LLM (segllm) cho 13 cường độ của đoạn và
  E4 đo lại.
- **Thang phạt:** các mức phạt đổi sang thang z (chia 0,34), vì z-distance lớn hơn khoảng 3 lần thang Euclid cũ.

## "Nghe ngay": danh sách phát + mức nhạc dưới giọng máy (03-10 14:xx, Lead giao)

Sách chỉ có chữ, không phân tích, nên không có không khí cảnh để chọn bài. Người nghe chọn một danh sách phát
(docs/LISTEN_ANYTHING.md mục 4).

**Danh sách phát** (`LLM_Train/music/playlists.py`; `build_catalog.py` ghi vào manifest trường `playlists`, có trong
revision):
- Mỗi mục: `{id, name, description, tracks: [link theo thứ tự trộn sẵn], minutes}`.
- Luật là bộ lọc trên nhãn sẵn có của danh mục: phong cách, V/E/T, 13 cường độ của thầy.
- Nền chung: dài ≥ 60 s và speechBand ≤ 0,75.
- Trộn sẵn: xáo theo hạt giống = id, không để hai bài liền nhau cùng tác giả khi tránh được.
- Mỗi danh sách tối đa 150 bài.
- Số đo trên danh mục bc472d9d9f40:

| id | Tên | Luật chính | Khớp | Giữ | Phút |
|---|---|---|---|---|---|
| fantasy_adventure | Kỳ ảo phiêu lưu | epic / folk / orch. nhẹ, wonder hay power ≥ 0,4, E > −0,3 | 169 | 150 | 459 |
| fantasy_calm | Kỳ ảo êm đềm | orch. nhẹ / folk / ambient, peace hay wonder ≥ 0,4, E < 0,1 | 134 | 134 | 1.161 |
| school_light | Học đường nhẹ nhàng | piano / acoustic / jazz / pop, V > 0,1, T < 0 | 242 | 150 | 545 |
| romance | Lãng mạn | tenderness hay moved ≥ 0,45, T < 0,1 | 144 | 144 | 903 |
| comedy | Hài hước, vui nhộn | playful hay joy ≥ 0,5, V > 0,2 | 271 | 150 | 485 |
| action | Hành động, chiến đấu | power ≥ 0,5, E > 0,4, T > 0 | 219 | 150 | 496 |
| horror | Kinh dị | fear ≥ 0,5 hay style dark, T > 0,3, V < 0 | 171 | 150 | 586 |
| mystery | Trinh thám, bí ẩn | mystery ≥ 0,5, jazz / piano / ambient / dark / điện tử, E < 0,5 | 84 | 84 | 431 |
| eastern | Tiên hiệp, cổ phong | style eastern_ancient hay family eastern | 132 | 132 | 410 |
| scifi | Khoa học viễn tưởng | điện tử / ambient, wonder hay mystery ≥ 0,4 | 76 | 76 | 543 |
| sad | Buồn, sâu lắng | sadness hay nostalgia ≥ 0,45, V < 0,1, E < 0,3 | 190 | 150 | 672 |
| sleep | Êm - để ngủ | E < −0,4, T < −0,2, peace ≥ 0,4, speechBand ≤ 0,5 | 113 | 113 | 1.081 |

- Không danh sách nào dưới 40 phút; ngắn nhất là `eastern`, 410 phút.
- **Chưa đo chất lượng:** luật dựa trên nhãn máy. Xem nhanh 6 bài đầu mỗi danh sách thấy vài bài lệch tên. Muốn biết danh sách
  có đúng "cảm giác" không thì cần người đọc chấm theo ghi trước riêng.

**Mức nhạc dưới giọng máy** (đo, không đoán): LUFS tích hợp BS.1770 (pyloudnorm), 60 câu mỗi giọng (~5 phút), ghép với
khoảng lặng 0,4 s. Câu của nghiên cứu căn từ `LLM_Train/word_align/data`.

| Giọng | LUFS | sd theo câu | Đỉnh |
|---|---|---|---|
| Edge TTS HoaiMy | −18,3 | 0,3 | −2,6 dBFS |
| Edge TTS NamMinh | −19,7 | 0,5 | −2,2 dBFS |
| VieNeu Mỹ Duyên | −17,8 | 0,5 | 0,0 dBFS |
| VieNeu Đức Trí | −18,7 | 0,5 | −2,9 dBFS |
| (tham chiếu) giọng Studio, Pha 4 | −20,3 | | |

- Edge TTS **không** ở −16: thấp hơn ~2–4 dB so với ước. Hai giọng Edge còn lệch nhau 1,4 dB.
- Giọng của máy (OneCore vi-VN / Android) **chưa đo**: máy chủ sách không cài giọng Việt OneCore. Giọng này đổi theo từng máy,
  nên không có một hằng số đúng cho mọi người.

**Đề xuất cho app:**
- Chuẩn hoá MỖI đoạn giọng "Nghe ngay" về −20 LUFS lúc tạo clip: đo LUFS trên chính PCM đã có, nhân gain. Kẹp ±6 dB và
  không để đỉnh vượt −1 dBFS.
- Sau đó giữ nguyên công thức nhạc đã chốt ở Pha 4: LD mặc định 20 LU, bù 8·(speechBand − 0,30) kẹp ±6.
- Lợi ích:
  - một công thức cho mọi giọng, kể cả giọng máy không biết trước;
  - đổi giọng giữa chừng không làm nhạc to / nhỏ đi;
  - Edge chỉ phải giảm 0,3–1,7 dB nên không có rủi ro vỡ tiếng.
- Nếu không chuẩn hoá: dùng mức giọng theo bảng trên thay cho −20,3 trong công thức gain nhạc (HoaiMy −18,3, NamMinh
  −19,7, VieNeu −17,8 / −18,7). Giọng máy khi đó không có số.
- **Lead chốt (03-10 14:xx):** chuẩn hoá mỗi clip về −20 LUFS (kẹp ±6 dB, đỉnh ≤ −1 dBFS) + công thức Pha 4. Danh mục
  bc472d9d9f40 đã triển khai.

**GHI TRƯỚC - CHẤM CHẤT LƯỢNG DANH SÁCH PHÁT (03-10 14:xx; máy chấm, chủ sách không chấm; chạy khi có chỗ):**

Mẫu:
- Mỗi danh sách lấy 10 bài TRONG danh sách (hạt giống 7 trên thứ tự đã trộn).
- Thêm 10 bài MỒI, lấy ngẫu nhiên từ những bài qua nền chung nhưng KHÔNG thuộc danh sách ấy (cùng hạt giống).

Mô tả bài:
- Không CLAP: tên, tác giả, nguồn, tag / mô tả trang gốc + âm học cả bài thành lời (cùng cách `describe_noclap.py`, bỏ phần
  đo trên clip 30 s).
- Không ghi bài thuộc danh sách nào.

Người chấm:
- Hai người đọc Sonnet r1 / r2, mỗi danh sách một gói, mỗi gói một agent.
- Đề: tên + mô tả danh sách, rồi 20 bài xáo lẫn. Mỗi bài trả "hợp / không hợp" làm nhạc nền cho sách loại ấy + độ chắc 1–5.
- 10% bài lặp ở gói khác.

Thước, mỗi danh sách:
- **Độ đúng** = tỉ lệ bài trong danh sách được cả hai chấm "hợp" (khác ý tính nửa).
- **Báo nhầm mồi** = tỉ lệ mồi được chấm "hợp".
- **ĐẠT** nếu độ đúng ≥ 0,70 VÀ hơn báo nhầm mồi ≥ 0,25.
- Dùng được chỉ khi ổn định a/b ≥ 0,75 và kappa r1-r2 ≥ 0,20.

Danh sách TRƯỢT thì siết luật (ghi lại luật mới) rồi chấm lại bằng mẫu MỚI (hạt giống 8), không dùng lại mẫu cũ.

**GHI TRƯỚC - KIỂM TỰ ĐỘNG DANH SÁCH PHÁT (03-10 14:4x, Lead giao; THAY lượt người đọc ở trên, phần ấy để sau nếu cần):**

Không agent; chỉ nhãn + model sẵn có (`audit_playlists.py`).

Mỗi bài trong danh sách bị tính **LỆCH** nếu vướng ít nhất một điều:
- **(1) Có lời:** `vocals` > 0,3. Danh mục chỉ loại > 0,5.
- **(2) Cường độ lệch theo TRÒ chỉ-nghe:**
  - Dùng dự đoán chéo, đọc âm thanh, không đọc chữ trang gốc. Đây là nguồn độc lập với nhãn thầy dùng để lọc.
  - Luật mỗi danh sách viết trong script: trục / cảm xúc chính ở hẳn phía sai. Ví dụ Kinh dị: trò valence > 0,3, hoặc
    fear < 0,15 và tension < 0,2.
  - Bài không có số trò (thiếu đặc trưng) thì bỏ phép này.
  - `eastern` không có phép này, vì nó lọc theo phong cách.
- **(3) Tên / tag lệch:** tên bài hay tag / thể loại trang gốc chứa từ trái nghĩa với danh sách, ví dụ Kinh dị có
  "happy, party, lullaby". Danh sách từ viết trong script.

Thước:
- % bài lệch mỗi danh sách, kèm số bài vướng từng điều.
- **> 10% → siết luật:** loại bài vướng (1), (2), (3) khỏi chính danh sách ấy. Báo lại số bài + phút; phải còn ≥ 40 phút.

Giới hạn:
- Sau khi siết, % lệch theo CHÍNH ba phép này là 0 theo cách dựng, nên không phải bằng chứng danh sách "đúng cảm giác".
- Bằng chứng ấy cần lượt người đọc ở trên.

**KẾT QUẢ KIỂM TỰ ĐỘNG (03-10 15:xx, `results/playlist_audit.txt`; trên danh mục bc472d9d9f40, luật gốc):**

| danh sách | bài | lệch | (1) lời | (2) trò | (3) chữ | sau khi siết |
|---|---|---|---|---|---|---|
| fantasy_adventure | 150 | 10% | 12 | 3 | 1 | giữ (không > 10%) |
| fantasy_calm | 134 | 37% | 44 | 0 | 9 | 84 bài / 545 phút |
| school_light | 150 | 31% | 42 | 0 | 5 | 150 / 539 |
| romance | 144 | 17% | 21 | 2 | 4 | 119 / 563 |
| comedy | 150 | 35% | 48 | 0 | 6 | 150 / 483 |
| action | 150 | 7% | 8 | 2 | 1 | giữ |
| horror | 150 | 15% | 17 | 1 | 5 | 147 / 570 |
| mystery | 84 | 27% | 22 | 1 | 1 | 61 / 284 |
| eastern | 132 | 23% | 29 | – | 2 | 101 / 297 |
| scifi | 76 | 50% | 35 | 2 | 1 | 38 / 193 |
| sad | 150 | 14% | 18 | 2 | 1 | 150 / 644 |
| sleep | 113 | 39% | 39 | 1 | 5 | 69 / 538 |

- Gần như toàn bộ phần lệch là **có lời 0,3–0,5**: danh mục chỉ loại > 0,5. Phép (2) trò chỉ-nghe gần như không bắt gì.
- **Đã siết** 10 danh sách > 10% (`playlists.TIGHTEN`; `playlists.Audit` dùng chung cho kiểm và dựng). Mọi danh sách
  vẫn ≥ 40 phút; thấp nhất scifi 193 phút.
  - school_light / comedy / sad vẫn đủ 150 vì trần `MAX_TRACKS`.
- Danh mục mới: **64f4a577f86b**.
- Đề xuất, chưa làm: hạ ngưỡng `vocals` của chính danh mục (đang 0,5) cũng cần ghi trước riêng, vì nó đổi cả chọn nhạc
  theo cảnh chứ không chỉ "Nghe ngay".

**GHI TRƯỚC - "ĐÚNG CẢM GIÁC" CỦA 12 DANH SÁCH PHÁT (03-10 15:1x, Lead giao; trước mọi lượt chấm):**

Câu hỏi: nghe bằng tai máy thì bài trong danh sách có đúng cảm giác của danh sách không?

Độc lập với luật lọc:
- Hai giám khảo chỉ nghe âm thanh. Không thấy tên bài, tag, trang gốc, nhãn thầy (chữ) hay số trò (CLAP).
- Danh mục: **64f4a577f86b** (bản đã siết).

**(M) Music Flamingo 2601** (4-bit, card nhà, qua hàng GPU của Model):
- Mẫu: 10 bài mỗi danh sách, `random.Random(20261003).sample` theo thứ tự danh sách trong manifest. Bài đã rơi vào mẫu
  của danh sách trước thì bỏ, bốc bài khác cùng danh sách.
- Đoạn nghe: 30 giây giữa bài (bắt đầu ở max(0, dài/2 − 15)), mono 16 kHz.
- Mỗi bài chấm hợp với CẢ 12 mô tả tiếng Anh (viết trong `playlist_feel.py` trước lượt chạy, chỉ tả cảm giác / phong
  cách, không có tên bài).
  - Hai cách hỏi a / b.
  - Điểm = kỳ vọng xác suất chữ số 1–7 ở token đầu, như J-mf.
  - 120 × 12 × 2 = 2.880 lượt forward.
- Mỗi bài, mỗi cách hỏi: chuẩn hoá z trên 12 mô tả (bỏ thiên lệch riêng của bài).
  - **ĐÚNG** nếu z của danh sách mình > z trung bình các danh sách ĐỐI (ghi sẵn dưới đây).
  - Phán quyết chính dùng z trung bình của a và b.
- Danh sách đối (theo cảm xúc / năng lượng ngược nhau):
  - fantasy_adventure ↔ sleep, sad, horror
  - fantasy_calm ↔ action, horror, comedy
  - school_light ↔ horror, sad, mystery
  - romance ↔ horror, action, mystery
  - comedy ↔ sad, horror, sleep
  - action ↔ sleep, fantasy_calm, romance
  - horror ↔ comedy, school_light, romance
  - mystery ↔ comedy, school_light, romance
  - sad ↔ comedy, action, school_light
  - sleep ↔ action, horror, comedy
  - eastern, scifi (danh sách theo phong cách) ↔ cả 11 danh sách còn lại
- **Cổng dùng được:** hai phán quyết riêng a và b khớp nhau ≥ 0,75 trên 120 bài, VÀ trung vị khối xác suất chữ số
  ≥ 0,5. Trượt cổng → M không dùng được, chỉ còn A.
- Mỗi danh sách:
  - **ĐẠT** nếu ≥ 8/10 bài ĐÚNG;
  - **NGHI** nếu ≤ 6/10;
  - 7/10 là chưa chắc.
- Ghi lại, không phải thước: ma trận nhầm theo mô tả điểm cao nhất; hạng của danh sách mình trong 12.

**(A) AST AudioSet** (`MIT/ast-finetuned-audioset-10-10-0.4593`, CPU):
- Chạy trên MỌI bài trong 12 danh sách.
- Ba cửa sổ 10 giây ở 25 / 50 / 75 % bài; lấy trung bình xác suất sigmoid.
- Lớp AudioSet mong đợi (ghi sẵn; điểm = trung bình các lớp):

| danh sách | lớp AudioSet |
|---|---|
| fantasy_adventure | Exciting music |
| fantasy_calm | Tender music, New-age music, Ambient music |
| school_light | Happy music |
| romance | Tender music |
| comedy | Funny music, Happy music |
| action | Exciting music, Angry music |
| horror | Scary music |
| mystery | Scary music |
| eastern | Music of Asia, Traditional music |
| scifi | Electronic music, Synthesizer |
| sad | Sad music |
| sleep | Lullaby, Ambient music, New-age music |

- Mỗi danh sách: AUC của điểm lớp mong đợi, bài trong danh sách so với bài của 11 danh sách kia (bài có mặt cả hai phía thì
  bỏ khỏi phía kia).
  - **ĐẠT** nếu AUC ≥ 0,65 VÀ cận dưới KTC 95 % (bootstrap 2.000 lần, hạt giống 7) > 0,5.
- Ghi lại: xác suất "Singing" (kiểm chéo bộ lọc có lời).

Kết luận mỗi danh sách:
- **"Đúng cảm giác"**: cả M (nếu qua cổng) và A đều ĐẠT.
- Một giám khảo ĐẠT: báo riêng từng giám khảo.
- Không giám khảo nào ĐẠT: **NGHI**. Đề xuất sửa luật lọc danh sách ấy, kèm ghi trước mới, không sửa thẳng.

Giới hạn:
- Lớp cảm xúc của AudioSet vốn yếu (mAP thấp), nên A trượt một danh sách chưa chắc là danh sách sai.
- M từng không ổn định khi chấm đoạn truyện khớp clip (J-mf 0,66). Phép này có cổng a / b riêng.
- Hai giám khảo đều là máy, không phải người nghe.

**KẾT QUẢ "ĐÚNG CẢM GIÁC" (03-10 16:2x, `results/feel_score.txt`): 11/12 ĐÚNG CẢM GIÁC; eastern chỉ một giám khảo đạt.**
- (M) MF **dùng được:** khớp a/b 0,97, trung vị khối 1,00, 1,04 giây / lượt (VRAM 6,1 GiB).
- (A) AST: đủ 2.087 bài.

| danh sách | M (ĐÚNG / 10) | A AUC [KTC 95 %] | kết luận |
|---|---|---|---|
| fantasy_adventure | 9 | 0,720 [0,682-0,757] | đúng cảm giác |
| fantasy_calm | 10 | 0,791 [0,735-0,843] | đúng cảm giác |
| school_light | 10 | 0,784 [0,747-0,820] | đúng cảm giác |
| romance | 9 | 0,863 [0,833-0,890] | đúng cảm giác |
| comedy | 8 | 0,890 [0,864-0,914] | đúng cảm giác |
| action | 9 | 0,885 [0,860-0,909] | đúng cảm giác |
| horror | 10 | 0,894 [0,869-0,917] | đúng cảm giác |
| mystery | 10 | 0,679 [0,630-0,728] | đúng cảm giác |
| **eastern** | **0 (NGHI)** | 0,802 [0,752-0,849] | **một giám khảo** |
| scifi | 10 | 0,798 [0,736-0,856] | đúng cảm giác |
| sad | 10 | 0,843 [0,812-0,873] | đúng cảm giác |
| sleep | 10 | 0,825 [0,779-0,869] | đúng cảm giác |

- MF thiên lệch theo mô tả: điểm thô TB cao nhất là fantasy_calm 5,67, thấp nhất eastern 2,84. Mô tả cao nhất của phần lớn
  bài là fantasy_calm. Phép "so với danh sách đối" khử được thiên lệch này; hạng tuyệt đối thì không.
- Thăm dò eastern, NHÌN SAU KHI THẤY SỐ:
  - Trên chính mô tả eastern, MF không phân biệt bài eastern với bài khác (AUC 0,455).
  - 10 bài mẫu: AST "Music of Asia" ≤ 0,005 cả 10 bài. Tên bài: "Holiday Weasel", "Goblin Tinker Soldier Spy", "nuage",
    "Blithe", … Chỉ 3/10 có style eastern_ancient.
  - Vậy hai giám khảo cùng nghe thấy MẪU không phương Đông. AUC 0,80 của A đến từ các bài khác của danh sách.
  - Nhánh `family == "eastern"` (54/101 bài) KHÔNG phải nguồn lỗi: AST Asia AUC 0,848, còn nhánh style là 0,750.
  - Xác suất "Music of Asia" của AST nhỏ trên toàn danh mục (p95 0,0017), không đủ chắc để làm bộ lọc.
- Đề xuất, chưa làm (cần ghi trước riêng):
  - Kiểm năng lực nghe phương Đông của MF và AST bằng chứng dương: bài có tên nhạc cụ rõ (guzheng, erhu, koto, shakuhachi,
    guqin, 和風 / 古风) so với bài phương Tây cùng nhịp.
  - Giám khảo nào nhận ra được thì dùng nó chấm lại toàn danh sách eastern; luật mới chỉ giữ bài được nhận ra, còn ≥ 40 phút.

**GHI TRƯỚC - (1) LỌC LẠI EASTERN + (2) NHÃN LỜI HÁT BẰNG MF (03-10 16:4x, Lead giao, thứ tự 1 rồi 2):**

Chung:
- Mọi lượt MF gộp vào MỘT job GPU (`eastern_vocals_check.py mf`). Chấm (1) và áp xong mới chấm (2).
- Đoạn nghe 30 giây, mono 16 kHz. MF 2601 4-bit như phép trước.

**(1) Eastern.**
- Tập kiểm: `eastern_testset.json` (02-10).
  - Dương: 155 bài nêu đích danh nhạc cụ Đông Á trong tên / tag.
  - Âm: 300 bài không có yếu tố Đông Á.
  - Chỉ bài có file. Bốc 40 bài dương (`random.Random(20261003)`); mỗi bài ghép bài âm chưa dùng gần nhất theo
    `arousal_raw` của CLAP (cùng cường độ) → 40 cặp.
  - Đoạn nghe: giữa bài.
- Giám khảo:
  - **M:** điểm MF với mô tả eastern của phép trước (`DESC["eastern"]`), cách hỏi a / b, điểm = trung bình a / b.
  - **A:** AST, trung bình xác suất "Music of Asia" + "Traditional music", ba cửa sổ như phép trước.
- **Đạt năng lực:** AUC dương so âm ≥ 0,80 VÀ cận dưới KTC 95 % (bootstrap 2.000, hạt 7) ≥ 0,65. Với M thêm điều kiện
  Spearman a so b ≥ 0,70.
- Cả hai đạt thì lấy giám khảo AUC cao hơn.
- Ngưỡng: điểm nhỏ nhất mà trên tập kiểm, trong các bài có điểm ≥ ngưỡng, ≥ 90 % là dương.
- **Lọc lại:**
  - Kho = mọi bài danh mục qua `_base` và luật eastern hiện tại (luật gốc, chưa siết; 132 bài). M chấm cả kho.
  - Eastern mới = bài trong kho có điểm ≥ ngưỡng, rồi siết như cũ trừ điều "lời" (chờ (2)).
  - Phải còn ≥ 40 phút.
- **Không giám khảo nào đạt, hoặc còn < 40 phút:** eastern = style `eastern_ancient` VÀ tên / tag có tên nhạc cụ / chữ Đông Á
  (danh sách từ trong script). Vẫn < 40 phút thì báo Lead, không độn.

**(2) Lời hát.**
- Mẫu phân tầng theo `vocals` của CLAP, 30 bài mỗi tầng (hạt 20261003):
  - S1 < 0,1; S2 0,1–0,3; S3 0,3–0,5 (bài danh mục, mọi nguồn);
  - S4 > 0,5 trong danh mục (Incompetech, được miễn);
  - S5 > 0,5 đã bị loại (không phải Incompetech, có file).
- Đối chứng:
  - 8 bài có tên chỉ rõ có hát ("sung by", "feat."): bài có hát.
  - 8 bài có "instrumental" trong tên: bài không lời.
- Mỗi bài hai đoạn (bắt đầu ở 25 % và 60 % độ dài). MF hỏi hai cách:
  - a: "Does this audio contain a human voice singing or rapping? Answer yes or no."
  - b: "Is this purely instrumental music with no singing voice at all? Answer yes or no."
  - p_hát của đoạn = trung bình (P_a(yes), 1 − P_b(yes)). P(yes) = xác suất "yes" chia (yes + no) ở token đầu, gộp hoa / thường.
  - Bài **có hát** nếu đoạn nào có p_hát ≥ 0,5.
- **Cổng dùng được:**
  - phán quyết nhị phân của a và của b (đảo) khớp ≥ 0,85 trên mọi đoạn;
  - đối chứng: ≥ 6/8 bài có hát được nhận có hát, ≥ 7/8 bài không lời được nhận không lời.
- **Ngưỡng:**
  - Với t ∈ {0,3; 0,5; 0,7; 0,9; 1,01}: ước tỉ lệ bài có hát trong số bài danh mục có `vocals` ≤ t, trọng số theo cỡ tầng
    S1–S4.
  - Chọn t LỚN NHẤT có tỉ lệ ấy ≤ 5 %.
  - Điều "lời" của siết "Nghe ngay" đổi từ vocals > 0,3 thành vocals > t.
  - Dựng lại danh sách và danh mục; Lead deploy.
- Ghi lại, không quyết: tỉ lệ có hát của S5. Nếu thấp thì bộ lọc danh mục 0,5 đang loại nhầm nhiều bài; đó là đề xuất riêng.

**KẾT QUẢ (1) EASTERN (03-10 17:0x, `results/evc_eastern.txt`): KHÔNG GIÁM KHẢO NGHE NÀO ĐẠT → luật dự phòng.**
- M (MF): AUC 0,672 [0,549-0,782]. Spearman a/b 0,95 (ổn định nhưng không nhận ra).
- A (AST "Music of Asia" + "Traditional music"): AUC 0,752 [0,638-0,854].
- So sánh: điểm `eastern_ancient` của CLAP trên chính bộ kiểm này (đủ 155 / 300, 02-10) là AUC 0,994. Đọc: CLAP nhận nhạc cụ
  Đông Á tốt hơn hẳn MF và AST.
- Eastern mới = style `eastern_ancient` VÀ tên / tag có chữ Đông Á: 36 bài / 108 phút (kho 132). Vẫn ≥ 40 phút.
  - Đa số đúng là nhạc phương Đông: 民族 (魔王魂), guzheng, shakuhachi, taiko, "Samurai", "Imperial China".
  - Vài bài vào nhờ tag: "Tequila Suicide", "ネオロック73", "Streichpsalter1". Ghi lại, không sửa tay.
- Áp qua `playlists.EASTERN_KEEP` (`evc/eastern_list.json`). Điều "lời" chờ (2).
- Lỗi khâu cắt (không đổi phương pháp): một đoạn 30,004 giây làm MF lỗi chỉ số ngoài biên ở lượt 526. Từ nay đoạn được cắt
  đúng 30,0 giây (resample trước khi trim). Phần (2) chạy lại từ lượt ấy.

**KẾT QUẢ (2) LỜI HÁT (03-10 17:0x, `results/evc_vocals.txt`): MF DÙNG ĐƯỢC; ngưỡng t = 1,01 → bỏ điều "lời".**
- Cổng:
  - khớp a/b 0,98;
  - đối chứng: bài có hát nhận 7/8, bài không lời nhận 8/8.

| tầng `vocals` (CLAP) | có hát / 30 | cỡ tầng |
|---|---|---|
| S1 < 0,1 | 0 (0 %) | 1.445 |
| S2 0,1–0,3 | 1 (3 %) | 182 |
| S3 0,3–0,5 | 0 (0 %) | 115 |
| S4 > 0,5 trong danh mục (Incompetech) | 2 (7 %) | 345 |
| S5 > 0,5 đã bị loại | 3 (10 %) | 1.395 |

- Ước tỉ lệ có hát trong bài danh mục có vocals ≤ t:
  - 0,4 % ở t 0,3; 0,3 % ở 0,5 / 0,7 / 0,9; 1,4 % khi không lọc.
  - Theo luật (t lớn nhất mà ≤ 5 %) → t = 1,01. `playlists.LIST_VOCALS_MAX = 1,01`.
- Danh mục **85fbdcd414d4** (Lead đã deploy):
  - 12 danh sách nới lại, ví dụ fantasy_calm 125 bài / 1.091 phút, sleep 107 / 1.018, scifi 73 / 530, mystery 83 / 428;
  - eastern 36 / 108.
- Đọc: điểm `vocals` zero-shot của CLAP gần như không tách được bài có hát ở danh mục này. 90 % bài nó đẩy lên > 0,5 là
  bài không lời.

**GHI TRƯỚC - NHÃN LỜI HÁT MF THAY BỘ LỌC VOCALS CỦA DANH MỤC (03-10 17:3x, Lead giao; trước lượt chạy):**
- Kho gán nhãn, mỗi bài một nhãn MF:
  - (R) 1.254 bài bị loại CHỈ vì CLAP vocals > 0,5: không phải Incompetech, có giấy phép, không field / noise, có file.
  - (I) 345 bài Incompetech có vocals > 0,5, đang được miễn.
- Cách gán: đúng quy trình (2) đã qua cổng. Hai đoạn 30 giây (25 % / 60 %), hai cách hỏi a / b; bài có hát nếu đoạn nào
  có p_hát ≥ 0,5. Không đổi prompt, không đổi ngưỡng.
- Áp vào `build_catalog.py`, nhãn ở `mf_vocals.jsonl`:
  - bài vocals > 0,5 (mọi nguồn) mà MF nói KHÔNG LỜI → giữ;
  - MF nói CÓ HÁT → loại, kể cả Incompetech;
  - bài chưa có nhãn MF → luật cũ (CLAP 0,5, Incompetech miễn).
- Báo:
  - số bài trả lại, số bài Incompetech bị loại;
  - cỡ danh mục và 25 ô;
  - danh sách phát sau dựng lại (≥ 40 phút);
  - revision mới cho Lead deploy.
- Kiểm chéo, ghi lại không quyết: 30 bài S5 của (2) có trong (R) thì nhãn mới phải trùng nhãn cũ (cùng đoạn, cùng prompt).

**KẾT QUẢ NHÃN LỜI HÁT MF CHO DANH MỤC (03-10 18:4x, `results/mfv_label.txt`, nhãn ở `mf_vocals.jsonl`):**
- Đã gán nhãn đủ 1.599 bài, 6.396 lượt MF, chạy 17:20–18:44 trên card nhà.
- (R) 1.254 bài bị loại vì CLAP > 0,5: 300 bài có hát (24 %) → **trả lại 954 bài không lời**.
- (I) 345 bài Incompetech đang được miễn: **loại 8 bài có hát**.
- Kiểm chéo với 26 bài S5 của (2): trùng nhãn 26/26.
- Danh mục mới **fd5679c5c32c**: 2.415 bài (trước 2.087).
  - Bỏ: vocals_mf 308, CLAP vocals (chưa có nhãn MF) 174, field 130, short 224, fill 1.507.
  - Nhiều bài trả lại rơi vào phần "fill" vì ô đã đầy.
  - Cả 25 ô đều tăng; ô 0_0 21 → 37, ô 4_0 15 → 27.
- Danh sách phát (bài / phút):
  - fantasy_adventure 150 / 458; fantasy_calm 150 / 1.171; school_light 150 / 565; romance 137 / 887;
  - comedy 150 / 505; action 150 / 504; horror 150 / 598; mystery 86 / 444;
  - eastern 34 / 103; scifi 90 / 633; sad 150 / 693; sleep 146 / 1.218.
- Còn lại: khoảng 550 bài không phải Incompetech chưa có bản sao archive.org, chủ yếu là bài vừa trả lại. Link gốc vẫn
  dùng được. Đăng bản sao khi hàng tác vụ của archive.org thông (đang ~1.000 tác vụ chờ từ 02-10).
- Bài mới vào danh mục sau này chưa có nhãn MF thì vẫn theo luật CLAP 0,5, cho tới khi được gán nhãn.

**GHI TRƯỚC - NGƯỠNG LỜI HÁT CỦA CẢ DANH MỤC (03-10 15:3x; trước khi có số AST nào ngoài 55 bài đầu đã bỏ):**

Câu hỏi: `vocals` (CLAP zero-shot) trong khoảng 0,3–0,5 có thật là có tiếng hát không?
- Danh mục chỉ loại bài > 0,5 (Incompetech được miễn), còn chọn nhạc theo cảnh vẫn nhận các bài này.

Đo:
- AST (cùng lượt chạy với phép A ở trên), trên MỌI bài của danh mục 64f4a577f86b.
- `Singing_max` = xác suất "Singing" cao nhất trong ba cửa sổ 10 giây.
- Bài **có tiếng hát theo AST** nếu `Singing_max` ≥ 0,3.

Nhóm theo `vocals`, chỉ bài không phải Incompetech: < 0,1 / 0,1–0,3 / 0,3–0,5.

Luật:
- **ĐỀ XUẤT hạ `VOCALS_MAX` xuống 0,3 cho cả danh mục** nếu tỉ lệ có tiếng hát ở nhóm 0,3–0,5 ≥ 25 % VÀ ≥ 2 × nhóm < 0,1.
- Kèm số bài mất ở mỗi ô vui/buồn × êm/dồn dập (25 ô).
- Lead / chủ sách quyết. Không đạt → giữ 0,5; 0,3 chỉ áp cho "Nghe ngay".

Ghi lại, không phải thước:
- tỉ lệ có tiếng hát của bài Incompetech theo từng nhóm `vocals`, vì nguồn này đang được miễn;
- `Speech` trung bình mỗi nhóm.

**KẾT QUẢ NGƯỠNG LỜI HÁT (03-10 16:1x, `results/vocals_check.txt`): KHÔNG KẾT LUẬN ĐƯỢC. Giám khảo trượt chứng dương.**
- Theo đúng luật: 0/2.087 bài có `Singing_max` ≥ 0,3, mọi nhóm (kể cả 345 bài Incompetech > 0,5). Luật cơ học ra "giữ 0,5".
- **Chứng dương (THÊM SAU KHI THẤY SỐ):** AST trên 30 bài đã bị loại có tên chỉ rõ có hát ("sung by Po Sun Yi" ×5,
  "feat. …" ×3, …). 0/30 đạt 0,3. Bài hát thật chỉ được 0,03–0,30.
  - Vậy ngưỡng 0,3 ghi trước quá cao so với thang của AST. Phép này **không** chứng minh được điều gì về ngưỡng 0,5.
- Thăm dò, NHÌN SAU KHI THẤY SỐ, không phải thước:
  - Ở `Singing_max` ≥ 0,05, ~6/7 bài có tên chắc chắn có hát vượt.
  - Bài không phải Incompetech: nhóm < 0,1 có 1 %, nhóm 0,1–0,3 có 7 %, nhóm 0,3–0,5 có 5 %. Incompetech > 0,5: 2 %.
  - 30 bài CLAP chấm vocals ≈ 1 mà bị loại: nhiều tên rõ là không lời ("Ambient Relaxing Loop", "St. Antoine
    Shakuhachi", "Inside Union Station-Chinese Harp").
  - Đọc: `vocals` (CLAP zero-shot) có vẻ báo nhầm nhiều. Bộ lọc 0,5 có thể đang loại cả bài không lời, còn siết
    "Nghe ngay" theo 0,3 thì loại chủ yếu bài không lời. Danh sách vẫn ≥ 40 phút, chỉ bớt đa dạng.
- Muốn quyết, cần một phép mới ghi trước:
  - Tập kiểm có nhãn: bài có hát / không lời theo tên và nguồn, chọn trước khi chấm.
  - Ngưỡng AST học trên tập ấy.
  - Rồi đo tỉ lệ báo nhầm của CLAP `vocals` ở ngưỡng 0,5 và 0,3 trên danh mục, cùng số bài lấy lại được.
  - Chưa đổi gì.

## Nguồn nhạc: giữ / loại và lý do (02-10, Lead + chủ sách - đọc trước khi hỏi lại)

LUẬT CUỐI (02-10 22:xx, Lead + chủ sách; thay đoạn ba câu hỏi bên dưới ở chỗ nào khác nhau):
- **Giấy phép:** mọi giấy phép đều dùng được (NC, ND, giấy phép riêng). Bài NC mang cờ `nc`.
- **Tải được ở mọi máy:** mọi bài trong danh mục phải tải được trên máy bất kỳ, nên KHÔNG có `localOnly`. Trang cấm link thẳng
  thì không vào danh mục chung.
- **Bản sao archive.org:** chỉ tạo khi giấy phép cho phân phối lại. Ngược lại thì gắn `noMirror` và chỉ dùng link gốc.
- **Cách lấy:** theo điều khoản từng trang. Có API thì dùng API, không thì tải tay. Trang cấm thu tự động thì tuyển tay một
  tập nhỏ.
- **Không xin phép:** không gửi thư xin phép (chủ sách không muốn).
- **甘茶の音楽工房 LOẠI:** cấm link thẳng, cấm 2次配布 nên không có bản sao. Ô 和風 lấp bằng Silverman / 魔王魂 / DOVA
  (tuyển tay, link gốc, `noMirror`).
- **Máy không tải được bài:** chọn bài kế, không im lặng vô cớ. Nhánh `dev/music-gems` làm phần này.

LUẬT (02-10 khuya, thay luật chặt hơn cùng ngày - chủ sách: đừng loại quá khắt khe như lần Freesound): tách ba câu hỏi.
(1) GIẤY PHÉP của tác phẩm quyết định có dùng được không: CC0 / CC BY / CC BY-SA / CC BY-NC dùng được (app miễn phí, phi
thương mại; ghi `license` để lọc nếu sau này thương mại hoá). ND chưa rõ (trộn dưới lời đọc có thể là phái sinh) - mặc định
không dùng tới khi Lead quyết. CC cấm thêm điều kiện, nên lời "đừng đăng lại" của tác giả không lấy mất quyền CC.
(2) CÁCH LẤY theo điều khoản trang: có API / tải tay thì làm; trang cấm tự động thì tuyển tay một tập nhỏ giá trị cao và xin
phép (Lead nhờ chủ sách gửi thư), KHÔNG tự loại.
(3) MONG MUỐN tác giả (không đăng lại, không hotlink): tôn trọng bằng `no_mirror` hoặc không gọi thẳng link gốc; không loại
hẳn vì lý do này. App tải `link` trước, bản sao archive.org (`mirrors`, kiểm sha1) là dự phòng.

| nguồn | (1) giấy phép | (2) cách lấy | (3) mong muốn | quyết định |
|---|---|---|---|---|
| Incompetech (Kevin MacLeod) | CC BY 4.0 | tải thẳng | - | GIỮ, có mirror |
| Jamendo (qua Openverse) | CC BY (NC nay cũng được) | Openverse API | không cache theo điều khoản API Jamendo | GIỮ, có mirror (chủ sách duyệt 02-10); bài NC: thu lại nếu Lead gật |
| Freesound | CC0 / CC BY (NC nay cũng được) | API | - | GIỮ, có mirror |
| OpenGameArt | CC0 / CC BY / OGA-BY (BY-SA nay cũng được; GPL không) | trang | - | GIỮ, mirror; chỉ lấp ô thiếu |
| Scott Buckley | CC BY 4.0 | trang | không đăng lại lên nền tảng stream nhạc | GIỮ, `no_mirror`; chỉ lấp ô thiếu |
| FreePD | CC0 | archive.org | trang đã đóng | GIỮ; link chính = bản sao của ta (archive.org/freepd chuyển tới máy chủ hỏng 02-10) |
| ccMixter | CC0 / BY / BY-NC (Sampling+ và ND không) | API công khai (chỉ cấm làm quá tải) | - | THU (Đông Á) |
| FMA | từng bài (BY / BY-NC / SA; ND không) | site cấm "data mine" -> metadata từ bộ dữ liệu FMA (CC BY), audio lấy từng file trong fma_full.zip của bộ dữ liệu bằng HTTP range | - | SAU ccMixter: Asia-Far East 53 dùng được (43 NC) + 109 có từ khoá Đông Á |
| Silverman Sound | CC BY 4.0 | VƯỚNG: T&C §11 cấm "data mining, extraction" | "can't redistribute ... as standalone audio" -> `no_mirror` | tuyển tay ~10-20 bài Đông Á + thư xin phép |
| 魔王魂 | CC BY 4.0 ("クリエイティブ・コモンズ 表示 4.0") | không nêu -> tuyển tay ~8-15 bài 和風 | "曲単品を再配布するのはNG" -> `no_mirror`; cấm đưa vào AI tự soạn nhạc (ta không làm) | tuyển tay, link gốc; thư xin mirror |
| 甘茶の音楽工房 | riêng: BGM web / game được | "音楽素材の直リンクでの使用は禁止" - app tải link gốc là vi phạm | cấm 2次配布 | chỉ đi được bằng thư xin phép |
| DOVA-SYNDROME / OpenTracks | riêng; "ツール・プラットフォームへの組み込み" phải hỏi | không API | - | thư xin phép |
| Senses Circuit | riêng; cấm dùng cho AI (từ 26-09) | - | - | GIỮ LOẠI tới khi đọc kỹ (ta chạy CLAP suy diễn, không huấn luyện) |
| Pixabay Music | Pixabay Content License (không phải CC) | cấm thu thập hàng loạt | cấm phát lại standalone | chưa xét lại (tuyển tay + thư nếu cần) |
| 공유마당 국악 BGM | CC BY (đã kiểm 1 mục) | API data.go.kr cần tài khoản + khoá (chủ sách tạo) | - | sau ccMixter / FMA |

## Thứ tự và tài nguyên

0. Dữ liệu (đang chạy): Incompetech 1.443 bài (đọc 3 đoạn từ máy chủ), Jamendo CC BY 665 bài; tải Film soundtracks,
   DEAM, PMEmo, GlobalMood (kiểm giấy phép từng bộ - chỉ để đo, không phát hành).
1. Bake-off model nhạc - CPU / hàng GPU nhà ngoài giờ êm; tín dụng Modal khi cần nhiều.
2. Đáp án cảnh: 2-3 chương mỗi thể loại (LN Nhật, tiên hiệp, Tam quốc / Đông Chu, truyện Việt) rồi đo A / B / C.
3. Ghép, 4. trộn - sau khi 1 và 2 có kết quả.

Mỗi pha xong: ghi số vào đây, đổi tham số trong app theo kết quả, nói rõ cái gì đã đo và cái gì còn là đường cơ sở.
