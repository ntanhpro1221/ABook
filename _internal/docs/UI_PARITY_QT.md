# Lệch chữ, icon và bo góc giữa web máy tính và bản Qt

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Cùng nguồn chung như `docs/UI_PARITY.md` (web <-> điện thoại native): bo góc `Theme.qml` sinh bởi `desktop_qt/tools/gen_theme.py` từ DESIGN.md 5.5,
icon `LucidePaths.js` sinh bởi `scripts/gen_lucide_icons.py --qml`. Bảng dưới do `scripts/ui_parity_qt.py` sinh (`--check` báo lệch,
`tests/test_ui_parity_qt.py` chạy `--check`). Bộ đọc là heuristic trên mã nguồn: chữ dựng từ dữ liệu (tên chương, thời gian) không tính.

<!-- ui_parity_qt:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity_qt.py - không sửa tay, chạy lại script) -->

Quét: web máy tính 1237 chữ (984 khác nhau), 178 cặp nhãn-icon; Qt 897 chữ (667 khác nhau), 110 cặp nhãn-icon (icon dùng ở 152 chỗ). Khoá so lỏng như UI_PARITY.md (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối); phím tắt trong chú thích Qt (`Thu nhỏ (Esc)`) tách khỏi nhãn.

## a. Cùng việc, khác chữ

Nhãn ngắn Qt không có nguyên văn (khoá lỏng) ở web máy tính mà giống một nhãn web CÙNG MÀN chưa có ở Qt. 17 cặp; mỗi nhãn Qt lấy một nhãn web giống nhất. Giống không có nghĩa là cùng việc: người sửa xem mã hai bên trước khi đổi.

| màn | Qt | web | giống | nơi |
|---|---|---|---|---|
| Cài đặt | Cần cập nhật | Cần cập nhật {} | 1.00 | `qt/StudioSettings.qml:168` ~ `studio/StudioSetup.tsx:376` |
| Cài đặt | Dự phòng qua Bluetooth cho | Dự phòng qua Bluetooth cho {} | 1.00 | `qt/OtherComputersBluetooth.qml:27` ~ `desktop/OtherComputers.tsx:359` |
| Cài đặt | Lần cuối | Lần cuối {} | 1.00 | `qt/PhoneSyncDevice.qml:45` ~ `desktop/PhoneSync.tsx:406` |
| Cài đặt | Mã ghép nối: | Mã ghép nối: {} | 1.00 | `qt/PhoneSyncPairing.qml:71` ~ `desktop/PhoneSync.tsx:205` |
| Cài đặt | Mở Studio của | Mở Studio của {} | 1.00 | `qt/OtherComputersRow.qml:113` ~ `desktop/OtherComputers.tsx:205` |
| Cài đặt | Tên mới của mẫu “ | Tên mới của mẫu “{}” | 1.00 | `qt/BookTemplates.qml:193` ~ `desktop/BookTemplates.tsx:79` |
| Cài đặt | Đang tải | Đang tải {} | 1.00 | `qt/DevicesSkeleton.qml:8` ~ `listen/VieneuModuleCard.tsx:237` |
| Cài đặt | Điều khiển sản xuất từ | Điều khiển sản xuất từ {} | 1.00 | `qt/PhoneSyncDevice.qml:86` ~ `desktop/PhoneSync.tsx:417` |
| Cài đặt | Đã thôi ghép | Thôi ghép {}? | 0.86 | `qt/PhoneSync.qml:79` ~ `desktop/PhoneSync.tsx:440` |
| Cài đặt | Tự tắt sau | Tự tắt sau {} giờ | 0.83 | `qt/SettingsScreen.qml:48` ~ `shared/settingsSummary.ts:5` |
| Cài đặt | Đã chọn Bluetooth dự phòng | Dự phòng qua Bluetooth cho {} | 0.69 | `qt/OtherComputers.qml:84` ~ `desktop/OtherComputers.tsx:359` |
| Cài đặt | Không cài được Studio | Chưa cài Studio | 0.67 | `qt/StudioSettings.qml:50` ~ `studio/StudioSetup.tsx:129` |
| Trang sách | Thêm việc với sách | Việc với sách | 0.84 | `qt/BookPage.qml:53` ~ `listen/BookScreen.tsx:1059` |
| Đang nghe | Dừng khi hết chương này | Sẽ dừng khi hết chương này. | 1.00 | `qt/SleepPopover.qml:16` ~ `listen/PlayerViews.tsx:2085` |
| Đang nghe | Tuỳ chọn | Tuỳ chọn {} | 1.00 | `qt/ChapterRow.qml:100` ~ `listen/BookScreen.tsx:134` |
| Đang nghe | Giọng | Thêm giọng… | 0.67 | `qt/NowPlaying.qml:209` ~ `listen/PlayerViews.tsx:808` |
| Đang nghe | Chưa có chương sau để nghe | Các chương sau chưa có audio. | 0.59 | `qt/NowPlaying.qml:284` ~ `listen/labels.ts:145` |

