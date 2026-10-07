# Chương trình nghiên cứu model phân tích

Chủ sách, 27-09: *"model phân tích là linh hồn quan trọng nhất, cực kỳ quan trọng của project này. bạn phải nghiên cứu
cực kỳ sâu để tận dụng mọi nguồn kiến thức, thử nghiệm mọi cách."*

Model phân tích quyết định mỗi câu do AI đọc: người nói (-> giọng), loại đoạn (kể / thoại / nội tâm), cảm xúc, cường độ,
nhịp, âm lượng, giới tính. Sai người nói là lỗi người nghe nhận ra ngay (giọng sai người). Tài liệu này là bản đồ: mục
tiêu, cách đo, tài liệu đã/phải đọc, và MA TRẬN THÍ NGHIỆM với trạng thái. Chi tiết số đo từng lượt ở `LLM_EVAL.md`.

## Luật chọn model: CHÍNH XÁC trước, nhưng ĐONG ĐẾM giá (chủ sách, 04-10)

- **Đích số một là card 8 GB của chủ sách**: model, lượng tử, ngữ cảnh phải nằm 100 % trên GPU ở đó, đo thật trên máy nhà.
  Mac 16 GB chỉ là thứ yếu - model chỉ chạy được nhờ Mac không làm mặc định.
- Xếp theo độ chính xác, không theo tốc độ: tách hai lượt, cửa sổ rộng hơn, model to hơn đều được nếu đúng hơn RÕ.
- Nhưng "chậm hơn, RAM to hơn nhiều mà chính xác thêm chút xíu thì phải xem xét". Mọi phương án (B8/B9/B10/E2, model mặc
  định) báo CẢ lợi (F1 giọng TB hạt, hạt tệ nhất, CI) LẪN giá đo thật trên card nhà (thời gian phân tích/chương so với v8,
  VRAM đỉnh, RAM). Quyết:
  - lợi trong nhiễu hạt (~2 điểm) mà giá >= 1,5x thời gian hoặc VRAM sát trần 8 GB -> KHÔNG lấy;
  - lợi vượt nhiễu rõ -> lấy dù chậm;
  - giáp ranh -> đưa bảng lợi/giá cho chủ sách quyết.
- Giá đo bằng `LLM_Train/runs/cost_logger.py` (mỗi 10 s: VRAM card, % GPU, size_vram model Ollama, RAM) đối chiếu khung giờ
  từng lượt trong sổ hàng GPU; thời gian/chương lấy từ eval_models.json. Mốc 04-10: 4B v8 Q8_0 = 5.248 MiB VRAM (card dùng
  ~5,9/8,15 GB khi chạy).

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

## 07-10 Kế hoạch gốc kế tiếp sau B10: B13 - học với TẬP đáp án chấp nhận (ghi trước, Model)

**Vì sao là gốc, và vì sao lúc này.** Hai gốc của 04-10 là (A) đáp án chuẩn và (B) thuật toán học. B13 đánh vào chỗ hai gốc chạm
nhau: nhãn gold nói "câu này người A HOẶC người kể đều đúng" (652/1.827 câu gold có nhiều đáp án chấp nhận, mục B3 bên dưới), bộ chấm
cũng chấm như thế, nhưng huấn luyện SFT ép MỘT tên. Với model, đó là nhiễu nhãn ở đúng token quyết định: hai câu giống nhau nhận hai
"đáp án duy nhất" khác nhau, và model học cách lưỡng lự. Các hướng khác đã có số hoặc đang chạy: lệch phơi bày không phải gốc (E1),
kênh nhiễu âm (B6), thêm dữ liệu cùng kiểu (B9, B10), học từ lỗi của chính học trò (B11, chuỗi riêng), lịch sử-gold (đang xếp hàng,
nếu trần >= +5 chặt thì B12 lịch sử nhiễu chạy trước theo b12/PLAN.md). B3 là hướng gốc duy nhất trong danh sách 04-10 chưa đo.
Không phải bỏ phiếu hạt, không chỉnh prompt: đổi HÀM MỤC TIÊU cho khớp nghĩa của nhãn.

**Bước 0 - chẩn đoán trên CPU (~1 giờ, chạy ngay, không tốn GPU).** Trên gốc cổng 19 chương đã có (mrel430b, B9 s1234):
(i) phần lỗi người nói chặt rơi vào câu nhiều đáp án; (ii) trong data_b9, số mẫu có câu gốc gold với tập > 1 (phần data_v8; phần bạc
một thầy chỉ có một tên). Luật dừng ghi trước: câu nhiều đáp án mang < 15 % lỗi chặt -> KHÔNG chạy GPU, ghi kết quả âm, chuyển
sang ứng viên kế (B7 gom cụm theo người nói, nếu B7m chưa trả lời).

**Bước 1 - huấn luyện (GPU, sau B10 + SR + lịch sử-gold).** Đúng công thức B9 (data_b9, 527 bước, hạt 1234 rồi 1), biến duy nhất là
loss ở khoảng token giá trị `speaker`: thay CE một đáp án bằng log-likelihood biên trên tập chấp nhận,
`-log Σ_{c ∈ A} P(c | tiền tố)`, mỗi ứng viên chấm teacher-forced trên cùng tiền tố (k <= 4, chỉ vài token đuôi; ước +20-30 %
thời gian bước). Câu một đáp án: loss y như B9. Tập A dựng BẰNG MÃ từ nhãn gold (dấu `~`), không xin thầy lập luận.
Làm trong LLM_Train/b1/train_lora_w.py (cờ `--set-loss`), không đụng repo app; kiểm trên CPU bằng mẫu đồ chơi: tập một phần tử ra
đúng loss của B9 tới 1e-6.

**Luật thắng (cổng 19 chương / 11 truyện, chạy MỘT lần, TB 2 hạt so B9 cùng cổng).**
- THẮNG: F1 giọng >= B9 + 1,5 và người nói chặt >= B9 + 1,0, CI cụm theo truyện của F1 không chứa 0; không truyện nào tụt > 3
  chặt; Hàn không tụt > 2.
- Cơ chế phải khớp: tỉ lệ sai trên câu nhiều đáp án giảm >= 20 % tương đối, câu một đáp án không tụt > 1 điểm. Điểm tăng mà câu
  nhiều đáp án không giảm -> ghi "thắng không vì lý do dự kiến", không triển khai trước khi hiểu.
- ÂM: < B9 - 1 ở F1 giọng -> đóng hướng, ghi số. Giữa hai mốc -> hoà, không thêm hạt để "kéo" qua ngưỡng.

**Giá.** Bước 0: 1 giờ CPU. Cài loss: ~nửa ngày agent Sonnet theo đặc tả này (không commit, Model duyệt diff). GPU nhà: 2 x
(huấn luyện ~9 giờ + cổng ~4 giờ) ~ 26 giờ; hoặc một hạt trên Kaggle sau thứ Bảy 10-10 để rút còn ~13 giờ nhà.

**KẾT QUẢ bước 0 (07-10 08:4x): DỪNG theo luật ghi trước - không chạy GPU.** Cổng 19 chương, 1.349 câu chấm (LLM_Train/b13/DIAG.md,
số đếm từng chương khớp `lnj_table.collect()`). "Nhiều đáp án" trong 652/1.827 của 04-10 phần lớn là BÍ DANH của cùng một người
(`~` liệt kê cách gọi khác của một nhân vật trên gần mọi dòng) - bộ chấm đã gộp bí danh (`matched_person`), nên đó không phải nhiễu
nhãn ở quyết định chọn người. Mơ hồ THẬT (người kể hoặc nhân vật, NPC* hoặc người có tên, hai người khác nhau) = 14,8 % câu nhưng chỉ
mang **1,6 % lỗi chặt của mrel430bA (6/381) và 2,7 % của B9 s1234 (8/301)** - dưới mốc 15 %. Tỉ lệ sai trên các câu ấy 3-4 % so với
25-33 % trên câu một người: model gần như không sai ở đó. Trong data_b9 mơ hồ thật là ~4,1 % quyết định người nói (246 câu, 186 bị ép
về NARRATOR). Đọc: lỗi người nói nằm ở câu MỘT đáp án - chọn sai người, không phải bị dạy lưỡng lự. Hướng kế theo kế hoạch: gom cụm
theo người nói (B7) - đang chờ số B7m trong hàng.

## 04-10 Đột phá - đánh vào gốc: đáp án chuẩn và thuật toán học

Chủ sách 04-10: model phân tích là tính năng chính, nguồn gốc ý tưởng của app; bỏ phiếu nhiều hạt "không giải quyết gốc";
không tối ưu vặt. Hai gốc: (A) đáp án chuẩn, (B) thuật toán huấn luyện. Mọi thí nghiệm ghi giả thuyết + ngưỡng TRƯỚC,
đo F1 giọng theo truyện trên truyện MỚI (Nhật trước, Hàn sau), >= 2 hạt mỗi bên, ghi cả kết quả âm.

### Đặt lại bài toán

Từ 26-09 bài toán được đặt là: một LLM nhỏ SINH ra tên người nói cho từng câu, học từ ~2.000 quyết định người nói (data
v8: 10 truyện; tên người nói chỉ 1,3-2 % ký tự đáp án, đo 40 mẫu: 0,74 % token). Ba số đo 03-04/10 cho thấy cách đặt ấy
đã chạm trần của chính nó:
- Ba công thức (4B Qwen3, 4B Qwen3.5, 9B) cách nhau ít hơn dao động giữa các hạt của cùng công thức (bảng mặc định 04-10:
  Nhật MỚI 60,5 / 59,6 / 57,4 trung bình hạt). Model to hơn không mua thêm điểm.
- Loss phẳng ~0,007 từ 1/4 epoch: phần lớn gradient đi vào định dạng và trường cố định, không vào quyết định người nói.
- Một hạt có thể rơi vào CHẾ ĐỘ thiên lệch: 9B s1 gán "tôi" cho 42,8 % câu không phải "tôi" (gốc 10,2 %). Bỏ phiếu hạt chỉ
  bảo hiểm trước hạt xấu (hơn trung bình hạt +1,2…+4,2), không hơn hạt tốt nhất (mọi CI chứa 0) - nhiễu hạt không phải trần.

Các cách đặt lại, mỗi cách là một thí nghiệm có ngưỡng ghi trước:
- **Kênh nhiễu (B6).** Không dạy model đoán tên. Chấm mỗi ứng viên c bằng log P(câu thoại | ngữ cảnh trước + "c nói:") của
  một LM NỀN không huấn luyện, trừ log P(câu thoại | ngữ cảnh, không tên) (PMI), chọn c cao nhất. LM đã học từ hàng tỉ câu
  cách người ta nói - xưng hô, vai vế, giọng; hướng cũ bắt model nhỏ học lại điều đó từ 2.000 nhãn.
