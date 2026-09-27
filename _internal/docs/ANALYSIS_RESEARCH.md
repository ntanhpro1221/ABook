# Chương trình nghiên cứu model phân tích

Chủ sách, 27-09: *"model phân tích là linh hồn quan trọng nhất, cực kỳ quan trọng của project này. bạn phải nghiên cứu
cực kỳ sâu để tận dụng mọi nguồn kiến thức, thử nghiệm mọi cách."*

Model phân tích quyết định mỗi câu do AI đọc: người nói (-> giọng), loại đoạn (kể / thoại / nội tâm), cảm xúc, cường độ,
nhịp, âm lượng, giới tính. Sai người nói là lỗi người nghe nhận ra ngay (giọng sai người). Tài liệu này là bản đồ: mục
tiêu, cách đo, tài liệu đã/phải đọc, và MA TRẬN THÍ NGHIỆM với trạng thái. Chi tiết số đo từng lượt ở `LLM_EVAL.md`.

## Luật làm việc (rút từ sai lầm)

1. **Đọc tài liệu trước khi thiết kế.** 26-09 tôi chọn QLoRA sinh tên mà không tra "quotation attribution" - hướng tốt
   nhất hiện nay (8/2026) là bộ mã hoá chấm điểm ứng viên, không phải sinh văn bản.
2. **Đo theo cặp trên cùng chương, trên tập test tách theo chương.** Độ đúng người nói của CÙNG một model dao động
   51,5-84,6% theo chương (21-09): chọn chương chi phối mạnh hơn chọn model. Công cụ: `scripts/model_eval/paired.py`.
3. **Ghi cả kết quả âm.** Mỗi thí nghiệm: câu hỏi, cấu hình, số đo, kết luận, commit.
4. **Tập test không bao giờ lọt vào huấn luyện**: TMA 351 363 378 381 + young_masters_pov 248
   (`scripts/model_eval/build_training_set.py`, `SPLIT`).

## Cách đo

- Đáp án chuẩn: 43 chương / 10 truyện (`scripts/model_eval/gold/`, `docs/GOLD_GUIDE.md`), Claude làm, phân xử theo
  `gold/ADJUDICATION.md`.
- Điểm: `score_models.py` (tổng có trọng số + từng trục: người nói, loại, cảm xúc, ...); so model: `paired.py`.
- Nên thêm (theo PDNC): tách độ đúng người nói theo KIỂU câu thoại - tường minh ("Lucien nói"), đại từ ("hắn nói"),
  ngầm (không có dấu hiệu) - vì mỗi hướng mạnh/yếu ở kiểu khác nhau.

## KẾT QUẢ CHÍNH 27-09 14:3x - phép so đúng với tình huống thật của app

TMA làm truyện MỚI với bộ chấm (không một nhãn TMA nào): học trước PDNC -> gold 9 truyện khác -> tự học trên 150 chương
TMA không nhãn (nhãn tạm cân từng lớp, xếp theo margin, trọng số "không ai" x3). Chấm chính thức từng câu:

| hệ | 847 câu gold TMA | 143 câu 4 chương test TMA |
|---|---|---|
| **bộ chấm + tự học theo cuốn** | **84,9%** (không ai 62,2%) | **82,5%** |
| bộ chấm, đối chứng cùng số epoch, không tự học | 82,2% (không ai 34,5%) | 76,9% |
| LoRA 27-09 (ĐÃ học trên các chương TMA có nhãn) | - | 76,9% (p 0,20) |
| qwen3:8b (model sản xuất) | - | 68,5% (**p 0,001**) |
| qwen3:4b | - | 68,5% (p 0,005) |

Tự học so với đối chứng trên 847 câu: 43 câu chỉ tự học đúng, 20 ngược lại, **p = 0,005**. Phần lợi nằm ở người kể/NPC
(34,5% -> 62,2%); trọng số x3 MỘT MÌNH không giúp (81,7%), chỉ khuếch đại nhãn tạm "không ai" của chính cuốn sách.
Tự học chọn nhãn tạm theo xác suất (bão hoà) thì CÓ HẠI (vòng 2: 80,0%, p 0,02) - cách chọn nhãn tạm là tất cả.

**ĐÍNH CHÍNH (27-09 15:0x) - bảng trên chấm DỄ DÃI ở câu "không ai", con số cho app nhỏ hơn.** `--official` coi lựa chọn
"không ai" của bộ chấm là đúng nếu gold nhận BẤT KỲ nhãn người kể/NPC nào; cách chấm chính thức của dự án (score_models)
thì NARRATOR và NPC* là hai giọng khác nhau, và trong app "không ai" phải thành MỘT giọng cụ thể. Bộ chấm không đặt được
nhãn ấy - đơn vị đúng để đo là HỆ KẾT HỢP: bộ chấm quyết người nói có tên khi đủ chắc, còn lại theo nhãn của LLM. Chấm
CHẶT trên 143 câu test TMA (ngưỡng tin cậy chọn bằng kiểm chứng chéo bỏ-một-chương):

| hệ | người nói, chấm chặt |
|---|---|
| qwen3:8b một mình | 67,1% |
| **qwen3:8b + bộ chấm tự học** | **74,8%** (+7,7) |
| LoRA 27-09 một mình | 74,8% |
| **LoRA + bộ chấm tự học** | **76,9%** (+2,1) |

Bản tự học có "không ai" x3 đoán "không ai" QUÁ TAY (40/143 câu, 20 trong số đó gold là người có tên) - dưới cách chấm dễ
dãi nó trông tốt nhất, dưới cách chấm chặt thì bản cân lớp không x3 kết hợp tốt hơn. Lợi thật cho app: ~+8 điểm so với
model sản xuất hiện tại, ~+2 so với LoRA; phần còn lại nằm ở quyết định giọng người kể vs NPC (chưa ai làm tốt).

Công cụ `combine_eval.py` (chấm chặt hệ kết hợp, θ kiểm chứng chéo, McNemar với LLM một mình), 143 câu test TMA:
qwen3:8b 67,1% -> + bộ chấm đối chứng (chưa từng thấy TMA, không tự học) **74,8% (15 vs 4, p 0,02)**, + bộ chấm tự học
74,8% (20 vs 9, p 0,06); LoRA 74,8% -> 75,5% / 76,9% (không đáng kể). **Trong hệ kết hợp tự học gần như không thêm gì**:
lợi của nó nằm ở câu người kể/NPC, phần mà hệ kết hợp giao cho LLM. Thứ tự thay đổi đáng làm cho app: (1) thay
qwen3:8b bằng LoRA (+7,7 người nói, +9 cảm xúc, nhanh gấp đôi); (2) N7b "tôi là ai" cho truyện ngôi thứ nhất (~30% ->
?); (3) bộ chấm cho câu có tên (+2 trên nền LoRA).

## KẾT QUẢ LỚN NHẤT 27-09 15:2x - MỘT DÒNG PROMPT cho truyện ngôi thứ nhất (chi tiết docs/LLM_EVAL.md)

YMP 248: cho LLM biết "người kể xưng 'tôi' là SAMAEL" -> **LoRA 34,0% -> 89,4% người nói** (điểm tổng 67,3 -> 87,8),
qwen3:8b 31,9% -> 61,7%. Người kể suy được KHÔNG cần gold (N7b). Đây là thay đổi đáng làm NHẤT cho app: lớn hơn mọi cải
tiến bộ chấm ở trên, và chỉ cần một câu hỏi/gợi ý trong Studio + một dòng prompt.

