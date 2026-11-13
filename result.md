# parity3 — kết quả kiểm chứng

## Trạng thái

Cây `D:/Novels/ABook_parity2`, nhánh `dev/parity2`, gốc `73473dfb2`. Commit mới, không amend, không push. Không đổi nhánh/reset/stash cây `D:/Novels/ABook`.

| Commit | Nội dung |
|---|---|
| `3fce94045` | Sửa các FAIL Qt WidthTests, binding của delegate khi mất parent, và hồi quy kiểm log QML |
| `eebcb15b9` | Cơ chế giữ nội dung/chuyển động web và Android; máy dò cấu trúc; ratchet L7 về 0; sửa lỗi runtime và test cũ |

Thư mục bằng chứng: `C:/Users/NGDtuanh/AppData/Local/Temp/claude/D--Novels-ABook/eba3e3d6-08dd-4ad9-8ba0-dc9003c54c4a/scratchpad/codex/parity3`. Có log nguyên bản, `qt_totals.json`, `android_test_totals.json`, `instant_rows.json`, danh sách miễn và manifest stage cụ thể. Báo cáo được commit riêng sau hai commit triển khai trên.

**Các gate đều xanh:** WidthTests 0 FAIL / 0 QML_TYPE_ERROR, ratchet L7 bằng 0, Vitest và Gradle không còn FAIL.

## Qt: từ 14 FAIL / 4 QML_TYPE_ERROR về 0 / 0

| Ca gốc | Nguyên nhân và sửa |
|---|---|
| CastTab waitingBook | Test còn câu “Đang chờ…”; dùng câu hiện hành “Chờ máy làm sách…” |
| D2Devices shots | Hướng dẫn ghép còn một từ cuối dòng; dùng `TextWrap.pretty` |
| D2Studio sharedReadings | Test còn tooltip cũ; cập nhật câu “Bỏ cách đọc…” |
| D2Voice screenshotsNarrowKeys | Dòng giới hạn/đồng bộ chữ chưa qua `TextWrap.pretty`; sửa thành phần `ProviderKey` |
| D3 chapterMore | Tên truy cập cũ vi phạm luật L8; test dùng “Thêm tuỳ chọn…” hiện hành |
| D3 longToast | Test so toạ độ của hai parent khác nhau sau khi có Collapse; chuyển hai mép về cùng hệ toạ độ toast |
| Gaps coverPlayButton | Test còn lề 10 px; code/design dùng token khoảng cách 12 px |
| Studio1 loadingEmpty | Assert đòi skeleton biến mất ngay; chờ hoàn tất fade. Khi đi tiếp còn lộ kỳ vọng tên thư mục cũ, cũng đã sửa |
| Studio5, hai ca Apply | Test còn tiêu đề cũ “N thay đổi chờ”; dùng “N thay đổi đang chờ áp” |
| Studio6, ba ca chữ bị cắt | `WorkField` cộng 12 px thay vì tổng hai padding thật; sửa chiều cao dùng topPadding + bottomPadding |
| Studio6 noticesAssign | Mô tả toast chưa được chống từ mồ côi; dùng `TextWrap.pretty`. Test nội dung toast so với cùng cách định dạng |
| SettingsVoice:184/307, VoiceModule:185, VoiceSpeed:75 | Repeater detach delegate khi huỷ/đổi model, parent trở thành null. Guard đúng bốn binding width; đây là lỗi vòng đời parent, không phải singleton |

`test_qt_singleton_context.py` thêm hồi quy: log có tổng PASS nhưng bốn TypeError trên vẫn bị gate từ chối; cảnh báo trùng vị trí chỉ đếm một lần.

### Số thật từ build.bat

Log: `C:/Users/NGDtuanh/AppData/Local/Temp/parity3-qtbuild-final.txt`.

| Bộ | PASS | FAIL | QML_TYPE_ERROR |
|---|---:|---:|---:|
| qt_pytests | 169 | 0 | — |
| PlayerNative | 18 | 0 | 0 |
| MediaControls | 6 | 0 | 0 |
| DesktopApi | 43 | 0 | 0 |
| Backend | 6 | 0 | 0 |
| SingleInstance | 8 | 0 | 0 |
| Player | 52 | 0 | 0 |
| AudioFx | 16 | 0 | 0 |
| TonePreset | 8 | 0 | 0 |
| ReadAlong | 14 | 0 | 0 |
| Music | 89 | 0 | 0 |
| Voice | 64 | 0 | 0 |
| Mix | 93 | 0 | 0 |
| MusicWindowActivity | 4 | 0 | 0 |
| MusicLibrary | 8 | 0 | 0 |
| SkipGlyph | 6 | 0 | 0 |
| Tray | 16 | 0 | 0 |
| WindowChrome | 7 | 0 | 0 |
| Sidebar | 166 | 0 | 0 |
| WidthTests | **1617** | **0** | **0** |

