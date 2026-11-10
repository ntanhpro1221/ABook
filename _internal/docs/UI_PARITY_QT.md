# Lệch chữ, icon và bo góc giữa web máy tính và bản Qt

Nguồn chữ hiện tại là `ui_strings/vi.json` (Kotlin/XML/TS/Qt JS/C++ sinh từ cùng kho).
Token thực thi ở `ui_design/tokens.json`, kiểm với DESIGN.md. Cổng build chung là `scripts/prepare_ui.py`.
Các gợi ý gần chữ và icon còn lại phải có giải thích exact trong `qt_wording_review.json` / `qt_icon_review.json`; gợi ý mới chưa duyệt làm build đỏ.

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Cùng nguồn chung như `docs/UI_PARITY.md` (web <-> điện thoại native): bo góc `Theme.qml` sinh bởi `desktop_qt/tools/gen_theme.py` từ DESIGN.md 5.5,
icon `LucidePaths.js` sinh bởi `scripts/gen_lucide_icons.py --qml`. Bảng dưới do `scripts/ui_parity_qt.py` sinh (`--check` báo lệch,
`tests/test_ui_parity_qt.py` chạy `--check`). Bộ đọc là heuristic trên mã nguồn: chữ dựng từ dữ liệu (tên chương, thời gian) không tính.

<!-- ui_parity_qt:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity_qt.py - không sửa tay, chạy lại script) -->

Quét: web máy tính 5799 chữ (2792 khác nhau), 324 cặp nhãn-icon; Qt 3452 chữ (2586 khác nhau), 283 cặp nhãn-icon (icon dùng ở 392 chỗ). Khoá so lỏng như UI_PARITY.md (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối); phím tắt trong chú thích Qt (`Thu nhỏ (Esc)`) tách khỏi nhãn.

## a. Cùng việc, khác chữ

Nhãn ngắn Qt không có nguyên văn (khoá lỏng) ở web máy tính mà giống một nhãn web CÙNG MÀN chưa có ở Qt. 41 cặp; mỗi nhãn Qt lấy một nhãn web giống nhất. Giống không có nghĩa là cùng việc: người sửa xem mã hai bên trước khi đổi.

Mỗi cặp còn lại phải có giải thích trong ui_strings/qt_wording_review.json; cặp mới chưa duyệt làm --check đỏ.

| màn | Qt | web | giống | nơi | giải thích |
|---|---|---|---|---|---|
| Cài đặt | Chưa lưu được mẫu{} | Chưa lưu được mẫu | 1.00 | `qt/BookTemplates.qml:28` ~ `desktop/BookTemplates.tsx:24` | Same error sentence; Qt includes the error value in one expression, web renders the detail beside the heading. |
| Cài đặt | Dùng Bluetooth cho | Dùng Bluetooth cho {} | 1.00 | `qt/OtherComputersBluetooth.qml:28` ~ `desktop/OtherComputers.tsx:345` | Same Bluetooth action; Qt renders the computer name in a separate ShortName item. |
| Cài đặt | Hết hạn sau {}:{} | Hết hạn sau | 1.00 | `qt/PhoneSyncPairing.qml:82` ~ `desktop/PhoneSync.tsx:167` | Same pairing-code expiry; Qt formats minutes and seconds in the expression, web places the clock after the label. |
| Cài đặt | Khoá | Khoá {} | 1.00 | `qt/ProviderKey.qml:139` ~ `listen/VoiceSettings.tsx:193` | The shared field label is Khoá. Web accessibility text additionally names the provider. |
| Cài đặt | Mã ghép nối: | Mã ghép nối: {} | 1.00 | `qt/PhoneSyncPairing.qml:73` ~ `desktop/PhoneSync.tsx:160` | Same pairing-code label; Qt places the six code digits in a separate text item. |
| Cài đặt | Mở Studio của | Mở Studio của {} | 1.00 | `qt/OtherComputersRow.qml:113` ~ `desktop/OtherComputers.tsx:209` | Same open-Studio action; Qt renders the computer name as another item in the row. |
| Cài đặt | Điều khiển sản xuất từ | Điều khiển sản xuất từ {} | 1.00 | `qt/PhoneSyncDevice.qml:88` ~ `desktop/PhoneSync.tsx:345` | Same production-control heading; Qt places the device name in a separate item. |
| Cài đặt | Địa chỉ: {} | Địa chỉ: | 1.00 | `qt/PhoneSyncPairing.qml:59` ~ `desktop/PhoneSync.tsx:153` | Same address label; web renders its address value as a JSX child. |
| Studio dự án | Chưa khởi động được: {} | Chưa khởi động được: | 1.00 | `qt/ProjectScreen.qml:475` ~ `studio/ProjectScreen.tsx:197` | Same start error; web renders the error after the heading as a JSX child. |
| Studio dự án | Chưa dừng được | Chưa tải được | 0.74 | `qt/StudioStore.qml:160` ~ `studio/ProjectScreen.tsx:1387` | Different operations: Qt reports a failed stop request, the matched web text reports a failed load. Do not rename a stop failure to a load failure. |
| Studio dự án | Đang làm tiếp | Làm tiếp từ chỗ ấy | 0.52 | `qt/StudioLogic.js:228` ~ `studio/ProjectScreen.tsx:373` | Different roles: Qt status after resuming versus the web resume action. Both phrases already exist in the shared catalog. |
| Studio kịch bản | Gán cho {} | Gán cho | 1.00 | `qt/ScriptRow.qml:245` ~ `studio/ScriptTab.tsx:1118` | Same attribution action; web renders the selected speaker after the label. |
| Studio kịch bản | Đang chọn {} câu | Đang chọn | 0.82 | `qt/ScriptTab.qml:466` ~ `studio/ScriptTab.tsx:1406` | Same selection count; web uses separate TickingValue and unit children. |
| Studio tạo sách | Tạo trên {} | Tạo trên | 1.00 | `qt/StudioSetupNotice.qml:98` ~ `studio/StudioSetup.tsx:104` | Same remote-create action; web renders the computer name as another child. |
| Studio tạo sách | Bản thử nghiệm | Bản thử nghiệm{} | 1.00 | `qt/NewProjectLogic.js:371` ~ `studio/AnalysisModelPicker.tsx:53` | Same model qualifier; web appends an optional model-description value. |
| Studio tạo sách | Có file không gửi{} | Có file không gửi | 1.00 | `qt/NewProjectStore.qml:270` ~ `studio/NewProjectScreen.tsx:305` | Same upload warning; Qt appends a detail list in the expression, web uses a separate child. |
| Studio tạo sách | Không gửi hết các chương{} {} | Không gửi hết các chương | 1.00 | `qt/NewProjectStore.qml:313` ~ `studio/NewProjectScreen.tsx:312` | Same upload warning; the two Qt slots are file count and detail, rendered separately on web. |
| Studio tạo sách | Máy thấy {} | Máy thấy | 1.00 | `qt/NewVolumes.qml:58` ~ `studio/VolumeSplit.tsx:101` | Same volume-detection sentence; web renders the count/source after the label. |
| Studio tạo sách | Studio chưa xong{} | Studio chưa xong | 1.00 | `qt/StudioSetupCard.qml:28` ~ `studio/StudioSetup.tsx:162` | Same setup status; Qt appends optional details in the expression. |
| Studio tạo sách | Tách theo {} | Tách theo | 1.00 | `qt/NewHints.qml:88` ~ `studio/NewProjectScreen.tsx:863` | Same chapter-split description; web renders the chosen rule after the label. |
| Studio tạo sách | Đã có mẫu “{}” | Đã có mẫu “ | 1.00 | `qt/TemplateLogic.js:52` ~ `studio/TemplateBar.tsx:171` | Same duplicate-template error; web renders the user-entered template name between JSX quote fragments. |
| Studio tạo sách | Máy này {}. | Máy thấy | 0.80 | `qt/StudioSetupLogic.js:17` ~ `studio/VolumeSplit.tsx:101` | Different subjects: Qt describes machine setup/capability, the matched web text describes detected book volumes. |
| Studio việc duyệt | Bỏ qua mọi việc từ | Bỏ qua mọi việc từ {}? | 1.00 | `qt/PhoneEdits.qml:154` ~ `studio/PhoneEdits.tsx:246` | Same destructive-confirmation question; Qt places the phone name and question mark in separate children. |
| Studio việc duyệt | Dùng “{}” | Dùng “ | 1.00 | `qt/ReadingProblem.qml:40` ~ `studio/ReadingProblem.tsx:27` | Same use-reading action; web renders the reading value between separate JSX quote fragments. |
| Studio việc duyệt | Máy nghe ra: “{}” | Máy nghe ra: “ | 1.00 | `qt/ReviewLogic.js:42` ~ `studio/ReviewQueue.tsx:224` | Same ASR transcript caption; web renders the transcript as another child. |
| Studio việc duyệt | Mọi việc đã có quyết định | Mọi việc đã có quyết định{}. | 1.00 | `qt/WorkLogic.js:276` ~ `studio/WorkInbox.tsx:1290` | Same completed-review state; web appends an optional pending-change count. |
| Studio việc duyệt | Sẽ đọc là “{}” | Sẽ đọc là “ | 1.00 | `qt/ReviewLogic.js:47` ~ `studio/ReviewQueue.tsx:233` | Same proposed-reading caption; web renders the reading as another child. |
| Studio việc duyệt | Đã dùng | Dùng “ | 1.00 | `qt/WorkStore.qml:324` ~ `studio/ReadingProblem.tsx:27` | Different states: Qt past-tense confirmation after saving, the matched web phrase is the action to use a proposed reading. |
| Studio việc duyệt | Đúng rồi, giữ “{}” | Đúng rồi, giữ “ | 1.00 | `qt/WorkPronunciation.qml:35` ~ `studio/WorkInbox.tsx:379` | Same keep-reading action; web renders the reading between separate JSX quote fragments. |
| Studio việc duyệt | Đoạn này do | Đoạn này do {} kể | 0.88 | `qt/WorkLogic.js:49` ~ `studio/workText.ts:23` | Same narrator-result sentence; Qt composes prefix, narrator and suffix from separate catalog keys. |
| Studio việc duyệt | Tải tiếp · còn | Tải tiếp · còn {} câu | 0.86 | `qt/ReviewLogic.js:60` ~ `studio/ReviewQueue.tsx:505` | Same review pagination; Qt renders remaining count and unit in separate items. |
| Studio việc duyệt | Nghe liền {} câu | Nghe liền | 0.82 | `qt/ReviewQueue.qml:254` ~ `studio/ReviewQueue.tsx:459` | Same continuous-listening action; web renders the count in a separate child. |
| Studio việc duyệt | Xem {} câu | Sửa {} câu | 0.57 | `qt/WorkSpeaker.qml:155` ~ `studio/reviewText.ts:21` | Different actions: Qt opens read-only context, the matched web label opens an editor for repeated lines. |
| Studio xuất và áp dụng | Bỏ cách đọc “{} | Bỏ cách đọc “{}” | 1.00 | `qt/ExportLogic.js:276` ~ `studio/ApplyChanges.tsx:56` | Same remove-reading action; Qt closes the quotation mark in a separate literal. |
| Studio xuất và áp dụng | Cỡ ước tính: khoảng {} | Cỡ ước tính: khoảng | 1.00 | `qt/ExportBook.qml:222` ~ `studio/ExportBook.tsx:509` | Same export-size estimate; web renders the size in a separate child. |
| Studio xuất và áp dụng | Xuất “ | Xuất “{}” | 1.00 | `qt/ExportBook.qml:51` ~ `studio/ExportBook.tsx:380` | Same export heading; Qt renders the title and closing quote in separate items. |
| Studio xuất và áp dụng | Đang thêm chữ sáng… | Đang thêm chữ sáng… {}% | 1.00 | `qt/ExportLogic.js:258` ~ `studio/WordTimings.tsx:43` | Same word-timing progress; Qt places the percentage in its separate steady clock value. |
| Studio xuất và áp dụng | Đã xuất | Xuất “{}” | 0.73 | `qt/ExportLogic.js:112` ~ `studio/ExportBook.tsx:380` | Different states: Qt completed-export confirmation, matched web text is an export-dialog heading. |
| Thanh phát | Nghe bằng giọng đọc. | Nghe bằng giọng đọc.{} | 1.00 | `qt/PlayerLabels.js:10` ~ `listen/labels.ts:143` | Same sentence; web appends an optional platform-specific pointer/editing hint. |
| Trang sách | Lần nghe | Lần nghe {} | 1.00 | `qt/RecordLogic.js:10` ~ `listen/BookScreen.tsx:699` | Same listening-record name prefix; Qt renders the record number separately. |
| Trang sách | Hồ sơ nghe: {} | Đã nghe {} | 0.59 | `qt/RecordChip.qml:14` ~ `listen/BookScreen.tsx:1163` | Different data: Qt accessibility name for a listening profile, the matched web label is listening progress. |

