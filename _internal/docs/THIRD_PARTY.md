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
- pypdf 6.16.2 (BSD-3-Clause, thuần Python) - đọc chữ của PDF có lớp chữ khi nhập sách (`abook/importers.py`). Chép nguyên vào
  `abook/vendor/pypdf/` (kèm LICENSE và băm wheel nguồn), không phụ thuộc pyproject/uv.lock hay gói cài sẵn. Nhập EPUB và DOCX chỉ
  dùng thư viện chuẩn của Python (zipfile, xml, html.parser).
- PySide6 / Qt (LGPLv3) - cửa sổ app máy tính.
- FFmpeg / imageio-ffmpeg (LGPL hoặc GPL tuỳ bản build). Bản app chỉ-nghe KHÔNG mang ffmpeg trong bộ cài: mô-đun "Phân tích nhạc" (người dùng
  bấm mới tải, `webui/music_module.py`) tải bánh xe `imageio-ffmpeg` 0.6.0 (PyPI, ghim URL + SHA-256, `webui/ffmpeg_setup.py`) và lấy ra đúng một file, FFmpeg 7.1
  bản "essentials" của gyan.dev (cấu hình GPL-3.0, mã nguồn: https://www.gyan.dev/ffmpeg/builds/); phần bọc imageio-ffmpeg là BSD-2-Clause.
  Tải về thư mục dữ liệu của app (`tools/ffmpeg`), gỡ app là gỡ nó.
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
- Đọc thẻ + độ dài nhạc nhập mà không cần ffmpeg (`webui/music_local.py`): tinytag 2.3.2 (MIT, thuần Python), chép nguyên vào gói ở `abook/vendor/tinytag` (kèm LICENSE; mọi bản - dev lẫn bản đóng gói - dùng bản này).
- Mô-đun "Phân tích nhạc" (KHÔNG nằm trong bộ cài; tải khi người dùng bấm, wheel ghim URL + SHA-256 trong `webui/music_module.py`, giải vào
  `<dữ liệu app>/music/lib`): NumPy (BSD-3-Clause; wheel mang theo OpenBLAS BSD-3-Clause, LAPACK và thư viện chạy GCC GPL-3.0-or-later kèm GCC
  Runtime Library Exception - giấy phép từng phần nằm trong `numpy-*.dist-info/licenses`), ONNX Runtime CPU (MIT), flatbuffers
  (Apache-2.0), protobuf (BSD-3-Clause), packaging (Apache-2.0 hoặc BSD-2-Clause); cùng ffmpeg (ở trên) và model (mục "Nhạc nền").
- Bộ nhập sách (`abook/importers.py`) mang theo pypdf 6.16.2 (BSD-3-Clause) trong mã nguồn (`abook/vendor/pypdf/`), nên bản app chỉ-nghe
  không cần thêm gói nào.
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
- ONNX Runtime 1.30.0 (Microsoft, MIT): phần Java API (`ai.onnxruntime.*`) chép nguyên từ `onnxruntime-android-1.30.0-sources.jar` vào
  `app/src/main/java/ai/onnxruntime` (giữ đầu giấy phép MIT của từng file; chỉ `OnnxRuntime.java` sửa chỗ nạp thư viện). Hai thư viện native
  (`libonnxruntime.so`, `libonnxruntime4j_jni.so`) KHÔNG nằm trong APK: tải cùng "Gói nhạc" khi người dùng bấm, lấy từ AAR chính thức trên
  Maven Central (`scripts/prepare_ort_runtime.py`).
- pdf.js / `pdfjs-dist` (Mozilla, Apache-2.0), bản "legacy" - đọc chữ của PDF có lớp chữ khi nhập sách trên điện thoại
  (`ui/src/shared/pdfPages.ts`); tải lười, chỉ chạy khi người dùng mở một file PDF. EPUB và DOCX do `BookImport.kt` tự đọc
  bằng java.util.zip, không thêm thư viện.

## Nhạc nền (không đóng gói trong bộ cài)

Bộ cài và APK không mang bài nhạc nào. Studio đọc danh mục nhạc đã phân tích sẵn qua mạng (địa chỉ trong cấu hình từ xa
có chữ ký), tải bài cần dùng từ nguồn gốc vào bộ đệm của máy và đóng vào file sách `.abook` của cuốn ấy, kèm ghi công của
từng bài; trình nghe hiện ghi công khi bài đang phát.

- Kevin MacLeod / incompetech.com - Creative Commons Attribution 4.0.
- Jamendo (bài CC BY / CC0 theo từng bài; thông tin bài qua Openverse - không do Openverse bảo trợ).
- Freesound (bài CC0 / CC BY theo từng âm thanh).

Bộ phân tích "Nhạc của tôi" (`webui/music_student.py`) dùng tháp âm thanh của LAION-CLAP `laion/clap-htsat-unfused` (Apache-2.0,
fp16, ~55 MB) cùng đầu hồi quy nhỏ của chính dự án; gói đăng ở huggingface.co/NGDtuanh/abook-music-student, tải về máy một lần
khi cần, KHÔNG nằm trong bộ cài. Kèm giấy phép Apache-2.0 và ghi chú của LAION-CLAP khi phân phối gói. Gói có thêm bản ONNX của
chính tháp âm thanh ấy (`clap_audio_fp16.onnx`, ~59 MB, cùng trọng số fp16, xuất bằng torch.onnx - Apache-2.0 như model gốc) và
đầu hồi quy A (`student_head_A.npz`) cho đường chạy bằng ONNX Runtime trên máy không có torch.

Căn từng chữ khi đóng gói sách (`webui/word_timing.py`) dùng model nhận dạng tiếng Việt `dragonSwing/wav2vec2-base-vietnamese`
(Apache-2.0; tinh chỉnh từ facebook/wav2vec2-base, Apache-2.0), xuất sang ONNX và lượng tử hoá int8 (~122 MB) bằng onnxruntime; cùng từ
điển ký tự và cấu hình tiền xử lý của model gốc. Gói đăng ở huggingface.co/NGDtuanh/abook-analyzer (thư mục `word-align`), tải về
Studio một lần (bước "wordalign"), KHÔNG nằm trong bộ cài chỉ-nghe. Kèm giấy phép Apache-2.0 và ghi chú của model gốc khi phân phối.

## Giọng đọc của "Nghe ngay" (không đóng gói giọng nào)

- Edge TTS: dịch vụ đọc to trực tuyến của Microsoft Edge (giọng neural vi-VN Hoài My, Nam Minh), gọi thẳng qua WebSocket - không
  thư viện nào được đóng gói. Máy khách viết lại theo giao thức mà dự án mã nguồn mở `edge-tts` (rany2, LGPL-3.0) mô tả; không chép mã
  của dự án ấy (`abook/readaloud/edge.py`, `websocket.py`; Android `readaloud/EdgeTts.kt`, `WebSocket.kt`). Chữ của đoạn đang
  đọc được gửi tới Microsoft; app nói rõ điều này lần đầu dùng.
- Giọng của máy: Windows OneCore (`Windows.Media.SpeechSynthesis`, qua PowerShell) trên máy tính, Android `TextToSpeech` trên điện
  thoại - dùng giọng người dùng đã cài, không phân phối giọng nào.
- Giọng VieNeu (mô-đun tải khi người dùng bấm, `webui/vieneu_module.py`; không nằm trong bộ cài): model VieNeu-TTS v3 Turbo int8 và
  v3 Nano (pnnbao-ump, Apache-2.0) và bộ giải mã MOSS-Audio-Tokenizer-Nano ONNX (OpenMOSS, Apache-2.0) tải thẳng từ Hugging Face (ghim
  commit + SHA-256); hai file giọng có sẵn lấy từ wheel `vieneu` 3.8.1 (Apache-2.0) - chỉ hai file JSON ấy, không cài gói. Phần suy
  luận (`abook/readaloud/vieneu_engine.py`) viết lại theo mã của `vieneu` 3.8.1 (Phạm Nguyễn Ngọc Bảo, Apache-2.0) - ghi nguồn ở đầu
  file. Chữ -> phoneme: wheel `sea-g2p` 0.9.1 (pnnbao97, Apache-2.0) tải cùng mô-đun. Mốc từng chữ dùng lại model căn chữ của Studio
  (mục trên). Khi phân phối: kèm giấy phép Apache-2.0 và ghi chú của các dự án này.

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
