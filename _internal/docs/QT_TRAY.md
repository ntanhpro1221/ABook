# Khay Win32 tự viết, bỏ Qt6Widgets.dll khỏi bản Qt (31-10)

Nhánh `dev/desk-qt-tray` (từ `dev/desk-qt-int2` f7ba17c1). `docs/QT_INSTALLER.md` nằm ở nhánh `dev/qt-installer`, chưa có ở đây:
khi gộp, chuyển bảng "Cỡ bộ cài" bên dưới vào mục cùng tên của file ấy, đổi dòng "Qt6Widgets ... đề xuất cho Lead, chưa làm"
thành "đã làm" và xoá câu "`Qt6Widgets.dll` ở lại vì `Qt.labs.platform`".

## Đã làm

- `src/trayicon.{h,cpp}`: lớp `TrayIcon` (QML_ELEMENT trong module ABook) dùng thẳng Win32.
  - Cửa sổ ẩn `HWND_MESSAGE` giữ icon; `Shell_NotifyIconW` NIM_ADD / MODIFY / DELETE / SETVERSION (`NOTIFYICON_VERSION_4`,
    kèm `NIF_SHOWTIP` vì bản 4 không hiện tooltip nếu thiếu), GUID cố định để Windows nhớ vị trí icon. Windows gắn GUID với
    đường dẫn exe: bản dựng ở thư mục khác bị từ chối, nên thêm thất bại thì gỡ rồi thêm lại, vẫn thất bại thì thêm không GUID.
  - Icon lấy từ resource `IDI_ICON1` của exe (`appicon.rc`, cùng `app.ico`), cỡ `SM_CXSMICON` theo DPI.
  - Thuộc tính `tooltip` (cắt 127 đơn vị UTF-16 của `szTip`, không chia đôi cặp surrogate), `actions` (cùng dạng TrayMenuModel),
    `visible`, `available` (icon đã vào khay; Explorer chưa chạy thì false, app đóng cửa sổ là thoát thay vì ẩn); tín hiệu
    `activated()` (NIN_SELECT / NIN_KEYSELECT) và `triggered(action)`; `showMessage(title, message)` cho lời báo "ABook vẫn chạy
    ở khay" của `Main.qml` (balloon, `NIIF_NOSOUND`).
  - Menu: `CreatePopupMenu` dựng lại MỖI LẦN MỞ từ `actions` (dòng tách = `MF_SEPARATOR`, mục tắt = `MF_GRAYED`, "&" thành "&&");
    `SetForegroundWindow` + `TrackPopupMenuEx(TPM_RETURNCMD)` + `PostMessage(WM_NULL)` theo hướng dẫn của Microsoft; lệnh phát ra
    SAU khi menu đã đóng và huỷ. Chuột phải / bàn phím mở bằng `WM_CONTEXTMENU`.
  - `TaskbarCreated`: Explorer khởi động lại thì thêm icon lại (không gửi NIM_DELETE vào thanh mới).
  - Gỡ icon: destructor và `aboutToQuit`. Process bị giết cứng thì icon ma vẫn còn tới khi rê chuột qua (Windows không cho cách khác).
  - Menu theo chế độ tối của Windows: ĐÃ LÀM (`TrayIcon::allowDarkMenus`: `SetPreferredAppMode(AllowDark)`,
    `AllowDarkModeForWindow`, `FlushMenuThemes` qua số hiệu 135 / 133 / 136 của uxtheme, chỉ khi `RtlGetVersion` >= build 18362;
    thiếu thì bỏ qua êm). Mới kiểm là ba hàm có mặt trên Windows build 26300 và gọi không hỏng; CHƯA nhìn thấy menu tối trên màn hình.
- `TrayShell`: ranh giới mỏng quanh `Shell_NotifyIcon` + `TrackPopupMenuEx`, bộ thử thay bằng đồ giả nên không icon nào vào khay.
- `qml/DesktopTray.qml` dùng `TrayIcon`; không file QML nào còn `import Qt.labs.platform`. `TrayMenuModel.qml` giữ nguyên.
- `tools/check_dist_deps.py` (selftest ở đầu `build.bat`, kiểm thật sau windeployqt): đỏ nếu một QML `import Qt.labs.platform`
  hoặc dist có `Qt6Widgets.dll`, `Qt6LabsPlatform.dll`, `qml/Qt/labs/platform`. Kiểm lực: selftest gieo từng lỗi; chạy thật với
  QML có dòng import trở lại thì đỏ (1 vấn đề), với dist cũ thì đỏ (3 vấn đề), với cây mới thì 0.
- `tests/test_tray.cpp` (`TrayTests`, 13 ca) và `tests/qml/stub/ABook/TrayIcon.qml` (chỗ của lớp thật cho `WidthTests` nạp `Main.qml`).

## Cỡ bộ cài (dist khi chưa có `resources/`)

Cùng máy, cùng cờ windeployqt/CRT; "trước" dựng từ f7ba17c1 nguyên vẹn. Bộ cài = NSIS `SetCompressor /SOLID lzma` (như
`installer/abook.nsi`) trên thư mục dist.

| | Trước | Sau | Đổi |
|---|---|---|---|
| Dist thô | 93.622.713 B (89,29 MiB) | 86.482.438 B (82,48 MiB) | −7,14 MB (−6,81 MiB) |
| Bộ cài (LZMA solid) | 21.735.160 B (20,73 MiB) | 19.369.105 B (18,47 MiB) | −2,37 MB (−2,26 MiB) |

File mất khỏi dist: `Qt6Widgets.dll` 6.577.464, `Qt6LabsPlatform.dll` 283.960, `qml/Qt/labs/platform/*` 76.012,
`styles/qmodernwindowsstyle.dll` 221.496 B. `ABookDesk.exe` +7 KB (khay C++).

## RAM nghỉ, app Qt, desktop riêng

`measure_shells.py --kinds qt --rounds 3 --seconds 40` (lấy từ `dev/qt-installer`): hồ sơ giả, desktop riêng, bộ canh tiêu điểm
(0 vi phạm); mỗi lượt lấy trung vị các mẫu 25-40 s sau khi mở; mỗi bên 3 vòng x (mở lần đầu + lần hai) x 2 lượt ABBA = 12 lượt.
Không có `resources/` nên không có host Python: số này là riêng tiến trình giao diện ABookDesk.exe.

| ABookDesk.exe | Trước (trung vị, min-max) | Sau (trung vị, min-max) | Đổi |
|---|---|---|---|
| USS (RAM riêng) | 73,1 MB (72,5-73,6) | 72,7 MB (72,0-73,2) | −0,4 MB |
| Private bytes | 148,85 MB (148,2-149,5) | 148,25 MB (147,4-149,0) | −0,6 MB |
| Cửa sổ đầu / lắng xuống | 517 ms / 835 ms | 515 ms / 841 ms | không đổi |
| CPU giao diện tới lúc lắng | 0,72 s | 0,74 s | không đổi |

Khay nay chỉ bớt ~0,5 MB RAM nghỉ (DLL không nạp thì không có trang nào chạm tới); phần được là cỡ cài đặt và tải.
Desktop riêng không có Explorer nên `Shell_NotifyIcon` luôn thất bại ở đây (icon không vào đâu cả, `available` false): chưa nhìn
đường THÀNH CÔNG (icon thật hiện, bấm, menu thật) vì chạy nó phải hiện icon trong khay của chủ máy.
