# Lệch chữ, icon và bo góc giữa web máy tính và bản Qt

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Cùng nguồn chung như `docs/UI_PARITY.md` (web <-> điện thoại native): bo góc `Theme.qml` sinh bởi `desktop_qt/tools/gen_theme.py` từ DESIGN.md 5.5,
icon `LucidePaths.js` sinh bởi `scripts/gen_lucide_icons.py --qml`. Bảng dưới do `scripts/ui_parity_qt.py` sinh (`--check` báo lệch,
`tests/test_ui_parity_qt.py` chạy `--check`). Bộ đọc là heuristic trên mã nguồn: chữ dựng từ dữ liệu (tên chương, thời gian) không tính.

<!-- ui_parity_qt:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity_qt.py - không sửa tay, chạy lại script) -->

Quét: web máy tính 1662 chữ (1302 khác nhau), 240 cặp nhãn-icon; Qt 2233 chữ (1672 khác nhau), 185 cặp nhãn-icon (icon dùng ở 260 chỗ). Khoá so lỏng như UI_PARITY.md (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối); phím tắt trong chú thích Qt (`Thu nhỏ (Esc)`) tách khỏi nhãn.

## a. Cùng việc, khác chữ

Nhãn ngắn Qt không có nguyên văn (khoá lỏng) ở web máy tính mà giống một nhãn web CÙNG MÀN chưa có ở Qt. 36 cặp; mỗi nhãn Qt lấy một nhãn web giống nhất. Giống không có nghĩa là cùng việc: người sửa xem mã hai bên trước khi đổi.

| màn | Qt | web | giống | nơi |
|---|---|---|---|---|
| Cài đặt | Dự phòng qua Bluetooth cho | Dự phòng qua Bluetooth cho {} | 1.00 | `qt/OtherComputersBluetooth.qml:27` ~ `desktop/OtherComputers.tsx:359` |
| Cài đặt | Hết hạn sau {}:{} | Hết hạn sau | 1.00 | `qt/PhoneSyncPairing.qml:80` ~ `desktop/PhoneSync.tsx:213` |
| Cài đặt | Mã ghép nối: | Mã ghép nối: {} | 1.00 | `qt/PhoneSyncPairing.qml:71` ~ `desktop/PhoneSync.tsx:205` |
| Cài đặt | Mở Studio của | Mở Studio của {} | 1.00 | `qt/OtherComputersRow.qml:113` ~ `desktop/OtherComputers.tsx:205` |
| Cài đặt | Điều khiển sản xuất từ | Điều khiển sản xuất từ {} | 1.00 | `qt/PhoneSyncDevice.qml:86` ~ `desktop/PhoneSync.tsx:417` |
| Cài đặt | Địa chỉ: {} | Địa chỉ: | 1.00 | `qt/PhoneSyncPairing.qml:57` ~ `desktop/PhoneSync.tsx:199` |
| Cài đặt | Đã chọn Bluetooth dự phòng | Dự phòng qua Bluetooth cho {} | 0.69 | `qt/OtherComputers.qml:85` ~ `desktop/OtherComputers.tsx:359` |
| Cài đặt | Đã ghép {} | Mã ghép nối: {} | 0.67 | `qt/OtherComputers.qml:62` ~ `desktop/PhoneSync.tsx:205` |
| Cài đặt | Có bản mới {} | ABook{} là bản mới nhất. | 0.60 | `qt/SettingsScreen.qml:59` ~ `desktop/updateCheck.ts:21` |
| Studio dự án | Không khởi động được: {} | Không khởi động được: | 1.00 | `qt/ProjectScreen.qml:320` ~ `studio/ProjectScreen.tsx:194` |
| Studio dự án | Chưa ghi được | Chưa tải được | 0.85 | `qt/StudioStore.qml:227` ~ `studio/ProjectScreen.tsx:1434` |
| Studio dự án | Chưa xoá được | Chưa tải được | 0.85 | `qt/StudioStore.qml:186` ~ `studio/ProjectScreen.tsx:1434` |
| Studio dự án | Giọng kể {} | Đổi giọng kể | 0.80 | `qt/StudioLogic.js:167` ~ `studio/ProjectScreen.tsx:264` |
| Studio dự án | Không dừng được | Không khởi động được: | 0.80 | `qt/StudioStore.qml:152` ~ `studio/ProjectScreen.tsx:194` |
| Studio dự án | Không làm tiếp được | Làm tiếp từ chỗ ấy | 0.59 | `qt/StudioStore.qml:141` ~ `studio/ProjectScreen.tsx:378` |
| Studio dự án | Đang làm tiếp | Làm tiếp từ chỗ ấy | 0.52 | `qt/StudioLogic.js:208` ~ `studio/ProjectScreen.tsx:378` |
| Studio tạo sách | Tạo trên {} | Tạo trên | 1.00 | `qt/StudioSetupNotice.qml:95` ~ `studio/StudioSetup.tsx:102` |
| Studio tạo sách | Dùng lại {} | Dùng lại | 1.00 | `qt/NewVoice.qml:209` ~ `studio/NewProjectScreen.tsx:1269` |
| Studio tạo sách | Máy thấy {} | Máy thấy | 1.00 | `qt/NewVolumes.qml:57` ~ `studio/VolumeSplit.tsx:102` |
| Studio tạo sách | Tách theo {} | Tách theo | 1.00 | `qt/NewHints.qml:86` ~ `studio/NewProjectScreen.tsx:899` |
| Studio tạo sách | Bản thử nghiệm | Bản khác (thử nghiệm) | 0.85 | `qt/NewProjectLogic.js:369` ~ `studio/AnalysisModelPicker.tsx:103` |
| Studio tạo sách | Không tách được | Không đọc được: {} | 0.83 | `qt/NewProjectStore.qml:329` ~ `studio/NewProjectScreen.tsx:1759` |
| Studio tạo sách | Đã có mẫu tên “{}” | Đã có mẫu “ | 0.82 | `qt/TemplateLogic.js:51` ~ `studio/TemplateBar.tsx:180` |
| Studio tạo sách | Chia thành | Tách thành | 0.80 | `qt/NewProjectLogic.js:488` ~ `studio/NewProjectScreen.tsx:912` |
| Studio tạo sách | Cập nhật {} | Cần cập nhật {} | 0.80 | `qt/StudioSetupLogic.js:61` ~ `studio/StudioSetup.tsx:376` |
| Studio tạo sách | Máy này {}. | Máy thấy | 0.80 | `qt/StudioSetupLogic.js:16` ~ `studio/VolumeSplit.tsx:102` |
| Studio tạo sách | Nhanh nhất | Nhanh | 0.67 | `qt/NewProjectLogic.js:9` ~ `studio/NewProjectScreen.tsx:93` |
| Studio tạo sách | Số tham khảo từ đâu | Tham khảo: | 0.64 | `qt/NewProjectLogic.js:513` ~ `studio/NewProjectScreen.tsx:1385` |
| Studio tạo sách | Đã bỏ {} | Sẽ bỏ | 0.60 | `qt/NewProjectStore.qml:261` ~ `studio/NewProjectScreen.tsx:799` |
| Studio tạo sách | Đã dừng gửi - {} | Dừng nghe {} | 0.60 | `qt/NewProjectStore.qml:312` ~ `studio/NewProjectScreen.tsx:992` |
| Thư viện | Trên {} | Thêm {} | 0.50 | `qt/BookCell.qml:122` ~ `listen/LibraryScreen.tsx:203` |
| Trang sách | Đã nghe {} | Đã nghe | 1.00 | `qt/BookPage.qml:316` ~ `listen/BookScreen.tsx:1023` |
| Trang sách | Thêm việc với sách | Việc với sách | 0.84 | `qt/BookPage.qml:55` ~ `listen/BookScreen.tsx:1059` |
| Trang sách | Không hoàn tác được | Không phát được | 0.82 | `qt/CastModal.qml:19` ~ `listen/BookScreen.tsx:1027` |
| Trang sách | Chờ áp dụng: đổi sang | Chờ áp dụng: giọng | 0.81 | `qt/CastVoice.qml:144` ~ `listen/BookScreen.tsx:441` |
| Đang nghe | Tắt sau {} | Tắt sau | 1.00 | `qt/SleepPopover.qml:19` ~ `listen/PlayerViews.tsx:1097` |

## b. Cùng nhãn khác icon, cùng icon khác nhãn