- **Gom câu theo người nói rồi mới đặt tên (B7).** Thứ người nghe nghe là "câu nào cùng một giọng". Học quan hệ cùng/khác
  người nói từ câu có thẻ dẫn tường minh trong 161 cuốn Corpus (bỏ thẻ khỏi câu để không lộ đáp án) - dữ liệu tự giám sát
  gần như vô hạn; tên đặt một lần cho cả cụm, cho cả cuốn.
- **Chấm ứng viên với tập đáp án chấp nhận (B3).** 652/1.827 câu gold có nhiều đáp án chấp nhận; huấn luyện ép MỘT đáp án
  là nhiễu nhãn. Encoder chấm cặp (câu, ứng viên), loss biên trên cả tập chấp nhận.
- **Đáp án chuẩn (A).** Hai thầy Opus độc lập gán lại 7 chương gold (không nhìn gold): đồng thuận thầy-thầy, thầy-gold, phân
  loại câu bất đồng -> tỉ lệ lỗi gold + trần thầy. Thầy >= ~85 % trên truyện mới thì dựng nhãn bạc x10-x50 (Lead).
- **Chẩn đoán "tín hiệu bị pha loãng" (B1a).** Giữ cách đặt cũ, chỉ nhân x10 loss token giá trị "speaker" của đoạn thoại.
  Không phải hướng, là phép thử giả thuyết: nếu thắng thì cách đặt cũ còn chỗ; nếu hoà thì trần nằm ở cách đặt bài toán.

### B1a - chẩn đoán pha loãng (ghi trước, 04-10 20:xx)

train_lora.py + `--speaker-weight 10` (token giá trị "speaker" của đoạn không phải narration; ~0,74 % token đáp án -> ~7 %
loss) + `--seed`; còn lại y lora29v8. Hạt 1234 (so CẶP với lora29v8) và hạt 1. Đo Nhật MỚI 11 ch (mh/rk/sm), Hàn MỚI sau.
Mốc họ v8 trên 11 ch: gốc 61,5, TB 4 lượt 60,5. THẮNG: TB 2 hạt >= 62,5 và không truyện nào tụt > 5 so với TB họ v8; HOÀ:
trong ±2,0; THUA: < 58,5. Báo kèm adj1/share (chữ ký chế độ "gán cho tôi"). Script: LLM_Train/b1/.

### B6 - kênh nhiễu zero-shot (ghi trước, 04-10 20:xx)

LM nền Qwen3-4B-Instruct-2507 (4-bit, không huấn luyện). Mỗi câu thoại gold của 11 ch Nhật MỚI (rồi 8 ch Hàn MỚI): ngữ cảnh
= chữ chương trước câu (cắt theo ngân sách token), ứng viên = (a) người nói có trong gold của chương + người kể (trần với
dàn nhân vật biết trước), (b) dàn nhân vật do 4B v8 xuất cho chương ấy (thực tế). Điểm = log P(câu | ngữ cảnh + "c nói:")
- log P(câu | ngữ cảnh). Đo trên CÙNG câu với 4B v8: độ đúng người nói (credit như bộ chấm), lỗi theo loại (lệch lượt /
"tôi" / người lạ), và độ BỔ SUNG = % câu 4B v8 sai mà kênh đúng.
- ĐỘT PHÁ: (b) đúng >= 4B v8 + 3 điểm trên cùng câu.
- HỨA HẸN: (b) trong ±3 của 4B v8 và bổ sung >= 30 % lỗi của v8 -> thử ghép (kênh làm đặc trưng / người phân xử).
- ÂM: (b) < 4B v8 - 3 và bổ sung < 30 %.
- Đã dựng (04-10 18:5x): 767 câu Nhật MỚI + 582 câu Hàn MỚI (LLM_Train/b6/items_*.jsonl); bộ chấm kiểm trên CPU bằng
  Qwen3-0.6B; với điểm ngẫu nhiên độ đúng (a)/(b) là 22-28 % (mốc dưới), v8 trên cùng câu 71,8 % (F1 61,7). Báo ba cách
  chuẩn hoá (PMI - chính, theo độ dài, thô) nhưng ngưỡng chỉ áp cho PMI.
- **KẾT QUẢ 04-10 19:47: ÂM.** Độ đúng người nói trên cùng câu - Nhật MỚI 767 câu: v8 71,8 %, kênh (a) 43,2 %, (b) 42,4 %
  (ngẫu nhiên 22-28 %); Hàn MỚI 582 câu: v8 72,2 %, (a) 38,1 %, (b) 37,8 %. Bổ sung (b) = 30 % lỗi v8 ở Nhật, 18 % ở Hàn -
  ngang mức ngẫu nhiên (~27 %). Kênh không bớt lệch lượt (12,5 % vs 13,0 %) và nhầm "tôi" nhiều hơn (8,6 % vs 3,1 %). Ba cách
  chuẩn hoá cho cùng lựa chọn (mốc không tên và độ dài câu chung cho mọi ứng viên của một câu). Đọc: LM nền 4B không nhận ra
  người nói từ văn phong câu thoại bản dịch Việt; quyết định nằm ở cấu trúc đối đáp và lời dẫn, không ở "cách người ấy nói".
  Số: LLM_Train/b6/result_{jp,kr}_pmi.txt.

### A1 - trần thầy và chất lượng gold (04-10 tối) + ĐỔI GOLD và ĐỔI THƯỚC

Hai thầy Opus độc lập gán lại 7 chương (mh009, rk014, kurakon034, nise086, zenith058, villain22, hdst052a) bằng harness
chạy NGUYÊN bộ phân tích của app với Ollama giả - prompt khớp từng ký tự với prompt 4B nhận; không nhìn gold.
- Đồng thuận (người nói chặt, 554 câu): thầy #1 đúng 94,6 %, thầy #2 96,2 %; chỉ 8 câu (1,4 %) hai thầy cùng chọn mà khác
  gold -> lỗi gold ước ~1,4 %. Gốc không phải chất lượng gold mà là SỐ LƯỢNG tín hiệu + năng lực model nhỏ.
- Lỗi theo loại (gold cũ): Nhật - thầy lệch lượt 1,1 % / v8 28,5 %; Hàn - thầy nhầm "tôi" 0,4 % / v8 18,9 %. Cùng thông tin,
  thầy không mắc hai lỗi chính của 4B -> thông tin ĐỦ trong prompt; 4B không dùng được nó. => A2 chưng cất (cặp prompt
  thật / câu trả lời thầy, kèm lý do) là hướng chính; B9 = 4B học v8 + bạc, B8 = con trỏ học v8 + bạc.

**ĐỔI GOLD (04-10):** luật chủ sách 20-09 "nội tâm = giọng chính người đang nghĩ" áp lên MỌI gold - dòng kind T có
NARRATOR đứng đầu mà có tên người nghĩ: tên lên đầu, NARRATOR giữ đủ điểm nếu dòng còn chấp nhận N (N,T), không thì NARRATOR~.
1.015 dòng (1.006 N,T + 9 T) / 94 file; 35 dòng T chỉ có NARRATOR (tên phép, dòng hệ thống trong nháy đơn) giữ nguyên.
**ĐỔI THƯỚC (04-10, Lead):** dòng có nhiều đáp án ĐỦ điểm thì cụm đáp án là phía nhãn TRÚNG (NARRATOR hay người nghĩ - các tên
đủ điểm trong một dòng là bí danh của một người); trượt hết thì phương án đầu. N,T là lời gián tiếp tự do: cả hai cách đọc
đúng với người nghe; dòng thuần T vẫn đòi người nghĩ. Mọi bảng TRƯỚC mục này chấm bằng gold cũ + phương án đầu - KHÔNG so thẳng.
(ln_table.matched_person; dữ liệu huấn luyện mới dựng từ gold MỚI.)

Chấm lại bằng gold mới + thước mới:
- A1 (7 ch): thầy 92,9 (Nhật 94,1 / Hàn 91,3); v8 53,3 (6 ch: Nhật 44,7 / Hàn 62,8).
- Bảng mặc định (TB mọi hạt / hạt tệ nhất / gốc): Nhật MỚI 11 ch - 4B v8 58,7 / 57,7 / 59,5; q35 57,7 / 55,5 / 57,7;
  9B 56,1 / 50,6 / 60,8. Hàn MỚI 8 ch - 4B v8 67,6 / 64,9 / 68,8; q35 70,3 / 69,3 / 69,3; 9B 66,0 / 57,2 / 71,7.

**Thầy Sonnet vs Opus (04-10 tối, cùng harness, 7 ch A1, thước 04-10):** F1 giọng Sonnet 89,9 vs Opus #1 92,9 (-3,0; Nhật
91,8 vs 94,1, Hàn 87,5 vs 91,3); người nói chặt 89,8 vs 94,5 (-4,7). Lỗi chính của Sonnet: đặt tên cho người lạ vô danh, nhầm người
nói trong nhóm đông (villain22); lệch lượt chỉ 0,8 %. Ngưỡng ghi trước "Sonnet >= Opus - 3": F1 đúng mép, người nói chặt trượt
-> theo luật chính xác trước, thầy cho MỌI đợt bạc là OPUS.

### Bước 1 của Lead (04-10, tài liệu breakthrough_lit.md): chẩn đoán và trần, chỉ tốn suy luận (ghi trước)

Cùng 11 ch Nhật MỚI (rồi 8 ch Hàn MỚI), cùng 4B v8 (lora29v8), qua bộ phân tích thật (nhánh đo dev/breakthrough-eval: các
hook tắt mặc định, prompt y hệt khi tắt).
- **E1 - lỗi do cách SINH hay do HIỂU.** Ép đáp án đúng vào chỗ model đang dựa vào quyết định của chính nó: (i) giữa các lô -
  "lượt nói trước" lấy người nói GOLD thay vì đầu ra của model, chạy sinh thật; (ii) trong lô - tiền tố JSON các đoạn trước
  là gold, chấm logprob ứng viên ở vị trí "speaker" (HF + adapter, prompt ghi lại từ lượt thật). Đếm lỗi "lặp người câu
  trước" (câu sai mà nhãn = người nói gold của câu thoại liền trước). Giảm >= 40 % -> gốc là sinh tự hồi quy (đi hướng chấm
  ứng viên / quyết định độc lập); giảm < 15 % -> gốc là hiểu.
- **O1 / O2 - trần của thông tin cảnh và xưng hô.** Chèn vào prompt hiện tại "Nhân vật có mặt trong cảnh này" (O1) và "Cách
  xưng hô giữa các nhân vật" (O2), cả hai do agent Opus đọc chương viết (không nhìn gold; Lead làm). Hướng nào cho F1 giọng
  >= +3 trên Nhật MỚI mới đầu tư (O2 dương -> hồ sơ xưng hô tự rút từ câu tường minh).
