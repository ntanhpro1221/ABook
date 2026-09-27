# Thành phần bên thứ ba

Ebook Reader phát hành theo giấy phép MIT (`_internal/LICENSE`). Mỗi thành phần bên thứ ba dưới đây giữ giấy phép riêng của
nó. Source không đóng gói model weights: lần cài đầu tải dependency và model về `_internal/runtime`. Khi phát hành gói cài
đặt, APK hay model cache, người bảo trì phải kiểm lại phiên bản THẬT SỰ được đóng gói và đính kèm LICENSE/NOTICE tương ứng
(`RELEASING.md`). Tên giấy phép ghi dưới đây là của bản đang dùng lúc viết - nguồn gốc cuối cùng luôn là file giấy phép
của chính thành phần ấy.

## App máy tính - dây chuyền sản xuất

- Qwen3 qua Ollama (model Qwen: Apache-2.0; Ollama: MIT).
- VieNeu / `vieneu` (TTS tiếng Việt) - xem giấy phép của model và thư viện trước khi phân phối lại.
- OpenAI Whisper (MIT).
- UTMOSv2 (SaruLab, MIT) cùng checkpoint naturalness MOS, Wav2Vec2 base, timm EfficientNet, Transformers, torchvision
  và librosa.
- PyTorch và torchaudio (BSD).
- PyWORLD và WORLD vocoder; Praat qua parselmouth.
- pyloudnorm; NumPy, SciPy, SoundFile, psutil, requests, huggingface-hub.
- PySide6 / Qt (LGPLv3) - cửa sổ app máy tính.
- FFmpeg / imageio-ffmpeg (LGPL hoặc GPL tuỳ bản build).
- CMU Pronouncing Dictionary (`cmudict.dict`, dữ liệu từ CMU Sphinx; sử dụng và phân phối không hạn chế, yêu cầu ghi nhận
  nguồn). Source đi kèm giữ nguyên `_internal/ebook_reader/assets/CMUDICT_LICENSE.txt`.

## Giao diện (máy tính và điện thoại dùng chung)

- React, React DOM, React Router (MIT); TanStack Query (MIT); Radix UI (MIT); lucide-react (ISC); sonner (MIT);
  Tailwind CSS (MIT); Vite (MIT).
- Font Be Vietnam Pro (SIL Open Font License 1.1).

## App điện thoại (Android)

- Capacitor (MIT).
- AndroidX Media3 - ExoPlayer, MediaSession, datasource, cache (Apache-2.0); các thư viện AndroidX khác (Apache-2.0).
- Kotlin và Guava (Apache-2.0).

## Model phân tích và dữ liệu nghiên cứu (chưa đóng gói trong bản phát hành)

- LoRA tự huấn luyện trên nền Qwen3-4B-Instruct-2507 (Apache-2.0), dữ liệu huấn luyện là đáp án chuẩn của chính dự án.
  Khi phân phối: kèm giấy phép Apache-2.0 và ghi chú của model nền.
- Bộ chấm ứng viên người nói trên nền mmBERT (jhu-clsp) - xem model card trước khi phân phối; học trước trên PDNC (tiểu
  thuyết tiếng Anh). Dữ liệu CSI (truyện mạng tiếng Trung) chỉ cho nghiên cứu phi thương mại: KHÔNG phát hành model học từ
  nó khi chưa được chủ dự án đồng ý.
- Văn bản thử nghiệm Tam quốc diễn nghĩa (Phan Kế Bính dịch, Bùi Kỷ hiệu đính) lấy từ Wikisource tiếng Việt - đã hết thời
  hạn bảo hộ.