## b. Cùng nhãn khác icon, cùng icon khác nhãn

**Cùng nhãn, khác icon** (4 nhãn Qt có icon mà icon ấy không đi với nhãn này ở bất cứ đâu trên web máy tính):

| nhãn | web | Qt | nơi | giải thích |
|---|---|---|---|---|
| Bắt đầu | headphones | wand-sparkles | `qt/NewProjectScreen.qml:176` ~ `desktop/AudiobookDialog.tsx:210` | Different operations: Qt starts a Studio production job (wand-sparkles); the matched web dialog starts a read-aloud export (headphones). |
| Chi tiết | info | chevron-right | `qt/MyMusicDetails.qml:29` (+1) ~ `studio/ProjectScreen.tsx:762` | Different controls: Qt rotates a disclosure chevron to expand the music details; the matched web item opens project information. |
| Quay lại | chevron-left | arrow-left | `qt/ScreenHeader.qml:14` ~ `listen/LineWishes.tsx:222` (+2) | Different navigation depth: the web chevron returns one step inside a sentence editor; the Qt arrow returns to the previous screen. |
| Tạm dừng {} | check, circle-dashed, play | pause | `qt/BookCell.qml:81` ~ `listen/BookScreen.tsx:173` (+2) | Scanner pairing ambiguity: the web book row has status check/circle icons beside its transport action. Its actual pause action and the Qt book cell use pause. |

**Cùng icon, khác nhãn** (63 cặp Qt; web cùng màn dùng cùng icon với nhãn khác):

| màn | icon | Qt | web cùng màn | nơi |
|---|---|---|---|---|
| Thêm sách | copy | Thêm bản riêng | Thêm bản riêng / Vẫn thêm bản mới | `qt/AddBook.qml:458` |
| Thêm sách | copy | Vẫn thêm bản mới | Thêm bản riêng / Vẫn thêm bản mới | `qt/AddBook.qml:458` |
| Thêm sách | file-text | Chọn file sách | Đang đọc / Chọn file sách | `qt/AddBook.qml:551` |
| Thêm sách | file-text | Đang đọc… | Đang đọc / Chọn file sách | `qt/AddBook.qml:551` |
| Cài đặt | download | Cập nhật ABook | Cài Studio, Cài tiếp, Có ABook {} | `qt/AdvancedUpdate.qml:96` |
| Cài đặt | download | Đang tải bản mới… | Cài Studio, Cài tiếp, Có ABook {} | `qt/AdvancedUpdate.qml:96` |
| Thư viện | play | Nghe ngay {} | Đọc {} | `qt/BookCell.qml:81` |
| Thư viện | play | Nghe {} | Đọc {} | `qt/BookCell.qml:81` |
| Thư viện | pause | Tạm dừng {} | Đọc {} | `qt/BookCell.qml:81` |
| Thư viện | laptop | Có sách trên máy khác | tập, {}, đã tải về máy này | `qt/BookCell.qml:131` |
| Thư viện | laptop | Trên {} | tập, {}, đã tải về máy này | `qt/BookCell.qml:131` |
| Trang sách | check-check | Chưa nghe xong | Chưa nghe / Đã nghe xong, Chưa nghe xong / Đã nghe xong | `qt/BookPage.qml:151` |
| Trang sách | check-check | Đã nghe xong | Chưa nghe / Đã nghe xong, Chưa nghe xong / Đã nghe xong | `qt/BookPage.qml:151` |
| Trang sách | circle-dashed | Chưa nghe | Chưa nghe / Đã nghe xong, Tạm dừng {} | `qt/BookPage.qml:281` |
| Trang sách | check-check | Đã nghe xong | Chưa nghe / Đã nghe xong, Chưa nghe xong / Đã nghe xong | `qt/BookPage.qml:281` |
| Trang sách | git-merge | Gộp | Gộp vào người khác | `qt/CastMerge.qml:163` |
| Đang nghe | play | Nghe từ đầu chương | Dừng / Thử, Nghe {} | `qt/ChapterList.qml:45` |
| Studio tạo sách | image-plus | Đặt bìa | Đổi ảnh bìa | `qt/CoverEditor.qml:133` |
| Studio tạo sách | image-plus | Đổi bìa | Đổi ảnh bìa | `qt/CoverEditor.qml:133` |
| Studio tạo sách | image-plus | Đặt ảnh bìa | Đổi ảnh bìa | `qt/CoverEditor.qml:142` |
| Studio tạo sách | trash | Bỏ ảnh bìa | Bỏ chương {}, Bỏ chỗ cắt trước {}, Bỏ ảnh bìa, dùng lại bìa vẽ từ tên sách | `qt/CoverEditor.qml:169` |
| Sửa sách | image-plus | Chọn ảnh bìa… | Đổi ảnh bìa / Chọn ảnh bìa | `qt/EditBook.qml:240` |
| Sửa sách | image-plus | Đổi ảnh bìa… | Đổi ảnh bìa / Chọn ảnh bìa | `qt/EditBook.qml:240` |
| Sửa sách | file-down | Lưu thành… | Lưu | `qt/EditBookItems.qml:82` |
| Sửa sách | trash | Xoá | Bỏ ảnh bìa | `qt/EditBookMyMusic.qml:289` |
| Sửa sách | trash | Xoá bài | Bỏ ảnh bìa | `qt/EditBookMyMusic.qml:303` |
| Sửa sách | trash | Bỏ cách đọc {} | Bỏ ảnh bìa | `qt/EditBookReadings.qml:121` |
| Thêm sách | book-plus | Thả để thêm sách | Thêm vào thư viện | `qt/ImportDrop.qml:49` |
| Thư viện | play | Nghe tiếp | Đọc {} | `qt/LibraryContinue.qml:46` |
| Thư viện | pause | Tạm dừng | Đọc {} | `qt/LibraryContinue.qml:46` |
| Thư viện | x | Đóng ô tìm | Xoá ô tìm | `qt/LibraryScreen.qml:184` |
| Thư viện | search | Chưa có cuốn nào nghe xong. | Thử tên sách hoặc tác giả khác., Tìm sách | `qt/LibraryScreen.qml:458` |
| Cài đặt | upload | Đang thêm {}/{} | Thêm nhạc của bạn | `qt/MyMusicSettings.qml:146` |
| Cài đặt | play | Nghe thử | Dừng / Nghe thử | `qt/MyMusicTrack.qml:82` |
| Studio tạo sách | layers | Phần | Chia thành nhiều phần, Chia thành {} phần / Chia thành mấy phần? | `qt/NewChapters.qml:205` |
| Studio tạo sách | layers | Chọn {} tập | Chia thành nhiều phần, Chia thành {} phần / Chia thành mấy phần? | `qt/NewDrop.qml:210` |
| Studio tạo sách | scissors | Tách thành {} chương | Tách thành chương | `qt/NewHints.qml:94` |
| Studio tạo sách | wand-sparkles | Bắt đầu | Bắt đầu / Tạo sách | `qt/NewProjectScreen.qml:176` |
| Đang nghe | moon | Hẹn giờ | {} trên {} | `qt/NowPlaying.qml:433` |
| Đang nghe | moon | Hết chương | {} trên {} | `qt/NowPlaying.qml:433` |
| Cài đặt | bluetooth | Dùng Bluetooth | Dùng Bluetooth cho {}, · bản thử | `qt/OtherComputersBluetooth.qml:23` |
| Cài đặt | refresh-cw | Làm mới | Hỏi lại, Hỏi lại thư viện | `qt/PhoneDiagnostics.qml:68` |
| Cài đặt | save | Lưu nhật ký | Gửi nhật ký | `qt/PhoneDiagnostics.qml:69` |
| Studio dự án | ellipsis | Tuỳ chọn dự án | Tuỳ chọn Studio, Tuỳ chọn dự án {}, Tuỳ chọn {} | `qt/ProjectScreen.qml:331` |
| Studio dự án | circle-alert | Chưa khởi động được: {} | Chưa mở được sách, Cuốn này đã bị xoá hoặc chuyển đi khỏi thư … | `qt/ProjectScreen.qml:471` |
| Studio việc duyệt | list-music | Nghe liền {} câu | Nghe liền câu | `qt/ReviewQueue.qml:253` |
| Studio việc duyệt | rotate-ccw | Cần thu lại | Cần thu lại / Thu lại câu này, Hoàn tác, Khôi phục tất cả | `qt/ReviewRow.qml:282` |
| Studio việc duyệt | rotate-ccw | Thu lại câu này | Cần thu lại / Thu lại câu này, Hoàn tác, Khôi phục tất cả | `qt/ReviewRow.qml:282` |
| Studio kịch bản | refresh-cw | Thu lại câu này | Thu lại câu: {}, Thu lại {} câu / Chưa có bản thu | `qt/ScriptRow.qml:297` |
| Studio kịch bản | refresh-cw | Chưa có bản thu | Thu lại câu: {}, Thu lại {} câu / Chưa có bản thu | `qt/ScriptTab.qml:484` |
| Studio kịch bản | refresh-cw | Thu lại {} câu | Thu lại câu: {}, Thu lại {} câu / Chưa có bản thu | `qt/ScriptTab.qml:484` |
| Studio kịch bản | check | Duyệt {} câu | Duyệt câu | `qt/ScriptTab.qml:586` |
| Cài đặt | trash | Gỡ Studio | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/StudioSettings.qml:123` |
| Cài đặt | trash | Xác nhận gỡ | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/StudioSettings.qml:123` |
| Cài đặt | trash | Đang gỡ… | Bỏ “{}” khỏi cách đọc chung, Xoá, Xoá bài | `qt/StudioSettings.qml:123` |
| Studio tạo sách | clapperboard | Tạo trên {} | Tạo trên | `qt/StudioSetupNotice.qml:99` |
| Studio việc duyệt | pause | Dừng | Dừng / Nghe thử | `qt/TryButton.qml:12` |
| Studio việc duyệt | volume-2 | Nghe thử | Dừng / Nghe thử | `qt/TryButton.qml:12` |
| Cài đặt | play | Thử giọng | Dừng / Nghe thử | `qt/VoiceRow.qml:106` |
| Studio việc duyệt | check | Giữ {} thẻ… | Giữ cả thẻ, Giữ thẻ, Giữ “{}” - không cần áp dụng. / Đã ghi “{}”… | `qt/WorkBulkKeep.qml:26` |
| Studio việc duyệt | user-plus | Người khác | Người kể khác, Đặt tên / Người khác | `qt/WorkSpeaker.qml:133` |
| Studio việc duyệt | user-plus | Đặt tên | Người kể khác, Đặt tên / Người khác | `qt/WorkSpeaker.qml:133` |
| Studio việc duyệt | search | Xem {} câu | Tìm người khác, Xem câu | `qt/WorkSpeaker.qml:154` |

