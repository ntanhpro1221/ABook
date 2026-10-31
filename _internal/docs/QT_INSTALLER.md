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
- Ở lần mở đầu, Qt lắng chậm hơn 0,9 s (nạp DLL nguội, tạo cache QML).
- "Cửa sổ đầu tiên" của Tauri là khung trống trước khi WebView vẽ, nên không so trực tiếp được với Qt (vẽ xong mới hiện).
  Số so được là "lắng xuống".
- Cắt được ở Q1:
  - Style Qt Quick Controls không dùng (app chỉ import `Controls.Basic`): Fluent 5,5 + Imagine 3,3 + Material 2,4 + Universal
    1,8 + Fusion 1,8 + Windows / NativeStyle 1,6 MB thô = 16,6 MB thô, chỉ **2,6 MB nén**.
  - `Qt6Widgets.dll` 6,6 MB thô (~2,5 nén), nếu `Qt.labs.platform` chạy được với QGuiApplication mà không có nó (phải kiểm
    bằng smoke).
  - Đích sau khi cắt: ≈ 34-36 MB nén.

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
  - **Còn thiếu:** smoke mới dừng ở host Ready, chưa mở Thư viện và phát clip giả. `Qt6Widgets.dll` vẫn ở lại vì
    `Qt.labs.platform` (khay) kéo nó vào; muốn bỏ thì phải kiểm khay chạy được không có nó.

### Q2. Bộ cài NSIS
- `desktop_qt/installer/abook.nsi`: chép `dist/` vào thư mục cài của bản Tauri; lối tắt Start menu (+ màn hình nền nếu bản
  Tauri có); khoá gỡ cài (DisplayName, DisplayVersion, Publisher "ABook", icon, EstimatedSize); trang chào và trang xong
  tiếng Việt; chế độ `/P` (passive, cho bộ cập nhật) và `/S`.
- `build.bat installer <ver>` (hay `scripts/build_windows_qt.ps1`): makensis, rồi minisign `.sig`, rồi `latest.json` (chung
  hàm `Write-LatestJson`).
- Test: cài im lặng vào thư mục tạm -> file đủ, khoá gỡ cài đúng -> chạy exe đã cài (offscreen) Ready -> gỡ im lặng -> thư mục
  và khoá sạch. Cài đè một bản giả cũ hơn.

### Q3. Móc gỡ / nâng cấp
- Dừng tiến trình chạy TỪ thư mục cài theo ExecutablePath (không theo tên), chừa chính bộ gỡ.
- Ô "xoá dữ liệu" khi gỡ (mặc định không tích; dữ liệu `%LOCALAPPDATA%\ABook`; thư viện sách không bao giờ đụng); uninstall_guard
  kiểm thư viện đã lưu trước mỗi lần xoá đệ quy, từ chối junction.
- Nâng cấp không hỏi xoá dữ liệu (cờ ABOOK_INSTALLER_UPGRADE như upgrade_mode.ps1).
- Giữ bản sao lưu liên kết `.abook` gốc qua các lần cập nhật, gỡ xong dọn phần của mình (lỗi Tauri 28-09 trong hooks.nsh).
- Test: từng nhánh của guard (thư viện nằm trong thư mục sắp xoá -> không xoá; settings không đọc được -> giữ; junction ->
  từ chối); app đang chạy khi gỡ -> bị dừng, pythonw của người dùng ở chỗ khác không bị đụng.

### Q4. Một phiên bản chạy
- `QLocalServer` tên theo người dùng (`ABookDesk-<băm SID>`). Lần mở thứ hai gửi danh sách đường file trên dòng lệnh rồi thoát
  mã 0; bản đang chạy nhận, đưa cửa sổ lên (`raise` + `requestActivate`; KHÔNG bao giờ trong test), rồi mở file.
- Đặt trước Q5 vì bấm đúp file khi app đang mở chính là lần mở thứ hai.
- Test (C++, GUILESS): server giả nhận đúng danh sách; lần hai thoát ngay; server chết thì lần hai tự làm server.

### Q5. Liên kết file + đọc dòng lệnh
- Bộ cài ghi `HKCU\Software\Classes\.abook` -> `ABook`, `.abookproj` -> `ABook.Project`, lệnh mở `"<exe>" "%1"`, icon.
- `main.cpp`: đường `.abook` -> cùng lối của "Mở file sách" (`addBook.begin([path])`, như `useOpenedBook` của web);
  `.abookproj` -> lối mở dự án của Studio. Đường lạ hay hỏng -> câu lỗi có sẵn, không màn trắng.
- Test: Width/QML test mở app với argv giả (đúng, sai đuôi, file không có); test bộ cài kiểm khoá registry trong hive tạm.

### Q6. Tự cập nhật
- Máy chủ: `GET latest.json` (netconnect, hạn chờ như mọi lần tải), so phiên bản, tải bộ cài vào `%LOCALAPPDATA%\ABook\update`
  có tiến độ, kiểm `.sig` minisign bằng khoá công khai của tauri.conf.json (đọc từ một hằng chung, không chép tay hai nơi).
  Sai chữ ký -> xoá file, báo "Chưa cập nhật được - bản tải về không đúng chữ ký."
- Qt: `CheckUpdate` / `InstallUpdate` gọi máy chủ; cài = chạy bộ cài `/P` (passive) rồi thoát app. AdvancedUpdate.qml giữ nguyên
  chữ; thêm tiến độ tải nếu web có.
- Test: máy chủ HTTP giả phục vụ latest.json + bộ cài + `.sig` ký bằng khoá TEST (chữ ký đúng, sai, phiên bản cũ hơn, mạng
  im) -> đúng nhánh; không bao giờ chạy bộ cài thật trong test (lệnh chạy là hàm thay được).

### Q7. release.py
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
- Ký Authenticode, MSIX/Store.
- Bản macOS / Linux của app Qt.
