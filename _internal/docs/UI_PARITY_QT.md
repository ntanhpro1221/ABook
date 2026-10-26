# Lệch chữ, icon và bo góc giữa web máy tính và bản Qt

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Cùng nguồn chung như `docs/UI_PARITY.md` (web <-> điện thoại native): bo góc `Theme.qml` sinh bởi `desktop_qt/tools/gen_theme.py` từ DESIGN.md 5.5,
icon `LucidePaths.js` sinh bởi `scripts/gen_lucide_icons.py --qml`. Bảng dưới do `scripts/ui_parity_qt.py` sinh (`--check` báo lệch,
`tests/test_ui_parity_qt.py` chạy `--check`). Bộ đọc là heuristic trên mã nguồn: chữ dựng từ dữ liệu (tên chương, thời gian) không tính.

<!-- ui_parity_qt:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity_qt.py - không sửa tay, chạy lại script) -->

Quét: web máy tính 1150 chữ (918 khác nhau), 165 cặp nhãn-icon; Qt 81 chữ (72 khác nhau), 21 cặp nhãn-icon (icon dùng ở 26 chỗ). Khoá so lỏng như UI_PARITY.md (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối); phím tắt trong chú thích Qt (`Thu nhỏ (Esc)`) tách khỏi nhãn.

## a. Cùng việc, khác chữ

Nhãn ngắn Qt không có nguyên văn (khoá lỏng) ở web máy tính mà giống một nhãn web CÙNG MÀN chưa có ở Qt. 3 cặp; mỗi nhãn Qt lấy một nhãn web giống nhất. Giống không có nghĩa là cùng việc: người sửa xem mã hai bên trước khi đổi.

| màn | Qt | web | giống | nơi |
|---|---|---|---|---|
| Đang nghe | Dừng khi hết chương này | Sẽ dừng khi hết chương này. | 1.00 | `qt/SleepPopover.qml:16` ~ `listen/PlayerViews.tsx:2085` |
| Đang nghe | Giọng | Giọng đọc | 0.71 | `qt/NowPlaying.qml:198` ~ `listen/PlayerViews.tsx:733` |
| Đang nghe | Chưa có chương sau để nghe | Các chương sau chưa có audio. | 0.59 | `qt/NowPlaying.qml:272` ~ `listen/labels.ts:145` |

## b. Cùng nhãn khác icon, cùng icon khác nhãn

**Cùng nhãn, khác icon** (1 nhãn Qt có icon mà icon ấy không đi với nhãn này ở bất cứ đâu trên web máy tính):

| nhãn | web | Qt | nơi |
|---|---|---|---|
| Quay lại | chevron-left | arrow-left | `qt/ScreenHeader.qml:12` ~ `listen/LineWishes.tsx:255` (+2) |

**Cùng icon, khác nhãn** (2 cặp Qt; web cùng màn dùng cùng icon với nhãn khác):

| màn | icon | Qt | web cùng màn | nơi |
|---|---|---|---|---|
| Đang nghe | moon | Hẹn giờ | {} trên {} | `qt/NowPlaying.qml:294` |
| Đang nghe | moon | Hết chương | {} trên {} | `qt/NowPlaying.qml:294` |

Số cặp: web máy tính 145, Qt 19. Nhãn Qt có icon (19): `Chưa có chương sau để nghe`, `Chương`, `Chương sau`, `Chương trước`, `Cài đặt`, `Hẹn giờ`, `Hết chương`, `Khởi động lại`, `Mở rộng`, `Mở thư mục nhật ký`, `Phát`, `Quay lại`, `Studio`, `Thu gọn`, `Thu nhỏ`, `Thư viện`, `Tạm dừng`, `Tới câu đang nghe`, `Về Thư viện`.

## c. Nhãn chỉ có một bên, theo màn

Nhãn ngắn (<= 6 chữ). **Chỉ Qt**: không có ở web cùng màn; `*` = web có ở màn khác. **Chỉ web**: nhãn web của màn không có ở đâu trong Qt - phần lớn là tính năng Qt chưa làm (bản thử), chỉ đếm và kể 15 đầu.

### Thư viện

- chỉ Qt (3): Chưa mở được ABook (`qt/LibraryScreen.qml:154`); Chưa tải được thư viện (`qt/LibraryScreen.qml:154`); Thử lại* (`qt/LibraryScreen.qml:171`)
- chỉ web (29): Chưa có sách (`100`); Tạo sách nói (`111`); Thêm truyện hoặc tạo sách nói. (`124`); Mở file sách (`436`); Chưa nghe (`31`); Nghe dở (`31`); Tất cả (`31`); Xong (`31`); Mở {} (`160`); Nghe ngay {} (`163`); Nghe {} (`163`); Tạm dừng {} (`163`); Đọc {} (`163`); Thêm {} (`203`); Đang nghe (`227`); ...