## b. Cùng nhãn khác icon, cùng icon khác nhãn

**Cùng nhãn, khác icon** (6 nhãn Qt có icon mà icon ấy không đi với nhãn này ở bất cứ đâu trên web máy tính):

| nhãn | web | Qt | nơi |
|---|---|---|---|
| Bỏ ảnh bìa | trash | trash-2 | `qt/EditBook.qml:240` ~ `listen/EditBook.tsx:450` |
| Nghe từ đây | play | headphones | `qt/ReaderScreen.qml:387` ~ `listen/MorningRecap.tsx:207` |
| Quay lại | chevron-left | arrow-left | `qt/ScreenHeader.qml:12` ~ `listen/LineWishes.tsx:255` (+2) |
| Xoá | trash | trash-2 | `qt/EditBookMyMusic.qml:291` (+1) ~ `listen/MyMusic.tsx:183` |
| Xoá bài | trash | trash-2 | `qt/EditBookMyMusic.qml:305` (+1) ~ `listen/MyMusic.tsx:175` |
| Xoá khoá | trash | trash-2 | `qt/ProviderKey.qml:171` ~ `listen/VoiceSettings.tsx:216` |

**Cùng icon, khác nhãn** (20 cặp Qt; web cùng màn dùng cùng icon với nhãn khác):

| màn | icon | Qt | web cùng màn | nơi |
|---|---|---|---|---|
| Thêm sách | file-text | Chọn file sách | Đang đọc… / Chọn file sách | `qt/AddBook.qml:535` |
| Thêm sách | file-text | Đang đọc… | Đang đọc… / Chọn file sách | `qt/AddBook.qml:535` |
| Cài đặt | download | Cập nhật ABook | Cài Studio, Cài tiếp, Có ABook {} | `qt/AdvancedUpdate.qml:95` |
| Cài đặt | download | Đang tải bản mới… | Cài Studio, Cài tiếp, Có ABook {} | `qt/AdvancedUpdate.qml:95` |
| Trang sách | ellipsis | Thêm | Thêm tuỳ chọn cho {}, Tuỳ chọn {} | `qt/BookPage.qml:52` |
| Trang sách | circle-dashed | Chưa nghe | Chưa nghe / Đã nghe xong, Tạm dừng {} | `qt/BookPage.qml:150` |
| Trang sách | check-check | Đã nghe xong | Chưa nghe / Đã nghe xong, Chưa nghe xong / Đã nghe xong | `qt/BookPage.qml:150` |
| Sửa sách | image-plus | Chọn ảnh bìa… | Đổi ảnh bìa… / Chọn ảnh bìa… | `qt/EditBook.qml:220` |
| Sửa sách | image-plus | Đổi ảnh bìa… | Đổi ảnh bìa… / Chọn ảnh bìa… | `qt/EditBook.qml:220` |
| Sửa sách | file-down | Lưu thành… | Lưu | `qt/EditBookItems.qml:81` |
| Cài đặt | upload | Thêm nhạc của bạn | Đang thêm {}/{} / Thêm nhạc của bạn | `qt/MyMusicSettings.qml:145` |
| Cài đặt | upload | Đang thêm | Đang thêm {}/{} / Thêm nhạc của bạn | `qt/MyMusicSettings.qml:145` |
| Cài đặt | upload | Thêm nhạc của bạn | Đang thêm {}/{} / Thêm nhạc của bạn | `qt/MyMusicState.qml:105` |
| Đang nghe | moon | Hẹn giờ | {} trên {} | `qt/NowPlaying.qml:310` |
| Đang nghe | moon | Hết chương | {} trên {} | `qt/NowPlaying.qml:310` |
| Cài đặt | bluetooth | Dự phòng qua Bluetooth… | Dự phòng qua Bluetooth cho {} | `qt/OtherComputersBluetooth.qml:22` |
| Cài đặt | refresh-cw | Làm mới | Hỏi lại, Hỏi lại thư viện | `qt/PhoneDiagnostics.qml:67` |
| Cài đặt | save | Lưu nhật ký | Gửi nhật ký | `qt/PhoneDiagnostics.qml:68` |
| Cài đặt | download | Xem tiến độ cài | Cài Studio, Cài tiếp, Có ABook {} | `qt/StudioSettings.qml:131` |
| Cài đặt | play | Thử giọng | Dừng / Thử giọng | `qt/VoiceRow.qml:104` |