Số cặp: web máy tính 282, Qt 246. Nhãn Qt có icon (192): `Bài nhạc`, `Bấm để cập nhật`, `Bấm để đổi tên chương`, `Bật tiếng`, `Bắt đầu`, `Bỏ chương này`, `Bỏ cách đọc {}`, `Bỏ ghép`, `Bỏ qua tất cả`, `Bỏ qua việc này`, `Bỏ ảnh bìa`, `Bỏ “{}” khỏi cách đọc chung`, `Chi tiết`, `Chia thành nhiều phần`, `Chưa có bản thu`, `Chưa có cuốn nào nghe xong.`, `Chưa khởi động được: {}`, `Chưa nghe`, `Chưa nghe xong`, `Chương`, `Chương sau`, `Chương sau chưa có audio`, `Chương trước`, `Chẩn đoán`, `Chọn`, `Chọn file`, `Chọn file sách`, `Chọn lại nhạc`, `Chọn thư mục`, `Chọn thư mục TXT`, `Chọn từng file`, `Chọn {} tập`, `Chọn ảnh bìa…`, `Cài Studio`, `Cài đặt`, `Có ABook`, `Có sách trên máy khác`, `Cần thu lại`, `Cập nhật ABook`, `Cửa sổ mini`, `Duyệt {} câu`, `Dùng Bluetooth`, `Dùng {} cách đọc chung`, `Dừng`, `Dừng nghe`, `Dừng nghe liền`, `Dừng nghe thử`, `Dự án mới`, `Ghim trên cùng`, `Ghép thiết bị mới`, `Giảm`, `Giọng {} đang không dùng được.`, `Giọng đọc`, `Giữ {} thẻ…`, `Gộp`, `Gộp vào người khác…`, `Gộp vào phần trước`, `Gỡ Studio`, `Gợi ý đọc`, `Gửi nhật ký`, `Hoàn tác`, `Huỷ tải`, `Hẹn giờ`, `Hết chương`, `Hỏi lại thư viện`, `Khôi phục tất cả`, `Khôi phục việc này`, `Không có mạng -`, `Khởi động lại`, `Kiểm tra`, `Làm mới`, `Lưu`, `Lưu nhật ký`, `Lưu thay đổi`, `Lưu thành…`, `Lưu thành mẫu…`, `Mở cuốn đó`, `Mở file sách`, `Mở Kịch bản`, `Mở màn hình đang nghe`, `Mở rộng`, `Mở Studio`, `Mở tab Nhạc nền`, `Mở thư mục`, `Mở thư mục nhật ký`, `Nghe liền {} câu`, `Nghe lại`, `Nghe ngay {}`, `Nghe thử`, `Nghe tiếp`, `Nghe từ đầu chương`, `Nghe {}`, `Người khác`, `Người kể khác…`, `Nhạc nền`, `Nhập nhạc`, `Nên dùng`, `Phát`, `Phím tắt`, `Phần`, `Quay lại`, `Studio`, `Sửa cách đọc {}`, `Sửa sách`, `Sửa thông tin`, `Thiết bị phát`, `Thu gọn`, `Thu lại câu này`, `Thu lại {} câu`, `Thu nhỏ`, `Thêm`, `Thêm bản riêng`, `Thêm cách đọc`, `Thêm file`, `Thêm giọng…`, `Thêm nhạc của bạn`, `Thêm sách`, `Thêm tuỳ chọn`, `Thêm tuỳ chọn cho {}`, `Thêm vào thư viện`, `Thư viện`, `Thả để thêm sách`, `Thử giọng`, `Thử lại`, `Trên {}`, `Tuỳ chọn dự án`, `Tuỳ chọn Studio`, `Tách thành {} chương`, `Tìm`, `Tìm bìa…`, `Tìm người khác…`, `Tìm sách`, `Tìm ảnh bìa trên mạng`, `Tăng`, `Tạm dừng`, `Tạm dừng {}`, `Tạo sách nói`, `Tạo trên {}`, `Tải thêm (3,2 GB)`, `Tắt tiếng`, `Tới câu đang nghe`, `Tự tìm`, `Vẫn cài`, `Vẫn thêm bản mới`, `Về chỗ vừa nghe`, `Về Cài đặt`, `Về màn trước`, `Về Studio`, `Về Thư viện`, `Xem tất cả`, `Xem {} câu`, `Xoá`, `Xoá bài`, `Xoá khoá`, `Xoá ô tìm`, `Xác nhận gỡ`, `Xếp theo`, `Áp dụng trước`, `Áp dụng tất cả`, `Áp dụng việc này`, `Âm thanh`, `Đang chuẩn bị giọng đọc…`, `Đang chọn lại`, `Đang gỡ…`, `Đang mở…`, `Đang thêm {}/{}`, `Đang tải bản mới…`, `Đang tải âm thanh…`, `Đang đọc…`, `Đang đọc không khí`, `Đang đổi`, `Đây là chương cuối`, `Đã nghe xong`, `Đóng`, `Đóng lời báo`, `Đóng trình phát`, `Đóng ô tìm`, `Đặt bìa`, `Đặt tên`, `Đặt ảnh bìa`, `Đọc chương này`, `Đọc lại ngữ cảnh`, `Đọc {}`, `Đổi bài`, `Đổi bìa`, `Đổi giọng người kể`, `Đổi giọng {}`, `Đổi giới tính`, `Đổi tên`, `Đổi tên chương…`, `Đổi ảnh bìa`, `Ổn`.

## c. Nhãn chỉ có một bên, theo màn

Nhãn ngắn (<= 6 chữ). **Chỉ Qt**: không có ở web cùng màn; `*` = web có ở màn khác. **Chỉ web**: nhãn web của màn không có ở đâu trong Qt - phần lớn là tính năng Qt chưa làm (bản thử), chỉ đếm và kể 15 đầu.

### Âm thanh

- chỉ Qt (1): Âm thanh* (`qt/AudioFxPanel.qml:11`)
- chỉ web (2): 1 kHz (`8`); 250 Hz (`8`)

### Khay và cửa sổ mini

- chỉ Qt (11): Ghim trên cùng (`qt/MiniPlayer.qml:54`); Mở rộng (`qt/MiniPlayer.qml:60`); Lùi {} giây* (`qt/MiniPlayer.qml:88`); Phát* (`qt/MiniPlayer.qml:89`); Tạm dừng* (`qt/MiniPlayer.qml:89`); Tới {} giây* (`qt/MiniPlayer.qml:90`); Chương sau* (`qt/TrayMenuModel.qml:13`); Chương trước* (`qt/TrayMenuModel.qml:13`); Cửa sổ mini (`qt/TrayMenuModel.qml:13`); Mở ABook (`qt/TrayMenuModel.qml:13`); Thoát ABook (`qt/TrayMenuModel.qml:13`)
- chỉ web (0): (không có)

### Thư viện

- chỉ Qt (8): Tạm dừng* (`qt/LibraryContinue.qml:44`); Mới thêm* (`qt/LibraryScreen.qml:48`); Tác giả* (`qt/LibraryScreen.qml:48`); Tên sách* (`qt/LibraryScreen.qml:48`); Đang mở ABook* (`qt/LibraryScreen.qml:367`); Chưa mở được ABook (`qt/LibraryScreen.qml:413`); Chưa tải được thư viện (`qt/LibraryScreen.qml:413`); Thử lại* (`qt/LibraryScreen.qml:430`)
- chỉ web (8): Đang tạm dừng {} (`330`); Đang làm {} (`331`); Đang tạm dừng{} (`335`); Chưa có chương nghe được{} (`337`); Đang làm · {} (`337`); Thư viện chưa có sách nào. (`456`); Chưa có sách trên máy (`561`); Chữ bìa trên hoạ tiết sóng (`84`)

### Thanh phát

