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
4. **Tập test không bao giờ lọt vào huấn luyện**: TMA 351 363 378 381 + young_masters_pov 248 + bộ LN 28-09 (dưới)
   (`scripts/model_eval/build_training_set.py`, `SPLIT`).
5. **Thước quyết định là thứ chủ sách đọc: LN Nhật + truyện mạng Hàn** (chủ sách 28-09: *"tôi hay đọc light novel nhật,
   hàn cơ mà"*). Truyện Trung, Việt, cổ chỉ là kiểm tra phụ "không được phá".
6. **Chỉ so hai model đo trên CÙNG host** (cùng mã phân tích và tách câu). Lượt đo trước một thay đổi host phải đo lại
   trên host mới, không đem ra so - 29-09 chiều: lượt LN cơ sở của v3 chạy trước các thay đổi host tối 28-09, và kết luận
   "v6 thua v3" rút từ đó không đứng (mục dưới).
7. **Người vô danh xác định được là MỘT người phải ghi `NPC*:<mô tả>` trong đáp án, cả ở chương kiểm tra**; đám đông
   để `NPC*` trơn. Thiếu mô tả thì F1 giọng không biết hai câu vô danh là một người, và xếp model ngược (mục 29-09 tối).

## 29-09 tối - F1 giọng biết người vô danh là ai; 8B-v5 nhập người lạ vào nhân vật có tên

**Lỗ của thước F1 giọng.** Từ sáng 29-09, câu đáp án `NPC*` chỉ được so với câu của người có tên: hai câu NPC* không tính
là cùng hay khác người. Làm vậy để model tách đúng ba người lạ không bị phạt. Nhưng nó có hai tác dụng phụ khi người vô danh
thật ra là MỘT người:

- tách người ấy làm hai giọng không mất điểm nào;
- một câu của nhân vật có tên lẫn vào giọng người ấy thì MỌI câu của người ấy mất một nửa độ chính xác (câu vô danh không
  đỡ nhau, nên câu lạc chiếm 1/2 thay vì 1/24).

Nageki 62 xếp ngược vì thế. v3 đọc bà thầy bói bằng hai giọng ("Bà lão" 14 câu, "Bà thầy bói" 8) và được 87,5. v6 giữ bà
trong một giọng, chỉ lẫn một câu của Krai, và được 77,7.

**Sửa.** Đáp án các chương đo nay ghi người vô danh là ai, như đáp án huấn luyện đã làm từ c525821: `NPC*:bà thầy bói`
(Nageki 62, 25 câu), `NPC*:ông chú trong làng` (Nise 132, 11), `NPC*:mẹ Kakeru` (LU 07, 11), và ba người của LU 10 (sếp 4,
mẹ 4, người qua đường 1). Đám đông để trơn: lính Toà án dị giáo ở Nise 086, câu "cả đám đồng nghiệp" ở LU 10.
`voice_identity.gold_person()` biến câu có mô tả thành một người như người có tên. Chấm người nói chặt không đổi. Test:
`tests/test_voice_identity_scoring.py`.

| model | Nageki 62 trước → sau | gộp 12 chương trước → sau |
|---|---|---|
| v3 | 87,5 → 78,6 | 61,1 → 59,9 |
| v6 | 77,7 → 82,6 | 60,0 → 59,8 |
| 8B-v5 | 71,3 → 77,3 | 62,4 → 62,6 |

**8B-v5 nhập người lạ vào nhân vật có tên gấp đôi** (`ln_strangers.py`, 5 chương có người vô danh):

| model | câu vô danh | giọng người lạ | NHẬP vào nhân vật có tên |
|---|---|---|---|
| v3 | 65 | 65% | 35% (23) |
| v6 | 65 | 68% | 32% (21) |
| 8B-v5 | 65 | 45% | 55% (36) |

- Nageki 62: 8B gán 21/25 câu của bà thầy bói cho LUCIA (em gái Krai). Người nghe nghe một bà lão bằng giọng cô gái trẻ.
- Yamiyo 225: 8B gán 12/22 câu của Gensei cho Azuma. v3 thì TÁCH Gensei: nhãn chức danh "Thủ lĩnh Âm Dương Liêu" 10 câu.
- Ngược lại LU 07: 8B giữ mẹ Kakeru riêng 11/11, v3 nhập 6/11.
- Đây là chỗ v7 nhắm tới (dữ liệu dạy nhãn cục bộ có mô tả cho từng người lạ).

**Dò việc nhập bằng xưng hô, không cần huấn luyện lại (thẻ 0c "hai người chung một tên", `address_cues.split_doubts`).**
Bà thầy bói nói "ta… cậu" với Krai; Lucia nói "anh… bà" - hai bộ từ không bao giờ đi chung một câu. Gom các từ xưng hô của
MỘT nhãn trong một chương theo việc chúng đi chung câu; hai nhóm tách hẳn là hai giọng.

- Luật "hai người" (tự xưng khác nhau như "ta"/"tôi", hoặc cả hai nhóm có từ hai từ trở lên): trên bộ LN 12 chương đúng
  15/15 lần báo (v3 6, v6 3, 8B 6); luật chưa thêm điều kiện ấy đúng 21/31 - báo nhầm khi một người gọi mẹ "con", gọi bạn
  "cậu".
- Truyện kể ngôi ba thì hỏng: Chu Du "ta… ngươi" với tướng dưới, "tôi… ngài" với chúa; Chị Dậu "con/em" với nhà mình,
  "cháu/bà" với người ngoài. Điều kiện "cùng người nghe" (xấp xỉ bằng người nói kề bên) không cứu được mà còn làm mất phần
  lớn ca đúng của 8B (6 -> 1). Nên thẻ chỉ xét chương kể ngôi thứ nhất, như thẻ xưng hô từng câu.
- Nhóm nào là người lạ: nhóm lệch khỏi cách nhãn ấy nói ở các chương KHÁC. Thử ghép hai chương mỗi truyện: v3 Nageki 62
  đúng 3/3; nhãn người kể thì hay chọn ngược (HDST 130: nhóm "tôi" đúng là Ed) vì hồ sơ người kể nhiễm lời model đã gộp -
  nên thẻ bỏ qua nhãn người kể (thẻ từng câu đã lo phần ấy). Chưa đo được trên một cuốn đủ chương: bộ đo chỉ có một chương
  mỗi dự án. Kiểm âm duy nhất có: bản sao lô 18 (TMA, 11 chương, 1257 câu thoại, văn "ta… ngươi" khắp nơi), ép coi như ngôi
  thứ nhất - 0 thẻ, 0,017 giây. Kiểm dương: Mac chạy 8B-v5 Nageki 56-64 đêm 29-09 (split_check_mac.sh) - Lucia đã có hồ sơ
  ở các chương khác thì bà thầy bói ở 62 có bị hỏi không.

**F1 giọng theo chương không thấy lỗi xuyên chương.** LU 10 kể ngôi thứ nhất của Hayase; khai sai người kể là Kakeru
(người kể cả cuốn): người nói chặt sụp ở cả ba model (v3 64,1 -> 35,9; v6 64,1 -> 35,9; 8B 66,7 -> 38,5), còn F1 giọng
gần như không đổi (73,0 -> 68,0; 79,1 -> 77,2; 78,9 -> 81,5) - trong chương, lời Hayase vẫn gom đúng một cụm, chỉ mang tên
sai. Trong cả cuốn thì cụm ấy chính là giọng Kakeru: người kể nữ đọc bằng giọng nam. Thước đo từng chương không bắt được, vì
vậy câu hỏi "Tôi là ai?" theo chương (0.4.3) là thứ giữ lỗi này, không phải model.

**Chữ hoa của 8B-v5 không tới tay người dùng.** 8B-v5 viết nhãn chữ hoa ("AZUMA") vì học từ data_v5. Lượt gom tên của dây
chuyền không đổi chữ hoa, nhưng `humanize.person_name` hiện nhãn toàn chữ hoa thành "Azuma". Chỉ nhãn hoa lẫn thường
("LOUise" của model cũ) lọt qua; nay cũng thành "Louise".

**8B-v5 so với v3, cùng host (LN mở rộng, 6 chương, 493 câu, thước mới):**

| model | F1 giọng | người nói chặt | cảm xúc |
|---|---|---|---|
| v3 | 63,6% | 65,5% | 90,7% |
| v6 | 65,1% | 64,3% | 92,0% |
| 8B-v5 | 64,3% | 67,7% | 91,6% |

8B − v3: F1 +0,8 [−2,8; +4,0], chặt +2,2 [−2,4; +7,6], thắng 3 thua 3 chương. **Không phân biệt được.**

**8B-v5 so với v6, cùng host (12 chương, 1014 câu):** F1 62,6 so với 59,8: +2,7 [+0,1; +5,2]; chặt 66,7 so với 61,4:
+5,2 [+1,8; +9,8]; thắng 7 thua 5. **8B hơn v6 thật**, và v6 ≈ v3 trên LN mở rộng.

**Cổng, 8B-v5 so với v6 cùng host (29-09 tối):**

| cổng | câu | F1 giọng v6 → 8B | người nói chặt v6 → 8B | từng chương |
|---|---|---|---|---|
| TMA 351/363/378/381 (cuốn chủ sách đang làm) | 156 | 64,3 → 70,7 | 73,1 → 82,7 | 8B thắng 4/4 |
| YMP 248 (ngôi thứ nhất) | 50 | 76,4 → 84,6 | 86,0 → 92,0 | - |

Lượt cổng TMA của v3 (28-09-lora3) chạy trên host cũ nên không đem so. Gộp theo CUỐN thay vì theo chương (`lnx_table.py
--by-book`: cùng người ở hai chương một truyện là một người) hạ cả ba model 2,5-3 điểm và không đổi thứ hạng (8B 60,4 > v3
57,2 ≈ v6 56,8); một phần mức hạ là giả, vì công cụ gom cách viết tên theo từng chương còn app gom theo cả cuốn.

**Kết luận cho câu hỏi đổi model mặc định (chủ sách quyết):** 8B-v5 hơn 4B một khoảng nhỏ nhưng thật trên LN (+2,7 F1,
+5,2 chặt so với v6) và rõ trên cổng (TMA +6,4 / +9,6, YMP +8,2 / +6,0), tốc độ gần ngang 4B. Đổi lại nó nhập người lạ vào nhân vật có tên nhiều hơn (55% so với 32-35%).
Nên chờ 8B trên dữ liệu sạch (data_v6, Modal 01-10) và v7 (nhãn người lạ có mô tả) trước khi đổi: v5 học dữ liệu có
nhãn chữ hoa và có chương cổng Tam quốc/Tắt đèn trong tập huấn luyện, nên hai cổng ấy không đo được v5.

## 29-09 chiều - đối chứng v6b; so với v3 bị nhiễu HOST; một khối câu làm lệch TCF 042

**Câu hỏi của v6b.** v6 (data_v6, 2057 mẫu) thua v3 trên LN cơ sở, và câu 『』 ở TCF 042 tụt. Giả thuyết: 4 chương "nhắm lỗi"
thêm vào data_v6 (LU 03, Nageki 53, TCF 107, Yamiyo 009) có hại, nhất là TCF 107, nơi 『』 là "ký sinh trùng" nói. v6b =
đúng công thức v6 trên data_v6 bỏ 4 chương ấy (1717 mẫu).

**data_v3 và data_v6b gần như trùng khít** (`data_diff.py`). Chung một prompt hệ thống (không lệch dòng nào). Trong 3971 câu
có mặt ở cả hai bộ, chỉ 2 nhãn đổi. Số mẫu mỗi truyện lệch ±2-4. Vậy v6b là một lượt huấn luyện LẠI của v3 với cùng dữ
liệu, không phải một công thức khác.

**Lượt LN cơ sở của v3 chạy trên host cũ.** v3 đo lúc 28-09 14:13, tức TRƯỚC các thay đổi host tối 28-09: bộ tách
“...,” là thoại, luật tên gọi, tên theo chữ sách, dòng người kể. v6, v6b và 8B đo ngày 29-09 trên host mới (c372ce37).
Mọi phép so v3 với các lượt ấy trên LN cơ sở vì thế lẫn hai biến. Có hai hệ quả:

- **v6 hoà v3.** Trên LN mở rộng (6 chương, 493 câu, cả hai đo cùng host 29-09), v6 − v3 = −0,5 F1 giọng, khoảng tin cậy
  95% [−5,6; +3,7], thắng 3 thua 3. Như vậy kết luận "giữ v3 vì v6 thua LN" (29-09 sáng) không đứng.
- **"8B hơn v3 3,8 điểm" (bảng trên) cũng lẫn host.** Phép so công bằng là 8B với v3 trên LN mở rộng. Lượt 8B trên LN mở
  rộng đang trong hàng GPU.

**v6 so với v6b cùng host là phép thử thật của 4 chương.** Trên LN cơ sở (521 câu):

| model | F1 giọng | người nói chặt |
|---|---|---|
| v6 (data_v6, có 4 chương) | 55,8% | 58,7% |
| v6b (data_v6b, bỏ 4 chương) | 54,3% | 53,9% |
| 8B-v5 | 61,2% | 65,6% |

- v6 hơn v6b 1,5 F1 và 4,8 chặt, nhưng thắng 3 thua 3 chương. Sau 3 chương khoảng cách là 5,0, sau 5 chương còn 1,8: phần
  lớn là dao động của từng chương.
- **Kết luận (29-09 18:4x):** gộp cả 12 chương LN (1014 câu, cùng host), v6 được 60,0 F1 / 61,4 chặt, v6b được 57,5 / 57,8.
  Luật đặt trước khi có số là chỉ bỏ 4 chương khi v6b hơn từ 1,0 điểm trở lên; thực tế v6b kém 2,5 điểm. Vậy **giữ 4 chương**:
  v7/v8/q35 và lượt 8B ngày 01-10 dùng data_v6.
- 4 chương không làm giảm lỗi người kể mà chỉ đẩy cán cân. Trên LN cơ sở, v6 gán nhầm CHO người kể 78 câu và bỏ sót 37; v6b
  gán nhầm 66 và bỏ sót 47. Tổng gần bằng nhau (115 và 113). 8B ít lỗi người kể nhất: 96.

**Dòng dặn về người kể trong prompt (A/B trên Mac, 8B-v5, Nageki 65 + LU 07 = 233 câu).**

- Nhánh dev/narrator-balance thêm vế "lời người khác nói VỚI người kể là của người ấy".
- Kết quả: F1 giọng 60,9 → 63,7, chặt 67,4 → 69,5; gán nhầm CHO người kể 42 → 38, bỏ sót 19 → 16.
- Theo truyện: LU +5,2, Nageki −0,5.
- Hai chương là quá ít để đổi `analysis.py`, file khoá nhóm phân tích: đổi nó thì sách đã bắt đầu phân tích không resume
  được. Lượt 2 đang chạy trên bốn chương ngôi thứ nhất của bộ mở rộng: Nageki 62, LU 10, Yamiyo 225, HDST 130.

**TCF 042 có một khối câu tương quan.**

- Câu 2-35 là bài đăng mạng xã hội trong 『』. Đáp án chấp nhận NARRATOR hoặc NPC\*. Gán cho người được NHẮC TÊN trong bài
  (Kuchinashi) là sai.
- v6b gán cả 21 câu cho "Kuchinashi"; v3 gán cho người lạ.
- Dữ liệu không giải thích được khác biệt này (`bracket_labels.py`):
  - câu mở bằng 『 chỉ có 31 (v3) / 76 (v6) / 31 (v6b);
  - 84-95% trong số đó dán nhân vật;
  - không mẫu nào có dạng "tên trong câu = người nói";
  - v6b có đúng thành phần 『』 của v3 mà vẫn lật.
- Vậy đây là MỘT quyết định cho cả khối, lật giữa các lượt huấn luyện. Khối này chiếm 21/55 câu của chương. Đừng dùng điểm
  chặt TCF 042 để chọn model; F1 giọng ít nhạy hơn.
- Thước LN cũng không truyền `--first-person` cho TCF 042, trong khi các truyện ngôi thứ nhất khác có. Khi chạy Studio thật,
  người dùng sẽ khai người kể.

**8B hơn 4B ở đâu** (cùng host, LN cơ sở 521 câu, `ln_categories.py`; người nói chặt):

| loại | số câu | v6 (4B) | 8B-v5 |
|---|---|---|---|
| đối đáp liền | 168 | 57,7% | 72,6% |
| 『』 | 78 | 23,1% | 42,3% |
| tôi nói | 138 | 73,2% | 79,7% |
| còn lại | 110 | 53,6% | 58,2% |
| có lời dẫn | 102 | 83,3% | 80,4% |
| vô danh | 22 | 4,5% | 13,6% |

Phần lớn khoảng cách nằm ở loạt thoại xen kẽ không có lời dẫn: 8B giữ lượt tốt hơn. Hai chỗ yếu còn lại là người vô danh và
câu 『』, cũng là hai chỗ v7 (nhãn người vô danh có mô tả) và v8 (người nói các câu trước) nhắm tới.

## 29-09 - NỀN 8B HƠN 4B RÕ RỆT; lỗi 『』 là quy ước của từng cuốn; gieo sổ nhân vật giúp nhẹ

**8B > 4B là thật, và chạy được trên card 8 GB.** Qwen3-8B QLoRA 1 epoch trên data_v5 (Kaggle T4), đo ở bản Q4_K_M 5,0 GB:

| model (bộ LN 6 chương, 521 câu) | F1 giọng | người nói chặt |
|---|---|---|
| 8B-v5 Q4, máy nhà (Ollama 0.33.2 như Studio) | **61,2%** | **65,6%** |
| 8B-v5 Q4, Kaggle (Ollama mới nhất) | 61,9% | 66,0% |
| v3 (4B, đang dùng) | 57,4% | 63,7% |
| v6 (4B, data_v6) | 55,8% | 58,7% |
| 4B-v5 (CÙNG dữ liệu với 8B) | 55,5% | 57,8% |

- **Đính chính 29-09 chiều.** Bản trước của bảng này ghi v3 = 53,9% / 56,5%. Con số ấy lấy từ lượt v3 chia câu Nageki 65
  theo cách CŨ: 520 câu, Nageki chỉ 37,5% vì đáp án lệch khỏi câu. Cùng cách chia mới (521 câu) thì v3 là 57,4% / 63,7%.
  - Như vậy 8B hơn v3 **3,8 điểm F1 và 1,9 điểm chặt**, không phải 7,3. Vẫn là thắng: 5/6 chương hơn, riêng HDST kém 8 điểm.
    Bộ LN mở rộng sẽ phân định.
  - Chỉ so các lượt có cùng số câu. Các lượt còn ở cách chia cũ: qwen3:8b gốc, 9B Modal, 8B-lora16.
- Cùng dữ liệu, 8B hơn 4B 5,7 điểm (ở nhà; Kaggle 6,4). Ở nhà trùng Kaggle từng chương, nên không phải nhiễu phiên bản.
- Tốc độ gần ngang 4B Q8 vì giải mã bị giới hạn băng thông: TCF 042 mất 356 giây, v3 mất 327 giây. Trên Mac mini M4 thì
  chậm khoảng 3 lần (1114 giây), nên không dùng Mac làm "máy phân tích" song song được.
- 8B hơn v3 ở hai chỗ yếu nhất (`research/ln/ln_categories.py` trong repo riêng tư):
  - câu người kể "tôi" nói: 79,7% (v3 72,5%);
  - đối đáp liền không lời dẫn: 72,6% (v3 68,5%).
- 8B lại KÉM v3 ở câu có lời dẫn nêu tên: 80,4% (v3 85,3%). Những câu sai ấy phần lớn là lời của người được lời dẫn nêu
  tên ("Franz đỏ mặt hét lên", "Eva nói") mà 8B gán cho người kể "tôi".
- **Lỗi lớn nhất của MỌI model là nhầm với người kể "tôi"** (`ln_narrator_bias.py`):
  - v3: gán nhầm câu của người khác cho người kể 73 lần, bỏ sót người kể 34 lần, trên khoảng 190 câu sai;
  - 8B: 68 và 28, trên khoảng 180 câu sai;
  - tức hơn nửa số câu sai.
  - Mỗi model lệch ở một cuốn khác nhau: 8B đỡ hẳn ở Yamiyo (32 → 14 lần gán nhầm) nhưng tệ hơn ở Nageki (14 → 23).
  - Dữ liệu kế tiếp nên nhắm đúng lỗi này: chương ngôi thứ nhất nhiều thoại mà người kể ít nói.
- Dữ liệu v5 có lỗi: nhãn viết hoa, và chương cổng Tam quốc/Tắt đèn nằm trong TRAIN. Việc kế là 8B trên dữ liệu sạch (v6/v6b), rồi đo LN mở rộng và 4 cổng trước khi đổi model mặc định.
- Khi đăng model, Studio phải mang theo khuôn chat qwen3. Tạo chỉ từ GGUF thì Ollama lấy khuôn Jinja thô. Việc này đã sửa: `PublishedModel.template`.

**Lỗi 『』 phần lớn KHÔNG phải việc của model** (`research/ln/bracket_flip.py` trong repo riêng tư):
- Two Childhood Friends 042: 30/35 câu 『』 là lời kể/thông báo, cả v3 lẫn 8B đều gán cho người trong cảnh.
- Yamiyo 141: 43 câu 『』 của linh thể Tọa Phu Đồng Tử, không model nào gán cho nó.
- Mỗi cuốn một quy ước. Máy không đoán được, người nghe thì biết ngay. Vì vậy app có **quy ước 『』 theo cả cuốn** (0.4.2, `ebook_reader/bracket_rule.py`): chọn một lần, các phần sau tự áp trước bước phân vai.

**Gieo sổ nhân vật đã biết** (Mac, v3), đúng thứ "Làm tiếp cuốn này" mang sang phần sau:

| chương | không gieo | có gieo |
|---|---|---|
| Nageki 65 (8 người) | 78,7 | 79,0 |
| Yamiyo 225 (13 người) | 74,8 | 76,2 |

Giúp nhẹ, rõ hơn khi truyện đông người.

**Phiên bản Ollama không đổi đầu ra.** Trên Mac, v3 chạy bằng 0.33.2 và 0.34.4 ra đúng từng số. Mac lệch nhà 4 điểm là do phần cứng (Metal so với CUDA), nên số đo trên Mac chỉ so với số đo trên Mac.

## BỘ ĐO LN 28-09 10:xx - chưa model nào từng được đo trên LN Nhật

Soát lại tập dữ liệu: test của LoRA chỉ có TMA (Trung, 4 chương) + YMP (Hàn, 1 chương); mọi chương LN Nhật có đáp án (1-2
chương mỗi truyện) đều nằm trong TRAIN, còn TMA chiếm 17 chương train. Các cổng 27-28/09 (TMA, Tam quốc, Tắt đèn) vì thế
không nói gì về LN Nhật - đúng thứ chủ sách đọc. Bộ đo mới: 5 chương CHƯA học, chọn chương nhiều thoại ở giữa truyện
(`scratchpad` chọn theo tỉ lệ đoạn thoại), 819 đoạn: Two Childhood Friends 042 (81), Nise Seiken 132 (101), Hướng dẫn sinh
tồn 062 (145, Hàn, ngôi thứ nhất), Yamiyo no Hotaru 141 (184, ngôi thứ nhất), Nageki no Bourei 65 (308, ngôi thứ nhất + đoạn
ngôi ba). Claude gán, agent soát đối kháng; mọi file qua `gold_replay.py` không LỆCH LUẬT. Các kiểu LN đáp án cũ chưa gặp:
- chuỗi bài đăng mạng xã hội trong 『』 (TCF 2-35) = văn bản viết, quy tắc 7: NARRATOR đủ, người đăng vô danh NPC*~;
- HAI giọng nội tâm cãi nhau (Yamiyo): "(…)" sau lời Hina là nội tâm thật của cô (bị khoá lời kể -> N,T, NARRATOR và HINA
  đều đủ); 『…』 là Yêu Mẫu trong người Tomobe, xưng "thiếp", chương không gọi tên -> YÊU MẪU và NPC* đủ, NARRATOR không;
- nhân vật chỉ được gọi bằng biệt hiệu trong một đoạn ngôi ba ("Thiên Biến Vạn Hoá" = Krai) -> tên đủ, danh hiệu không
  điểm (quy tắc 11: nhãn danh hiệu là giọng thứ hai của cùng người);
- tên giả trước khi chương lộ tên thật (Killigan -> Killiam, quy tắc 13).
Chạy ở hàng GPU: `scratchpad/ln_eval.sh`, đầu hàng i (v3, qwen3:8b, LoRA v2), hàng j (8B) và khảo sát E1 (đổi từ 10 chương
TMA sang 5 chương này). Soát đối kháng (3 agent) bắt HAI lỗi nặng cùng một kiểu trong đáp án của A - giọng 『』 trong đầu nhân
vật gán cho cái tên gần tay (ký sinh trùng ở TCF, Tọa Phu Đồng Tử ở Yamiyo) - và danh tính Killiam đã lộ từ chương 60;
thêm quy ước GOLD_GUIDE 7b (chuỗi bài đăng mạng xã hội: NARRATOR và NPC* đều đủ) và 7c (giọng trong đầu: lần hết cuốn tìm tên).

**Mốc qwen3:8b (model app đang dùng) - lần đầu đo trên LN Nhật** (khởi đầu lạnh: không gieo sổ nhân vật như sản xuất giữa
cuốn; mọi model đo cùng điều kiện):

| chương | người nói (score_models) | cảm xúc | F1 giọng main | F1 giọng dev/ln-names |
|---|---|---|---|---|
| TCF 042 | 42,7% | 92,5% | 39,2% | 42,2% |
| Nise 132 | 59,2% | 84,0% | 52,0% | 52,0% |
| HDST 062 (Hàn) | 65,5% | 87,5% | 60,7% | **70,3%** |
| Yamiyo 141 | 38,5% | 59,0% | 47,9% | 47,9% |
| Nageki 65 | hết giờ (trần 20 phút/chương, 308 đoạn) - đo lại ở hàng i với trần 60 phút | | | |

Lỗi của model (mổ bằng `score_models --misses` + `scratchpad/turn_taking.py`):
- **Chộp tên quen**: người không tên hay chưa gọi tên lấy tên người đã biết - ông chú trong làng (Nise) thành Alistar/Magali;
  Yamiyo: Sumire nói MỘT câu đầu chương rồi rời cảnh, model gán cho bà 22/41 câu của Tọa Phu Đồng Tử và 11/22 câu của Hina.
- **Gộp lượt / lệch pha** trong đối đáp hai người không lời dẫn: lời Grey mang tên Yoshihito (TCF); Ed <-> Glast (HDST);
  Magali <-> Alistar lệch một nhịp suốt đoạn (Nise). Cặp thoại liền nhau: gộp sai 16/44 (TCF 4/6, Nise 3/13, HDST 9/25), đáp
  án thật sự cùng người chỉ 2/44 - nhưng lệch pha thì luật "đổi lượt" không cứu (model vẫn đổi, chỉ đổi sai chỗ): việc của MODEL.
- **Một người nhiều nhãn** (-> nhiều giọng) - việc của HOST, nhánh `dev/ln-names`, ba luật, gold-check 16 truyện sạch, mọi
  lượt đo cũ không đổi một số: (1) tên Nhật họ trước là tên kiểu Việt ("HINA" -> "ONIZUKI HINA", nhận bằng romaji); (2) nhãn
  một chữ là họ HOẶC tên gọi của đúng một tên Nhật đủ mà SÁCH viết >= 2 lần ("Kuchinashi", "Yoshihito" -> KUCHINASHI YOSHIHITO -
  sách viết 33 lần; họ Onizuki chung 8 người ở Yamiyo thì không đoán); (3) chức danh trước tên: "GIÁO SƯ GLAST" = "Glast"
  (thêm chức danh học đường, hoàng tộc, quân đội, sư môn vào danh sách cũ chỉ có xưng hô gia đình + tước quý tộc).
- Bỏ: khoá "(…)" ngay sau lời thoại thành nội tâm - 81 dòng ở Yamiyo nhưng ở truyện khác là ghi chú dịch ("(note: ...)"),
  tiếng động ("(Tiếng sợ hãi)").

## LN ĐỦ 6 TRUYỆN 28-09 19:xx - các LoRA đám mây, và lỗi nằm ở đâu

Đo trên Modal (L4, `LLM_Train/modal/modal_eval.py`) + máy nhà, 519 câu có lời, thước chính F1 giọng B-cubed:

| model | F1 giọng | người nói chặt | cảm xúc |
|---|---|---|---|
| qwen3:8b gốc (đang dùng) | 52,9 | 54,9 | 84,4 |
| v3 = lora28v3-4b (máy nhà) | 55,7 | **62,4** | 87,9 |
| lfm2.5:8b gốc | 55,6 | 41,8 | 80,9 |
| Qwen3-4B-Instruct LoRA16 e1 | 53,1 | 47,4 | 88,7 |
| Qwen3-4B-Instruct LoRA16 e2 | 57,7 | 55,7 | 88,9 |
| Qwen3.5-4B LoRA16 | 57,5 | 51,4 | 88,6 |
| **Qwen3.5-9B LoRA28** | **59,9** | 57,4 | 88,8 |

Theo truyện, 9B hơn/kém 4B-e2 từ -11 tới +7 điểm: các khoảng cách 57-60 nằm trong nhiễu của 519 câu. Đang đo: v4 (cấu
hình e2 trên data_v4), 8B QLoRA huấn luyện trên Kaggle, qwen3.5:9b GỐC (tách phần LoRA khỏi phần cỡ model).

Ba phép thử offline trên kết quả đã có (script ở `scratchpad`, CPU):

- **Bỏ phiếu giữa model KHÔNG giúp** (`ln_vote.py`): 9B + v3 + e2 = 58,7%, thêm q35-4B + lfm = 58,6% - đều dưới 9B một
  mình (59,9%). Chỉ 278/519 câu ba model cùng nhãn: sai khác chỗ, nhưng trộn nhãn làm cụm giọng kém nhất quán - đúng thứ
  B-cubed chấm. Âm.
- **Neo nhãn vào tên người kể đã cho KHÔNG đổi F1** (`ln_firstperson_anchor.py`): 9B viết "Krai Andrej" cho KRAI ANDREY
  (28 câu), "Tomo" cho TOMOBE (25) - nhưng `canonical_speaker_names` đã gộp các dạng ấy về một giọng; lỗi này chỉ hại
  điểm "chặt". Âm.
- **Phân loại lỗi** (`ln_errors.py`, 9B, người nói chặt): sai 221/519, trong đó 179 là nhầm giữa HAI người có tên, dồn ở
  truyện ngôi thứ nhất (Yamiyo 83/126, Nageki 57/97). Ở Yamiyo, linh thể Tọa Phu Đồng Tử LUÔN nói trong 『』 và máy gán
  mỗi câu cho người đứng gần (người kể, Hina, Yuusei, "người lạ"; v3 cùng lỗi). Câu 『』 = 78/519 câu, sai 56% (9B, v3) /
  67% (qwen3:8b) so với 34-41% ở câu thường: một "kênh giọng" riêng máy chưa học.
- TCF: lfm2.5 được 65,5% (cao nhất) nhờ SUY BIẾN - gán gần hết câu, cả lời Yoshihito và Grey, cho một nhãn "Thất Anh Hùng";
  chuỗi bình luận 『』 (đáp án NARRATOR đủ, quy tắc 7) một nhãn thì B-cubed thưởng. Đừng tin điểm TCF của lfm. 9B tách chuỗi
  ấy thành 6 "người lạ" theo lô nên mất điểm.

Đã đưa vào app: thẻ "Lời trong 『』 là của một người?" (`webui/work_items.py`, kind `bracket`) - chương chia câu 『』 cho
nhiều người thì một cú bấm gán cả nhóm; trên dự án đo Yamiyo của 9B nó đứng đầu hộp việc (43 câu, 7 người). Vòng dữ liệu
sau: mẫu ngôi thứ nhất có người đối thoại thân cận, và mẫu 『』 nhất quán trong chương.

## ĐÊM 28-29/09 - đăng model, máy nào chạy nổi model nào, và ba phép so công bằng

Chủ sách 28-09 22:xx: đăng model tự huấn luyện công khai (Hugging Face, không GitHub Release); "chỉ train những thằng mà sau
khi train xong có thể chạy trên card của tôi" - rồi nới: 9B được nếu chạy nhờ Mac mini; "các nguồn gpu trên mạng là có hạn
nên mỗi bước sử dụng phải tính toán chiến thuật".

- **Đã đăng `abook-analyzer:v3`** (= lora28v3-4b, GGUF Q8_0 4,28 GB, sha256 9545ce0b...): huggingface.co/NGDtuanh/abook-analyzer,
  thẻ model `docs/models/abook-analyzer-v3.md`. Studio cài từ đường ghim theo commit (`studio_setup.PUBLISHED_MODELS`); thử
  thật trên Studio thử: 6 phút tải, model trong Ollama riêng trùng TỪNG LỚP bản đã đo. Tải lên từ Mac (đăng nhập `hf` ở đó).
- **Kaggle/Colab T4 không huấn luyện được Qwen3.5** (không bf16: Unsloth ép float32, 9B không vừa - thử 28-09). Qwen3.5 chỉ
  huấn luyện được trên Modal (L40S, 9B LoRA ~11 s/bước) hay máy nhà (4B, bf16 có trên RTX 5060).
- **Mac mini M4 chạy 9B chậm ~4 lần máy nhà**: qwen35-9b-lora28 (bản 59,9 F1 LN) TCF 042 (81 câu) 1.385 s, Nise 132 (101
  câu) 1.580 s - v3 trên máy nhà ~330 s cho TCF. Không "suy nghĩ" (think=false đúng), sinh ~21 token/s, đọc đề ~100 token/s
  (băng thông ~120 GB/s). Dây chuyền máy nhà làm ~7-10 phút/chương (phân tích + đọc), nên phân tích nhờ Mac bằng 9B làm cả
  dây chuyền chậm ~4 lần. Kết luận chiến thuật: KHÔNG tiêu Modal cho 9B mới trừ khi 9B hơn v3 rất rõ (hiện +4,2 F1, trong
  nhiễu của 519 câu). Lượt Mac đầy đủ (29-09 01:xx): HDST 062 QUÁ GIỜ 2.400 s (máy nhà ~5 phút), Yamiyo 141 3.093 s - chương
  dài chậm 6-9 lần, không dùng được cho sách thật. "Chạy nhờ Mac" chỉ đáng khi model 9B hơn hẳn VÀ chạy nền qua đêm.
- **Ba phép so công bằng đang chạy** (cùng data_v5, cùng công thức, cùng bộ đo): v5 = Qwen3-4B-Instruct-2507 (máy nhà) ->
  q35 = Qwen3.5-4B (máy nhà, tự chạy sau v5, `scratchpad/gpu_queue_29_09q35.sh`) -> 8B = Qwen3-8B QLoRA (Kaggle,
  abook-lora-8b-v5, trả lời "8B sau khi train phải hơn 4B chứ?"; lượt 8B cũ: F1 55,6 = v3, người nói chặt 54,0 < 62,4).
- VieNeu-TTS-v3-Turbo main mới (61b85e3d) so bản ghim 8b7e9cff: chỉ README, onnx_int8 (CPU) và 53 file gguf thêm - trọng số
  PyTorch dây chuyền dùng không đổi, không cần thử.

## LoRA v3 QUA MỌI CỔNG 28-09 20:xx - ứng viên thay qwen3:8b trên máy 8 GB

Hàng GPU i đo xong v3 (`lora28v3-4b`, Qwen3-4B LoRA trên data_v3, huấn luyện tại máy nhà) trên bốn cổng ngoài bộ LN; chấm
lại mọi lượt bằng thước chính (`voice_identity.py`, F1 giọng B-cubed / người nói chặt):

| cổng | câu | qwen3:8b (đang dùng) | LoRA v2 | **v3** | v3 - 8b (F1) |
|---|---|---|---|---|---|
| LN 6 truyện (thước quyết định) | 519 | 52,9 / 54,9 | - | **55,7 / 62,4** | +2,8 |
| YMP 248 (Hàn), có dòng "tôi là ai" | 47 | 56,1 / 61,7 | 82,8 / 91,5 | **85,5 / 93,6** | +29,4 |
| Tam quốc Hồi 50-52 (chưa học) | 219 | 74,8 / 79,5 | 73,6 / 43,4 | **85,6 / 89,5** | +10,8 |
| Tắt đèn XX, XXI, XXIV (Việt, chưa học) | 112 | 72,7 / 75,9 | 71,4 / 51,8 | **73,9 / 82,1** | +1,2 |
| TMA test (4 chương) | 156 | 55,8 / 65,4 (host 21-09) | 59,8 / 75,0 | **60,1 / 69,9** | +4,3 |

- Cổng Tam quốc từng chặn v2 (viết sai tên: 43% nhãn chặt dù F1 giọng ngang 8b) - v3 viết đúng tên (89,5%), cùng lúc luật
  tên gọi của host (4930919) gom "DU" -> "CHU DU". Tắt đèn: v3 kém 8b ở chương XXI (65,5 vs 80,4 F1) nhưng hơn ở XX, XXIV.
- v3 KHÔNG phá cổng nào và nhanh hơn 1,5-1,7 lần (LN: 327-1049 giây/chương, qwen3:8b 552-1700, cùng card, cùng host).
- Trên LN, khoảng cách F1 +2,8 nằm trong nhiễu của 519 câu; người nói chặt +7,5 thì không. Model LN tốt nhất đo được vẫn
  là Qwen3.5-9B LoRA28 (59,9) nhưng không nạp nổi card 8 GB.
- Kết luận nghiên cứu: v3 là ứng viên thay qwen3:8b cho máy 8 GB. CHƯA đổi model mặc định (file khoá `config.py`, sách
  mới) và đường tải model cho Studio (model tự huấn luyện phải được đăng ở đâu đó để Studio kéo về = phát hành, chủ sách
  quyết - đã hỏi 28-09 21:0x). Hai đối thủ cùng cỡ máy đo xong trên Modal (21:3x): v4 (cấu hình e2 trên data_v4) đủ 6
  truyện 55,6 / 51,1 / 89,8 - F1 ngang v3, người nói chặt kém 11 điểm; 8B QLoRA (Kaggle, Q4) 5/6 truyện 55,6 / 54,0. Không
  model nào chạy được trên card 8 GB hơn v3.
- Dữ liệu huấn luyện chỉ là đáp án của chính dự án (`build_training_set.py` gom JSONL của `gold_replay`), không có
  CSI/PDNC (giấy phép phi thương mại).

**Ollama 0.34 cho qwen3 "suy nghĩ" (28-09 20:4x, thử Studio tự chứa).** Cùng prompt, Ollama 0.34.4 sinh 360 token thay vì
61 cho request đầu (suy nghĩ trước khi trả JSON dù request có `format`) -> hết ngân sách đầu ra, cuốn thử hỏng ở khâu phân
tích; máy dev chạy 0.33.2 nên chưa từng gặp. Hai lớp chặn: Studio ghim đúng 0.33.2 (`studio_setup.OLLAMA`), và mọi request
phân tích gửi `"think": false` (main 7a5f9d6, hash 73ef04cb -> ab2a5f39). A/B trên 0.33.2 (YMP 248, qwen3:8b, mã main vs
nhánh): 130/130 đoạn trùng khít từng trường, điểm trùng (76,5 / 61,7 / 78,3 - cũng trùng lượt N7b ngày 27-09: dây chuyền
tái lập qua ngày). Ollama của máy tự cập nhật lên 0.34 thì dây chuyền dev không còn hỏng theo.

## LƯỢT ĐỐI ĐÁP + HAI MODEL BẤT ĐỒNG 28-09 12:xx - hai tín hiệu lỗi đo được trên kết quả đã có (CPU, không tốn GPU)

**Lượt đối đáp.** Cặp câu thoại liền kề ở hai đoạn văn liền nhau, chia theo dấu ngoặc (đáp án 7 truyện, bài làm qwen3:8b):

| kiểu cặp | khác người | cùng người | qwen3:8b gán cùng người mà sai |
|---|---|---|---|
| đoạn trước ĐÓNG ngoặc, đoạn sau MỞ ngoặc mới | 91 | 4 | **38/42** cặp nó gán cùng người (LN: TCF 4, Nise 3, HDST 9, Yamiyo 19, YMP 2; TMA 1) |
| đoạn trước để NGỎ ngoặc (lời nói tiếp) | 0 | 11 (TMA) | - (khoá "thoại nối tiếp" đã lo) |
| gạch đầu dòng (Tắt đèn) | 16 | 0 | 5 (luật 7ca7ef7 đã lo ở host) |

Một cặp đóng -> mở mà cùng một người thì 90% là máy bỏ lỡ lượt đổi. Tự sửa ở host thì KHÔNG đáng (`scratchpad/
sim_alternation.py`, 19 lượt model x truyện): sàng "mẫu hội thoại" của Muzny và cs. 2017 (A, B, B -> A, B, A) chỉ đổi 1 câu,
vì lỗi của model là cả dãy A, A, A sau một câu A có lời dẫn; luân phiên cả dãy với người kể ngôi thứ nhất làm vai kia: +5
(HDST 4, Yamiyo 1), 0 hỏng; lấy người có tên gần nhất làm vai kia: +9 -3. Nên làm hai việc khác:
1. **Hộp "Việc cần duyệt" thẻ "Lượt đối đáp"** (`webui/work_items.py`, nhánh `feat/turn-doubt`): mỗi cặp như thế là một thẻ sửa
   CÂU SAU, lựa chọn đầu là người kể "tôi" (truyện ngôi thứ nhất), rồi người có tên nói nhiều nhất chương. Độ chính xác đã đo
   90% - cao hơn mọi tín hiệu khác trong hộp.
2. **Prompt** (nhánh `dev/ln-turns`): quy tắc 2 thêm "đoạn thoại liền nhau không lời dẫn là hai người luân phiên" và "ngoặc
   đặc biệt 『』 [ ] là một giọng riêng" (Yamiyo 41 câu 『』 của Tọa Phu Đồng Tử thành SUMIRE/HINA/TOMOBE; TCF 8 bài đăng ẩn
   danh thành Kuchinashi). Đo ở hàng GPU n, cùng 5 chương LN, so với mốc qwen3:8b.