Số cặp: web máy tính 156, Qt 104. Nhãn Qt có icon (88): `Bấm để đổi tên chương`, `Bỏ cách đọc`, `Bỏ ảnh bìa`, `Bỏ “`, `Chi tiết`, `Chưa có chương sau để nghe`, `Chưa nghe`, `Chương`, `Chương sau`, `Chương trước`, `Chẩn đoán`, `Chọn`, `Chọn file sách`, `Chọn thư mục TXT`, `Chọn ảnh bìa…`, `Cài Studio`, `Cài đặt`, `Cập nhật ABook`, `Cỡ chữ và giãn dòng`, `Dừng`, `Dự phòng qua Bluetooth…`, `Ghép thiết bị mới`, `Gỡ Studio`, `Gửi nhật ký`, `Hẹn giờ`, `Hết chương`, `Hỏi lại thư viện`, `Khởi động lại`, `Kiểm tra`, `Làm mới`, `Lưu`, `Lưu nhật ký`, `Lưu thay đổi`, `Lưu thành…`, `Mở cuốn đó`, `Mở file sách`, `Mở rộng`, `Mở Studio`, `Mở tab Nhạc nền`, `Mở thư mục nhật ký`, `Nghe từ đây`, `Nghe từ đầu chương`, `Nhạc nền`, `Phát`, `Quay lại`, `Studio`, `Sửa cách đọc`, `Sửa sách`, `Sửa thông tin`, `Thu gọn`, `Thu nhỏ`, `Thêm`, `Thêm bản riêng`, `Thêm nhạc của bạn`, `Thêm sách`, `Thêm vào thư viện`, `Thôi ghép`, `Thư viện`, `Thả để thêm sách`, `Thử giọng`, `Thử lại`, `Tìm`, `Tìm bìa…`, `Tìm máy trong mạng`, `Tạm dừng`, `Tạo sách nói`, `Tới câu đang nghe`, `Vẫn cài`, `Vẫn thêm bản mới`, `Về Cài đặt`, `Về Thư viện`, `Về trang sách`, `Xem tiến độ cài`, `Xoá`, `Xoá bài`, `Xoá khoá`, `Xác nhận gỡ`, `Đang gỡ…`, `Đang mở…`, `Đang thêm`, `Đang tải bản mới…`, `Đang đọc…`, `Đã nghe xong`, `Đóng`, `Đọc chương này`, `Đổi bài`, `Đổi tên chương…`, `Đổi ảnh bìa…`.

## c. Nhãn chỉ có một bên, theo màn

Nhãn ngắn (<= 6 chữ). **Chỉ Qt**: không có ở web cùng màn; `*` = web có ở màn khác. **Chỉ web**: nhãn web của màn không có ở đâu trong Qt - phần lớn là tính năng Qt chưa làm (bản thử), chỉ đếm và kể 15 đầu.

### Thư viện

- chỉ Qt (3): Chưa mở được ABook (`qt/LibraryScreen.qml:207`); Chưa tải được thư viện (`qt/LibraryScreen.qml:207`); Thử lại* (`qt/LibraryScreen.qml:224`)
- chỉ web (22): Nghe dở (`31`); Tất cả (`31`); Nghe ngay {} (`163`); Nghe {} (`163`); Tạm dừng {} (`163`); Đọc {} (`163`); Đang nghe (`227`); Chờ chương mới (`246`); Nghe tiếp {}{} (`248`); Sách (`334`); Mở bộ {} (`376`); Có sách trên máy khác (`384`); Chưa có sách nào (`519`); Lọc sách (`532`); Nghe xong (`534`); ...

### Thanh phát

- chỉ Qt (0): (không có)
- chỉ web (30): Vị trí trong chương (`181`); Shift+← (`260`); Sắp tắt · (`1265`); Nghe kiểm (`1335`); Đã nghe hết phần đã có (`1337`); Đọc bằng (`1380`); Chọn giọng khác (`1400`); Đóng lời báo (`1407`); Đã nghe chương này (`1434`); Thêm tuỳ chọn (`1537`); Trình phát (`1577`); Mở màn hình đang nghe (`1589`); Đóng trình phát (`1667`); Thiết bị phát (`1668`); Đang chuẩn bị giọng đọc… (`9`); ...

