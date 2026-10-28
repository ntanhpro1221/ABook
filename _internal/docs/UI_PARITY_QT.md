# Lệch chữ, icon và bo góc giữa web máy tính và bản Qt

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Cùng nguồn chung như `docs/UI_PARITY.md` (web <-> điện thoại native): bo góc `Theme.qml` sinh bởi `desktop_qt/tools/gen_theme.py` từ DESIGN.md 5.5,
icon `LucidePaths.js` sinh bởi `scripts/gen_lucide_icons.py --qml`. Bảng dưới do `scripts/ui_parity_qt.py` sinh (`--check` báo lệch,
`tests/test_ui_parity_qt.py` chạy `--check`). Bộ đọc là heuristic trên mã nguồn: chữ dựng từ dữ liệu (tên chương, thời gian) không tính.

<!-- ui_parity_qt:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity_qt.py - không sửa tay, chạy lại script) -->

Quét: web máy tính 1404 chữ (1102 khác nhau), 218 cặp nhãn-icon; Qt 1139 chữ (821 khác nhau), 147 cặp nhãn-icon (icon dùng ở 197 chỗ). Khoá so lỏng như UI_PARITY.md (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối); phím tắt trong chú thích Qt (`Thu nhỏ (Esc)`) tách khỏi nhãn.

## a. Cùng việc, khác chữ

Nhãn ngắn Qt không có nguyên văn (khoá lỏng) ở web máy tính mà giống một nhãn web CÙNG MÀN chưa có ở Qt. 24 cặp; mỗi nhãn Qt lấy một nhãn web giống nhất. Giống không có nghĩa là cùng việc: người sửa xem mã hai bên trước khi đổi.

| màn | Qt | web | giống | nơi |
|---|---|---|---|---|
| Cài đặt | Dự phòng qua Bluetooth cho | Dự phòng qua Bluetooth cho {} | 1.00 | `qt/OtherComputersBluetooth.qml:27` ~ `desktop/OtherComputers.tsx:359` |
| Cài đặt | Lần cuối | Lần cuối {} | 1.00 | `qt/PhoneSyncDevice.qml:45` ~ `desktop/PhoneSync.tsx:406` |
| Cài đặt | Mã ghép nối: | Mã ghép nối: {} | 1.00 | `qt/PhoneSyncPairing.qml:71` ~ `desktop/PhoneSync.tsx:205` |
| Cài đặt | Mở Studio của | Mở Studio của {} | 1.00 | `qt/OtherComputersRow.qml:113` ~ `desktop/OtherComputers.tsx:205` |
| Cài đặt | Tên mới của mẫu “ | Tên mới của mẫu “{}” | 1.00 | `qt/BookTemplates.qml:193` ~ `desktop/BookTemplates.tsx:79` |
| Cài đặt | Đang tải | Đang tải {} | 1.00 | `qt/DevicesSkeleton.qml:8` ~ `listen/VieneuModuleCard.tsx:237` |
| Cài đặt | Điều khiển sản xuất từ | Điều khiển sản xuất từ {} | 1.00 | `qt/PhoneSyncDevice.qml:86` ~ `desktop/PhoneSync.tsx:417` |
| Cài đặt | Đã thôi ghép | Thôi ghép {}? | 0.86 | `qt/PhoneSync.qml:87` ~ `desktop/PhoneSync.tsx:440` |
| Cài đặt | Tự tắt sau | Tự tắt sau {} giờ | 0.83 | `qt/SettingsScreen.qml:59` ~ `shared/settingsSummary.ts:5` |
| Cài đặt | Đã chọn Bluetooth dự phòng | Dự phòng qua Bluetooth cho {} | 0.69 | `qt/OtherComputers.qml:85` ~ `desktop/OtherComputers.tsx:359` |
| Cài đặt | Không cài được Studio | Chưa cài Studio | 0.67 | `qt/StudioSettings.qml:51` ~ `studio/StudioSetup.tsx:129` |
| Studio dự án | Thu lại cả | Thu lại cả {}? | 1.00 | `qt/ProjectScreen.qml:525` ~ `studio/ProjectScreen.tsx:948` |
| Studio dự án | Xoá dự án “ | Xoá dự án “{}”? | 1.00 | `qt/StudioDialogs.qml:56` ~ `studio/ProjectScreen.tsx:565` |
| Studio dự án | Đã xoá dự án “ | Đã xoá dự án “{}” | 1.00 | `qt/StudioStore.qml:186` ~ `studio/ProjectScreen.tsx:553` |
| Studio dự án | Chưa xoá được | Chưa mở được: | 0.88 | `qt/StudioStore.qml:186` ~ `studio/ProjectsScreen.tsx:69` |
| Studio dự án | Không dừng được | Không đọc được: | 0.83 | `qt/StudioStore.qml:152` ~ `studio/ProjectsScreen.tsx:69` |
| Studio dự án | Chưa ghi được | Chưa mở được: | 0.80 | `qt/StudioStore.qml:227` ~ `studio/ProjectsScreen.tsx:69` |
| Studio dự án | Khôi phục “ | Khôi phục bản sao… | 0.69 | `qt/StudioDialogs.qml:56` ~ `studio/ProjectsScreen.tsx:81` |
| Studio dự án | Chưa bỏ xếp hàng được | Bỏ xếp hàng | 0.69 | `qt/StudioStore.qml:163` ~ `studio/ProjectScreen.tsx:780` |
| Studio dự án | Không bắt đầu được | Bắt đầu | 0.67 | `qt/StudioStore.qml:123` ~ `studio/ProjectScreen.tsx:750` |
| Studio dự án | Đã khôi phục “ | Khôi phục bản sao… | 0.62 | `qt/StudioStore.qml:197` ~ `studio/ProjectsScreen.tsx:81` |
| Studio dự án | Không làm tiếp được | Làm tiếp cuốn này… | 0.61 | `qt/StudioStore.qml:141` ~ `studio/ProjectScreen.tsx:655` |
| Studio dự án | Đã ghi: thu lại | Thu lại chương | 0.50 | `qt/StudioStore.qml:227` ~ `studio/ProjectScreen.tsx:970` |
| Trang sách | Thêm việc với sách | Việc với sách | 0.84 | `qt/BookPage.qml:53` ~ `listen/BookScreen.tsx:1059` |