**Hai model bất đồng về người nói = câu đáng nghe lại** (`scratchpad/disagree.py`: mỗi model gom nhãn qua đúng
`canonical_speaker_names`; "HINA" và "ONIZUKI HINA" coi là đồng ý). Model chính qwen3:8b, model phụ LoRA v2 (4B):

| truyện | câu | 8b sai | cờ (tải duyệt) | bắt được lỗi | cờ đúng là lỗi | tin cậy tự báo, cùng tải: bắt / đúng |
|---|---|---|---|---|---|---|
| Tắt đèn XX, XXI, XXIV | 112 | 30 | 47% | 77% | 43% | 53% / 30% |
| TMA test (chưa học) | 156 | 58 | 25% | 55% | 82% | 16% / 23% |
| YMP 248 | 47 | 18 | 38% | 89% | 89% | 33% / 33% |
| Tam quốc 50-52 | 219 | 46 | 64% | 87% | 29% | 67% / 22% |

Duyệt 20% số câu (xếp: số model phụ bất đồng, rồi tin cậy thấp): bắt 33-50% số lỗi, tin cậy tự báo 11-35%, ngẫu nhiên 20%.
So với bộ chấm ứng viên đang xếp hộp "Việc cần duyệt" (`review_curve.py` + `scratchpad/review_curve2.py`, 143 câu TMA test, chấm
chặt, máy một mình 67,1%): duyệt 20% -> bộ chấm 81,1%, LLM phụ 83,2%, LLM phụ rồi bộ chấm **85,3%** (trần 87,4%); duyệt 30% ->
85,3 / 89,5 / **91,6%** (trần 97,2%); dưới 15% thì bộ chấm một mình đã bằng cách ghép. Bầu đa số tự đổi nhãn (hai model phụ
cùng ý, khác 8b): YMP +11, TMA +2, Tam quốc +2, Tắt đèn -3 - không bền, KHÔNG tự áp. Kết luận: lượt phân tích thứ hai bằng
model 4B là tín hiệu duyệt tốt hơn tin cậy tự báo ở cả 4 truyện và cộng thêm vào bộ chấm từ mức duyệt 20%; giá là một lượt
phân tích nữa (4B ~ nửa thời gian 8B). Chưa dựng vào app: chờ số trên bộ LN (hàng i đo qwen3:8b, v2, v3 cùng 5 chương).

