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
  `LOCALAPPDATA` / `USERPROFILE` / `HKCU\Software\Classes` riêng (registry ảo qua hive tạm hoặc khoá con có tiền tố test),
  không đụng bản ABook thật của chủ sách.

## Thứ tự

### Q1. Tài nguyên Python + app trong dist
- Tách `Build-Python` / `Copy-App` / `Remove-UnusedFromPython` / `Test-Python` / `Test-Host` của `build_windows_app.ps1` ra
  một file dùng chung (`scripts/windows_resources.ps1`). Bản Tauri và bản Qt cùng gọi, nên hai bộ cài mang đúng một bộ Python.
- `desktop_qt/build.bat package` thêm bước dựng `dist/resources/{python,app}`. Bản dev không đổi.
- Cắt các style Qt Quick Controls không dùng (windeployqt `--skip-plugin-types` hoặc xoá theo danh sách có kiểm). Đo cỡ
  trước và sau từng bước (`optional-runtime-on-demand`: đo cỡ mỗi phụ thuộc).
- Test: `smoke_dist.py` chạy exe đóng gói KHÔNG có `_internal` bên cạnh (chép dist sang thư mục tạm) -> host Ready từ
  `resources/`, mở Thư viện, phát một clip giả. Thêm `tools/smoke_packaged.py`.

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
- Bỏ `shell/` khỏi đường phát hành sau một bản Qt chạy thật trên máy ảo sạch (cài mới, cập nhật lên bản kế, gỡ có/không xoá
  dữ liệu).

## Ngoài phạm vi
- Ký Authenticode, MSIX/Store.
- Bản macOS / Linux của app Qt.