## b. Cùng nhãn khác icon, cùng icon khác nhãn

**Cùng nhãn, khác icon** (4 nhãn Qt có icon mà icon ấy không đi với nhãn này ở bất cứ đâu trên web máy tính):

| nhãn | web | Qt | nơi |
|---|---|---|---|
| Chi tiết | info | chevron-right | `qt/MyMusicDetails.qml:28` (+1) ~ `studio/ProjectScreen.tsx:789` |
| Quay lại | chevron-left | arrow-left | `qt/ScreenHeader.qml:12` ~ `listen/LineWishes.tsx:255` (+2) |
| Tuỳ chọn Studio | more-horizontal | ellipsis | `qt/ProjectsScreen.qml:83` ~ `studio/ProjectsScreen.tsx:236` |
| Tạm dừng {} | check, circle-dashed, play | pause | `qt/BookCell.qml:76` ~ `listen/BookScreen.tsx:94` (+2) |

**Cùng icon, khác nhãn** (36 cặp Qt; web cùng màn dùng cùng icon với nhãn khác):

| màn | icon | Qt | web cùng màn | nơi |
|---|---|---|---|---|
| Thêm sách | file-text | Chọn file sách | Đang đọc… / Chọn file sách | `qt/AddBook.qml:540` |
| Thêm sách | file-text | Đang đọc… | Đang đọc… / Chọn file sách | `qt/AddBook.qml:540` |
| Cài đặt | download | Cập nhật ABook | Cài Studio, Cài tiếp, Có ABook {} | `qt/AdvancedUpdate.qml:95` |
| Cài đặt | download | Đang tải bản mới… | Cài Studio, Cài tiếp, Có ABook {} | `qt/AdvancedUpdate.qml:95` |
| Thư viện | play | Nghe {} | Đọc {} | `qt/BookCell.qml:76` |
| Thư viện | pause | Tạm dừng {} | Đọc {} | `qt/BookCell.qml:76` |
| Thư viện | laptop | Có sách trên máy khác | tập, {}, đã tải về máy này | `qt/BookCell.qml:125` |
| Thư viện | laptop | Trên | tập, {}, đã tải về máy này | `qt/BookCell.qml:125` |
| Trang sách | circle-dashed | Chưa nghe | Chưa nghe / Đã nghe xong, Tạm dừng {} | `qt/BookPage.qml:138` |
| Trang sách | check-check | Đã nghe xong | Chưa nghe / Đã nghe xong, Chưa nghe xong / Đã nghe xong | `qt/BookPage.qml:138` |
| Sửa sách | image-plus | Chọn ảnh bìa… | Đổi ảnh bìa… / Chọn ảnh bìa… | `qt/EditBook.qml:239` |
| Sửa sách | image-plus | Đổi ảnh bìa… | Đổi ảnh bìa… / Chọn ảnh bìa… | `qt/EditBook.qml:239` |
| Sửa sách | file-down | Lưu thành… | Lưu | `qt/EditBookItems.qml:81` |
| Sửa sách | trash-2 | Xoá | Bỏ ảnh bìa | `qt/EditBookMyMusic.qml:295` |
| Sửa sách | trash-2 | Xoá bài | Bỏ ảnh bìa | `qt/EditBookMyMusic.qml:309` |
| Sửa sách | trash-2 | Bỏ cách đọc | Bỏ ảnh bìa | `qt/EditBookReadings.qml:120` |
| Thư viện | pause | Chờ chương mới | Đọc {} | `qt/LibraryContinue.qml:42` |
| Thư viện | x | Đóng tìm kiếm | Xoá ô tìm | `qt/LibraryScreen.qml:164` |
| Thư viện | file-audio | Mở file sách | Đang mở… / Mở file sách | `qt/LibraryScreen.qml:418` |
| Thư viện | file-audio | Đang mở… | Đang mở… / Mở file sách | `qt/LibraryScreen.qml:418` |
| Thư viện | search | Chưa có cuốn nào nghe xong. | Thử tên sách hoặc tác giả khác., Tìm sách | `qt/LibraryScreen.qml:429` |
| Cài đặt | upload | Thêm nhạc của bạn | Đang thêm {}/{} / Thêm nhạc của bạn | `qt/MyMusicSettings.qml:145` |
| Cài đặt | upload | Đang thêm | Đang thêm {}/{} / Thêm nhạc của bạn | `qt/MyMusicSettings.qml:145` |
| Cài đặt | upload | Thêm nhạc của bạn | Đang thêm {}/{} / Thêm nhạc của bạn | `qt/MyMusicState.qml:105` |
| Đang nghe | moon | Hẹn giờ | {} trên {} | `qt/NowPlaying.qml:388` |
| Đang nghe | moon | Hết chương | {} trên {} | `qt/NowPlaying.qml:388` |
| Đang nghe | keyboard | Phím | Phím tắt | `qt/NowPlaying.qml:518` |
| Cài đặt | bluetooth | Dự phòng qua Bluetooth… | Dự phòng qua Bluetooth cho {} | `qt/OtherComputersBluetooth.qml:22` |
| Cài đặt | refresh-cw | Làm mới | Hỏi lại, Hỏi lại thư viện | `qt/PhoneDiagnostics.qml:67` |
| Cài đặt | save | Lưu nhật ký | Gửi nhật ký | `qt/PhoneDiagnostics.qml:68` |
| Cài đặt | trash-2 | Bỏ “ | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/SharedReadingsSettings.qml:99` |
| Cài đặt | download | Xem tiến độ cài | Cài Studio, Cài tiếp, Có ABook {} | `qt/StudioSettings.qml:132` |
| Cài đặt | trash-2 | Gỡ Studio | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/StudioSettings.qml:152` |
| Cài đặt | trash-2 | Xác nhận gỡ | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/StudioSettings.qml:152` |
| Cài đặt | trash-2 | Đang gỡ… | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/StudioSettings.qml:152` |
| Cài đặt | play | Thử giọng | Dừng / Thử giọng | `qt/VoiceRow.qml:105` |