**Lỗi người nói của qwen3:8b trên LN, theo loại** (4 chương, 288 câu, 130 câu sai, nhãn đã gom tên): tên A -> tên B **104**
(Yamiyo 72, trong đó 41 câu 『』 của Tọa Phu Đồng Tử; phần còn lại phần lớn là gộp/lệch lượt đối đáp), đáp án NARRATOR mà
model gán người có tên 11 (TCF: 8 bài đăng ẩn danh thành Kuchinashi), người vô danh bị gán tên đã biết 9 (ông chú ở Nise),
người có tên thành vô danh 6. "Chộp tên quen" theo nghĩa hẹp (vô danh -> tên) là lỗi NHỎ; lỗi lớn là nhầm giữa những người
đã biết - đúng hai thứ prompt `dev/ln-turns` nhắm tới.

**Chương đo thứ 6 (28-09 13:xx): Love Unseen 07** - LN Nhật ngôi thứ nhất, 132 câu có người nói, gần như toàn đối đáp hai
người không lời dẫn (Kakeru - Fuyutsuki, Kakeru - mẹ qua điện thoại). Hai truyện định chọn trước (Năng lực bá đạo, Đã bảo
là cùng nhau tự sát) hoá ra là truyện TRUNG - kho hiện chỉ có 6 truyện LN Nhật/Hàn thật. Gold phát lại qua host 99,7%: lệch
duy nhất 90 - đoạn KỂ ("Tôi nhìn những người bên trong...") ngay sau một câu thoại quên đóng ngoặc bị khoá thoại nối tiếp
gán cho người vừa nói (lỗi host, chưa có cách phân biệt bằng dấu câu: đoạn giữa một bài nói dài ở TMA cũng y như thế).

