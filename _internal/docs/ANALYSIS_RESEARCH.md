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
| E1 | LLM có sẵn qua Ollama (qwen3 4b/8b, qwen3.5, gemma4, ministral, lfm2.5, ornith) | 8b/4b đo 21-09 (ngang nhau, 4b nhanh 27%); hàng 6 model mới chờ GPU (`scratchpad/night_27_09.sh`) | đo theo cặp 10 chương |
| E2 | SFT QLoRA Qwen3-4B-Instruct-2507 trên gold (sinh JSON) | đang huấn luyện 1 epoch 27-09 (`LLM_Train/runs/qwen3-4b-lora-27-09`) | sau đó: gộp adapter -> GGUF -> ollama -> chấm tập TEST so với chính nền |
| E3 | **Bộ chấm ứng viên người nói bằng encoder** (joint scoring, mmBERT, học trước PDNC rồi tinh chỉnh gold) | chuẩn bị: độ phủ ứng viên ±3 đoạn 93,3%, ±6 đoạn 95,1% (27-09) | chỉ thay trục người nói; cần: ứng viên = sổ nhân vật + chỗ nhắc |
| E4 | Prompt: few-shot lấy ví dụ gần nhất, tự nhất quán (k mẫu + bỏ phiếu), bỏ số lần nhắc | no-counts đo 21-09: không đáng kể | chưa thử few-shot / tự nhất quán |
| E5 | Luật sàng (host) - đo riêng từng luật: sửa bao nhiêu, phá bao nhiêu | có công cụ phát lại (`replay_from_candidates.py`, `gold_replay.py`) | |
| E6 | Kết hợp: encoder cho người nói + LLM cho cảm xúc/nhịp; bỏ phiếu nhiều model | chưa | |
| E7 | DPO trên cặp (đúng / sai của model) nhắm thiên lệch "nhân vật nổi tiếng nhất" | chưa | lỗi BELLAK -> LUCIEN (363:34-36) |
| E8 | Thêm gold (theo nhu cầu, nói rõ mục đích) cho chỗ yếu | chưa | luật "gold theo nhu cầu" 20-09 |

## Máy và giới hạn

RTX 5060 Laptop 8 GB, Windows. PyTorch Windows không có flash attention; huấn luyện phải ghim attention cuDNN và KHÔNG
dùng optimizer `paged_*` (UVM làm BSOD khi lưu checkpoint - 27-09). Huấn luyện dài: `train_lora.py --resume`, lưu mỗi
50 bước. Phân tích sản xuất dùng Ollama (flash attention bật, tái dùng tiền tố prompt).