Tổng 19 suite Qt: **2241 PASS, 0 FAIL**, không thiếu suite; glyph missing 0, text leak 0. WidthTests có 1 skipped; qt_pytests có 3 skipped. CMake 51/51 bước; đóng gói thành công, dependency gate 0 lỗi, kiểm import 46 binary, `SMOKE_OK` tải Main.qml và vẽ khung đầu không cảnh báo QML.

## L7

| Nền | Ratchet trước | Ratchet sau |
|---|---:|---:|
| Qt | 0 | 0 |
| Web | 124 | **0** |
| Android | 161 | **0** |
| Tổng | 285 | **0** |

Máy dò cuối: **0 ứng viên loại a / 743 vị trí đã phân loại** (Qt 77, web 479, Android 187). Web có 115 ca Presence giữ cây, 341 ca chuyển động ở cha, 11 thành phần tự lo chuyển động, 3 vòng đời hoạt ảnh riêng và 9 ca không vẽ UI. Android có 167 ca được host hoạt ảnh sở hữu; các ca đặc biệt còn lại có lý do ở bảng dưới.

- Web: `Presence` giữ cây React cuối khi điều kiện mất giá trị, hoạt ảnh trên DOM root của thành phần tự viết. Root DOM dùng `Reveal` không lớp bọc để giữ đúng cấu trúc danh sách; `Fact` chuyển props hoạt ảnh xuống div để `dl` hợp lệ. Dialog/Sheet nhận context đóng để portal thoát bằng cơ chế chung. Các slot tuỳ chọn kiểm nội dung hiện tại, tránh menu/footer rỗng vì phần tử Presence vẫn truthy.
- Android: `SwapContent` dùng AnimatedContent với snapshot dữ liệu nhánh, giữ nullable/smart cast tới hết hiệu ứng. Giữ weight, align và khoảng cách ở đúng host. Giảm chuyển động dùng fade ngắn trên clock không bị OS scale zero tắt; nội dung đang thoát không nhận tương tác/trợ năng.
- Máy dò được siết: Presence phải trực tiếp sở hữu điều kiện; SwapContent phải có contentKey khớp điều kiện; nhận composable generic và alias. Các ca thêm được phát hiện cũng đã xử lý, không giữ ngân sách ngầm.
- Danh sách từng vị trí, loại và lý do được lưu trong `instant_rows.json`; các ca miễn đặc biệt được ghi trong `exemptions.md` cùng thư mục bàn giao parity3.

## Web / Android / máy dò

| Bộ | PASS | FAIL | Skipped | Bằng chứng |
|---|---:|---:|---:|---|
| Vitest đầy đủ | **3121** | **0** | **0** | 338 file; `parity3-vitest-final.txt`, 498,04 giây |
| tsc | — | **0 lỗi** | — | `parity3-tsc-last.txt` |
| pytest máy dò/ngữ cảnh | **38** | **0** | **0** | `parity3-rules-last.txt` |
| Android đầy đủ | **3676** | **0** | **12** | 430 suite, 3688 test; XML mới hoàn toàn, 0 errors |

Vitest đã bao gồm 227 reading forms bằng interpreter production qua `ABOOK_TEST_PYTHON`; không bỏ qua suite do worktree thiếu venv. Các test cũ đòi font-semibold và literal skeleton timing được sửa theo font-medium/token chung hiện hành; các assert gỡ DOM ngay chuyển sang kiểm cây còn tương tác, vì cây thoát phải được giữ để fade.

Gradle cuối **BUILD SUCCESSFUL** trong 5 phút 26 giây (`parity3-gradle-final.txt`). Timestamp XML từ `2026-11-13T05:00:30.543Z` tới `05:04:54.187Z`; không cộng lẫn XML cũ. Hai hồi quy snapshot normal/reduced và hai ca máy dò mới nằm trong bộ đầy đủ.

Các lỗi Android được xử lý gồm cả năm FAIL có sẵn: hai kỳ vọng tên truy cập thiết bị, câu Cast đang chờ, luật máy dò skeleton/reduced fade, và chú thích ngoại lệ cắt dòng phụ đặt sai chỗ. Ba lỗi mới được bắt/sửa khi chạy thật: mất khoảng cách 8 dp ở ValuePicker; hai nút Mở/Gửi bị Box chồng lên nhau; footer xuất Studio cần tự subscribe luồng job qua ranh giới hoạt ảnh. MotionScan chỉ miễn fade ngắn trên clock cố định khi mọi lời gọi helper nằm trong nhánh giảm chuyển động dương; bộ tự kiểm vẫn bắt helper gọi sai nhánh và alpha không liên quan.

Máy dò L1–L10 đều **0**. Không giữ ngân sách FAIL cũ ở web/Android.

## Danh sách miễn đặc biệt (31 vị trí)

