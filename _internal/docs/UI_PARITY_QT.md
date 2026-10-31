# Lệch chữ, icon và bo góc giữa web máy tính và bản Qt

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Cùng nguồn chung như `docs/UI_PARITY.md` (web <-> điện thoại native): bo góc `Theme.qml` sinh bởi `desktop_qt/tools/gen_theme.py` từ DESIGN.md 5.5,
icon `LucidePaths.js` sinh bởi `scripts/gen_lucide_icons.py --qml`. Bảng dưới do `scripts/ui_parity_qt.py` sinh (`--check` báo lệch,
`tests/test_ui_parity_qt.py` chạy `--check`). Bộ đọc là heuristic trên mã nguồn: chữ dựng từ dữ liệu (tên chương, thời gian) không tính.

<!-- ui_parity_qt:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity_qt.py - không sửa tay, chạy lại script) -->

Quét: web máy tính 4871 chữ (2785 khác nhau), 320 cặp nhãn-icon; Qt 3450 chữ (2565 khác nhau), 281 cặp nhãn-icon (icon dùng ở 400 chỗ). Khoá so lỏng như UI_PARITY.md (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối); phím tắt trong chú thích Qt (`Thu nhỏ (Esc)`) tách khỏi nhãn.

## a. Cùng việc, khác chữ

Nhãn ngắn Qt không có nguyên văn (khoá lỏng) ở web máy tính mà giống một nhãn web CÙNG MÀN chưa có ở Qt. 47 cặp; mỗi nhãn Qt lấy một nhãn web giống nhất. Giống không có nghĩa là cùng việc: người sửa xem mã hai bên trước khi đổi.

| màn | Qt | web | giống | nơi |
|---|---|---|---|---|
| Cài đặt | Chưa lưu được mẫu{} | Chưa lưu được mẫu | 1.00 | `qt/BookTemplates.qml:26` ~ `desktop/BookTemplates.tsx:23` |
| Cài đặt | Dùng Bluetooth cho | Dùng Bluetooth cho {} | 1.00 | `qt/OtherComputersBluetooth.qml:26` ~ `desktop/OtherComputers.tsx:360` |
| Cài đặt | Hết hạn sau {}:{} | Hết hạn sau | 1.00 | `qt/PhoneSyncPairing.qml:80` ~ `desktop/PhoneSync.tsx:169` |
| Cài đặt | Khoá | Khoá {} | 1.00 | `qt/ProviderKey.qml:138` ~ `listen/VoiceSettings.tsx:192` |
| Cài đặt | Mã ghép nối: | Mã ghép nối: {} | 1.00 | `qt/PhoneSyncPairing.qml:71` ~ `desktop/PhoneSync.tsx:162` |
| Cài đặt | Mở Studio của | Mở Studio của {} | 1.00 | `qt/OtherComputersRow.qml:112` ~ `desktop/OtherComputers.tsx:210` |
| Cài đặt | Điều khiển sản xuất từ | Điều khiển sản xuất từ {} | 1.00 | `qt/PhoneSyncDevice.qml:86` ~ `desktop/PhoneSync.tsx:374` |
| Cài đặt | Địa chỉ: {} | Địa chỉ: | 1.00 | `qt/PhoneSyncPairing.qml:57` ~ `desktop/PhoneSync.tsx:155` |
| Cài đặt | Dừng nghe | Dừng nghe thử {} | 0.82 | `qt/MyMusicTrack.qml:104` ~ `listen/VoiceSettings.tsx:342` |
| Studio dự án | Chưa khởi động được: {} | Chưa khởi động được: | 1.00 | `qt/ProjectScreen.qml:471` ~ `studio/ProjectScreen.tsx:196` |
| Studio dự án | Chưa dừng được | Chưa tải được | 0.74 | `qt/StudioStore.qml:159` ~ `studio/ProjectScreen.tsx:1440` |
| Studio dự án | Đang làm tiếp | Làm tiếp từ chỗ ấy | 0.52 | `qt/StudioLogic.js:227` ~ `studio/ProjectScreen.tsx:380` |
| Studio kịch bản | Gán cho {} | Gán cho | 1.00 | `qt/ScriptRow.qml:244` ~ `studio/ScriptTab.tsx:1125` |
| Studio kịch bản | Đang chọn {} câu | Đang chọn | 0.82 | `qt/ScriptTab.qml:464` ~ `studio/ScriptTab.tsx:1419` |
| Studio tạo sách | Tạo trên {} | Tạo trên | 1.00 | `qt/StudioSetupNotice.qml:97` ~ `studio/StudioSetup.tsx:103` |
| Studio tạo sách | Bản thử nghiệm | Bản thử nghiệm{} | 1.00 | `qt/NewProjectLogic.js:369` ~ `studio/AnalysisModelPicker.tsx:51` |
| Studio tạo sách | Có file không gửi{} | Có file không gửi | 1.00 | `qt/NewProjectStore.qml:269` ~ `studio/NewProjectScreen.tsx:304` |
| Studio tạo sách | Không gửi hết các chương{} {} | Không gửi hết các chương | 1.00 | `qt/NewProjectStore.qml:312` ~ `studio/NewProjectScreen.tsx:311` |
| Studio tạo sách | Máy thấy {} | Máy thấy | 1.00 | `qt/NewVolumes.qml:57` ~ `studio/VolumeSplit.tsx:102` |
| Studio tạo sách | Phần {} của “{}” | Phần {}: {} | 1.00 | `qt/NewSeedBanner.qml:37` ~ `studio/NewProjectScreen.tsx:633` |
| Studio tạo sách | Studio chưa xong{} | Studio chưa xong | 1.00 | `qt/StudioSetupCard.qml:27` ~ `studio/StudioSetup.tsx:164` |
| Studio tạo sách | Tách theo {} | Tách theo | 1.00 | `qt/NewHints.qml:86` ~ `studio/NewProjectScreen.tsx:896` |
| Studio tạo sách | Đã có mẫu tên “{}” | Đã có mẫu “ | 0.82 | `qt/TemplateLogic.js:51` ~ `studio/TemplateBar.tsx:180` |
| Studio tạo sách | Cập nhật {} | Cần cập nhật {} | 0.80 | `qt/StudioSetupLogic.js:61` ~ `studio/StudioSetup.tsx:377` |
| Studio tạo sách | Máy này {}. | Máy thấy | 0.80 | `qt/StudioSetupLogic.js:16` ~ `studio/VolumeSplit.tsx:102` |
| Studio tạo sách | Chia {} phần? | Phần {}: {} | 0.67 | `qt/NewVolumes.qml:51` ~ `studio/NewProjectScreen.tsx:633` |
| Studio việc duyệt | Bỏ qua mọi việc từ | Bỏ qua mọi việc từ {}? | 1.00 | `qt/PhoneEdits.qml:152` ~ `studio/PhoneEdits.tsx:255` |
| Studio việc duyệt | Dùng “{}” | Dùng “ | 1.00 | `qt/ReadingProblem.qml:39` ~ `studio/ReadingProblem.tsx:26` |
| Studio việc duyệt | Máy nghe ra: “{}” | Máy nghe ra: “ | 1.00 | `qt/ReviewLogic.js:41` ~ `studio/ReviewQueue.tsx:231` |
| Studio việc duyệt | Mọi việc đã có quyết định | Mọi việc đã có quyết định{}. | 1.00 | `qt/WorkLogic.js:274` ~ `studio/WorkInbox.tsx:1300` |
| Studio việc duyệt | Sẽ đọc là “{}” | Sẽ đọc là “ | 1.00 | `qt/ReviewLogic.js:46` ~ `studio/ReviewQueue.tsx:241` |
| Studio việc duyệt | Đã dùng | Dùng “ | 1.00 | `qt/WorkStore.qml:323` ~ `studio/ReadingProblem.tsx:26` |
| Studio việc duyệt | Đúng rồi, giữ “{}” | Đúng rồi, giữ “ | 1.00 | `qt/WorkPronunciation.qml:34` ~ `studio/WorkInbox.tsx:356` |
| Studio việc duyệt | Đoạn này do | Đoạn này do {} kể | 0.88 | `qt/WorkLogic.js:47` ~ `studio/workText.ts:22` |
| Studio việc duyệt | Tải tiếp · còn | Tải tiếp · còn {} câu | 0.86 | `qt/ReviewLogic.js:59` ~ `studio/ReviewQueue.tsx:524` |
| Studio việc duyệt | Nghe liền {} câu | Nghe liền | 0.82 | `qt/ReviewQueue.qml:253` ~ `studio/ReviewQueue.tsx:474` |
| Studio việc duyệt | Xem {} câu | Sửa {} câu | 0.57 | `qt/WorkSpeaker.qml:144` ~ `studio/reviewText.ts:20` |
| Studio xuất và áp dụng | Bỏ cách đọc “{} | Bỏ cách đọc “{}” | 1.00 | `qt/ExportLogic.js:275` ~ `studio/ApplyChanges.tsx:55` |
| Studio xuất và áp dụng | Cỡ ước tính: khoảng {} | Cỡ ước tính: khoảng | 1.00 | `qt/ExportBook.qml:220` ~ `studio/ExportBook.tsx:518` |
| Studio xuất và áp dụng | Xuất “ | Xuất “{}” | 1.00 | `qt/ExportBook.qml:49` ~ `studio/ExportBook.tsx:387` |
| Studio xuất và áp dụng | Đang thêm chữ sáng… | Đang thêm chữ sáng… {}% | 1.00 | `qt/ExportLogic.js:257` ~ `studio/WordTimings.tsx:42` |
| Studio xuất và áp dụng | Đã xuất | Xuất “{}” | 0.73 | `qt/ExportLogic.js:111` ~ `studio/ExportBook.tsx:387` |
| Thanh phát | Nghe bằng giọng đọc. | Nghe bằng giọng đọc.{} | 1.00 | `qt/PlayerLabels.js:9` ~ `listen/labels.ts:142` |
| Trang sách | Lần nghe | Lần nghe {} | 1.00 | `qt/RecordLogic.js:9` ~ `listen/BookScreen.tsx:701` |
| Trang sách | Tạo và nghe từ đầu | Tạo và nghe | 0.76 | `qt/RecordLogic.js:74` ~ `listen/BookScreen.tsx:851` |
| Trang sách | Hồ sơ nghe: {} | Đã nghe {} | 0.59 | `qt/RecordChip.qml:12` ~ `listen/BookScreen.tsx:1146` |
| Đang nghe | Hẹn giờ tắt | Hẹn giờ đã tắt tiếng lúc | 0.63 | `qt/NowPlaying.qml:409` ~ `listen/PlayerViews.tsx:997` |