Số cặp: web máy tính 193, Qt 134. Nhãn Qt có icon (111): `Bấm để đổi tên chương`, `Bật tiếng`, `Bỏ cách đọc`, `Bỏ ảnh bìa`, `Bỏ “`, `Chi tiết`, `Chưa có cuốn nào nghe xong.`, `Chưa nghe`, `Chương`, `Chương sau`, `Chương sau chưa có audio`, `Chương trước`, `Chẩn đoán`, `Chọn`, `Chọn file sách`, `Chọn thư mục`, `Chọn thư mục TXT`, `Chọn ảnh bìa…`, `Chờ chương mới`, `Cài Studio`, `Cài đặt`, `Có sách trên máy khác`, `Cập nhật ABook`, `Cửa sổ mini`, `Dừng`, `Dự phòng qua Bluetooth…`, `Dự án mới`, `Ghim trên cùng`, `Ghép thiết bị mới`, `Gỡ Studio`, `Gợi ý đọc`, `Gửi nhật ký`, `Hẹn giờ`, `Hết chương`, `Hỏi lại thư viện`, `Khởi động lại`, `Kiểm tra`, `Làm mới`, `Lưu`, `Lưu nhật ký`, `Lưu thay đổi`, `Lưu thành…`, `Mở cuốn đó`, `Mở file sách`, `Mở rộng`, `Mở Studio`, `Mở tab Nhạc nền`, `Mở thư mục`, `Mở thư mục nhật ký`, `Nghe từ đầu chương`, `Nghe {}`, `Nhạc nền`, `Phát`, `Phím`, `Quay lại`, `Studio`, `Sửa cách đọc`, `Sửa sách`, `Sửa thông tin`, `Thu gọn`, `Thu nhỏ`, `Thêm`, `Thêm bản riêng`, `Thêm giọng…`, `Thêm nhạc của bạn`, `Thêm sách`, `Thêm tuỳ chọn`, `Thêm vào thư viện`, `Thôi ghép`, `Thư viện`, `Thả để thêm sách`, `Thử giọng`, `Thử lại`, `Trên`, `Tuỳ chọn dự án`, `Tuỳ chọn Studio`, `Tìm`, `Tìm bìa…`, `Tìm máy trong mạng`, `Tìm sách`, `Tạm dừng`, `Tạm dừng {}`, `Tạo sách nói`, `Tới câu đang nghe`, `Vẫn cài`, `Vẫn thêm bản mới`, `Về chỗ vừa nghe`, `Về Cài đặt`, `Về Studio`, `Về Thư viện`, `Xem tiến độ cài`, `Xoá`, `Xoá bài`, `Xoá khoá`, `Xoá ô tìm`, `Xác nhận gỡ`, `Xếp theo`, `Đang gỡ…`, `Đang mở…`, `Đang thêm`, `Đang tải bản mới…`, `Đang đọc…`, `Đây là chương cuối`, `Đã nghe xong`, `Đóng`, `Đóng tìm kiếm`, `Đọc chương này`, `Đọc {}`, `Đổi bài`, `Đổi tên chương…`, `Đổi ảnh bìa…`.

## c. Nhãn chỉ có một bên, theo màn

Nhãn ngắn (<= 6 chữ). **Chỉ Qt**: không có ở web cùng màn; `*` = web có ở màn khác. **Chỉ web**: nhãn web của màn không có ở đâu trong Qt - phần lớn là tính năng Qt chưa làm (bản thử), chỉ đếm và kể 15 đầu.

### Khay và cửa sổ mini

- chỉ Qt (11): Ghim trên cùng (`qt/MiniPlayer.qml:52`); Mở rộng (`qt/MiniPlayer.qml:58`); Lùi {} giây* (`qt/MiniPlayer.qml:86`); Phát* (`qt/MiniPlayer.qml:87`); Tạm dừng* (`qt/MiniPlayer.qml:87`); Tới {} giây* (`qt/MiniPlayer.qml:88`); Chương sau* (`qt/TrayMenuModel.qml:12`); Chương trước* (`qt/TrayMenuModel.qml:12`); Cửa sổ mini (`qt/TrayMenuModel.qml:12`); Mở ABook (`qt/TrayMenuModel.qml:12`); Thoát ABook (`qt/TrayMenuModel.qml:12`)
- chỉ web (0): (không có)

### Thư viện

- chỉ Qt (10): Trên (`qt/BookCell.qml:122`); Tạm dừng* (`qt/LibraryContinue.qml:41`); Mới thêm* (`qt/LibraryScreen.qml:47`); Tác giả* (`qt/LibraryScreen.qml:47`); Tên sách* (`qt/LibraryScreen.qml:47`); Chưa mở được ABook (`qt/LibraryScreen.qml:384`); Chưa tải được thư viện (`qt/LibraryScreen.qml:384`); Thử lại* (`qt/LibraryScreen.qml:401`); Không có sách ở đây (`qt/LibraryScreen.qml:430`); Chưa có cuốn nào nghe xong. (`qt/LibraryScreen.qml:431`)
- chỉ web (2): Nghe ngay {} (`163`); Chưa có sách nào (`519`)

### Thanh phát

- chỉ Qt (1): Cửa sổ mini (`qt/PlayerBar.qml:105`)
- chỉ web (20): Vị trí trong chương (`181`); Shift+← (`260`); Sắp tắt · (`1265`); Nghe kiểm (`1335`); Đọc bằng (`1380`); Chọn giọng khác (`1400`); Đóng lời báo (`1407`); Đã nghe chương này (`1434`); Trình phát (`1577`); Mở màn hình đang nghe (`1589`); Đóng trình phát (`1667`); Thiết bị phát (`1668`); Đang chuẩn bị giọng đọc… (`9`); Nghe tiếp · {} (`59`); Chưa có audio (`90`); ...

### Đang nghe