- chỉ Qt (11): Không có mạng - (`qt/PlayerAlert.qml:10`); Giọng {} đang không dùng được.* (`qt/PlayerAlert.qml:25`); Cửa sổ mini (`qt/PlayerBar.qml:121`); Chỉnh* (`qt/PlayerBar.qml:149`); Âm thanh* (`qt/PlayerBar.qml:149`); Hẹn giờ* (`qt/PlayerBar.qml:150`); Nhạc nền* (`qt/PlayerBar.qml:153`); Giọng đọc* (`qt/PlayerBar.qml:154`); Hẹn lại {} phút* (`qt/PlayerFade.qml:16`); Nghe bằng giọng đọc. (`qt/PlayerLabels.js:10`); Thêm giọng…* (`qt/PlayerVoicePopover.qml:31`)
- chỉ web (8): Shift+← (`272`); Sắp tắt · (`1265`); Chưa nghe · {} chương (`63`); Nghe tiếp · {} (`82`); Shift+→ (`100`); Chưa có audio (`110`); Chạm (`121`); Nghe bằng giọng đọc.{} (`143`)

### Đang nghe

- chỉ Qt (21): Tạm dừng {}* (`qt/ChapterList.qml:27`); Đọc {} (chưa có audio)* (`qt/ChapterList.qml:27`); Đọc chương này* (`qt/ChapterList.qml:46`); Đọc* (`qt/ChapterReader.qml:15`); Chưa có chương để đọc. (`qt/ChapterReader.qml:34`); Đang tải chương… (`qt/ChapterReader.qml:87`); Đã nghe* (`qt/ChapterRow.qml:51`); Tuỳ chọn {}* (`qt/ChapterRow.qml:103`); Thêm tuỳ chọn* (`qt/NowPlaying.qml:240`); Giọng {}* (`qt/NowPlaying.qml:296`); Thử lại* (`qt/NowPlaying.qml:339`); Danh sách chương* (`qt/NowPlaying.qml:456`); Nhạc nền* (`qt/NowPlaying.qml:467`); Chỉnh* (`qt/NowPlaying.qml:605`); Âm thanh* (`qt/NowPlaying.qml:605`); Cửa sổ mini (`qt/NowPlaying.qml:613`); Gợi ý cho phần đọc* (`qt/ReadingSuggestions.qml:9`); Bỏ dòng (`qt/ReadingSuggestions.qml:57`); Đóng* (`qt/ReadingSuggestions.qml:80`); Giảm* (`qt/SleepPopover.qml:89`); Tăng* (`qt/SleepPopover.qml:103`)
- chỉ web (17): Shift+← (`272`); Đã chọn tốc độ đọc {} (`473`); Phím (`477`); Đã chọn giọng {} (`739`); Hẹn giờ đã tắt tiếng lúc (`960`); Bật lại (`968`); Tiếng nhỏ dần (`974`); Hẹn giờ ngủ trên {} (`1048`); Về chế độ nghe (`2089`); Chưa nghe · {} chương (`63`); Nghe tiếp · {} (`82`); Shift+→ (`100`); Chưa có audio (`110`); Chạm (`121`); Nghe bằng giọng đọc.{} (`143`); ...

### Đọc theo

- chỉ Qt (1): Đang mở văn bản chương… (`qt/ReadAlongView.qml:361`)
- chỉ web (3): Đang tải chữ (`1708`); Nghe từ “{}” (`56`); Shift F10: sửa cách đọc. (`338`)

### Trang sách

- chỉ Qt (62): Thêm* (`qt/BookPage.qml:497`); Thêm việc với sách (`qt/BookPage.qml:498`); Chưa tải được giọng* (`qt/CastEngine.qml:72`); Tải giọng* (`qt/CastEngine.qml:80`); Chưa huỷ được việc tải giọng* (`qt/CastEngine.qml:115`); Giới tính của {}* (`qt/CastGender.qml:17`); Hiện đang là nhân vật {}.* (`qt/CastGender.qml:18`); Chưa đổi được giới tính* (`qt/CastGender.qml:26`); Giới tính* (`qt/CastGender.qml:48`); Nữ* (`qt/CastGender.qml:50`); Nếu giọng* (`qt/CastGender.qml:67`); Ghi lại* (`qt/CastGender.qml:83`); Thôi* (`qt/CastGender.qml:83`); Đang tải nhân vật (`qt/CastList.qml:85`); Gộp nhân vật* (`qt/CastMerge.qml:18`); Chưa gộp được* (`qt/CastMerge.qml:29`); Đã ghi:* (`qt/CastMerge.qml:29`); Tìm người trong truyện…* (`qt/CastMerge.qml:51`); Gộp vào ai* (`qt/CastMerge.qml:68`); Không có ai khớp “{}”. (`qt/CastMerge.qml:137`); Gộp* (`qt/CastMerge.qml:159`); Chưa hoàn tác được* (`qt/CastModal.qml:24`); Hoàn tác* (`qt/CastModal.qml:24`); Đã hoàn tác (`qt/CastModal.qml:24`); Đã hoàn tác. {} (`qt/CastModal.qml:24`); Đổi tên {}* (`qt/CastRename.qml:14`); Chưa đổi được tên* (`qt/CastRename.qml:26`); Đã trở về tên gốc: {}* (`qt/CastRename.qml:26`); Đã đổi tên thành {}* (`qt/CastRename.qml:26`); Tên mới của {}* (`qt/CastRename.qml:48`); Tên gốc:* (`qt/CastRename.qml:58`); Về tên gốc* (`qt/CastRename.qml:64`); Chưa bỏ gộp được* (`qt/CastUnmerge.qml:13`); Đã bỏ gộp {}* (`qt/CastUnmerge.qml:13`); Chưa đổi được giọng* (`qt/CastVoice.qml:70`); Giọng (`qt/CastVoice.qml:70`); Chưa bỏ được lựa chọn* (`qt/CastVoice.qml:89`); Đã bỏ lựa chọn giọng* (`qt/CastVoice.qml:89`); Đã bỏ lựa chọn {}* (`qt/CastVoice.qml:89`); Đang tải giọng đọc* (`qt/CastVoice.qml:117`); Chờ áp dụng: đổi sang* (`qt/CastVoice.qml:151`); Giữ* (`qt/CastVoice.qml:158`); Giữ như cũ* (`qt/CastVoice.qml:198`); Lọc giọng theo giới* (`qt/CastVoice.qml:205`); Tất cả* (`qt/CastVoice.qml:207`); Đang dùng* (`qt/CastVoice.qml:327`); Máy gợi ý* (`qt/CastVoice.qml:341`); Giữ giọng này* (`qt/CastVoice.qml:364`); Dùng chung giọng* (`qt/CastVoice.qml:385`); Tìm hiểu thêm* (`qt/CastVoice.qml:385`); Đang tải lịch sử (`qt/HistoryList.qml:62`); Chủ Nhật (`qt/HistoryLogic.js:10`); Thứ Ba (`qt/HistoryLogic.js:10`); Thứ Bảy (`qt/HistoryLogic.js:10`); Thứ Hai (`qt/HistoryLogic.js:10`); Thứ Năm (`qt/HistoryLogic.js:10`); Thứ Sáu (`qt/HistoryLogic.js:10`); Thứ Tư (`qt/HistoryLogic.js:10`); Hồ sơ nghe: {} (`qt/RecordChip.qml:14`); Lần nghe (`qt/RecordLogic.js:10`); Đổi tên hồ sơ này… (`qt/RecordLogic.js:39`); Hồ sơ mới “ (`qt/RecordLogic.js:104`)
- chỉ web (12): Đã làm sẵn (`198`); Chờ áp dụng: giọng (`558`); Nghe tiếp từ (`676`); Lần nghe {} (`699`); Chia sẻ (`1233`); Đã nghe {} {} · {} (`31`); Chưa nghe · {} chương (`63`); Nghe tiếp · {} (`82`); Shift+→ (`100`); Chưa có audio (`110`); Chạm (`121`); Nghe bằng giọng đọc.{} (`143`)

### Cài đặt

