# Bộ cài cho app máy tính Qt (ABookDesk) - đặc tả và thứ tự

Mục tiêu: bản phát hành Windows dùng app Qt (`desktop_qt/`, ABookDesk.exe) thay vỏ Tauri (`shell/`), làm được đủ những việc
vỏ Tauri đang làm hộ. Không có tính năng mới cho người dùng; người dùng thấy cùng một bộ cài, cùng nơi cài, cùng cách cập nhật.
Lead giao 31-10 (sau bản 0.4.149 vẫn là Tauri + APK native). Làm từng mục theo thứ tự dưới, mỗi mục có test riêng, không mục
nào phát hành một mình.

## Hiện trạng (int150)

- `desktop_qt/build.bat` ra thư mục `dist/`: ABookDesk.exe + DLL Qt (windeployqt) + VC runtime app-local + licenses, chạy
  `tools/smoke_dist.py`. 92 MB chưa nén, gồm cả các style Qt Quick Controls không dùng (Material, Imagine, Fusion,
  Universal, FluentWinUI3).
- `Backend` đã biết đường của bản cài (backend.cpp:86-157): `resources/python/pythonw.exe` + `resources/app` cạnh exe; Studio
  tải thêm vào `%LOCALAPPDATA%\ABook\Studio` (ABOOK_RUNTIME).
- Tự cập nhật: `CheckUpdate` trả "không có bộ cập nhật" (`HostMessage::updateCheckedWithoutUpdater`), `InstallUpdate` không
  làm gì. Giao diện `AdvancedUpdate.qml` đã có ("ABook X đã có", "Cập nhật ABook", "Kiểm tra bản mới").
- Không đọc đường file trên dòng lệnh, không có "một phiên bản chạy", không liên kết `.abook` / `.abookproj`.
- Vỏ Tauri làm những việc ấy bằng: `scripts/build_windows_app.ps1` (Python nhúng + app + `npx tauri bundle` NSIS + `latest.json`),
  `shell/src-tauri/tauri.conf.json` (updater minisign, fileAssociations, NSIS currentUser tiếng Việt),
  `shell/src-tauri/windows/` (hooks.nsh, stop_processes.ps1, uninstall_guard.ps1, upgrade_mode.ps1),
  tauri_plugin_single_instance / updater / window_state / dialog.

## Đo trước khi đổi (31-10, bằng chứng cho việc đổi vỏ)

Hai bố cục đúng như bộ cài đặt ra đĩa, cùng một Python nhúng (3.14 của `shell/src-tauri/resources/python`):
- Tauri = `ABook.exe` 0.4.133 (ABook_rel437) + `resources/{python,app}` thật.
- Qt = dist của int150 17f8a33c + `resources/python` + `resources/app` (mã `abook` của int150, luật `Copy-App`).

Mỗi lượt: hồ sơ giả mới (`LOCALAPPDATA` / `APPDATA` / `USERPROFILE`), cửa sổ thật (không offscreen) trên desktop riêng, bộ canh
tiêu điểm. 3 vòng xen kẽ thứ tự, mỗi vòng một lần mở đầu (hồ sơ trống) và một lần mở lại (cùng hồ sơ). Máy nghỉ, đang cắm
sạc. Kịch bản: `desktop_qt/tools/prep_shells.py` (dựng hai bố cục) + `tools/measure_shells.py`. Qua cả 12 lượt: 0 lần cướp tiêu điểm, 0 tiến trình sót lại.

| | Tauri | Qt (chưa cắt) |
|---|---|---|
| Bộ cài nén | **20,1 MB** (0.4.148 thật; LZMA bố cục 19,4) | **≈ 39 MB** (LZMA bố cục 38,2 + NSIS ~0,7) |
| Trên đĩa sau khi cài | 65,9 MB (+ WebView2 của hệ thống) | 152,8 MB |
| RAM nghỉ, USS, giao diện (25-40 s) | 113-119 MB (ABook.exe + msedgewebview2) | **76 MB** (ABookDesk.exe) |
| RAM nghỉ, USS, host Python | 58-65 MB | 50-54 MB |
| RAM nghỉ, private bytes, giao diện | 260-279 MB | 152-154 MB |
| Cửa sổ đầu tiên (lần đầu / mở lại) | 261 / 264 ms (khung trống, trang web vẽ sau) | 1048 / 784 ms (đã có nội dung QML) |
| Lắng xuống (CPU cả cây < 5 % một nhân trong 2 s) | 4,5 / 3,6 s | 5,4 / 3,0 s |

Đọc bảng:
- Qt **nhẹ RAM hơn rõ**: giao diện −35 % USS, −42 % private; cả cây −27 % USS. Mở lại thì lắng nhanh hơn 0,6 s.
- Qt **nặng tải hơn gần gấp đôi**: +19 MB mỗi lần cài hay cập nhật. Tauri mượn WebView2 có sẵn trong Windows, còn Qt mang DLL
  riêng.
- Ở lần mở đầu, Qt lắng chậm hơn 0,9 s. **Đo lại bên dưới: đó là lệch cách đo; khi cả hai vừa cài thì Qt 5,18 s <= Tauri 5,25 s.**
- "Cửa sổ đầu tiên" của Tauri là khung trống trước khi WebView vẽ, nên không so trực tiếp được với Qt (vẽ xong mới hiện).
  Số so được là "lắng xuống".
- Cắt được ở Q1:
  - Style Qt Quick Controls không dùng (app chỉ import `Controls.Basic`): Fluent 5,5 + Imagine 3,3 + Material 2,4 + Universal
    1,8 + Fusion 1,8 + Windows / NativeStyle 1,6 MB thô = 16,6 MB thô, chỉ **2,6 MB nén**.
  - `Qt6Widgets.dll` 6,6 MB thô (~2,5 nén), nếu `Qt.labs.platform` chạy được với QGuiApplication mà không có nó (phải kiểm
    bằng smoke).
  - Đích sau khi cắt: ≈ 34-36 MB nén.