- chỉ Qt (14): Đọc* (`qt/ChapterReader.qml:11`); Chưa có chương để đọc. (`qt/ChapterReader.qml:27`); Đang tải chương… (`qt/ChapterReader.qml:68`); Thử lại* (`qt/ChapterReader.qml:73`); Thêm tuỳ chọn* (`qt/NowPlaying.qml:196`); Bìa (`qt/NowPlaying.qml:219`); Giọng (`qt/NowPlaying.qml:253`); Vẫn đang nghe* (`qt/NowPlaying.qml:315`); Danh sách chương* (`qt/NowPlaying.qml:409`); Nhạc nền* (`qt/NowPlaying.qml:420`); Cửa sổ mini (`qt/NowPlaying.qml:521`); Gợi ý cho phần đọc* (`qt/ReadingSuggestions.qml:8`); Bỏ dòng (`qt/ReadingSuggestions.qml:56`); Đóng* (`qt/ReadingSuggestions.qml:78`)
- chỉ web (12): Đã làm sẵn (`119`); Shift+← (`260`); Esc (`2037`); Thiết bị phát (`2049`); Đang chuẩn bị giọng đọc… (`9`); Nghe tiếp · {} (`59`); Chưa có audio (`90`); Đang thu âm… (`90`); Bấm (`101`); Chạm (`101`); Máy này chưa có giọng đọc. (`121`); Nghe bằng giọng đọc.{} (`123`)

### Đọc theo

- chỉ Qt (0): (không có)
- chỉ web (0): (không có)

### Trang sách

- chỉ Qt (3): Thêm* (`qt/BookPage.qml:52`); Thêm việc với sách (`qt/BookPage.qml:53`); Chưa lấy được danh sách chương. (`qt/BookPage.qml:273`)
- chỉ web (59): Đã làm sẵn (`119`); Dừng nghe thử (`228`); Chưa có giọng (`312`); Chờ áp dụng (`317`); Đang chờ máy làm sách (`317`); Bỏ gộp {} vào {} (`327`); Bỏ gộp (`332`); Nghe {} nói (`345`); Đổi giọng {} (`347`); Thêm tuỳ chọn cho {} (`352`); Gộp vào người khác… (`364`); Đổi giới tính (`374`); Chưa có dàn nhân vật (`426`); Người kể chuyện (`438`); Chờ áp dụng: giọng (`441`); ...

### Cài đặt

- chỉ Qt (101): Chọn nơi lưu gói nhật ký (`qt/AdvancedDiagnostics.qml:12`); Chưa lưu được gói nhật ký (`qt/AdvancedDiagnostics.qml:17`); Đã lưu gói nhật ký (`qt/AdvancedDiagnostics.qml:17`); Đã lưu gói nhật ký trong (`qt/AdvancedDiagnostics.qml:17`); Chưa dọn được bản đọc (`qt/AdvancedStorage.qml:23`); Đã dọn bản đọc đã làm (`qt/AdvancedStorage.qml:23`); Chưa cập nhật được (`qt/AdvancedUpdate.qml:30`); Chất lượng cao (`qt/BookTemplates.qml:12`); Cân bằng (`qt/BookTemplates.qml:12`); Tên mẫu tối đa (`qt/BookTemplates.qml:46`); Đã có mẫu tên “ (`qt/BookTemplates.qml:46`); Đặt cho mẫu một cái tên (`qt/BookTemplates.qml:46`); Không làm được lúc này. (`qt/BookTemplates.qml:61`); Không lưu được mẫu (`qt/BookTemplates.qml:61`); Đã xoá mẫu “ (`qt/BookTemplates.qml:103`); Tên mới của mẫu “ (`qt/BookTemplates.qml:193`); Đang tải (`qt/DevicesSkeleton.qml:8`); Chưa lưu được cài đặt (`qt/ListenSave.qml:8`); Phím một chữ cái đang tắt (`qt/LookShortcuts.qml:11`); Chương trước / sau (`qt/LookShortcuts.qml:14`); Cửa sổ mini (`qt/LookShortcuts.qml:14`); Giảm / tăng tốc độ đọc (`qt/LookShortcuts.qml:14`); Lùi / tới 15 giây (`qt/LookShortcuts.qml:14`); Phát / tạm dừng (`qt/LookShortcuts.qml:14`); Thu nhỏ màn hình đang nghe (`qt/LookShortcuts.qml:14`); Tắt / bật tiếng (`qt/LookShortcuts.qml:14`); Xem các phím tắt này (`qt/LookShortcuts.qml:14`); Tìm hiểu thêm (`qt/MoreInfo.qml:8`); Bật đo cảm xúc (`qt/MyMusicModule.qml:37`); Tắt đo cảm xúc (`qt/MyMusicModule.qml:37`); Phân tích nhạc (`qt/MyMusicModule.qml:73`); Phân tích (`qt/MyMusicModule.qml:117`); Cảm xúc chính xác (`qt/MyMusicModule.qml:145`); Đang thêm nhạc thì dừng (`qt/MyMusicSettings.qml:71`); Không xoá được bài này (`qt/MyMusicSettings.qml:84`); Đã xoá khỏi Nhạc của tôi (`qt/MyMusicSettings.qml:84`); Không đổi được (`qt/MyMusicSettings.qml:95`); Chọn nhạc của bạn (`qt/MyMusicSettings.qml:119`); Đang thêm* (`qt/MyMusicSettings.qml:144`); Kết nối Wi-Fi (`qt/OtherComputers.qml:34`); Chưa chọn được (`qt/OtherComputers.qml:85`); Không dùng Bluetooth dự phòng nữa (`qt/OtherComputers.qml:85`); Đã chọn Bluetooth dự phòng (`qt/OtherComputers.qml:85`); Không tìm được (`qt/OtherComputers.qml:94`); Chưa thôi ghép được (`qt/OtherComputers.qml:120`); Dự phòng qua Bluetooth cho (`qt/OtherComputersBluetooth.qml:27`); Mở Studio của (`qt/OtherComputersRow.qml:113`); Chưa lưu được nhật ký (`qt/PhoneDiagnostics.qml:49`); Chọn nơi lưu nhật ký (`qt/PhoneDiagnostics.qml:49`); Đã lưu nhật ký (`qt/PhoneDiagnostics.qml:49`); Làm mới* (`qt/PhoneDiagnostics.qml:67`); Lưu nhật ký* (`qt/PhoneDiagnostics.qml:68`); Chi tiết kỹ thuật* (`qt/PhoneDiagnostics.qml:105`); Chưa bật được đồng bộ (`qt/PhoneSync.qml:60`); Đã tắt chia sẻ qua Wi-Fi (`qt/PhoneSync.qml:60`); Đã thôi ghép (`qt/PhoneSync.qml:87`); Đã đổi tên thành “ (`qt/PhoneSync.qml:95`); Lần cuối (`qt/PhoneSyncDevice.qml:45`); Điều khiển sản xuất từ (`qt/PhoneSyncDevice.qml:86`); Mã ghép nối: (`qt/PhoneSyncPairing.qml:71`); Chưa dùng được (`qt/ProviderKey.qml:20`); Dùng được · (`qt/ProviderKey.qml:20`); Dán khoá trước đã. (`qt/ProviderKey.qml:31`); Khoá chưa dùng được. (`qt/ProviderKey.qml:40`); Đã lưu (`qt/ProviderKey.qml:139`); Đã đổi thư mục thư viện (`qt/SettingsAdvanced.qml:14`); Chọn thư mục thư viện (`qt/SettingsAdvanced.qml:62`); Tự chọn nhạc nền (`qt/SettingsListen.qml:23`); Đã bật tự chọn nhạc nền (`qt/SettingsListen.qml:28`); Đã tắt tự chọn nhạc nền (`qt/SettingsListen.qml:28`); Thu vào khay khi đóng (`qt/SettingsLook.qml:13`); Tự mở cửa sổ mini (`qt/SettingsLook.qml:18`); Giấy* (`qt/SettingsLook.qml:33`); Ngà* (`qt/SettingsLook.qml:33`); Đêm* (`qt/SettingsLook.qml:33`); Có bản mới (`qt/SettingsScreen.qml:59`); Không tự lùi (`qt/SettingsScreen.qml:59`); Phiên bản (`qt/SettingsScreen.qml:59`); Tự tắt sau (`qt/SettingsScreen.qml:59`); Có ABook* (`qt/SettingsScreen.qml:120`); Tự tắt (`qt/SettingsSleep.qml:31`); Mỗi lần nghe thêm (`qt/SettingsSleep.qml:56`); Số phút nghe thêm (`qt/SettingsSleep.qml:57`); Lúc đang nhỏ dần: (`qt/SettingsSleep.qml:58`); Nhỏ dần (`qt/SettingsSleep.qml:65`); Độ dài nhỏ dần (`qt/SettingsSleep.qml:66`); Đã bỏ “ (`qt/SharedReadingsSettings.qml:33`); Bỏ “ (`qt/SharedReadingsSettings.qml:103`); Không cài được Studio (`qt/StudioSettings.qml:51`); Chưa gỡ được Studio (`qt/StudioSettings.qml:60`); Đã gỡ Studio (`qt/StudioSettings.qml:60`); Cần cập nhật* (`qt/StudioSettings.qml:169`); Mất (`qt/StudioSettings.qml:169`); Chưa tải được* (`qt/VoiceModule.qml:55`); Chưa gỡ được (`qt/VoiceModule.qml:56`); Chưa huỷ được việc tải (`qt/VoiceModule.qml:156`); Chưa đổi được cách đọc (`qt/VoiceModule.qml:283`); Gỡ “ (`qt/VoiceModule.qml:399`); Thử* (`qt/VoiceRow.qml:108`); Chưa đổi được tốc độ giọng (`qt/VoiceSpeed.qml:20`); Chưa tải được bản nhanh hơn (`qt/VoiceSpeed.qml:94`)
- chỉ web (40): Tên mới của mẫu “{}” (`79`); Mở Studio của {} (`205`); Chẩn đoán {} (`216`); Hỏi lại (`229`); Thôi ghép {} (`232`); Dự phòng qua Bluetooth cho {} (`359`); Bluetooth (`368`); Mã ghép nối: {} (`205`); Lần cuối {} (`406`); Điều khiển sản xuất từ {} (`417`); ABook {} (`180`); Mẫu thiết lập (`383`); Có ABook {} (`532`); ABook{} là bản mới nhất. (`21`); Đang thêm {}/{} (`146`); ...