## LORA NỀN 8B TRÊN CARD 8 GB 28-09 (chủ sách: "sao không huấn luyện trên nền qwen3:8b?")

Unsloth trong WSL2 archlinux (`train_lora_unsloth.py`, cùng siêu tham số với 4B). Thử VRAM trên 8 mẫu DÀI NHẤT:
1. Bản 4-bit "dynamic" của Unsloth (`unsloth/Qwen3-8B-unsloth-bnb-4bit`, 6,98 GB - giữ vài lớp 16-bit): KHÔNG NẠP ĐƯỢC
   ("Some modules are dispatched on the CPU") - card 8 GB trừ màn hình và app còn ~6,4 GB.
2. Bản 4-bit thường (`unsloth/Qwen3-8B-bnb-4bit`, 5,67 GB): nạp được; khuôn chat Qwen3-8B làm mẫu dài nhất 4.526 token
   (4B-2507: 4.276) -> `--max-length 4608`.
3. Bước đầu hết VRAM ở loss: "No or negligible GPU memory available for fused cross entropy" - Unsloth dò VRAM trống để chia
   khúc logits, thấy ~0. Sửa: `UNSLOTH_CE_LOSS_N_CHUNKS=32` (đặt TRƯỚC import unsloth). `offload_embedding` KHÔNG dùng được:
   nhánh tối ưu `FastLanguageModel` của Qwen3 lặng lẽ bỏ qua, còn `FastModel` từ chối trên WSL.