Đoán người kể TỪ VĂN BẢN THÔ lúc nhập sách (`narrator_raw.py`: ứng viên = cụm viết hoa không đứng đầu câu, 40 chương đầu)
KHÔNG đủ tin để tự áp: Love Unseen -> "Sorano" (họ của Kakeru - đúng), Yamiyo -> "Tomobe-san" (đúng), 5 truyện ngôi thứ ba
đều không đoán bừa (tỉ lệ "tôi" 7-23%), nhưng YMP -> "Portal" (sai): 40 chương đầu YMP nhắc "Samael" 103 lần trong LỜI KỂ
(giả định "người kể không tự gọi tên mình" chỉ đúng ở các chương sau). Thiết kế cho app: phát hiện truyện ngôi thứ nhất
bằng tỉ lệ "tôi" trong lời kể (phần này đáng tin), GỢI Ý các tên hay gặp nhất, chủ sách chọn MỘT lần trong Studio, khoá
như cài đặt của sách; hoặc suy bằng N7b theo sổ nhân vật sau vài chương đầu rồi phân tích lại các chương ấy.

## Phát hiện 27-09 17:2x - giá trị thật của bộ chấm có thể là ĐO ĐỘ KHÔNG CHẮC

Độ tin cậy do LLM tự báo gần như vô dụng để biết câu nào cần người duyệt: trên Tập 18 (sản xuất) câu thoại trung bình
0,91, chỉ 14/1.157 câu dưới 0,8 - nó quá tự tin. Bộ chấm ứng viên thì hiệu chỉnh tốt (tin cậy >= 0,95 đúng 100%, < 0,5
đúng 33%). Trong hệ kết hợp nó chỉ thêm +2 điểm độ đúng trên nền LoRA, nhưng cho hộp "Việc cần anh" (docs/STUDIO_REVIEW.md)
nó là nguồn xếp hạng tốt nhất: chỉ ra ĐÚNG câu nào người nên nghe lại. **ĐÃ ĐO (27-09 17:3x, `quote_scorer/review_curve.py`, 143 câu test TMA, chấm chặt):**

| người duyệt | 10% câu | 20% | 30% | 50% |
|---|---|---|---|---|
| LoRA một mình 74,8% -> xếp theo bộ chấm (bất đồng chắc trước) | 80,4% | **84,6%** | **89,5%** | **98,6%** |
| ... xếp theo tin cậy LLM tự báo | 75,5% | 79,7% | 83,2% | 88,1% |
| ... ngẫu nhiên (500 lần) | 77,3% | 79,9% | 82,4% | 87,4% |
| ... trần (câu sai trước) | 84,6% | 95,1% | 100% | 100% |
| qwen3:8b một mình 67,1% -> bộ chấm / LLM tự báo / ngẫu nhiên, duyệt 20% | | 81,1 / 72,7 / 73,7% | | |

Tin cậy LLM tự báo KHÔNG hơn ngẫu nhiên; bộ chấm cho lợi gấp ~2 lần ngẫu nhiên. **Đổi quyết định 17:0x "gác bộ chấm"**:
vai của nó là CHỌN CÂU CHO NGƯỜI DUYỆT trong hộp "Việc cần anh" - chỉ xếp hạng, không đổi nhãn, nên chạy được phía
Studio (đọc SQLite chỉ đọc) mà không đụng file khoá/dấu vân tay của dây chuyền. Cần: suy luận mmBERT trong runtime app.
Cũng 27-09: 3 câu mở đầu bằng lời gọi ("Heidi, các cậu đi đâu vậy?") vẫn bị gán cho chính người được gọi - luật host
"tên trong lời gọi là người nghe" (AGENTS.md) còn lọt; hộp việc bắt được bằng một luật chữ đơn giản.

## Công thức đầy đủ trên 10 truyện chưa thấy (27-09 17:3x) - tự học theo cuốn: DỪNG

Mỗi truyện lần lượt làm truyện MỚI (học trước PDNC -> gold 9 truyện kia), 1.827 câu, chấm gold đầy đủ (`--official`):
m0 **73,3%** (có tên 77,1%, không ai 38,5%); đối chứng +2 epoch gold 72,7%; tự học trên chính truyện mới 72,1%
(107 câu chỉ m0 đúng vs 85 chỉ tự học đúng, p 0,13). Kết quả vòng TMA (84,9 vs 82,2, p 0,005) KHÔNG lặp lại trên truyện
khác - tự học theo cuốn dừng hẳn. Quan trọng hơn: **độ đúng theo truyện chênh cực lớn** - m0: Two Childhood Friends 42,9%,
Hướng dẫn sinh tồn 47,3%, Yamiyo 56,5%, Nise 57,8%, Năng lực bá đạo 65,6%, Love Unseen 68,0%, Nageki 71,4%, YMP 72,6%,
Đã bảo là 74,0%, TMA 83,8%. Trung bình che mất những truyện model còn rất yếu - đúng yêu cầu chủ sách 27-09 "nhiều thể
loại, phong cách, trình độ viết": luôn báo theo truyện, và gold/huấn luyện phải phủ những kiểu viết đang yếu.

## CỔNG TAM QUỐC 27-09 21:xx - giữ qwen3:8b; LoRA mất phần lớn điểm vì VIẾT SAI TÊN, không phải vì nhận sai người

Cổng đổi model: Tam quốc diễn nghĩa (Phan Kế Bính) Hồi 50-52, 219 câu thoại gold - truyện chưa từng thấy, khác hẳn thể
loại tập huấn luyện. Luật đổi model (v2 >= qwen3:8b) không đạt -> **giữ qwen3:8b làm mặc định**. Kết quả đủ 3 hồi
(22:19, `score_models`):

| model | điểm | người nói | cảm xúc | giây |
|---|---|---|---|---|
| qwen3:8b | **87,2** | **79,2** | 88,7 | 2.748 |
| LoRA v2 | 72,9 | 43,2 | 95,1 | 1.809 |
| LoRA v1 | 64,0 | 30,1 | **95,3** | 1.825 |

v2 hơn v1 rõ (+13 người nói), cảm xúc của cả hai LoRA vẫn hơn qwen3:8b 6 điểm, nhanh hơn 1,5 lần - chỉ trục người nói
kéo tụt, và phần lớn vì chính tả tên (dưới).

Mổ lỗi (`scratchpad/tamquoc_errors.py`, `tamquoc_folded.py`): phần lớn câu LoRA "sai" là **nhân vật đúng, chuỗi tên sai**:

- Rơi dấu: `HOANG CAI`, `KHONG MINH`, `LO TUC`, `HUYEN-THUC` (đáp án Hoàng Cái, Khổng Minh, Lỗ Túc...). Chấm lại bỏ qua
  dấu và gạch nối (`scripts/model_eval/name_form.py`, câu thoại, đủ 219 câu):

  | model | chặt | bỏ qua dấu | 050 | 051 | 052 |
  |---|---|---|---|---|---|
  | qwen3:8b | 79,5% | 79,5% | 65,0 / 65,0 | 80,5 / 80,5 | 89,0 / 89,0 |
  | LoRA v2 | 43,4% | **76,3%** | 63,3 / **75,0** | 63,6 / 77,9 | **9,8** / 75,6 |
  | LoRA v1 | 30,1% | 67,1% | 48,3 / 61,7 | 36,4 / 66,2 | 11,0 / 72,0 |

  qwen3:8b chép tên đúng như văn bản nên không mất gì. v2 mất 33 điểm chỉ vì chính tả; bỏ qua dấu thì v2 kém qwen3:8b
  3,2 điểm, và **hơn nó 10 điểm ở hồi 50**. Lỗi theo CHƯƠNG, không theo câu: hồi 52 v2 viết gần như MỌI tên không dấu
  (chặt 9,8%, bỏ dấu 75,6%) - một khi bắt đầu rơi dấu trong một chương, nó rơi đến hết chương.
- Tên ngắn thay tên đủ (v2 hồi 52): `TUC` 16 câu, `VAN` 8, `DU` 5, `PHAM` 5 - model chép chữ gọi tại chỗ ("Túc nói")
  thay tên đủ (Lỗ Túc, Triệu Vân, Chu Du, Triệu Phạm); qwen3:8b viết tên đủ. Có cả phiên âm lạc: `DIAO VINH` (Đạo-vinh).
- Tên tự thay tên chính: "Triệu Tử-long" cho Triệu Vân, "Cam Hưng-bá" cho Cam Ninh - model chép đúng chữ trong câu
  ("Ta là Triệu Tử-long"), đáp án dùng tên chính.
- Dữ liệu huấn luyện KHÔNG bỏ dấu (18% nhãn là tên có dấu: HẠ TỬ CƯỜNG, DẠ OANH...). Nghi phạm: nhãn tên viết IN HOA.
  Chữ Việt in hoa có dấu hiếm trong dữ liệu tiền huấn luyện; bị ép in hoa, model 4B hay rơi dấu với tên chưa gặp.
  qwen3:8b không bị ép in hoa nên viết đúng.

Hệ quả trong dây chuyền thật: `HOANG CAI` không khớp nhân vật "Hoàng Cái" -> thành nhân vật MỚI, giọng khác - lỗi người
nghe nghe ra, không chỉ là lỗi bộ chấm.

Việc kế (theo thứ tự lợi):
1. **Neo tên vào văn bản gốc** (host, lợi cho MỌI model): tên người nói không có nguyên văn trong chương mà khớp DUY NHẤT
   một tên trong chương khi bỏ dấu/gạch nối -> thay bằng đúng chữ trong văn bản; rồi tên ngắn là đuôi của DUY NHẤT một
   tên đủ đã biết (sổ nhân vật / cùng chương) -> tên đủ. Trần đo được: v2 43,4% -> 76,3% trên Tam quốc (chưa tính phần
   tên ngắn). Nằm trong `analysis.py` (file khoá) -> làm ở nhánh dev, đo bằng replay trên gold, khi hàng GPU rảnh; phải đo
   cả phần PHÁ (tên ngắn trùng đuôi hai người, "Phạm" / "Triệu Phạm").
2. **Huấn luyện lại với tên giữ nguyên dạng văn bản** (không in hoa; host lo so không phân biệt hoa thường) - kiểm giả
   thuyết in hoa.
3. **Thêm truyện tên thuần Việt/Hán Việt vào gold** (đa thể loại, xem mục "Bộ phân tích phải đa thể loại").
4. Tên tự/tên gọi tắt (Tử-long = Triệu Vân, Du = Chu Du): cần sổ bí danh theo truyện - câu hỏi riêng.

## MỘT NGƯỜI MỘT GIỌNG 27-09 23:xx - chấm thứ người nghe nghe, không chấm chữ trên nhãn

**Đính chính mục trên:** "`HOANG CAI` thành nhân vật MỚI, giọng khác" là SAI phần lớn. Trước khi khoá giọng, sổ nhân vật
đã gom tên (`character_registry`): bản rơi dấu về bản đủ dấu (`merge_dropped_mark_variants`), "tên + họ bịa" về tên,
tên vắng mặt trong sách về tên có mặt. Một người viết lúc có dấu lúc không vẫn là MỘT giọng; chỉ viết không dấu suốt thì
là một giọng mang tên xấu trong danh sách nhân vật (lỗi hiển thị cho chủ sách, không phải lỗi người nghe). Nhãn chặt
(`score_models`) chấm CHỮ; người nghe nghe GIỌNG.

Thước mới `scripts/model_eval/voice_identity.py`: nhãn của model qua ĐÚNG các lượt gom tên của dây chuyền (gọi thẳng
`character_registry.canonical_speaker_names`, gộp các chương đo như một cuốn), rồi chấm câu thoại theo cụm bằng B-cubed
(Bagga & Baldwin 1998): độ chính xác thấp = hai người chung giọng, độ phủ thấp = một người hai giọng. `--gold-check` chạy
các lượt gom trên chính nhãn đáp án của 11 truyện - gom hai người khác nhau làm một là phá.

F1 giọng (trước luật tên gọi dưới đây; YMP có dòng người kể "tôi = SAMAEL" như Studio hỏi):

| bộ test | qwen3:8b | LoRA v1 | LoRA v2 | nhãn chặt qwen / v2 |
|---|---|---|---|---|
| TMA 351 363 378 381 (156 câu) | 55,8 | 60,2 | 59,8 | 65,4 / 75,0 |
| YMP 248 có người kể (47 câu) | 56,1 | 79,7 | **82,8** | 61,7 / 91,5 |
| Tam quốc 50-52 (219 câu) | 69,2 | 68,7 | **71,1** | 79,5 / 43,4 |

Trên Tam quốc, nhãn chặt nói qwen3:8b hơn v2 36 điểm; giọng nói v2 hơn 1,9. Khoảng cách gần như toàn là chính tả.

Lỗi giọng lớn nhất của CẢ BA model trên Tam quốc: gọi người bằng TÊN (chữ cuối) - "DU" 16-24 câu cho Chu Du, "THÁO"
17-18 câu cho Tào Tháo, "NHÂN" cho Tào Nhân - dây chuyền chưa gom loại này (luật "họ bịa" chỉ gom tên kiểu Âu, chữ
ĐẦU). Luật mới `character_registry.merge_given_names` (nhánh dev/given-names): nhãn một chữ là chữ CUỐI của đúng một tên
nhiều chữ trong sổ -> tên ấy; chỉ tên kiểu Việt/Hán Việt (mọi chữ là âm tiết tiếng Việt - tên kiểu Âu thì chữ cuối là
HỌ chung cả nhà); nhãn không dấu so theo chữ bỏ dấu, có dấu so đúng dấu; bỏ qua tước đứng sau tên (lão, ca, huynh, gia...).

| Tam quốc, F1 giọng | trước | sau | 050 | 051 | 052 |
|---|---|---|---|---|---|
| qwen3:8b | 69,2 | **74,8** | 74,7 -> 74,7 | 69,7 -> 76,0 | 76,9 -> 80,7 |
| LoRA v2 | 71,1 | 74,2 | 73,8 -> 78,7 | 76,7 -> 79,9 | 72,2 -> 73,8 |
| LoRA v1 | 68,7 | 74,6 | 77,0 -> 78,5 | 84,6 -> 89,0 | 68,9 -> 69,1 |