| Nền | Vị trí | Lý do |
|---|---|---|
| qt | `desktop_qt/qml/Main.qml:42` | Theo trạng thái cửa sổ native; hệ điều hành hoặc cơ chế cửa sổ chung quản lý chuyển tiếp. |
| qt | `desktop_qt/qml/Main.qml:102` | Theo trạng thái cửa sổ native; hệ điều hành hoặc cơ chế cửa sổ chung quản lý chuyển tiếp. |
| qt | `desktop_qt/qml/Main.qml:348` | Theo trạng thái cửa sổ native; hệ điều hành hoặc cơ chế cửa sổ chung quản lý chuyển tiếp. |
| web | `ui/src/desktop/App.tsx:601` | `StartupNotices` chỉ điều phối side effect; mọi return đều null, không vẽ UI. |
| web | `ui/src/desktop/App.tsx:602` | `VolumeSaver` chỉ điều phối side effect; mọi return đều null, không vẽ UI. |
| web | `ui/src/desktop/App.tsx:607` | `ExportJobHost` chỉ điều phối side effect; mọi return đều null, không vẽ UI. |
| web | `ui/src/desktop/App.tsx:608` | `ExportJobHost` chỉ điều phối side effect; mọi return đều null, không vẽ UI. |
| web | `ui/src/desktop/OtherComputers.tsx:367` | Chỉ có chữ cho trình đọc màn hình (sr-only); không vẽ lên màn hình. |
| web | `ui/src/desktop/Shell.tsx:269` | `ThisPlayerReporter` chỉ điều phối side effect; mọi return đều null, không vẽ UI. |
| web | `ui/src/listen/ReadAlongText.tsx:375` | Chỉ có chữ cho trình đọc màn hình (sr-only); không vẽ lên màn hình. |
| web | `ui/src/studio/NewProjectScreen.tsx:688` | Chỉ có chữ cho trình đọc màn hình (sr-only); không vẽ lên màn hình. |
| web | `ui/src/studio/ScriptTab.tsx:1068` | Chỉ có chữ cho trình đọc màn hình (sr-only); không vẽ lên màn hình. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/NativeActivity.kt:211` | `DemoBookSource` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/addbook/BookForms.kt:101` | `LaunchedEffect` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/components/BookCover.kt:84` | `LaunchedEffect` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/components/Insets.kt:53` | `WindowInsets` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/components/ListParts.kt:296` | Chọn cơ chế giảm chuyển động; cả hai nhánh đều hoạt ảnh, giảm chuyển động vẫn có fade ngắn. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/components/Sheet.kt:193` | `Offset` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/components/Sheet.kt:195` | `Offset` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/components/WrapText.kt:49` | Cùng bề mặt chữ và nội dung; chỉ đổi cách định dạng chữ thường/annotated để giấu dấu ngăn cuối dòng. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/data/LibraryView.kt:133` | `Series` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/export/ExportModel.kt:287` | `ExportProgress` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/motion/SwapContent.kt:42` | Chọn cơ chế giảm chuyển động; cả hai nhánh đều hoạt ảnh, giảm chuyển động vẫn có fade ngắn. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/music/library/MusicScreen.kt:141` | `LaunchedEffect` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/pip/PipContent.kt:132` | `LaunchedEffect` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/screens/BookSheets.kt:167` | `LaunchedEffect` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/shell/Shell.kt:235` | `LaunchedEffect` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/shell/Shell.kt:357` | Theo trạng thái cửa sổ native; hệ điều hành hoặc cơ chế cửa sổ chung quản lý chuyển tiếp. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/studio/StudioPreview.kt:30` | `Rejected` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/studio/StudioPreview.kt:46` | `Rejected` là effect host hoặc đối tượng dữ liệu; không tạo node UI hiển thị. |
| android | `mobile/android/app/src/main/java/vn/abook/player/ui/theme/ThemeReveal.kt:131` | Ảnh cũ đã được vòng tròn Clear phủ hết trước giải phóng bitmap; giữ thêm ảnh có thể vẽ bitmap đã recycle. |

Các ca còn lại trong phân loại b có chuyển động thật, trạng thái bất biến hoặc bố cục theo kích thước; instant_rows.json ghi từng vị trí và lý do. Không có danh sách miễn theo số dòng trong code.

## Quality và giới hạn thực thi

- Đọc `QUALITY_IMPLEMENTATION_FILES` trực tiếp: **69 mục** ở checkout này.
- Hash trước/sau: `71563e9c1a2ecee91b3be33d3300e0f529f3af7ceb77d7c0e18b6ee800489d9d`.
- Không sửa `_internal/abook/`. Không dừng hay resume sách.
- Python dùng đúng `D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe -X utf8`. CUDA bị tắt cho test; Qt offscreen; không emulator/điện thoại.
- Các bộ nặng chạy nối tiếp, kiểm RAM trống ít nhất 6 GiB và giữ tối đa bốn tiến trình nặng khi khởi động. Gradle một worker; tách JVM biên dịch và pha test để coordinator chỉ cần heap 512 MB.
- Trước commit đã quét ký tự điều khiển và LF; không thay file `.bat`.