- chỉ Qt (109): Chưa làm được lúc này. (`qt/BookTemplates.qml:28`); Chưa lưu được mẫu{} (`qt/BookTemplates.qml:28`); Chưa kết nối* (`qt/DevicesLogic.js:62`); Đang nối qua Bluetooth* (`qt/DevicesLogic.js:64`); Đang nối qua Tailscale* (`qt/DevicesLogic.js:69`); Đang nối qua Wi-Fi nhà* (`qt/DevicesLogic.js:70`); Đang nối qua mạng* (`qt/DevicesLogic.js:72`); Gửi trước rồi bỏ ghép* (`qt/DevicesLogic.js:109`); Thử gửi trước rồi bỏ ghép* (`qt/DevicesLogic.js:111`); Vẫn bỏ ghép, bỏ thay đổi* (`qt/DevicesLogic.js:115`); Tải sách* (`qt/DevicesLogic.js:140`); Xuất M4B* (`qt/DevicesLogic.js:140`); Xuất MP3* (`qt/DevicesLogic.js:140`); Xuất sách nói* (`qt/DevicesLogic.js:140`); Việc nền* (`qt/DevicesLogic.js:149`); Việc* (`qt/DevicesLogic.js:150`); Bản ABook* (`qt/DevicesLogic.js:176`); Giờ trên máy* (`qt/DevicesLogic.js:184`); Mạng* (`qt/DevicesLogic.js:192`); Chỗ trống* (`qt/DevicesLogic.js:198`); Thông báo* (`qt/DevicesLogic.js:202`); Chạy nền* (`qt/DevicesLogic.js:203`); Đang nghe* (`qt/DevicesLogic.js:207`); Cho máy khác nghe thư viện* (`qt/DevicesLogic.js:219`); Lần tắt gần nhất* (`qt/DevicesLogic.js:223`); Lần văng* (`qt/DevicesLogic.js:227`); Phục hồi dữ liệu* (`qt/DevicesLogic.js:228`); Chưa có dòng nào.* (`qt/DevicesLogic.js:242`); Đang tải* (`qt/DevicesSkeleton.qml:9`); Chưa lưu được cài đặt{} (`qt/ListenSave.qml:9`); Phím một chữ cái đang tắt (`qt/LookShortcuts.qml:12`); Cửa sổ mini (`qt/LookShortcuts.qml:15`); Tải lại ({}) (`qt/MyMusicModule.qml:35`); Bật đo cảm xúc (`qt/MyMusicModule.qml:39`); Tải tiếp ({}) (`qt/MyMusicModule.qml:39`); Tắt đo cảm xúc (`qt/MyMusicModule.qml:39`); Phân tích nhạc (`qt/MyMusicModule.qml:75`); Cảm xúc chính xác (`qt/MyMusicModule.qml:147`); Xoá file ({}) (`qt/MyMusicModule.qml:186`); Chưa đổi được* (`qt/MyMusicSettings.qml:96`); Chọn nhạc của bạn (`qt/MyMusicSettings.qml:120`); Đang phân tích nhạc đã thêm (`qt/MyMusicText.js:32`); Đang nghe kỹ bài vừa thêm (`qt/MyMusicText.js:64`); Chạy (`qt/MyMusicText.js:68`); Tự chọn (`qt/MyMusicText.js:80`); Chưa phân tích (`qt/MyMusicText.js:81`); Có lời (`qt/MyMusicText.js:89`); Hợp không khí đoạn này (`qt/MyMusicText.js:92`); Không tự chọn (`qt/MyMusicText.js:92`); Chưa thêm được nhạc* (`qt/MyMusicText.js:116`); Đã thêm: {} (`qt/MyMusicText.js:121`); Chưa có bản đọc đã lưu.* (`qt/MyMusicText.js:131`); Ghi chú cho người bảo trì* (`qt/MyMusicText.js:147`); Dừng nghe thử* (`qt/MyMusicTrack.qml:81`); Chất lượng cao* (`qt/NewBookDefaults.qml:12`); Cân bằng* (`qt/NewBookDefaults.qml:12`); Kết nối Wi-Fi* (`qt/OtherComputers.qml:35`); Chưa bỏ ghép được* (`qt/OtherComputers.qml:122`); Chưa ghép được: {} (`qt/OtherComputers.qml:339`); Dùng Bluetooth cho (`qt/OtherComputersBluetooth.qml:28`); Vân tay {} (`qt/OtherComputersRow.qml:99`); Mở Studio của (`qt/OtherComputersRow.qml:113`); Chưa lưu được nhật ký* (`qt/PhoneDiagnostics.qml:50`); Chọn nơi lưu nhật ký* (`qt/PhoneDiagnostics.qml:50`); Đã lưu nhật ký* (`qt/PhoneDiagnostics.qml:50`); Làm mới* (`qt/PhoneDiagnostics.qml:68`); Lưu nhật ký* (`qt/PhoneDiagnostics.qml:69`); Chi tiết kỹ thuật* (`qt/PhoneDiagnostics.qml:106`); Nhật ký của ABook ({} dòng)* (`qt/PhoneDiagnostics.qml:120`); Mở {}* (`qt/PhoneSync.qml:198`); Điều khiển sản xuất từ (`qt/PhoneSyncDevice.qml:88`); Địa chỉ: {} (`qt/PhoneSyncPairing.qml:59`); Mã ghép nối: (`qt/PhoneSyncPairing.qml:73`); Hết hạn sau {}:{} (`qt/PhoneSyncPairing.qml:82`); Dùng được · (`qt/ProviderKey.qml:41`); Khoá (`qt/ProviderKey.qml:139`); Tự chọn nhạc nền* (`qt/SettingsListen.qml:24`); Thu vào khay khi đóng (`qt/SettingsLook.qml:14`); Tự mở cửa sổ mini (`qt/SettingsLook.qml:19`); Giấy* (`qt/SettingsLook.qml:34`); Ngà* (`qt/SettingsLook.qml:34`); Đêm* (`qt/SettingsLook.qml:34`); Cần cập nhật* (`qt/StudioSettings.qml:140`); Mất {} (`qt/StudioSettings.qml:140`); Giọng của máy* (`qt/VoiceLogic.js:39`); Nữ* (`qt/VoiceLogic.js:44`); Mỹ Duyên* (`qt/VoiceLogic.js:92`); Ngọc Linh (`qt/VoiceLogic.js:92`); Quỳnh Anh (`qt/VoiceLogic.js:92`); Thanh Bình* (`qt/VoiceLogic.js:92`); Thục Đoan (`qt/VoiceLogic.js:92`); Đoan Trang (`qt/VoiceLogic.js:92`); Đức Trí* (`qt/VoiceLogic.js:92`); Ái Hân* (`qt/VoiceLogic.js:93`); Ngọc Huyền (`qt/VoiceLogic.js:96`); Ngọc Trân (`qt/VoiceLogic.js:96`); Trúc Ly (`qt/VoiceLogic.js:96`); Giọng VieNeu* (`qt/VoiceLogic.js:130`); Giọng Supertonic* (`qt/VoiceLogic.js:135`); Giọng VieNeu Nano* (`qt/VoiceLogic.js:139`); Đang đọc bằng bản thường.* (`qt/VoiceLogic.js:217`); Đang đọc bằng bản tăng tốc.* (`qt/VoiceLogic.js:219`); Máy này chưa dùng được {}. (`qt/VoiceLogic.js:252`); Tốc độ đọc* (`qt/VoiceLogic.js:275`); Chất lượng cao nhất* (`qt/VoiceLogic.js:278`); Nhanh hơn* (`qt/VoiceLogic.js:279`); Gỡ (`qt/VoiceModule.qml:263`); Thử giọng (`qt/VoiceRow.qml:105`); Thử* (`qt/VoiceRow.qml:109`)
- chỉ web (28): Chưa lưu được mẫu (`24`); Mở Studio của {} (`204`); Hỏi lại (`224`); Dùng Bluetooth cho {} (`344`); Bluetooth (`353`); Địa chỉ: (`153`); Trình duyệt: mở (`154`); Mã ghép nối: {} (`159`); Hết hạn sau (`167`); Kết nối lần cuối (`340`); Điều khiển sản xuất từ {} (`344`); Chưa đổi được lịch đêm (`29`); ABook{} là bản mới nhất. (`22`); Space (`18`); Chưa nghe thử được giọng này. (`111`); ...

### Thêm sách

- chỉ Qt (24): Chưa mở được file sách* (`qt/AddBook.qml:224`); Đã mở (`qt/AddBook.qml:235`); Bỏ qua* (`qt/AddBook.qml:402`); Đang đọc file tiếp (`qt/AddBook.qml:529`); Đang đọc file sách (`qt/AddBook.qml:587`); Không đọc số chú thích (`qt/AddBook.qml:879`); Đọc lời chú ở cuối chương (`qt/AddBook.qml:888`); Bỏ lời chú* (`qt/AddBook.qml:896`); Bỏ dòng này khỏi phần đọc (`qt/AddBook.qml:965`); Đang thêm {} (`qt/AddBook.qml:1006`); Tất cả file (*) (`qt/AddBook.qml:1038`); Đưa vào sách: (`qt/ImportChapters.qml:101`); Bấm để đổi tên chương* (`qt/ImportChapters.qml:136`); Tên chương* (`qt/ImportChapters.qml:175`); Thả để thêm sách* (`qt/ImportDrop.qml:53`); Tách theo {} dòng “Chương N” (`qt/ImportQueue.js:119`); File này có bản thu khác* (`qt/ImportQueue.js:198`); Sách đã có* (`qt/ImportQueue.js:198`); Đã cập nhật* (`qt/ImportQueue.js:198`); Sách của Studio* (`qt/ImportQueue.js:199`); Đã khôi phục file* (`qt/ImportQueue.js:199`); Đã mở dự án* (`qt/ImportQueue.js:199`); Đã gộp {} sửa từ file* (`qt/ImportQueue.js:206`); Đang tải* (`qt/ImportSkeleton.qml:11`)
- chỉ web (2): Xem trước (`542`); Tách chương (`705`)

### Sửa sách

- chỉ Qt (42): Mức nhạc nền* (`qt/BookMusicSettings.qml:113`); Chưa đọc được file ảnh* (`qt/EditBook.qml:406`); Lưu thay đổi* (`qt/EditBookItems.qml:71`); Chưa nối được {} (`qt/EditBookLogic.js:68`); Đang thêm nhạc thì dừng* (`qt/EditBookMyMusic.qml:69`); Chưa xoá được bài này* (`qt/EditBookMyMusic.qml:82`); Đã xoá khỏi Nhạc của tôi* (`qt/EditBookMyMusic.qml:82`); Chọn nhạc của bạn (`qt/EditBookMyMusic.qml:115`); Nhạc của tôi* (`qt/EditBookMyMusic.qml:124`); Chưa có bài nào* (`qt/EditBookMyMusic.qml:125`); Thêm nhạc của bạn* (`qt/EditBookMyMusic.qml:134`); Đang thêm {}/{}* (`qt/EditBookMyMusic.qml:134`); Nhạc riêng* (`qt/EditBookMyMusic.qml:146`); Phân tích nhạc (`qt/EditBookMyMusic.qml:158`); Huỷ* (`qt/EditBookMyMusic.qml:174`); Cập nhật ({})* (`qt/EditBookMyMusic.qml:182`); Phân tích {} bài (`qt/EditBookMyMusic.qml:182`); Thử lại* (`qt/EditBookMyMusic.qml:182`); Tải ({})* (`qt/EditBookMyMusic.qml:182`); Tải lại ({}) (`qt/EditBookMyMusic.qml:182`); Đang tải nhạc riêng* (`qt/EditBookMyMusic.qml:194`); Xoá* (`qt/EditBookMyMusic.qml:289`); Xoá: {}* (`qt/EditBookMyMusic.qml:290`); Xoá bài* (`qt/EditBookMyMusic.qml:303`); Xoá bài: {}* (`qt/EditBookMyMusic.qml:305`); Giữ lại* (`qt/EditBookMyMusic.qml:310`); Giữ lại: {}* (`qt/EditBookMyMusic.qml:312`); Chưa bỏ được cách đọc* (`qt/EditBookReadings.qml:28`); Chưa lưu được cách đọc* (`qt/EditBookReadings.qml:28`); Đang tải cách đọc* (`qt/EditBookReadings.qml:68`); Sửa cách đọc {}* (`qt/EditBookReadings.qml:113`); Bỏ cách đọc {}* (`qt/EditBookReadings.qml:123`); Cách đọc cho {}* (`qt/EditBookReadings.qml:142`); Lưu cho cả cuốn* (`qt/EditBookReadings.qml:153`); Đọc như chữ trong sách (`qt/EditBookReadings.qml:161`); Đổi tên chương* (`qt/EditBookRename.qml:19`); Số chương hay nhãn (`qt/EditBookRename.qml:44`); Tên chương (có thể để trống) (`qt/EditBookRename.qml:44`); Chọn nơi lưu* (`qt/EditBookSaveAs.qml:52`); Đang tải* (`qt/EditBookSkeleton.qml:11`); Đang tải bài nhạc* (`qt/EditBookSwap.qml:39`); Chọn* (`qt/EditBookSwap.qml:94`)
- chỉ web (6): Bỏ mọi thay đổi ({}) (`469`); Nhãn (`543`); Tên (`554`); Chưa chia sẻ được sách (`610`); Google Books (`13`); Open Library (`13`)

### Thanh bên