- **E2 - độ dài ngữ cảnh/lô.** batch_segments / batch_chars / previous_text-next_text quét về ~256 / 512 / 1.024 token so
  với hiện tại (~3k token người dùng). Một mức ngắn hơn cho F1 >= hiện tại + 2 và không tụt ở Hàn -> đổi mặc định.

**Kết quả E1 (i) (04-10 21:2x, thước 04-10).** Cùng lora29v8, cùng digest (= cùng hạt) nên so CẶP với v8 gốc trên 767 câu thoại
Nhật MỚI: lỗi "lặp người câu trước" 69 -> 25 (giảm 64 %, qua ngưỡng 40 % về phía SINH), đúng chặt 71,8 -> 73,9 %, lỗi "tôi"
24 -> 27, nhưng F1 giọng 59,5 -> 59,6 (họ v8 dải 57,7-59,7). 44 lỗi lặp bớt đi chỉ thành 16 câu đúng thêm - phần còn lại đổi sang
lỗi khác. Kết luận: lan lỗi giữa các lô là THẬT (đúng loại lỗi lặp) nhưng gần như không đóng góp vào khoảng cách 53 vs 93 với thầy;
chấm ứng viên / quyết định độc lập KHÔNG phải hướng chính. Gốc còn lại là HIỂU (model không đọc được cấu trúc lượt) -> A2 chưng cất,
B8 con trỏ, B8 tách việc. E1 (ii) (ép gold trong lô, HF) xếp sau.

**Kết quả E2 (05-10 02:xx, thước 04-10, so CẶP với v8 gốc cùng digest, Nhật MỚI 11 ch).** Hai biến thể:
- HẸP (lô 3 đoạn, kề 250 ký tự, e2sv8): TỆ hơn - đúng chặt 71,8 -> 66,6 %, lỗi lặp 35. Bỏ. Rokujouma 122a hỏng hẳn (lỗi
  "Narration-before-next-paragraph-thought context hash is not source-ledger-bound" ở lô ngắn - bug đường kiểm ngữ cảnh khi lô nhỏ;
  biến thể rộng chạy đủ 11 chương nên không dính).
- RỘNG (9 đoạn "ngay trước" thay 4, e2wv8; hook ABOOK_EVAL_SETTINGS previous_turns): F1 giọng 59,5 -> **61,8 (+2,3)**, đúng
  chặt 71,8 -> 73,7 %, lỗi lặp 69 -> **22 (-68 %, cùng hướng E1)**. Giá ~1,0x: 500 s/chương (E1 cùng ngày 497), VRAM không đổi
  (model 5.248 MiB, đỉnh card 5.932 MiB), RAM đỉnh 18,8 GB.
- Lead 05-10: RỘNG = ứng viên mặc định, chốt nếu Hàn (e2wkr, 8 ch) không tụt quá 1 điểm F1. Từ nay B8/B9 đo ở cửa sổ rộng
  (cây ghim ABook_pin_wide a40231f3), mốc a_rộng = e2wv8; dữ liệu huấn luyện giữ hẹp (đã kiểm: v8 train hẹp, đo rộng tốt hơn).
- **Hàn (05-10 07:16, 8 ch đợt 3, gold bản 1): F1 giọng +0,9 [KTC -3,3; +4,8], người nói chặt +0,5, cảm xúc +0,3; hơn 3 / thua 5
  chương -> KHÔNG tụt quá 1 điểm -> RỘNG QUA CỔNG, là ứng viên mặc định.** Lỗi lặp 48 -> 47 (Hàn vốn ít lỗi lặp, lợi của rộng nằm ở
  Nhật). Cặp cùng máy meke/demonking (v8home): -1,9 [-6,1; +1,5], 2 chương, trong nhiễu.

**Gold Hàn bản 2 (05-10, nhánh dev/gold-kr-brackets 1a51a90f) - CHỈ cho lượt đo trên main >= e926ed12** (dòng nguyên vẹn [..] /
【..】 là đơn vị giọng). zenith/058: 34 dòng "[...]" của hồn ma N -> D SHINCHEOL (LÃO SHIN~); ke_yeu/26 seq 62 (thông báo hệ thống)
và nhan_vien/170 seq 146 (tên sổ) N -> D NARRATOR. seq không đổi. Mọi lượt trên cây ghim cũ (kể cả E2/E8/B8/B9 hiện tại) dùng bản 1.

**E8 sửa đường đo (05-10 07:4x).** Thăm dò: Ollama 0.33.2 /api/generate với think + format nhét JSON vào "thinking", không nghĩ
(21 ký tự, đáp rỗng); /api/chat cùng mẫu chat thì nghĩ rồi trả JSON. Hook nhánh think đổi sang /api/chat (08e12992, cây ghim
ABook_pin_think2); nhánh think=false giữ /api/generate như app.

**E8 kết quả lượt 1 (05-10 09:46) - CHƯA KẾT LUẬN.** qwen3:4b gốc, cửa sổ 9, 6 chương (rk 014/015/122a, sm 195, villain 22,
nhanvien 170). think=false: F1 giọng 47,3 % (688 câu) - thua v8 8,9 điểm [KTC -14,7; -4,7], người nói chặt -16,7, như dự kiến
(nền vs LoRA). think=true: HỎNG 6/6 chương - ngay lô 1 đoạn model nghĩ hết 2.048 token (~8.500 ký tự, lặp "Wait, but...") mà
chưa trả JSON; ngân sách nghĩ 1.024/lô và ngữ cảnh 7.168 của project đo quá nhỏ. Thử lại thí điểm (E8P): 2 chương (sm 195,
nhanvien 170), ngân sách nghĩ 8.192, ngữ cảnh 16.384 (hook think_num_ctx, ABook_pin_think3 b3deb76a), sau OmniVoice. Giá ước:
~60 token/s, 2-8k token nghĩ/lô -> 1-2 phút/lô, ~1,5-3 giờ cho 2 chương (think=false: 4-12 phút/chương) - nghĩa là dù thắng,
suy nghĩ lúc chạy KHÔNG dùng được trong app trên card nhà (x10-30 thời gian); câu hỏi chỉ là có đáng làm RLVR có suy nghĩ không.
Nếu thí điểm vẫn không trả JSON trong 8k token phần lớn lô -> nhánh nghĩ của 4B gốc coi như âm.

**Kết quả O1+O2 (05-10 03:37, thước 04-10, chạy lại trên cây ghim 1808bdf7 = o12cv8).** Dump prompt + raw khớp TỪNG BYTE với lượt
nghi ngờ o12v8 (612/612 lô) -> lượt cũ không bị nhiễm. Khối oracle "có mặt" (O1) + "xưng hô" (O2) chèn vào prompt v8: F1 giọng
59,5 -> 60,2 (+0,7, trong nhiễu hạt), lỗi lặp 69 -> 23, nhưng đúng chặt 71,8 -> 63,0 % (model lấy tên/biến thể tên trong khối
oracle, lệch tập tên gold - cụm giọng gần như giữ). Kết luận: biết ai có mặt / ai xưng hô thế nào KHÔNG mở khoá người nói cho 4B ->
B10 (trạng thái cảnh) không chen trước B8; xuống cuối hàng (dữ liệu + hook dev/breakthrough-eval-b10 đã sẵn).

**Chuyên gia cảm xúc VSMEC (05-10, CPU) - ÂM.** visolex phobert-emotion / bartpho-emotion (UIT-VSMEC, 7 lớp, ánh xạ ghi trước) trên
767 câu thoại/nội tâm Nhật MỚI: thay hẳn 48,8 / 56,8 %, lai (p >= 0,7) 60,1 / 80,6, lai ngược (chỉ đè neutral) 69,0 / 83,8 vs v8 86,7
("luôn neutral" 70,1). Lệch miền (bình luận mạng xã hội vs LN dịch), tự tin sai (PhoBERT p >= 0,7 trúng 51 %), thiếu 5 nhãn ABook.
Cảm xúc giữ trong LLM; B8 d trả lời câu tách việc.

### Ghi trước 04-10 tối: B9 (chưng cất đáp án), B8 bốn nhánh (tách việc), B10 (trạng thái cảnh)

**Bạc A2.** Thầy Opus trả lời prompt THẬT của app qua harness (Ollama giả). So chéo 5 chương trùng: bạc harness MỘT thầy khớp bạc
đồng thuận HAI thầy gold-format của Lead 459/465 = 98,7 % người nói chặt -> một thầy là đủ. Đợt 1: 150 chương (94 Nhật / 56 Hàn,
71 truyện, chương khó nhất mỗi truyện trước; luật PICK_RULES của Lead, mọi truyện đủ điều kiện, tối đa 3 chương/truyện, ngoài bộ đo).
Ghi chú lý do của thầy chỉ để NGƯỜI soát nhãn, KHÔNG vào dữ liệu học. Không xin agent Claude viết quá trình/lập luận để làm dữ liệu
huấn luyện (bộ lọc an toàn API đã chặn một yêu cầu như thế - không lách).

**B9 = 4B học data_v8 + bạc** (cùng công thức lora29v8, hạt 1234 và 1). Mốc họ v8 (thước 04-10): Nhật MỚI TB 58,7, Hàn MỚI 67,6.
THẮNG: TB 2 hạt >= mốc + 2,0 ở Nhật MỚI, không truyện nào tụt > 5, Hàn không tụt > 2. THUA (< mốc - 2): soát bạc trước khi kết luận.
Dấu liều-đáp cho quy mô A2: lỗi lặp lượt giảm >= 15 %.

**B8 bốn nhánh trên cùng data_v8 (gold mới), 2 hạt mỗi nhánh** - câu chủ sách "tách phân vai và cảm xúc có hơn không":
(a) v8 đa nhiệm; (b) chỉ id/kind/speaker; (c) như (b) nhưng người nói là CON TRỎ (cửa sổ 9 đoạn); (d) chỉ cảm xúc/cường độ/nhịp/âm
lượng, người nói gold đưa sẵn trong prompt. Ngưỡng: b-a >= +2,0 F1 giọng (tách có lợi cho phía người nói); c-b >= +3,0 và lỗi lặp
-25 % (con trỏ có lợi); d vs a trên độ đúng cảm xúc cùng chương (phía cảm xúc). Cảm xúc hiện KHÔNG phải nút thắt: họ v8 Nhật MỚI cảm
xúc 91,6-93,5 %, người nói chặt 68,6-72,6 %. Nếu tách thắng, triển khai là MỘT adapter đa nhiệm + thẻ nhiệm vụ ở cuối prompt (dùng
lại KV tiền tố, ước +3-5 % thời gian); hai adapter không chia được KV (LoRA đổi luồng dư từ lớp đầu) -> ước +20-30 % (đo token 306 lô
E1: prefill 2.139, đáp đủ 349, chỉ người nói 125, phần cảm xúc 265).