### Cỡ bộ cài, từng MB có lý do (31-10, sau Q6)
Lead hỏi: 10 file lớn nhất, cái nào bỏ được, số trước/sau. NSIS nén LZMA **solid** cả gói, nên cỡ thô và cỡ "nén riêng
từng file" không cộng được; mỗi phần dưới đây đo bằng cách dựng lại bộ cài thật không có phần ấy (`makensis` cùng
cờ, mốc 35,30 MiB = bộ cài 0.4.150 của nhánh). Mười file lớn nhất (thô / LZMA riêng, MB):

| File | Thô | Nén | Vì sao giữ |
|---|---|---|---|
| ABookDesk.exe | 17,6 | 3,1 | QML biên dịch trước (AOT) vào exe: mở nhanh, không có JIT lúc chạy |
| Qt6Core.dll | 9,8 | 2,4 | lõi Qt |
| Qt6Gui.dll | 9,1 | 3,0 | vẽ, font, ảnh |
| python314.zip | 7,7 | 2,1 | thư viện chuẩn của Python nhúng (host) |
| python314.dll | 6,5 | 2,0 | Python nhúng |
| Qt6Widgets.dll | 6,3 | 2,2 | chỉ `Qt.labs.platform` (SystemTrayIcon của khay) kéo theo |
| Qt6Quick.dll | 6,2 | 2,1 | Qt Quick |
| libcrypto-3.dll | 5,7 | 1,6 | OpenSSL của Python: https tới trang phát hành, tải nhạc, đồng bộ |
| Qt6Qml.dll | 5,1 | 1,5 | QML engine |
| Qt6QuickDialogs2QuickImpl.dll | 2,7 | 0,5 | hộp chọn file / thư mục |

Theo nhóm (thô / nén riêng): Qt + CRT 55,9 / 16,4; `resources/app` 25,1 / 9,8; `resources/python` 33,5 / 10,4.

Đã cắt (`tools/trim_dist.py`, `build.bat`, `abook.nsi`), số là phần bộ cài nhỏ đi khi bỏ riêng phần ấy:
- VC runtime chỉ còn 5 DLL có binary import (bỏ concrt140, vccorlib140, msvcp140_atomic_wait, msvcp140_codecvt_ids,
  vcruntime140_threads): 0,06 MiB. `tools/check_imports.py` đọc bảng import + delay-import của mọi exe/dll/pyd và làm
  hỏng bản dựng nếu một binary cần DLL redist không có cạnh nó (máy dựng có VC++ trong System32 nên smoke không bắt được).