### Thanh phát

- chỉ Qt (0): (không có)
- chỉ web (30): Vị trí trong chương (`181`); Shift+← (`260`); Sắp tắt · (`1265`); Nghe kiểm (`1335`); Đã nghe hết phần đã có (`1337`); Đọc bằng (`1380`); Chọn giọng khác (`1400`); Đóng lời báo (`1407`); Đã nghe chương này (`1434`); Thêm tuỳ chọn (`1537`); Trình phát (`1577`); Mở màn hình đang nghe (`1589`); Đóng trình phát (`1667`); Thiết bị phát (`1668`); Đang chuẩn bị giọng đọc… (`9`); ...

### Đang nghe

- chỉ Qt (6): Bìa (`qt/NowPlaying.qml:164`); Giọng (`qt/NowPlaying.qml:198`); Thử lại* (`qt/NowPlaying.qml:231`); Chưa có chương sau để nghe (`qt/NowPlaying.qml:272`); Danh sách chương* (`qt/NowPlaying.qml:308`); Dừng khi hết chương này (`qt/SleepPopover.qml:16`)
- chỉ web (54): Tạm dừng {} (`84`); Đọc {} (chưa có audio) (`103`); Đã làm sẵn (`119`); Tuỳ chọn {} (`134`); Nghe từ đầu chương (`146`); Đọc chương này (`150`); Chưa nghe (`155`); Đổi tên chương… (`160`); Shift+← (`260`); Lùi {} giây (`261`); Tới {} giây (`286`); Phím (`478`); Giọng đọc (`713`); Dừng (`790`); Thử (`790`); ...

### Đọc theo

- chỉ Qt (0): (không có)
- chỉ web (0): (không có)

### Trang sách

- chỉ Qt (1): Chưa lấy được danh sách chương. (`qt/BookPage.qml:138`)
- chỉ web (85): Nghe {} (`84`); Tạm dừng {} (`84`); Đọc {} (chưa có audio) (`103`); Đã làm sẵn (`119`); Tuỳ chọn {} (`134`); Nghe từ đầu chương (`146`); Đọc chương này (`150`); Chưa nghe (`155`); Đổi tên chương… (`160`); Dừng (`227`); Dừng nghe thử (`228`); Chưa có giọng (`312`); Chờ áp dụng (`317`); Đang chờ máy làm sách (`317`); Bỏ gộp {} vào {} (`327`); ...

### Cài đặt

- chỉ Qt (3): Nhật ký (`qt/SettingsScreen.qml:109`); Mở thư mục* (`qt/SettingsScreen.qml:123`); Phiên bản (`qt/SettingsScreen.qml:133`)
- chỉ web (46): Giọng kể (`78`); Máy đề xuất (`85`); Chất lượng (`94`); Cập nhật ABook (`145`); Đang tải bản mới… (`145`); ABook {} (`180`); Bản mới (`180`); Kiểm tra bản mới (`185`); Đang kiểm tra… (`185`); Thành phần sử dụng (`196`); Tự lùi (`229`); Nhạc nền (`234`); Không (`275`); 1 giờ (`276`); 2 giờ (`277`); ...

### Thanh bên

- chỉ Qt (10): Trạng thái ABook (`qt/ConnectionChip.qml:9`); Gặp lỗi (`qt/ConnectionChip.qml:54`); Sẵn sàng (`qt/ConnectionChip.qml:54`); Đang mở…* (`qt/ConnectionChip.qml:54`); Bản (`qt/ConnectionPopover.qml:75`); Khởi động lại (`qt/ConnectionPopover.qml:87`); Mở thư mục nhật ký (`qt/ConnectionPopover.qml:95`); Mở rộng (`qt/Sidebar.qml:84`); Thu gọn* (`qt/Sidebar.qml:84`); Studio chưa mở trong bản này. (`qt/StudioScreen.qml:14`)
- chỉ web (10): Đang tải tiến độ (`99`); Đang chờ {} (`111`); Đang dừng (`112`); Đang tạm dừng (`112`); Tiến độ: {} (`119`); Chờ (`120`); Xem tất cả (`125`); Có ABook (`146`); Bấm để cập nhật (`147`); Điều hướng chính (`166`)

### Thanh tiêu đề

- chỉ Qt (1): ABook* (`qt/Main.qml:10`)
- chỉ web (2): Tới nội dung (`228`); Điều hướng (`248`)

### Chung

- chỉ Qt (1): Quay lại* (`qt/ScreenHeader.qml:12`)
- chỉ web (3): Xem các tab trước (`514`); Xem các tab sau (`519`); Đóng (`699`)

## d. Bo góc QML không theo token