**B10 - trạng thái cảnh trước quyết định** (GPU sau B9): trò sinh {present, pair, last_speakers, narrator} rồi mới gán người nói;
trạng thái DỰNG BẰNG MÃ từ nhãn (người nói các câu trước, tên có nhãn trong cửa sổ cảnh, first_person), không từ lập luận của thầy.

## 03-10 chiều - Vì sao model to không hơn rõ: tín hiệu khó quá ít, lỗi theo loại, và truyện ĐÃ HỌC vs truyện MỚI

Câu chủ sách hỏi: "ít thông tin thì huấn luyện tốt hơn?". Trả lời từ số đo, không dùng GPU:

**Loss huấn luyện không phân biệt được hạt tốt và hạt hỏng.** `trainer_state.json` bước 258 của 9 lượt (4B v8m, q35-4B, 9B,
mỗi loại 3 hạt; cùng thứ tự dữ liệu `data_seed=3407`): loss cuối q35/9B ~0,007, 4B v8m ~0,019, mọi hạt trong một công thức
trùng nhau tới phần nghìn, và đã xuống ~0,01 từ 1/4 epoch. 9B hạt 1 (F1 kém nhất mọi bộ) có loss y như hai hạt kia.

**Vì phần khó chỉ là 1-2% câu trả lời.** Trong data v8, tên người nói trên câu thoại/nội tâm chiếm 2,0% ký tự câu trả lời mẫu
sinh và 1,3% ở mẫu phản biện; phần còn lại là khung JSON, câu người kể và các trường gần như cố định (tuổi luôn unknown, cách
đọc tên luôn rỗng). Cả bộ có ~2.000 quyết định người nói, từ 10 truyện (một truyện Trung chiếm 1/3; Hàn chỉ YMP 194 + HDST 60
câu); nửa số mẫu (phản biện) chép nguyên ứng viên. Model thuộc phần dễ rất sớm, còn phần khó quá ít mẫu để học ổn định - nên
model to hơn không có thêm gì để học, và kết quả lệ thuộc hạt. Không phải "ít thông tin thì học tốt hơn", mà là **ít tín hiệu
khó**. Hướng data v9: thêm câu khó (đối đáp so le, ngôi thứ nhất), mẫu phản biện sửa sai thật, nhiều truyện hơn (LN Nhật trước).

**Lỗi theo loại** (% câu có người nói, chương chung của ba ứng viên, nhãn đi QUA bước gom tên của app như F1 giọng;
`Corpus/claude/model_lane/error_types.py`):

| | Nhật: đúng | lệch lượt | nhầm "tôi" (2 chiều) | Hàn: đúng | lệch lượt | nhầm "tôi" |
|---|---|---|---|---|---|---|
| 4B v8 | 70,2 | 12,7 | 6,9 | 66,1 | 2,0 | 18,3 |
| q35-4B | 66,5 | 12,8 | 9,2 | 74,6 | 3,5 | 15,5 |
| 9B | 71,0 | 10,5 | 6,3 | 77,4 | 2,4 | 11,3 |
| 9B hạt 1 | 53,3 | 17,7 | 19,6 | 52,4 | 4,1 | 31,3 |

Truyện Nhật hỏng ở **đối đáp so le**: hơn nửa số ca, câu liền trước cũng là thoại và model lặp lại người nói của nó. Truyện Hàn
(phần lớn kể ngôi thứ nhất) hỏng ở **nhầm "tôi"**. Đọc mẫu ngẫu nhiên (agent, seed 0):

- 9B sửa được các ca tín hiệu yếu: người vô danh, thoại gọi tên người nghe (khoảng 0,3 lần số ca của 4B).
- 9B không sửa được việc lặp người nói trước, hay việc bỏ qua lời dẫn nêu đúng tên (khoảng 1,0-1,4 lần).
- Gán nhầm cho người kể: 9B chỉ còn khoảng 0,5 lần số ca của 4B.
- Ca gán nhầm thường nằm trong đoạn kể ngôi ba chen giữa truyện ngôi một, chứ không phải do chữ "tôi" trong lời người khác.
- 9B hạt 1 là một chế độ hỏng riêng: dồn câu về người kể theo cả chuỗi, tỉ lệ 22:1 so với khoảng 1,5:1 ở các lượt khác.

**So khớp mờ tên: KHÔNG đáng sửa file khoá.** Bản đầu của mục này (cùng ngày) cho rằng 45/98 lỗi "lẽ ra là tôi" của 9B ở
Nageki là tên người kể viết khác ("Krai Andrej") và app không gộp - SAI: script lỗi khi ấy so nhãn thô, còn
`canonical_speaker_names` (lượt đánh vần theo nguồn) đã gộp "Krai Andrej"/"Krai Andrei" về KRAI ANDREY. Mô phỏng offline đúng
cách chấm (`fuzzy_sim.py`, ngưỡng ghi trước: cùng số từ, thứ tự xuôi/ngược, nhiều nhất một từ khác đúng 1 ký tự và dài >= 5)
trên mọi chương đã đo của 10 nhãn: luật neo tên người kể gộp 0 lần; luật neo tên đã biết gộp 3 lần, đều là đảo thứ tự họ tên
(Yamiyo 225), 0 gộp sai, F1 Yamiyo +0,3..+1,7, mọi truyện khác không đổi. Lỗi tên còn lại thật sự là BIỆT DANH (Nageki: biệt
hiệu của người kể thành một giọng riêng) - so khớp chữ không bắt được.

**Bảng phải tách truyện ĐÃ HỌC và truyện MỚI.** Bộ đo cũ (TCF, Nise, Yamiyo, Nageki, Love Unseen, HDST, YMP) là chương khác của
chính các truyện có trong dữ liệu học; người dùng app thì gặp truyện mới. Nháp hiện tại (F1 giọng, 4B v8 / q35-4B / 9B): Nhật đã học
64,8 / 63,4 / 64,4, Nhật MỚI (3 ch) 69,6 / 61,6 / 66,1; Hàn đã học 68,4 / 71,3 / 73,4, Hàn MỚI (2 ch) 63,6 / 58,7 / 76,5 - mẫu
truyện mới còn quá nhỏ; các lô đang chạy đưa lên ~27 chương Nhật và ~12 chương Hàn mới (Hàn đợt 4: 4 bộ chưa từng dùng).

## 03-10 - Hai nghi vấn về cách chạy model, đều loại: presence_penalty của Qwen3.5 và bước reconcile sau phân tích

**presence_penalty.** Modelfile của q35-4B và 9B (tạo bằng `ollama create --like` từ qwen3.5 gốc) mang theo tham số mẫu của
bản gốc: `presence_penalty 1.5`, `temperature 1`, `top_k 20`, `top_p 0.95`. Lúc huấn luyện không có các tham số này; 4B v8
(nền Qwen3) không có. Phạt lặp 1,5 có thể đẩy model tránh lặp lại đúng tên người nói vừa dùng, nên đo lại bằng tag `-nopp`
(cùng GGUF, bỏ hết PARAMETER), hạt 3407, ở nhà, trên đúng 7 chương của bảng hạt giống. F1 giọng:

| | LN Nhật (5 ch, 463 câu) | Hàn (hdst062 + ymp248, 108 câu) | cả 7 |
|---|---|---|---|
| q35-4B có penalty, 3 hạt | 58,2 - 60,8 | 77,9 - 80,9 | 62,5 - 64,0 |
| q35-4B **không** penalty (3407) | 57,2 | 76,6 | 60,8 |
| 9B có penalty, 3 hạt | 53,7 - 63,2 | 62,3 - 81,9 | 55,4 - 66,7 |
| 9B **không** penalty (3407) | 62,3 | 75,7 | 64,8 |

Cùng hạt 3407: q35 62,5 -> 60,8, 9B 66,7 -> 64,8. Cả hai **hơi kém đi** và đều nằm trong dải hạt giống, nên không có lý do
đổi Modelfile của app; hàng đo giữ tag cũ. Lưu ý: tag 9B-v8 (3407) trên Mac được tạo thẳng từ GGUF nên **không có**
PARAMETER - mọi số 9B-v8 đo ở Mac (hiệu chuẩn 77,9 trên 4 chương Hàn mới, Hàn đợt 3 Mẹ kế/Demon King) là bản không
penalty; các tag q35/9B khác ở mọi máy đều có penalty 1,5. Với độ lệch đo được ở trên, chênh này nhỏ hơn nhiễu hạt giống.

**reconcile_local_speaker_identities / reconcile_name_pronunciations** chạy sau phân tích, gộp tên vai địa phương
(`NPC_LOCAL::...`) thành nhân vật có tên. Không cần đo lại bằng GPU: mỗi lô phân tích được lưu nguyên trong
`analysis_candidates.commit_envelope_json` TRƯỚC khi reconcile chạy, nên dựng lại được người nói trước reconcile cho mọi lượt đo
đã có (phủ đủ mọi đoạn) và chấm y thước cũ. F1 giọng gộp, sau -> trước reconcile: 4B v8 62,8 -> 62,9; q35-4B 61,7 -> 61,5;
9B 66,0 -> 65,9; q35 hạt 1/2 62,9 -> 62,7 / 64,0 -> 63,7; 9B hạt 1/2 không đổi; v8m 3 hạt 59,4 -> 58,8 / 64,9 -> 65,5 /
62,5 -> 62,4; 8B-v5 63,6 -> 63,4. Từng chương lệch tới ~8 điểm theo cả hai chiều. Reconcile gần như trung tính (±0,6) và
9B không có gì để reconcile vì nó gọi tên thẳng. Bộ chấm: `Corpus/claude/model_lane/prereconcile_table.py`.

Mức lượng tử của bốn model đang so (ghi kèm mọi bảng): 4B v8 Q8_0, q35-4B Q8_0, 9B Q4_K_M, 8B-v5 Q4_K_M (tràn sang CPU
trên card 8 GB). Phép so Q4_K_M / Q8_0 của 9B trên cùng Mac đang chạy.

## 02-10 chiều - Bộ LN Nhật thứ hai: thêm 767 câu có người nói để tách q35-4B / 9B / v8