- chỉ Qt (10): Trạng thái ABook (`qt/ConnectionChip.qml:10`); Gặp lỗi (`qt/ConnectionChip.qml:55`); Sẵn sàng (`qt/ConnectionChip.qml:55`); Đang mở…* (`qt/ConnectionChip.qml:55`); Bản {} (`qt/ConnectionPopover.qml:73`); Khởi động lại (`qt/ConnectionPopover.qml:85`); Mở thư mục nhật ký (`qt/ConnectionPopover.qml:93`); Mở rộng (`qt/Sidebar.qml:93`); Thu gọn* (`qt/Sidebar.qml:93`); Duyệt* (`qt/SidebarProgress.qml:37`)
- chỉ web (1): Thanh bên (`173`)

### Studio dự án

- chỉ Qt (44): Làm* (`qt/OnComputerPill.qml:10`); Chưa gộp được* (`qt/ProjectScreen.qml:138`); Chưa làm được lúc này. (`qt/ProjectScreen.qml:138`); Chưa khởi động được: {} (`qt/ProjectScreen.qml:475`); Chưa có chương nào (`qt/ProjectScreen.qml:741`); Đang tải nhật ký (`qt/ProjectScreen.qml:763`); Không thấy thư mục thư viện* (`qt/ProjectsScreen.qml:228`); Chọn thư mục* (`qt/ProjectsScreen.qml:231`); Chọn lại thư mục thư viện* (`qt/ProjectsScreen.qml:232`); Mở dự án có sẵn… (`qt/ProjectsScreen.qml:257`); Nghe* (`qt/StudioChapterRow.qml:49`); Chi tiết lỗi (`qt/StudioChapterRow.qml:122`); Tuỳ chọn* (`qt/StudioChapterRow.qml:197`); Đóng* (`qt/StudioDialogs.qml:63`); 0 phút* (`qt/StudioLogic.js:21`); Còn* (`qt/StudioLogic.js:95`); Sắp tới lượt (`qt/StudioLogic.js:95`); Chờ bạn duyệt (`qt/StudioLogic.js:100`); Mất kết nối tới ABook. (`qt/StudioLogic.js:120`); Đang tạm dừng* (`qt/StudioLogic.js:217`); Sách vẫn đang tạm dừng (`qt/StudioLogic.js:222`); Đang làm tiếp (`qt/StudioLogic.js:228`); Card đồ hoạ hết bộ nhớ.* (`qt/StudioLogic.js:263`); Ổ đĩa hết chỗ trống.* (`qt/StudioLogic.js:277`); Có lỗi khi làm sách.* (`qt/StudioLogic.js:294`); Áp dụng* (`qt/StudioLogic.js:340`); Cài Studio* (`qt/StudioLogic.js:429`); Cập nhật Studio* (`qt/StudioLogic.js:429`); Sửa Studio* (`qt/StudioLogic.js:429`); Bộ phân tích bản {}* (`qt/StudioLogic.js:491`); Bộ phân tích tuỳ chọn* (`qt/StudioLogic.js:491`); Tạo {} (`qt/StudioLogic.js:504`); Mất file audio (`qt/StudioLogic.js:528`); Lỗi {} (`qt/StudioStore.qml:48`); Chưa bắt đầu được (`qt/StudioStore.qml:131`); Chưa làm tiếp được (`qt/StudioStore.qml:149`); Chưa tạm dừng được (`qt/StudioStore.qml:149`); Chưa dừng được (`qt/StudioStore.qml:160`); Chưa bỏ xếp hàng được (`qt/StudioStore.qml:171`); Chưa mở được thư mục (`qt/StudioStore.qml:179`); Hoàn tác* (`qt/StudioStore.qml:194`); Chưa hoàn tác được* (`qt/StudioStore.qml:205`); Đã khôi phục “{}”* (`qt/StudioStore.qml:205`); Chưa đổi được* (`qt/StudioStore.qml:242`)
- chỉ web (8): Chưa khởi động được: (`197`); Làm tiếp từ chỗ ấy (`373`); Phân tích của “ (`373`); Tuỳ chọn dự án {} (`600`); Chờ lượt (`769`); Thu lại (`919`); Chưa tải được (`1387`); Chưa đọc được dự án này (`40`)

### Studio tạo sách

- chỉ Qt (35): Tìm ảnh bìa* (`qt/CoverEditor.qml:194`); Chọn ảnh bìa* (`qt/CoverPicker.qml:13`); Gợi ý: {} chương có {} (`qt/NewCredits.qml:60`); Chọn {} tập (`qt/NewDrop.qml:215`); Tách theo {} (`qt/NewHints.qml:88`); Truyện (*.txt *.epub *.docx *.pdf) (`qt/NewPicker.qml:18`); Tất cả file (*) (`qt/NewPicker.qml:18`); Đang đọc nguồn… (`qt/NewProjectLogic.js:49`); Nhân vật tự kể* (`qt/NewProjectLogic.js:193`); Thứ tự lệch: {} (`qt/NewProjectLogic.js:234`); Có vẻ thiếu {} (`qt/NewProjectLogic.js:235`); Bản thử nghiệm (`qt/NewProjectLogic.js:371`); Chưa làm được lúc này. (`qt/NewProjectStore.qml:59`); Chưa đọc được:* (`qt/NewProjectStore.qml:154`); Đã áp (`qt/NewProjectStore.qml:224`); Có file không gửi{} (`qt/NewProjectStore.qml:270`); Chưa gửi được. (`qt/NewProjectStore.qml:285`); Không gửi hết các chương{} {} (`qt/NewProjectStore.qml:313`); Tìm hiểu thêm* (`qt/NewTemplateBar.qml:144`); Dùng lại {} (`qt/NewVoice.qml:211`); Chia {} phần? (`qt/NewVolumes.qml:52`); Máy thấy {} (`qt/NewVolumes.qml:58`); Studio chưa xong{} (`qt/StudioSetupCard.qml:28`); Tiến độ:* (`qt/StudioSetupCard.qml:207`); Máy này {}. (`qt/StudioSetupLogic.js:17`); Tải lại {} (`qt/StudioSetupLogic.js:61`); Tạo trên {} (`qt/StudioSetupNotice.qml:98`); Mặc định* (`qt/TemplateLogic.js:12`); Đặt cho mẫu một cái tên (`qt/TemplateLogic.js:49`); Tên mẫu tối đa {} chữ (`qt/TemplateLogic.js:50`); Đã có mẫu “{}” (`qt/TemplateLogic.js:52`); Giọng máy đề xuất* (`qt/TemplateLogic.js:57`); Tải lên {} (`qt/UploadLogic.js:29`); Chưa gửi file nào. (`qt/UploadLogic.js:93`); Đã gửi {}/{} file, giữ lại (`qt/UploadLogic.js:95`)
- chỉ web (29): Bản thử nghiệm{} (`53`); Bản thử nghiệm ({}) (`59`); Nhanh (`94`); Có file không gửi (`305`); Không gửi hết các chương (`312`); Gửi các chương từ máy này (`437`); Sẽ bỏ (`775`); Gợi ý: (`780`); Gợi ý: “ (`862`); Tách theo (`863`); Tách thành (`875`); Nam (`1108`); Giọng kể phần trước: (`1201`); Đang chọn: (`1226`); Tham khảo: (`1314`); ...

### Studio việc duyệt

- chỉ Qt (33): Đã hoàn tác (`qt/DecisionLogic.js:32`); Đã hoàn tác. {} (`qt/DecisionLogic.js:32`); Trước đó chưa ai quyết khác (`qt/DecisionLogic.js:40`); Trước đó đang là {} (`qt/DecisionLogic.js:40`); Xem thêm {} tên (`qt/NameLogic.js:34`); Thêm* (`qt/NameLogic.js:46`); Đã bỏ qua ({}) (`qt/PhoneEdits.qml:84`); Bỏ qua mọi việc từ (`qt/PhoneEdits.qml:154`); Dùng “{}” (`qt/ReadingProblem.qml:40`); Máy nghe ra: “{}” (`qt/ReviewLogic.js:42`); Sẽ đọc là “{}” (`qt/ReviewLogic.js:47`); Tải tiếp · còn (`qt/ReviewLogic.js:60`); Nghe liền {} câu (`qt/ReviewQueue.qml:254`); Nghe câu: (`qt/ReviewRow.qml:83`); Đang đọc là: <span style="color:{}">{} (`qt/ReviewRow.qml:212`); Máy đọc câu này thành (`qt/ReviewSpoken.qml:42`); Ảnh hưởng <b><span style="color:{}">{} (`qt/WorkCard.qml:150`); Đang mở* (`qt/WorkCard.qml:342`); Đang đóng (`qt/WorkCard.qml:342`); Xem thêm {} việc (`qt/WorkInbox.qml:219`); Đoạn này do (`qt/WorkLogic.js:49`); Đang chọn cả {} câu* (`qt/WorkLogic.js:154`); Đang chọn {}/{} câu* (`qt/WorkLogic.js:156`); Xem thêm (đang hiện {}/{} câu)* (`qt/WorkLogic.js:165`); Giọng nam* (`qt/WorkLogic.js:221`); Giọng nữ* (`qt/WorkLogic.js:221`); Mọi việc đã có quyết định (`qt/WorkLogic.js:276`); Đúng rồi, giữ “{}” (`qt/WorkPronunciation.qml:35`); Cả chuỗi (`qt/WorkSpeaker.qml:63`); Xem {} câu (`qt/WorkSpeaker.qml:155`); Chưa hoàn tác được* (`qt/WorkStore.qml:88`); Mới hoàn tác được {}/{} việc (`qt/WorkStore.qml:88`); Đã dùng (`qt/WorkStore.qml:324`)
- chỉ web (21): Tìm hoặc thêm tên (`126`); Không khớp “ (`164`); Bỏ qua mọi việc từ {}? (`232`); Dùng “ (`27`); Máy nghe ra: “ (`224`); Sẽ đọc là “ (`233`); Đang đọc là: (`238`); Nghe liền (`459`); Tải tiếp · còn {} câu (`505`); Nghe thử {} đọc là {} (`100`); Chưa nghe thử được: (`147`); Đúng rồi, giữ “ (`379`); Xem (`612`); Nam (`639`); Ảnh hưởng (`935`); ...

### Studio nhân vật

- chỉ Qt (1): Đổi giọng kể* (`qt/TellerLogic.js:38`)
- chỉ web (8): Nam (`92`); Giọng đọc của (`153`); Áp dụng sẽ thu lại (`160`); Không có ai khớp “ (`123`); Tên nào cũng ổn (`164`); Không câu nào nghi (`165`); Nghe và chỉnh giọng cho (`227`); Giọng của {} (`251`)

### Studio kịch bản