Độ phủ +8 đến +10, độ chính xác -0,5 đến -1,4 (vài câu gán nhầm tên gọi đi theo người mang tên ấy). Không chương nào
tụt. TMA, YMP: không đổi (tên kiểu Âu/Nhật - luật không chạm). `--gold-check`: 11 truyện không nhập hai người nào. Trên
nhãn của các project sản xuất cũ (cuốn 2 lô 17: 48 nhân vật, các bản alpha): luật không gom gì.

Chữ hiển thị (danh sách nhân vật trong Studio) - luật `restore_source_marks`, lượt cuối, chỉ đổi chữ (một tên thành
một tên): tên mà sách không viết như thế, nhưng bỏ dấu ra khớp ĐÚNG MỘT cách viết tên trong sách (mọi chữ viết hoa đầu;
tên một chữ không tính chỗ đầu câu) -> cách của sách: `HOANG CAI` -> `HOÀNG CÁI`, `KHỐNG MINH` -> `KHỔNG MINH`. Tên
hiển thị đúng đáp án trên Tam quốc: LoRA v2 43,4% -> **71,7%**, v1 30,1% -> 61,6%, qwen3:8b 79,5% (vốn viết đúng); F1
giọng không đổi; TMA, YMP không đổi. Nhân tiện: đếm tên trong sách nhanh 50 lần - `unicodedata.normalize` của CPython
chậm vượt tuyến tính trên chuỗi dài (cuốn 2, 11 triệu ký tự: 21 giây cả cuốn, 0,05 giây từng dòng, kết quả y hệt), và
dựng sổ nhân vật đã trả 21 giây ấy cho mỗi cuốn.

Độ vững: bỏ các câu đáp án là người vô danh (NPC* - không có danh tính để giữ giọng), kết luận giữ nguyên: Tam quốc
qwen3:8b 81,6 / v2 80,7 / v1 79,9; TMA qwen3:8b 59,7 / **qwen3:4b 63,3** / v1 64,4 / v2 64,0 / nền 4B 59,0 / gemma4
e2b 57,6; YMP không đổi (không có câu vô danh). Lạ: qwen3:4b hơn qwen3:8b trên TMA theo giọng ở cả hai cách chấm -
hàng GPU g (tự chạy sau c3) đo qwen3:4b trên Tam quốc và YMP có người kể.