Mục đích: LN Nhật dịch Việt là nhóm trọng số cao nhất của chủ sách, và trên 10 chương LN Nhật cũ bốn model HOÀ (hiệu với
v8 đều trong nhiễu) - phép so cần thêm câu để quyết model mặc định. Gold mới (bộ KIỂM TRA, không vào dữ liệu học): Make
Heroine ga Oosugiru 009, 023, 017a; Rokujouma no Shinryakusha 014, 015, 122a, 284a; Shimotsuki wa Mob ga Suki 029, 032,
195, 456 - 1.475 đoạn, 767 câu có người nói. Chọn bằng LUẬT CỐ ĐỊNH, không nhìn nội dung: file ở vị trí 30% và 70% của bộ
(bỏ file < 3 KB) + các chương phiên nhạc đã chép; chương > 30 KB chỉ lấy các đoạn đầu tới 25 KB (`<số>a.txt` trong Corpus).
A = agent Opus một truyện một người, B = agent soát đối kháng, Claude phân xử (ADJUDICATION.md): B bắt 2 câu sai người nói
(Make Heroine 017a:100-101), Rokujouma và Shimotsuki 0. Người kể cấp cuốn như Studio (Nukumizu, Nakayama; Rokujouma ngôi
ba). Đo 11 model (ba ứng viên, 4 hạt giống q35/9B, 3 hạt v8, 8B-v5) xếp sau hạt giống - kết quả ghi ở đây khi xong.

Dải hạt giống v8 trên hai cổng quyết định (4 lượt: nhà + Modal 3407/1/2), F1 giọng: TMA 65,4-72,1, YMP 72,5-83,7. q35-4B
v8 79,5 / 86,7 và 9B-v8 77,8 / 92,2 đều trên trần dải ở cả hai cổng; YMP chỉ một chương nên dải rộng - q35 hơn trần 3 điểm
là chưa chắc. Hai hạt mới mỗi ứng viên (Modal 02-10, trình có `--seed`) đang đo.

## 02-10 - So bốn model trên đủ bộ đo: q35-4B v8 giữ phần lớn mức hơn của 9B ở cổng Hàn/Trung, nhanh như 4B

Bốn model, cùng thước (cây mặc định `D:/Novels/ABook`, `gold_person`), đo ở nhà: 4B v8 (`train_lora.py`), Qwen3.5-4B công
thức v8 (Modal, unsloth), 8B-v5 (Kaggle), 9B-v8 (Modal). Theo trọng số chủ sách (02-10: LN Nhật dịch Việt > Hàn > Trung;
văn Việt gốc chỉ tham khảo). F1 giọng, thứ tự v8 / q35-4B v8 / 8B-v5 / 9B-v8:

| nhóm | bộ | v8 | q35-4B v8 | 8B-v5 | 9B-v8 |
|---|---|---|---|---|---|
| Nhật | LN+LNX 10 chương (866 câu) | 64,8 | 63,4 | 63,3 | 64,4 |
| Hàn | cổng YMP 248 (ngôi 1) | 77,0 | 86,7 | 84,6 | 92,2 |
| Hàn | HDST 062+130 (148 câu) | 64,3 | 65,0 | 58,1 | 66,3 |
| Trung | cổng TMA (4 chương) | 72,1 | 79,5 | 70,7 | 77,8 |
| Trung | cổng Tam quốc | 83,0 | 88,3 | (đã học) | 91,9 |
| tham khảo | Tắt đèn | 76,3 | 75,4 | (đã học) | 77,7 |
| | thời gian LN6 | 1,00x | 1,06x | 1,11x | 1,28x |

Nhật: hiệu với v8 đều trong nhiễu (q35 -1,4 [-5,2; +2,9], 8B -1,5, 9B -0,4). Gộp LN+LNX 12 chương: 64,7 / 63,6 / 62,6 /
64,7, người nói chặt 66,7 / 67,3 / 66,7 / 64,0. Mức hơn ở YMP (+10..+15) và TMA (+6..+7) lớn hơn mọi dao động đã thấy,
nhưng mỗi model mới MỘT lượt huấn luyện; Tam quốc của q35 (88,3) chạm mép dải hạt giống v8 (84,3-88,2). TMA của 9B-v8
ghép hai lượt (351/381 lượt đầu + 363/378 đo lại sau khi bộ giữ êm làm quá giờ; gốc `02-10-9bv8-tmamerged`).

8B dữ liệu sạch BỎ (11-12 giờ GPU không trả lời câu hỏi nào còn mở: 8B thua q35 mọi nơi mà chậm hơn). Việc kế: dải hạt
giống v8 trên YMP + TMA (ba lượt v8m Modal, đo ở nhà); hạt giống cho q35-4B và 9B cần Modal (Kaggle T4 không chạy được
Qwen3.5: không bf16, float32 không vừa 16 GB; tín dụng Modal tháng 10 đã hết). Đổi model mặc định = chủ sách quyết sau khi
có hạt giống.

## 01-10 16:3x - Qwen3.5-9B Q4 VỪA card 8 GB và nhanh gấp đôi 8B

`vram_probe.py` ở ngữ cảnh 16384, máy đang bận 2,2 GB VRAM (app khác): 8B-v5 Q4 (Qwen3) cần 7,09 GiB, chỉ 83% nằm trên GPU
(tràn CPU), đề 535 tok/s, sinh 22,5 tok/s, 27 s một lô; Qwen3.5-9B LoRA28 Q4 cần **5,35 GiB, 100% trên GPU**, đề 1885
tok/s, sinh **47,2 tok/s**, 14 s một lô. Kiến trúc lai của Qwen3.5 (3/4 lớp chú ý tuyến tính) làm KV cache rất nhỏ. Câu
"9B không nạp nổi card 8 GB" (28-09) đã lỗi thời: 9B là ứng viên thật cho máy nhà, và nhanh hơn ứng viên 8B. Việc: lượt
Qwen3.5-9B trên CÔNG THỨC v8 đã giao Modal (`LLM_Train/modal/launch_9b_v8_01_10.sh`, data_v8, ~4 USD), tự xuất GGUF q4_k_m
và nạp Ollama `qwen35-9b-lora-v8-q4`; đo LN 12 + 4 cổng từ ABook_ui khi hàng GPU rảnh.

## 01-10 tối - v9: dạy đúng chỗ v8 thua Tam quốc bằng DỮ LIỆU (Đông Chu liệt quốc)

Lỗi v8 ở cổng Tam quốc là ghép lời dẫn của câu SAU ("Vân-trường đáp:") vào câu hiện tại khi lời dẫn đứng TRƯỚC câu thoại.
Đếm trong data_v8 (`colon_tag_share.py`): lời dẫn "X nói/hỏi/đáp…:" đứng trước ở 130/1.939 câu thoại (6,7%), nhưng cấu hình
BẪY - previous_text là lời dẫn của chính câu, next_text là lời dẫn của câu kế - chỉ **7 câu**; Tam quốc thì gần như mọi
lượt đối đáp đều thế. v9b (prompt) đã chứng minh không phải thiếu chữ láng giềng; vậy là thiếu MẪU. Gold mới (chương
HUẤN LUYỆN, không phải cổng): Đông Chu liệt quốc Hồi 2 (273 đoạn) và Hồi 4 (184 đoạn), bản dịch Nguyễn Đỗ Mục (mất 1948, hết
bản quyền, vi.wikisource) - cùng lối "X nói :" rồi gạch đầu dòng, có cả bẫy thật ("Trang-công làm thinh, không nói :" rồi
câu của mẹ). A: Claude; B: agent soát đối kháng - không câu nào sai người, phân xử dạng tên/cảm xúc (`ADJUDICATION.md`). Dạng
tên đầu tiên CỐ ĐỊNH cho mỗi người cả chương (dạng đầu là nhãn dạy; đổi theo lời dẫn là dạy tách giọng). Phát lại từ
ABook_ui (prompt v8): 100%. data_v9 = data_v8 + 184 mẫu (92 sinh + 92 phản biện). Nhánh dev/prev-speakers-main 26dec3dc.

Đo: hàng GPU nhà kín tới mai, nên huấn luyện CẢ HAI trên Modal bằng cùng trình (`train_lora_unsloth.py`, Qwen3-4B-
Instruct-2507 4-bit, r16, 1 epoch): v8m (data_v8, đối chứng) và v9m (data_v9) - khác nhau DUY NHẤT ở 184 mẫu Đông Chu; đo
LN 6 + Tam quốc trên Modal, host 26dec3dc (`LLM_Train/modal/launch_v9_01_10.sh`, `v9_chain_01_10.sh`). Luật nhận như v7/v8:
không thua v8m quá 2 điểm ở LN, và Tam quốc phải về gần v6 (87,5).

LN 6 (01-10 22:1x): v9m 63,7 vs v8m 58,2 = **+5,5 [+1,6; +10,2]**, hơn 5/6 chương; chặt −2,1 [−23,0; +8,3]; NHẬP người
lạ 86% vs 50% (22 câu, lu 8/11 vs 0/11). NHƯNG đối chứng v8m (data_v8, trình unsloth trên Modal) thấp hơn v8 nhà (cùng
data_v8, `train_lora.py`) −6,0 [−8,2; −2,8], thua 6/6 - khác trình/lượt huấn luyện đã to ngang hiệu của 184 mẫu, và v9m
chỉ ngang v8 nhà (63,7 vs 64,2). KTC bootstrap theo chương KHÔNG gồm nhiễu giữa hai lượt huấn luyện. Chưa nhận: chờ Tam
quốc; nếu v9m hồi ở Tam quốc thì huấn luyện v9 ở NHÀ bằng đúng trình của v8 nhà rồi so thẳng với v8 nhà.

Tam quốc (01-10 22:2x): v8m 87,8 / v9m 87,2 (chặt 86,8 / 88,1) - KHÔNG khác, cả hai ngang v6 (87,5). Mà v8 NHÀ chỉ 83,0:
"v8 thua Tam quốc 4,5" là của LƯỢT huấn luyện ở nhà, không phải của data_v8. **Kết luận: v9 không nhận** (Tam quốc không
có gì để sửa, LN +5,5 nằm trong nhiễu giữa hai lượt). **Bài học lớn hơn: hai lượt cùng dữ liệu lệch ~6 F1 LN và ~5 Tam
quốc** - mọi so sánh model trước đây hơn kém dưới mức ấy (v7, v6b, 9B-v8 ±0) là CHƯA phân định; muốn tách hiệu của dữ liệu
phải huấn luyện >= 2-3 hạt giống mỗi bên rồi so trung bình. Việc kế: 3 hạt giống v8 cùng trình (Modal, rẻ) đo LN6 + Tam
quốc để biết độ rộng nhiễu thật trước khi đổi model mặc định.

8B dữ liệu SẠCH (Modal 01-10, đo trên Mac cùng host với 8B-v5 lượt A, 5 chương chung): v6n-e1 F1 giọng 56,6 vs 8B-v5 63,8
(−8,0 [−12,7; −3,0], thua 5/5 chương), chặt −20,8; nhưng NHẬP người lạ vào nhân vật có tên 0% (v5 39%) - mọi câu vô danh
đọc bằng giọng người lạ. Dữ liệu "bẩn" của v5 (nhãn chữ hoa, có chương cổng) vẫn cho F1 cao hơn; chờ v6-e1 / v6n-e2 trước
khi kết luận về 8B.