### Đang nghe

- chỉ Qt (8): Tuỳ chọn (`qt/ChapterRow.qml:100`); Bìa (`qt/NowPlaying.qml:175`); Giọng (`qt/NowPlaying.qml:209`); Thử lại* (`qt/NowPlaying.qml:243`); Chưa có chương sau để nghe (`qt/NowPlaying.qml:284`); Danh sách chương* (`qt/NowPlaying.qml:324`); Nhạc nền* (`qt/NowPlaying.qml:335`); Dừng khi hết chương này (`qt/SleepPopover.qml:16`)
- chỉ web (46): Tạm dừng {} (`84`); Đọc {} (chưa có audio) (`103`); Đã làm sẵn (`119`); Tuỳ chọn {} (`134`); Shift+← (`260`); Lùi {} giây (`261`); Tới {} giây (`286`); Phím (`478`); Thêm giọng… (`808`); Bật lại (`1004`); Tiếng nhỏ dần (`1012`); Dừng khi (`1097`); Đặt lại (`1124`); Âm lượng (`1181`); Bật tiếng (`1193`); ...

### Đọc theo

- chỉ Qt (0): (không có)
- chỉ web (0): (không có)

### Màn đọc

- chỉ Qt (0): (không có)
- chỉ web (3): Tìm trong sách (`359`); Máy này chưa có giọng đọc. (`121`); Nghe bằng giọng đọc.{} (`123`)

### Trang sách

- chỉ Qt (3): Thêm* (`qt/BookPage.qml:52`); Thêm việc với sách (`qt/BookPage.qml:53`); Chưa lấy được danh sách chương. (`qt/BookPage.qml:284`)
- chỉ web (72): Tạm dừng {} (`84`); Đọc {} (chưa có audio) (`103`); Đã làm sẵn (`119`); Tuỳ chọn {} (`134`); Dừng nghe thử (`228`); Chưa có giọng (`312`); Chờ áp dụng (`317`); Đang chờ máy làm sách (`317`); Bỏ gộp {} vào {} (`327`); Bỏ gộp (`332`); Nghe {} nói (`345`); Đổi giọng {} (`347`); Thêm tuỳ chọn cho {} (`352`); Gộp vào người khác… (`364`); Đổi giới tính (`374`); ...

### Cài đặt