### Thêm sách

- chỉ Qt (21): Chưa đọc lại được file (`qt/AddBook.qml:175`); Không mở được file sách (`qt/AddBook.qml:215`); Không mở được file sách này. (`qt/AddBook.qml:226`); Chưa thêm được sách (`qt/AddBook.qml:306`); Đã thêm sách vào thư viện (`qt/AddBook.qml:306`); Bỏ qua* (`qt/AddBook.qml:393`); Thêm bản riêng (`qt/AddBook.qml:427`); Vẫn thêm bản mới (`qt/AddBook.qml:427`); Xong* (`qt/AddBook.qml:433`); Còn (`qt/AddBook.qml:484`); Không đọc số chú thích* (`qt/AddBook.qml:870`); Đọc lời chú ở cuối chương* (`qt/AddBook.qml:879`); Bỏ lời chú* (`qt/AddBook.qml:887`); Bỏ dòng này khỏi phần đọc* (`qt/AddBook.qml:956`); Tất cả file (*) (`qt/AddBook.qml:1029`); Đưa vào sách: (`qt/ImportChapters.qml:100`); Bấm để đổi tên chương* (`qt/ImportChapters.qml:135`); Tên chương* (`qt/ImportChapters.qml:171`); Thả để thêm sách* (`qt/ImportDrop.qml:52`); Thử lại* (`qt/ImportError.qml:50`); Đang tải (`qt/ImportSkeleton.qml:10`)
- chỉ web (9): Đóng khi còn sách chưa thêm (`585`); Đang thêm {} (`802`); Các file đã chọn (`825`); Chờ (`833`); Đang xem (`833`); Sách {}/{} (`87`); Đã thêm {} sách (`133`); Không thêm cuốn nào (`140`); Tách theo {} dòng “Chương N” (`180`)

### Sửa sách