**ĐỘ NHIỄU GIỮA HAI LƯỢT HUẤN LUYỆN (02-10 01:2x)** - cùng data_v8, cùng trình unsloth trên Modal, chỉ khác hạt giống (training_args.bin: seed 3407/1/2 nhưng data_seed 3407 cả ba - CÙNG thứ tự mẫu, dải này chỉ gồm khởi tạo + ngẫu nhiên khi học; bản trình có --seed đã mất, trình hiện tại ghi cứng 3407):
LN6 F1 giọng 58,2 / 63,9 / 60,5 (hạt 3407 / 1 / 2; trung bình 60,9, lệch ~2,9), riêng chương TCF 40,5 / **83,1** / 42,7 - một
chương ngôi thứ nhất lật theo hạt giống; Tam quốc 87,8 / 84,3 / 88,2. v9m (63,7; 87,2) nằm trong dải -> v9 không phân biệt
được, đúng như đã không nhận. Luật từ nay: so hai công thức bằng >= 3 hạt giống mỗi bên (Modal ~2,5 USD/lượt), báo trung
bình +- lệch; một lượt đơn chỉ đủ để loại thứ thua xa. 9B-v8: Tam quốc 91,9 chỉ hơn dải v8 (84-88) 4-8 điểm - dè dặt; YMP +15
lớn hơn mọi dao động đã thấy, nhưng chưa đo hạt giống trên cổng YMP.

**Tốc độ THẬT theo chương (02-10 02:xx, log hàng GPU, 13 chương LN chung, cùng máy nhà):** 9B-v8 Q4 chậm hơn v8 4B Q8
trung vị **1,32 lần** (TCF 042: 412 / 313 giây; Nageki 65: 1379 / 1103), gần ngang 8B-v5 Q4 (356 / 1196). Con số 47 vs 22 tok/s
ở trên chỉ là tốc độ SINH trong phép thử riêng; cả chương thì đọc prompt dài chiếm phần lớn. 9B nằm trọn VRAM, 8B tràn.
Nên cái giá của 9B là ~30% thời gian phân tích - cân với +4..+15 ở hai cổng khó. Qwen3.5-4B công thức v8 (chưa huấn luyện được
ở nhà - Windows thiếu kernel lớp gated delta) là phép thử còn thiếu: nếu giữ phần lớn mức hơn của 9B mà nhanh như 4B thì hơn.

**9B-v8 ĐỦ CỔNG (02-10 01:0x)** - LN 12 chương: 64,7 = v8 4B (-0,1 [-3,4; +3,7], hơn 6 thua 6); cổng: Tam quốc F1 giọng
**91,9 vs 83,0** (chặt 89,0 vs 82,2; v8m Modal 87,8 - vẫn hơn), YMP ngôi thứ nhất **92,2 vs 77,0** (chặt 92,0 vs 86,0),
Tắt đèn 77,7 vs 76,3 (chặt 92,0 vs 84,8); cổng 351/381 OK, 363/378 hỏng vì QUÁ GIỜ do bộ giữ êm (lỗi đo - đo lại bằng
scratchpad/redo_9bv8_gates.sh). Chạy được trên card 8 GB (Q4, 16k ngữ cảnh, 5,35 GiB, 47 tok/s - nhanh hơn 8B). Hơn hẳn ở
hai cổng khó nhất (cảnh nhiều người kiểu Tam quốc, kể ngôi thứ nhất) vượt cỡ nhiễu giữa hai lượt huấn luyện (~5-6) ->
**ỨNG VIÊN đổi model mặc định** (đổi = file khoá config.py + đăng model: chủ sách quyết). Trước khi đổi: đo lại 363/378,
và một lượt 9B-v8 hạt giống khác nếu tín dụng cho phép.

9B-v8 (Qwen3.5-9B công thức v8, đo ở nhà, 6 chương LN cơ sở): F1 giọng 64,2 = v8 4B (+0,0 [−3,5; +4,6]), chặt −6,0
[−16,0; +3,9]; chênh lớn theo chương (Nise 79,0 vs 62,8; TCF 25,8 vs 40,7). Chưa đủ để nói 9B hơn; chờ LN mở rộng + cổng.

## 01-10 chiều - v8 (mỗi lô thấy người nói 4 lượt trước): LoRA 4B tốt nhất trên LN, giữ lượt đối đáp, thua cổng Tam quốc

v8 = công thức v7 trên data_v8 (= data_v7 phát lại bằng prompt của nhánh dev/prev-speakers: mỗi lô nêu người nói ĐÃ gán của
4 đoạn ngay trước - cả lúc học lẫn lúc đo, đo từ worktree ABook_ui). v8 và v7 khác nhau DUY NHẤT ở phần prompt ấy.

| lượt | LN 12 chương F1 giọng | người nói chặt | cảm xúc | nhập người lạ vào nhân vật có tên |
|---|---|---|---|---|
| v6 | 59,8% | 61,4% | 90,4% | 32% (21/65) |
| v7 | 61,7% | 63,2% | 89,7% | 34% (22/65) |
| v8 | **64,7%** | **66,7%** | 90,5% | 29% (19/65) |

v8 − v7: F1 +3,0 [−1,3; +6,3], chặt +3,5 [−5,7; +11,4], hơn 7/12 chương. v8 − v6: **F1 +4,9 [+0,6; +8,5]** - lần đầu một
LoRA 4B hơn v6 vượt nhiễu. Theo loại câu (chặt, v7 → v8): đối đáp liền 66,1 → **78,8** (đúng điều v8 nhắm - nối lượt qua
ranh giới lô), 『』 14,6 → 38,2, tôi nói 74,0 → 77,5, còn lại 60,0 → 66,4; nhưng **có lời dẫn 82,4 → 70,4**. Soi 36 câu có lời
dẫn v8 sai mà v7 đúng (`v8_cue_errors.py`): chỉ 4 câu v8 chép người nói của lượt trước; **24 câu ở một chương HDST (062)**
v8 viết "Professor Glast" thay "Glast" - thêm chức danh, lệch nhãn chặt nhưng vẫn một giọng (F1 giọng không mất). Tức phần
tụt chủ yếu là CÁCH VIẾT TÊN, không phải đọc sai lời dẫn. Gốc của nó: sách viết **"giáo sư Glast"** (29 lần), v8 **dịch chức
danh sang tiếng Anh** khi gán nhãn ("Professor Glast", 34 câu); v6/v7 viết "Glast". Trong app điều ấy có hại thật: luật gộp
chức danh của host (`character_registry.HONORIFIC_PREFIX_PATTERN`) chỉ biết chức danh tiếng Việt, nên "Professor Glast"
không gộp với "Glast" ở chương khác -> có thể thành hai giọng. Sửa (file khoá, sự kiện phiên bản): thêm chức danh tiếng Anh
(Professor, Lady, Lord, Sir, Master, Miss, Mr, Mrs, Dr, Captain, Prince, Princess, King, Queen, Duke, Count…) vào luật ấy.

Cổng (F1 giọng, v6 / v7 / v8): TMA 64,3 / 65,4 / **72,1**; YMP 76,4 / 67,0 / **77,0**; Tắt đèn 72,8 / 72,9 / **76,3**; Tam
quốc **87,5** / 83,8 / 83,0 (v8 tách 13/32 người thành nhiều giọng, v6 10/32).

**Quyết định (cùng luật đặt trước như v7: không thua v6 quá 2 điểm ở cổng nào):** v8 thua Tam quốc 4,5 -> CHƯA nhận làm
công thức; nhưng giữ hướng "thấy người nói lượt trước" (lợi rõ nhất từ trước tới nay ở LN và 3/4 cổng).

Soi Tam quốc (`tamquoc_v8.py`, nhãn sau lượt gom tên của dây chuyền): KHÔNG phải tách tên - v8 sai người 40/219 câu, v6
35. Các câu v8 sai thêm đều là gán cho NGƯỜI VỪA NÓI GẦN ĐÂY trong cảnh nhiều người (hội nghị, trận mạc): Trình Phổ -> Chu
Du / Tào Nhân, Lã Mông -> Chu Du, Lỗ Túc -> Chu Du, Triệu Phạm -> Pháo Long, câu vô danh -> Khổng Minh (3). Tức nêu người nói
lượt trước giúp đối đáp HAI người luân phiên (LN: đối đáp liền +12,7) nhưng kéo lệch về người hay nói ở cảnh NHIỀU người.