Hợp lệ: `Theme.radiusControl / radiusCover / radiusSheet` (DESIGN.md 5.5, `desktop_qt/tools/gen_theme.py`), `0`, tròn (`width / 2`, `height / 2`), lấy lại bo khung chứa (`parent.radius`), vòng đồng tâm ngoài (`Theme.radiusCover + 8` của bóng, vòng tiêu điểm). Còn lại (0):

| nơi | radius |
|---|---|
| (không có) | |

## e. Dấu thanh kiểu mới và dấu ba chấm cuối nhãn

**Dấu thanh kiểu mới (`òa óa úy`)** trong chữ Qt (0); web và native đa số viết kiểu cũ (`oà oá uý`, UI_PARITY.md d2):

- (không có)

**Nhãn kết thúc bằng `…` / `...`** (3): DESIGN.md chỉ cho `…` ở chữ đang chờ ("Đang mở…"), không cho nhãn nút.

- Đang mở văn bản chương… (`qt/ReadAlongView.qml:311`) - web: `Đang mở văn bản chương…`
- Đang mở… (`qt/ConnectionChip.qml:54`) - web: `Đang mở…`
- Đang tải âm thanh… (`qt/PlayerBar.qml:87`) - web: `Đang tải âm thanh…`

## f. Phím tắt trong chú thích

Chú thích Qt ghi phím tắt sau nhãn; web ghép bằng `withShortcut(nhãn, phím)`. Phím khác nhau là khác HÀNH VI (phím thật trong `Main.qml` / `player.tsx`), không chỉ khác chữ.

| nhãn | Qt | web | nơi |
|---|---|---|---|
| Chương trước | `Ctrl+←` | `Shift+←` | `qt/NowPlaying.qml:261` |
| Chương sau | `Ctrl+→` | `Shift+→` | `qt/NowPlaying.qml:272` |
| Phát | `Space` | (không ghi) | `qt/PlayButton.qml:13` |
| Tạm dừng | `Space` | (không ghi) | `qt/PlayButton.qml:13` |
| Mở rộng | `Ctrl+B` | (không ghi) | `qt/Sidebar.qml:84` |
| Thu gọn | `Ctrl+B` | (không ghi) | `qt/Sidebar.qml:84` |

Chú thích có hai dấu cách trước phím (web `withShortcut` ghép một dấu cách): 0.


<!-- ui_parity_qt:end -->

## Đã sửa phía Qt cho trùng web (26-10)

Chỉ những chỗ chắc chắn cùng việc; web không đổi. Chưa build Qt sau lần sửa này (bản Qt chỉ dựng trên Windows - `desktop_qt/build.bat`);
đã chạy `desktop_qt/tools/check_text_cut.py` và `gen_theme.py --check`.

| màn | nơi (QML) | cũ | mới (theo web) | nguồn web |
|---|---|---|---|---|
| Đang nghe | `NowPlaying.qml` công tắc hẹp | Bìa / Chữ | Bìa / Đọc theo | `PlayerViews.tsx` PANELS |
| Đang nghe | `NowPlaying.qml` chú thích nút tốc độ | Tốc độ nghe | Tốc độ đọc | `SpeedMenu` dialogLabel |
| Đang nghe | `NowPlaying.qml` nút hẹn giờ đang đếm | 14:51 (đồng hồ) | 15 phút / 40 giây | `sleep.ts` sleepButtonLabel |
| Đang nghe | `NowPlaying.qml` chú thích nút hẹn giờ | Hẹn giờ ngủ | Hẹn giờ tắt | `SleepPicker` dialogLabel |
| Đang nghe | `SpeedPopover.qml` dòng đầu | Tốc độ nghe | Tốc độ đọc · nhớ riêng cho cuốn này | `MenuNote` |
| Đang nghe | `SpeedPopover.qml` dòng cuối | Cuốn này nhớ tốc độ riêng của nó. | (bỏ - đã ở dòng đầu) | `MenuNote` |
| Đang nghe | `SleepPopover.qml` đang hẹn phút | Còn 12:34 | Tắt sau 12:34 | `SleepPicker` "Tắt sau" |
| Đang nghe | `SleepPopover.qml` chưa hẹn | Hẹn giờ ngủ | Dừng phát sau | `SleepPicker` |
| Đang nghe | `SleepPopover.qml` vừa tắt | Đã dừng lúc 23:10 | Hẹn giờ đã tắt tiếng lúc 23:10. | `SleepMenu` idle |
| Đang nghe | `SleepPopover.qml` nút thêm giờ | Thêm 10 phút | +10 phút | `SleepPicker` |
| Đọc theo | `ReadAlongView.qml` viên quay lại | Về chỗ đang đọc, icon chevron-up / chevron-down 14 | Tới câu đang nghe, icon locate 16 | `ReadAlongText.tsx` JumpToPlaying |
| Thư viện | `LibraryScreen.qml` trống | Thư viện còn trống · Sách bạn thêm sẽ nằm ở đây. | Chưa có sách nào · Sách nghe được sẽ hiện ở đây. | `LibraryScreen.tsx` EmptyState |
| Thư viện | `LibraryScreen.qml` lỗi | Chưa lấy được thư viện | Chưa tải được thư viện | `LoadError what="thư viện"` |
| Trang sách | `BookPage.qml` tiến độ | Bạn đã nghe xong / Bạn đã nghe 42 % | Đã nghe xong / Đã nghe 42% | `progressText`, `formatPercent` |
| Trang sách | `ScreenHeader.qml` + `BookPage.qml` nút ← | Quay lại (Esc) | Về Thư viện (Esc) | `BookScreen` back.label |
| Cài đặt | `SettingsScreen.qml` | Màu nền | Màu | `LookGroup` |
| mọi màn | chú thích có phím (`NavItem`, `IconButton`...) | `Thu nhỏ  (Esc)` (hai dấu cách) | `Thu nhỏ (Esc)` | `labels.ts` withShortcut |