- chỉ Qt (98): Chọn nơi lưu gói nhật ký (`qt/AdvancedDiagnostics.qml:12`); Chưa lưu được gói nhật ký (`qt/AdvancedDiagnostics.qml:17`); Đã lưu gói nhật ký (`qt/AdvancedDiagnostics.qml:17`); Đã lưu gói nhật ký trong (`qt/AdvancedDiagnostics.qml:17`); Chưa dọn được bản đọc (`qt/AdvancedStorage.qml:22`); Đã dọn bản đọc đã làm (`qt/AdvancedStorage.qml:22`); Chưa cập nhật được (`qt/AdvancedUpdate.qml:30`); Chất lượng cao (`qt/BookTemplates.qml:12`); Cân bằng (`qt/BookTemplates.qml:12`); Tên mẫu tối đa (`qt/BookTemplates.qml:46`); Đã có mẫu tên “ (`qt/BookTemplates.qml:46`); Đặt cho mẫu một cái tên (`qt/BookTemplates.qml:46`); Không làm được lúc này. (`qt/BookTemplates.qml:61`); Không lưu được mẫu (`qt/BookTemplates.qml:61`); Đã xoá mẫu “ (`qt/BookTemplates.qml:103`); Tên mới của mẫu “ (`qt/BookTemplates.qml:193`); Đang tải (`qt/DevicesSkeleton.qml:8`); Chưa lưu được cài đặt (`qt/ListenSave.qml:8`); Phím một chữ cái đang tắt (`qt/LookShortcuts.qml:11`); Chương trước / sau (`qt/LookShortcuts.qml:14`); Giảm / tăng tốc độ đọc (`qt/LookShortcuts.qml:14`); Lùi / tới 15 giây (`qt/LookShortcuts.qml:14`); Phát / tạm dừng (`qt/LookShortcuts.qml:14`); Thu nhỏ màn hình đang nghe (`qt/LookShortcuts.qml:14`); Tắt / bật tiếng (`qt/LookShortcuts.qml:14`); Xem các phím tắt này (`qt/LookShortcuts.qml:14`); Tìm hiểu thêm (`qt/MoreInfo.qml:8`); Bật đo cảm xúc (`qt/MyMusicModule.qml:36`); Tắt đo cảm xúc (`qt/MyMusicModule.qml:36`); Phân tích nhạc (`qt/MyMusicModule.qml:72`); Phân tích (`qt/MyMusicModule.qml:116`); Cảm xúc chính xác (`qt/MyMusicModule.qml:144`); Đang thêm nhạc thì dừng (`qt/MyMusicSettings.qml:71`); Không xoá được bài này (`qt/MyMusicSettings.qml:84`); Đã xoá khỏi Nhạc của tôi (`qt/MyMusicSettings.qml:84`); Không đổi được (`qt/MyMusicSettings.qml:95`); Chọn nhạc của bạn (`qt/MyMusicSettings.qml:119`); Đang thêm* (`qt/MyMusicSettings.qml:144`); Kết nối Wi-Fi (`qt/OtherComputers.qml:33`); Chưa chọn được (`qt/OtherComputers.qml:84`); Không dùng Bluetooth dự phòng nữa (`qt/OtherComputers.qml:84`); Đã chọn Bluetooth dự phòng (`qt/OtherComputers.qml:84`); Không tìm được (`qt/OtherComputers.qml:93`); Chưa thôi ghép được (`qt/OtherComputers.qml:119`); Dự phòng qua Bluetooth cho (`qt/OtherComputersBluetooth.qml:27`); Mở Studio của (`qt/OtherComputersRow.qml:113`); Chưa lưu được nhật ký (`qt/PhoneDiagnostics.qml:49`); Chọn nơi lưu nhật ký (`qt/PhoneDiagnostics.qml:49`); Đã lưu nhật ký (`qt/PhoneDiagnostics.qml:49`); Làm mới* (`qt/PhoneDiagnostics.qml:67`); Lưu nhật ký* (`qt/PhoneDiagnostics.qml:68`); Chi tiết kỹ thuật* (`qt/PhoneDiagnostics.qml:105`); Chưa bật được đồng bộ (`qt/PhoneSync.qml:52`); Đã tắt chia sẻ qua Wi-Fi (`qt/PhoneSync.qml:52`); Đã thôi ghép (`qt/PhoneSync.qml:79`); Đã đổi tên thành “ (`qt/PhoneSync.qml:87`); Lần cuối (`qt/PhoneSyncDevice.qml:45`); Điều khiển sản xuất từ (`qt/PhoneSyncDevice.qml:86`); Mã ghép nối: (`qt/PhoneSyncPairing.qml:71`); Chưa dùng được (`qt/ProviderKey.qml:20`); Dùng được · (`qt/ProviderKey.qml:20`); Dán khoá trước đã. (`qt/ProviderKey.qml:31`); Khoá chưa dùng được. (`qt/ProviderKey.qml:40`); Đã lưu (`qt/ProviderKey.qml:139`); Đã đổi thư mục thư viện (`qt/SettingsAdvanced.qml:14`); Chọn thư mục thư viện (`qt/SettingsAdvanced.qml:62`); Tự chọn nhạc nền (`qt/SettingsListen.qml:23`); Đã bật tự chọn nhạc nền (`qt/SettingsListen.qml:28`); Đã tắt tự chọn nhạc nền (`qt/SettingsListen.qml:28`); Giấy* (`qt/SettingsLook.qml:23`); Ngà* (`qt/SettingsLook.qml:23`); Đêm* (`qt/SettingsLook.qml:23`); Có bản mới (`qt/SettingsScreen.qml:48`); Không tự lùi (`qt/SettingsScreen.qml:48`); Phiên bản (`qt/SettingsScreen.qml:48`); Tự tắt sau (`qt/SettingsScreen.qml:48`); Có ABook* (`qt/SettingsScreen.qml:106`); Tự tắt (`qt/SettingsSleep.qml:31`); Mỗi lần nghe thêm (`qt/SettingsSleep.qml:56`); Số phút nghe thêm (`qt/SettingsSleep.qml:57`); Lúc đang nhỏ dần: (`qt/SettingsSleep.qml:58`); Nhỏ dần (`qt/SettingsSleep.qml:65`); Độ dài nhỏ dần (`qt/SettingsSleep.qml:66`); Đã bỏ “ (`qt/SharedReadingsSettings.qml:33`); Bỏ “ (`qt/SharedReadingsSettings.qml:103`); Không cài được Studio (`qt/StudioSettings.qml:50`); Chưa gỡ được Studio (`qt/StudioSettings.qml:59`); Đã gỡ Studio (`qt/StudioSettings.qml:59`); Cần cập nhật (`qt/StudioSettings.qml:168`); Mất (`qt/StudioSettings.qml:168`); Chưa tải được (`qt/VoiceModule.qml:54`); Chưa gỡ được (`qt/VoiceModule.qml:55`); Chưa huỷ được việc tải (`qt/VoiceModule.qml:155`); Chưa đổi được cách đọc (`qt/VoiceModule.qml:281`); Gỡ “ (`qt/VoiceModule.qml:397`); Thử* (`qt/VoiceRow.qml:107`); Chưa đổi được tốc độ giọng (`qt/VoiceSpeed.qml:20`); Chưa tải được bản nhanh hơn (`qt/VoiceSpeed.qml:93`)
- chỉ web (41): Tên mới của mẫu “{}” (`79`); Mở Studio của {} (`205`); Chẩn đoán {} (`216`); Hỏi lại (`229`); Thôi ghép {} (`232`); Dự phòng qua Bluetooth cho {} (`359`); Bluetooth (`368`); Mã ghép nối: {} (`205`); Lần cuối {} (`406`); Điều khiển sản xuất từ {} (`417`); ABook {} (`180`); Mẫu thiết lập (`383`); Có ABook {} (`532`); ABook{} là bản mới nhất. (`21`); Đang thêm {}/{} (`146`); ...