Việc kế: (1) v9 nhắm đúng chỗ ấy - chỉ nêu người nói lượt trước khi các lượt gần đây luân phiên giữa hai người, hay nêu
kèm lời nhắc "lời dẫn nêu tên luôn thắng lượt trước"; đo lại trên LN + Tam quốc. **Đã thử rẻ 01-10 17:5x (model v8, host
nhánh dev/prev-speakers-v9 193e1d08: bỏ khối khi 4 đoạn trước có >2 người nói): Tam quốc y hệt v8 (F1 83,0, 0/197 câu khác
nhãn) - vì điều kiện KHÔNG LẦN NÀO xảy ra: trong 105 lô, 4 đoạn trước lô chỉ có 1 người (40 lô) hoặc 2 người (65 lô), thoại
xen lời kể và lô chỉ 5 đoạn. Vậy v8 gán nhầm cho người vừa nói ngay trong cửa sổ 1-2 người; "cảnh đông người" là mô tả
đúng cảnh nhưng sai CƠ CHẾ. Bỏ ý này (không gộp nhánh); hướng kế phải nhắm câu có lời dẫn nêu tên NGƯỜI KHÁC người vừa
nói (dữ liệu, hay lời nhắc trong khối).** **Soi tận câu (`tamquoc_v8_cases.py`): Tam quốc đặt lời dẫn TRƯỚC câu thoại
("Khổng Minh hỏi:" rồi "- Thế có bắt được…"); 6/8 câu v8 sai mà v6 đúng bị gán cho tên trong lời dẫn của câu SAU ("Vân-trường
đáp:", "Du nói:") - v8 ghép lệch lời dẫn sang câu kề, không phải "người vừa nói". Thử luật xác định "câu kể ngay trước kết
thúc bằng '… X nói/hỏi/đáp:' -> X" (`colon_tag_rule2.py`, tên đầu tiên trong mệnh đề cuối, có tên gọi tắt): trên đúng những
câu luật áp được, luật KHÔNG hơn model - Tam quốc 93% (v6 96%, v8 92%), Tắt đèn 74% (76%, 76%), TMA 92% (92%, 85%); luật
hỏng ở bí danh ("Huyền-đức hỏi Khổng Minh:" là Lưu Bị) và tên trùng chữ ("Anh Dậu" / "Chị Dậu"). Không làm luật ghi đè; sửa
v8 phải ở dữ liệu / prompt (vd ví dụ lời dẫn đứng trước trong khối lượt trước).** **v9b (01-10 18:0x, nhánh
dev/prev-speakers-v9 6c2b82ed: câu đầu / cuối lô thấy câu láng giềng THẬT bên kia ranh giới lô) - đo trên Modal cùng model
v8, 4 chương LN (tcf, nise, hdst, yamiyo): trùng v8 TỪNG CÂU (người nói, loại, cảm xúc) ở cả 511 câu - lại một nhánh không
làm gì. Lý do: giả thuyết sai từ gốc. Đường chạy thật (`analyze_all`) dựng `_original_neighbor_context` cho MỌI câu từ cả
chương trước khi chia lô, và `_neighbor_texts` dùng nó trước - câu đầu lô vốn đã thấy câu kể ngay trước nó (cả "Khổng Minh
hỏi:"). Phần "4/8 câu sai ở vị trí 0 của lô" là thật nhưng không do thiếu chữ láng giềng. Bỏ nhánh (không gộp); dừng hai
lượt Modal giữa chừng (app abook-eval stop, khi cần thì deploy lại). Bài học, lần thứ hai trong ngày: TRƯỚC khi thuê GPU đo
một thay đổi host, chạy một lô thật qua cả hai mã và so PROMPT gửi đi - giống nhau thì không cần đo.** (2) Qwen3.5-4B trên đúng công thức v8 (`q35v8_after_8bclean.sh`, sau hàng
8B sạch) - lượt Qwen3.5 đầu tiên ở nhà (01-10 16:06) hỏng ngay bước 1: cuDNN không nhận đầu chú ý 256 của Qwen3.5 và
train_lora.py cấm mọi kernel khác; nay mở thêm kernel memory-efficient khi đầu > 128 (vẫn cấm math), kèm chốt tốc độ (quá
14 giờ một epoch thì lên đám mây - Windows thiếu kernel nhanh cho lớp gated delta của Qwen3.5). v8 cần mã host của nhánh
dev/prev-speakers (prompt) - đưa vào app là sự kiện phiên bản.

## 30-09 chiều - v7 (nhãn người lạ có mô tả): LN nhích lên, việc nhập người lạ KHÔNG giảm, thua hai cổng

v7 = công thức v6 (4B, 1 epoch) trên data_v7 = data_v6 với 174 câu "người lạ" đổi thành 50 nhãn mô tả ("trưởng thôn",
"nữ hầu cận của Marla"). Cùng host với v6 và 8B-v5 (29-09), LN 12 chương, 1014 câu:

| | F1 giọng | người nói chặt | cảm xúc | nhập người lạ vào nhân vật có tên |
|---|---|---|---|---|
| v6 | 59,8% | 61,4% | 90,4% | 32% (21/65) |
| v7 | 61,7% | 63,2% | 89,7% | 34% (22/65) |
| 8B-v5 | 62,6% | 66,7% | 90,0% | 55% (36/65) |

v7 − v6: F1 +1,9 [−0,0; +4,0], chặt +1,8 [−0,3; +3,9], cảm xúc −0,7 [−1,6; +0,1], hơn 10/12 chương. Nhưng điều v7 nhắm
tới không đổi: nhập người lạ 34% so với 32% (Nise 11/11, LU 6/11 vẫn nhập; Nageki 62 0/25 như v6). Với 4B, nhãn mô tả
trong dữ liệu không dạy được việc giữ người lạ riêng - chỗ nhập là chỗ model không nhận ra có một người mới, không phải
chỗ nó thiếu cách gọi tên người ấy.

Mức +1,9 tới từ đâu (`error_map.py`, câu sai theo loại chính, v6 → v7 → 8B-v5): có lời dẫn 40 → **30** → 39, đối đáp
liền 60 → 53 → 52, còn lại 100 → 94 → 87, "tôi nói" 60 → 59 → 47, vô danh 60 → 61 → 57, 『』 71 → 76 → 56 (cộng 391 →
373 → 338). v7 đọc lời dẫn tốt hơn cả 8B - có lẽ nhờ học nhãn mô tả ("bà lão nói" -> người tên "bà lão") - nhưng mất ở
『』 của TCF (28 → 33).

Cổng (F1 giọng / người nói chặt, v6 → v7): TMA 156 câu 64,3 → 65,4 / 73,1 → 71,2; YMP 248 50 câu 76,4 → 67,0 / 86,0 →
80,0; Tam quốc 219 câu 87,5 → 83,8 / 84,5 → 80,8; Tắt đèn 112 câu 72,8 → 72,9 / 80,4 → 80,4. Thua quá 2 điểm ở hai cổng.

**Quyết định (luật đặt trước khi có số cổng: dùng data_v7 chỉ khi không thua v6 quá 2 điểm ở cổng nào):** lượt 8B dữ liệu
sạch trên Modal 01-10 dùng **data_v6** (`data_base.txt` không ghi gì). Cũng là phép so sạch hơn: 8B và 4B học cùng một bộ
dữ liệu, khác nhau chỉ cỡ model. v7 không thay v6; mức +1,9 trên LN nằm sát nhiễu và không tới từ cơ chế đã nhắm.

**Thẻ "hai người chung một tên" trên 5 chương liền nhau (Mac, 8B-v5, Nageki 60-64, 1.024 câu, từng chương một dự án):
0 thẻ.** Không phải thẻ sai mà là không có gì để so: ở 60, 61, 63, 64 Lucia chỉ nói 3 câu (2 từ xưng hô), còn ở 62 cả 24
câu mang nhãn LUCIA gần như toàn là lời bà thầy bói ("cậu" 38, "ta" 10) - một nhóm xưng hô duy nhất, không có nhóm thứ
hai, không có hồ sơ ở chương khác. Thẻ chỉ bắt được việc nhập khi nhân vật bị nhập CÓ nói ở nơi khác trong cuốn. Kiểm tiếp
trên Mac: thêm ba chương Lucia nói nhiều (49, 48, 79) rồi ghép với 62.

**Thêm chương 49 (Lucia nói 25 câu "anh/em"; 6 chương, 2.080 câu) - 30-09 20:4x, chưa có 48 và 79:**

- Thẻ đang có trong app (hai nhóm xưng hô trong MỘT chương): 1 thẻ, và SAI - Sitri ở chương 49, "tôi… ngài" khi đàm phán
  với người ngoài và "em… anh" với Krai; cả hai nhóm đều là lời Sitri. Đúng hạn chế đã biết (xưng hô đổi theo người nghe),
  lần đầu gặp trong chương kể ngôi thứ nhất: độ đúng trên LN từ 15/15 thành 15/16.
- Biến thể chưa vào app (MỘT nhóm lệch khỏi hồ sơ của nhãn ở các chương khác): 3 lần hỏi. Chương 62: 13 câu nhãn LUCIA
  ("ta… cậu") - đáp án: cả 13 là bà thầy bói, BẮT ĐÚNG. Chương 49: 25 câu của chính Lucia bị hỏi, vì "các chương khác" của
  49 chỉ có hồ sơ bẩn của 62 - hai chương thì không biết chương nào lệch. Sitri chương 49 (4 câu): sai như trên.
- Hệ quả thiết kế: biến thể một nhóm chỉ nên hỏi khi hồ sơ ở các chương khác đến từ ít nhất hai chương và các chương ấy
  khớp nhau (đa số quyết chương nào lệch). Đo lại khi 48 và 79 xong: mong 62 bị hỏi, 49 thì không.

**Đủ 8 chương (48, 49, 60-64, 79; 4.156 câu; 79 dừng ở hạn 4 giờ nhưng đã phân tích 1.442 câu) - 01-10 sáng:** đúng như
mong đợi, biến thể một nhóm vẫn hỏi 13 câu bà thầy bói ở 62 (đúng cả 13) và KHÔNG còn hỏi Lucia ở 49 - hồ sơ của Lucia giờ
là đa số lời thật ("anh" 62, "em" 58 qua 48/49/79). Nhưng nó hỏi thêm 4 nhóm nhỏ 3-5 câu (Lucia 48, Sitri 48/49, Liz 49),
không có đáp án, ít nhất Sitri 49 là sai. Thẻ đang có trong app hỏi 3 lần, ít nhất 2 SAI: Sitri 49 (đàm phán "tôi… ngài"
/ với Krai "em… anh") và Franz 79 ("tôi… cậu" / "chúng ta"); Luke 49 không có đáp án. **Kết luận: xưng hô bắt được ca nhập
lớn nhất của 8B khi nhân vật bị nhập có hồ sơ, nhưng trên một cuốn thật nó ồn - một người đổi xưng hô theo người nghe (đàm
phán, nổi nóng) trông như hai người.** Chưa đưa biến thể vào app; thẻ hiện có giữ nguyên (sai chỉ tốn một lần bấm "là một
người"). Nếu làm tiếp: chấm từng nhóm theo người nghe (câu liền trước là của ai) thay vì gộp cả chương.

## 30-09 sáng - lời dặn "cân bằng người kể" không giúp; phép kiểm thẻ tách giọng trên Mac quá chậm

**Lời dặn thêm về người kể: kết quả âm, đóng thí nghiệm.** Vòng 2 (Mac, 8B-v5, 4 chương ngôi thứ nhất của LN mở rộng, 315
câu, cùng mã e09c6c3): nhánh B (prompt có đoạn dặn "lời nói VỚI người kể là của người kia") so với A:

| | F1 giọng | người nói chặt | gán nhầm CHO người kể | bỏ sót người kể |
|---|---|---|---|---|
| A (prompt hiện tại) | 65,7% | 69,5% | 33 | 16 |
| B (thêm lời dặn) | 64,3% | 67,6% | 36 | 18 |

B − A: F1 −1,4 [−4,0; +0,8], chặt −1,9 [−4,9; +1,1], B thua 3/4 chương. Vòng 1 (một chương Nageki 65) từng +2,8. Model
LoRA gần như bỏ qua lời dặn thêm, nên thiên vị người kể phải sửa bằng dữ liệu (v8: người nói các lượt trước) chứ không bằng
chữ trong prompt. Nhánh `dev/narrator-balance` KHÔNG gộp.

**Lỗi dồn vào đâu (8B-v5, bộ LN 12 chương, người nói chặt, mỗi câu một loại chính):** sai 338/1014.

| loại | sai | ghi chú |
|---|---|---|
| 『』 | 56/89 (63%) | Yamiyo 43/43 - quy ước riêng từng cuốn, app đã có thẻ "quy ước 『』 cả cuốn" |
| người vô danh | 57/65 (88%) | LU 20/21, Nageki 22/25, Nise 15/19 - v7 nhắm |
| còn lại | 87/235 (37%) | ô lớn nhất: không lời dẫn tên, không chuỗi đối đáp, không phải người kể |
| đối đáp liền | 52/204 (25%) | v8 nhắm |
| người kể "tôi" nói | 47/227 (21%) | |
| có lời dẫn | 39/194 (20%) | |

v6 sai 391: 8B bớt chủ yếu ở 『』 của TCF (28 -> 13) và "tôi nói" (60 -> 47). Trong ô "còn lại" (87 câu sai), 42 câu là
câu người khác bị gán cho người kể: tính cả hai chiều, NHẦM NGƯỜI KỂ là 89/338 lỗi (26%) - vẫn là lỗi số một. App bắt được
ít: 97 câu 8B gán nhầm cho người kể trên các chương ngôi thứ nhất, thẻ 0b (xưng hô) hỏi 18 (19%), gợi ý đúng người 9, hỏi
nhầm 7 câu đúng; tên người kể nằm trong câu chỉ 7 câu (6 sai), phần lớn đã là thẻ 2 ("gọi tên ở đầu câu") - không làm thẻ
mới. Phần còn lại cần ngữ cảnh lượt lời (v8) hay người đọc Kịch bản. Công cụ: `card0b_recall.py`, `narrator_name_cue.py`. Cặp chương LN (cơ sở + mở rộng, cách xa
nhau) gần như không chung nhân vật ngoài người kể, nên KHÔNG đo được thẻ tách giọng cần hồ sơ ở chương khác - phải dùng
các chương liền nhau (Nageki 60-64). Công cụ: scratchpad `error_map.py`, `split_pairs_eval.py`.

**Huấn luyện 8B trên Mac mini M4 16 GB (MLX): chạy được nhưng ~35 giờ/epoch.** Câu hỏi của chủ sách ("sao không train 8b
trên mac?"). mlx-lm, `mlx-community/Qwen3-8B-4bit`, LoRA rank 16 mọi lớp tuyến tính, chỉ tính loss câu trả lời, tối đa 4608
token, batch 1, 24 mẫu data_v7n rải đều (trung bình 10.367 ký tự/mẫu, cả tập 10.333): ~62 giây/mẫu (0,014-0,017 it/s),
bộ nhớ đỉnh 11,4 GB, RAM trống còn ~10%. Cả tập 2.057 mẫu: ~35 giờ. So: máy nhà 4B ~5 giây/mẫu (card 8 GB không vừa
huấn luyện 8B), Modal L40S 8B ~1 giờ/epoch (~3 USD). Công thức MLX (lượng tử affine 4-bit của MLX, tối ưu hoá khác) cũng
khác Unsloth của Kaggle/Modal nên kết quả không so thẳng được. Kết luận: 8B học trên Modal; Mac chỉ gánh thêm một biến thể
chạy nền khi thật cần.

**Phép kiểm thẻ "hai người chung một tên" trên cuốn đủ chương: dừng, làm lại trên máy nhà.** `split_check_mac.sh` gộp
Nageki 56-64 (8 chương, 2.203 câu) thành MỘT dự án, nên dây chuyền phân tích cả cuốn trước: sau 8 giờ mới 608 câu (~76
câu/giờ, chậm ~6 lần các chương đơn), mỗi lượt đo một chương hết hạn 2 giờ. Làm lại khi hàng GPU nhà rảnh (8B ở nhà nhanh
~6 lần Mac), hay bớt còn 3-4 chương.

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
- Đây là chỗ v7 nhắm tới (dữ liệu dạy nhãn cục bộ có mô tả cho từng người lạ). Kiểm tiền đề trên đáp án mẫu của tập huấn
  luyện: data_v6 dạy 174/176 câu người lạ bằng MỘT nhãn "người lạ"; data_v7 dạy 50 mô tả khác nhau ("nữ hầu cận của
  Marla", "trưởng thôn"...), không còn "người lạ" nào. v7 có giảm việc nhập không: `ln_strangers.py` khi v7 đo xong.

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

**Kết quả âm: danh từ chỉ người trong lời kể sát câu không dò được việc nhập.** Câu người lạ bị gán cho nhân vật có tên,
lời kể trong hai đoạn quanh câu có nhắc "bà lão", "gã", "người đàn ông"... mà không nhắc tên nhân vật được gán? Chỉ
4/23 (v3), 4/21 (v6), 6/36 (8B) câu nhập có dấu hiệu ấy, và câu gán ĐÚNG cũng có (7/287, 7/263, 10/283): hỏi theo nó chỉ
đúng 36-38%. Lời kể của LN hiếm gắn lời dẫn vào từng câu thoại; xưng hô (thẻ 0c) là tín hiệu tốt hơn. Công cụ:
scratchpad `stranger_tag_cue.py`.

**Kết quả âm: lời dẫn nêu tên ("…," Lucia nói.) cũng không.** Câu máy gán cho X mà đoạn lời kể liền trước/sau có "<Y>
nói/hỏi/đáp…" (Y một nhân vật có tên khác trong chương): trên 12 chương LN, 8B-v5 chỉ 17/768 câu có dấu hiệu, đúng là Y
3/17; v6 27/781, đúng 7. Bắt được 1-2% số câu sai. Model đã dùng tốt lời dẫn có tên - câu sai là câu KHÔNG có lời dẫn
(đối đáp liền, người kể "tôi"), chỉ ngữ cảnh lượt lời gỡ được. Công cụ: scratchpad `named_tag_cue.py` (so bằng
`speaker_credit`, không bằng tên đầu của đáp án - đáp án ghi nhiều cách viết một tên).

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
- Mỗi cuốn một quy ước. Máy không đoán được, người nghe thì biết ngay. Vì vậy app có **quy ước 『』 theo cả cuốn** (0.4.2, `abook/bracket_rule.py`): chọn một lần, các phần sau tự áp trước bước phân vai.

**Gieo sổ nhân vật đã biết** (Mac, v3), đúng thứ "Làm tiếp cuốn này" mang sang phần sau:

| chương | không gieo | có gieo |
|---|---|---|
| Nageki 65 (8 người) | 78,7 | 79,0 |
| Yamiyo 225 (13 người) | 74,8 | 76,2 |

Giúp nhẹ, rõ hơn khi truyện đông người.

**Phiên bản Ollama không đổi đầu ra.** Trên Mac, v3 chạy bằng 0.33.2 và 0.34.4 ra đúng từng số. Mac lệch nhà 4 điểm là do phần cứng (Metal so với CUDA), nên số đo trên Mac chỉ so với số đo trên Mac.

## v6 29-09 07:2x - KẾT QUẢ ÂM: dữ liệu "nhắm lỗi" làm tệ đúng loại câu nó nhắm

v6 = công thức v3 trên data_v6 (2057 mẫu = thành phần v3 + 4 chương thêm để nhắm lỗi 『』 và đối đáp ngôi thứ nhất: LU 03,
Nageki 53, TCF 107, Yamiyo 009; tên theo sách, không chương cổng). LN gốc 6 chương: F1 giọng 55,8 vs v3 57,4 (-1,7, KTC95
-3,9..+0,4), người nói chặt 58,7 vs 63,7, hơn 2 thua 4. Theo loại (scratchpad ln_categories.py): 『』 43,6 -> 23,1; đối đáp
liền 68,5 -> 57,7; các loại khác gần như cũ.

Soi (bracket_flip.py): TCF 107 có 18 câu 『』 là "KÝ SINH TRÙNG" nói (thần giao); TCF 042 (chương thi) có 35 câu 『』 là LỜI
KỂ (đáp án NARRATOR, chấp nhận vai phụ). v3 gán chúng cho vai phụ cục bộ (được tính), v6 gán 15 câu cho KUCHINASHI - học
"『』 = một thực thể đang nói" từ 107. **Nghĩa của 『』 đổi theo chương ngay trong một truyện**: thêm vài chương cùng kiểu
dạy model một liên tưởng của truyện chứ không dạy cách đọc ngữ cảnh. Linh thể TỌA PHU ĐỒNG TỬ (Yamiyo 141, tên CÓ trong
chương) vẫn không model nào nhận ra, kể cả sau khi học Yamiyo 009.

Bài học: dữ liệu nhắm một loại lỗi phải có nhiều truyện, nhiều nghĩa của cùng một dấu hiệu - không phải vài chương của một
truyện. Đối chứng v6b (data_v6 bỏ 4 chương, 1717 mẫu ~ data_v3 1727) đã xếp hàng trước v7; luật đặt trước: v6b hơn v6 >= 1,0
F1 trên 12 chương LN thì v7/v8/q35 học bản bỏ 4 chương (hàng tự quyết, scratchpad choose_composition.py).

## ĐỘ TIN CỦA THƯỚC LN 29-09 05:xx - sổ "nhân vật đã biết" trống trong bộ đo, đầy trong sách thật

Bộ đo `--book` (LN, các cổng) tạo project trống cho MỖI chương: prompt mở đầu "(Chưa có nhân vật đã biết)". Sách thật tới
chương 141 có sổ tới 80 người từ các chương trước (`_known_summary`: tên, số lần gặp, giới). Thước quyết định model đo một
điều kiện mà sản xuất chỉ gặp ở chương đầu.

Đo bằng CPU (scratchpad `cast_absent.py`): 133/722 câu có tên trong 12 chương LN có người nói KHÔNG được nhắc tên trong
chương, cả 133 đều có ở chương trước - nhưng 130 câu là của người kể "tôi" (TOMOBE Yamiyo 62, KAKERU LU 54, KRAI Nageki 13)
mà prompt đã nêu qua `--first-person`. Chỉ 3 câu thật sự vắng tên. (Tôi đã nhầm lúc đầu: TOMOBE là người kể, không phải
linh thể nói trong 『』 - linh thể là TỌA PHU ĐỒNG TỬ và tên có trong chương.) Vậy không có nhóm câu "không thể đoán";
câu hỏi còn lại là model dùng một sổ thật tốt hay bị nó kéo lệch - 21-09 trên cuốn 2 (`LLM_EVAL.md`, `no-counts`): số đếm
kéo model về người nổi tiếng, cơ chế thật, lợi ròng ~0 với qwen3:8b. Với LoRA (học phần lớn trên sổ ngắn: replay gom các
chương gold THƯA của một truyện vào một project) thì chưa ai đo.

Công cụ: `seed_gold_cast.py` + `eval_models.py --seed-gold-cast` gieo sổ từ đáp án các chương SỐ NHỎ HƠN chương đo (sách
thật không biết tương lai). Lượt đầu (Mac, cùng máy cho hai điều kiện): v3 trên Nageki 65 (gieo 8 người) và Yamiyo 225
(13 người), xen kẽ tắt/bật. **Luật đặt trước khi có số:** hiệu người nói/F1 giọng trong ±3 điểm trên cả hai chương = thước
LN hiện tại đủ tin, giữ nguyên; lệch cùng chiều quá 3 điểm = đo lại các model ứng viên có gieo trước khi chọn mặc định.

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
1. `abook/speaker_scorer.py` (chỉ suy luận): dựng cửa sổ theo chương từ `segments` (seq, kind, paragraph_index,
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
