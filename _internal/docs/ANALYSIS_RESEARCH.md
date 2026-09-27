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