- chỉ Qt (48): Chưa chỉnh được nhạc nền (`qt/BookMusicSettings.qml:32`); Tìm ảnh bìa (`qt/EditBook.qml:44`); Chưa đổi được tên sách (`qt/EditBook.qml:113`); Đã đổi tên sách (`qt/EditBook.qml:113`); Chưa đổi được tác giả (`qt/EditBook.qml:117`); Đã bỏ tên tác giả (`qt/EditBook.qml:117`); Đã đổi tác giả (`qt/EditBook.qml:117`); Chưa đặt được ảnh bìa (`qt/EditBook.qml:121`); Đã đặt ảnh bìa (`qt/EditBook.qml:121`); Chưa bỏ được ảnh bìa (`qt/EditBook.qml:124`); Chưa bỏ được thay đổi (`qt/EditBook.qml:127`); Không đọc được file ảnh (`qt/EditBook.qml:405`); Thử lại* (`qt/EditBookError.qml:45`); Lưu thay đổi* (`qt/EditBookItems.qml:70`); Lưu thành…* (`qt/EditBookItems.qml:80`); Đang thêm nhạc thì dừng (`qt/EditBookMyMusic.qml:66`); Không xoá được bài này (`qt/EditBookMyMusic.qml:79`); Đã xoá khỏi Nhạc của tôi (`qt/EditBookMyMusic.qml:79`); Chọn nhạc của bạn (`qt/EditBookMyMusic.qml:112`); Nhạc của tôi* (`qt/EditBookMyMusic.qml:121`); Chưa có bài nào* (`qt/EditBookMyMusic.qml:122`); Thêm nhạc của bạn* (`qt/EditBookMyMusic.qml:131`); Đang thêm* (`qt/EditBookMyMusic.qml:131`); Phân tích nhạc (`qt/EditBookMyMusic.qml:148`); Huỷ* (`qt/EditBookMyMusic.qml:164`); Phân tích (`qt/EditBookMyMusic.qml:172`); Nhạc riêng* (`qt/EditBookMyMusic.qml:184`); Đang tải nhạc riêng* (`qt/EditBookMyMusic.qml:190`); Xoá* (`qt/EditBookMyMusic.qml:295`); Xoá bài* (`qt/EditBookMyMusic.qml:309`); Giữ lại* (`qt/EditBookMyMusic.qml:316`); Chưa bỏ được cách đọc (`qt/EditBookReadings.qml:27`); Chưa lưu được cách đọc (`qt/EditBookReadings.qml:27`); Đang tải cách đọc* (`qt/EditBookReadings.qml:67`); Sửa cách đọc* (`qt/EditBookReadings.qml:112`); Bỏ cách đọc (`qt/EditBookReadings.qml:122`); Cách đọc cho (`qt/EditBookReadings.qml:141`); Lưu cho cả cuốn* (`qt/EditBookReadings.qml:152`); Đọc như chữ trong sách* (`qt/EditBookReadings.qml:160`); Chưa đổi được tên chương (`qt/EditBookRename.qml:29`); Đã đổi tên chương: (`qt/EditBookRename.qml:29`); Chưa lưu được file sách (`qt/EditBookSaveAs.qml:25`); Đã lưu file sách (`qt/EditBookSaveAs.qml:25`); Chọn nơi lưu file sách (`qt/EditBookSaveAs.qml:51`); Loại file (`qt/EditBookSaveAs.qml:59`); Đang tải (`qt/EditBookSkeleton.qml:10`); Đang tải bài nhạc* (`qt/EditBookSwap.qml:36`); Chọn* (`qt/EditBookSwap.qml:91`)
- chỉ web (1): Bỏ mọi thay đổi ({}) (`486`)

### Thanh bên

- chỉ Qt (9): Trạng thái ABook (`qt/ConnectionChip.qml:9`); Gặp lỗi (`qt/ConnectionChip.qml:54`); Sẵn sàng (`qt/ConnectionChip.qml:54`); Đang mở…* (`qt/ConnectionChip.qml:54`); Bản (`qt/ConnectionPopover.qml:75`); Khởi động lại (`qt/ConnectionPopover.qml:87`); Mở thư mục nhật ký (`qt/ConnectionPopover.qml:95`); Mở rộng (`qt/Sidebar.qml:84`); Thu gọn* (`qt/Sidebar.qml:84`)
- chỉ web (9): Đang tải tiến độ (`99`); Đang chờ {} (`111`); Đang dừng (`112`); Đang tạm dừng (`112`); Tiến độ: {} (`119`); Chờ (`120`); Xem tất cả (`125`); Bấm để cập nhật (`147`); Điều hướng chính (`166`)

### Studio dự án

- chỉ Qt (31): Làm (`qt/OnComputerPill.qml:9`); Chưa có chương nào (`qt/ProjectScreen.qml:481`); Đang tải nhật ký (`qt/ProjectScreen.qml:503`); Thu lại cả (`qt/ProjectScreen.qml:525`); Không thấy thư mục thư viện* (`qt/ProjectsScreen.qml:216`); Chọn thư mục* (`qt/ProjectsScreen.qml:219`); Chọn lại thư mục thư viện* (`qt/ProjectsScreen.qml:220`); Nghe* (`qt/StudioChapterRow.qml:46`); Tuỳ chọn (`qt/StudioChapterRow.qml:159`); Khôi phục “ (`qt/StudioDialogs.qml:56`); Xoá dự án “ (`qt/StudioDialogs.qml:56`); Áp dụng (`qt/StudioDialogs.qml:56`); Đóng* (`qt/StudioDialogs.qml:56`); Lỗi (`qt/StudioStore.qml:40`); Mất kết nối tới ABook. (`qt/StudioStore.qml:40`); Không bắt đầu được (`qt/StudioStore.qml:123`); Không làm tiếp được (`qt/StudioStore.qml:141`); Không tạm dừng được (`qt/StudioStore.qml:141`); Không dừng được (`qt/StudioStore.qml:152`); Chưa bỏ xếp hàng được (`qt/StudioStore.qml:163`); Không mở được thư mục (`qt/StudioStore.qml:171`); Chưa đổi được tên (`qt/StudioStore.qml:176`); Đã đổi tên thành “ (`qt/StudioStore.qml:176`); Chưa xoá được (`qt/StudioStore.qml:186`); Hoàn tác* (`qt/StudioStore.qml:186`); Đã xoá dự án “ (`qt/StudioStore.qml:186`); Chưa hoàn tác được (`qt/StudioStore.qml:197`); Đã khôi phục “ (`qt/StudioStore.qml:197`); Chưa khôi phục được (`qt/StudioStore.qml:204`); Chưa ghi được (`qt/StudioStore.qml:227`); Đã ghi: thu lại (`qt/StudioStore.qml:227`)
- chỉ web (43): Đổi giọng kể (`264`); Tiến độ cả sách (`291`); Các bước (`317`); Phân tích truyện (`319`); Phân vai (`333`); Thu âm và kiểm tra (`340`); Làm tiếp từ chỗ ấy (`378`); Phân tích của “ (`378`); Dừng phân tích? (`420`); Dừng thu âm? (`420`); Nên để chạy hết bước này (`442`); Đã xoá dự án “{}” (`553`); Xoá dự án “{}”? (`565`); Tuỳ chọn dự án {} (`626`); Làm tiếp cuốn này… (`655`); ...

