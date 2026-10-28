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

# abook-speaker:v2

*Per-line speaker attribution model for [ABook](https://github.com/ntanhpro1221/ABook): given one dialogue or thought
line of a Vietnamese novel, with its surrounding paragraphs and the speakers already assigned before it, answers who speaks
it as `{"speaker": ...}` under ABook's own prompt and schema. Qwen3-4B-Instruct-2507 + a weight-averaged soup of three LoRA
runs, merged, GGUF Q8_0 (3.99 GiB). Apache-2.0. Replaces `abook-speaker:v1` with the same prompt and schema.*

Model xác định người nói của ABook, bản thay `abook-speaker:v1`. Sau khi model phân tích (`abook-analyzer:v5`) làm xong cả
quyển, ABook hỏi lại model này người nói của TỪNG câu thoại và nội tâm, mỗi câu một lời gọi, với cùng cửa sổ văn bản mà
người nghe sẽ thấy quanh câu ấy. Loại câu (kể, thoại, nội tâm) vẫn là của model phân tích. Đề và lược đồ giống hệt v1;
chạy được trên card NVIDIA 8 GB, cùng tốc độ v1. Chỉ đi cặp với `abook-analyzer:v5`.

## Dùng

**Studio của ABook tự tải** khi cài hoặc khi bấm "Cập nhật Studio", không phải làm gì.

Dùng tay: tải `abook-speaker-v2.Q8_0.gguf` và `Modelfile` vào cùng một thư mục, kiểm SHA-256
(`813031b68a16c04032cc776341b0369dbec7adef66a28c2488b37fcdd376520a`), rồi chạy:

```
ollama create abook-speaker:v2 -f Modelfile
```

Gửi `"think": false`, `format` là schema `{"speaker": string}`, nhiệt độ 0, hạt 0, `num_ctx` 16384 như ABook
(`abook/speaker_pass.py`). Model chỉ học đúng đề của ABook, hỏi theo kiểu khác thì không có gì bảo đảm.

## Huấn luyện

- Nền: `Qwen/Qwen3-4B-Instruct-2507` (Apache-2.0). Điểm xuất phát: adapter của v1 (LoRA r=16, alpha 32).
- Học tiếp 716 bước (accum 8, lr 1e-4 cosine) trên 5.728 mẫu (cùng câu hỏi như v1), nhưng lịch sử "người nói đã gán trước câu này"
  trong đề được làm nhiễu giống lỗi thật: 27 % mục lịch sử đổi sang nhãn sai theo đúng tỉ lệ các kiểu lỗi mà v1 mắc khi
  tự đoán (đổi lượt, nhầm sang nhân vật đã biết, sang vai phụ, sang tên lạ). Model học trả lời đúng cả khi lịch sử trước
  đó sai - đúng tình huống lúc chạy thật, khi lịch sử là do chính nó đoán.
- Học ba lần chỉ khác hạt (1234, 1, 4321) từ cùng adapter v1, rồi lấy TRUNG BÌNH trọng số của ba lần (model soup, đúng
  từng phần tử của ΔW = B·A). Một lần học riêng dao động tới 1,6 điểm giữa các hạt; trung bình ba lần tốt hơn cả lần tốt nhất.
- Loss chỉ tính trên câu trả lời: model học gán nhãn, không học sinh lại văn bản truyện. Nhãn từ đáp án chuẩn của dự án;
  chương dùng để đo không bao giờ vào dữ liệu huấn luyện. Văn bản truyện không được phát hành.

## Kết quả đo

Chỉ số: độ đúng người nói theo giọng nghe, sau đúng các bước chuẩn hoá tên mà app chạy, trên 56 chương chưa học (44 truyện)
so với đáp án chuẩn, model phân tích v5 cho loại câu, lịch sử do chính model tự đoán (như lúc chạy thật).

| bộ đo | v1 | **v2** | chênh |
|---|---|---|---|
| 56 chương, máy dev (card 8 GB) | 79,11 | **81,40** | +2,30 |
| cổng 19 chương, máy dev | 81,17 | **82,98** | +1,81 |
| 56 chương, đo lặp trên máy thứ hai (Mac mini) | 78,55 | **81,36** | +2,81 |

Khoảng tin cậy 95 % (bootstrap theo truyện) của chênh so với bản đối chứng học cùng công thức không nhiễu: [+0,51; +3,80].
Đo lặp ở máy khác cùng dấu, cùng cỡ.

## Giấy phép

Apache-2.0, như model nền Qwen3-4B-Instruct-2507.