4. Với (2)+(3): bước 1 xong 32 giây, VRAM 7,85/8,15 GB - rồi bước 2 bò (GPU 99% nhưng 32 W thay vì 77 W, RAM máy còn
   trống 2,1 GB): bộ nhớ tràn qua lại VRAM <-> RAM. Kết luận đang chờ số cuối.
Hạ tầng rút ra cùng lúc: WSL `networkingMode=mirrored` làm rớt wifi Realtek 8852BE (đổi sang nat); ở nat, dải mạng của
WSL (192.168.0.1/20) trùng cổng wifi 192.168.0.1 nên WSL không ra mạng - model tải bằng Python bên Windows
(`LLM_Train/scripts/fetch_hf.py`), WSL chạy OFFLINE; xuất GGUF 8B cũng làm bên Windows (`serve_lora.py --like qwen3:8b
--quantize q4_K_M`, gộp CPU với bản gốc 16-bit).

**Lên đám mây (28-09 13:xx, chủ sách: "thử cả 9b đi / 8b, 4b thì huấn luyện", "sử dụng hết tài nguyên").** Cùng data_v3, cùng
`train_lora_unsloth.py` (thêm `--load-16bit`, `--time-limit-hours`, fp16 khi card không có bf16):
- Kaggle (miễn phí 30 giờ/tuần, T4 16 GB): 8B QLoRA trên nền 4-bit "dynamic" của Unsloth - ~100 s/bước, ~6 giờ/epoch. L4 không
  cấp cho tài khoản miễn phí (`machine_shape` bị bỏ qua); Qwen3.5 trên T4 phải float32 nên 9B không chạy được ở Kaggle.