### Studio máy khác

- chỉ Qt (3): Về Studio* (`qt/StudioScreen.qml:158`); Dự án mới* (`qt/StudioScreen.qml:159`); Studio* (`qt/StudioScreen.qml:186`)
- chỉ web (1): Đang mở Studio của {} (`52`)

### Thanh tiêu đề

- chỉ Qt (3): ABook* (`qt/Main.qml:10`); ABook vẫn chạy ở khay (`qt/Main.qml:26`); Chưa tải được bản mới (`qt/Main.qml:200`)
- chỉ web (2): Tới nội dung (`228`); Điều hướng (`248`)

### Chung

- chỉ Qt (3): Không làm được lúc này. (`qt/Api.qml:39`); Quay lại* (`qt/ScreenHeader.qml:12`); Đóng thông báo (`qt/Toast.qml:146`)
- chỉ web (4): Đang mở ABook (`578`); Đang tải điều hướng (`578`); Xem các tab trước (`514`); Xem các tab sau (`519`)

File QML chưa xếp màn (thêm vào SCREENS): `desktop_qt/qml/MusicCredit.qml`, `desktop_qt/qml/MusicPopover.qml`.

## d. Bo góc QML không theo token

Hợp lệ: `Theme.radiusControl / radiusCover / radiusSheet` (DESIGN.md 5.5, `desktop_qt/tools/gen_theme.py`), `0`, tròn (`width / 2`, `height / 2`), lấy lại bo khung chứa (`parent.radius`), vòng đồng tâm ngoài (`Theme.radiusCover + 8` của bóng, vòng tiêu điểm). Còn lại (1):

| nơi | radius |
|---|---|
| `qt/MiniPlayer.qml:22` | `framed ? Theme.radiusSheet : 0` |

## e. Dấu thanh kiểu mới và dấu ba chấm cuối nhãn

**Dấu thanh kiểu mới (`òa óa úy`)** trong chữ Qt (0); web và native đa số viết kiểu cũ (`oà oá uý`, UI_PARITY.md d2):

- (không có)

**Nhãn kết thúc bằng `…` / `...`** (23): DESIGN.md chỉ cho `…` ở chữ đang chờ ("Đang mở…"), không cho nhãn nút.

- Bỏ mọi thay đổi… (`qt/EditBook.qml:338`) - web: `Bỏ mọi thay đổi…`
- Chọn thư mục… (`qt/EditBookSaveAs.qml:80`) - web: `Chọn thư mục`, `Chọn thư mục…`
- Chọn ảnh bìa… (`qt/EditBook.qml:238`) - web: `Chọn ảnh bìa…`
- Dự phòng qua Bluetooth… (`qt/OtherComputersBluetooth.qml:25`) - web: `Dự phòng qua Bluetooth…`
- Lưu thành… (`qt/EditBookItems.qml:80`) - web: `Lưu thành…`
- Lưu thành… (`qt/EditBookSaveAs.qml:16`) - web: `Lưu thành…`
- Mở dự án có sẵn… (`qt/ProjectsScreen.qml:245`) - web: `Mở dự án có sẵn…`
- Thu lại cả chương… (`qt/ProjectScreen.qml:126`) - web: `Thu lại cả chương…`
- Thêm giọng… (`qt/NowPlaying.qml:519`) - web: `Thêm giọng…`
- Tìm bìa… (`qt/EditBook.qml:247`) - web: `Tìm bìa…`
- Tìm tên… (`qt/SharedReadingsSettings.qml:61`) - web: `Tìm tên…`
- Đang gỡ… (`qt/StudioSettings.qml:153`) - web: `Đang gỡ…`
- Đang kiểm tra… (`qt/AdvancedUpdate.qml:116`) - web: `Đang kiểm tra…`
- Đang mở văn bản chương… (`qt/ReadAlongView.qml:318`) - web: `Đang mở văn bản chương…`
- Đang mở… (`qt/ConnectionChip.qml:54`) - web: `Đang mở…`
- Đang mở… (`qt/LibraryScreen.qml:418`) - web: `Đang mở…`
- Đang tải bản mới… (`qt/AdvancedUpdate.qml:94`) - web: `Đang tải bản mới…`
- Đang tải chương… (`qt/ChapterReader.qml:68`) - web: (không có)
- Đang tải âm thanh… (`qt/PlayerBar.qml:87`) - web: `Đang tải âm thanh…`
- Đang xem cuốn nào còn dùng giọng này… (`qt/VoiceModule.qml:400`) - web: `Đang xem cuốn nào còn dùng giọng này…`
- Đang đọc… (`qt/AddBook.qml:539`) - web: `Đang đọc…`
- Đổi tên chương… (`qt/BookPage.qml:147`) - web: `Đổi tên chương`, `Đổi tên chương…`
- Đổi ảnh bìa… (`qt/EditBook.qml:238`) - web: `Đổi ảnh bìa…`

## f. Phím tắt trong chú thích

Chú thích Qt ghi phím tắt sau nhãn; web ghép bằng `withShortcut(nhãn, phím)`. Phím khác nhau là khác HÀNH VI (phím thật trong `Main.qml` / `player.tsx`), không chỉ khác chữ.

| nhãn | Qt | web | nơi |
|---|---|---|---|
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

## Ngoài phạm vi hai màn