Chuyện chọn model, theo thước giọng + luật mới: v2 thắng 5/8 chương (TMA 2-2, Tam quốc 2-1, YMP 1-0), gộp TMA +4,0,
YMP +26,7, Tam quốc -0,6 (hoà); cảm xúc hơn 6-9 điểm; nhanh 1,5 lần. Cổng "v2 >= qwen3:8b trên truyện chưa thấy" đo bằng
giọng: hoà, không đạt rõ -> **vẫn giữ qwen3:8b**, nhưng lý do đã khác hẳn lúc 21:xx. Việc kế:
1. Gộp luật tên gọi vào dây chuyền (lợi cho mọi model; đổi hash - không lô nào cần resume).
2. Thước chính của mọi phép đo người nói từ nay là F1 giọng; nhãn chặt vẫn báo kèm (tên hiển thị trong Studio).
3. ~~Neo cách viết tên vào văn bản cho phần HIỂN THỊ~~ - xong (`restore_source_marks`, trên).
4. Một truyện chưa thấy nữa, tên thuần Việt (văn học Việt hết bản quyền, wikisource), 2-3 chương gold, chạy lại cổng.
5. Tên tự (Tử-long = Triệu Vân, Công-cẩn = Chu Du): sách Trung giới thiệu bằng "<tên>, tự (là) <tên tự>" ("Bàng Thống
   tự là Sĩ-nguyên", "Hoàng Trung, tự Hán-thăng" - Tam quốc 047, 053) - một luật đọc câu giới thiệu ấy thành sổ bí danh
   theo cuốn; đo được bằng chính các bí danh đáp án Tam quốc đã ghi ("CHU DU,DU,CHU CÔNG-CẨN,...").

## Tài liệu

Đã đọc (27-09):
- Quotation attribution: He, Barbosa, Kondrak 2013 (ACL); Muzny và cs. 2017 (EACL, sàng hai tầng = luật host của ta);
  PDNC - Vishnubhotla, Hammond, Hirst 2022 (LREC; 35.978 câu / 22 tiểu thuyết Anh); Vishnubhotla và cs. 2023
  (arXiv 2307.03734: nút thắt là nhận nhân vật + đồng tham chiếu); SIG (arXiv 2312.14590); prompt learning Trung/Anh
  (arXiv 2408.09452); Michel và cs. NAACL 2025 (Llama-3-8B 89,8% PDNC); **"Fast and Accurate Quotation Attribution in
  Literary Texts" (arXiv 2608.02359, 8/2026): joint scoring ModernBERT-large, 94,5%, nhanh 1.000x, 9,2 GB VRAM**.
- Huấn luyện LLM: LoRA (2106.09685), QLoRA (2305.14314), optimizer 8-bit (2110.02861), gradient checkpointing
  (1604.06174), FlashAttention (2205.14135), chưng cất (Hinton 2015, 1503.02531).
- Bộ mã hoá đa ngữ đọc dài: mmBERT (JHU, kiến trúc ModernBERT, 1.800+ ngôn ngữ có tiếng Việt, 8.192 token).

Phải đọc tiếp:
- "Improving Quotation Attribution with Fictional Character Embeddings" (arXiv 2406.11368) - biểu diễn nhân vật.
- Đồng tham chiếu span-based (Lee và cs. 2017) - nền của joint scoring; coreference tiếng Việt / đa ngữ.
- Nhận dạng cảm xúc trong hội thoại (ERC: MELD, EmoryNLP, COSMIC...) cho trục cảm xúc.
- Chưng cất có lý do (Distilling step-by-step, Hsieh và cs. 2023), tự nhất quán (Wang và cs. 2022), DPO (Rafailov và
  cs. 2023), STaR (Zelikman và cs. 2022), DoRA (2024) - các cách làm mô hình nhỏ tốt hơn với ít nhãn.
- Chú thích văn bản cho TTS biểu cảm / sách nói (prosody, speaking style) - trục nhịp, âm lượng, cường độ.

## Ma trận thí nghiệm

| # | hướng | trạng thái | ghi chú |
|---|---|---|---|
| E1 | LLM có sẵn qua Ollama (qwen3 4b/8b, qwen3.5, gemma4, ministral, lfm2.5, ornith) | 8b/4b đo 21-09 (ngang nhau, 4b nhanh 27%); hàng 6 model 27-09 HỎNG 3 lần ("exit 1" sau 17 s) vì một việc GPU khác giữ VRAM lúc Ollama nạp model (07:24/07:56 huấn luyện LoRA, 11:09 một phép thử bộ chấm) - xếp lại cuối hàng `gpu_queue_27_09b.sh` | đo theo cặp 10 chương |
| E2 | SFT QLoRA Qwen3-4B-Instruct-2507 trên gold (sinh JSON) | **DƯƠNG RÕ (27-09 13:1x)**, 4 chương TMA test so với CHÍNH model nền: thắng 4/4 chương, điểm tổng 86,0 vs 79,3 (Δ +6,6 ± 1,3), người nói 72,8 vs 63,8% (Δ +9,2 ± 2,4), cảm xúc 96,5 vs 87,5%, **nhanh gấp đôi** (1.474 vs 2.952 s - nền nói dài/thử lại nhiều hơn). Chấm từng câu chính thức: LoRA 76,9% vs nền 66,4%, qwen3:8b/4b 68,5%; bộ chấm mốc 79,0% (15 vs 12 câu bất đồng với LoRA, p 0,70), bộ chấm PDNC 84,6%; trần hợp bộ chấm mốc + LoRA 87,4%. **YMP 248 (ngôi thứ nhất): LoRA 28,6%, nền 31,0% người nói** vs bộ chấm 92,9% (bộ chấm được biết "tôi" là ai - N7 suy từ gold = trần; LLM không được biết) -> truyện ngôi thứ nhất cần câu hỏi Studio "'Tôi' là ai?" cho cả LLM lẫn bộ chấm | test TMA là truyện có trong train của LoRA (như bộ chấm) - so với nền là sạch |
| E3 | **Bộ chấm ứng viên người nói bằng encoder** (joint scoring, mmBERT, học trước PDNC rồi tinh chỉnh gold) | cơ sở xong (test 78,4%); học trước PDNC đang chạy | PDNC -> `build_pdnc.py`: 48.810 câu con, 7.598 cửa sổ, 89,2% người nói có trong ứng viên; người kể "I" suy ra đúng cả 4 truyện ngôi thứ nhất (Watson, Hastings, Jake Barnes, Alexis) |
| E4 | Prompt: few-shot lấy ví dụ gần nhất, tự nhất quán (k mẫu + bỏ phiếu), bỏ số lần nhắc | no-counts đo 21-09: không đáng kể | chưa thử few-shot / tự nhất quán |
| E5 | Luật sàng (host) - đo riêng từng luật: sửa bao nhiêu, phá bao nhiêu | có công cụ phát lại (`replay_from_candidates.py`, `gold_replay.py`) | |
| E6 | Kết hợp: encoder cho người nói + LLM cho cảm xúc/nhịp; bỏ phiếu nhiều model | chưa | |
| E7 | DPO trên cặp (đúng / sai của model) nhắm thiên lệch "nhân vật nổi tiếng nhất" | chưa | lỗi BELLAK -> LUCIEN (363:34-36) |
| E8 | Thêm gold (theo nhu cầu, nói rõ mục đích) cho chỗ yếu | chưa | luật "gold theo nhu cầu" 20-09 |
| E9 | Bộ chấm dùng LLM làm bộ mã hoá (Qwen3 0,6-1,7B + LoRA, điểm ứng viên trên trạng thái ẩn; nhân quả nên chỗ nhắc SAU câu thấy câu còn câu không thấy thẻ đứng sau - đầu cặp kết hợp được) | chưa | tiếng Việt của Qwen tốt hơn mmBERT? |
| E10 | Bộ mã hoá lớn hơn: mmBERT chỉ có base (110M ngoài từ vựng) và small; **BGE-M3** (nền XLM-R-large 568M, ngữ cảnh 8.192, MIT) - 8 GB thì phải đóng băng bảng từ vựng 256M như mmBERT | chưa | sau khi chốt học trước + kiểm chứng chéo |

## Hướng MỚI của riêng project (chủ sách 27-09: "nghiên cứu, sáng tạo kiến thức, cải tiến kiến thức có sẵn")

Không chỉ áp dụng bài báo: bài toán của ta khác PDNC ở chỗ (tiếng Việt dịch, truyện mạng hàng nghìn chương, đầu ra là
GIỌNG ĐỌC) - và chính các chỗ khác ấy là chỗ cải tiến được. Mỗi hướng một giả thuyết đo được, đo trên tập test theo cặp:

| # | hướng | giả thuyết | cách đo |
|---|---|---|---|
| N1 | **Che dấu hiệu (distant supervision)**: câu tường minh ("Lucien nói: …") thì luật gán gần như chắc đúng; xoá cụm dấu hiệu -> một câu NGẦM biết chắc đáp án. Làm trên hàng nghìn chương chưa gán nhãn | tăng độ đúng câu ngầm (loại khó nhất: 81-89% ở bài báo) mà không cần thêm gold | train bộ chấm có/không dữ liệu che dấu hiệu, so trên câu ngầm của test |
| N2 | **Đại từ xưng hô tiếng Việt** (ta/ngươi, anh/em, lão phu, tiểu thư, sư huynh…) mã hoá giới, vai vế, quan hệ người nói-người nghe - tín hiệu tiếng Anh không có | giảm lỗi gán sang nhân vật khác giới/khác vai | đặc trưng cặp đại từ trong bộ chấm; đếm lỗi khác giới trước/sau |
| N3 | **Giải mã theo cả hội thoại** (luân phiên A-B-A-B; CRF/Viterbi trên chuỗi câu thoại), bài báo quyết từng câu độc lập | tăng độ đúng câu ngầm trong đoạn hội thoại dài | cùng điểm số, giải mã độc lập vs theo chuỗi |
| N4 | **Hồ sơ giọng văn từng nhân vật dựng dần theo sách** (xưng hô, câu cửa miệng, độ dài) từ câu đã gán chắc | sách càng dài càng đúng câu ngầm | đo theo vị trí chương trong sách |
| N5 | **Tối ưu cho NGƯỜI NGHE**: nhầm sang giọng khác hẳn tệ hơn nhầm giọng gần; không chắc thì lùi về giọng người kể (trung tính) | giảm lỗi "chói tai" ở cùng độ phủ | hiệu chỉnh độ tin cậy; đường cong đúng/bỏ qua; ma trận nhầm theo khoảng cách giọng |
| N6 | **Học chồng** luật + bộ chấm + LLM; bất đồng giữa nguồn = độ bất định | hơn nguồn tốt nhất riêng lẻ | so theo cặp |
| N7 | **Ứng viên bắt cả tên phiên âm lệch** ("A-mét-lơn" / "Amelton") theo cách đọc | nâng trần ứng viên từ 91-93% | tỉ lệ người nói có trong ứng viên |
| N7b | **Tự nhận ra "tôi" là ai** (không cần gold): người kể KHÔNG BAO GIỜ tự gọi tên mình trong lời kể, nhưng người khác gọi tên anh ta trong thoại ("Samael, nằm xuống!") -> tên có tỉ lệ (lần nhắc trong ngoặc thoại) / (lần nhắc trong lời kể) cực đoan, ở truyện có nhiều "tôi" trong lời kể. Đo trên gold 27-09: YMP -> SAMAEL (10 / 0) đúng, Yamiyo -> TOMOBE (7 / 0) đúng (truyện đổi người kể theo chương - phải làm theo chương), nageki KRAI 8 / 1 (bị che vì bí danh mơ hồ). LLM hiện gán câu của người kể cho NGƯỜI ĐỐI THOẠI (LoRA: VINCE 13 lần) hoặc nhãn đại từ "tôi" (-> giọng NPC) - nhân vật chính truyện ngôi thứ nhất không bao giờ có giọng của mình | truyện ngôi thứ nhất: người nói ~30% -> ? | gợi ý trong Studio "'Tôi' là ai?"; đưa vào prompt LLM + ứng viên bộ chấm; đo YMP 248 |
| N8 | **Dàn trang theo paragraph**: cửa sổ cũ xuống dòng giữa MỌI đoạn, kể cả các đoạn cùng một paragraph ("“Chào anh,” Lucien nói, “hôm nay…”" thành 3 dòng) - mất tín hiệu "xuống dòng = đổi lượt". TMA có 38% đoạn nằm chung paragraph với đoạn khác | tăng độ đúng ở truyện kiểu phương Tây | `build_vi.py --layout paragraph`, cùng mọi thứ khác |
| N9 | **Danh sách nhân vật của chương đầu cửa sổ** ("Nhân vật trong chương: Douglas, Lucien, …"), chỗ nhắc trong danh sách có xô khoảng cách riêng: 12/12 câu test "người nói ngoài ứng viên" là nhân vật CÓ tên trong chương, chỉ nằm ngoài cửa sổ (381 mở đầu bằng Lucien-Augustus nói chuyện, tên chỉ xuất hiện sau). Chính là danh sách LLM được đưa | độ phủ test 92,7% -> 100%, train 95,2% -> 98,5% | `build_vi.py --cast` |

Kết quả đầu (27-09):
- **N7 ngôi thứ nhất**: 118/138 câu có người nói nằm ngoài ứng viên là của nhân vật-người-kể xưng "tôi". Thêm "tôi/mình/tớ"
  trong lời kể làm chỗ nhắc người kể của chương -> độ phủ train 91,2% -> 95,2% (build_vi.py c3a7188). Thẻ lời nói truyện
  dịch thường đứng SAU câu thoại ("…," tôi nói.) - lấy nhầm câu sau từng nhận người đối thoại làm người kể.
- **N1 che dấu hiệu**: luật thẻ tường minh đúng 95,5% nhưng chỉ phủ **7,5%** câu thoại (cues.py) - gần như mọi câu là ngầm/đại
  từ. Sinh được 1.525 câu ngầm có nhãn từ 771 chương sản xuất (build_cue_masked.py), gần gấp đôi dữ liệu gold.
- **N2 đại từ**: đại từ xưng chính chiếm trung bình 69,5% câu của mỗi nhân vật (30 người >= 8 câu); có người gần như chữ
  ký (Hạ "anh" 95%, Fuyutsuki "mình" 94%, Sitri "em" 75%) nhưng Lucien chia "tôi" 47% / "ta" 38% theo NGƯỜI NGHE (vai vế) -
  nên đặc trưng đúng là hồ sơ xưng hô theo CẶP người nói -> người nghe (nối N2 với N4), không phải một đại từ mỗi người.

- **E3 bộ chấm cơ sở** (mmBERT-base, embedding đóng băng, 6 epoch x 48 s, dữ liệu quote_vi_pov): test 185 câu thoại/nội
  tâm **78,4%** (có tên 80,6%, người kể/NPC 60%, 12 câu người nói ngoài ứng viên). Trên CÙNG 143 câu của 4 chương TMA test:
  **bộ chấm 74,1% vs qwen3:8b 67,8% và qwen3:4b 67,8%** - bộ chấm đúng/LLM sai 22 câu, ngược lại 13 (McNemar p = 0,18,
  chưa đủ chắc: tập test nhỏ). Chương 248 (ngôi thứ nhất): 39/42 = 92,9%. Hai bên sai ở câu KHÁC nhau -> trần kết hợp
  83,2% (bằng chứng cho N6). Chạy cả tập test trong vài giây.

- **N1 trộn thẳng vào huấn luyện: SẬP** - test **34,6%** (có tên 38,8%, người kể/NPC **0%**) so với 78,4% của mốc; dev
  tụt dần theo epoch (52,9% -> 44,1%) trong khi loss giảm (2,33 -> 0,62) = học thuộc nhiễu. Hai nguyên nhân: 1.525 câu che
  đều là câu CÓ TÊN (không câu người kể/NPC nào) nên lựa chọn "không ai" bị bỏ đói; và xoá thẻ thường xoá luôn bằng
  chứng DUY NHẤT ("“…” Lucien nói." -> "“…”"), nên nhiều câu che không còn trả lời được từ văn bản - model học đoán mò.
  Còn thử: học hai giai đoạn (che dấu hiệu trước, gold sau) một seed; hướng sửa đúng hơn là chỉ che câu VẪN trả lời
  được (vd hai câu kề có thẻ của hai người khác nhau -> luân phiên cho đáp án).
- **N3 giải mã cả hội thoại: KHÔNG giúp** (`decode_conversation.py`). Luật lượt lời đo trên gold train: cùng paragraph
  -> 81% cùng người câu trước; xuống dòng liền -> chỉ 26% cùng người câu trước, 38% người của câu t-2, 36% người khác
  (truyện dịch tách lời một người thành nhiều dòng - luân phiên yếu hơn tiểu thuyết Anh nhiều). Viterbi bậc hai với λ
  chọn trên dev: λ = 0 thắng (dev giảm đều khi λ tăng, test đứng yên ±0,5%), kể cả sau khi hiệu chỉnh nhiệt độ. Bộ mã
  hoá đã thấy các câu kề trong cửa sổ nên đã tự học cấu trúc này.
- **Bộ chấm quá tự tin nhưng xếp hạng đúng** (N5): xác suất ra kiểu 0,99999996 (loss train 0,03); nhiệt độ khớp trên dev
  T = 6. Sau hiệu chỉnh, trên 143 câu TMA test: tin cậy < 0,5 (36 câu, 25%) đúng **33%**; 0,5-0,8 đúng 75%; 0,8-0,95
  đúng 93%; >= 0,95 đúng 100%. Tức là có thể biết TRƯỚC câu nào nhiều khả năng sai - nền cho "không chắc thì lùi về giọng
  người kể" (N5) và cho việc hỏi chủ sách đúng câu cần hỏi.
- **N6 thăm dò** (chưa có dự đoán LLM trên dev nên ngưỡng chọn bằng kiểm chứng chéo bỏ-một-chương trên 4 chương test):
  câu bộ chấm tin cậy < 0,5 thì lấy của **qwen3:4b** -> **76,9%** vs 74,1% (CV chọn đúng θ = 0,5 cả 4 lần); với qwen3:8b
  thì không lợi (72,0%). Nhóm khó 36 câu: bộ chấm 33%, qwen3:8b 33%, qwen3:4b 44% - câu khó với mọi hệ. Chưa có ý nghĩa
  thống kê; cần LLM chạy trên chương dev (TMA 344, da_bao_la 050) để chọn ngưỡng đúng cách.

- **Cách đo phải đổi (27-09 trưa)**: (1) chọn checkpoint theo dev làm hỏng phép so - dev (TMA 344 + da_bao_la 050)
  không có truyện ngôi thứ nhất, nên lượt dàn trang paragraph chọn epoch 3 (chưa học "tôi = người kể"): YMP 248 tụt
  92,9% -> 59,5% trong khi TMA ngang (74,1% / 72,7%). Từ nay mọi lần chạy ghi dự đoán TỪNG EPOCH và so bằng epoch cuối.
  (2) Test cố định 185 câu / 2 truyện quá nhỏ -> **kiểm chứng chéo**: 5 phần theo chương (1.827 câu, 10 truyện) và 10
  phần THEO TRUYỆN (học trên 9 truyện, chấm truyện thứ 10). (3) Test cũ (TMA, YMP) là truyện CÓ trong train: bộ chấm học
  thuộc được nhân vật ("Lucien nói nhiều"), còn app thì truyện nào cũng mới và LLM cũng chưa từng thấy các truyện này -
  phép so 74,1% vs 67,8% nghiêng về bộ chấm. Phép so công bằng là theo truyện.
- **Học trước PDNC chuyển được sang tiếng Việt - kể cả KHÔNG có gold tiếng Việt nào**: sau 1 epoch chỉ PDNC (tiếng Anh,
  916 s), bộ chấm chưa từng thấy câu tiếng Việt nào đạt test **69,7%**, câu có tên **78,2%** (người kể/NPC 0% - PDNC không
  có lớp ấy). Trên 123 câu có tên của TMA test: **78,9% vs qwen3:8b 70,7%** (19 câu chỉ bộ chấm đúng, 9 câu chỉ LLM đúng)
  và vs qwen3:4b 74,8%. Đây là phép so CÔNG BẰNG đầu tiên với LLM: cả hai chưa từng thấy các truyện này.
  Tiếp 6 epoch gold (một lịch tốc độ học chung, pha gold chạy ở ~24% đỉnh rồi giảm): test theo epoch 83,2 / 82,2 / 78,9 /
  80,5 / 80,0 / **81,1%** (epoch cuối - con số chốt trước) vs mốc 78,4% (16 câu chỉ PDNC đúng, 11 ngược lại, p = 0,44);
  câu có tên **85,5%** vs 80,6%; người kể/NPC tụt dần 75% -> 45% khi học lâu (ít câu loại này - học quá khớp). Theo
  loại câu (sau 1 epoch gold): câu có thẻ mọi hệ 100% (chỉ 13/185 câu); câu NGẦM mốc 75%, PDNC 80%, qwen3:8b 68%,
  qwen3:4b 72% - PDNC giúp đúng chỗ khó. Mô hình đã học trước cần ít epoch gold hơn: kiểm chứng chéo sẽ chọn số epoch.
- **LỖI DỮ LIỆU tìm ra 27-09 12:4x (mọi lượt bộ chấm trước đó dính - dữ liệu cũ giữ ở `*_v1`)**: `gold_quotes` lấy
  người nói bằng `parts[2]` = CHỮ ĐẦU của tên: 250/2.023 câu gold bị cắt; "TRỊNH VĨNH MONG" và "TRỊNH LÃO" (45 + 45 câu)
  nhập làm một "TRỊNH"; "DẠ OANH" -> "DẠ" nên bí danh "dạ" khớp chữ "dạ" lễ phép trong mọi câu thoại ("HẠ", "CHU",
  "SƠN" tương tự). Sửa: tách tên từ PHẢI như `score_models.parse_gold`. Cùng lúc: (1) khớp tên có PHÂN BIỆT HOA THƯỜNG
  (`--case-sensitive`: tên Hán-Việt ghép từ âm tiết thông dụng - "mặc", "hạ", "chu đáo") bỏ 481/9.952 chỗ nhắc giả, độ
  phủ không đổi; (2) trường `accept` = MỌI người nói đủ điểm (652/1.827 câu có hơn một) - bộ chấm học và chấm với cả tập,
  như score_models chấm LLM; (3) "UNKNOWN" là không-ai. Chấm lại theo gold đầy đủ (`compare_predictions --official`):
  test cố định bộ chấm PDNC 86,5% (TMA 84,6%) vs qwen3 68,5% - bộ chấm được cộng nhiều hơn vì hay chọn đúng người được
  nêu tên trong lời dẫn của câu cả đám nói.
- **N7b tự suy người kể - KHÔNG dùng gold, và đúng hơn cách suy từ gold** (`build_vi.py --pov-auto`, 27-09 13:4x): truyện
  có >= 30% lời kể chứa "tôi/tớ/mình" (bỏ "mình" phản thân sau "của/tự" - Yamiyo 155 ngôi thứ ba đếm được 13% chỉ nhờ nó);
  người kể = tên được gọi trong thoại mà không có trong lời kể (tỉ lệ >= 3, >= 5 lần thoại; theo chương, lùi về người của
  cả truyện chỉ khi chính chương ấy >= 20% "tôi"). Kết quả: YMP 134/188/199/248 SAMAEL, nageki 20 KRAI, Love Unseen 09
  KAKERU ("tôi hỏi." kề câu của KAKERU), Yamiyo 189 TOMOBE; để trống đúng ở nageki 73 và Yamiyo 155 (chương ngôi thứ BA,
  điểm nhìn Kule / Tamaki - cách suy từ gold cũ đã gán nhầm KRAI cho nageki 73). Độ phủ train 97,9% (từ gold: 96,6%).
  Từ 13:46 mọi bộ dữ liệu bộ chấm (`quote_vi_pov`, `quote_vi_para`, `quote_vi_para_cast`) dùng cách này - phép đo không
  còn dùng gold ở khâu nào ngoài nhãn; bản suy-từ-gold giữ ở `*_goldpov`.
- **N4' tự học theo cuốn** (mới, đúng luồng app: phân tích CẢ cuốn trước khi đọc): TMA làm truyện mới (học trên 9 truyện
  kia), bộ chấm chấm 150 chương TMA không nhãn (4.440 câu, `build_unlabeled.py`), giữ nửa câu chắc nhất làm nhãn tạm
  (`pseudo_label.py`), học thêm 2 epoch, đo trên 847 câu gold TMA; đối chứng = cùng +2 epoch không nhãn tạm; 2 vòng.
  **Kết quả vòng 1-2 (27-09 14:1x, 847 câu gold TMA, TMA là truyện MỚI với mô hình):**

  | | tất cả | có tên | không ai |
  |---|---|---|---|
  | m0: PDNC -> 9 truyện khác | **82,6%** | 89,6% | **40,3%** |
  | đối chứng: +2 epoch, không nhãn tạm | 82,2% | 90,0% | 34,5% |
  | vòng 1: +2 epoch + 2.220 nhãn tạm | 81,3% | 90,4% | 26,1% |
  | vòng 2: nhãn tạm từ mô hình vòng 1 | 80,0% | **91,1%** | 12,6% |

  Tự học giúp ĐÚNG loại câu nó có nhãn tạm: câu có tên tăng đều (89,6 -> 91,1%), nhưng nhãn tạm chọn theo xác suất
  (bão hoà ở 1,0) toàn là câu có tên (2.220/2.220), nên "không ai" sụp. Vòng 3 (`pseudo_label.py --rank margin
  --balance`: 2.074 có tên + 145 không ai) và biến thể nhân 3 trọng số "không ai" đang chạy.