- chỉ Qt (7): Người nghĩ (`qt/ScriptRow.qml:97`); Người nói (`qt/ScriptRow.qml:97`); Gán cho {} (`qt/ScriptRow.qml:245`); Thu lại câu này* (`qt/ScriptRow.qml:291`); Lấy của máy kia (`qt/ScriptStore.qml:53`); Đang chọn {} câu (`qt/ScriptTab.qml:466`); Duyệt {} câu (`qt/ScriptTab.qml:588`)
- chỉ web (8): Cách đọc câu này (`767`); Nam (`867`); Ai nghĩ câu này? (`940`); Đang chọn. (`1067`); Cách đọc mới không áp được: (`1104`); Gán cho (`1118`); Yêu cầu (`1143`); Thu lại câu này (R) (`1151`)

### Studio xuất và áp dụng

- chỉ Qt (27): Xuất “ (`qt/ExportBook.qml:51`); Kèm nhạc nền* (`qt/ExportBook.qml:209`); Cỡ ước tính: khoảng {} (`qt/ExportBook.qml:222`); Xuất {} chương đổi (`qt/ExportBook.qml:305`); Đang đóng gói* (`qt/ExportLogic.js:51`); Đã xuất vào máy tính* (`qt/ExportLogic.js:96`); Đã xuất vào máy tính {}* (`qt/ExportLogic.js:96`); Đã xuất (`qt/ExportLogic.js:112`); Phần {}* (`qt/ExportLogic.js:170`); Đã xuất MP3* (`qt/ExportLogic.js:189`); Đã xuất M4B* (`qt/ExportLogic.js:191`); Đang tải nhạc nền {}/{} bài* (`qt/ExportLogic.js:200`); Đang kiểm đỉnh âm…* (`qt/ExportLogic.js:202`); Chương {}/{}* (`qt/ExportLogic.js:206`); Đang ghi chương {}/{}* (`qt/ExportLogic.js:208`); Đang trộn nhạc chương {}/{}* (`qt/ExportLogic.js:210`); Đang chờ mạng…* (`qt/ExportLogic.js:215`); Đang thêm chữ sáng… (`qt/ExportLogic.js:258`); Bỏ cách đọc “{} (`qt/ExportLogic.js:276`); Công cụ ghép âm thanh* (`qt/FfmpegNeeded.qml:25`); Cập nhật công cụ* (`qt/FfmpegNeeded.qml:30`); Thiếu công cụ ghép* (`qt/FfmpegNeeded.qml:30`); Dừng* (`qt/FfmpegNeeded.qml:50`); Tải công cụ ghép âm thanh* (`qt/FfmpegNeeded.qml:76`); Thử lại* (`qt/FfmpegNeeded.qml:97`); Tải công cụ* (`qt/FfmpegNeeded.qml:97`); Nghe thử* (`qt/PendingRow.qml:82`)
- chỉ web (6): Bỏ cách đọc “{}” (`56`); Thu lại (`196`); File .abook (`55`); Xuất “{}” (`359`); Cỡ ước tính: khoảng (`509`); Đang thêm chữ sáng… {}% (`43`)

### Studio máy khác

- chỉ Qt (1): Studio* (`qt/StudioScreen.qml:210`)
- chỉ web (0): (không có)

### Thanh tiêu đề

- chỉ Qt (2): ABook vẫn chạy ở khay (`qt/Main.qml:28`); Chưa tải được bản mới* (`qt/Main.qml:320`)
- chỉ web (3): Mở rộng (Ctrl+B) (`255`); Thu gọn (Ctrl+B) (`255`); Điều hướng (`272`)

### Chung

- chỉ Qt (2): Chưa làm được lúc này. (`qt/Api.qml:49`); Quay lại* (`qt/ScreenHeader.qml:14`)
- chỉ web (4): Đang tải điều hướng (`581`); Thông báo (Alt+T) (`697`); Xem các tab trước (`516`); Xem các tab sau (`521`)

File QML chưa xếp màn (thêm vào SCREENS): `desktop_qt/qml/BookLogic.js`, `desktop_qt/qml/CastLogic.js`, `desktop_qt/qml/FindInBook.qml`, `desktop_qt/qml/FindLogic.js`, `desktop_qt/qml/MusicCredit.qml`, `desktop_qt/qml/MusicLevelSlider.qml`, `desktop_qt/qml/MusicPopover.qml`, `desktop_qt/qml/PeerStudio.js`, `desktop_qt/qml/PlayerConsent.qml`, `desktop_qt/qml/ProjectSteps.qml`, `desktop_qt/qml/StudioChapterHead.qml`, `desktop_qt/qml/StudioMusic.qml`, `desktop_qt/qml/StudioMusicLogic.js`, `desktop_qt/qml/StudioMusicMoods.qml`, `desktop_qt/qml/StudioMusicScene.qml`, `desktop_qt/qml/StudioMusicSwap.qml`, `desktop_qt/qml/StudioMusicTrackRow.qml`, `desktop_qt/qml/StudioMyMusic.qml`, `desktop_qt/qml/UiNumber.js`, `desktop_qt/qml/ValuePicker.qml`, `desktop_qt/qml/ValuePickerLogic.js`.

## d. Bo góc QML không theo token

Hợp lệ: `Theme.radiusControl / radiusCover / radiusSheet` (DESIGN.md 5.5, `desktop_qt/tools/gen_theme.py`), `0`, tròn (`width / 2`, `height / 2`), lấy lại bo khung chứa (`parent.radius`), vòng đồng tâm ngoài (`Theme.radiusCover + 8` của bóng, vòng tiêu điểm). Còn lại (0):

| nơi | radius |
|---|---|
| (không có) | |

## e. Dấu thanh kiểu mới và dấu ba chấm cuối nhãn

**Dấu thanh kiểu mới (`òa óa úy`)** trong chữ Qt (0); web và native đa số viết kiểu cũ (`oà oá uý`, UI_PARITY.md d2):

- (không có)

**Nhãn kết thúc bằng `…` / `...`** (80): DESIGN.md chỉ cho `…` ở chữ đang chờ ("Đang mở…"), không cho nhãn nút.

- Bỏ mọi thay đổi… (`qt/EditBook.qml:339`) - web: `Bỏ mọi thay đổi`
- Chuyển sang cuốn khác… (`qt/RecordLogic.js:40`) - web: `Chuyển sang cuốn khác`
- Chưa tải lại được sách: {} Đang thử lại… (`qt/StudioLogic.js:566`) - web: `Chưa tải lại được sách: {} Đang thử lại`
- Chọn cuốn… (`qt/RecordDialogs.qml:118`) - web: `Chọn cuốn`
- Chọn giọng khác… (`qt/WorkCard.qml:230`) - web: `Chọn giọng khác`
- Chọn thư mục… (`qt/EditBookSaveAs.qml:81`) - web: `Chọn thư mục`
- Chọn ảnh bìa… (`qt/EditBook.qml:239`) - web: `Chọn ảnh bìa`
- Chữ hay câu cần tìm… (`qt/FindInBook.qml:120`) - web: `Chữ hay câu cần tìm`
- Dừng… (`qt/StudioLogic.js:447`) - web: `Dừng`
- Giữ {} thẻ… (`qt/WorkBulkKeep.qml:27`) - web: (không có)
- Gộp vào người khác… (`qt/CastMenu.qml:29`) - web: `Gộp vào người khác`
- Gộp vào… (`qt/PrecastReview.qml:418`) - web: `Gộp vào`
- Khôi phục bản sao… (`qt/StudioLogic.js:476`) - web: `Khôi phục bản sao`
- Làm tiếp cuốn này… (`qt/StudioLogic.js:466`) - web: `Làm tiếp cuốn này`
- Lưu thành mẫu… (`qt/NewTemplateBar.qml:80`) - web: `Lưu thành mẫu`
- Lưu thành… (`qt/EditBookItems.qml:81`) - web: `Lưu thành`
- Lưu thành… (`qt/EditBookSaveAs.qml:17`) - web: `Lưu thành`
- Mạng chập chờn - đang thử lại… (`qt/MyMusicText.js:11`) - web: (không có)
- Mạng chập chờn - đang thử lại… (`qt/VoiceLogic.js:16`) - web: (không có)
- Mất kết nối tới ABook, đang thử lại… (`qt/StudioLogic.js:566`) - web: `Mất kết nối tới ABook, đang thử lại`
- Mọi cách đọc tên… (`qt/WorkPronunciation.qml:76`) - web: `Mọi cách đọc tên`
- Mở dự án có sẵn… (`qt/ProjectsScreen.qml:257`) - web: (không có)
- Người kể khác… (`qt/WorkNarrator.qml:66`) - web: `Người kể khác`
- Thu lại cả chương… (`qt/ProjectScreen.qml:247`) - web: `Thu lại cả chương`
- Thêm giọng… (`qt/NowPlaying.qml:611`) - web: `Thêm giọng`
- Thêm giọng… (`qt/PlayerVoicePopover.qml:31`) - web: `Thêm giọng`
- Tìm bìa… (`qt/EditBook.qml:248`) - web: `Tìm bìa`
- Tìm chữ trong chương… (`qt/ScriptTab.qml:720`) - web: `Tìm chữ trong chương`
- Tìm người khác trong truyện… (`qt/ScriptSpeakerMenu.qml:30`) - web: `Tìm người khác trong truyện`
- Tìm người khác… (`qt/WorkSpeaker.qml:145`) - web: `Tìm người khác`
- Tìm người trong truyện… (`qt/CastMerge.qml:51`) - web: `Tìm người trong truyện`
- Tìm người trong truyện… (`qt/CastMerge.qml:52`) - web: `Tìm người trong truyện`
- Tìm tên… (`qt/SharedReadingsSettings.qml:61`) - web: `Tìm tên`
- Vẫn tiếp tục… (`qt/StudioLogic.js:446`) - web: `Vẫn tiếp tục`
- Xoá dự án… (`qt/StudioLogic.js:470`) - web: `Xoá dự án`
- Xoá hồ sơ này… (`qt/RecordLogic.js:41`) - web: `Xoá hồ sơ này`
- Xoá hồ sơ… (`qt/RecordLogic.js:28`) - web: `Xoá hồ sơ`
- Xuất… (`qt/StudioLogic.js:451`) - web: `Xuất`
- {} ({}/{} chương)… (`qt/ExportLogic.js:58`) - web: (không có)
- Đang chuẩn bị giọng đọc… (`qt/PlayButton.qml:14`) - web: `Đang chuẩn bị giọng đọc`
- Đang chuẩn bị giọng đọc… (`qt/PlayerSubtitle.qml:21`) - web: `Đang chuẩn bị giọng đọc`
- Đang chờ mạng… (`qt/ExportLogic.js:215`) - web: `Đang chờ mạng…`
- Đang dừng… (`qt/NewChapters.qml:106`) - web: `Đang dừng`, `Đang dừng…`
- Đang dừng… (`qt/NewDrop.qml:129`) - web: `Đang dừng`, `Đang dừng…`
- Đang dừng… (`qt/StudioLogic.js:333`) - web: `Đang dừng`, `Đang dừng…`
- Đang gỡ… (`qt/StudioSettings.qml:124`) - web: `Đang gỡ`
- Đang huỷ… (`qt/ExportLogic.js:346`) - web: `Đang huỷ…`
- Đang kiểm tra… (`qt/AdvancedUpdate.qml:117`) - web: `Đang kiểm tra`, `đang kiểm tra`
- Đang kiểm đỉnh âm… (`qt/ExportLogic.js:202`) - web: `Đang kiểm đỉnh âm`, `Đang kiểm đỉnh âm…`
- Đang làm file M4B… (`qt/ExportLogic.js:191`) - web: `Đang làm file M4B…`
- Đang làm file M4B… (`qt/ExportLogic.js:21`) - web: `Đang làm file M4B…`
- Đang mở thư viện… (`qt/RecordDialogs.qml:98`) - web: `Đang mở thư viện`
- Đang mở văn bản chương… (`qt/ReadAlongView.qml:361`) - web: (không có)
- Đang mở… (`qt/ConnectionChip.qml:55`) - web: `Đang mở`
- Đang mở… (`qt/LibraryScreen.qml:447`) - web: `Đang mở`
- Đang thêm chữ sáng… (`qt/ExportLogic.js:258`) - web: (không có)
- Đang thử giọng vừa tải trên máy này (vài giây)… (`qt/VoiceLogic.js:251`) - web: `Đang thử giọng vừa tải trên máy này (và…`
- Đang tìm… (`qt/FindLogic.js:132`) - web: `Đang tìm`
- Đang tải bản mới… (`qt/AdvancedUpdate.qml:95`) - web: `Đang tải bản mới`
- Đang tải chương… (`qt/ChapterReader.qml:87`) - web: (không có)
- Đang tải nhạc nền ({}/{})… (`qt/ExportLogic.js:345`) - web: `Đang tải nhạc nền ({}/{})…`
- Đang tải âm thanh… (`qt/PlayButton.qml:14`) - web: `Đang tải âm thanh`
- Đang tải… (`qt/ReviewLogic.js:60`) - web: `Đang tải`, `đang tải`
- Đang tải… (`qt/WorkCard.qml:354`) - web: `Đang tải`, `đang tải`
- Đang xem cuốn nào còn dùng giọng này… (`qt/VoiceModule.qml:403`) - web: `Đang xem cuốn nào còn dùng giọng này`
- Đang xem các thay đổi… (`qt/ApplyChanges.qml:70`) - web: `Đang xem các thay đổi`
- Đang xuất MP3… (`qt/ExportLogic.js:189`) - web: `Đang xuất MP3`, `Đang xuất MP3…`
- Đang xuất MP3… (`qt/ExportLogic.js:19`) - web: `Đang xuất MP3`, `Đang xuất MP3…`
- Đang đo lại tốc độ trên máy này (vài giây)… (`qt/VoiceLogic.js:251`) - web: `Đang đo lại tốc độ trên máy này (vài gi…`
- Đang đóng gói dự án… (`qt/ExportLogic.js:22`) - web: `Đang đóng gói dự án…`
- Đang đóng gói sách… (`qt/ExportLogic.js:20`) - web: `Đang đóng gói sách…`
- Đang đọc các chương… (`qt/NewDrop.qml:82`) - web: `Đang đọc các chương`
- Đang đọc nguồn… (`qt/NewProjectLogic.js:49`) - web: (không có)
- Đang đọc… (`qt/AddBook.qml:550`) - web: `Đang đọc`, `đang đọc`
- Đổi tên chương… (`qt/BookPage.qml:290`) - web: `Đổi tên chương`
- Đổi tên hồ sơ này… (`qt/RecordLogic.js:39`) - web: (không có)
- Đổi tên hồ sơ… (`qt/RecordLogic.js:27`) - web: `Đổi tên hồ sơ`
- Đổi tên… (`qt/StudioLogic.js:463`) - web: `Đổi tên`
- Đổi ảnh bìa… (`qt/EditBook.qml:239`) - web: `Đổi ảnh bìa`
- đang ước tính thời gian… (`qt/StudioLogic.js:380`) - web: `đang ước tính thời gian`