**Cùng nhãn, khác icon** (5 nhãn Qt có icon mà icon ấy không đi với nhãn này ở bất cứ đâu trên web máy tính):

| nhãn | web | Qt | nơi |
|---|---|---|---|
| Chi tiết | info | chevron-right | `qt/MyMusicDetails.qml:28` (+1) ~ `studio/ProjectScreen.tsx:789` |
| Quay lại | chevron-left | arrow-left | `qt/ScreenHeader.qml:12` ~ `listen/LineWishes.tsx:255` (+2) |
| Thêm tuỳ chọn cho {} | more-horizontal | ellipsis | `qt/CastPerson.qml:176` ~ `listen/BookScreen.tsx:357` |
| Tuỳ chọn Studio | more-horizontal | ellipsis | `qt/ProjectsScreen.qml:83` ~ `studio/ProjectsScreen.tsx:236` |
| Tạm dừng {} | check, circle-dashed, play | pause | `qt/BookCell.qml:76` ~ `listen/BookScreen.tsx:94` (+2) |

**Cùng icon, khác nhãn** (48 cặp Qt; web cùng màn dùng cùng icon với nhãn khác):

| màn | icon | Qt | web cùng màn | nơi |
|---|---|---|---|---|
| Thêm sách | file-text | Chọn file sách | Đang đọc… / Chọn file sách | `qt/AddBook.qml:540` |
| Thêm sách | file-text | Đang đọc… | Đang đọc… / Chọn file sách | `qt/AddBook.qml:540` |
| Cài đặt | download | Cập nhật ABook | Cài Studio, Cài tiếp, Có ABook {} | `qt/AdvancedUpdate.qml:95` |
| Cài đặt | download | Đang tải bản mới… | Cài Studio, Cài tiếp, Có ABook {} | `qt/AdvancedUpdate.qml:95` |
| Thư viện | play | Nghe {} | Đọc {} | `qt/BookCell.qml:76` |
| Thư viện | pause | Tạm dừng {} | Đọc {} | `qt/BookCell.qml:76` |
| Thư viện | laptop | Có sách trên máy khác | tập, {}, đã tải về máy này | `qt/BookCell.qml:125` |
| Thư viện | laptop | Trên {} | tập, {}, đã tải về máy này | `qt/BookCell.qml:125` |
| Trang sách | circle-dashed | Chưa nghe | Chưa nghe / Đã nghe xong, Tạm dừng {} | `qt/BookPage.qml:192` |
| Trang sách | check-check | Đã nghe xong | Chưa nghe / Đã nghe xong, Chưa nghe xong / Đã nghe xong | `qt/BookPage.qml:192` |
| Trang sách | git-merge | Gộp | Gộp vào người khác… | `qt/CastMerge.qml:162` |
| Trang sách | play | Dừng | Nghe tiếp từ, Nghe từ đầu chương, Tạm dừng {} | `qt/CastSample.qml:29` |
| Trang sách | audio-lines | Dừng | Chưa có giọng, Dàn nhân vật hiện ra khi truyện đã được phâ… | `qt/CastSample.qml:46` |
| Studio tạo sách | image-plus | Đặt bìa | Đổi ảnh bìa | `qt/CoverEditor.qml:132` |
| Studio tạo sách | image-plus | Đổi bìa | Đổi ảnh bìa | `qt/CoverEditor.qml:132` |
| Studio tạo sách | image-plus | Đặt ảnh bìa | Đổi ảnh bìa | `qt/CoverEditor.qml:141` |
| Studio tạo sách | trash-2 | Bỏ ảnh bìa | Bỏ chương {}, Bỏ chỗ cắt trước {}, Bỏ ảnh bìa, dùng lại bìa vẽ từ tên sách | `qt/CoverEditor.qml:168` |
| Sửa sách | image-plus | Chọn ảnh bìa… | Đổi ảnh bìa… / Chọn ảnh bìa… | `qt/EditBook.qml:239` |
| Sửa sách | image-plus | Đổi ảnh bìa… | Đổi ảnh bìa… / Chọn ảnh bìa… | `qt/EditBook.qml:239` |
| Sửa sách | file-down | Lưu thành… | Lưu | `qt/EditBookItems.qml:81` |
| Sửa sách | trash-2 | Xoá | Bỏ ảnh bìa | `qt/EditBookMyMusic.qml:295` |
| Sửa sách | trash-2 | Xoá bài | Bỏ ảnh bìa | `qt/EditBookMyMusic.qml:309` |
| Sửa sách | trash-2 | Bỏ cách đọc {} | Bỏ ảnh bìa | `qt/EditBookReadings.qml:120` |
| Thư viện | pause | Chờ chương mới | Đọc {} | `qt/LibraryContinue.qml:42` |
| Thư viện | x | Đóng tìm kiếm | Xoá ô tìm | `qt/LibraryScreen.qml:164` |
| Thư viện | file-audio | Mở file sách | Đang mở… / Mở file sách | `qt/LibraryScreen.qml:418` |
| Thư viện | file-audio | Đang mở… | Đang mở… / Mở file sách | `qt/LibraryScreen.qml:418` |
| Thư viện | search | Chưa có cuốn nào nghe xong. | Thử tên sách hoặc tác giả khác., Tìm sách | `qt/LibraryScreen.qml:429` |
| Cài đặt | upload | Thêm nhạc của bạn | Đang thêm {}/{} / Thêm nhạc của bạn | `qt/MyMusicSettings.qml:145` |
| Cài đặt | upload | Đang thêm {}/{} | Đang thêm {}/{} / Thêm nhạc của bạn | `qt/MyMusicSettings.qml:145` |
| Cài đặt | upload | Thêm nhạc của bạn | Đang thêm {}/{} / Thêm nhạc của bạn | `qt/MyMusicState.qml:105` |
| Studio tạo sách | layers | Phần | Chia thành nhiều phần, Chia thành {} phần / Chia thành mấy phần? | `qt/NewChapters.qml:205` |
| Studio tạo sách | trash-2 | Bỏ chương này | Bỏ chương {}, Bỏ chỗ cắt trước {}, Bỏ ảnh bìa, dùng lại bìa vẽ từ tên sách | `qt/NewChapters.qml:289` |
| Studio tạo sách | layers | Chọn {} tập | Chia thành nhiều phần, Chia thành {} phần / Chia thành mấy phần? | `qt/NewDrop.qml:209` |
| Studio tạo sách | scissors | Tách thành {} chương | Tách thành chương | `qt/NewHints.qml:92` |
| Studio tạo sách | trash-2 | Gộp vào phần trước | Bỏ chương {}, Bỏ chỗ cắt trước {}, Bỏ ảnh bìa, dùng lại bìa vẽ từ tên sách | `qt/NewVolumes.qml:167` |
| Đang nghe | moon | Hẹn giờ | {} trên {} | `qt/NowPlaying.qml:388` |
| Đang nghe | moon | Hết chương | {} trên {} | `qt/NowPlaying.qml:388` |
| Đang nghe | keyboard | Phím | Phím tắt | `qt/NowPlaying.qml:518` |
| Cài đặt | bluetooth | Dự phòng qua Bluetooth… | Dự phòng qua Bluetooth cho {} | `qt/OtherComputersBluetooth.qml:22` |
| Cài đặt | refresh-cw | Làm mới | Hỏi lại, Hỏi lại thư viện | `qt/PhoneDiagnostics.qml:67` |
| Cài đặt | save | Lưu nhật ký | Gửi nhật ký | `qt/PhoneDiagnostics.qml:68` |
| Cài đặt | download | Xem tiến độ cài | Cài Studio, Cài tiếp, Có ABook {} | `qt/StudioSettings.qml:102` |
| Cài đặt | trash-2 | Gỡ Studio | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/StudioSettings.qml:122` |
| Cài đặt | trash-2 | Xác nhận gỡ | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/StudioSettings.qml:122` |
| Cài đặt | trash-2 | Đang gỡ… | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/StudioSettings.qml:122` |
| Studio tạo sách | clapperboard | Tạo trên {} | Tạo trên | `qt/StudioSetupNotice.qml:96` |
| Cài đặt | play | Thử giọng | Dừng / Thử giọng | `qt/VoiceRow.qml:105` |

Số cặp: web máy tính 213, Qt 169. Nhãn Qt có icon (135): `Bấm để đổi tên chương`, `Bật tiếng`, `Bắt đầu`, `Bỏ chương này`, `Bỏ cách đọc {}`, `Bỏ ảnh bìa`, `Bỏ “{}” khỏi cách đọc chung`, `Chi tiết`, `Chia thành nhiều phần`, `Chưa có cuốn nào nghe xong.`, `Chưa nghe`, `Chương`, `Chương sau`, `Chương sau chưa có audio`, `Chương trước`, `Chẩn đoán`, `Chọn`, `Chọn file`, `Chọn file sách`, `Chọn thư mục`, `Chọn thư mục TXT`, `Chọn từng file`, `Chọn {} tập`, `Chọn ảnh bìa…`, `Chờ chương mới`, `Cài Studio`, `Cài đặt`, `Có sách trên máy khác`, `Cập nhật ABook`, `Cửa sổ mini`, `Dừng`, `Dự phòng qua Bluetooth…`, `Dự án mới`, `Ghim trên cùng`, `Ghép thiết bị mới`, `Gộp`, `Gộp vào người khác…`, `Gộp vào phần trước`, `Gỡ Studio`, `Gợi ý đọc`, `Gửi nhật ký`, `Hẹn giờ`, `Hết chương`, `Hỏi lại thư viện`, `Khởi động lại`, `Kiểm tra`, `Làm mới`, `Lưu`, `Lưu nhật ký`, `Lưu thay đổi`, `Lưu thành…`, `Lưu thành mẫu…`, `Mở cuốn đó`, `Mở file sách`, `Mở rộng`, `Mở Studio`, `Mở tab Nhạc nền`, `Mở thư mục`, `Mở thư mục nhật ký`, `Nghe từ đầu chương`, `Nghe {}`, `Nhạc nền`, `Nên dùng`, `Phát`, `Phím`, `Phần`, `Quay lại`, `Studio`, `Sửa cách đọc {}`, `Sửa sách`, `Sửa thông tin`, `Thu gọn`, `Thu nhỏ`, `Thêm`, `Thêm bản riêng`, `Thêm file`, `Thêm giọng…`, `Thêm nhạc của bạn`, `Thêm sách`, `Thêm tuỳ chọn`, `Thêm tuỳ chọn cho {}`, `Thêm vào thư viện`, `Thôi ghép`, `Thư viện`, `Thả để thêm sách`, `Thử giọng`, `Thử lại`, `Trên {}`, `Tuỳ chọn dự án`, `Tuỳ chọn Studio`, `Tách thành {} chương`, `Tìm`, `Tìm bìa…`, `Tìm máy trong mạng`, `Tìm sách`, `Tìm ảnh bìa trên mạng`, `Tạm dừng`, `Tạm dừng {}`, `Tạo sách nói`, `Tạo trên {}`, `Tới câu đang nghe`, `Vẫn cài`, `Vẫn thêm bản mới`, `Về chỗ vừa nghe`, `Về Cài đặt`, `Về Studio`, `Về Thư viện`, `Xem tiến độ cài`, `Xoá`, `Xoá bài`, `Xoá khoá`, `Xoá ô tìm`, `Xác nhận gỡ`, `Xếp theo`, `Đang gỡ…`, `Đang mở…`, `Đang thêm {}/{}`, `Đang tải bản mới…`, `Đang đọc…`, `Đây là chương cuối`, `Đã nghe xong`, `Đóng`, `Đóng tìm kiếm`, `Đặt bìa`, `Đặt ảnh bìa`, `Đọc chương này`, `Đọc {}`, `Đổi bài`, `Đổi bìa`, `Đổi giọng người kể`, `Đổi giọng {}`, `Đổi giới tính`, `Đổi tên`, `Đổi tên chương…`, `Đổi ảnh bìa`.

## c. Nhãn chỉ có một bên, theo màn

Nhãn ngắn (<= 6 chữ). **Chỉ Qt**: không có ở web cùng màn; `*` = web có ở màn khác. **Chỉ web**: nhãn web của màn không có ở đâu trong Qt - phần lớn là tính năng Qt chưa làm (bản thử), chỉ đếm và kể 15 đầu.

### Khay và cửa sổ mini

- chỉ Qt (11): Ghim trên cùng (`qt/MiniPlayer.qml:52`); Mở rộng (`qt/MiniPlayer.qml:58`); Lùi {} giây* (`qt/MiniPlayer.qml:86`); Phát* (`qt/MiniPlayer.qml:87`); Tạm dừng* (`qt/MiniPlayer.qml:87`); Tới {} giây* (`qt/MiniPlayer.qml:88`); Chương sau* (`qt/TrayMenuModel.qml:12`); Chương trước* (`qt/TrayMenuModel.qml:12`); Cửa sổ mini (`qt/TrayMenuModel.qml:12`); Mở ABook (`qt/TrayMenuModel.qml:12`); Thoát ABook (`qt/TrayMenuModel.qml:12`)
- chỉ web (0): (không có)

### Thư viện

- chỉ Qt (10): Trên {} (`qt/BookCell.qml:122`); Tạm dừng* (`qt/LibraryContinue.qml:41`); Mới thêm* (`qt/LibraryScreen.qml:47`); Tác giả* (`qt/LibraryScreen.qml:47`); Tên sách* (`qt/LibraryScreen.qml:47`); Chưa mở được ABook (`qt/LibraryScreen.qml:384`); Chưa tải được thư viện (`qt/LibraryScreen.qml:384`); Thử lại* (`qt/LibraryScreen.qml:401`); Không có sách ở đây (`qt/LibraryScreen.qml:430`); Chưa có cuốn nào nghe xong. (`qt/LibraryScreen.qml:431`)
- chỉ web (3): Nghe ngay {} (`163`); Đã nghe (`241`); Chưa có sách nào (`519`)

### Thanh phát

- chỉ Qt (1): Cửa sổ mini (`qt/PlayerBar.qml:105`)
- chỉ web (20): Vị trí trong chương (`181`); Shift+← (`260`); Sắp tắt · (`1265`); Nghe kiểm (`1335`); Đọc bằng (`1380`); Chọn giọng khác (`1400`); Đóng lời báo (`1407`); Đã nghe chương này (`1434`); Trình phát (`1577`); Mở màn hình đang nghe (`1589`); Đóng trình phát (`1667`); Thiết bị phát (`1668`); Đang chuẩn bị giọng đọc… (`9`); Nghe tiếp · {} (`59`); Chưa có audio (`90`); ...

### Đang nghe

- chỉ Qt (15): Đọc* (`qt/ChapterReader.qml:11`); Chưa có chương để đọc. (`qt/ChapterReader.qml:27`); Đang tải chương… (`qt/ChapterReader.qml:68`); Thử lại* (`qt/ChapterReader.qml:73`); Thêm tuỳ chọn* (`qt/NowPlaying.qml:196`); Bìa (`qt/NowPlaying.qml:219`); Giọng {}* (`qt/NowPlaying.qml:253`); Vẫn đang nghe* (`qt/NowPlaying.qml:315`); Danh sách chương* (`qt/NowPlaying.qml:409`); Nhạc nền* (`qt/NowPlaying.qml:420`); Cửa sổ mini (`qt/NowPlaying.qml:521`); Gợi ý cho phần đọc* (`qt/ReadingSuggestions.qml:8`); Bỏ dòng (`qt/ReadingSuggestions.qml:56`); Đóng* (`qt/ReadingSuggestions.qml:78`); Tắt sau {} (`qt/SleepPopover.qml:19`)
- chỉ web (17): Đã nghe (`94`); Đã làm sẵn (`119`); Shift+← (`260`); Hẹn giờ đã tắt tiếng lúc (`995`); Bật lại (`1004`); Tiếng nhỏ dần (`1012`); Tắt sau (`1097`); Esc (`2037`); Thiết bị phát (`2049`); Đang chuẩn bị giọng đọc… (`9`); Nghe tiếp · {} (`59`); Chưa có audio (`90`); Đang thu âm… (`90`); Bấm (`101`); Chạm (`101`); ...

### Đọc theo

- chỉ Qt (0): (không có)
- chỉ web (0): (không có)

### Trang sách

- chỉ Qt (49): Thêm* (`qt/BookPage.qml:54`); Thêm việc với sách (`qt/BookPage.qml:55`); Chưa bỏ gộp được (`qt/BookPage.qml:130`); Đã bỏ gộp {} (`qt/BookPage.qml:130`); Đã nghe {} (`qt/BookPage.qml:316`); Chưa lấy được danh sách chương. (`qt/BookPage.qml:359`); Giới tính của {} (`qt/CastGender.qml:16`); Hiện đang là nhân vật {}. (`qt/CastGender.qml:17`); Chưa đổi được giới tính (`qt/CastGender.qml:25`); Giới tính* (`qt/CastGender.qml:47`); Nữ* (`qt/CastGender.qml:49`); Nếu giọng (`qt/CastGender.qml:66`); Ghi lại (`qt/CastGender.qml:82`); Thôi* (`qt/CastGender.qml:82`); Đang tải nhân vật (`qt/CastList.qml:72`); Gộp nhân vật (`qt/CastMerge.qml:17`); Chưa gộp được (`qt/CastMerge.qml:28`); Đã ghi: (`qt/CastMerge.qml:28`); Tìm người trong truyện… (`qt/CastMerge.qml:50`); Gộp vào ai (`qt/CastMerge.qml:67`); Không có ai khớp “{}”. (`qt/CastMerge.qml:136`); Gộp (`qt/CastMerge.qml:158`); Hoàn tác* (`qt/CastModal.qml:19`); Không hoàn tác được (`qt/CastModal.qml:19`); Đã hoàn tác (`qt/CastModal.qml:19`); Đã hoàn tác. {} (`qt/CastModal.qml:19`); Đổi tên {} (`qt/CastRename.qml:13`); Chưa đổi được tên (`qt/CastRename.qml:25`); Đã trở về tên gốc: {} (`qt/CastRename.qml:25`); Đã đổi tên thành {} (`qt/CastRename.qml:25`); Tên mới của {} (`qt/CastRename.qml:47`); Tên gốc: (`qt/CastRename.qml:57`); Lưu* (`qt/CastRename.qml:63`); Về tên gốc* (`qt/CastRename.qml:63`); Chưa đổi được giọng (`qt/CastVoice.qml:53`); Giọng (`qt/CastVoice.qml:53`); Chưa bỏ được lựa chọn (`qt/CastVoice.qml:72`); Đã bỏ lựa chọn giọng (`qt/CastVoice.qml:72`); Đã bỏ lựa chọn {} (`qt/CastVoice.qml:72`); Đang tải giọng đọc* (`qt/CastVoice.qml:100`); Thử lại* (`qt/CastVoice.qml:125`); Chờ áp dụng: đổi sang (`qt/CastVoice.qml:144`); Giữ* (`qt/CastVoice.qml:151`); Giữ như cũ (`qt/CastVoice.qml:191`); Lọc giọng theo giới (`qt/CastVoice.qml:198`); Tất cả* (`qt/CastVoice.qml:200`); Đang dùng* (`qt/CastVoice.qml:275`); Máy gợi ý (`qt/CastVoice.qml:289`); Giữ giọng này (`qt/CastVoice.qml:312`)
- chỉ web (38): Đã nghe (`94`); Đã làm sẵn (`119`); Chờ áp dụng: giọng (`441`); Chưa có lịch sử nghe (`528`); 7 ngày qua: (`541`); Nghe tiếp từ (`563`); Hồ sơ mới (`595`); Chuyển hồ sơ (`596`); Đổi tên hồ sơ… (`597`); Xoá hồ sơ… (`598`); Chuyển sang cuốn (`609`); Đang mở thư viện… (`609`); Chọn cuốn… (`619`); Mở cuốn ấy (`664`); Hồ sơ nghe: (`681`); ...

### Cài đặt

- chỉ Qt (155): Chọn nơi lưu gói nhật ký (`qt/AdvancedDiagnostics.qml:12`); Chưa lưu được gói nhật ký (`qt/AdvancedDiagnostics.qml:17`); Đã lưu gói nhật ký (`qt/AdvancedDiagnostics.qml:17`); Chưa dọn được bản đọc (`qt/AdvancedStorage.qml:23`); Đã dọn bản đọc đã làm (`qt/AdvancedStorage.qml:23`); Chưa cập nhật được (`qt/AdvancedUpdate.qml:30`); Không làm được lúc này. (`qt/BookTemplates.qml:26`); Không lưu được mẫu{} (`qt/BookTemplates.qml:26`); Đã xoá mẫu “{}” (`qt/BookTemplates.qml:68`); Chưa kết nối (`qt/DevicesLogic.js:77`); Đang nối qua Bluetooth (`qt/DevicesLogic.js:79`); Đang nối qua Tailscale (`qt/DevicesLogic.js:84`); Đang nối qua Wi-Fi nhà (`qt/DevicesLogic.js:85`); Đang nối qua mạng (`qt/DevicesLogic.js:87`); Đã thôi ghép {} (`qt/DevicesLogic.js:102`); Gửi trước rồi thôi ghép (`qt/DevicesLogic.js:124`); Thử gửi trước rồi thôi ghép (`qt/DevicesLogic.js:126`); Vẫn thôi ghép, bỏ thay đổi (`qt/DevicesLogic.js:130`); Tải sách (`qt/DevicesLogic.js:155`); Xuất M4B* (`qt/DevicesLogic.js:155`); Xuất MP3* (`qt/DevicesLogic.js:155`); Xuất sách nói* (`qt/DevicesLogic.js:155`); Việc nền (`qt/DevicesLogic.js:164`); Việc (`qt/DevicesLogic.js:165`); Bản ABook (`qt/DevicesLogic.js:191`); Giờ trên máy (`qt/DevicesLogic.js:199`); Mạng (`qt/DevicesLogic.js:207`); Chỗ trống (`qt/DevicesLogic.js:213`); Thông báo (`qt/DevicesLogic.js:217`); Chạy nền (`qt/DevicesLogic.js:218`); Đang nghe* (`qt/DevicesLogic.js:222`); Cho máy khác nghe thư viện (`qt/DevicesLogic.js:234`); Lần tắt gần nhất (`qt/DevicesLogic.js:238`); Lần văng (`qt/DevicesLogic.js:242`); Phục hồi dữ liệu (`qt/DevicesLogic.js:243`); Chưa có dòng nào. (`qt/DevicesLogic.js:257`); Đang tải (`qt/DevicesSkeleton.qml:8`); Chưa lưu được cài đặt{} (`qt/ListenSave.qml:8`); Phím một chữ cái đang tắt (`qt/LookShortcuts.qml:11`); Chương trước / sau (`qt/LookShortcuts.qml:14`); Cửa sổ mini (`qt/LookShortcuts.qml:14`); Giảm / tăng tốc độ đọc (`qt/LookShortcuts.qml:14`); Lùi / tới 15 giây (`qt/LookShortcuts.qml:14`); Phát / tạm dừng (`qt/LookShortcuts.qml:14`); Thu nhỏ màn hình đang nghe (`qt/LookShortcuts.qml:14`); Tắt / bật tiếng (`qt/LookShortcuts.qml:14`); Xem các phím tắt này (`qt/LookShortcuts.qml:14`); Tìm hiểu thêm (`qt/MoreInfo.qml:8`); Tải lại ({}) (`qt/MyMusicModule.qml:33`); Bật đo cảm xúc (`qt/MyMusicModule.qml:37`); Tải tiếp ({}) (`qt/MyMusicModule.qml:37`); Tắt đo cảm xúc (`qt/MyMusicModule.qml:37`); Phân tích nhạc (`qt/MyMusicModule.qml:73`); Cảm xúc chính xác (`qt/MyMusicModule.qml:145`); Xoá file ({}) (`qt/MyMusicModule.qml:184`); Đang thêm nhạc thì dừng (`qt/MyMusicSettings.qml:71`); Không xoá được bài này (`qt/MyMusicSettings.qml:84`); Đã xoá khỏi Nhạc của tôi (`qt/MyMusicSettings.qml:84`); Không đổi được (`qt/MyMusicSettings.qml:95`); Chọn nhạc của bạn (`qt/MyMusicSettings.qml:119`); Đang phân tích nhạc đã thêm (`qt/MyMusicText.js:38`); Đang nghe kỹ bài vừa thêm (`qt/MyMusicText.js:70`); Chạy (`qt/MyMusicText.js:74`); Máy không tự chọn bài này (`qt/MyMusicText.js:87`); Tự chọn lại (`qt/MyMusicText.js:94`); Theo mặc định (`qt/MyMusicText.js:95`); Cho tự chọn (`qt/MyMusicText.js:96`); Tắt tự chọn (`qt/MyMusicText.js:96`); Không thêm được file nào (`qt/MyMusicText.js:123`); Không thêm được file này (`qt/MyMusicText.js:123`); Đã thêm: {} (`qt/MyMusicText.js:128`); Chưa có bản đọc đã lưu. (`qt/MyMusicText.js:138`); Ghi chú cho người bảo trì (`qt/MyMusicText.js:154`); Chất lượng cao* (`qt/NewBookDefaults.qml:11`); Cân bằng* (`qt/NewBookDefaults.qml:11`); Kết nối Wi-Fi (`qt/OtherComputers.qml:34`); Đã ghép {} (`qt/OtherComputers.qml:62`); Chưa chọn được (`qt/OtherComputers.qml:85`); Không dùng Bluetooth dự phòng nữa (`qt/OtherComputers.qml:85`); Đã chọn Bluetooth dự phòng (`qt/OtherComputers.qml:85`); Không tìm được (`qt/OtherComputers.qml:94`); Chưa thôi ghép được (`qt/OtherComputers.qml:120`); Chưa ghép được: {} (`qt/OtherComputers.qml:338`); Dự phòng qua Bluetooth cho (`qt/OtherComputersBluetooth.qml:27`); Vân tay {} (`qt/OtherComputersRow.qml:99`); Mở Studio của (`qt/OtherComputersRow.qml:113`); Chưa lưu được nhật ký (`qt/PhoneDiagnostics.qml:49`); Chọn nơi lưu nhật ký (`qt/PhoneDiagnostics.qml:49`); Đã lưu nhật ký (`qt/PhoneDiagnostics.qml:49`); Làm mới* (`qt/PhoneDiagnostics.qml:67`); Lưu nhật ký* (`qt/PhoneDiagnostics.qml:68`); Chi tiết kỹ thuật* (`qt/PhoneDiagnostics.qml:105`); Nhật ký của ABook ({} dòng)* (`qt/PhoneDiagnostics.qml:119`); Chưa bật được đồng bộ (`qt/PhoneSync.qml:60`); Đã tắt chia sẻ qua Wi-Fi (`qt/PhoneSync.qml:60`); Đã đổi tên thành “{}” (`qt/PhoneSync.qml:95`); Mở {}* (`qt/PhoneSync.qml:197`); Điều khiển sản xuất từ (`qt/PhoneSyncDevice.qml:86`); Địa chỉ: {} (`qt/PhoneSyncPairing.qml:57`); Mã ghép nối: (`qt/PhoneSyncPairing.qml:71`); Hết hạn sau {}:{} (`qt/PhoneSyncPairing.qml:80`); Chưa dùng được (`qt/ProviderKey.qml:20`); Dùng được · {} giọng (`qt/ProviderKey.qml:20`); Dán khoá trước đã. (`qt/ProviderKey.qml:31`); Dùng được · (`qt/ProviderKey.qml:40`); Khoá chưa dùng được. (`qt/ProviderKey.qml:40`); Đã đổi thư mục thư viện (`qt/SettingsAdvanced.qml:14`); Chọn thư mục thư viện (`qt/SettingsAdvanced.qml:62`); Tự chọn nhạc nền (`qt/SettingsListen.qml:23`); Đã bật tự chọn nhạc nền (`qt/SettingsListen.qml:28`); Đã tắt tự chọn nhạc nền (`qt/SettingsListen.qml:28`); Thu vào khay khi đóng (`qt/SettingsLook.qml:13`); Tự mở cửa sổ mini (`qt/SettingsLook.qml:18`); Giấy* (`qt/SettingsLook.qml:33`); Ngà* (`qt/SettingsLook.qml:33`); Đêm* (`qt/SettingsLook.qml:33`); Có bản mới {} (`qt/SettingsScreen.qml:59`); Không tự lùi (`qt/SettingsScreen.qml:59`); Phiên bản {} (`qt/SettingsScreen.qml:59`); Tự tắt (`qt/SettingsSleep.qml:31`); Mỗi lần nghe thêm (`qt/SettingsSleep.qml:56`); Số phút nghe thêm (`qt/SettingsSleep.qml:57`); Lúc đang nhỏ dần: {}. (`qt/SettingsSleep.qml:58`); Nhỏ dần (`qt/SettingsSleep.qml:65`); Độ dài nhỏ dần (`qt/SettingsSleep.qml:66`); Đang dùng: {} (`qt/SettingsVoice.qml:149`); Không cài được Studio (`qt/StudioSettings.qml:30`); Chưa gỡ được Studio (`qt/StudioSettings.qml:36`); Đã gỡ Studio (`qt/StudioSettings.qml:36`); Cần cập nhật* (`qt/StudioSettings.qml:139`); Mất {} (`qt/StudioSettings.qml:139`); Giọng của máy* (`qt/VoiceLogic.js:36`); Nữ* (`qt/VoiceLogic.js:41`); Ngọc Linh (`qt/VoiceLogic.js:89`); Phạm Tuyên (`qt/VoiceLogic.js:89`); Thanh Bình (`qt/VoiceLogic.js:89`); Mỹ Duyên (`qt/VoiceLogic.js:90`); Ái Hân (`qt/VoiceLogic.js:90`); Đức Trí (`qt/VoiceLogic.js:90`); Giọng VieNeu* (`qt/VoiceLogic.js:120`); Giọng Supertonic* (`qt/VoiceLogic.js:125`); Giọng VieNeu Nano (`qt/VoiceLogic.js:129`); Tải, đo và quản lý (`qt/VoiceLogic.js:160`); Đang đọc bằng bản thường. (`qt/VoiceLogic.js:214`); Đang đọc bằng bản tăng tốc. (`qt/VoiceLogic.js:216`); Máy này chưa dùng được {}. (`qt/VoiceLogic.js:249`); Tốc độ đọc* (`qt/VoiceLogic.js:272`); Chất lượng cao nhất* (`qt/VoiceLogic.js:275`); Nhanh hơn* (`qt/VoiceLogic.js:276`); Chưa tải được {} (`qt/VoiceModule.qml:55`); Chưa gỡ được {} (`qt/VoiceModule.qml:56`); Chưa huỷ được việc tải {} (`qt/VoiceModule.qml:156`); Chưa đổi được cách đọc (`qt/VoiceModule.qml:283`); Thử* (`qt/VoiceRow.qml:108`); Chưa tải được bản nhanh hơn (`qt/VoiceSpeed.qml:94`)
- chỉ web (21): Mở Studio của {} (`205`); Hỏi lại (`229`); Dự phòng qua Bluetooth cho {} (`359`); Bluetooth (`368`); Địa chỉ: (`199`); Trình duyệt: mở (`200`); Mã ghép nối: {} (`205`); Hết hạn sau (`213`); Kết nối lần cuối (`410`); Điều khiển sản xuất từ {} (`417`); ABook{} là bản mới nhất. (`21`); Space (`17`); Shift (`19`); Esc (`22`); Đang mở danh sách… (`56`); ...

### Thêm sách

- chỉ Qt (30): Chưa đọc lại được file (`qt/AddBook.qml:175`); Không mở được file sách (`qt/AddBook.qml:215`); Không mở được file sách này. (`qt/AddBook.qml:226`); Chưa thêm được sách (`qt/AddBook.qml:306`); Đã thêm sách vào thư viện (`qt/AddBook.qml:306`); Bỏ qua* (`qt/AddBook.qml:393`); Thêm bản riêng (`qt/AddBook.qml:427`); Vẫn thêm bản mới (`qt/AddBook.qml:427`); Xong* (`qt/AddBook.qml:433`); Không đọc số chú thích* (`qt/AddBook.qml:870`); Đọc lời chú ở cuối chương* (`qt/AddBook.qml:879`); Bỏ lời chú* (`qt/AddBook.qml:887`); Bỏ dòng này khỏi phần đọc* (`qt/AddBook.qml:956`); Tất cả file (*) (`qt/AddBook.qml:1029`); Đưa vào sách: (`qt/ImportChapters.qml:100`); Bấm để đổi tên chương* (`qt/ImportChapters.qml:135`); Tên chương* (`qt/ImportChapters.qml:171`); Thả để thêm sách* (`qt/ImportDrop.qml:52`); Thử lại* (`qt/ImportError.qml:50`); Chưa đọc được (`qt/ImportQueue.js:100`); Đã thêm (`qt/ImportQueue.js:100`); File này có bản thu khác (`qt/ImportQueue.js:197`); Sách đã có (`qt/ImportQueue.js:197`); Đã cập nhật (`qt/ImportQueue.js:197`); Đã thêm sách (`qt/ImportQueue.js:197`); Sách của Studio (`qt/ImportQueue.js:198`); Đã khôi phục file (`qt/ImportQueue.js:198`); Đã mở dự án (`qt/ImportQueue.js:198`); Đã gộp {} sửa từ file (`qt/ImportQueue.js:205`); Đang tải (`qt/ImportSkeleton.qml:10`)
- chỉ web (2): Đóng khi còn sách chưa thêm (`585`); Các file đã chọn (`825`)

### Sửa sách

- chỉ Qt (69): Chưa chỉnh được nhạc nền (`qt/BookMusicSettings.qml:32`); Tìm ảnh bìa (`qt/EditBook.qml:44`); Chưa đổi được tên sách (`qt/EditBook.qml:113`); Đã đổi tên sách (`qt/EditBook.qml:113`); Chưa đổi được tác giả (`qt/EditBook.qml:117`); Đã bỏ tên tác giả (`qt/EditBook.qml:117`); Đã đổi tác giả (`qt/EditBook.qml:117`); Chưa đặt được ảnh bìa (`qt/EditBook.qml:121`); Đã đặt ảnh bìa (`qt/EditBook.qml:121`); Chưa bỏ được ảnh bìa (`qt/EditBook.qml:124`); Chưa bỏ được thay đổi (`qt/EditBook.qml:127`); Không đọc được file ảnh (`qt/EditBook.qml:405`); Thử lại* (`qt/EditBookError.qml:45`); Lưu thay đổi* (`qt/EditBookItems.qml:70`); Lưu thành…* (`qt/EditBookItems.qml:80`); Hơi to (`qt/EditBookLogic.js:48`); Nhỏ (`qt/EditBookLogic.js:48`); Rất nhỏ (`qt/EditBookLogic.js:48`); Vừa (mặc định) (`qt/EditBookLogic.js:48`); Chưa nối được {} (`qt/EditBookLogic.js:78`); Máy không tự chọn bài này (`qt/EditBookLogic.js:89`); Tự chọn lại (`qt/EditBookLogic.js:94`); Theo mặc định (`qt/EditBookLogic.js:95`); Cho tự chọn (`qt/EditBookLogic.js:96`); Tắt tự chọn (`qt/EditBookLogic.js:96`); Hợp không khí đoạn này (`qt/EditBookLogic.js:100`); Đang phân tích nhạc đã thêm (`qt/EditBookLogic.js:117`); Không thêm được file nào (`qt/EditBookLogic.js:135`); Không thêm được file này (`qt/EditBookLogic.js:135`); Đã thêm: {} (`qt/EditBookLogic.js:140`); Đang thêm nhạc thì dừng (`qt/EditBookMyMusic.qml:66`); Không xoá được bài này (`qt/EditBookMyMusic.qml:79`); Đã xoá khỏi Nhạc của tôi (`qt/EditBookMyMusic.qml:79`); Chọn nhạc của bạn (`qt/EditBookMyMusic.qml:112`); Nhạc của tôi* (`qt/EditBookMyMusic.qml:121`); Chưa có bài nào* (`qt/EditBookMyMusic.qml:122`); Thêm nhạc của bạn* (`qt/EditBookMyMusic.qml:131`); Đang thêm {}/{}* (`qt/EditBookMyMusic.qml:131`); Phân tích nhạc (`qt/EditBookMyMusic.qml:148`); Huỷ* (`qt/EditBookMyMusic.qml:164`); Cập nhật ({})* (`qt/EditBookMyMusic.qml:172`); Phân tích {} bài (`qt/EditBookMyMusic.qml:172`); Tải ({})* (`qt/EditBookMyMusic.qml:172`); Tải lại ({}) (`qt/EditBookMyMusic.qml:172`); Nhạc riêng* (`qt/EditBookMyMusic.qml:184`); Đang tải nhạc riêng* (`qt/EditBookMyMusic.qml:190`); Xoá* (`qt/EditBookMyMusic.qml:295`); Xoá: {}* (`qt/EditBookMyMusic.qml:296`); Xoá bài* (`qt/EditBookMyMusic.qml:309`); Xoá bài: {}* (`qt/EditBookMyMusic.qml:311`); Giữ lại* (`qt/EditBookMyMusic.qml:316`); Giữ lại: {}* (`qt/EditBookMyMusic.qml:318`); Chưa bỏ được cách đọc (`qt/EditBookReadings.qml:27`); Chưa lưu được cách đọc (`qt/EditBookReadings.qml:27`); Đang tải cách đọc* (`qt/EditBookReadings.qml:67`); Sửa cách đọc {}* (`qt/EditBookReadings.qml:112`); Bỏ cách đọc {}* (`qt/EditBookReadings.qml:122`); Cách đọc cho {}* (`qt/EditBookReadings.qml:141`); Lưu cho cả cuốn* (`qt/EditBookReadings.qml:152`); Đọc như chữ trong sách* (`qt/EditBookReadings.qml:160`); Chưa đổi được tên chương (`qt/EditBookRename.qml:29`); Đã đổi tên chương: {} (`qt/EditBookRename.qml:29`); Chưa lưu được file sách (`qt/EditBookSaveAs.qml:25`); Đã lưu file sách (`qt/EditBookSaveAs.qml:25`); Chọn nơi lưu file sách (`qt/EditBookSaveAs.qml:51`); Loại file (`qt/EditBookSaveAs.qml:59`); Đang tải (`qt/EditBookSkeleton.qml:10`); Đang tải bài nhạc* (`qt/EditBookSwap.qml:36`); Chọn* (`qt/EditBookSwap.qml:91`)
- chỉ web (1): Bỏ mọi thay đổi ({}) (`486`)

### Thanh bên

- chỉ Qt (9): Trạng thái ABook (`qt/ConnectionChip.qml:9`); Gặp lỗi (`qt/ConnectionChip.qml:54`); Sẵn sàng (`qt/ConnectionChip.qml:54`); Đang mở…* (`qt/ConnectionChip.qml:54`); Bản {} (`qt/ConnectionPopover.qml:75`); Khởi động lại (`qt/ConnectionPopover.qml:87`); Mở thư mục nhật ký (`qt/ConnectionPopover.qml:95`); Mở rộng (`qt/Sidebar.qml:84`); Thu gọn* (`qt/Sidebar.qml:84`)
- chỉ web (7): Đang tải tiến độ (`99`); Đang chờ {} (`111`); Tiến độ: {} (`119`); Xem tất cả (`125`); Có ABook (`146`); Bấm để cập nhật (`147`); Điều hướng chính (`166`)

### Studio dự án

- chỉ Qt (57): Làm (`qt/OnComputerPill.qml:9`); Không khởi động được: {} (`qt/ProjectScreen.qml:320`); Chưa có chương nào (`qt/ProjectScreen.qml:501`); Đang tải nhật ký (`qt/ProjectScreen.qml:523`); Không thấy thư mục thư viện* (`qt/ProjectsScreen.qml:227`); Chọn thư mục* (`qt/ProjectsScreen.qml:230`); Chọn lại thư mục thư viện* (`qt/ProjectsScreen.qml:231`); Nghe* (`qt/StudioChapterRow.qml:46`); Tuỳ chọn* (`qt/StudioChapterRow.qml:159`); Áp dụng (`qt/StudioDialogs.qml:56`); Đóng* (`qt/StudioDialogs.qml:56`); 0 phút (`qt/StudioLogic.js:20`); Còn (`qt/StudioLogic.js:75`); Sắp tới lượt (`qt/StudioLogic.js:75`); Chờ bạn duyệt (`qt/StudioLogic.js:80`); Mất kết nối tới ABook. (`qt/StudioLogic.js:100`); Giọng kể {} (`qt/StudioLogic.js:167`); Đang tạm dừng* (`qt/StudioLogic.js:197`); Sách vẫn đang tạm dừng (`qt/StudioLogic.js:202`); Đang làm tiếp (`qt/StudioLogic.js:208`); Card đồ hoạ hết bộ nhớ. (`qt/StudioLogic.js:243`); Ổ đĩa hết chỗ trống. (`qt/StudioLogic.js:257`); Có lỗi khi làm sách. (`qt/StudioLogic.js:274`); Cài Studio* (`qt/StudioLogic.js:361`); Cập nhật Studio* (`qt/StudioLogic.js:361`); Sửa Studio* (`qt/StudioLogic.js:361`); Cần cài Studio (`qt/StudioLogic.js:364`); Cần cập nhật Studio (`qt/StudioLogic.js:364`); Cần sửa Studio* (`qt/StudioLogic.js:364`); Thêm {} chương (`qt/StudioLogic.js:384`); Bộ phân tích bản {} (`qt/StudioLogic.js:423`); Bộ phân tích tuỳ chọn (`qt/StudioLogic.js:423`); Giọng kể {} (chờ áp dụng) (`qt/StudioLogic.js:426`); Tạo {} (`qt/StudioLogic.js:429`); Cần nghe lại (`qt/StudioLogic.js:435`); Duyệt trước khi thu* (`qt/StudioLogic.js:435`); Kịch bản* (`qt/StudioLogic.js:435`); Nhân vật* (`qt/StudioLogic.js:435`); Nhạc nền* (`qt/StudioLogic.js:435`); Nhật ký (`qt/StudioLogic.js:435`); Việc cần duyệt* (`qt/StudioLogic.js:435`); Mất file audio (`qt/StudioLogic.js:453`); Lỗi {} (`qt/StudioStore.qml:40`); Không bắt đầu được (`qt/StudioStore.qml:123`); Không làm tiếp được (`qt/StudioStore.qml:141`); Không tạm dừng được (`qt/StudioStore.qml:141`); Không dừng được (`qt/StudioStore.qml:152`); Chưa bỏ xếp hàng được (`qt/StudioStore.qml:163`); Không mở được thư mục (`qt/StudioStore.qml:171`); Chưa đổi được tên (`qt/StudioStore.qml:176`); Đã đổi tên thành “{}” (`qt/StudioStore.qml:176`); Chưa xoá được (`qt/StudioStore.qml:186`); Hoàn tác* (`qt/StudioStore.qml:186`); Chưa hoàn tác được (`qt/StudioStore.qml:197`); Đã khôi phục “{}” (`qt/StudioStore.qml:197`); Chưa khôi phục được (`qt/StudioStore.qml:204`); Chưa ghi được (`qt/StudioStore.qml:227`)
- chỉ web (24): Không khởi động được: (`194`); Đổi giọng kể (`264`); Tiến độ cả sách (`291`); Các bước (`317`); Phân tích truyện (`319`); Phân vai (`333`); Thu âm và kiểm tra (`340`); Làm tiếp từ chỗ ấy (`378`); Phân tích của “ (`378`); Tuỳ chọn dự án {} (`626`); Chờ lượt (`796`); Dùng pin (`830`); Thu lại (`961`); Sửa chữ (`969`); Thu lại chương (`970`); ...

### Studio tạo sách

- chỉ Qt (71): Chưa đặt được ảnh bìa (`qt/CoverEditor.qml:29`); Đã đặt ảnh bìa (`qt/CoverEditor.qml:29`); Chưa bỏ được ảnh bìa (`qt/CoverEditor.qml:40`); Đã bỏ ảnh bìa (`qt/CoverEditor.qml:40`); Tìm ảnh bìa (`qt/CoverEditor.qml:193`); Chọn ảnh bìa* (`qt/CoverPicker.qml:12`); Gợi ý: {} chương có {} (`qt/NewCredits.qml:59`); Chọn {} tập (`qt/NewDrop.qml:214`); Tách theo {} (`qt/NewHints.qml:86`); Truyện (*.txt *.epub *.docx *.pdf) (`qt/NewPicker.qml:17`); Tất cả file (*) (`qt/NewPicker.qml:17`); Nhanh nhất (`qt/NewProjectLogic.js:9`); Soát cơ bản sau khi đọc (`qt/NewProjectLogic.js:10`); Vừa phải (`qt/NewProjectLogic.js:11`); Phân tích truyện đầy đủ (`qt/NewProjectLogic.js:12`); Chậm nhất, kỹ nhất (`qt/NewProjectLogic.js:13`); Đang đọc nguồn… (`qt/NewProjectLogic.js:46`); Nhân vật tự kể (`qt/NewProjectLogic.js:190`); Thứ tự lệch: {} (`qt/NewProjectLogic.js:231`); Có vẻ thiếu {} (`qt/NewProjectLogic.js:232`); Bản thử nghiệm (`qt/NewProjectLogic.js:369`); Mặc định của ABook (`qt/NewProjectLogic.js:372`); Đã tạo {} phần (`qt/NewProjectLogic.js:470`); Đã làm lại sách từ đầu (`qt/NewProjectLogic.js:471`); Đã tạo sách (`qt/NewProjectLogic.js:472`); Chia thành (`qt/NewProjectLogic.js:488`); Các phần sau (`qt/NewProjectLogic.js:489`); Độ dài audio (`qt/NewProjectLogic.js:493`); Người kể “tôi” (`qt/NewProjectLogic.js:495`); Lời kể (`qt/NewProjectLogic.js:496`); Là (`qt/NewProjectLogic.js:501`); Nhân vật* (`qt/NewProjectLogic.js:504`); Thời gian làm (`qt/NewProjectLogic.js:508`); Thời gian làm (tham khảo) (`qt/NewProjectLogic.js:511`); Số tham khảo từ đâu (`qt/NewProjectLogic.js:513`); Giọng kể máy chọn (`qt/NewProjectLogic.js:537`); Giọng kể {} (`qt/NewProjectLogic.js:537`); Không làm được lúc này. (`qt/NewProjectStore.qml:58`); Không đọc được:* (`qt/NewProjectStore.qml:153`); Đã áp (`qt/NewProjectStore.qml:223`); Đã bỏ {} (`qt/NewProjectStore.qml:261`); Có file không gửi{} (`qt/NewProjectStore.qml:269`); Không gửi được. (`qt/NewProjectStore.qml:284`); Không gửi hết các chương{} {} (`qt/NewProjectStore.qml:312`); Đã dừng gửi - {} (`qt/NewProjectStore.qml:312`); Đã huỷ gửi (`qt/NewProjectStore.qml:312`); Không tách được (`qt/NewProjectStore.qml:329`); Không tạo được sách (`qt/NewProjectStore.qml:348`); Phần {} của “{}” (`qt/NewSeedBanner.qml:37`); Đã lưu mẫu “{}” (`qt/NewTemplateBar.qml:42`); Tìm hiểu thêm (`qt/NewTemplateBar.qml:143`); Dùng lại {} (`qt/NewVoice.qml:209`); Bắc (`qt/NewVoice.qml:236`); Chia {} phần? (`qt/NewVolumes.qml:51`); Máy thấy {} (`qt/NewVolumes.qml:57`); Studio chưa xong{} (`qt/StudioSetupCard.qml:26`); Studio đã sẵn sàng (`qt/StudioSetupCard.qml:26`); Không cài được Studio (`qt/StudioSetupCard.qml:40`); Tiến độ:* (`qt/StudioSetupCard.qml:205`); Máy này {}. (`qt/StudioSetupLogic.js:16`); Tải lại {} (`qt/StudioSetupLogic.js:60`); Cập nhật {} (`qt/StudioSetupLogic.js:61`); Tạo trên {} (`qt/StudioSetupNotice.qml:95`); Mặc định* (`qt/TemplateLogic.js:11`); Đặt cho mẫu một cái tên (`qt/TemplateLogic.js:48`); Tên mẫu tối đa {} chữ (`qt/TemplateLogic.js:49`); Đã có mẫu tên “{}” (`qt/TemplateLogic.js:51`); Giọng máy đề xuất* (`qt/TemplateLogic.js:56`); Tải lên {} (`qt/UploadLogic.js:28`); Chưa gửi file nào. (`qt/UploadLogic.js:92`); Đã gửi {}/{} file, giữ lại (`qt/UploadLogic.js:94`)
- chỉ web (28): Bản khác (thử nghiệm) (`103`); Nhanh (`93`); Gửi các chương từ máy này (`439`); Sẽ bỏ (`799`); Gợi ý: (`808`); Mọi dòng gợi ý theo chương (`819`); Gợi ý: “ (`898`); Tách theo (`899`); Tách thành (`912`); Dừng nghe {} (`992`); Nam (`1165`); Giọng kể phần trước: (`1264`); Dùng lại (`1269`); Đang chọn: (`1291`); Tham khảo: (`1385`); ...

### Studio máy khác

- chỉ Qt (1): Studio* (`qt/StudioScreen.qml:196`)
- chỉ web (0): (không có)

### Thanh tiêu đề

- chỉ Qt (3): ABook* (`qt/Main.qml:10`); ABook vẫn chạy ở khay (`qt/Main.qml:26`); Chưa tải được bản mới (`qt/Main.qml:203`)
- chỉ web (2): Tới nội dung (`228`); Điều hướng (`248`)

### Chung

- chỉ Qt (3): Không làm được lúc này. (`qt/Api.qml:39`); Quay lại* (`qt/ScreenHeader.qml:12`); Đóng thông báo (`qt/Toast.qml:146`)
- chỉ web (4): Đang mở ABook (`578`); Đang tải điều hướng (`578`); Xem các tab trước (`514`); Xem các tab sau (`519`)

File QML chưa xếp màn (thêm vào SCREENS): `desktop_qt/qml/CastLogic.js`, `desktop_qt/qml/MusicCredit.qml`, `desktop_qt/qml/MusicPopover.qml`, `desktop_qt/qml/PeerStudio.js`.

## d. Bo góc QML không theo token

Hợp lệ: `Theme.radiusControl / radiusCover / radiusSheet` (DESIGN.md 5.5, `desktop_qt/tools/gen_theme.py`), `0`, tròn (`width / 2`, `height / 2`), lấy lại bo khung chứa (`parent.radius`), vòng đồng tâm ngoài (`Theme.radiusCover + 8` của bóng, vòng tiêu điểm). Còn lại (0):

| nơi | radius |
|---|---|
| (không có) | |

## e. Dấu thanh kiểu mới và dấu ba chấm cuối nhãn

**Dấu thanh kiểu mới (`òa óa úy`)** trong chữ Qt (0); web và native đa số viết kiểu cũ (`oà oá uý`, UI_PARITY.md d2):

- (không có)

**Nhãn kết thúc bằng `…` / `...`** (46): DESIGN.md chỉ cho `…` ở chữ đang chờ ("Đang mở…"), không cho nhãn nút.

- Bỏ mọi thay đổi… (`qt/EditBook.qml:338`) - web: `Bỏ mọi thay đổi…`
- Chưa tải lại được sách: {} Đang thử lại… (`qt/StudioLogic.js:491`) - web: `Chưa tải lại được sách: {} Đang thử lại…`
- Chọn thư mục… (`qt/EditBookSaveAs.qml:80`) - web: `Chọn thư mục`, `Chọn thư mục…`
- Chọn ảnh bìa… (`qt/EditBook.qml:238`) - web: `Chọn ảnh bìa…`
- Dừng… (`qt/StudioLogic.js:379`) - web: `Dừng`, `Dừng…`
- Dự phòng qua Bluetooth… (`qt/OtherComputersBluetooth.qml:25`) - web: `Dự phòng qua Bluetooth…`
- Gộp vào người khác… (`qt/BookPage.qml:225`) - web: `Gộp vào người khác…`
- Khôi phục bản sao… (`qt/StudioLogic.js:408`) - web: `Khôi phục bản sao…`
- Làm tiếp cuốn này… (`qt/StudioLogic.js:398`) - web: `Làm tiếp cuốn này`, `Làm tiếp cuốn này…`
- Lưu thành mẫu… (`qt/NewTemplateBar.qml:79`) - web: `Lưu thành mẫu…`
- Lưu thành… (`qt/EditBookItems.qml:80`) - web: `Lưu thành…`
- Lưu thành… (`qt/EditBookSaveAs.qml:16`) - web: `Lưu thành…`
- Mạng chập chờn - đang thử lại… (`qt/EditBookLogic.js:86`) - web: (không có)
- Mạng chập chờn - đang thử lại… (`qt/MyMusicText.js:9`) - web: (không có)
- Mạng chập chờn - đang thử lại… (`qt/VoiceLogic.js:13`) - web: (không có)
- Mất kết nối tới ABook, đang thử lại… (`qt/StudioLogic.js:491`) - web: `Mất kết nối tới ABook, đang thử lại…`
- Mở dự án có sẵn… (`qt/ProjectsScreen.qml:256`) - web: `Mở dự án có sẵn…`
- Thu lại cả chương… (`qt/ProjectScreen.qml:127`) - web: `Thu lại cả chương…`
- Thêm giọng… (`qt/NowPlaying.qml:519`) - web: `Thêm giọng…`
- Tìm bìa… (`qt/EditBook.qml:247`) - web: `Tìm bìa…`
- Tìm người trong truyện… (`qt/CastMerge.qml:50`) - web: (không có)
- Tìm người trong truyện… (`qt/CastMerge.qml:51`) - web: (không có)
- Tìm tên… (`qt/SharedReadingsSettings.qml:61`) - web: `Tìm tên…`
- Vẫn tiếp tục… (`qt/StudioLogic.js:378`) - web: `Vẫn tiếp tục`, `Vẫn tiếp tục…`
- Xoá dự án… (`qt/StudioLogic.js:402`) - web: `Xoá dự án…`
- Xuất… (`qt/StudioLogic.js:383`) - web: `Xuất…`
- Đang dừng… (`qt/NewChapters.qml:104`) - web: `Đang dừng`, `Đang dừng…`
- Đang dừng… (`qt/NewDrop.qml:128`) - web: `Đang dừng`, `Đang dừng…`
- Đang dừng… (`qt/StudioLogic.js:313`) - web: `Đang dừng`, `Đang dừng…`
- Đang gỡ… (`qt/StudioSettings.qml:123`) - web: `Đang gỡ…`
- Đang kiểm tra… (`qt/AdvancedUpdate.qml:116`) - web: `Đang kiểm tra…`
- Đang mở văn bản chương… (`qt/ReadAlongView.qml:318`) - web: `Đang mở văn bản chương…`
- Đang mở… (`qt/ConnectionChip.qml:54`) - web: `Đang mở…`
- Đang mở… (`qt/LibraryScreen.qml:418`) - web: `Đang mở…`
- Đang thử giọng vừa tải trên máy này (vài giây)… (`qt/VoiceLogic.js:248`) - web: (không có)
- Đang tải bản mới… (`qt/AdvancedUpdate.qml:94`) - web: `Đang tải bản mới…`
- Đang tải chương… (`qt/ChapterReader.qml:68`) - web: (không có)
- Đang tải âm thanh… (`qt/PlayerBar.qml:87`) - web: `Đang tải âm thanh…`
- Đang xem cuốn nào còn dùng giọng này… (`qt/VoiceModule.qml:400`) - web: `Đang xem cuốn nào còn dùng giọng này…`
- Đang đo lại tốc độ trên máy này (vài giây)… (`qt/VoiceLogic.js:248`) - web: (không có)
- Đang đọc các chương… (`qt/NewDrop.qml:81`) - web: `Đang đọc các chương…`
- Đang đọc nguồn… (`qt/NewProjectLogic.js:46`) - web: (không có)
- Đang đọc… (`qt/AddBook.qml:539`) - web: `Đang đọc…`
- Đổi tên chương… (`qt/BookPage.qml:201`) - web: `Đổi tên chương`, `Đổi tên chương…`
- Đổi tên… (`qt/StudioLogic.js:395`) - web: `Đổi tên`, `Đổi tên…`
- Đổi ảnh bìa… (`qt/EditBook.qml:238`) - web: `Đổi ảnh bìa`, `Đổi ảnh bìa…`

## f. Phím tắt trong chú thích

Chú thích Qt ghi phím tắt sau nhãn; web ghép bằng `withShortcut(nhãn, phím)`. Phím khác nhau là khác HÀNH VI (phím thật trong `Main.qml` / `player.tsx`), không chỉ khác chữ.

| nhãn | Qt | web | nơi |
|---|---|---|---|
| Phát | `Space` | (không ghi) | `qt/PlayButton.qml:13` |
| Tạm dừng | `Space` | (không ghi) | `qt/PlayButton.qml:13` |
| {} | `Esc` | (không ghi) | `qt/ScreenHeader.qml:24` |
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