### Thêm sách

- chỉ Qt (21): Chưa đọc lại được file (`qt/AddBook.qml:170`); Không mở được file sách (`qt/AddBook.qml:210`); Không mở được file sách này. (`qt/AddBook.qml:221`); Chưa thêm được sách (`qt/AddBook.qml:301`); Đã thêm sách vào thư viện (`qt/AddBook.qml:301`); Bỏ qua* (`qt/AddBook.qml:388`); Thêm bản riêng (`qt/AddBook.qml:422`); Vẫn thêm bản mới (`qt/AddBook.qml:422`); Xong* (`qt/AddBook.qml:428`); Còn (`qt/AddBook.qml:479`); Không đọc số chú thích* (`qt/AddBook.qml:868`); Đọc lời chú ở cuối chương* (`qt/AddBook.qml:877`); Bỏ lời chú* (`qt/AddBook.qml:885`); Bỏ dòng này khỏi phần đọc* (`qt/AddBook.qml:954`); Tất cả file (*) (`qt/AddBook.qml:1006`); Đưa vào sách: (`qt/ImportChapters.qml:99`); Bấm để đổi tên chương* (`qt/ImportChapters.qml:134`); Tên chương* (`qt/ImportChapters.qml:170`); Thả để thêm sách* (`qt/ImportDrop.qml:52`); Thử lại* (`qt/ImportError.qml:50`); Đang tải (`qt/ImportSkeleton.qml:10`)
- chỉ web (9): Đóng khi còn sách chưa thêm (`585`); Đang thêm {} (`802`); Các file đã chọn (`825`); Chờ (`833`); Đang xem (`833`); Sách {}/{} (`87`); Đã thêm {} sách (`133`); Không thêm cuốn nào (`140`); Tách theo {} dòng “Chương N” (`180`)

### Sửa sách