Bo góc (19 chỗ -> 0): chữ đang đọc / câu đang đọc / rê câu `4` -> `Theme.radiusControl` (web `rounded-control`, `.read-along-word`); viên "Tới câu
đang nghe" `20` -> `height / 2` (`rounded-full`); chú thích nổi (`Main.qml`) và bóng giờ thanh tua `6` -> `Theme.radiusControl` (Tooltip
`rounded-control`); khung xám đang tải `4` -> `Theme.radiusControl` (Skeleton); nhãn phần của bìa tự sinh `3` và dấu nguồn của ô sách
`height > 24 ? 8 : height / 2` -> `Theme.radiusControl` (BookCover); bìa nhỏ thanh phát `4` -> `Theme.radiusControl` (BookCover mặc định); lời
nhắn của bộ phát `Math.min(20, height / 2)` -> `Theme.radiusCover` (toast `rounded-cover`); nút kéo thanh tua `7`, chấm trạng thái `4` ->
`width / 2`; vạch tiến độ (ô sách `1.5`, trang sách `2`, hàng chương `1`) -> `height / 2` (`rounded-full`); gạch dưới lựa chọn Màu `1` -> `0`
(SlidingIndicator không bo); khối sáng của công tắc Bìa / Đọc theo `Theme.radiusControl - 2` -> `Theme.radiusControl`.

Icon mới cho Qt: `locate` (thêm vào ICONS của `scripts/gen_lucide_icons.py`; sinh lại `LucidePaths.js` - bản cũ còn thiếu các icon nhánh điện thoại
đã thêm - và `LucidePaths.kt`, chỉ thêm `LOCATE`).

## Chưa sửa (không chắc cùng việc, hay là hành vi chứ không phải chữ)

- Phím chương trước / sau: Qt `Ctrl+←/→`, web `Shift+←/→` (mục f) - đổi phím là đổi hành vi (`Main.qml` Shortcut), cần Lead chọn.
- "Chưa có chương sau để nghe": web tách hai trường hợp ("Đây là chương cuối" - nút mờ; "Chương sau chưa có audio" - nút vẫn bấm được); Qt
  `Player.canNext` không phân biệt hai trường hợp, cần thêm thuộc tính ở C++.
- Nút ← mặc định của `ScreenHeader.qml` vẫn "Quay lại" + arrow-left (mục b báo lệch với "Quay lại" + chevron-left của web): web dùng cặp ấy cho
  bước lùi trong hộp thoại, còn nút ← của màn là ArrowLeft như Qt - không lệch thật; màn nào dùng ← thì đặt `backLabel` như web.
- Cấu trúc khác web (không chỉ chữ): hàng nút phụ Đang nghe (Qt ba ô Tốc độ / Hẹn giờ / Chương; web máy tính hai nút có nhãn, Chương là tab bảng
  phải), dòng "Giọng …" dưới tên chương (web không có), bảng hẹn giờ của web có "Đặt lại", "Bật lại N phút", lời nhắc nhỏ dần; Thư viện trống
  của web máy tính có nút "Thêm sách" / "Tạo sách nói" mà Qt chưa có (nên giữ câu "Sách nghe được sẽ hiện ở đây." thay vì "Thêm truyện hoặc tạo
  sách nói."); tên cửa sổ web đổi theo màn ("Thư viện · ABook"), Qt luôn "ABook"; nút cửa sổ Qt chưa có `Accessible.name`.
- Chữ chỉ có ở Qt vì là tính năng riêng của vỏ Qt: chip trạng thái phần chạy nền (Sẵn sàng / Đang mở… / Gặp lỗi, Khởi động lại, Mở thư mục nhật
  ký), thu gọn thanh bên, nhóm Nâng cao (Nhật ký / Mở thư mục / Phiên bản) - web có "Chẩn đoán" / "Gửi nhật ký" khác việc.
