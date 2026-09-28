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

# abook-analysis:v3

*Vietnamese audiobook analysis model for [ABook](https://github.com/ntanhpro1221/ABook): labels every segment of a
Vietnamese novel with who speaks, narration / dialogue / thought, emotion, intensity, pace, volume and gender, as JSON
under ABook's own prompt and schema. Qwen3-4B-Instruct-2507 + LoRA (r=16), merged, GGUF Q8_0 (4.28 GB). Apache-2.0.*

Model phân tích truyện của dây chuyền làm sách nói ABook: với mỗi đoạn văn, ai nói (-> giọng đọc), đoạn kể / thoại / nội
tâm, cảm xúc, cường độ, nhịp, âm lượng, giới tính. Chạy được trên card NVIDIA 8 GB, nhanh hơn qwen3:8b 1,5-1,7 lần.

## Dùng

**Studio của ABook tự tải** khi cài hoặc bấm "Cập nhật Studio" - không phải làm gì.

Dùng tay: tải `abook-analysis-v3.Q8_0.gguf` và `Modelfile` vào cùng một thư mục, kiểm SHA-256
(`9545ce0bf921f3b771a796272b736d043dc4082cb14d1a51fcc93c55e4c53778`), rồi:

```
ollama create abook-analysis:v3 -f Modelfile
```

Đã đo với Ollama 0.33.2. Ollama 0.34 cho dòng qwen3 "suy nghĩ" trước khi trả JSON kể cả khi request có `format`: gửi
`"think": false` như ABook.

Model chỉ học prompt và schema của ABook (`ebook_reader/analysis.py`); hỏi kiểu khác thì không có gì bảo đảm.

## Huấn luyện

- Nền: `Qwen/Qwen3-4B-Instruct-2507` (Apache-2.0).
- LoRA r=16, alpha 32, dropout 0,05 trên mọi lớp chiếu (q, k, v, o, gate, up, down); 1 epoch; gộp vào model nền rồi
  xuất GGUF Q8_0 (`scripts/model_eval/train_lora.py`, `serve_lora.py`).
- Loss chỉ tính trên câu trả lời (`assistant_only_loss`): model học gán nhãn, không học sinh lại văn bản truyện.
- Dữ liệu: nhãn đáp án chuẩn do chính dự án làm (`scripts/model_eval/gold/`, quy ước trong `docs/GOLD_GUIDE.md`), phát
  lại qua đúng bộ phân tích sản xuất (`gold_replay.py` -> `build_training_set.py`). Không dùng bộ dữ liệu ngoài nào. Văn
  bản truyện không được phát hành.
- Chương dùng để đo không bao giờ vào dữ liệu huấn luyện.

## Kết quả đo

Thước chính: F1 giọng B-cubed (người nghe nghe thấy đúng một giọng cho một người) / người nói đúng tuyệt đối. Cùng máy,
cùng mã host, khởi đầu lạnh. Chi tiết: `docs/ANALYSIS_RESEARCH.md`.

| bộ đo | câu | qwen3:8b gốc | **abook-analysis:v3** |
|---|---|---|---|
| Light novel Nhật/Hàn, 6 truyện, chương chưa học | 519 | 52,9 / 54,9 | **55,7 / 62,4** |
| Young Master's PoV 248 (Hàn), ngôi thứ nhất | 47 | 56,1 / 61,7 | **85,5 / 93,6** |
| Tam quốc diễn nghĩa, hồi 50-52 | 219 | 74,8 / 79,5 | **85,6 / 89,5** |
| Tắt đèn XX, XXI, XXIV | 112 | 72,7 / 75,9 | **73,9 / 82,1** |
| Throne of Magical Arcana, 4 chương đo | 156 | 55,8 / 65,4 | **60,1 / 69,9** |

Lỗi còn nhiều nhất: truyện ngôi thứ nhất có hai người cùng tên gọi quen, lời trong 『』 (linh thể, giọng trong đầu), và
chuỗi thoại hai người không lời dẫn bị lệch một nhịp.

## Giấy phép

Apache-2.0, như model nền Qwen3-4B-Instruct-2507.