- **Học trước tiếng TRUNG** (mới): CSI (Yu và cs., NAACL 2022) là TRUYỆN MẠNG Trung Quốc - đúng thể loại gốc của phần lớn
  truyện dịch app đọc - cộng JY (Kim Dung) và WP: 78.623 câu -> 54.963 cửa sổ (`build_csi.py`; dữ liệu gốc là hỏi-đáp
  trích đoạn, ứng viên dựng lại từ từ điển tên của chính bộ dữ liệu, bỏ chuỗi đáp án gán nhầm như 东西 "đồ vật"). **Giấy
  phép: dữ liệu CSI chỉ cho nghiên cứu phi thương mại** - không commit dữ liệu; phát hành mô hình học từ nó phải hỏi chủ sách.
  Kết quả 0-shot (1 epoch 20k cửa sổ, chưa thấy câu tiếng Việt nào): test **40,0%** (có tên 43,6%) - kém xa PDNC (73,5%,
  có tên 80,6%). Tiếng Trung chuyển sang tiếng Việt kém dù cùng thể loại gốc: ngữ cảnh chỉ ~270 chữ, ~10% chữ bị che, ứng
  viên dựng lại từ từ điển tên (không có danh sách nhân vật thật). Giá trị làm điểm khởi đầu: chờ kiểm chứng chéo theo truyện.