- chỉ Qt (48): Chưa chỉnh được nhạc nền (`qt/BookMusicSettings.qml:32`); Tìm ảnh bìa (`qt/EditBook.qml:39`); Chưa đổi được tên sách (`qt/EditBook.qml:108`); Đã đổi tên sách (`qt/EditBook.qml:108`); Chưa đổi được tác giả (`qt/EditBook.qml:112`); Đã bỏ tên tác giả (`qt/EditBook.qml:112`); Đã đổi tác giả (`qt/EditBook.qml:112`); Chưa đặt được ảnh bìa (`qt/EditBook.qml:116`); Đã đặt ảnh bìa (`qt/EditBook.qml:116`); Chưa bỏ được ảnh bìa (`qt/EditBook.qml:119`); Chưa bỏ được thay đổi (`qt/EditBook.qml:122`); Không đọc được file ảnh (`qt/EditBook.qml:385`); Thử lại* (`qt/EditBookError.qml:45`); Lưu thay đổi* (`qt/EditBookItems.qml:70`); Lưu thành…* (`qt/EditBookItems.qml:80`); Đang thêm nhạc thì dừng (`qt/EditBookMyMusic.qml:65`); Không xoá được bài này (`qt/EditBookMyMusic.qml:78`); Đã xoá khỏi Nhạc của tôi (`qt/EditBookMyMusic.qml:78`); Chọn nhạc của bạn (`qt/EditBookMyMusic.qml:111`); Nhạc của tôi* (`qt/EditBookMyMusic.qml:120`); Chưa có bài nào* (`qt/EditBookMyMusic.qml:121`); Thêm nhạc của bạn* (`qt/EditBookMyMusic.qml:130`); Đang thêm* (`qt/EditBookMyMusic.qml:130`); Phân tích nhạc (`qt/EditBookMyMusic.qml:147`); Huỷ* (`qt/EditBookMyMusic.qml:163`); Phân tích (`qt/EditBookMyMusic.qml:171`); Nhạc riêng* (`qt/EditBookMyMusic.qml:183`); Đang tải nhạc riêng* (`qt/EditBookMyMusic.qml:189`); Xoá* (`qt/EditBookMyMusic.qml:291`); Xoá bài* (`qt/EditBookMyMusic.qml:305`); Giữ lại* (`qt/EditBookMyMusic.qml:312`); Chưa bỏ được cách đọc (`qt/EditBookReadings.qml:27`); Chưa lưu được cách đọc (`qt/EditBookReadings.qml:27`); Đang tải cách đọc* (`qt/EditBookReadings.qml:67`); Sửa cách đọc* (`qt/EditBookReadings.qml:111`); Bỏ cách đọc (`qt/EditBookReadings.qml:121`); Cách đọc cho (`qt/EditBookReadings.qml:140`); Lưu cho cả cuốn* (`qt/EditBookReadings.qml:151`); Đọc như chữ trong sách* (`qt/EditBookReadings.qml:159`); Chưa đổi được tên chương (`qt/EditBookRename.qml:29`); Đã đổi tên chương: (`qt/EditBookRename.qml:29`); Chưa lưu được file sách (`qt/EditBookSaveAs.qml:25`); Đã lưu file sách (`qt/EditBookSaveAs.qml:25`); Chọn nơi lưu file sách (`qt/EditBookSaveAs.qml:51`); Loại file (`qt/EditBookSaveAs.qml:59`); Đang tải (`qt/EditBookSkeleton.qml:10`); Đang tải bài nhạc* (`qt/EditBookSwap.qml:36`); Chọn* (`qt/EditBookSwap.qml:91`)
- chỉ web (1): Bỏ mọi thay đổi ({}) (`486`)

### Thanh bên

- chỉ Qt (9): Trạng thái ABook (`qt/ConnectionChip.qml:9`); Gặp lỗi (`qt/ConnectionChip.qml:54`); Sẵn sàng (`qt/ConnectionChip.qml:54`); Đang mở…* (`qt/ConnectionChip.qml:54`); Bản (`qt/ConnectionPopover.qml:76`); Khởi động lại (`qt/ConnectionPopover.qml:88`); Mở thư mục nhật ký (`qt/ConnectionPopover.qml:96`); Mở rộng (`qt/Sidebar.qml:84`); Thu gọn* (`qt/Sidebar.qml:84`)
- chỉ web (9): Đang tải tiến độ (`99`); Đang chờ {} (`111`); Đang dừng (`112`); Đang tạm dừng (`112`); Tiến độ: {} (`119`); Chờ (`120`); Xem tất cả (`125`); Bấm để cập nhật (`147`); Điều hướng chính (`166`)

### Studio máy khác

- chỉ Qt (2): Studio* (`qt/StudioScreen.qml:67`); Studio chưa mở trong bản này. (`qt/StudioScreen.qml:95`)
- chỉ web (1): Đang mở Studio của {} (`52`)

### Thanh tiêu đề

- chỉ Qt (2): ABook* (`qt/Main.qml:10`); Chưa tải được bản mới (`qt/Main.qml:166`)
- chỉ web (2): Tới nội dung (`228`); Điều hướng (`248`)

### Chung

