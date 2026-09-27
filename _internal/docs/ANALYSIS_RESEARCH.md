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
| E2 | SFT QLoRA Qwen3-4B-Instruct-2507 trên gold (sinh JSON) | huấn luyện xong 1 epoch (8.140 s), xuất Ollama `lora27-4b:latest` + nền `base27-4b:latest`; lần chấm đầu hỏng vì app đòi tên model dạng `tên:tag` - xếp lại | chấm tập TEST so với chính nền |
| E3 | **Bộ chấm ứng viên người nói bằng encoder** (joint scoring, mmBERT, học trước PDNC rồi tinh chỉnh gold) | cơ sở xong (test 78,4%); học trước PDNC đang chạy | PDNC -> `build_pdnc.py`: 48.810 câu con, 7.598 cửa sổ, 89,2% người nói có trong ứng viên; người kể "I" suy ra đúng cả 4 truyện ngôi thứ nhất (Watson, Hastings, Jake Barnes, Alexis) |
| E4 | Prompt: few-shot lấy ví dụ gần nhất, tự nhất quán (k mẫu + bỏ phiếu), bỏ số lần nhắc | no-counts đo 21-09: không đáng kể | chưa thử few-shot / tự nhất quán |
| E5 | Luật sàng (host) - đo riêng từng luật: sửa bao nhiêu, phá bao nhiêu | có công cụ phát lại (`replay_from_candidates.py`, `gold_replay.py`) | |
| E6 | Kết hợp: encoder cho người nói + LLM cho cảm xúc/nhịp; bỏ phiếu nhiều model | chưa | |
| E7 | DPO trên cặp (đúng / sai của model) nhắm thiên lệch "nhân vật nổi tiếng nhất" | chưa | lỗi BELLAK -> LUCIEN (363:34-36) |
| E8 | Thêm gold (theo nhu cầu, nói rõ mục đích) cho chỗ yếu | chưa | luật "gold theo nhu cầu" 20-09 |

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

Công cụ: `compare_predictions.py` (so theo cặp từng câu, ensemble nhiều seed, McNemar, đọc cả dự đoán LLM từ project
eval) tái lập đúng số 74,1 / 67,8 / 22-13 / p 0,1755 ở trên. Mọi lần chạy bộ chấm ghi `dev/test_predictions.jsonl` có xác
suất biên từng thực thể + "không ai".

Hàng GPU (27-09 bài học): MỌI việc GPU đi qua một hàng; không sửa file script bash khi nó đang chạy (bash đọc theo vị trí
byte - sửa `scorer_27_09.sh` giữa chừng làm nó gãy cú pháp ở 11:09); mỗi bước tự bỏ qua khi đã xong để dừng/thả lại an
toàn (`scratchpad/gpu_queue_27_09b.sh`).

Thứ tự: E3 cơ sở (mốc) -> N7 + N1 (tăng trần và dữ liệu) -> N2, N3 -> N5 -> N4, N6.

## Máy và giới hạn

RTX 5060 Laptop 8 GB, Windows. PyTorch Windows không có flash attention; huấn luyện phải ghim attention cuDNN và KHÔNG
dùng optimizer `paged_*` (UVM làm BSOD khi lưu checkpoint - 27-09). Huấn luyện dài: `train_lora.py --resume`, lưu mỗi
50 bước. Phân tích sản xuất dùng Ollama (flash attention bật, tái dùng tiền tố prompt).
