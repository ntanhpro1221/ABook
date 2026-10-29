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

# abook-analyzer:v5

*Vietnamese audiobook analysis model for [ABook](https://github.com/ntanhpro1221/ABook): labels every segment of a
Vietnamese novel with who speaks, narration / dialogue / thought, emotion, intensity, pace, volume and gender, as JSON
under ABook's own prompt and schema. Qwen3-4B-Instruct-2507 + LoRA (r=16), merged, GGUF Q8_0 (3.99 GiB). Apache-2.0.*

Model phân tích truyện của dây chuyền làm sách nói ABook. Với mỗi đoạn văn, model cho biết ai nói (để chọn giọng đọc),
đoạn ấy là lời kể, lời thoại hay nội tâm, cùng cảm xúc, cường độ, nhịp, âm lượng và giới tính. Chạy được trên card
NVIDIA 8 GB. Là mặc định cho sách mới từ ABook 0.4.116, đi cặp với abook-speaker:v2 (v1 tới 0.4.147) (hỏi lại người nói từng câu). Sách đã phân tích bằng v4 vẫn giữ v4, vì app khoá model theo
từng cuốn.

## Dùng

**Studio của ABook tự tải** khi cài hoặc khi bấm "Cập nhật Studio", không phải làm gì.

Dùng tay: tải `abook-analyzer-v5.Q8_0.gguf` và `Modelfile` vào cùng một thư mục, kiểm SHA-256
(`TODO_SHA256`), rồi chạy:

```
ollama create abook-analyzer:v5 -f Modelfile
```

Gửi `"think": false` như ABook vẫn làm, nếu không, dòng qwen3 trên Ollama 0.34 sẽ "suy nghĩ" trước khi trả JSON.

Model chỉ học prompt và schema của ABook (`abook/analysis.py`), hỏi theo kiểu khác thì không có gì bảo đảm. Model học
với khối "đoạn ngay trước" trong prompt; Studio gửi 9 đoạn.

## Huấn luyện

- Nền: `Qwen/Qwen3-4B-Instruct-2507` (Apache-2.0).
- Công thức giống hệt v4: LoRA r=16, alpha 32, dropout 0,05 trên mọi lớp chiếu; 1 epoch; lr 1e-4 cosine; hạt 1234.
  LoRA được gộp vào model nền rồi xuất GGUF Q8_0.
- Loss chỉ tính trên câu trả lời: model học gán nhãn, không học sinh lại văn bản truyện.
- Dữ liệu: 4.216 mẫu, gấp khoảng 2 lần v4:
  - 2.057 mẫu đáp án chuẩn của v4;
  - 2.159 mẫu nhãn "bạc" trên khoảng 40 chương khó, do model lớn hơn gán dưới đúng prompt sản xuất (đợt thí điểm chỉ giữ
    câu hai model thầy đồng thuận).
- Không chương bạc nào thuộc truyện của bộ đo. Chương dùng để đo không bao giờ vào dữ liệu huấn luyện. Văn bản truyện
  không được phát hành.

## Kết quả đo

Chỉ số chính: F1 giọng, tức gán đúng người nói cho câu thoại và nội tâm, có trọng số theo giọng, so với đáp án chuẩn.
Cả hai model đo như app gửi prompt (9 đoạn trước).

| bộ đo | v4 | **v5** | chênh |
|---|---|---|---|
| LN Nhật, 11 chương chưa học | 61,8 % | **67,2 %** | +5,4 |
| LN Hàn, 8 chương chưa học | 69,7 % | **72,4 %** | +2,7 |
| gộp 19 chương / 11 truyện, F1 giọng | | | **+4,2** (KTC 95 % +1,8..+5,3) |
| gộp, người nói chặt | | | **+5,0** (KTC 95 % +2,3..+7,7) |

KTC là bootstrap theo CỤM TRUYỆN (2.000 lần lấy lại cả truyện). Các chương của cùng một truyện không độc lập với nhau,
nên KTC theo chương sẽ hẹp giả. Hạt thứ hai (hạt 1) ra cùng hướng: Nhật 65,2, Hàn 74,7.

Kiểm phụ tiếng Trung (Tam quốc diễn nghĩa 050-052 + 4 chương truyện mạng): TODO_ZH.

Thay đổi hành vi đã biết: v5 gán nhãn **nội tâm** cho cửa sổ hệ thống trong `[ ... ]` và lời thần giao cách cảm trong
`≪ ... ≫`, và gán câu `≪ ... ≫` cho người nói ra nó. Khi nghe không thấy hại gì: giọng vẫn là của đúng người.

## Giấy phép

Apache-2.0, như model nền Qwen3-4B-Instruct-2507.