- ScreenHeader dùng arrow-left cho nút về một màn; cặp Quay lại + chevron-left của web là bước lùi trong hộp, khác ngữ cảnh.
- Chip trạng thái backend, khay/mini và các màn khác giữ báo cáo riêng trong bảng sinh tự động.

## Thư viện và Đang nghe - quyết định 28-10

Đã đọc từng nhãn web-only ban đầu (22 + 45); bảng từng nhãn, nơi đặt control, kiểm thử và phần còn lại nằm trong `../../report.md` (không commit).
Sau thay đổi: **Thư viện 22 -> 2**, **Đang nghe 45 -> 12**. Bộ đếm giữ nguyên tiêu chí; thêm tên các component QML mới vào đúng màn.
`Nghe gần đây / Tên sách / Tác giả / Mới thêm` hiện nằm trong menu Xếp theo (nguồn web là librarySort.ts, ngoài danh sách nguồn hiện có của scanner).

| Control | Nơi đặt và lý do trên desktop |
|---|---|
| Nghe tiếp / Chờ chương mới | Thẻ ngang trên bộ lọc; phân biệt mở trang sách và phát, không tự phát lại cuốn caughtUp. |
| Tất cả / Nghe dở / Chưa nghe / Xong | Cùng một hàng trước kết quả; khổ hẹp nhường hàng riêng cho nhóm lọc để không cắt chữ. |
| Xếp theo / Tìm sách | Cạnh bộ lọc; xếp có nhớ lựa chọn, ô tìm là lớp Back, nút x xoá trước rồi đóng. |
| Mở bộ | Một bìa cho nhóm; Modal danh sách tập cho chuột/bàn phím, Esc trả về đúng lưới. |
| Sách máy khác | Laptop và nguồn dưới tên bìa như web; không phủ lên chữ bìa. |
| Âm lượng / tắt tiếng | Trực tiếp trong … của trình phát; không mở thêm một tầng chỉ để kéo mức. Slider dùng Player chung và nhận mũi tên/Home/End. |
| Phím / Về chỗ vừa nghe / Thêm giọng… / mini | Trong …; tác vụ phụ không chiếm hàng transport. Phím mở hộp dùng chung; Thêm giọng đi thẳng nhóm Giọng đọc hiện có. |
| Chương / Đọc theo | Hai tab bảng phải ở cửa sổ rộng; hẹp vẫn có Chương cạnh hẹn giờ. Tab dùng trái/phải/Home/End và fade-through nội dung. |
| Đọc chương này | Menu chương và cả dòng chưa có audio; lớp đọc riêng để Back trả về đúng vị trí nghe. Bản chữ đọc /text, bản thu đọc /script. |
| Hẹn giờ | Cùng chỗ cũ; bổ sung Đặt lại, Dừng khi, Bật lại, lời nhỏ dần và tên đọc màn hình theo giây/phút. Bảng đo lại khi nội dung đổi và cuộn nếu thiếu chỗ. |
| Nghe tiếp / Nghe cuốn khác | Sau khi hết sách: tập kế và danh sách cuốn nghe được, loại cuốn đã xong/caughtUp; không tự nghe cuốn khác. |
| Gợi ý đọc | Trong … khi có gợi ý từ host; hộp gom dòng theo chương, công tắc Bỏ dòng ngắn gọn, trích nguyên dòng trong mô tả, không sửa chữ gốc. |

Các nhãn vẫn bị đếm chỉ web được phân biệt rõ:

| Nhãn | Quyết định / lý do |
|---|---|
| Nghe ngay {}; Đã làm sẵn; Đang chuẩn bị giọng đọc…; Máy này chưa có giọng đọc.; Nghe bằng giọng đọc.{} | **Để sau, không phải miễn trừ web-only.** Cần bộ phát TTS theo đoạn, cache, mốc chữ, giọng riêng và lỗi/huỷ. Qt Player hiện chỉ phát chương có audio; không thay đường audio đang thuộc job khác hay dựng nút giả. |
| Thiết bị phát | **Để sau, không phải miễn trừ web-only.** Đây là điều khiển/chuyển phiên phát từ xa, khác ghép thiết bị trong Cài đặt. Qt chưa có adapter queue/session/lease/sleep của luồng này. |
| Chưa có sách nào | Chỉ là fallback của LibraryScreen. Web desktop App.tsx truyền EmptyLibrary với Chưa có sách; Qt dùng đúng empty state desktop cùng các lối thêm/tạo/mở file. |
| Shift+←; Esc | Đã có hành vi và tooltip như web; scanner tách phần phím khỏi nhãn Qt nên vẫn báo. Ctrl+←/→ là alias sẵn của cửa sổ, Shift là phím giới thiệu cho người nghe. |
| Chưa có audio; Đang thu âm… | Đã render từ model.status của ChaptersModel.cpp; scanner chỉ quét QML nên không thấy literal C++. |
| Nghe tiếp · {} | Helper primaryListenLabel của trang sách bị tính vào Now Playing vì labels.ts được nạp trọn file. Trình phát dùng transport và nút tập kế, không cần lặp nút chính của trang sách. |
| Bấm; Chạm | Mảnh của readerHint, không phải control độc lập. Qt đã bấm chữ/câu để tua ở ReadAlongView; Chạm là biến thể coarse pointer của web, ngoài thiết kế chuột/bàn phím này. |

Icon mới (volume-1/2/x, keyboard, undo-2, lightbulb) sinh bằng `gen_lucide_icons.py --qml-only` từ đúng lucide-react 1.61.0 của package-lock; không vẽ tay, không đổi file Android.

Kiểm chứng lượt 28-10: `build.bat` trả 0 ở tiến trình cmd, 908 test qua, 0 lỗi; 1 ca âm tính glyph chỉ chạy khi opt-in được bỏ qua. Glyph audit 0 lỗi; 128 ảnh offscreen (32 trạng thái, sáng/tối, 1024/1920) và `parity_manifest.json` ở `D:/Novels/native_desk_proto/qtpar_shots/`. `quality_implementation_hash` trước/sau cùng `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`. Không commit; Lead duyệt. Các phần TTS và phát trên thiết bị khác vẫn để sau như đã ghi, không được tính là đã xây xong.
