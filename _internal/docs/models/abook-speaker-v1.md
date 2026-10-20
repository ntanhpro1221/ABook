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

# abook-speaker:v1

*Per-line speaker attribution model for [ABook](https://github.com/ntanhpro1221/ABook): given one dialogue or thought
line of a Vietnamese novel, with its surrounding paragraphs and the speakers already assigned before it, answers who speaks
it as `{"speaker": ...}` under ABook's own prompt and schema. Qwen3-4B-Instruct-2507 + LoRA (r=16), merged, GGUF Q8_0
(3.99 GiB). Apache-2.0.*

Model xác định người nói của ABook. Sau khi model phân tích (`abook-analyzer:v5`) làm xong cả quyển, ABook hỏi lại model
này người nói của TỪNG câu thoại và nội tâm, mỗi câu một lời gọi, với cùng cửa sổ văn bản mà người nghe sẽ thấy quanh câu
ấy. Loại câu (kể, thoại, nội tâm) vẫn là của model phân tích. Chạy được trên card NVIDIA 8 GB, cộng khoảng 6 % thời gian
phân tích. Chỉ đi cặp với `abook-analyzer:v5`: app khoá cặp model theo từng cuốn, sách phân tích bằng model khác không
chạy lượt này.

## Dùng

**Studio của ABook tự tải** khi cài hoặc khi bấm "Cập nhật Studio", không phải làm gì.

Dùng tay: tải `abook-speaker-v1.Q8_0.gguf` và `Modelfile` vào cùng một thư mục, kiểm SHA-256
(`156f08246478eac7de78cfe61bcca2d14df75c6fdcb0b2e896738676c341e69a`), rồi chạy:

```
ollama create abook-speaker:v1 -f Modelfile
```

Gửi `"think": false`, `format` là schema `{"speaker": string}`, nhiệt độ 0, hạt 0, `num_ctx` 16384 như ABook
(`abook/speaker_pass.py`). Model chỉ học đúng đề của ABook, hỏi theo kiểu khác thì không có gì bảo đảm.

## Huấn luyện

- Nền: `Qwen/Qwen3-4B-Instruct-2507` (Apache-2.0).
- Công thức như model phân tích v5: LoRA r=16, alpha 32, dropout 0,05 trên mọi lớp chiếu; 1 epoch; lr 1e-4 cosine; hạt 1234.
  LoRA được gộp vào model nền rồi xuất GGUF Q8_0.
- Loss chỉ tính trên câu trả lời: model học gán nhãn, không học sinh lại văn bản truyện.
- Dữ liệu: 5.724 mẫu, mỗi mẫu là một câu thoại hoặc nội tâm trong một khối đoạn liền nhau (4-8 câu nói), kèm 9 đoạn trước,
  6 đoạn sau chỉ để đọc tiếp và danh sách nhân vật đã biết. Nhãn từ đáp án chuẩn của dự án. Chương dùng để đo không bao
  giờ vào dữ liệu huấn luyện. Văn bản truyện không được phát hành.

## Kết quả đo

Chỉ số: độ đúng người nói theo giọng nghe, sau đúng các bước chuẩn hoá tên mà app chạy (khoá tên, ghép biệt danh), trên 56
chương chưa học so với đáp án chuẩn. Cùng nội dung chương, cùng loại câu của model phân tích; chỉ khác nhãn người nói.

| bộ đo | model phân tích một mình (v5) | **v5 + lượt người nói** | chênh |
|---|---|---|---|
| 56 chương (hạt 1234) | 73,96 | **79,00** | +4,98 |
| 56 chương (hạt 1) | 73,59 | **78,51** | +4,92 |
| cổng 19 chương (hạt 1234) | 77,62 | **81,32** | +3,7 |

Chênh sau khi trừ sai số: +1,69 điểm (hệ số 2,4, độ lệch giữa các hạt 0,23, SE 1,37). Cả hai hạt cùng hướng.

Chi phí: khoảng 58 giây mỗi chương trên card 8 GB, cộng khoảng 6 % thời gian phân tích.

## Giấy phép

Apache-2.0, như model nền Qwen3-4B-Instruct-2507.