- chỉ Qt (3): Không làm được lúc này. (`qt/Api.qml:83`); Quay lại* (`qt/ScreenHeader.qml:12`); Đóng thông báo (`qt/Toast.qml:233`)
- chỉ web (4): Đang mở ABook (`578`); Đang tải điều hướng (`578`); Xem các tab trước (`514`); Xem các tab sau (`519`)

File QML chưa xếp màn (thêm vào SCREENS): `desktop_qt/qml/MusicCredit.qml`, `desktop_qt/qml/MusicPopover.qml`.

## d. Bo góc QML không theo token

Hợp lệ: `Theme.radiusControl / radiusCover / radiusSheet` (DESIGN.md 5.5, `desktop_qt/tools/gen_theme.py`), `0`, tròn (`width / 2`, `height / 2`), lấy lại bo khung chứa (`parent.radius`), vòng đồng tâm ngoài (`Theme.radiusCover + 8` của bóng, vòng tiêu điểm). Còn lại (0):

| nơi | radius |
|---|---|
| (không có) | |

## e. Dấu thanh kiểu mới và dấu ba chấm cuối nhãn

**Dấu thanh kiểu mới (`òa óa úy`)** trong chữ Qt (0); web và native đa số viết kiểu cũ (`oà oá uý`, UI_PARITY.md d2):

- (không có)

**Nhãn kết thúc bằng `…` / `...`** (19): DESIGN.md chỉ cho `…` ở chữ đang chờ ("Đang mở…"), không cho nhãn nút.

- Bỏ mọi thay đổi… (`qt/EditBook.qml:319`) - web: `Bỏ mọi thay đổi…`
- Chọn thư mục… (`qt/EditBookSaveAs.qml:80`) - web: `Chọn thư mục`, `Chọn thư mục…`
- Chọn ảnh bìa… (`qt/EditBook.qml:219`) - web: `Chọn ảnh bìa…`
- Dự phòng qua Bluetooth… (`qt/OtherComputersBluetooth.qml:25`) - web: `Dự phòng qua Bluetooth…`
- Lưu thành… (`qt/EditBookItems.qml:80`) - web: `Lưu thành…`
- Lưu thành… (`qt/EditBookSaveAs.qml:16`) - web: `Lưu thành…`
- Tìm bìa… (`qt/EditBook.qml:228`) - web: `Tìm bìa…`
- Tìm tên… (`qt/SharedReadingsSettings.qml:61`) - web: `Tìm tên…`
- Đang gỡ… (`qt/StudioSettings.qml:152`) - web: `Đang gỡ…`
- Đang kiểm tra… (`qt/AdvancedUpdate.qml:116`) - web: `Đang kiểm tra…`
- Đang mở văn bản chương… (`qt/ReadAlongView.qml:395`) - web: `Đang mở văn bản chương…`
- Đang mở… (`qt/ConnectionChip.qml:54`) - web: `Đang mở…`
- Đang mở… (`qt/LibraryScreen.qml:241`) - web: `Đang mở…`
- Đang tải bản mới… (`qt/AdvancedUpdate.qml:94`) - web: `Đang tải bản mới…`
- Đang tải âm thanh… (`qt/PlayerBar.qml:87`) - web: `Đang tải âm thanh…`
- Đang xem cuốn nào còn dùng giọng này… (`qt/VoiceModule.qml:398`) - web: `Đang xem cuốn nào còn dùng giọng này…`
- Đang đọc… (`qt/AddBook.qml:534`) - web: `Đang đọc…`
- Đổi tên chương… (`qt/BookPage.qml:159`) - web: `Đổi tên chương`, `Đổi tên chương…`
- Đổi ảnh bìa… (`qt/EditBook.qml:219`) - web: `Đổi ảnh bìa…`

## f. Phím tắt trong chú thích

Chú thích Qt ghi phím tắt sau nhãn; web ghép bằng `withShortcut(nhãn, phím)`. Phím khác nhau là khác HÀNH VI (phím thật trong `Main.qml` / `player.tsx`), không chỉ khác chữ.

| nhãn | Qt | web | nơi |
|---|---|---|---|
| Chương trước | `Ctrl+←` | `Shift+←` | `qt/NowPlaying.qml:273` |
| Chương sau | `Ctrl+→` | `Shift+→` | `qt/NowPlaying.qml:284` |
| Phát | `Space` | (không ghi) | `qt/PlayButton.qml:13` |
| Tạm dừng | `Space` | (không ghi) | `qt/PlayButton.qml:13` |
| Về trang sách | `Esc` | (không ghi) | `qt/ReaderScreen.qml:175` |
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