## f. Phím tắt trong chú thích

Chú thích Qt ghi phím tắt sau nhãn; web ghép bằng `withShortcut(nhãn, phím)`. Phím khác nhau là khác HÀNH VI (phím thật trong `Main.qml` / `player.tsx`), không chỉ khác chữ.

| nhãn | Qt | web | nơi |
|---|---|---|---|
| Thu nhỏ | `Esc` | (không ghi) | `qt/NowPlaying.qml:254` |
| Chương trước | `Shift+←` | (không ghi) | `qt/NowPlaying.qml:392` |
| Chương sau | `Shift+→` | (không ghi) | `qt/NowPlaying.qml:403` |
| Phát | `Space` | (không ghi) | `qt/PlayButton.qml:14` |
| Tạm dừng | `Space` | (không ghi) | `qt/PlayButton.qml:14` |
| {} | `Esc` | (không ghi) | `qt/ScreenHeader.qml:26` |
| Thu lại câu này | `R` | (không ghi) | `qt/ScriptRow.qml:291` |
| Mở rộng | `Ctrl+B` | (không ghi) | `qt/Sidebar.qml:93` |
| Thu gọn | `Ctrl+B` | (không ghi) | `qt/Sidebar.qml:93` |
| Lùi {} giây | `←` | (không ghi) | `qt/SkipButton.qml:12` |
| Tới {} giây | `→` | (không ghi) | `qt/SkipButton.qml:12` |
| Bật tiếng | `M` | (không ghi) | `qt/VolumeControl.qml:21` |
| Tắt tiếng | `M` | (không ghi) | `qt/VolumeControl.qml:21` |

Chú thích có hai dấu cách trước phím (web `withShortcut` ghép một dấu cách): 0.

## g. Công tắc chế độ Đang nghe (luật cứng, từng chữ, ba nền)

Mục a-c chỉ ghép nhãn GIỐNG nhau cùng màn và chỉ liệt kê nhãn một bên, nên một công tắc đổi chữ ở một nền không đỏ; riêng công tắc hai chế độ ở đầu Đang nghe (hẹp) so thẳng: Android `PlayerModeSwitch` (`NowPlayingScreen.kt`) = web `PlayerModeSwitch` (`PlayerViews.tsx`), còn Qt `PageSwitch` (`NowPlaying.qml`, `index: root.page`) phải có đúng chữ ấy ở từng ô. Ô 2 của Qt đổi sang `Chương` khi sách chưa có mốc thời gian (không có gì để đọc theo) - nhánh trạng thái, không phải chữ khác.

| nền | ô 1 | ô 2 |
|---|---|---|
| Android | `Nghe` | `Đọc theo` |
| Web | `Nghe` | `Đọc theo` |
| Qt | `Nghe` | `Chương` / `Đọc theo` |

Lệch: (không có)

## h. Cùng thao tác đã duyệt (luật cứng)

So đúng file và nhãn của thao tác, không dùng độ giống chữ. Cửa sổ mini và tự mở mini có ở Qt/Android; web trình duyệt không có cửa sổ app của hệ điều hành. Đây không còn là việc chờ Tauri/cloud-tray.

| thao tác | nhãn chuẩn | nền |
|---|---|---|
| record-create | Tạo và nghe | Qt, Web, Android |
| record-delete | Xoá hồ sơ | Qt, Web, Android |
| record-move | Chuyển | Qt, Web, Android |
| mini-enter | Cửa sổ mini | Qt, Android |
| mini-auto | Tự mở cửa sổ mini | Qt, Android |

Lệch: (không có)


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
| Chương / Đọc theo | Hai tab bảng phải ở cửa sổ rộng; hẹp vẫn có Chương cạnh hẹn giờ. Tab dùng trái/phải/Home/End; nội dung trượt, có hình học cả lúc rời và lúc vào. |
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

## Lượt đồng bộ chữ và icon 31-10 (mục a + b)

Đã mở mã hai bên cho cả 55 cặp mục a và mọi cặp mục b. Agent đã đổi 4 chữ Qt "theo web" nhưng đổi NGƯỢC: chữ Qt cũ mới
là chữ web ("Dùng Bluetooth", "Dùng Bluetooth cho {}", "Qua Bluetooth", "Huỷ mã", "Chưa tìm được"), chữ mới không có ở
web. Lead hoàn tác 31-10 22:xx (sau khi Music thấy `test_qt_copy_rules` đỏ vì "Không tìm được"); mục a còn 47 cặp. Bài học:
đổi chữ "theo web" thì grep chữ mới trong `ui/src` trước khi tin; `build.bat` nay chạy `test_qt_copy_rules.py`.

Phần còn lại của mục a là scanner ghép nhầm, giữ nguyên: (1) web ghép chữ với dữ liệu (`Mã ghép nối: {}` / `Mã ghép nối:` + mã) - cùng câu đầy đủ;
(2) Qt gom nhãn ngắn từ chuỗi dài hơn mà web cũng có nguyên văn ở chỗ khác (lời báo `Chưa ghi được`, `Chưa xoá được`, `Không dừng được`, `Chưa gộp được`,
`Chưa đổi được`, `Không làm tiếp được`, `Đã dùng N cách đọc chung`, `Không tách được`, `Đã bỏ {}`, `Nhanh nhất`, `Chia thành`, `Số tham khảo từ đâu`, `Đã xuất` ...);
(3) hai chữ khác việc thật (`Xem {} câu` mở Kịch bản, `Trên {}` là nguồn sách, `Đang làm tiếp` là tiêu đề thông báo tạm dừng).

Mục b không đổi icon nào: ba nhãn "cùng nhãn khác icon" đều là cặp khác ngữ cảnh (`Chi tiết` ở MyMusicDetails là phần thu gọn như `<details>` của web ErrorDetails, còn `info` là mục menu dự án - Qt cũng dùng `info` ở đó;
`Quay lại` xem mục "Ngoài phạm vi hai màn"; `Tạm dừng {}` web cũng dùng `Pause` ở LibraryScreen). 62 cặp "cùng icon khác nhãn": mọi nhãn Qt đều có nguyên văn trong mã web, icon đã trùng.