- Modal (30 USD/tháng, spend limit 0): L40S 48 GB. Qwen3.5-9B LoRA 16-bit (Unsloth không khuyên 4-bit cho Qwen3.5): **12 s/bước,
  ~45 phút/epoch, ~1,5 USD** - nhanh hơn card nhà ~5 lần và rẻ, nên mọi thử nghiệm huấn luyện chuyển lên đây (4B 1 và 2 epoch
  16-bit, 8B 16-bit); GPU nhà dành trọn cho ĐO - chỗ nghẽn thật. Xuất GGUF làm ngay trên Modal (`modal_train.py --gguf`).
- Card nhà khi huấn luyện 4B: màn hình + app chiếm ~1,5 GB, trần `--vram-cap 0.95` làm driver tràn VRAM sang RAM (38 -> 295
  s/bước); dùng 0,78.

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
đúng 33%). Trong hệ kết hợp nó chỉ thêm +2 điểm độ đúng trên nền LoRA, nhưng cho hộp "Việc cần duyệt" (docs/STUDIO_REVIEW.md)
nó là nguồn xếp hạng tốt nhất: chỉ ra ĐÚNG câu nào người nên nghe lại. **ĐÃ ĐO (27-09 17:3x, `quote_scorer/review_curve.py`, 143 câu test TMA, chấm chặt):**

