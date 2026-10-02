# Thành phần bên thứ ba

ABook phát hành theo giấy phép MIT (`_internal/LICENSE`). Mỗi thành phần bên thứ ba dưới đây giữ giấy phép riêng của
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
  nguồn). Source đi kèm giữ nguyên `_internal/abook/assets/CMUDICT_LICENSE.txt`.

## App Windows đóng gói (bộ cài NSIS, `docs/PACKAGING.md`)

Bộ cài mang theo:

- Tauri 2 và các plugin single-instance, dialog, updater (MIT hoặc Apache-2.0); WebView2 là của Windows (Microsoft) -
  bộ cài chỉ tải trình cài WebView2 khi máy thiếu, không phân phối lại.
- NSIS (giấy phép zlib/libpng) và `nsis_tauri_utils` (MIT hoặc Apache-2.0) - trình cài/gỡ.
- Python 3.14 embeddable (Python Software Foundation License).
- Pillow (HPND), psutil (BSD-3-Clause), requests (Apache-2.0), urllib3 (MIT), certifi (MPL-2.0), charset-normalizer
  (MIT), idna (BSD-3-Clause) - đúng các bản trong `shell/python/requirements.txt`.
- Thư viện chạy Microsoft Visual C++ (`msvcp140*.dll`, `vcruntime140*.dll`, `concrt140.dll` từ thư mục
  `Microsoft.VC145.CRT` của Visual Studio) - thuộc "Distributable Code" của giấy phép Visual Studio, được phép phát hành
  kèm ứng dụng; bộ cài chỉ mang để chép vào Python của Studio (máy chưa cài gói VC++ Redistributable vẫn chạy được).

Studio tải thêm khi người dùng bấm "Cài Studio" (không nằm trong bộ cài; tải thẳng từ nơi phát hành chính thức, ghim
băm trong `webui/studio_setup.py`):

- uv (MIT hoặc Apache-2.0); Python 3.11 bản python-build-standalone (PSF License cùng giấy phép của từng thành phần).
- MinGit / Git for Windows (GPL-2.0) - chỉ để cài UTMOSv2 từ đúng commit; ABook không sửa hay phân phối lại.
- Ollama (MIT) - bản riêng của Studio, đúng bản dây chuyền đã kiểm, kể cả khi máy đã có Ollama; các thư viện của dây
  chuyền theo `shell/python/studio-requirements.txt` (giấy phép như mục
  "App máy tính - dây chuyền sản xuất" ở trên); model tải từ Hugging Face / Ollama theo giấy phép của từng model,
  trong đó model phân tích của chính dự án `abook-analyzer` (huggingface.co/NGDtuanh/abook-analyzer, Apache-2.0 như
  model nền Qwen3-4B-Instruct-2507; thẻ model: `docs/models/`).

## Giao diện (máy tính và điện thoại dùng chung)

- React, React DOM, React Router (MIT); TanStack Query (MIT); Radix UI (MIT); lucide-react (ISC); sonner (MIT);
  Tailwind CSS (MIT); Vite (MIT).
- Font Be Vietnam Pro (SIL Open Font License 1.1).

## App điện thoại (Android)

- Capacitor (MIT).
- AndroidX Media3 - ExoPlayer, MediaSession, datasource, cache (Apache-2.0); các thư viện AndroidX khác (Apache-2.0).
- Kotlin và Guava (Apache-2.0).

## Nhạc nền (không đóng gói trong bộ cài)

Bộ cài và APK không mang bài nhạc nào. Studio đọc danh mục nhạc đã phân tích sẵn qua mạng (địa chỉ trong cấu hình từ xa
có chữ ký), tải bài cần dùng từ nguồn gốc vào bộ đệm của máy và đóng vào file sách `.abook` của cuốn ấy, kèm ghi công của
từng bài; trình nghe hiện ghi công khi bài đang phát.

- Kevin MacLeod / incompetech.com - Creative Commons Attribution 4.0.
- Jamendo (bài CC BY / CC0 theo từng bài; thông tin bài qua Openverse - không do Openverse bảo trợ).
- Freesound (bài CC0 / CC BY theo từng âm thanh).

Bộ phân tích "Nhạc của tôi" (`webui/music_student.py`) dùng tháp âm thanh của LAION-CLAP `laion/clap-htsat-unfused` (Apache-2.0,
fp16, ~55 MB) cùng đầu hồi quy nhỏ của chính dự án; gói đăng ở huggingface.co/NGDtuanh/abook-music-student, tải về máy một lần
khi cần, KHÔNG nằm trong bộ cài. Kèm giấy phép Apache-2.0 và ghi chú của LAION-CLAP khi phân phối gói.

## Model phân tích và dữ liệu nghiên cứu (chưa đóng gói trong bản phát hành)

- LoRA tự huấn luyện trên nền Qwen3-4B-Instruct-2507 (Apache-2.0), dữ liệu huấn luyện là đáp án chuẩn của chính dự án.
  Khi phân phối: kèm giấy phép Apache-2.0 và ghi chú của model nền.
- Bộ chấm ứng viên người nói trên nền mmBERT (jhu-clsp) - xem model card trước khi phân phối; học trước trên PDNC (tiểu
  thuyết tiếng Anh). Dữ liệu CSI (truyện mạng tiếng Trung) chỉ cho nghiên cứu phi thương mại: KHÔNG phát hành model học từ
  nó khi chưa được chủ dự án đồng ý.
- Kho truyện nghiên cứu (văn bản truyện dùng để đo và huấn luyện) KHÔNG nằm trong repo này hay bất kỳ bản phát hành nào:
  phần lớn còn bản quyền, nên kho ở một repo riêng tư. Repo này chỉ giữ đáp án chuẩn (số thứ tự câu và nhãn người nói,
  cảm xúc), không chép văn bản truyện. Hai bản đã hết bảo hộ trong kho, lấy từ Wikisource tiếng Việt: Tam quốc diễn
  nghĩa (Phan Kế Bính dịch 1909, Bùi Kỷ hiệu đính) và Tắt đèn (Ngô Tất Tố, 1937-1939).