- Style Qt Quick Controls không dùng + biến thể `+Style` của Dialogs: 0,07 MiB (phần lớn đã cắt ở Q1).
- `tls\` + `networkinformation\`: 0,09 MiB - mọi yêu cầu của phía C++ là http://127.0.0.1 tới host.
- QtQuick.Effects (+ Qt6QuickEffects.dll): 0,29 MiB - chỉ các style đã bỏ import nó.
- Cộng bốn mục an toàn: **0,53 MiB** (solid nén nên nhỏ).
- `.pyc` không chở trong gói, biên dịch lúc cài (`compileall -j 0`, ~0,7 s cho ~250 file; bộ gỡ xoá cả `resources\`):
  **2,57 MiB**. test_installer đòi mỗi .py của `abook` có đúng một .pyc sau khi cài.
- **Đo lại cả gói sau khi cắt: 32,21 MiB (33.772.115 byte), từ 35,30 MiB = −3,10 MiB**, đúng tổng hai dòng trên.
  Trên đĩa sau khi cài: 122 MB (EstimatedSize của khoá gỡ cài).

Không cắt, có lý do:
- Qt6Widgets qua khay Win32 tự viết (Shell_NotifyIcon thay `Qt.labs.platform`): 2,24 MiB - phải viết lại khay bằng C++,
  đề xuất cho Lead, chưa làm.
- `webui/static` (0,81 MiB): host vẫn phục vụ trang web cho iPhone/iPad qua LAN (sync.py) và Studio trong trình duyệt
  (remote_studio.py).
- `vcruntime140*.dll` trùng trong `resources/app`: 0,00 MiB (solid nén bỏ được bản trùng).
- AOT trong exe: giữ vì mở nhanh; có thể đo `--only-bytecode` nếu Lead muốn đổi ~2 MB lấy thời gian mở.

### Mở lần đầu, đo lại (31-10, sau Q1)

Câu hỏi: lần mở đầu Qt 5,4 s > Tauri 4,5 s ở trên là do đâu (host Python, cache QML, nạp DLL/plugin)?

**Bảng trên lệch vì cách đo, không phải vì Qt.**
- Lần đo ấy dùng MỘT bố cục cho mọi vòng. Bố cục Tauri là bản đã từng chạy, còn bố cục Qt vừa chép mới.
- Vì vậy chỉ lần mở đầu của vòng 1 là nguội thật. Qt mở đầu theo vòng là 7,2 / 5,4 / 2,75 s, và ở vòng 3 thì mở đầu
  bằng mở lại (2,73 s).
- Hồ sơ mới chỉ thêm 64 KB DXCache của driver. Không có cache QML nào (0 file `.qmlc`): QML đã biên dịch sẵn vào exe
  (`qt_add_qml_module`, qmlcachegen).
- Cache pipeline của Qt Quick (`qtpipelinecache-*`) có thư mục nhưng rỗng: app bị dừng lúc hết lượt đo, không thoát êm,
  nên không ghi.

Đo lại bằng `measure_shells.py --fresh-install`: mỗi lần mở đầu chạy từ một bản chép MỚI của bố cục, đúng như ngay sau khi
cài hay cập nhật (file chưa từng mở, Defender quét, cache đĩa trống). Qt là dist của Q1 (đã cắt, 131,9 MB). 3 vòng, xen kẽ
thứ tự, 0 lần cướp tiêu điểm. Ngoài thời gian, đo CPU tới lúc lắng của từng phần: giao diện, host Python, tiến trình con
khác, và Defender (`MsMpEng.exe`, chỉ đọc).

| trung vị 3 vòng | Qt mở đầu | Qt mở lại | Tauri mở đầu | Tauri mở lại |
|---|---|---|---|---|
| Lắng xuống | **5,18 s** | **2,78 s** | 5,25 s | 3,64 s |
| CPU giao diện | 1,47 s | 1,09 s | 0,14 s | 0,11 s |
| CPU host Python | 2,41 s | 2,61 s | 2,70 s | 2,70 s |
| CPU con khác (msedgewebview2...) | 0,42 s | 0,34 s | 2,70 s | 2,64 s |
| CPU Defender cùng quãng | **6,59 s** | 3,47 s | 6,75 s | 3,02 s |

Theo từng vòng ghép đôi, Qt mở đầu nhanh hơn Tauri cả 3 lần: 5,48 / 5,83, 5,18 / 5,25, 4,91 / 5,24 s. **Qt <= Tauri đã đạt**,
không cần sửa gì thêm cho mục này.

Phần chiếm của lần mở đầu (Qt):
- **Defender**: 6,6 s CPU so với 3,5 s khi mở lại. Chênh lớn nhất là quét DLL mới. Tauri chịu y như vậy (6,75 s).
- **Host Python**: 2,4 s, ngang nhau giữa mở đầu và mở lại, ngang Tauri. Cùng mã, cùng Python, `.pyc` đã có sẵn
  (`compileall` trong `Copy-App`).
- **Nạp DLL / plugin nguội**: +0,4 s CPU giao diện (1,47 so với 1,09).
- **Cache QML**: 0, vì không có.

Chưa làm: cache pipeline dựng sẵn để ship kèm (`QQuickGraphicsConfiguration::setPipelineCacheLoadFile`; với D3D11 là
bytecode HLSL, không phụ thuộc card). Lợi tối đa là phần của 0,4 s CPU giao diện nguội, nên để sau.

## Quyết định chung

- **Cùng chỗ với bản Tauri:** cài cho người dùng hiện tại (không cần quyền quản trị), cùng thư mục cài, cùng khoá gỡ cài trong
  registry, cùng ProgId (`ABook`, `ABook.Project`), cùng mime (`application/vnd.ngdtuanh.abook+zip`,
  `application/vnd.ngdtuanh.abookproj+zip`), cùng `latest.json` ở `releases/latest/download/latest.json`.
  - Lý do: một bản cài đè lên bản kia là xong, không cần đoạn mã chuyển đổi nào (luật không migrate).
  - Tên file bộ cài giữ `ABook_<ver>_x64-setup.exe`, nên `release.py` chỉ đổi bước dựng.
- **NSIS** (makensis có sẵn ở `%LOCALAPPDATA%\tauri\NSIS\Bin`, cùng bản Tauri dùng). Kịch bản riêng
  `desktop_qt/installer/abook.nsi`, dùng MUI2, chỉ tiếng Việt. Móc gỡ/nâng cấp chép logic của `shell/src-tauri/windows/`
  (đọc lại từng nhánh và test lại, không gọi file của shell/).
- **Ký:** như Tauri hôm nay. Bộ cài không ký Authenticode; `.sig` minisign (khoá `ABOOK_SIGNING_KEY` hiện có, khoá công khai
  trong tauri.conf.json) cho bộ cập nhật. Ký Authenticode là việc riêng, cần chứng chỉ.
- **Kiểm chữ ký cập nhật ở máy chủ Python**, không viết lại Ed25519 bằng C++: `abook/webui/ed25519_verify.py` đã có (danh mục
  nhạc dùng). Chữ ký minisign của Tauri là Ed25519 trên BLAKE2b-512 của file (thuật toán "ED"); `hashlib.blake2b` có sẵn.
- **Không có cửa sổ nào lên màn hình khi test:** mọi test bộ cài chạy cài im lặng (`/S`) vào thư mục tạm với
  `LOCALAPPDATA` / `APPDATA` / `USERPROFILE` riêng (`desktop_qt/tools/private_profile.py`); app đã cài chạy trên desktop riêng
  không bao giờ chuyển tới (`tools/windows_process.py` + bộ canh tiêu điểm của `guarded_process.py`).
- **Không test nào đụng registry hay thư mục cài thật của chủ máy** (Lead 31-10). Cướp liên kết `.abook` của người dùng là sự
  cố, không phải lỗi test.
  - Kịch bản NSIS đọc gốc registry từ một hằng: bản phát hành là `Software\Classes` và khoá gỡ cài thật. Bản dựng cho test
    (`makensis /DABOOK_TEST_ROOT=Software\ABookTest-<uuid>`) ghi mọi khoá dưới `HKCU\Software\ABookTest-<uuid>\...`.
  - Lệnh nào không đổi gốc được (vd `SHChangeNotify`) thì không chạy trong bản test. Phần ấy kiểm bằng đọc kịch bản, không
    bằng chạy.
  - Test tạo khoá con có tiền tố test và dọn nó trong `finally`, kể cả khi hỏng.
  - Một test chụp `HKCU\Software\Classes\.abook`, `.abookproj`, `ABook`, `ABook.Project` và khoá gỡ cài của ABook (đệ quy,
    mọi giá trị) TRƯỚC và SAU cả bộ test bộ cài. Khác một byte là đỏ.
  - Thư mục cài trong test luôn là thư mục tạm (`/D=`). Test từ chối chạy nếu `/D` trỏ vào thư mục cài thật hay
    `%LOCALAPPDATA%\ABook` của chủ máy.

## Thứ tự

### Q1. Tài nguyên Python + app trong dist
- Tách `Build-Python` / `Copy-App` / `Remove-UnusedFromPython` / `Test-Python` / `Test-Host` của `build_windows_app.ps1` ra
  một file dùng chung (`scripts/windows_resources.ps1`). Bản Tauri và bản Qt cùng gọi, nên hai bộ cài mang đúng một bộ Python.
- `desktop_qt/build.bat package` thêm bước dựng `dist/resources/{python,app}`. Bản dev không đổi.
- Cắt các style Qt Quick Controls không dùng (windeployqt `--skip-plugin-types` hoặc xoá theo danh sách có kiểm). Đo cỡ
  trước và sau từng bước (`optional-runtime-on-demand`: đo cỡ mỗi phụ thuộc).
- Test: `smoke_dist.py` chạy exe đóng gói KHÔNG có `_internal` bên cạnh (chép dist sang thư mục tạm) -> host Ready từ
  `resources/`, mở Thư viện, phát một clip giả. Thêm `tools/smoke_packaged.py`.
- **Đã làm (31-10):**
  - `scripts/windows_resources.ps1` dùng chung. Bản Tauri (`build_windows_app.ps1 -SkipUi -SkipBundle`) vẫn "host OK".
    `resources/python` của hai bản: 284 file, giống từng byte, trừ dòng `bin/idna.exe` trong RECORD (pip sinh ra, nằm
    ngoài thư mục đóng gói).
  - `build.bat package` (`tools/build_hidden.py <nhãn> --package`) gọi `scripts/build_windows_qt.ps1`.
  - `main.cpp` ép style `Basic` (Qt 6.8+ mặc định FluentWinUI3 trên Windows 11). `tools/trim_dist.py` xoá 6 style kia và
    từ chối nếu QML của app import chúng: dist không tài nguyên 91,6 -> 75,0 MB thô. Có `resources` thì 131,9 MB thô.
  - `ABOOK_SMOKE_EXIT=host`: chờ khung đầu tiên VÀ `Backend::Ready`. Host hỏng thì in `SMOKE_HOST_FAILED`, thoát mã 5.
    `tools/smoke_packaged.py` chép dist sang thư mục tạm không có cây nguồn phía trên, đòi pythonw của host nằm trong
    `resources/python` của bản chép. Kiểm âm: bỏ `server.py` khỏi bản chép -> đỏ.
  - `Qt6Widgets.dll` ở lại vì `Qt.labs.platform` (khay) kéo nó vào. Lead chấp nhận 31-10.
  - **Phát thử (31-10, `ABOOK_SMOKE_EXIT=play` + `tools/smoke_play.py`):**
    - Cuốn thử là `python_v4.abook` với chương 1 thay bằng mp3 thật: sine 440 Hz, 6 s, ffmpeg dựng. mp3 trong fixture chỉ
      là byte giả, ffmpeg không mở được. Nhạc nền bỏ đi để nhạc không che giọng.
    - Cuốn ấy nhập vào `<thư viện>/Sách đã nhập/` bằng `BookFile.extract`, như khi người dùng nhập file.
    - App chạy: host Ready, rồi Thư viện tải xong (có ít nhất 1 cuốn; rỗng thì mã 7), rồi `Player.playBook(cuốn đầu)`.
      Giọng (`AudioOut` của Player) phát quá 2 s thì mã 0. `AudioOut::failed` hay `Player.error` thì mã 6.
    - Tai là `ABOOK_AUDIO_SINK` (`src/filesinkdevice.h`): bộ trộn ghi WAV thay vì ra loa, nên âm thanh đi thật qua host
      của bản đóng gói, Media Foundation và bộ trộn, chỉ thiếu thiết bị WASAPI. WAV phải có ≥ 1,5 s tiếng, tần số trội
      440 ± 5 Hz.
    - Kiểm âm, hai lớp:
      - `smoke_play.selftest()`: bộ soi phải bắt được file lặng, sai tần số (220 Hz), quá ngắn, quá nhỏ.
      - Chạy lại với chương là byte rác (mã băm khớp nên vẫn nhập được): lần ấy phải KHÔNG qua.
    - Kết quả lần đầu chạy:
      `SMOKE_LIBRARY 1 book(s), 1 row(s)` -> `SMOKE_PLAYED 2.02 s`, nghe 2,6 s ở 440 Hz.
      Chương rác: `SMOKE_PLAY_FAILED Chapter is not a supported MP3 file`, mã 6, tai 0 s.
      Cả `smoke_packaged` 12 s.

### Q2. Bộ cài NSIS
- `desktop_qt/installer/abook.nsi`: chép `dist/` vào thư mục cài của bản Tauri; lối tắt Start menu (+ màn hình nền nếu bản
  Tauri có); khoá gỡ cài (DisplayName, DisplayVersion, Publisher "ABook", icon, EstimatedSize); trang chào và trang xong
  tiếng Việt; chế độ `/P` (passive, cho bộ cập nhật) và `/S`.
- `build.bat installer <ver>` (hay `scripts/build_windows_qt.ps1`): makensis, rồi minisign `.sig`, rồi `latest.json` (chung
  hàm `Write-LatestJson`).
- Test: cài im lặng vào thư mục tạm -> file đủ, khoá gỡ cài đúng -> chạy exe đã cài (offscreen) Ready -> gỡ im lặng -> thư mục
  và khoá sạch. Cài đè một bản giả cũ hơn.
- **Đã làm (31-10):** `desktop_qt/installer/` (abook.nsi, files.py, stop_processes.ps1, minisign_verify.py),
  `build.bat installer` / `build_windows_qt.ps1 -Installer`, test `desktop_qt/tools/test_installer.py`.
  - **Tên exe đã cài là `ABook.exe`** (đổi từ ABookDesk.exe lúc cài). Lối tắt, liên kết file, `MainBinaryName` và mọi chỗ
    đọc đường exe của bản Tauri vẫn đúng; cài Qt đè Tauri chỉ thay exe.
  - **Gỡ theo danh sách.** `$INSTDIR` = `%LOCALAPPDATA%\ABook`, cũng là cha của Studio và dữ liệu người dùng.
    - `files.py` sinh danh sách cài và gỡ từ cùng một lần duyệt dist. Bộ gỡ xoá từng file, rồi `RMDir` không `/r` từ sâu lên
      nông.
    - Riêng `resources\` toàn của app nên xoá cả cây, cả khi cài (file thừa của bản cũ, kể cả bản Tauri, không ở lại). Trước
      khi xoá, kiểm nó không phải junction.
  - Trước khi chép, dừng `ABook.exe` của thư mục cài và mọi tiến trình chạy từ `resources\`, theo đường exe, không theo tên.
    Giao diện đầy đủ thì hỏi trước; `/P` và `/S` thì dừng luôn. Không dừng cả `$INSTDIR`: worker Studio sống ở đó.
  - **Lối tắt** Start + màn hình nền mang AUMID `ABook.Desktop`, đúng ID app Qt tự đặt (`mediacontrols.cpp`).
    - Lối tắt hay ghim thanh tác vụ đang trỏ vào exe đã cài (kể cả của bản Tauri, có AUMID `com.ngdtuanh.abook`) được đặt lại
      AUMID ở mọi lần cài, để cửa sổ Qt gộp vào ghim cũ.
    - Ghim không bao giờ được tạo hay xoá: nó là của người dùng.
    - `/UPDATE` và `/NS` không tạo lại lối tắt người dùng đã xoá.
  - `EstimatedSize` = cỡ các file đã cài (files.py), không phải `GetSize $INSTDIR` như bản Tauri (con số ấy tính cả Studio).
  - Gỡ thật thì xoá luôn giá trị "chỗ cài" ở `Software\ABook\ABook`, để lần cài sau về chỗ mặc định. Bản Tauri chỉ xoá khi
    tích ô xoá dữ liệu.
  - Bản Tauri không ghi mime và không gọi `SHChangeNotify`, nên bản test không phải bỏ lệnh nào vì lý do ấy. Những gì bản test
    bỏ: bỏ ghim Start và xoá jump list (trạng thái chung của shell). Lối tắt lấy thư mục từ `%ABOOK_TEST_SHELL%`.
  - Đặt tên khi dựng: makensis cảnh báo 9000 với tên `setup.exe` (Windows nạp shim tương thích), nên dựng dưới tên trung tính
    rồi mới đổi sang `ABook_<ver>_x64-setup.exe`, như Tauri.
  - **Ký:** `npx tauri signer sign --app-version <ver>`, cùng khoá. Trusted comment mang `version:<ver>` như chữ ký của
    `tauri bundle`. `minisign_verify.py --version` kiểm bằng khoá công khai của tauri.conf.json.
    - Đối chứng trên bộ cài thật 0.4.133 / 0.4.149: đúng -> OK; lật 1 bit -> FAIL; chữ ký của bản khác -> FAIL; đúng chữ ký
      nhưng sai `--version` -> FAIL.
  - **Kết quả test** (`INSTALLER_OK`, 21 kiểm):
    - Kiểm tĩnh `/PPO`: kịch bản test không có dòng nào chạm khoá hay thư mục thật. Đối chứng: bản phát hành bị bắt 19 dòng.
    - Không `/D` -> mã 7. `/D` ngoài `%TEMP%` -> mã 7, không tạo gì.
    - Cài đè bản giả cũ (exe 3 byte, `resources\app\stale.py`, lối tắt + ghim kiểu Tauri, Studio + preferences.json):
      1051 file đúng từng byte, `stale.py` mất, dữ liệu còn, khoá gỡ cài đúng, 3 lối tắt trỏ exe mới với AUMID mới.
    - Exe đã cài tới host Ready bằng `resources\python\pythonw.exe` của chính nó.
    - Gỡ: chỉ còn dữ liệu người dùng (và `uninstall.exe`, vì test chạy `_?=` để chờ được), lối tắt mất, ghim còn, khoá test
      rỗng. HKCU thật + exe / lối tắt / ghim thật trước và sau giống hệt.
  - Bộ cài 0.4.148 (LZMA): **35,3 MB**, so với 20,1 MB của Tauri.
  - **Cho Q3:**
    - Cache Qt (`QStandardPaths`, org = app = `ABook`) nằm ở `%LOCALAPPDATA%\ABook\ABook\cache`, tức trong `$INSTDIR`. Gỡ thật
      phải xoá nó dù không tích ô xoá dữ liệu.
    - `desktop_qt.ini` ở `%LOCALAPPDATA%\ABook` là dữ liệu người dùng (theo ô xoá dữ liệu).
  - **Cho Q6 (Lead quyết 31-10, đã làm):** phép kiểm nằm ở `abook/webui/minisign_verify.py` (file mới; hash vẫn c95fac04),
    dùng lại `ed25519_verify.py`. API:
    - `signature_ok(data, ...)`, `digest_ok(blake2b_512, ...)`, `file_ok(path, ...)` (đọc từng MB); có `version=` thì
      trusted comment phải ghi đúng `version:<bản>`.
    - Đầu vào hỏng thì trả False, không ném lỗi.
    - `installer/minisign_verify.py` chỉ còn là dòng lệnh gọi `file_ok`.

    `tests/test_minisign_verify.py`, 21 ca:
    - Phải bị từ chối: chữ ký sai, chữ ký chung sai, khoá sai, mã khoá khác (dù đúng khoá), file sửa một byte, bản khác,
      thiếu `version:`, chữ ký / khoá công khai sai định dạng.
    - Ca thật: `.sig` của `ABook_0.4.149_x64-setup.exe` với khoá trong tauri.conf.json. Test lưu mã BLAKE2b-512 của bộ cài,
      không lưu file 20 MB: chữ ký "ED" ký trên chính mã ấy.
    - Kiểm lực: 4 lỗi cấy (bỏ chữ ký chung / bỏ kiểm version / bỏ kiểm chữ ký file / bỏ kiểm mã khoá) đều làm test đỏ.

    Sửa route / server.py có sẵn cho Q6: gửi Lead diff trước.

### Q3. Móc gỡ / nâng cấp
- Dừng tiến trình chạy TỪ thư mục cài theo ExecutablePath (không theo tên), chừa chính bộ gỡ.
- Ô "xoá dữ liệu" khi gỡ (mặc định không tích; dữ liệu `%LOCALAPPDATA%\ABook`; thư viện sách không bao giờ đụng); uninstall_guard
  kiểm thư viện đã lưu trước mỗi lần xoá đệ quy, từ chối junction.
- Nâng cấp không hỏi xoá dữ liệu (cờ ABOOK_INSTALLER_UPGRADE như upgrade_mode.ps1).
- Giữ bản sao lưu liên kết `.abook` gốc qua các lần cập nhật, gỡ xong dọn phần của mình (lỗi Tauri 28-09 trong hooks.nsh).
- Test: từng nhánh của guard (thư viện nằm trong thư mục sắp xoá -> không xoá; settings không đọc được -> giữ; junction ->
  từ chối); app đang chạy khi gỡ -> bị dừng, pythonw của người dùng ở chỗ khác không bị đụng.
- **Đã làm (31-10):** `installer/abook.nsi` + `installer/uninstall_guard.ps1`.
  - Gỡ thật luôn dừng rồi xoá `Studio` và cache Qt (`%LOCALAPPDATA%\ABook\ABook`).
  - Ô "Xoá dữ liệu ứng dụng" dưới trang xác nhận gỡ, mặc định không tích; `/DELETEDATA` cho gỡ im lặng. Có tích thì dừng
    rồi xoá `%LOCALAPPDATA%\ABook`.
  - Mỗi lần xoá đệ quy hỏi guard trước, với `ABOOK_PREFERENCES` truyền thẳng.
  - `/UPDATE` không xoá gì của người dùng. Bộ cài Qt không gọi bộ gỡ cũ (cài tại chỗ), nên không cần cờ
    ABOOK_INSTALLER_UPGRADE.
  - Liên kết `.abook` -> `ABook`, `.abookproj` -> `ABook.Project` (Q5 phần registry):
    - Lệnh mở `"<exe>" "%1"`, có ngoặc quanh exe. Bản Tauri thiếu ngoặc, đường có dấu cách thì hỏng.
    - Biểu tượng `book_file.ico` / `project_file.ico`, cùng `Content Type`.
    - Giá trị cũ của app khác giữ ở `ABook_backup` qua mọi lần cập nhật. Gỡ: còn trỏ ABook thì trả lại; gốc rỗng thì bỏ
      khoá; ProgId xoá.
    - `SHChangeNotify` chỉ có ở bản phát hành.
  - **Lỗi thật test bắt được:** `RMDir /r` của NSIS ĐI THEO junction. Một junction bên trong thư mục dữ liệu (ví dụ
    `Studio` -> chỗ khác) làm rỗng thư mục ngoài. Guard của Tauri chỉ kiểm junction trên đường TỚI thư mục, nên bộ gỡ
    Tauri đang phát hành cũng dính lỗi này.
    - Guard của Qt duyệt cả bên trong (không bao giờ bước vào reparse point). Thấy một cái là giữ cả thư mục (mã 4).
  - `tools/test_installer.py`: 56 ca, hồ sơ giả + gốc registry test như Q2.
    - Liên kết khi cài / cập nhật / gỡ (có và không có giá trị gốc).
    - Worker Studio giả (Python nhúng chép vào `Studio\python`) sống qua cài đè + cập nhật, bị dừng khi gỡ. pythonw của
      "người dùng" ở chỗ khác vẫn sống.
    - Gỡ không tích: còn `preferences.json`, Studio + cache đi.
    - `/DELETEDATA`:
      - Thư viện trong thư mục dữ liệu -> giữ.
      - Tuỳ chọn hỏng -> giữ.
      - Studio là junction -> giữ, đích còn nguyên.
      - Thư viện ở chỗ khác -> xoá hết, thư viện còn.
  - `tests/test_a85_setup_safety.py`: các ca guard chạy trên cả hai guard, thêm ca junction bên trong.
  - Kiểm lực: guard cũ (không duyệt bên trong) đỏ ở ca junction; bỏ việc giữ bản sao lưu gốc thì 3 ca đỏ.
  - Chưa kiểm được: ô đánh dấu trên giao diện gỡ. Test chỉ chạy im lặng; ô chỉ đặt `$DeleteDataState` như `/DELETEDATA`.

### Q4. Một phiên bản chạy
- `QLocalServer` tên theo người dùng (`ABookDesk-<băm SID>`). Lần mở thứ hai gửi danh sách đường file trên dòng lệnh rồi thoát
  mã 0; bản đang chạy nhận, đưa cửa sổ lên (`raise` + `requestActivate`; KHÔNG bao giờ trong test), rồi mở file.
- Đặt trước Q5 vì bấm đúp file khi app đang mở chính là lần mở thứ hai.
- Test (C++, GUILESS): server giả nhận đúng danh sách; lần hai thoát ngay; server chết thì lần hai tự làm server.
- Đã làm (31-10): `src/singleinstance.{h,cpp}`, `tests/test_singleinstance.cpp` (SingleInstanceTests trong build.bat).
  - Tên kênh `ABookDesk-` + sha256(SID | `%LOCALAPPDATA%` chữ thường).16 hex. Hồ sơ giả của mọi công cụ đo / smoke / bộ cài
    thử có `LOCALAPPDATA` riêng (`tools/private_profile.py`), nên không bao giờ gửi file sang app thật của chủ máy.
  - Quyền làm bản đang chạy là mutex `Local\<tên>`, không phải ống: Windows cho nhiều `QLocalServer` nghe cùng một tên ống
    (test bắt được: hai server cùng tên đều `listen` thành công). Tiến trình chết thì Windows nhả mutex (ca tiến trình con
    `--hold` bị giết).
  - Giao thức một dòng mỗi chiều: bản đang chạy chào `<pid>` (bản mới gọi `AllowSetForegroundWindow`), bản mới gửi
    `{"files": [...]}`, bản đang chạy đáp `ok`. Có người nghe mà không đáp kịp thì bản mới vẫn thoát (hai host cùng hồ sơ là
    hai bên ghi một `preferences.json`).
  - `main.cpp` hỏi trước khi khởi động host; `Main.qml otherLaunch(files)` hiện cửa sổ (`windowMode.reveal()`), đo đạc
    (`ABOOK_BENCH`) không nối. Mở `files`: Q5.

### Q5. Liên kết file + đọc dòng lệnh
- Bộ cài ghi `HKCU\Software\Classes\.abook` -> `ABook`, `.abookproj` -> `ABook.Project`, lệnh mở `"<exe>" "%1"`, icon.
- `main.cpp`: đường `.abook` -> cùng lối của "Mở file sách" (`addBook.begin([path])`, như `useOpenedBook` của web);
  `.abookproj` -> lối mở dự án của Studio. Đường lạ hay hỏng -> câu lỗi có sẵn, không màn trắng.
- Test: Width/QML test mở app với argv giả (đúng, sai đuôi, file không có); test bộ cài kiểm khoá registry trong hive tạm.
- Đã làm (31-10): registry ở Q3. `main.cpp` lấy đường tuyệt đối theo thư mục của lần mở (lần mở thứ hai có thư mục khác bản
  đang chạy), gọi `Main.qml openFiles` lúc khởi động; lần mở khác qua `otherLaunch`. `openFiles` giữ file tới khi host Ready
  rồi đưa vào `addBook.begin(paths)` - đúng lối kéo thả: `.abook` -> trang sách, `.abookproj` -> Studio (server quyết), đuôi
  lạ / file mất -> câu lỗi trong hộp "Thêm sách" (ImportQueue.itemFromPath, open-book-file), EPUB... -> bản xem trước.
  - Test thay cho Width/QML: `tools/smoke_open.py` trên bản đóng gói chép ra ngoài cây nguồn (smoke_packaged.py gọi nó):
    A mở với python_v4.abook -> cuốn vào Thư viện riêng; B mở với cuốn khác khi A còn sống -> B thoát 0 (< 10 s), A nhập cuốn
    ấy. Cuốn khác phải khác chương 1 (`smoke_play.write_package`): máy nhận cuốn theo mã băm audio, kotlin_v4 là cùng cuốn.
  - Kiểm lực: bỏ lời gọi lúc khởi động -> đỏ bước A; bỏ `openFiles` trong `otherLaunch` -> đỏ bước B.
  - Chưa test: đuôi lạ / file mất qua dòng lệnh (cùng lối kéo thả, đã có test ở ImportQueue), `.abookproj` qua dòng lệnh.
  - `tools/test_installer.py` chạy cùng bài trên `ABook.exe` ĐÃ CÀI, ngay sau bước host Ready (lệnh mở của liên kết đã được
    kiểm là `"<exe>" "%1"`).

### Q6. Tự cập nhật
- Máy chủ: `GET latest.json` (netconnect, hạn chờ như mọi lần tải), so phiên bản, tải bộ cài vào `%LOCALAPPDATA%\ABook\update`
  có tiến độ, kiểm `.sig` minisign bằng khoá công khai của tauri.conf.json (đọc từ một hằng chung, không chép tay hai nơi).
  Sai chữ ký -> xoá file, báo "Chưa cập nhật được - bản tải về không đúng chữ ký."
- Qt: `CheckUpdate` / `InstallUpdate` gọi máy chủ; cài = chạy bộ cài `/P` (passive) rồi thoát app. AdvancedUpdate.qml giữ nguyên
  chữ; thêm tiến độ tải nếu web có.
- Test: máy chủ HTTP giả phục vụ latest.json + bộ cài + `.sig` ký bằng khoá TEST (chữ ký đúng, sai, phiên bản cũ hơn, mạng
  im) -> đúng nhánh; không bao giờ chạy bộ cài thật trong test (lệnh chạy là hàm thay được).
- Đã làm (31-10, Lead duyệt thư 17:00 + điều kiện). Khác kế hoạch trên: thư mục tải là `%TEMP%\ABook-update`, chưa có tiến độ.
  - Host (`webui/updater.py`, cờ `--self-update` do vỏ Qt truyền cho bản cài, hay bản dev có `ABOOK_UPDATE_URL`) thay vỏ trả
    lời `check_update` / `install_update` của server.py. Mở app kiểm một lần, im lặng khi mất mạng; không bao giờ tự cài.
  - Khoá + nơi hỏi: `plugins.updater` của tauri.conf.json. Bản đóng gói mang bản chép `resources/app/updater.json`
    (windows_resources.ps1 Copy-App), smoke so nó với tauri.conf.json. Không lấy khoá từ mạng.
  - Chặn trước khi tải:
    - chỉ https (http chỉ 127.0.0.1 / localhost);
    - tên gói đúng `^ABook_\d+\.\d+\.\d+_x64-setup\.exe$` với số == version của latest.json (không lấy tên thô từ URL);
    - thư mục tải dựng mới mỗi lần, là junction thì từ chối.
  - Sau khi tải:
    - ít byte hơn Content-Length thì hỏng;
    - `minisign_verify.file_ok(..., version=<latest.json>)` luôn có version.
    - Hỏng thì xoá gói, trang nhận `abook-update-failed`.
  - Đúng: host gửi `{"run_installer", "args": ["/P","/UPDATE","/R"]}`; vỏ (`Backend::runInstaller`) chạy bộ cài trước, chạy
    được mới dừng host và thoát.
  - Test:
    - `tests/test_updater.py`: trang giả trên 127.0.0.1, khoá thử. Ca: tên lạ / `..\x.exe` / `%2e%2e`, http://example,
      tải dở, chữ ký bản khác, junction. Kiểm lực: phá từng điều kiện (7 chỗ) đều đỏ.
    - `tools/smoke_update.py` (trong smoke_packaged): host đóng gói thấy bản 9.9.9 giả, tải gói ký khoá thử, từ chối,
      không chạy bộ cài. Ca dương: Q7.
  - Bản cài nay hỏi GitHub latest.json mỗi lần mở, kể cả trong các lượt smoke / test bộ cài (im lặng nếu không có mạng).

### Q7. Phát hành bằng bộ cài Qt
Lead duyệt 31-10, thứ tự: (1) cập nhật thật N -> N+1 + ca an toàn tham số Tauri, (2) release.py một đường Qt (gửi diff
trước), (3) bản Qt đầu tiên do Lead quyết. latest.json dùng chung; không viết đường chuyển Tauri -> Qt.
- Bước 1 (`tools/test_installer.py`, sau bước mở file):
  - Khoá minisign THỬ của lượt (`tools/update_site.py`, cùng định dạng `tauri signer`) thay khoá trong updater.json của bản N
    đã cài; bản N+1 (số 9.9.9) dựng từ bản sao dist có updater.json khác làm dấu. Trang phát hành giả trên 127.0.0.1.
  - App chạy `ABOOK_SMOKE_EXIT=update` (main.cpp): thấy bản mới thì `POST /api/app/update` như nút "Cập nhật"; thoát 0 là do
    `Backend::runInstaller`, 8 khi host từ chối gói.
  - Ca âm trước: đúng khoá, chữ ký của gói khác -> tải rồi từ chối, khoá gỡ cài vẫn số N, file app không đổi, gói không nằm lại.
  - Ca dương: bộ cài chạy với đúng tham số của host (`/P /UPDATE /R`, không `/D`) -> khoá gỡ cài 9.9.9, file N+1 đúng từng
    byte, .pyc biên dịch lại, app mở lại (/R), dữ liệu + worker Studio đang chạy còn nguyên.
  - Lượt đầu bắt được một lỗi thật: bộ cài tới bước dừng app khi app còn đang tự tắt (host lưu nốt, tối đa 5 s), rồi
    `Stop-Process -Force` cắt ngang (app thoát -1). Với /UPDATE, `stop_processes.ps1 -GraceSeconds 15` chờ app thoát êm,
    hết hạn mới dừng cứng; test đòi app thoát 0.
  - Gốc của exit -1 (lỗi thật, không phải của test): `Backend::runInstaller` gọi `QCoreApplication::quit()`, mà ở
    QGuiApplication thì quit hỏi đóng cửa sổ trước; Main.qml (closeToTray) từ chối và thu xuống khay, nên app không thoát
    tới khi bộ cài dừng cứng. Nay là `QCoreApplication::exit(0)`; BackendTests
    `runInstallerLeavesEvenWhenTheWindowStaysOpen` (cửa sổ từ chối Close, vòng sự kiện phải thoát 0) hỏng với quit(), qua
    với exit. Lệnh `run_installer` cũng chạy sau slot readyRead của host (stop() xoá chính QProcess ấy).
  - test_installer 31-10 tối: INSTALLER_OK (72 phép kiểm), cả ca cập nhật dương / âm và ca tham số Tauri.
  - Lý do hỏng in dạng percent-encoding UTF-8 (`SMOKE_UPDATE_FAILED`): stderr của Qt ra theo bảng mã ANSI, chữ Việt thành '?'.
  - Mỗi lượt chạy app có hồ sơ riêng do test giữ: bộ cài và app nó mở lại thừa hưởng handle app.log.
  - Bản test của bộ cài không /D thì lấy chỗ cài từ gốc registry test (như bản thật đọc `Software\ABook\ABook`), không có
    thì vẫn từ chối; `AbookTestGuard` vẫn đòi chỗ ấy nằm trong %TEMP%.
- Ca an toàn tham số Tauri: tauri-plugin-updater 2.14 chạy bộ cài bằng ShellExecute với `/P /UPDATE /R /ARGS` (installMode
  passive, restart_after_install mặc định), không /D. Test dựng một bản Tauri đã cài (exe, bộ gỡ, resources\, khoá
  Uninstall + Software\ABook\ABook + .abook của Tauri) cùng dữ liệu đúng tên của một máy dùng thật (book_ids.key,
  computers.json, listening-node.json, cache\, logs\, Studio\, thư viện bên trong, WebView2 của com.ngdtuanh.abook, một
  junction ra ngoài). Chạy bộ cài Qt với đúng chuỗi ấy: cài được hay thoát lỗi đều được, dữ liệu phải còn nguyên từng byte.
  Ca này ghi lệnh mở lại vào `ABOOK_TEST_RELAUNCH_LOG` thay vì mở app (chỉ bản test), để app vừa mở không kịp ghi gì
  trước khi so.

- `build` gọi bước dựng Qt thay `build_windows_app.ps1`; cùng tên file, cùng `latest.json`, kiểm `.sig`.
- Bỏ `shell/` khỏi đường phát hành sau một bản Qt chạy thật trên "máy sạch": cài mới, cập nhật lên bản kế, gỡ có và không
  xoá dữ liệu.
- **"Máy sạch" = hồ sơ giả, không phải máy ảo** (chọn 31-10, Lead duyệt).
  - Vì sao không dùng Windows Sandbox: nó chưa bật trên máy (`C:\Windows\System32\WindowsSandbox.exe` không có), bật nó là đổi
    tính năng Windows, và cửa sổ Sandbox hiện lên màn hình chủ máy.
  - Mỗi lượt thử có thư mục cài tạm (`/D=`), `LOCALAPPDATA` / `APPDATA` / `USERPROFILE` riêng, gốc registry test (điều ở
    "Quyết định chung"), và desktop riêng có bộ canh tiêu điểm.
  - Kịch bản: cài mới, cập nhật lên bản kế (máy chủ HTTP giả của Q6), gỡ không xoá dữ liệu, cài lại, gỡ có xoá dữ liệu. Sau mỗi
    bước kiểm file, khoá test và host Ready.
  - Không bật tính năng Windows nào (Hyper-V, Sandbox) nếu chưa hỏi Lead.

## Ngoài phạm vi
- Cảnh báo QML thấy trong WidthTests (31-10, luồng UI): `StudioSettings.qml:139` gọi `.join` trên
  `(root.status ? root.status.outdated : [])`, ra `undefined` khi status không có `outdated` -> "TypeError: Cannot call method
  'join' of undefined". Test vẫn qua; chưa có test nào phủ hộp `studioOutdated`, nên sửa kèm test để luồng UI làm.
- Ký Authenticode, MSIX/Store.
- Bản macOS / Linux của app Qt.