| người duyệt | 10% câu | 20% | 30% | 50% |
|---|---|---|---|---|
| LoRA một mình 74,8% -> xếp theo bộ chấm (bất đồng chắc trước) | 80,4% | **84,6%** | **89,5%** | **98,6%** |
| ... xếp theo tin cậy LLM tự báo | 75,5% | 79,7% | 83,2% | 88,1% |
| ... ngẫu nhiên (500 lần) | 77,3% | 79,9% | 82,4% | 87,4% |
| ... trần (câu sai trước) | 84,6% | 95,1% | 100% | 100% |
| qwen3:8b một mình 67,1% -> bộ chấm / LLM tự báo / ngẫu nhiên, duyệt 20% | | 81,1 / 72,7 / 73,7% | | |

Tin cậy LLM tự báo KHÔNG hơn ngẫu nhiên; bộ chấm cho lợi gấp ~2 lần ngẫu nhiên. **Đổi quyết định 17:0x "gác bộ chấm"**:
vai của nó là CHỌN CÂU CHO NGƯỜI DUYỆT trong hộp "Việc cần duyệt" - chỉ xếp hạng, không đổi nhãn, nên chạy được phía
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
**Kết quả (28-09 05:4x): KHÔNG đổi sang qwen3:4b.** Tam quốc (truyện chưa thấy) F1 giọng **56,4%** vs qwen3:8b 74,8% -
thua cả ba hồi (65,9 / 58,8 / 56,2 vs 74,7 / 76,0 / 80,7), nhãn chặt 63,9 vs 79,5%. YMP 248 có người kể (47 câu): 59,6
vs 56,1% - ngang, còn hai LoRA 79,7 / 82,8%. Lợi thế trên TMA là của riêng truyện ấy, không chuyển sang truyện khác.

Chuyện chọn model, theo thước giọng + luật mới: v2 thắng 5/8 chương (TMA 2-2, Tam quốc 2-1, YMP 1-0), gộp TMA +4,0,
YMP +26,7, Tam quốc -0,6 (hoà); cảm xúc hơn 6-9 điểm; nhanh 1,5 lần. Cổng "v2 >= qwen3:8b trên truyện chưa thấy" đo bằng
giọng: hoà, không đạt rõ -> **vẫn giữ qwen3:8b**, nhưng lý do đã khác hẳn lúc 21:xx. Việc kế:
1. Gộp luật tên gọi vào dây chuyền (lợi cho mọi model; đổi hash - không lô nào cần resume).
2. Thước chính của mọi phép đo người nói từ nay là F1 giọng; nhãn chặt vẫn báo kèm (tên hiển thị trong Studio).
3. ~~Neo cách viết tên vào văn bản cho phần HIỂN THỊ~~ - xong (`restore_source_marks`, trên).
4. Một truyện chưa thấy nữa, tên thuần Việt (văn học Việt hết bản quyền, wikisource), 2-3 chương gold, chạy lại cổng.
   -> Tắt đèn, mục dưới.