- **N6 với LoRA** (143 câu TMA test, chấm chính thức, ngưỡng chọn bằng kiểm chứng chéo bỏ-một-chương): bộ chấm mốc
  79,0% -> 81,1% khi câu tin cậy thấp lấy của LoRA (θ chọn 0,6-0,7); bộ chấm PDNC 84,6% -> **không lợi** (CV chọn θ = 0:
  không bao giờ chuyển; ngay trong nhóm tin cậy < 0,5 bộ chấm PDNC đúng 18/31, LoRA 13/31). Tạm kết luận kiến trúc:
  người nói = bộ chấm (PDNC), các trục còn lại = LoRA - chờ kiểm chứng chéo theo truyện xác nhận.

Công cụ: `compare_predictions.py` (so theo cặp từng câu, ensemble nhiều seed, McNemar, đọc cả dự đoán LLM từ project
eval) tái lập đúng số 74,1 / 67,8 / 22-13 / p 0,1755 ở trên. Mọi lần chạy bộ chấm ghi `dev/test_predictions.jsonl` có xác
suất biên từng thực thể + "không ai".

Hàng GPU (27-09 bài học): MỌI việc GPU đi qua một hàng; không sửa file script bash khi nó đang chạy (bash đọc theo vị trí
byte - sửa `scorer_27_09.sh` giữa chừng làm nó gãy cú pháp ở 11:09); mỗi bước tự bỏ qua khi đã xong để dừng/thả lại an
toàn (`scratchpad/gpu_queue_27_09b.sh`).

