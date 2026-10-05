---
license: apache-2.0
base_model: Qwen/Qwen3-4B-Instruct-2507
base_model_relation: finetune
language:
- vi
pipeline_tag: text-generation
library_name: gguf
tags:
- gguf
- ollama
- audiobook
- vietnamese
- speaker-attribution
---

# abook-analyzer:v4

*Vietnamese audiobook analysis model for [ABook](https://github.com/ntanhpro1221/ABook): labels every segment of a
Vietnamese novel with who speaks, narration / dialogue / thought, emotion, intensity, pace, volume and gender, as JSON
under ABook's own prompt and schema. Qwen3-4B-Instruct-2507 + LoRA (r=16), merged, GGUF Q8_0 (4.28 GB). Apache-2.0.*

Model phân tích truyện của dây chuyền làm sách nói ABook: với mỗi đoạn văn, ai nói (-> giọng đọc), đoạn kể / thoại / nội
tâm, cảm xúc, cường độ, nhịp, âm lượng, giới tính. Chạy được trên card NVIDIA 8 GB, nhanh hơn qwen3:8b 1,5-1,7 lần.

## Dùng

**Studio của ABook tự tải** khi cài hoặc bấm "Cập nhật Studio" - không phải làm gì.

Dùng tay: tải `abook-analyzer-v4.Q8_0.gguf` và `Modelfile` vào cùng một thư mục, kiểm SHA-256
(`1ecd40a6b6839fc986f1095001110ebbfd9043608d0e69b30be762a85673feeb`), rồi:

```
ollama create abook-analyzer:v4 -f Modelfile
```

Đã đo với Ollama 0.33.2. Ollama 0.34 cho dòng qwen3 "suy nghĩ" trước khi trả JSON kể cả khi request có `format`: gửi
`"think": false` như ABook.

Model chỉ học prompt và schema của ABook (`abook/analysis.py`); hỏi kiểu khác thì không có gì bảo đảm.

## Huấn luyện

- Nền: `Qwen/Qwen3-4B-Instruct-2507` (Apache-2.0).
- LoRA r=16, alpha 32, dropout 0,05 trên mọi lớp chiếu (q, k, v, o, gate, up, down); 1 epoch; gộp vào model nền rồi
  xuất GGUF Q8_0 (`scripts/model_eval/train_lora.py`, `serve_lora.py`).
- Loss chỉ tính trên câu trả lời (`assistant_only_loss`): model học gán nhãn, không học sinh lại văn bản truyện.
- Dữ liệu: nhãn đáp án chuẩn do chính dự án làm (`scripts/model_eval/gold/`, quy ước trong `docs/GOLD_GUIDE.md`), phát
  lại qua đúng bộ phân tích sản xuất (`gold_replay.py` -> `build_training_set.py`). Không dùng bộ dữ liệu ngoài nào. Văn
  bản truyện không được phát hành.
- Dữ liệu v4 (data_v7): đáp án chuẩn của v3 + mô tả người vô danh; mỗi mẫu có khối 4 đoạn ngay trước.
- Chương dùng để đo không bao giờ vào dữ liệu huấn luyện.

## Kết quả đo

Chỉ số: F1 giọng (gán đúng người nói cho câu thoại và nội tâm, có trọng số theo giọng), so với đáp án chuẩn. Mỗi model đo với đúng cách app gửi prompt cho nó: v3 không có khối đoạn trước (như 0.4.27), v4 có 9 đoạn. KTC: bootstrap theo chương, 2.000 lần.
| bộ đo | câu | chỉ số | v3 khối 0 (app 0.4.27) | **v4 khối 9** | chênh (KTC 95 %) |
|---|---|---|---|---|---|
| LN Nhật, 3 truyện, 11 chương chưa học | 767 | F1 giọng | 56,0 % | **61,8 %** | +5,8 (+2,0..+11,2) |
| | | người nói chặt | 65,4 % | **72,9 %** | +7,4 (+3,4..+12,6) |
| | | cảm xúc | 88,9 % | **93,5 %** | +4,6 (+2,7..+6,1) |
| LN Hàn, 8 chương chưa học | 618 | F1 giọng | 61,4 % | **68,5 %** | +7,0 (+3,8..+10,9) |
| | | người nói chặt | 62,9 % | **68,0 %** | +5,0 (+0,0..+10,4) |
| | | cảm xúc | 91,1 % | **93,7 %** | +2,5 (+1,5..+3,8) |

F1 giọng từng chương: v4 hơn v3 ở 9/11 chương Nhật (thua 2: −0,6 và −0,1 điểm) và 7/8 chương Hàn (thua 1: −3,2 điểm).

v4 học với khối "đoạn ngay trước" trong prompt (ai nói ở các đoạn liền trước lô); Studio từ 0.4.28 gửi 9 đoạn. Dùng v4 với
host cũ (không khối) thì không có gì bảo đảm.

## Giấy phép

Apache-2.0, như model nền Qwen3-4B-Instruct-2507.