5. Tên tự (Tử-long = Triệu Vân, Công-cẩn = Chu Du): sách Trung giới thiệu bằng "<tên>, tự (là) <tên tự>" ("Bàng Thống
   tự là Sĩ-nguyên", "Hoàng Trung, tự Hán-thăng" - Tam quốc 047, 053) - một luật đọc câu giới thiệu ấy thành sổ bí danh
   theo cuốn; đo được bằng chính các bí danh đáp án Tam quốc đã ghi ("CHU DU,DU,CHU CÔNG-CẨN,...").

## TRUYỆN VIỆT 28-09 01:xx - Tắt đèn lộ hai lỗi của HOST trước cả khi chạy model

Tắt đèn (Ngô Tất Tố, vi.wikisource, hết bản quyền): truyện đầu tiên VIẾT bằng tiếng Việt chứ không dịch. Đáp án chương
XX, XXI, XXIV (`gold/tat_den_ngo_tat_to/`): 245 đoạn, 112 câu thoại. Ba cái khó mà mười truyện dịch không có: thoại gạch
đầu dòng với rất nhiều cặp hỏi - đáp KHÔNG lời dẫn; nhân vật chỉ có chức danh suốt cuốn (quan Phủ, lý trưởng, cai lệ -
dạng ấy là tên, như "Trịnh lão"); vợ gọi theo tên chồng ("chị Dậu" - "DẬU" trơn là chồng chị).

1. **Khoá "thoại nối tiếp cùng người nói"** (`_repair_continued_dialogue_speakers`, từ 10-08) coi hai đoạn thoại liền
   nhau không mở bằng ngoặc là MỘT lời nói kéo dài. Đúng với ngoặc kép bỏ ngỏ qua nhiều đoạn; sai hoàn toàn với gạch
   đầu dòng, nơi mỗi dòng là một lượt mới: câu trả lời mang tên người vừa hỏi. Phát lại đáp án (`replay_all.py`, Ollama
   giả trả lời đúng): Tắt đèn **90,2% -> 100%** người nói (11/112 câu bị đè, đúng mọi cặp hỏi - đáp liền); 11 truyện
   còn lại không đổi một số nào. Câu trả lời thô đã ghi của ba model trên Tam quốc 50-52 phát lại qua luật mới
   (`replay_from_candidates.py`): không đổi - thoại Tam quốc gần như luôn có "X nói:" đứng trước. Sửa: dòng mở bằng
   gạch đầu dòng (`DIALOGUE_DASH_TURN_PATTERN`, cùng mẫu bộ tách câu dùng để khoá dòng ấy là thoại) là một lượt mới.
2. **Luật tên gọi** (`merge_given_names`, 27-09) gom nhãn "DẬU" về "CHỊ DẬU" - chữ cuối của đúng một tên nhiều chữ -
   tức chồng đọc bằng giọng vợ. `voice_identity.py --gold-check` bắt được ngay trên nhãn đáp án. Sửa: tên mở bằng chữ
   xưng hô (`NAME_PREFIX_TITLES`: chị, anh, bác, cụ, mẹ...) không làm đích gom. Cái giá: "DẬU" không gom về "ANH DẬU"
   khi sổ chỉ có anh (một người hai giọng - nhẹ hơn hai người một giọng); có "NGUYỄN VĂN DẬU" thì vẫn gom về đó.
   `--gold-check`: 12 truyện không nhập hai người nào.

Cả hai lỗi nằm ngoài model: model nào cũng bị trừ như nhau, nên không đổi thứ hạng nào đã đo, nhưng mọi con số tuyệt
đối trên truyện Việt thuần trước bản sửa đều thấp oan. Việc kế: chạy cổng (qwen3:8b, LoRA v2, qwen3:4b) trên ba chương
này sau hàng GPU c3/g, chấm bằng F1 giọng.

**Cổng Tắt đèn (28-09 06:3x, 112 câu thoại, host đã sửa):**

| | F1 giọng | từng chương (XX / XXI / XXIV) | nhãn chặt -> sau gom | giây (3 chương) |
|---|---|---|---|---|
| qwen3:8b | **73,3%** | 74,3 / 80,4 / 72,0 | 75,9 -> 79,5% | 1.335 |
| LoRA v2 | 72,3% | 80,3 / 76,6 / 68,0 | 51,8 -> 78,6% | 797 |
| qwen3:4b | 47,4% | 65,0 / 46,7 / 51,6 | 54,5% | 855 |

Như Tam quốc: qwen3:8b và LoRA v2 ngang nhau về giọng (LoRA nhanh 1,7 lần, thua ở cách viết tên cho tới khi được gom),
qwen3:4b tụt xa -> giữ qwen3:8b. Nỗi lo "prompt cấm tiền tố xưng hô nên model ghi vợ là DẬU" không xảy ra: cả qwen3:8b
lẫn LoRA v2 ghi "CHỊ DẬU" / "ANH DẬU".

3. **Tên sai nằm lọt trong chữ khác** (lộ ra ở cổng này): qwen3:8b ghi "AN DẬU" cho 3 câu của anh Dậu. Bỏ dấu là "an
   dau" - chuỗi con của "Nguyễn Văn Dậu" ("v|an dau") - nên luật gom tên vắng mặt coi nó là có trong sách. Sửa:
   `source_occurrences` đếm NGUYÊN CHỮ (`str.find` rồi xét ranh giới, giữ tốc độ). Việc ấy làm lộ luật thứ hai: nhánh
   "chữ đầu lệch một ký tự" (dành cho tên kiểu Âu + họ bịa, `SELNE VALKRYN` -> `SELENE`) trỏ "TƯƠNG TỬ" về "LUONG" và -
   từ trước đó - "DONG VINH", "HỒNG CÁI" về "PHÁO LONG": với tên kiểu Việt chữ đầu là HỌ, lệch một chữ là họ khác. Nhánh
   ấy nay chỉ cho tên kiểu Âu. Đo lại 17 lượt (mọi model, TMA / YMP / Tam quốc / Tắt đèn): chỉ 3 lượt đổi, đều tăng -
   Tắt đèn qwen3:8b 72,7 -> 73,3, Tam quốc LoRA v1 74,6 -> 75,0, v2 74,2 -> 74,5; `--gold-check` sạch. Bản sao của luật
   trong `scripts/source_spellings.py` (gieo ở ranh giới lô) sửa cùng lúc - `test_source_spellings_agree` giữ hai bản
   khớp nhau.

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
- **Kiểm chứng chéo THEO TRUYỆN (hàng c3, xong 28-09 02:0x)**: 10 lượt, mỗi lượt học 9 truyện (dữ liệu dàn trang
  paragraph + dàn nhân vật), chấm truyện thứ 10 chưa từng thấy - đúng tình huống của app. Epoch cuối, 1.827 câu:

  | học trước | trung bình theo truyện | theo câu | hơn / hoà / thua "không học trước" (theo truyện) |
  |---|---|---|---|
  | không, và bỏ dàn trang + dàn nhân vật (base) | 47,1% | 46,6% | 2 / 1 / 7 |
  | không (para_cast) | 50,5% | 48,2% | - |
  | tiếng Trung CSI (zh) | 49,6% | 52,8% | 4 / 0 / 6 |
  | tiếng Anh PDNC + Trung (enzh) | **58,3%** | **68,5%** | **8 / 1 / 1** |

  Học trước tiếng Anh là thứ mang lợi (+7,8 điểm trung bình theo truyện; con số theo câu phồng vì truyện đông câu nhất -
  847 câu - nhảy 42 -> 80%); tiếng Trung một mình không giúp gì, khớp kết quả 0-shot 40% ở trên. Chênh giữa các truyện rất
  lớn (35-80%): con số cho một truyện mới là khoảng rộng, không phải một điểm. Dàn trang paragraph + dàn nhân vật cũng
  có ích (+3,4, hơn 7/10 truyện so với base). Kiểm chứng theo chương (cv) đang chạy.

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