Thứ tự: E3 cơ sở (mốc) -> N7 + N1 (tăng trần và dữ liệu) -> N2, N3 -> N5 -> N4, N6.

## Đường vào app (phác thảo 27-09 - chưa làm, chờ kiểm chứng chéo theo truyện)

Bộ chấm chỉ thay TRỤC NGƯỜI NÓI; loại đoạn, cảm xúc, cường độ, nhịp, âm lượng vẫn do LLM. Vị trí trong luồng bắt buộc
(AGENTS.md): sau "segment toàn book" và sổ nhân vật (bí danh + tên hiển thị), trước "khoá voice mapping".

- **Đầu vào đã có sẵn trong app**: đoạn (seq, kind, paragraph_index), bảng `characters` (canonical + display) -> bí danh,
  danh sách nhân vật chương (N9), người kể "tôi" (N7: hỏi chủ sách trong Studio, hoặc tự suy từ thẻ "tôi nói").
- **Tất định**: cùng trọng số + cùng văn bản -> cùng kết quả, không lấy mẫu, không phụ thuộc lô. Điều AGENTS.md mô tả
  (dừng/resume giữa pha phân tích ra cuốn sách khác: 23 vs 19 nhân vật) không xảy ra ở trục người nói nữa.
- **Nhanh**: cả tập test (185 câu) trong vài giây; một chương ~1-2 s trên GPU. Mô hình ~1,2 GB (mmBERT-base fp32); torch
  đã có trong runtime.
- **Câu không chắc** (tin cậy < 0,5 sau hiệu chỉnh, ~25% câu, đúng ~33%): lấy câu trả lời LLM (N6), hoặc giọng người kể
  (N5) - lựa chọn sản phẩm của chủ sách. **Người kể/NPC** ("không ai"): bộ chấm không đặt được nhãn NPC cục bộ - giữ
  nhãn NPC của LLM.
- **Tự học theo cuốn** (N4', nếu thí nghiệm dương): sau lượt chấm đầu, học thêm vài phút trên chính cuốn ấy.
- Mô hình là một artifact mới -> đi vào `QUALITY_IMPLEMENTATION_FILES`/hash như mọi thứ quyết định đầu ra; làm trên nhánh
  dev, không đụng sách đang cần resume.

**Chỗ cắm cụ thể (đọc code 27-09 14:0x):** `pipeline.py` sau `analyzer.analyze_all(...)` đã có chuỗi bước "sau khi phân tích
CẢ cuốn": `reconcile_local_speaker_identities` (hỏi LLM một lần: nhãn NPC mô tả có phải nhân vật được nêu tên sau đó
không) -> `reconcile_name_pronunciations` -> `build_registry_and_cast` -> `finalize_casting`. Bộ chấm là một bước mới
cùng khuôn, ĐẦU chuỗi ấy:
1. `ebook_reader/speaker_scorer.py` (chỉ suy luận): dựng cửa sổ theo chương từ `segments` (seq, kind, paragraph_index,
   dàn trang paragraph), bí danh từ tên nhân vật phân tích đã gặp + bảng `characters`, dòng danh sách nhân vật chương (N9),
   người kể "tôi" (N7b tự suy, hoặc câu trả lời Studio); ra cho mỗi đoạn thoại/nội tâm: thực thể, độ tin cậy đã hiệu
   chỉnh, xác suất "không ai".
2. Bước pipeline `reconcile_speakers_with_scorer`: đoạn nào bộ chấm CHẮC (ngưỡng chọn bằng kiểm chứng chéo) và chọn một
   nhân vật có tên khác LLM -> `db.rewrite_segment_speakers(...)` (giới tính/tuổi theo sổ nhân vật), ghi `db.event` từng
   lần sửa để soát như các bước reconcile khác; bộ chấm nói "không ai" -> giữ nhãn NPC/người kể của LLM.
3. Kết quả bộ chấm lưu bền trong SQLite theo chương (resume không chấm lại - GPU bf16 có thể lệch bit giữa hai lần chạy);
   hash trọng số + phiên bản thuật toán đi vào dấu vân tay `ANALYSIS_CASTING_STAGE` (quality_policy.py) để resume bằng
   mô hình khác bị từ chối như mọi thay đổi casting.
4. Trọng số (~1,2 GB) tải theo revision ghim như các model khác, không commit.

## Máy và giới hạn

RTX 5060 Laptop 8 GB, Windows. PyTorch Windows không có flash attention; huấn luyện phải ghim attention cuDNN và KHÔNG
dùng optimizer `paged_*` (UVM làm BSOD khi lưu checkpoint - 27-09). Huấn luyện dài: `train_lora.py --resume`, lưu mỗi
50 bước. Phân tích sản xuất dùng Ollama (flash attention bật, tái dùng tiền tố prompt).
