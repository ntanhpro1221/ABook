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
- Chờ chủ sách: tài khoản Cloudflare (
 ⛅️ wrangler 4.146.0
────────────────────
Attempting to login via OAuth...
Opening a link in your default browser: https://dash.cloudflare.com/oauth2/auth?response_type=code&client_id=54d11594-84e4-41aa-b438-e81b8fa78ee7&redirect_uri=http%3A%2F%2Flocalhost%3A8976%2Foauth%2Fcallback&scope=k2.read%20k2.write%20account%3Aread%20user%3Aread%20workers%3Awrite%20workers_kv%3Awrite%20workers_routes%3Awrite%20workers_scripts%3Awrite%20workers_tail%3Aread%20d1%3Awrite%20pages%3Awrite%20zone%3Aread%20ssl_certs%3Awrite%20ai%3Awrite%20ai-search%3Awrite%20ai-search%3Arun%20agent-memory%3Awrite%20queues%3Awrite%20pipelines%3Awrite%20secrets_store%3Awrite%20artifacts%3Awrite%20flagship%3Awrite%20containers%3Awrite%20cloudchamber%3Awrite%20connectivity%3Aadmin%20email_routing%3Awrite%20email_sending%3Awrite%20browser%3Awrite%20challenge-widgets.write%20offline_access&state=vKISkfIq2w2Evdw9Kjib31H6FpRUJY-c&code_challenge=BD2BVWA7WIcythy-25LT0Wtw3BbcRGQhVp_2AmLmqvw&code_challenge_method=S256) và archive.org (khoá S3 để đăng bản dự phòng).

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

## Thứ tự và tài nguyên

0. Dữ liệu (đang chạy): Incompetech 1.443 bài (đọc 3 đoạn từ máy chủ), Jamendo CC BY 665 bài; tải Film soundtracks,
   DEAM, PMEmo, GlobalMood (kiểm giấy phép từng bộ - chỉ để đo, không phát hành).
1. Bake-off model nhạc - CPU / hàng GPU nhà ngoài giờ êm; tín dụng Modal khi cần nhiều.
2. Đáp án cảnh: 2-3 chương mỗi thể loại (LN Nhật, tiên hiệp, Tam quốc / Đông Chu, truyện Việt) rồi đo A / B / C.
3. Ghép, 4. trộn - sau khi 1 và 2 có kết quả.

Mỗi pha xong: ghi số vào đây, đổi tham số trong app theo kết quả, nói rõ cái gì đã đo và cái gì còn là đường cơ sở.
