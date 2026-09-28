# Đóng gói app Windows

Chủ sách, 26-09: app Windows **Tauri 2 + NSIS + updater**, **Studio tải thêm khi cần**, một APK mỗi phiên bản. Tài liệu
này là kế hoạch và là chỗ ghi các quyết định; làm tới đâu cập nhật tới đó.

## Vì sao không đóng gói luôn cửa sổ hiện tại

Cửa sổ hiện tại (`desktop.py`) là giao diện web trong Qt WebEngine, chạy bằng runtime đầy đủ của dây chuyền. Đóng gói
nguyên như thế là bắt người chỉ muốn **nghe** sách tải PySide6 + QtWebEngine (~350 MB) cộng torch CUDA, VieNeu, Whisper,
Ollama và model (~15-20 GB). Phần lớn người dùng app nghe, không sản xuất.

Đo 28-09: server giao diện (`webui/`) lúc nạp chỉ cần thư viện chuẩn; khi dùng thì thêm Pillow (bìa), psutil + requests
(các màn Studio đọc sổ nhân vật). Mọi thứ nặng chỉ cần khi **chạy** một cuốn (worker). Nên app chia hai phần:

| phần | gồm | cỡ | khi nào có |
|---|---|---|---|
| **ABook** | vỏ Tauri (WebView2 của Windows) + Python nhúng + `ebook_reader` + giao diện đã build | ~20 MB bộ cài | cài là có |
| **Studio** | venv dây chuyền (torch cu128, VieNeu, Whisper...) + Ollama + model | ~15-20 GB | bấm "Cài Studio" |

Không có Studio vẫn làm được mọi thứ trừ **chạy** sách: nghe, đồng bộ điện thoại, nghe máy tính khác, mở `.abook`, duyệt
kịch bản, sửa người nói/giọng/cách đọc của sách đã có.

## Kiến trúc

```text
ABook.exe (Tauri 2, Rust)
 ├─ chạy: python\pythonw.exe -m ebook_reader.webui.host      (con, không cửa sổ console)
 │    └─ HTTP 127.0.0.1:<cổng ngẫu nhiên>/?t=<token>         = đúng server webui + giao diện hôm nay
 ├─ cửa sổ WebView2 mở địa chỉ ấy
 ├─ một phiên bản: lần mở thứ hai (bấm đúp .abook) chuyển đường dẫn cho cửa sổ đang chạy
 ├─ hộp thoại Windows (chọn thư mục/file) theo yêu cầu của host
 └─ cập nhật: kiểm GitHub Releases, tải gói đã ký, cài, mở lại
```

**Kênh vỏ ↔ host: JSON từng dòng qua stdin/stdout của tiến trình con** - không mở IPC của Tauri cho trang web (trang
nằm ở `http://127.0.0.1`, cấp quyền IPC cho địa chỉ ngoài là mở cửa cho mọi thứ chạy trên cổng ấy). Trang vẫn chỉ nói
chuyện với server Python như hôm nay; server nhờ vỏ những việc chỉ vỏ làm được:

| chiều | thông điệp | nghĩa |
|---|---|---|
| host → vỏ | `{"ready": url}` | server đã nghe, mở cửa sổ ở `url` |
| host → vỏ | `{"dialog": id, "kind": "folder"\|"files"\|"book", "title", "start"}` | mở hộp thoại, trả kết quả |
| vỏ → host | `{"dialog": id, "result": ...}` | đường dẫn đã chọn (hay `null` khi huỷ) |
| vỏ → host | `{"open": path}` | mở file `.abook` (lần mở thứ hai của app) |
| host → vỏ | `{"event": name, "detail": ...}` | vỏ phát CustomEvent vào trang (`abook-opened`...) |
| vỏ → host | `{"update": {version, notes}}` | có bản mới - server đưa vào `/api/state`, trang hiện nút |
| host → vỏ | `{"install_update": true}` | người dùng bấm "Cập nhật" |
| vỏ → host | `{"quit": true}` | đóng cửa sổ: dừng server; stdin đóng (vỏ chết) cũng là thoát |

Hôm nay `desktop.py` làm đúng các việc ấy bằng Qt (`Dialogs`, `claim_single_instance`, `runJavaScript`); `host.py` là
cùng các việc qua ống. Cửa sổ Qt giữ nguyên làm lối lui trong bản dev.

## Studio tải thêm khi cần

