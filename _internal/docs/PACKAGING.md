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
| **ABook** | vỏ Tauri (WebView2 của Windows) + Python nhúng + `abook` + giao diện đã build | ~20 MB bộ cài | cài là có |
| **Studio** | venv dây chuyền (torch cu128, VieNeu, Whisper...) + Ollama + model | ~15-20 GB | bấm "Cài Studio" |

Không có Studio vẫn làm được mọi thứ trừ **chạy** sách: nghe, đồng bộ điện thoại, nghe máy tính khác, mở `.abook`, duyệt
kịch bản, sửa người nói/giọng/cách đọc của sách đã có.

## Kiến trúc

```text
ABook.exe (Tauri 2, Rust)
 ├─ chạy: python\pythonw.exe -m abook.webui.host      (con, không cửa sổ console)
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

- Nơi ở: `%LOCALAPPDATA%\ABook\Studio\` - MỌI thứ Studio cần nằm trong đó (mục "Tự chứa" dưới). Dữ liệu người dùng ở
  `%LOCALAPPDATA%\ABook\` như bản dev hôm nay (tuỳ chọn, `listening.json`, `devices.json`, `computers.json`...).
- Gỡ app (chủ sách 28-09: "gỡ thì gỡ hết", `shell/src-tauri/windows/hooks.nsh`): LUÔN xoá Studio và bộ nhớ đệm WebView2
  (`%LOCALAPPDATA%\com.ngdtuanh.abook`), dừng trước mọi tiến trình chạy từ hai chỗ ấy và từ thư mục cài (host Python,
  worker, Ollama riêng); dữ liệu cá nhân chỉ xoá khi tích ô "xoá dữ liệu ứng dụng" của bộ gỡ; thư viện sách (thư mục người
  dùng chọn) không bao giờ bị đụng. Bộ gỡ chạy vì bộ cài bản mới "gỡ trước khi cài" (tiến trình ông là `*setup*.exe`)
  thì giữ Studio - nâng cấp không bắt tải lại 13 GB.
- Cài: màn "Cài Studio" chạy các bước của `scripts/setup_windows.ps1` (uv, venv từ `pyproject.toml` + `uv.lock` đi kèm
  bản cài, torch cu128, FFmpeg, Ollama, kéo model), có tiến độ, làm tiếp được khi mất mạng giữa chừng, không hỏi gì giữa
  lúc chạy. Kiểm GPU trước (không có NVIDIA thì nói thẳng là Studio không chạy được trên máy này).
- Chạy sách: `BackgroundRunner` truyền `python_executable` = `pythonw.exe` của Studio (`start_background` đã nhận tham số
  này).
- **Sách đang làm dở và bản cập nhật.** Đổi một file trong `QUALITY_IMPLEMENTATION_FILES` là sách dở không làm tiếp được
  (AGENTS.md). Nên: (1) bản đầu - có sách dở thì trình cập nhật nói rõ "cuốn X sẽ phải làm lại từ đầu" và để người dùng
  chọn cập nhật ngay hay sau; (2) sau đó - Studio giữ mã của từng phiên bản (`Studio\code\<phiên bản>\`), sách chạy bằng
  đúng mã đã tạo ra nó (khớp theo hash chất lượng), mã cũ xoá khi không còn sách nào cần.

### Cài Studio: làm gì, theo thứ tự (chuyển từ `scripts/setup_windows.ps1`)

`setup_windows.ps1` của bản dev cài qua winget (Git, uv, Ollama, FFmpeg) và ghi vào `_internal\runtime`. App đóng gói
không được đụng PATH hay cài gì toàn máy, nên mỗi công cụ là một bản ghim cứng (URL + SHA-256) tải vào
`Studio\tools\`, và mọi bước do host Python làm ở luồng nền (`webui/studio_setup.py`, chưa viết), có tiến độ, làm tiếp
được sau khi mất mạng hay tắt máy (tải có Range, mỗi bước một dấu hoàn tất ghi atomic):

| bước | nguồn | cỡ |
|---|---|---|
| kiểm máy | NVML (`nvml.dll` của driver NVIDIA) - không có GPU NVIDIA thì dừng, nói rõ; ổ đĩa còn ≥ 30 GB | - |
| uv | bản phát hành GitHub của astral-sh/uv, ghim | ~20 MB |
| Python 3.11 + venv | `uv python install` + `uv venv` vào `Studio\runtime\.venv` | ~50 MB |
| thư viện C++ của Microsoft | `msvcp140.dll`, `vcruntime140*.dll`, `concrt140.dll` - bản redist của Visual Studio đi kèm BỘ CÀI app (`resources\app\vcruntime`), chép vào thư mục Python của Studio: Windows tìm DLL ở thư mục của exe trước System32, nên máy chưa cài "Visual C++ Redistributable" vẫn chạy được torch | ~2 MB |
| thư viện | `uv pip sync` từ danh sách khoá sinh từ `uv.lock` (torch cu128 từ index của PyTorch) | ~6 GB |
| UTMOSv2 | đúng commit đã khoá, cài từ git: `runtime_contract` đòi `direct_url.json` có `vcs_info.commit_id` (không giả được bằng bản lưu trữ) -> MinGit (bản Git nhúng chính thức của Git for Windows) ghim vào `Studio\tools\git` | ~40 MB |
| FFmpeg | bản dựng ghim | ~100 MB |
| Ollama | `ollama-windows-amd64.zip` ghim ĐÚNG bản dây chuyền đã đo (0.33.2 - bản 0.34.4 cho qwen3 "suy nghĩ" và làm hỏng cuốn thử 28-09) vào `Studio\tools\ollama`, LUÔN bản riêng kể cả khi máy đã có Ollama: chạy ẩn ở cổng 11439 (`OLLAMA_HOST`), model ở `Studio\runtime\models\ollama` (`OLLAMA_MODELS`), `USERPROFILE` = `Studio\ollama-home` nên không ghi `%USERPROFILE%\.ollama`; sách tạo từ app mang `analysis.base_url` = cổng ấy (`StudioSetup.settings_overrides`) | ~1,5 GB |
| model | LLM phân tích (qua Ollama), VieNeu, Whisper turbo + faster-whisper, UTMOSv2 + wav2vec2 + timm (revision khoá) | ~10 GB |
| kiểm tra | `check_system.py`, dấu `.setup_complete` như bản dev | - |

**Studio cũ hơn app.** Mỗi bước tải (uv, Git, Ollama, model phân tích) ghi lại bản ghim đã cài vào `setup.json`; app lên
bản mới đổi ghim thì bước ấy thành "cần cập nhật" (`StudioSetup.outdated`): sách không chạy bằng bản cũ, thẻ "Cập nhật
Studio" ở màn Dự án chạy lại đúng các bước ấy rồi "Kiểm tra lần cuối" - không tải lại thư viện hay model khác. Thử thật 28-09
trên Studio cài từ mã chưa ghi ghim: nhận ra 4 bước cũ, tải Ollama 0.33.2 thay bản 0.34.4 đang chạy (dừng nó trước), 3 phút.

Worker chạy bằng `Studio\runtime\.venv\Scripts\pythonw.exe`, mã lấy từ thư mục `app` của bản cài (PYTHONPATH),
`ABOOK_RUNTIME=Studio\runtime`. Hash chất lượng tính trên đúng các file ấy (kể cả `pyproject.toml` + `uv.lock`
chép vào `app`) - nên cập nhật app đổi file khoá là sách dở không làm tiếp được: xem mục dưới.

### Tự chứa: không dựa vào thứ gì cài sẵn trên máy (kiểm 28-09)

Chủ sách 28-09: "tất tần tận mọi thứ cần thiết khi bấm nút tải Studio" nằm trong app, và app không có Studio cũng không
được cần gì của máy. Đo bằng danh sách DLL mỗi tiến trình đã nạp (`psutil` `memory_maps`):

| phần | phụ thuộc ngoài app | ghi chú |
|---|---|---|
| app không Studio (vỏ Tauri + host Python nhúng) | WebView2 Runtime | thành phần của Windows 11; máy thiếu (Windows 10 cũ) thì bộ cài tự tải bản Evergreen. Ngoài nó 0 DLL từ ngoài thư mục cài và `C:\Windows` |
| Studio | driver NVIDIA (`nvcuda.dll`, `nvml.dll`) | phần cứng, không đóng gói được; Studio kiểm GPU trước khi cài. Mọi DLL khác nạp từ `Studio\` |

Trước 28-09 Studio còn mượn ba thứ của máy, giờ đều là bản riêng: `msvcp140.dll`/`vcruntime140*.dll` nạp từ System32
(của gói Visual C++ Redistributable, Windows sạch không có) -> chép kèm; Ollama của máy (`%LOCALAPPDATA%\Programs\Ollama`)
được dùng lại nếu có, model kéo vào `%USERPROFILE%\.ollama` -> bản riêng, cổng riêng; Python cài sẵn -> `only-managed`.
Phần còn lại vốn đã riêng: Git là MinGit trong `Studio\tools\git`, FFmpeg là bản trong gói `imageio-ffmpeg`, CUDA/cuDNN
là thư viện trong venv (`torch\lib`, `ctranslate2`; máy thử không cài CUDA toolkit), bộ nhớ đệm uv/Hugging Face/torch trỏ
vào `Studio\`. Thử gỡ trên bộ cài thật (`/S`): gỡ thật -> Studio, WebView2 cache, khoá gỡ cài đặt, liên kết `.abook` mất,
dữ liệu cá nhân còn; gỡ lúc cài lại -> Studio còn.

Ngoài DLL còn FILE: chạy trọn một cuốn bằng Studio rồi so ảnh chụp các chỗ hay bị ghi rác (`%USERPROFILE%`, `.cache`,
`.ollama`, `AppData`, Temp). Lần đầu lộ `%APPDATA%\NVIDIA\ComputeCache` (bộ nhớ đệm JIT của driver CUDA, 21 mục) -> biến
`CUDA_CACHE_PATH` trỏ vào `Studio\cache\nvidia`; lần hai: 0 mục ngoài, 68 mục trong Studio. Phần còn lại đổi trong lúc chạy
là của app khác (DXCache của DirectX, `cv_debug.log` của Edge, ba file `*.tmp` tên GUID vẫn bị giữ sau khi dừng mọi tiến
trình Studio). Còn hở một chỗ hiếm: Ollama riêng chết giữa cuốn thì dây chuyền tự bật lại nó (`analysis.py`, file khoá)
bằng `USERPROFILE` của người dùng - Ollama tạo khoá định danh ở `~/.ollama` (2 file nhỏ); sửa cùng lần đổi `analysis.py`
kế tiếp.

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

`scripts/build_windows_app.ps1`: build giao diện (`ui/`) -> tải + kiểm Python nhúng -> cài gói phụ -> chép `abook`
(không `__pycache__`, không test) + VC++ runtime (tìm bằng `vswhere`, cho Studio) -> chạy thử host -> `tauri build
--no-bundle`, chờ tới khi không ai giữ `ABook.exe`, rồi `tauri bundle` (ký gói cập nhật bằng khoá ngoài repo). Tách hai
bước vì bước đóng gói ghi vào exe vừa dựng và đụng trình diệt virus đang quét nó (os error 32; 28-09 `tauri build` thử lại
3 lần hỏng cả 3 - mỗi lần thử lại dựng lại exe). Bộ cài ra `_internal/shell/src-tauri/target/release/bundle/nsis/`.

Công cụ: Rust stable MSVC (rustup, cài 28-09), MSVC C++ (Visual Studio Community 2026 có sẵn), `tauri-cli` 2.x. NSIS do
Tauri tự tải.

## Thứ tự làm

Mỗi bước một commit có test, không bước nào đụng file khoá chất lượng.

1. XONG 28-09 - `webui/host.py` + `PipeDialogs`: host nói giao thức ở trên; test bằng tiến trình con thật và ống
   (`tests/test_webui_host.py`).
2. XONG 28-09 - `_internal/shell/` (Tauri 2.12): chạy host (bản dev: `ABOOK_HOST_PYTHON` + `ABOOK_HOST_APP`, hay python
   của runtime cạnh mã nguồn), mở cửa sổ, hộp thoại, một phiên bản + chuyển file `.abook`, đóng là thoát sạch.
3. XONG 28-09 - `scripts/build_windows_app.ps1`: bộ cài 28 MB (tài nguyên 69 MB chưa nén; Qt sẽ là ~350 MB). Đã thử
   trên máy này bằng bản release: Python nhúng 3.14.7 chạy host, WebView2 hiện thư viện, hộp thoại gốc có chủ là cửa
   sổ ABook (huỷ -> `null`), lần mở thứ hai thoát ngay và chuyển file `.abook`, đóng cửa sổ -> host thoát. RAM: vỏ
   ~28 MB + host ~31 MB (+ tiến trình WebView2).
4. XONG 28-09 - cập nhật: khoá minisign ở `%USERPROFILE%\.abook-keys` (ACL chỉ chủ máy), script dựng ký gói và sinh
   `latest.json`. Thử trọn trên máy này: cài 0.1.0 (NSIS `/S /D=`), server cục bộ phục vụ 0.1.1, app hiện "Có ABook
   0.1.1" ở thanh bên + mục Cập nhật, bấm -> vỏ tải + kiểm chữ ký -> dừng host -> bộ cài passive ghi đè cả Python nhúng
   -> app tự mở lại ở 0.1.1; gỡ sạch (thư mục, khoá gỡ cài đặt, liên kết `.abook`). Bản thử bật
   `dangerousInsecureTransportProtocol` bằng `-TauriConfig <file>`; bản phát hành chỉ https. Lỗi của mẫu NSIS Tauri
   tìm ra khi thử: cập nhật cài đè làm bản sao lưu liên kết `.abook` trỏ vào chính ABook, gỡ xong còn liên kết treo ->
   `shell/src-tauri/windows/hooks.nsh`.
5. ĐANG LÀM 28-09 - "Cài Studio" (`webui/studio_setup.py`, thẻ ở màn Dự án `ui/src/studio/StudioSetup.tsx`) + chạy
   sách bằng Studio (`actions.StudioRunner`) + mã theo phiên bản cho sách dở (`StudioSetup.code_for`: lần chạy đầu
   chép mã app vào `Studio\code\<hash chất lượng>`, ghi `studio_code.json` vào dự án; cập nhật app không làm hỏng
   sách dở). Thư viện: `shell/python/studio-requirements.txt` sinh bằng `scripts/freeze_studio_requirements.py` từ
   runtime dev (165 gói, `pip freeze --all`, bỏ PySide6 + công cụ dev), cài `--no-deps`. Thử cài thật vào thư mục thử:
   uv + MinGit 5 giây, thư viện 135 giây (mạng nhanh). Hai lỗi tìm ra khi cài thật: `uv venv --seed` cài setuptools mới
   nhất mà torch đòi <82 (bỏ `--seed`, ghim theo runtime dev); huggingface_hub 1.29 dò symlink có tranh chấp giữa các
   luồng tải -> WinError 1314 trên máy không bật Developer Mode (`HF_HUB_DISABLE_SYMLINKS=1`). `pip check` chỉ ghi
   nhật ký: chính runtime làm ra sách cũng có xung đột khai báo vô hại (datasets khai fsspec cũ).
6. Phát hành theo `RELEASING.md` (thêm bộ cài + `latest.json` + APK đã ký).

## Mẹo thử

- Nhìn trang trong cửa sổ vỏ mà không cần điều khiển màn hình: đặt `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=
  --remote-debugging-port=9333` trước khi mở `ABook.exe`, rồi dùng CDP (`/json/list`, `Runtime.evaluate`,
  `Page.captureScreenshot`).
- Đóng cửa sổ bằng WM_CLOSE: gửi vào cửa sổ lớp `Tauri Window`. `Process.MainWindowHandle` của .NET hay trỏ nhầm vào
  cửa sổ ẩn `Tao Thread Event Target` - đóng "không ăn" là do phép thử, không phải app.
- Dữ liệu thử: `ABOOK_PREFERENCES=<thư mục tạm>\preferences.json` (host chuyển cho server), `ABOOK_FAKE_RUNNER=1`
  (không khởi động worker thật), `ABOOK_UPDATE_URL=<latest.json cục bộ>`.