## b. Cùng nhãn khác icon, cùng icon khác nhãn

**Cùng nhãn, khác icon** (4 nhãn Qt có icon mà icon ấy không đi với nhãn này ở bất cứ đâu trên web máy tính):

| nhãn | web | Qt | nơi |
|---|---|---|---|
| Bắt đầu | headphones | wand-sparkles | `qt/NewProjectScreen.qml:175` ~ `desktop/AudiobookDialog.tsx:216` |
| Chi tiết | info | chevron-right | `qt/MyMusicDetails.qml:28` (+1) ~ `studio/ProjectScreen.tsx:791` |
| Quay lại | chevron-left | arrow-left | `qt/ScreenHeader.qml:12` ~ `listen/LineWishes.tsx:223` (+2) |
| Tạm dừng {} | check, circle-dashed, play | pause | `qt/BookCell.qml:77` ~ `listen/BookScreen.tsx:161` (+2) |

**Cùng icon, khác nhãn** (63 cặp Qt; web cùng màn dùng cùng icon với nhãn khác):

| màn | icon | Qt | web cùng màn | nơi |
|---|---|---|---|---|
| Thêm sách | copy | Thêm bản riêng | Thêm bản riêng / Vẫn thêm bản mới | `qt/AddBook.qml:456` |
| Thêm sách | copy | Vẫn thêm bản mới | Thêm bản riêng / Vẫn thêm bản mới | `qt/AddBook.qml:456` |
| Thêm sách | file-text | Chọn file sách | Đang đọc / Chọn file sách | `qt/AddBook.qml:549` |
| Thêm sách | file-text | Đang đọc… | Đang đọc / Chọn file sách | `qt/AddBook.qml:549` |
| Cài đặt | download | Cập nhật ABook | Cài Studio, Cài tiếp, Có ABook {} | `qt/AdvancedUpdate.qml:95` |
| Cài đặt | download | Đang tải bản mới… | Cài Studio, Cài tiếp, Có ABook {} | `qt/AdvancedUpdate.qml:95` |
| Thư viện | play | Nghe ngay {} | Đọc {} | `qt/BookCell.qml:77` |
| Thư viện | play | Nghe {} | Đọc {} | `qt/BookCell.qml:77` |
| Thư viện | pause | Tạm dừng {} | Đọc {} | `qt/BookCell.qml:77` |
| Thư viện | laptop | Có sách trên máy khác | tập, {}, đã tải về máy này | `qt/BookCell.qml:127` |
| Thư viện | laptop | Trên {} | tập, {}, đã tải về máy này | `qt/BookCell.qml:127` |
| Trang sách | check-check | Chưa nghe xong | Chưa nghe / Đã nghe xong, Chưa nghe xong / Đã nghe xong | `qt/BookPage.qml:148` |
| Trang sách | check-check | Đã nghe xong | Chưa nghe / Đã nghe xong, Chưa nghe xong / Đã nghe xong | `qt/BookPage.qml:148` |
| Trang sách | circle-dashed | Chưa nghe | Chưa nghe / Đã nghe xong, Tạm dừng {} | `qt/BookPage.qml:274` |
| Trang sách | check-check | Đã nghe xong | Chưa nghe / Đã nghe xong, Chưa nghe xong / Đã nghe xong | `qt/BookPage.qml:274` |
| Trang sách | git-merge | Gộp | Gộp vào người khác | `qt/CastMerge.qml:162` |
| Trang sách | audio-lines | Dừng | Chưa có giọng, Dàn nhân vật hiện ra khi truyện đã được phâ… | `qt/CastSample.qml:53` |
| Đang nghe | play | Nghe từ đầu chương | Dừng / Thử, Nghe {} | `qt/ChapterList.qml:44` |
| Studio tạo sách | image-plus | Đặt bìa | Đổi ảnh bìa | `qt/CoverEditor.qml:132` |
| Studio tạo sách | image-plus | Đổi bìa | Đổi ảnh bìa | `qt/CoverEditor.qml:132` |
| Studio tạo sách | image-plus | Đặt ảnh bìa | Đổi ảnh bìa | `qt/CoverEditor.qml:141` |
| Studio tạo sách | trash | Bỏ ảnh bìa | Bỏ chương {}, Bỏ chỗ cắt trước {}, Bỏ ảnh bìa, dùng lại bìa vẽ từ tên sách | `qt/CoverEditor.qml:168` |
| Sửa sách | image-plus | Chọn ảnh bìa… | Đổi ảnh bìa / Chọn ảnh bìa | `qt/EditBook.qml:239` |
| Sửa sách | image-plus | Đổi ảnh bìa… | Đổi ảnh bìa / Chọn ảnh bìa | `qt/EditBook.qml:239` |
| Sửa sách | file-down | Lưu thành… | Lưu | `qt/EditBookItems.qml:81` |
| Sửa sách | trash | Xoá | Bỏ ảnh bìa | `qt/EditBookMyMusic.qml:296` |
| Sửa sách | trash | Xoá bài | Bỏ ảnh bìa | `qt/EditBookMyMusic.qml:310` |
| Sửa sách | trash | Bỏ cách đọc {} | Bỏ ảnh bìa | `qt/EditBookReadings.qml:120` |
| Thêm sách | book-plus | Thả để thêm sách | Thêm vào thư viện | `qt/ImportDrop.qml:48` |
| Thư viện | play | Nghe tiếp | Đọc {} | `qt/LibraryContinue.qml:42` |
| Thư viện | pause | Tạm dừng | Đọc {} | `qt/LibraryContinue.qml:42` |
| Thư viện | x | Đóng ô tìm | Xoá ô tìm | `qt/LibraryScreen.qml:173` |
| Thư viện | search | Chưa có cuốn nào nghe xong. | Thử tên sách hoặc tác giả khác., Tìm sách | `qt/LibraryScreen.qml:445` |
| Cài đặt | upload | Đang thêm {}/{} | Thêm nhạc của bạn | `qt/MyMusicSettings.qml:145` |
| Cài đặt | square | Dừng nghe | Dừng, Dừng / Nghe thử, Dừng lượt cũ | `qt/MyMusicTrack.qml:105` |
| Cài đặt | play | Nghe thử | Dừng / Nghe thử | `qt/MyMusicTrack.qml:105` |
| Studio tạo sách | layers | Phần | Chia thành nhiều phần, Chia thành {} phần / Chia thành mấy phần? | `qt/NewChapters.qml:205` |
| Studio tạo sách | layers | Chọn {} tập | Chia thành nhiều phần, Chia thành {} phần / Chia thành mấy phần? | `qt/NewDrop.qml:209` |
| Studio tạo sách | scissors | Tách thành {} chương | Tách thành chương | `qt/NewHints.qml:92` |
| Studio tạo sách | wand-sparkles | Bắt đầu | Bắt đầu / Tạo sách | `qt/NewProjectScreen.qml:175` |
| Đang nghe | moon | Hẹn giờ | {} trên {} | `qt/NowPlaying.qml:401` |
| Đang nghe | moon | Hết chương | {} trên {} | `qt/NowPlaying.qml:401` |
| Cài đặt | bluetooth | Dùng Bluetooth | Dùng Bluetooth cho {} | `qt/OtherComputersBluetooth.qml:21` |
| Cài đặt | refresh-cw | Làm mới | Hỏi lại, Hỏi lại thư viện | `qt/PhoneDiagnostics.qml:67` |
| Cài đặt | save | Lưu nhật ký | Gửi nhật ký | `qt/PhoneDiagnostics.qml:68` |
| Studio dự án | ellipsis | Tuỳ chọn dự án | Tuỳ chọn Studio, Tuỳ chọn dự án {}, Tuỳ chọn {} | `qt/ProjectScreen.qml:327` |
| Studio dự án | circle-alert | Chưa khởi động được: {} | Chưa mở được sách, Cuốn này đã bị xoá hoặc chuyển đi khỏi thư … | `qt/ProjectScreen.qml:467` |
| Studio việc duyệt | list-music | Nghe liền {} câu | Nghe liền câu | `qt/ReviewQueue.qml:252` |
| Studio việc duyệt | rotate-ccw | Cần thu lại | Cần thu lại / Thu lại câu này, Hoàn tác, Khôi phục tất cả | `qt/ReviewRow.qml:283` |
| Studio việc duyệt | rotate-ccw | Thu lại câu này | Cần thu lại / Thu lại câu này, Hoàn tác, Khôi phục tất cả | `qt/ReviewRow.qml:283` |
| Studio kịch bản | refresh-cw | Thu lại câu này | Thu lại câu: {}, Thu lại {} câu / Chưa có bản thu | `qt/ScriptRow.qml:296` |
| Studio kịch bản | refresh-cw | Chưa có bản thu | Thu lại câu: {}, Thu lại {} câu / Chưa có bản thu | `qt/ScriptTab.qml:482` |
| Studio kịch bản | refresh-cw | Thu lại {} câu | Thu lại câu: {}, Thu lại {} câu / Chưa có bản thu | `qt/ScriptTab.qml:482` |
| Studio kịch bản | check | Duyệt {} câu | Duyệt câu | `qt/ScriptTab.qml:584` |
| Cài đặt | trash | Gỡ Studio | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/StudioSettings.qml:122` |
| Cài đặt | trash | Xác nhận gỡ | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/StudioSettings.qml:122` |
| Cài đặt | trash | Đang gỡ… | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/StudioSettings.qml:122` |
| Studio tạo sách | clapperboard | Tạo trên {} | Tạo trên | `qt/StudioSetupNotice.qml:98` |
| Studio việc duyệt | pause | Dừng | Dừng / Nghe thử | `qt/TryButton.qml:11` |
| Studio việc duyệt | volume-2 | Nghe thử | Dừng / Nghe thử | `qt/TryButton.qml:11` |
| Cài đặt | play | Thử giọng | Dừng / Nghe thử | `qt/VoiceRow.qml:105` |
| Studio việc duyệt | check | Giữ {} thẻ… | Giữ cả thẻ, Giữ thẻ, Giữ “{}” - không cần áp dụng. / Đã ghi “{}”… | `qt/WorkBulkKeep.qml:25` |
| Studio việc duyệt | search | Xem {} câu | Tìm người khác, Xem câu | `qt/WorkSpeaker.qml:143` |

Số cặp: web máy tính 279, Qt 245. Nhãn Qt có icon (187): `Bài nhạc`, `Bấm để cập nhật`, `Bấm để đổi tên chương`, `Bật tiếng`, `Bắt đầu`, `Bỏ chương này`, `Bỏ cách đọc {}`, `Bỏ ghép`, `Bỏ qua tất cả`, `Bỏ qua việc này`, `Bỏ ảnh bìa`, `Bỏ “{}” khỏi cách đọc chung`, `Chi tiết`, `Chia thành nhiều phần`, `Chưa có bản thu`, `Chưa có cuốn nào nghe xong.`, `Chưa khởi động được: {}`, `Chưa nghe`, `Chưa nghe xong`, `Chương`, `Chương sau`, `Chương sau chưa có audio`, `Chương trước`, `Chẩn đoán`, `Chọn`, `Chọn file`, `Chọn file sách`, `Chọn lại nhạc`, `Chọn thư mục`, `Chọn thư mục TXT`, `Chọn từng file`, `Chọn {} tập`, `Chọn ảnh bìa…`, `Cài Studio`, `Cài đặt`, `Có ABook`, `Có sách trên máy khác`, `Cần thu lại`, `Cập nhật ABook`, `Cửa sổ mini`, `Duyệt {} câu`, `Dùng Bluetooth`, `Dùng {} cách đọc chung`, `Dừng`, `Dừng nghe`, `Dừng nghe liền`, `Dự án mới`, `Ghim trên cùng`, `Ghép thiết bị mới`, `Giọng {} đang không dùng được.`, `Giọng đọc`, `Giữ {} thẻ…`, `Gộp`, `Gộp vào người khác…`, `Gộp vào phần trước`, `Gỡ Studio`, `Gợi ý đọc`, `Gửi nhật ký`, `Hoàn tác`, `Huỷ tải`, `Hẹn giờ`, `Hết chương`, `Hỏi lại thư viện`, `Khôi phục tất cả`, `Khôi phục việc này`, `Không có mạng -`, `Khởi động lại`, `Kiểm tra`, `Làm mới`, `Lưu`, `Lưu nhật ký`, `Lưu thay đổi`, `Lưu thành…`, `Lưu thành mẫu…`, `Mở cuốn đó`, `Mở file sách`, `Mở Kịch bản`, `Mở màn hình đang nghe`, `Mở rộng`, `Mở Studio`, `Mở tab Nhạc nền`, `Mở thư mục`, `Mở thư mục nhật ký`, `Nghe liền {} câu`, `Nghe lại`, `Nghe ngay {}`, `Nghe thử`, `Nghe tiếp`, `Nghe từ đầu chương`, `Nghe {}`, `Người khác…`, `Người kể khác…`, `Nhạc nền`, `Nhập nhạc`, `Nên dùng`, `Phát`, `Phím tắt`, `Phần`, `Quay lại`, `Studio`, `Sửa cách đọc {}`, `Sửa sách`, `Sửa thông tin`, `Thiết bị phát`, `Thu gọn`, `Thu lại câu này`, `Thu lại {} câu`, `Thu nhỏ`, `Thêm`, `Thêm bản riêng`, `Thêm cách đọc`, `Thêm file`, `Thêm giọng…`, `Thêm nhạc của bạn`, `Thêm sách`, `Thêm tuỳ chọn`, `Thêm tuỳ chọn cho {}`, `Thêm vào thư viện`, `Thư viện`, `Thả để thêm sách`, `Thử giọng`, `Thử lại`, `Trên {}`, `Tuỳ chọn dự án`, `Tuỳ chọn Studio`, `Tách thành {} chương`, `Tìm`, `Tìm bìa…`, `Tìm người khác…`, `Tìm sách`, `Tìm ảnh bìa trên mạng`, `Tạm dừng`, `Tạm dừng {}`, `Tạo sách nói`, `Tạo trên {}`, `Tải thêm (3,2 GB)`, `Tắt tiếng`, `Tới câu đang nghe`, `Tự tìm`, `Vẫn cài`, `Vẫn thêm bản mới`, `Về chỗ vừa nghe`, `Về Cài đặt`, `Về màn trước`, `Về Studio`, `Về Thư viện`, `Xem tất cả`, `Xem {} câu`, `Xoá`, `Xoá bài`, `Xoá khoá`, `Xoá ô tìm`, `Xác nhận gỡ`, `Xếp theo`, `Áp dụng trước`, `Áp dụng tất cả`, `Áp dụng việc này`, `Đang chuẩn bị giọng đọc…`, `Đang chọn lại`, `Đang gỡ…`, `Đang mở…`, `Đang thêm {}/{}`, `Đang tải bản mới…`, `Đang tải âm thanh…`, `Đang đọc…`, `Đang đọc không khí`, `Đang đổi`, `Đây là chương cuối`, `Đã nghe xong`, `Đóng`, `Đóng lời báo`, `Đóng trình phát`, `Đóng ô tìm`, `Đặt bìa`, `Đặt ảnh bìa`, `Đọc chương này`, `Đọc lại ngữ cảnh`, `Đọc {}`, `Đổi bài`, `Đổi bìa`, `Đổi giọng người kể`, `Đổi giọng {}`, `Đổi giới tính`, `Đổi tên`, `Đổi tên chương…`, `Đổi ảnh bìa`, `Ổn`.

## c. Nhãn chỉ có một bên, theo màn

Nhãn ngắn (<= 6 chữ). **Chỉ Qt**: không có ở web cùng màn; `*` = web có ở màn khác. **Chỉ web**: nhãn web của màn không có ở đâu trong Qt - phần lớn là tính năng Qt chưa làm (bản thử), chỉ đếm và kể 15 đầu.

### Khay và cửa sổ mini

- chỉ Qt (11): Ghim trên cùng (`qt/MiniPlayer.qml:52`); Mở rộng (`qt/MiniPlayer.qml:58`); Lùi {} giây* (`qt/MiniPlayer.qml:86`); Phát* (`qt/MiniPlayer.qml:87`); Tạm dừng* (`qt/MiniPlayer.qml:87`); Tới {} giây* (`qt/MiniPlayer.qml:88`); Chương sau* (`qt/TrayMenuModel.qml:12`); Chương trước* (`qt/TrayMenuModel.qml:12`); Cửa sổ mini (`qt/TrayMenuModel.qml:12`); Mở ABook (`qt/TrayMenuModel.qml:12`); Thoát ABook (`qt/TrayMenuModel.qml:12`)
- chỉ web (0): (không có)

### Thư viện

- chỉ Qt (8): Tạm dừng* (`qt/LibraryContinue.qml:41`); Mới thêm* (`qt/LibraryScreen.qml:47`); Tác giả* (`qt/LibraryScreen.qml:47`); Tên sách* (`qt/LibraryScreen.qml:47`); Đang mở ABook* (`qt/LibraryScreen.qml:354`); Chưa mở được ABook (`qt/LibraryScreen.qml:400`); Chưa tải được thư viện (`qt/LibraryScreen.qml:400`); Thử lại* (`qt/LibraryScreen.qml:417`)
- chỉ web (8): Đang tạm dừng {} (`329`); Đang làm {} (`330`); Đang tạm dừng{} (`334`); Chưa có chương nghe được{} (`336`); Đang làm · {} (`336`); Thư viện chưa có sách nào. (`456`); Chưa có sách trên máy (`561`); Chữ bìa trên hoạ tiết sóng (`78`)

### Thanh phát

- chỉ Qt (8): Không có mạng - (`qt/PlayerAlert.qml:9`); Giọng {} đang không dùng được.* (`qt/PlayerAlert.qml:22`); Cửa sổ mini (`qt/PlayerBar.qml:111`); Hẹn giờ* (`qt/PlayerBar.qml:139`); Nhạc nền* (`qt/PlayerBar.qml:142`); Giọng đọc* (`qt/PlayerBar.qml:143`); Nghe bằng giọng đọc. (`qt/PlayerLabels.js:9`); Thêm giọng…* (`qt/PlayerVoicePopover.qml:30`)
- chỉ web (7): Shift+← (`264`); Sắp tắt · (`1268`); Nghe tiếp · {} (`81`); Shift+→ (`99`); Chưa có audio (`109`); Chạm (`120`); Nghe bằng giọng đọc.{} (`142`)

### Đang nghe

- chỉ Qt (19): Tạm dừng {}* (`qt/ChapterList.qml:26`); Đọc {} (chưa có audio)* (`qt/ChapterList.qml:26`); Đọc chương này* (`qt/ChapterList.qml:45`); Đọc* (`qt/ChapterReader.qml:14`); Chưa có chương để đọc. (`qt/ChapterReader.qml:33`); Đang tải chương… (`qt/ChapterReader.qml:86`); Thử lại* (`qt/ChapterReader.qml:91`); Đã nghe* (`qt/ChapterRow.qml:49`); Tuỳ chọn {}* (`qt/ChapterRow.qml:101`); Thêm tuỳ chọn* (`qt/NowPlaying.qml:212`); Bìa (`qt/NowPlaying.qml:235`); Giọng {}* (`qt/NowPlaying.qml:264`); Hẹn giờ tắt (`qt/NowPlaying.qml:409`); Danh sách chương* (`qt/NowPlaying.qml:424`); Nhạc nền* (`qt/NowPlaying.qml:435`); Cửa sổ mini (`qt/NowPlaying.qml:538`); Gợi ý cho phần đọc* (`qt/ReadingSuggestions.qml:8`); Bỏ dòng (`qt/ReadingSuggestions.qml:56`); Đóng* (`qt/ReadingSuggestions.qml:78`)
- chỉ web (15): Shift+← (`264`); Đã chọn tốc độ đọc {} (`465`); Phím (`480`); Đã chọn giọng {} (`765`); Hẹn giờ đã tắt tiếng lúc (`997`); Bật lại (`1006`); Tiếng nhỏ dần (`1014`); Hẹn giờ ngủ trên {} (`1080`); Nghe tiếp · {} (`81`); Shift+→ (`99`); Chưa có audio (`109`); Chạm (`120`); Nghe bằng giọng đọc.{} (`142`); Hẹn giờ ngủ: còn {} giây (`84`); Hẹn giờ ngủ: còn {} phút (`84`)

### Đọc theo

- chỉ Qt (1): Đang mở văn bản chương… (`qt/ReadAlongView.qml:330`)
- chỉ web (3): Đang tải chữ (`1715`); Nghe từ “{}” (`55`); Shift F10: sửa cách đọc. (`339`)

### Trang sách

- chỉ Qt (64): Thêm* (`qt/BookPage.qml:490`); Thêm việc với sách (`qt/BookPage.qml:491`); Chưa tải được giọng* (`qt/CastEngine.qml:71`); Tải giọng* (`qt/CastEngine.qml:79`); Chưa huỷ được việc tải giọng* (`qt/CastEngine.qml:114`); Giới tính của {}* (`qt/CastGender.qml:16`); Hiện đang là nhân vật {}.* (`qt/CastGender.qml:17`); Chưa đổi được giới tính* (`qt/CastGender.qml:25`); Giới tính* (`qt/CastGender.qml:47`); Nữ* (`qt/CastGender.qml:49`); Nếu giọng* (`qt/CastGender.qml:66`); Ghi lại* (`qt/CastGender.qml:82`); Thôi* (`qt/CastGender.qml:82`); Đang tải nhân vật (`qt/CastList.qml:84`); Gộp nhân vật* (`qt/CastMerge.qml:17`); Chưa gộp được* (`qt/CastMerge.qml:28`); Đã ghi:* (`qt/CastMerge.qml:28`); Tìm người trong truyện…* (`qt/CastMerge.qml:50`); Gộp vào ai* (`qt/CastMerge.qml:67`); Không có ai khớp “{}”. (`qt/CastMerge.qml:136`); Gộp* (`qt/CastMerge.qml:158`); Chưa hoàn tác được* (`qt/CastModal.qml:23`); Hoàn tác* (`qt/CastModal.qml:23`); Đã hoàn tác (`qt/CastModal.qml:23`); Đã hoàn tác. {} (`qt/CastModal.qml:23`); Đổi tên {}* (`qt/CastRename.qml:13`); Chưa đổi được tên* (`qt/CastRename.qml:25`); Đã trở về tên gốc: {}* (`qt/CastRename.qml:25`); Đã đổi tên thành {}* (`qt/CastRename.qml:25`); Tên mới của {}* (`qt/CastRename.qml:47`); Tên gốc:* (`qt/CastRename.qml:57`); Về tên gốc* (`qt/CastRename.qml:63`); Chưa bỏ gộp được* (`qt/CastUnmerge.qml:12`); Đã bỏ gộp {}* (`qt/CastUnmerge.qml:12`); Chưa đổi được giọng* (`qt/CastVoice.qml:68`); Giọng (`qt/CastVoice.qml:68`); Chưa bỏ được lựa chọn* (`qt/CastVoice.qml:87`); Đã bỏ lựa chọn giọng* (`qt/CastVoice.qml:87`); Đã bỏ lựa chọn {}* (`qt/CastVoice.qml:87`); Đang tải giọng đọc* (`qt/CastVoice.qml:115`); Thử lại* (`qt/CastVoice.qml:140`); Chờ áp dụng: đổi sang* (`qt/CastVoice.qml:159`); Giữ* (`qt/CastVoice.qml:166`); Giữ như cũ* (`qt/CastVoice.qml:206`); Lọc giọng theo giới* (`qt/CastVoice.qml:213`); Tất cả* (`qt/CastVoice.qml:215`); Đang dùng* (`qt/CastVoice.qml:335`); Máy gợi ý* (`qt/CastVoice.qml:349`); Giữ giọng này* (`qt/CastVoice.qml:372`); Dùng chung giọng* (`qt/CastVoice.qml:393`); Tìm hiểu thêm* (`qt/CastVoice.qml:393`); Đang tải lịch sử (`qt/HistoryList.qml:61`); Chủ Nhật (`qt/HistoryLogic.js:9`); Thứ Ba (`qt/HistoryLogic.js:9`); Thứ Bảy (`qt/HistoryLogic.js:9`); Thứ Hai (`qt/HistoryLogic.js:9`); Thứ Năm (`qt/HistoryLogic.js:9`); Thứ Sáu (`qt/HistoryLogic.js:9`); Thứ Tư (`qt/HistoryLogic.js:9`); Hồ sơ nghe: {} (`qt/RecordChip.qml:12`); Lần nghe (`qt/RecordLogic.js:9`); Đổi tên hồ sơ này… (`qt/RecordLogic.js:38`); Tạo và nghe từ đầu (`qt/RecordLogic.js:74`); Hồ sơ mới “ (`qt/RecordLogic.js:103`)
- chỉ web (11): Đã làm sẵn (`186`); Chờ áp dụng: giọng (`555`); Nghe tiếp từ (`677`); Lần nghe {} (`701`); Tạo và nghe (`851`); Chia sẻ (`1219`); Nghe tiếp · {} (`81`); Shift+→ (`99`); Chưa có audio (`109`); Chạm (`120`); Nghe bằng giọng đọc.{} (`142`)

### Cài đặt

- chỉ Qt (105): Chưa làm được lúc này. (`qt/BookTemplates.qml:26`); Chưa lưu được mẫu{} (`qt/BookTemplates.qml:26`); Chưa kết nối* (`qt/DevicesLogic.js:61`); Đang nối qua Bluetooth* (`qt/DevicesLogic.js:63`); Đang nối qua Tailscale* (`qt/DevicesLogic.js:68`); Đang nối qua Wi-Fi nhà* (`qt/DevicesLogic.js:69`); Đang nối qua mạng* (`qt/DevicesLogic.js:71`); Gửi trước rồi bỏ ghép* (`qt/DevicesLogic.js:108`); Thử gửi trước rồi bỏ ghép* (`qt/DevicesLogic.js:110`); Vẫn bỏ ghép, bỏ thay đổi* (`qt/DevicesLogic.js:114`); Tải sách* (`qt/DevicesLogic.js:139`); Xuất M4B* (`qt/DevicesLogic.js:139`); Xuất MP3* (`qt/DevicesLogic.js:139`); Xuất sách nói* (`qt/DevicesLogic.js:139`); Việc nền* (`qt/DevicesLogic.js:148`); Việc* (`qt/DevicesLogic.js:149`); Bản ABook* (`qt/DevicesLogic.js:175`); Giờ trên máy* (`qt/DevicesLogic.js:183`); Mạng* (`qt/DevicesLogic.js:191`); Chỗ trống* (`qt/DevicesLogic.js:197`); Thông báo* (`qt/DevicesLogic.js:201`); Chạy nền* (`qt/DevicesLogic.js:202`); Đang nghe* (`qt/DevicesLogic.js:206`); Cho máy khác nghe thư viện* (`qt/DevicesLogic.js:218`); Lần tắt gần nhất* (`qt/DevicesLogic.js:222`); Lần văng* (`qt/DevicesLogic.js:226`); Phục hồi dữ liệu* (`qt/DevicesLogic.js:227`); Chưa có dòng nào.* (`qt/DevicesLogic.js:241`); Đang tải* (`qt/DevicesSkeleton.qml:8`); Chưa lưu được cài đặt{} (`qt/ListenSave.qml:8`); Phím một chữ cái đang tắt (`qt/LookShortcuts.qml:11`); Cửa sổ mini (`qt/LookShortcuts.qml:14`); Tải lại ({}) (`qt/MyMusicModule.qml:34`); Bật đo cảm xúc (`qt/MyMusicModule.qml:38`); Tải tiếp ({}) (`qt/MyMusicModule.qml:38`); Tắt đo cảm xúc (`qt/MyMusicModule.qml:38`); Phân tích nhạc (`qt/MyMusicModule.qml:74`); Cảm xúc chính xác (`qt/MyMusicModule.qml:146`); Xoá file ({}) (`qt/MyMusicModule.qml:185`); Chưa đổi được* (`qt/MyMusicSettings.qml:95`); Chọn nhạc của bạn (`qt/MyMusicSettings.qml:119`); Đang phân tích nhạc đã thêm (`qt/MyMusicText.js:31`); Đang nghe kỹ bài vừa thêm (`qt/MyMusicText.js:63`); Chạy (`qt/MyMusicText.js:67`); Máy không tự chọn bài này (`qt/MyMusicText.js:80`); Tự chọn lại (`qt/MyMusicText.js:87`); Theo mặc định (`qt/MyMusicText.js:88`); Cho tự chọn (`qt/MyMusicText.js:89`); Tắt tự chọn (`qt/MyMusicText.js:89`); Chưa thêm được nhạc* (`qt/MyMusicText.js:116`); Đã thêm: {} (`qt/MyMusicText.js:121`); Chưa có bản đọc đã lưu.* (`qt/MyMusicText.js:131`); Ghi chú cho người bảo trì* (`qt/MyMusicText.js:147`); Dừng nghe (`qt/MyMusicTrack.qml:104`); Chất lượng cao* (`qt/NewBookDefaults.qml:11`); Cân bằng* (`qt/NewBookDefaults.qml:11`); Kết nối Wi-Fi* (`qt/OtherComputers.qml:33`); Chưa bỏ ghép được* (`qt/OtherComputers.qml:119`); Chưa ghép được: {} (`qt/OtherComputers.qml:336`); Dùng Bluetooth cho (`qt/OtherComputersBluetooth.qml:26`); Vân tay {} (`qt/OtherComputersRow.qml:98`); Mở Studio của (`qt/OtherComputersRow.qml:112`); Chưa lưu được nhật ký* (`qt/PhoneDiagnostics.qml:49`); Chọn nơi lưu nhật ký* (`qt/PhoneDiagnostics.qml:49`); Đã lưu nhật ký* (`qt/PhoneDiagnostics.qml:49`); Làm mới* (`qt/PhoneDiagnostics.qml:67`); Lưu nhật ký* (`qt/PhoneDiagnostics.qml:68`); Chi tiết kỹ thuật* (`qt/PhoneDiagnostics.qml:105`); Nhật ký của ABook ({} dòng)* (`qt/PhoneDiagnostics.qml:119`); Mở {}* (`qt/PhoneSync.qml:196`); Điều khiển sản xuất từ (`qt/PhoneSyncDevice.qml:86`); Địa chỉ: {} (`qt/PhoneSyncPairing.qml:57`); Mã ghép nối: (`qt/PhoneSyncPairing.qml:71`); Hết hạn sau {}:{} (`qt/PhoneSyncPairing.qml:80`); Dùng được · (`qt/ProviderKey.qml:40`); Khoá (`qt/ProviderKey.qml:138`); Tự chọn nhạc nền* (`qt/SettingsListen.qml:23`); Thu vào khay khi đóng (`qt/SettingsLook.qml:13`); Tự mở cửa sổ mini (`qt/SettingsLook.qml:18`); Giấy* (`qt/SettingsLook.qml:33`); Ngà* (`qt/SettingsLook.qml:33`); Đêm* (`qt/SettingsLook.qml:33`); Số phút hẹn (`qt/SleepWindow.qml:55`); Cần cập nhật* (`qt/StudioSettings.qml:139`); Mất {} (`qt/StudioSettings.qml:139`); Giọng của máy* (`qt/VoiceLogic.js:37`); Nữ* (`qt/VoiceLogic.js:42`); Ngọc Linh* (`qt/VoiceLogic.js:90`); Phạm Tuyên* (`qt/VoiceLogic.js:90`); Thanh Bình* (`qt/VoiceLogic.js:90`); Mỹ Duyên* (`qt/VoiceLogic.js:91`); Ái Hân* (`qt/VoiceLogic.js:91`); Đức Trí* (`qt/VoiceLogic.js:91`); Giọng VieNeu* (`qt/VoiceLogic.js:121`); Giọng Supertonic* (`qt/VoiceLogic.js:126`); Giọng VieNeu Nano* (`qt/VoiceLogic.js:130`); Đang đọc bằng bản thường.* (`qt/VoiceLogic.js:208`); Đang đọc bằng bản tăng tốc.* (`qt/VoiceLogic.js:210`); Máy này chưa dùng được {}. (`qt/VoiceLogic.js:243`); Tốc độ đọc* (`qt/VoiceLogic.js:266`); Chất lượng cao nhất* (`qt/VoiceLogic.js:269`); Nhanh hơn* (`qt/VoiceLogic.js:270`); Gỡ (`qt/VoiceModule.qml:261`); Thử giọng (`qt/VoiceRow.qml:104`); Thử* (`qt/VoiceRow.qml:108`)
- chỉ web (29): Chưa lưu được mẫu (`23`); Mở Studio của {} (`205`); Hỏi lại (`229`); Dùng Bluetooth cho {} (`359`); Bluetooth (`368`); Địa chỉ: (`155`); Trình duyệt: mở (`156`); Mã ghép nối: {} (`161`); Hết hạn sau (`169`); Kết nối lần cuối (`366`); Điều khiển sản xuất từ {} (`373`); Chưa đổi được lịch đêm (`26`); ABook{} là bản mới nhất. (`21`); Space (`17`); Chưa nghe thử được giọng này. (`110`); ...

### Thêm sách

- chỉ Qt (25): Chưa mở được file sách* (`qt/AddBook.qml:222`); Đã mở (`qt/AddBook.qml:233`); Bỏ qua* (`qt/AddBook.qml:400`); Đang đọc file tiếp (`qt/AddBook.qml:527`); Đang đọc file sách (`qt/AddBook.qml:585`); Không đọc số chú thích (`qt/AddBook.qml:879`); Đọc lời chú ở cuối chương (`qt/AddBook.qml:888`); Bỏ lời chú* (`qt/AddBook.qml:896`); Bỏ dòng này khỏi phần đọc (`qt/AddBook.qml:965`); Đang thêm {} (`qt/AddBook.qml:1006`); Tất cả file (*) (`qt/AddBook.qml:1038`); Đưa vào sách: (`qt/ImportChapters.qml:100`); Bấm để đổi tên chương* (`qt/ImportChapters.qml:135`); Tên chương* (`qt/ImportChapters.qml:171`); Thả để thêm sách* (`qt/ImportDrop.qml:52`); Thử lại* (`qt/ImportError.qml:50`); Tách theo {} dòng “Chương N” (`qt/ImportQueue.js:118`); File này có bản thu khác* (`qt/ImportQueue.js:197`); Sách đã có* (`qt/ImportQueue.js:197`); Đã cập nhật* (`qt/ImportQueue.js:197`); Sách của Studio* (`qt/ImportQueue.js:198`); Đã khôi phục file* (`qt/ImportQueue.js:198`); Đã mở dự án* (`qt/ImportQueue.js:198`); Đã gộp {} sửa từ file* (`qt/ImportQueue.js:205`); Đang tải* (`qt/ImportSkeleton.qml:10`)
- chỉ web (2): Xem trước (`543`); Tách chương (`730`)

### Sửa sách

- chỉ Qt (55): Mức nhạc dưới giọng đọc (`qt/BookMusicSettings.qml:110`); Chưa đọc được file ảnh* (`qt/EditBook.qml:405`); Thử lại* (`qt/EditBookError.qml:45`); Lưu thay đổi* (`qt/EditBookItems.qml:70`); Hơi to* (`qt/EditBookLogic.js:49`); Nhỏ* (`qt/EditBookLogic.js:49`); Rất nhỏ* (`qt/EditBookLogic.js:49`); Vừa (mặc định)* (`qt/EditBookLogic.js:49`); Chưa nối được {} (`qt/EditBookLogic.js:79`); Máy không tự chọn bài này (`qt/EditBookLogic.js:90`); Tự chọn lại (`qt/EditBookLogic.js:95`); Theo mặc định (`qt/EditBookLogic.js:96`); Cho tự chọn (`qt/EditBookLogic.js:97`); Tắt tự chọn (`qt/EditBookLogic.js:97`); Hợp không khí đoạn này (`qt/EditBookLogic.js:101`); Đang phân tích nhạc đã thêm (`qt/EditBookLogic.js:112`); Chưa thêm được nhạc* (`qt/EditBookLogic.js:130`); Đã thêm: {} (`qt/EditBookLogic.js:135`); Đang thêm nhạc thì dừng* (`qt/EditBookMyMusic.qml:67`); Chưa xoá được bài này* (`qt/EditBookMyMusic.qml:80`); Đã xoá khỏi Nhạc của tôi* (`qt/EditBookMyMusic.qml:80`); Chọn nhạc của bạn (`qt/EditBookMyMusic.qml:113`); Nhạc của tôi* (`qt/EditBookMyMusic.qml:122`); Chưa có bài nào* (`qt/EditBookMyMusic.qml:123`); Thêm nhạc của bạn* (`qt/EditBookMyMusic.qml:132`); Đang thêm {}/{}* (`qt/EditBookMyMusic.qml:132`); Phân tích nhạc (`qt/EditBookMyMusic.qml:149`); Huỷ* (`qt/EditBookMyMusic.qml:165`); Cập nhật ({})* (`qt/EditBookMyMusic.qml:173`); Phân tích {} bài (`qt/EditBookMyMusic.qml:173`); Tải ({})* (`qt/EditBookMyMusic.qml:173`); Tải lại ({}) (`qt/EditBookMyMusic.qml:173`); Nhạc riêng* (`qt/EditBookMyMusic.qml:185`); Đang tải nhạc riêng* (`qt/EditBookMyMusic.qml:191`); Xoá* (`qt/EditBookMyMusic.qml:296`); Xoá: {}* (`qt/EditBookMyMusic.qml:297`); Xoá bài* (`qt/EditBookMyMusic.qml:310`); Xoá bài: {}* (`qt/EditBookMyMusic.qml:312`); Giữ lại* (`qt/EditBookMyMusic.qml:317`); Giữ lại: {}* (`qt/EditBookMyMusic.qml:319`); Chưa bỏ được cách đọc* (`qt/EditBookReadings.qml:27`); Chưa lưu được cách đọc* (`qt/EditBookReadings.qml:27`); Đang tải cách đọc* (`qt/EditBookReadings.qml:67`); Sửa cách đọc {}* (`qt/EditBookReadings.qml:112`); Bỏ cách đọc {}* (`qt/EditBookReadings.qml:122`); Cách đọc cho {}* (`qt/EditBookReadings.qml:141`); Lưu cho cả cuốn* (`qt/EditBookReadings.qml:152`); Đọc như chữ trong sách (`qt/EditBookReadings.qml:160`); Đổi tên chương* (`qt/EditBookRename.qml:18`); Số chương hay nhãn (`qt/EditBookRename.qml:43`); Tên chương (có thể để trống) (`qt/EditBookRename.qml:43`); Chọn nơi lưu* (`qt/EditBookSaveAs.qml:51`); Đang tải* (`qt/EditBookSkeleton.qml:10`); Đang tải bài nhạc* (`qt/EditBookSwap.qml:36`); Chọn* (`qt/EditBookSwap.qml:91`)
- chỉ web (7): Mức nhạc nền (`192`); Bỏ mọi thay đổi ({}) (`488`); Nhãn (`574`); Tên (`585`); Chưa chia sẻ được sách (`641`); Google Books (`12`); Open Library (`12`)

### Thanh bên

- chỉ Qt (10): Trạng thái ABook (`qt/ConnectionChip.qml:9`); Gặp lỗi (`qt/ConnectionChip.qml:54`); Sẵn sàng (`qt/ConnectionChip.qml:54`); Đang mở…* (`qt/ConnectionChip.qml:54`); Bản {} (`qt/ConnectionPopover.qml:74`); Khởi động lại (`qt/ConnectionPopover.qml:86`); Mở thư mục nhật ký (`qt/ConnectionPopover.qml:94`); Mở rộng (`qt/Sidebar.qml:89`); Thu gọn* (`qt/Sidebar.qml:89`); Duyệt* (`qt/SidebarProgress.qml:35`)
- chỉ web (1): Thanh bên (`170`)

### Studio dự án

- chỉ Qt (42): Làm* (`qt/OnComputerPill.qml:9`); Chưa gộp được* (`qt/ProjectScreen.qml:134`); Chưa làm được lúc này. (`qt/ProjectScreen.qml:134`); Chưa khởi động được: {} (`qt/ProjectScreen.qml:471`); Chưa có chương nào (`qt/ProjectScreen.qml:734`); Đang tải nhật ký (`qt/ProjectScreen.qml:756`); Không thấy thư mục thư viện* (`qt/ProjectsScreen.qml:227`); Chọn thư mục* (`qt/ProjectsScreen.qml:230`); Chọn lại thư mục thư viện* (`qt/ProjectsScreen.qml:231`); Mở dự án có sẵn… (`qt/ProjectsScreen.qml:256`); Nghe* (`qt/StudioChapterRow.qml:47`); Chi tiết lỗi (`qt/StudioChapterRow.qml:119`); Tuỳ chọn* (`qt/StudioChapterRow.qml:194`); Đóng* (`qt/StudioDialogs.qml:62`); 0 phút* (`qt/StudioLogic.js:20`); Còn* (`qt/StudioLogic.js:94`); Sắp tới lượt (`qt/StudioLogic.js:94`); Chờ bạn duyệt (`qt/StudioLogic.js:99`); Mất kết nối tới ABook. (`qt/StudioLogic.js:119`); Đang tạm dừng* (`qt/StudioLogic.js:216`); Sách vẫn đang tạm dừng (`qt/StudioLogic.js:221`); Đang làm tiếp (`qt/StudioLogic.js:227`); Card đồ hoạ hết bộ nhớ.* (`qt/StudioLogic.js:262`); Ổ đĩa hết chỗ trống.* (`qt/StudioLogic.js:276`); Áp dụng* (`qt/StudioLogic.js:339`); Cài Studio* (`qt/StudioLogic.js:428`); Cập nhật Studio* (`qt/StudioLogic.js:428`); Sửa Studio* (`qt/StudioLogic.js:428`); Bộ phân tích bản {}* (`qt/StudioLogic.js:490`); Bộ phân tích tuỳ chọn* (`qt/StudioLogic.js:490`); Tạo {} (`qt/StudioLogic.js:503`); Lỗi {} (`qt/StudioStore.qml:47`); Chưa bắt đầu được (`qt/StudioStore.qml:130`); Chưa làm tiếp được (`qt/StudioStore.qml:148`); Chưa tạm dừng được (`qt/StudioStore.qml:148`); Chưa dừng được (`qt/StudioStore.qml:159`); Chưa bỏ xếp hàng được (`qt/StudioStore.qml:170`); Chưa mở được thư mục (`qt/StudioStore.qml:178`); Hoàn tác* (`qt/StudioStore.qml:193`); Chưa hoàn tác được* (`qt/StudioStore.qml:204`); Đã khôi phục “{}”* (`qt/StudioStore.qml:204`); Chưa đổi được* (`qt/StudioStore.qml:241`)
- chỉ web (8): Chưa khởi động được: (`196`); Làm tiếp từ chỗ ấy (`380`); Phân tích của “ (`380`); Tuỳ chọn dự án {} (`628`); Chờ lượt (`798`); Thu lại (`962`); Chưa tải được (`1440`); Chưa đọc được dự án này (`39`)

### Studio tạo sách

- chỉ Qt (37): Tìm ảnh bìa* (`qt/CoverEditor.qml:193`); Chọn ảnh bìa* (`qt/CoverPicker.qml:12`); Gợi ý: {} chương có {} (`qt/NewCredits.qml:59`); Chọn {} tập (`qt/NewDrop.qml:214`); Tách theo {} (`qt/NewHints.qml:86`); Truyện (*.txt *.epub *.docx *.pdf) (`qt/NewPicker.qml:17`); Tất cả file (*) (`qt/NewPicker.qml:17`); Đang đọc nguồn… (`qt/NewProjectLogic.js:47`); Nhân vật tự kể* (`qt/NewProjectLogic.js:191`); Thứ tự lệch: {} (`qt/NewProjectLogic.js:232`); Có vẻ thiếu {} (`qt/NewProjectLogic.js:233`); Bản thử nghiệm (`qt/NewProjectLogic.js:369`); Chưa làm được lúc này. (`qt/NewProjectStore.qml:58`); Chưa đọc được:* (`qt/NewProjectStore.qml:153`); Đã áp (`qt/NewProjectStore.qml:223`); Có file không gửi{} (`qt/NewProjectStore.qml:269`); Chưa gửi được. (`qt/NewProjectStore.qml:284`); Không gửi hết các chương{} {} (`qt/NewProjectStore.qml:312`); Phần {} của “{}” (`qt/NewSeedBanner.qml:37`); Tìm hiểu thêm* (`qt/NewTemplateBar.qml:143`); Dùng lại {} (`qt/NewVoice.qml:209`); Chia {} phần? (`qt/NewVolumes.qml:51`); Máy thấy {} (`qt/NewVolumes.qml:57`); Studio chưa xong{} (`qt/StudioSetupCard.qml:27`); Tiến độ:* (`qt/StudioSetupCard.qml:206`); Máy này {}. (`qt/StudioSetupLogic.js:16`); Tải lại {} (`qt/StudioSetupLogic.js:60`); Cập nhật {} (`qt/StudioSetupLogic.js:61`); Tạo trên {} (`qt/StudioSetupNotice.qml:97`); Mặc định* (`qt/TemplateLogic.js:11`); Đặt cho mẫu một cái tên (`qt/TemplateLogic.js:48`); Tên mẫu tối đa {} chữ (`qt/TemplateLogic.js:49`); Đã có mẫu tên “{}” (`qt/TemplateLogic.js:51`); Giọng máy đề xuất* (`qt/TemplateLogic.js:56`); Tải lên {} (`qt/UploadLogic.js:28`); Chưa gửi file nào. (`qt/UploadLogic.js:92`); Đã gửi {}/{} file, giữ lại (`qt/UploadLogic.js:94`)
- chỉ web (31): Bản thử nghiệm{} (`51`); Bản thử nghiệm ({}) (`57`); Nhanh (`93`); Có file không gửi (`304`); Không gửi hết các chương (`311`); Gửi các chương từ máy này (`436`); Phần {}: {} (`633`); Sẽ bỏ (`796`); Gợi ý: (`805`); Gợi ý: “ (`895`); Tách theo (`896`); Tách thành (`909`); Nam (`1162`); Giọng kể phần trước: (`1261`); Đang chọn: (`1288`); ...

### Studio việc duyệt

- chỉ Qt (31): Đã hoàn tác (`qt/DecisionLogic.js:31`); Đã hoàn tác. {} (`qt/DecisionLogic.js:31`); Trước đó chưa ai quyết khác (`qt/DecisionLogic.js:39`); Trước đó đang là {} (`qt/DecisionLogic.js:39`); Xem thêm {} tên (`qt/NameLogic.js:33`); Thêm* (`qt/NameLogic.js:45`); Đã bỏ qua ({}) (`qt/PhoneEdits.qml:82`); Bỏ qua mọi việc từ (`qt/PhoneEdits.qml:152`); Dùng “{}” (`qt/ReadingProblem.qml:39`); Máy nghe ra: “{}” (`qt/ReviewLogic.js:41`); Sẽ đọc là “{}” (`qt/ReviewLogic.js:46`); Tải tiếp · còn (`qt/ReviewLogic.js:59`); Nghe liền {} câu (`qt/ReviewQueue.qml:253`); Nghe câu: (`qt/ReviewRow.qml:82`); Đang đọc là: <span style="color:{}">{} (`qt/ReviewRow.qml:213`); Máy đọc câu này thành (`qt/ReviewSpoken.qml:41`); Ảnh hưởng <b><span style="color:{}">{} (`qt/WorkCard.qml:149`); Đang mở* (`qt/WorkCard.qml:339`); Đang đóng (`qt/WorkCard.qml:339`); Xem thêm {} việc (`qt/WorkInbox.qml:218`); Đoạn này do (`qt/WorkLogic.js:47`); Đang chọn cả {} câu* (`qt/WorkLogic.js:152`); Đang chọn {}/{} câu* (`qt/WorkLogic.js:154`); Xem thêm (đang hiện {}/{} câu)* (`qt/WorkLogic.js:163`); Mọi việc đã có quyết định (`qt/WorkLogic.js:274`); Đúng rồi, giữ “{}” (`qt/WorkPronunciation.qml:34`); Cả chuỗi (`qt/WorkSpeaker.qml:60`); Xem {} câu (`qt/WorkSpeaker.qml:144`); Chưa hoàn tác được* (`qt/WorkStore.qml:87`); Mới hoàn tác được {}/{} việc (`qt/WorkStore.qml:87`); Đã dùng (`qt/WorkStore.qml:323`)
- chỉ web (20): Không khớp “ (`166`); Bỏ qua mọi việc từ {}? (`237`); Dùng “ (`26`); Máy nghe ra: “ (`231`); Sẽ đọc là “ (`241`); Đang đọc là: (`246`); Nghe liền (`474`); Tải tiếp · còn {} câu (`524`); Nghe thử {} đọc là {} (`99`); Chưa nghe thử được: (`146`); Đúng rồi, giữ “ (`356`); Xem (`596`); Nam (`625`); Ảnh hưởng (`930`); Giữ cả {} thẻ “{}”? (`1078`); ...

### Studio nhân vật

- chỉ Qt (1): Đổi giọng kể* (`qt/TellerLogic.js:37`)
- chỉ web (6): Nam (`97`); Giọng đọc của (`162`); Áp dụng sẽ thu lại (`171`); Không có ai khớp “ (`127`); Nghe và chỉnh giọng cho (`228`); Giọng của {} (`252`)

### Studio kịch bản

- chỉ Qt (7): Người nghĩ (`qt/ScriptRow.qml:96`); Người nói (`qt/ScriptRow.qml:96`); Gán cho {} (`qt/ScriptRow.qml:244`); Thu lại câu này* (`qt/ScriptRow.qml:290`); Lấy của máy kia (`qt/ScriptStore.qml:52`); Đang chọn {} câu (`qt/ScriptTab.qml:464`); Duyệt {} câu (`qt/ScriptTab.qml:586`)
- chỉ web (8): Cách đọc câu này (`772`); Nam (`872`); Ai nghĩ câu này? (`945`); Đang chọn. (`1072`); Cách đọc mới không áp được: (`1110`); Gán cho (`1125`); Yêu cầu (`1155`); Thu lại câu này (R) (`1164`)

### Studio xuất và áp dụng

- chỉ Qt (27): Xuất “ (`qt/ExportBook.qml:49`); Kèm nhạc nền* (`qt/ExportBook.qml:207`); Cỡ ước tính: khoảng {} (`qt/ExportBook.qml:220`); Xuất {} chương đổi (`qt/ExportBook.qml:303`); Đang đóng gói* (`qt/ExportLogic.js:50`); Đã xuất vào máy tính* (`qt/ExportLogic.js:95`); Đã xuất vào máy tính {}* (`qt/ExportLogic.js:95`); Đã xuất (`qt/ExportLogic.js:111`); Phần {}* (`qt/ExportLogic.js:169`); Đã xuất MP3* (`qt/ExportLogic.js:188`); Đã xuất M4B* (`qt/ExportLogic.js:190`); Đang tải nhạc nền {}/{} bài* (`qt/ExportLogic.js:199`); Đang kiểm đỉnh âm…* (`qt/ExportLogic.js:201`); Chương {}/{}* (`qt/ExportLogic.js:205`); Đang ghi chương {}/{}* (`qt/ExportLogic.js:207`); Đang trộn nhạc chương {}/{}* (`qt/ExportLogic.js:209`); Đang chờ mạng…* (`qt/ExportLogic.js:214`); Đang thêm chữ sáng… (`qt/ExportLogic.js:257`); Bỏ cách đọc “{} (`qt/ExportLogic.js:275`); Công cụ ghép âm thanh* (`qt/FfmpegNeeded.qml:24`); Cập nhật công cụ* (`qt/FfmpegNeeded.qml:29`); Thiếu công cụ ghép* (`qt/FfmpegNeeded.qml:29`); Dừng* (`qt/FfmpegNeeded.qml:49`); Tải công cụ ghép âm thanh* (`qt/FfmpegNeeded.qml:75`); Thử lại* (`qt/FfmpegNeeded.qml:96`); Tải công cụ* (`qt/FfmpegNeeded.qml:96`); Nghe thử* (`qt/PendingRow.qml:81`)
- chỉ web (6): Bỏ cách đọc “{}” (`55`); Thu lại (`197`); File .abook (`54`); Xuất “{}” (`356`); Cỡ ước tính: khoảng (`518`); Đang thêm chữ sáng… {}% (`42`)

### Studio máy khác

- chỉ Qt (1): Studio* (`qt/StudioScreen.qml:203`)
- chỉ web (0): (không có)

### Thanh tiêu đề

- chỉ Qt (2): ABook vẫn chạy ở khay (`qt/Main.qml:27`); Chưa tải được bản mới* (`qt/Main.qml:260`)
- chỉ web (3): Mở rộng (Ctrl+B) (`257`); Thu gọn (Ctrl+B) (`257`); Điều hướng (`274`)

### Chung

- chỉ Qt (2): Chưa làm được lúc này. (`qt/Api.qml:46`); Quay lại* (`qt/ScreenHeader.qml:12`)
- chỉ web (4): Đang tải điều hướng (`598`); Thông báo (Alt+T) (`714`); Xem các tab trước (`516`); Xem các tab sau (`521`)

File QML chưa xếp màn (thêm vào SCREENS): `desktop_qt/qml/BookLogic.js`, `desktop_qt/qml/CastLogic.js`, `desktop_qt/qml/FindInBook.qml`, `desktop_qt/qml/FindLogic.js`, `desktop_qt/qml/MusicCredit.qml`, `desktop_qt/qml/MusicPopover.qml`, `desktop_qt/qml/PeerStudio.js`, `desktop_qt/qml/PlayerConsent.qml`, `desktop_qt/qml/ProjectSteps.qml`, `desktop_qt/qml/StudioChapterHead.qml`, `desktop_qt/qml/StudioMusic.qml`, `desktop_qt/qml/StudioMusicLogic.js`, `desktop_qt/qml/StudioMusicMoods.qml`, `desktop_qt/qml/StudioMusicScene.qml`, `desktop_qt/qml/StudioMusicSwap.qml`, `desktop_qt/qml/StudioMusicTrackRow.qml`, `desktop_qt/qml/StudioMyMusic.qml`.

## d. Bo góc QML không theo token

Hợp lệ: `Theme.radiusControl / radiusCover / radiusSheet` (DESIGN.md 5.5, `desktop_qt/tools/gen_theme.py`), `0`, tròn (`width / 2`, `height / 2`), lấy lại bo khung chứa (`parent.radius`), vòng đồng tâm ngoài (`Theme.radiusCover + 8` của bóng, vòng tiêu điểm). Còn lại (0):

| nơi | radius |
|---|---|
| (không có) | |

## e. Dấu thanh kiểu mới và dấu ba chấm cuối nhãn

**Dấu thanh kiểu mới (`òa óa úy`)** trong chữ Qt (0); web và native đa số viết kiểu cũ (`oà oá uý`, UI_PARITY.md d2):

- (không có)

**Nhãn kết thúc bằng `…` / `...`** (82): DESIGN.md chỉ cho `…` ở chữ đang chờ ("Đang mở…"), không cho nhãn nút.

- Bỏ mọi thay đổi… (`qt/EditBook.qml:338`) - web: `Bỏ mọi thay đổi`
- Chuyển sang cuốn khác… (`qt/RecordLogic.js:39`) - web: `Chuyển sang cuốn khác`
- Chưa tải lại được sách: {} Đang thử lại… (`qt/StudioLogic.js:565`) - web: `Chưa tải lại được sách: {} Đang thử lại`
- Chọn cuốn… (`qt/RecordDialogs.qml:117`) - web: `Chọn cuốn`
- Chọn giọng khác… (`qt/WorkCard.qml:229`) - web: `Chọn giọng khác`
- Chọn thư mục… (`qt/EditBookSaveAs.qml:80`) - web: `Chọn thư mục`
- Chọn ảnh bìa… (`qt/EditBook.qml:238`) - web: `Chọn ảnh bìa`
- Chữ hay câu cần tìm… (`qt/FindInBook.qml:119`) - web: `Chữ hay câu cần tìm`
- Dừng… (`qt/StudioLogic.js:446`) - web: `Dừng`
- Giữ {} thẻ… (`qt/WorkBulkKeep.qml:26`) - web: (không có)
- Gộp vào người khác… (`qt/CastMenu.qml:28`) - web: `Gộp vào người khác`
- Gộp vào… (`qt/PrecastReview.qml:423`) - web: `Gộp vào`
- Khôi phục bản sao… (`qt/StudioLogic.js:475`) - web: `Khôi phục bản sao`
- Làm tiếp cuốn này… (`qt/StudioLogic.js:465`) - web: `Làm tiếp cuốn này`
- Lưu thành mẫu… (`qt/NewTemplateBar.qml:79`) - web: `Lưu thành mẫu`
- Lưu thành… (`qt/EditBookItems.qml:80`) - web: `Lưu thành`
- Lưu thành… (`qt/EditBookSaveAs.qml:16`) - web: `Lưu thành`
- Mạng chập chờn - đang thử lại… (`qt/EditBookLogic.js:87`) - web: (không có)
- Mạng chập chờn - đang thử lại… (`qt/MyMusicText.js:10`) - web: (không có)
- Mạng chập chờn - đang thử lại… (`qt/VoiceLogic.js:14`) - web: (không có)
- Mất kết nối tới ABook, đang thử lại… (`qt/StudioLogic.js:565`) - web: `Mất kết nối tới ABook, đang thử lại`
- Mọi cách đọc tên… (`qt/WorkPronunciation.qml:75`) - web: `Mọi cách đọc tên`
- Mở dự án có sẵn… (`qt/ProjectsScreen.qml:256`) - web: (không có)
- Người khác… (`qt/WorkSpeaker.qml:123`) - web: `Người khác`
- Người kể khác… (`qt/WorkNarrator.qml:65`) - web: `Người kể khác`
- Thu lại cả chương… (`qt/ProjectScreen.qml:243`) - web: `Thu lại cả chương`
- Thêm giọng… (`qt/NowPlaying.qml:536`) - web: `Thêm giọng`
- Thêm giọng… (`qt/PlayerVoicePopover.qml:30`) - web: `Thêm giọng`
- Tìm bìa… (`qt/EditBook.qml:247`) - web: `Tìm bìa`
- Tìm chữ trong chương… (`qt/ScriptTab.qml:718`) - web: `Tìm chữ trong chương`
- Tìm người khác trong truyện… (`qt/ScriptSpeakerMenu.qml:29`) - web: `Tìm người khác trong truyện`
- Tìm người khác… (`qt/WorkSpeaker.qml:134`) - web: `Tìm người khác`
- Tìm người trong truyện… (`qt/CastMerge.qml:50`) - web: `Tìm người trong truyện`
- Tìm người trong truyện… (`qt/CastMerge.qml:51`) - web: `Tìm người trong truyện`
- Tìm tên… (`qt/SharedReadingsSettings.qml:60`) - web: `Tìm tên`
- Vẫn tiếp tục… (`qt/StudioLogic.js:445`) - web: `Vẫn tiếp tục`
- Xoá dự án… (`qt/StudioLogic.js:469`) - web: `Xoá dự án`
- Xoá hồ sơ này… (`qt/RecordLogic.js:40`) - web: `Xoá hồ sơ này`
- Xoá hồ sơ… (`qt/RecordLogic.js:27`) - web: `Xoá hồ sơ`
- Xuất… (`qt/StudioLogic.js:450`) - web: `Xuất`
- {} ({}/{} chương)… (`qt/ExportLogic.js:57`) - web: (không có)
- Đang chuẩn bị giọng đọc… (`qt/PlayButton.qml:13`) - web: `Đang chuẩn bị giọng đọc`
- Đang chuẩn bị giọng đọc… (`qt/PlayerSubtitle.qml:17`) - web: `Đang chuẩn bị giọng đọc`
- Đang chờ mạng… (`qt/ExportLogic.js:214`) - web: `Đang chờ mạng…`
- Đang dừng… (`qt/NewChapters.qml:104`) - web: `Đang dừng`, `Đang dừng…`
- Đang dừng… (`qt/NewDrop.qml:128`) - web: `Đang dừng`, `Đang dừng…`
- Đang dừng… (`qt/StudioLogic.js:332`) - web: `Đang dừng`, `Đang dừng…`
- Đang gỡ… (`qt/StudioSettings.qml:123`) - web: `Đang gỡ`
- Đang huỷ… (`qt/ExportLogic.js:344`) - web: `Đang huỷ…`
- Đang kiểm tra… (`qt/AdvancedUpdate.qml:116`) - web: `Đang kiểm tra`, `đang kiểm tra`
- Đang kiểm đỉnh âm… (`qt/ExportLogic.js:201`) - web: `Đang kiểm đỉnh âm`, `Đang kiểm đỉnh âm…`
- Đang làm file M4B… (`qt/ExportLogic.js:190`) - web: `Đang làm file M4B…`
- Đang làm file M4B… (`qt/ExportLogic.js:20`) - web: `Đang làm file M4B…`
- Đang mở thư viện… (`qt/RecordDialogs.qml:97`) - web: `Đang mở thư viện`
- Đang mở văn bản chương… (`qt/ReadAlongView.qml:330`) - web: (không có)
- Đang mở… (`qt/ConnectionChip.qml:54`) - web: `Đang mở`
- Đang mở… (`qt/LibraryScreen.qml:434`) - web: `Đang mở`
- Đang thêm chữ sáng… (`qt/ExportLogic.js:257`) - web: (không có)
- Đang thử giọng vừa tải trên máy này (vài giây)… (`qt/VoiceLogic.js:242`) - web: `Đang thử giọng vừa tải trên máy này (và…`
- Đang tìm… (`qt/FindLogic.js:131`) - web: `Đang tìm`
- Đang tải bản mới… (`qt/AdvancedUpdate.qml:94`) - web: `Đang tải bản mới`
- Đang tải chương… (`qt/ChapterReader.qml:86`) - web: (không có)
- Đang tải nhạc nền ({}/{})… (`qt/ExportLogic.js:343`) - web: `Đang tải nhạc nền ({}/{})…`
- Đang tải âm thanh… (`qt/PlayButton.qml:13`) - web: `Đang tải âm thanh`
- Đang tải… (`qt/ReviewLogic.js:59`) - web: `Đang tải`, `đang tải`
- Đang tải… (`qt/WorkCard.qml:351`) - web: `Đang tải`, `đang tải`
- Đang xem cuốn nào còn dùng giọng này… (`qt/VoiceModule.qml:401`) - web: `Đang xem cuốn nào còn dùng giọng này`
- Đang xem các thay đổi… (`qt/ApplyChanges.qml:69`) - web: `Đang xem các thay đổi`
- Đang xuất MP3… (`qt/ExportLogic.js:188`) - web: `Đang xuất MP3`, `Đang xuất MP3…`
- Đang xuất MP3… (`qt/ExportLogic.js:18`) - web: `Đang xuất MP3`, `Đang xuất MP3…`
- Đang đo lại tốc độ trên máy này (vài giây)… (`qt/VoiceLogic.js:242`) - web: `Đang đo lại tốc độ trên máy này (vài gi…`
- Đang đóng gói dự án… (`qt/ExportLogic.js:21`) - web: `Đang đóng gói dự án…`
- Đang đóng gói sách… (`qt/ExportLogic.js:19`) - web: `Đang đóng gói sách…`
- Đang đọc các chương… (`qt/NewDrop.qml:81`) - web: `Đang đọc các chương`
- Đang đọc nguồn… (`qt/NewProjectLogic.js:47`) - web: (không có)
- Đang đọc… (`qt/AddBook.qml:548`) - web: `Đang đọc`, `đang đọc`
- Đổi tên chương… (`qt/BookPage.qml:283`) - web: `Đổi tên chương`
- Đổi tên hồ sơ này… (`qt/RecordLogic.js:38`) - web: (không có)
- Đổi tên hồ sơ… (`qt/RecordLogic.js:26`) - web: `Đổi tên hồ sơ`
- Đổi tên… (`qt/StudioLogic.js:462`) - web: `Đổi tên`
- Đổi ảnh bìa… (`qt/EditBook.qml:238`) - web: `Đổi ảnh bìa`
- đang ước tính thời gian… (`qt/StudioLogic.js:379`) - web: `đang ước tính thời gian`

## f. Phím tắt trong chú thích

Chú thích Qt ghi phím tắt sau nhãn; web ghép bằng `withShortcut(nhãn, phím)`. Phím khác nhau là khác HÀNH VI (phím thật trong `Main.qml` / `player.tsx`), không chỉ khác chữ.

| nhãn | Qt | web | nơi |
|---|---|---|---|
| Phát | `Space` | (không ghi) | `qt/PlayButton.qml:13` |
| Tạm dừng | `Space` | (không ghi) | `qt/PlayButton.qml:13` |
| {} | `Esc` | (không ghi) | `qt/ScreenHeader.qml:24` |
| Thu lại câu này | `R` | (không ghi) | `qt/ScriptRow.qml:290` |
| Mở rộng | `Ctrl+B` | (không ghi) | `qt/Sidebar.qml:89` |
| Thu gọn | `Ctrl+B` | (không ghi) | `qt/Sidebar.qml:89` |

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