- Nơi ở: `%LOCALAPPDATA%\ABook\Studio\` (`runtime\.venv`, `models\`, Ollama). Dữ liệu người dùng ở
  `%LOCALAPPDATA%\ABook\` như bản dev hôm nay (tuỳ chọn, `listening.json`, `devices.json`, `computers.json`...) - gỡ app
  không xoá dữ liệu.
- Cài: màn "Cài Studio" chạy các bước của `scripts/setup_windows.ps1` (uv, venv từ `pyproject.toml` + `uv.lock` đi kèm
  bản cài, torch cu128, FFmpeg, Ollama, kéo model), có tiến độ, làm tiếp được khi mất mạng giữa chừng, không hỏi gì giữa
  lúc chạy. Kiểm GPU trước (không có NVIDIA thì nói thẳng là Studio không chạy được trên máy này).
- Chạy sách: `BackgroundRunner` truyền `python_executable` = `pythonw.exe` của Studio (`start_background` đã nhận tham số
  này).
- **Sách đang làm dở và bản cập nhật.** Đổi một file trong `QUALITY_IMPLEMENTATION_FILES` là sách dở không làm tiếp được
  (AGENTS.md). Nên: (1) bản đầu - có sách dở thì trình cập nhật nói rõ "cuốn X sẽ phải làm lại từ đầu" và để người dùng
  chọn cập nhật ngay hay sau; (2) sau đó - Studio giữ mã của từng phiên bản (`Studio\code\<phiên bản>\`), sách chạy bằng
  đúng mã đã tạo ra nó (khớp theo hash chất lượng), mã cũ xoá khi không còn sách nào cần.

## Cập nhật và ký

- `tauri-plugin-updater`, nguồn `https://github.com/ntanhpro1221/ABook/releases/latest/download/latest.json`.
- Khoá ký cập nhật (minisign) sinh bằng `tauri signer generate`, nằm **ngoài repo** ở `%USERPROFILE%\.abook-keys\`;
  không bao giờ commit, in ra hay gửi đi. Mất khoá = các bản đã cài không tự cập nhật được nữa (phải cài tay) - chủ sách
  cần giữ một bản sao.
- Chưa có chứng chỉ ký mã (Authenticode): lần đầu chạy bộ cài, SmartScreen hiện "Windows đã bảo vệ máy tính" (bấm
  "Thông tin thêm" -> "Vẫn chạy"). Mua chứng chỉ là chi tiền - chủ sách quyết.

## Bộ cài (NSIS)

- Cài cho người dùng hiện tại (`%LOCALAPPDATA%\Programs\ABook`), không cần quyền quản trị.
- Lối tắt Start Menu + màn hình nền "ABook", liên kết `.abook` (thay `register_file_types.ps1` của bản dev), AUMID
  giữ nguyên để Windows+A và thông báo không đổi.
- WebView2: Windows 11 có sẵn; bộ cài tự tải khi thiếu.
- Python nhúng: bản embeddable chính thức mới nhất còn bản vá nhị phân (server đồng bộ nghe cả mạng LAN - cần bản vá bảo
  mật); URL + SHA-256 ghi cứng trong script build. Gói phụ (Pillow, psutil, requests) cài `--require-hashes`.

## Build

`scripts/build_windows_app.ps1`: build giao diện (`ui/`) -> tải + kiểm Python nhúng -> cài gói phụ -> chép `ebook_reader`
(không `__pycache__`, không test) -> `cargo tauri build` (ký gói cập nhật bằng khoá ngoài repo) -> chạy thử bản vừa build
(`ABook.exe --smoke`: host lên, `/api/state` trả lời, thoát). Bộ cài ra `_internal/shell/target/release/bundle/nsis/`.

Công cụ: Rust stable MSVC (rustup, cài 28-09), MSVC C++ (Visual Studio Community 2026 có sẵn), `tauri-cli` 2.x. NSIS do
Tauri tự tải.

## Thứ tự làm

Mỗi bước một commit có test, không bước nào đụng file khoá chất lượng.

1. `webui/host.py` + `PipeDialogs`: host nói giao thức ở trên; test bằng tiến trình con thật và ống.
2. `_internal/shell/` (Tauri 2): chạy host (bản dev: python của runtime + mã nguồn), mở cửa sổ, hộp thoại, một phiên
   bản + chuyển file `.abook`, đóng là thoát sạch (không bỏ lại python).
3. Build + bộ cài NSIS + chạy thử trên máy này (cài vào thư mục riêng, gỡ sạch).
4. Cập nhật: khoá ngoài repo, `latest.json`, thử nâng từ bản cũ lên bản mới qua một server cục bộ.
5. "Cài Studio" + chạy sách bằng Studio; rồi mã theo phiên bản cho sách dở.
6. Phát hành theo `RELEASING.md` (thêm bộ cài + `latest.json` + APK đã ký).
