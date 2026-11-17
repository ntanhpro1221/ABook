# Lệch chữ, icon và bo góc giữa web máy tính và bản Qt

Nguồn chữ hiện tại là `ui_strings/vi.json` (Kotlin/XML/TS/Qt JS/C++ sinh từ cùng kho).
Token thực thi ở `ui_design/tokens.json`, kiểm với DESIGN.md. Cổng build chung là `scripts/prepare_ui.py`.
Các gợi ý gần chữ và icon còn lại phải có giải thích exact trong `qt_wording_review.json` / `qt_icon_review.json`; gợi ý mới chưa duyệt làm build đỏ.

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Cùng nguồn chung như `docs/UI_PARITY.md` (web <-> điện thoại native): bo góc `Theme.qml` sinh bởi `desktop_qt/tools/gen_theme.py` từ DESIGN.md 5.5,
icon `LucidePaths.js` sinh bởi `scripts/gen_lucide_icons.py --qml`. Bảng dưới do `scripts/ui_parity_qt.py` sinh (`--check` báo lệch,
`tests/test_ui_parity_qt.py` chạy `--check`). Bộ đọc là heuristic trên mã nguồn: chữ dựng từ dữ liệu (tên chương, thời gian) không tính.

<!-- ui_parity_qt:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity_qt.py - không sửa tay, chạy lại script) -->

Quét: web máy tính 6228 chữ (2878 khác nhau), 350 cặp nhãn-icon; Qt 3684 chữ (2716 khác nhau), 290 cặp nhãn-icon (icon dùng ở 414 chỗ). Khoá so lỏng như UI_PARITY.md (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối); phím tắt trong chú thích Qt (`Thu nhỏ (Esc)`) tách khỏi nhãn.

## a. Cùng việc, khác chữ

Nhãn ngắn Qt không có nguyên văn (khoá lỏng) ở web máy tính mà giống một nhãn web CÙNG MÀN chưa có ở Qt. 42 cặp; mỗi nhãn Qt lấy một nhãn web giống nhất. Giống không có nghĩa là cùng việc: người sửa xem mã hai bên trước khi đổi.

Mỗi cặp còn lại phải có giải thích trong ui_strings/qt_wording_review.json; cặp mới chưa duyệt làm --check đỏ.

| màn | Qt | web | giống | nơi | giải thích |
|---|---|---|---|---|---|
| Cài đặt | Chưa lưu được mẫu{} | Chưa lưu được mẫu | 1.00 | `qt/BookTemplates.qml:28` ~ `desktop/BookTemplates.tsx:24` | Same error sentence; Qt includes the error value in one expression, web renders the detail beside the heading. |
| Cài đặt | Dùng Bluetooth cho | Dùng Bluetooth cho {} | 1.00 | `qt/OtherComputersBluetooth.qml:28` ~ `desktop/OtherComputers.tsx:359` | Same Bluetooth action; Qt renders the computer name in a separate ShortName item. |
| Cài đặt | Hết hạn sau {}:{} | Hết hạn sau | 1.00 | `qt/PhoneSyncPairing.qml:81` ~ `desktop/PhoneSync.tsx:168` | Same pairing-code expiry; Qt formats minutes and seconds in the expression, web places the clock after the label. |
| Cài đặt | Mã ghép nối: | Mã ghép nối: {} | 1.00 | `qt/PhoneSyncPairing.qml:72` ~ `desktop/PhoneSync.tsx:161` | Same pairing-code label; Qt places the six code digits in a separate text item. |
| Cài đặt | Mở Studio của | Mở Studio của {} | 1.00 | `qt/OtherComputersRow.qml:112` ~ `desktop/OtherComputers.tsx:217` | Same open-Studio action; Qt renders the computer name as another item in the row. |
| Cài đặt | Vân tay {} | Vân tay | 1.00 | `qt/OtherComputersRow.qml:99` ~ `desktop/OtherComputers.tsx:204` | Same certificate-fingerprint label; Qt appends the first fingerprint groups in one expression, web renders them as a JSX child. |
| Cài đặt | Địa chỉ: {} | Địa chỉ: | 1.00 | `qt/PhoneSyncPairing.qml:59` ~ `desktop/PhoneSync.tsx:155` | Same address label; web renders its address value as a JSX child. |
| Cài đặt | Xoá file ({}) | Xoá: {} | 0.67 | `qt/MyMusicModule.qml:188` ~ `listen/MyMusic.tsx:169` | Different controls: Qt removes the optional emotion module files; the web phrase is the accessible name of deleting an imported music track. Both actions show their own object-specific confirmation. |
| Cài đặt | Khoá | Chưa có khoá | 0.50 | `qt/ProviderKey.qml:141` ~ `listen/VoiceSettings.tsx:126` | Different roles: Qt labels the provider key input and appends its provider name; the web phrase describes an empty provider key status. |
| Studio dự án | Chưa khởi động được: {} | Chưa khởi động được: | 1.00 | `qt/ProjectScreen.qml:477` ~ `studio/ProjectScreen.tsx:198` | Same start error; web renders the error after the heading as a JSX child. |
| Studio dự án | Chưa dừng được | Chưa tải được | 0.74 | `qt/StudioStore.qml:161` ~ `studio/ProjectScreen.tsx:1374` | Different operations: Qt reports a failed stop request, the matched web text reports a failed load. Do not rename a stop failure to a load failure. |
| Studio dự án | Đang làm tiếp | Làm tiếp từ chỗ ấy | 0.52 | `qt/StudioLogic.js:228` ~ `studio/ProjectScreen.tsx:370` | Different roles: Qt status after resuming versus the web resume action. Both phrases already exist in the shared catalog. |
| Studio kịch bản | Gán cho {} | Gán cho | 1.00 | `qt/ScriptRow.qml:259` ~ `studio/ScriptTab.tsx:1127` | Same attribution action; web renders the selected speaker after the label. |
| Studio kịch bản | Đang chọn {} câu | Đang chọn | 0.82 | `qt/ScriptTab.qml:467` ~ `studio/ScriptTab.tsx:1417` | Same selection count; web uses separate TickingValue and unit children. |
| Studio kịch bản | Duyệt {} câu | Chưa có câu: {} | 0.50 | `qt/ScriptTab.qml:591` ~ `studio/ScriptTab.tsx:1405` | Different states: Qt opens review for a selected count; web is the empty result of filtering by a speaker. Not a wording pair. |
| Studio tạo sách | Tạo trên {} | Tạo trên | 1.00 | `qt/StudioSetupNotice.qml:98` ~ `studio/StudioSetup.tsx:104` | Same remote-create action; web renders the computer name as another child. |
| Studio tạo sách | Bản thử nghiệm | Bản thử nghiệm{} | 1.00 | `qt/NewProjectLogic.js:371` ~ `studio/AnalysisModelPicker.tsx:53` | Same model qualifier; web appends an optional model-description value. |
| Studio tạo sách | Có file không gửi{} | Có file không gửi | 1.00 | `qt/NewProjectStore.qml:273` ~ `studio/NewProjectScreen.tsx:312` | Same upload warning; Qt appends a detail list in the expression, web uses a separate child. |
| Studio tạo sách | Không gửi hết các chương{} {} | Không gửi hết các chương | 1.00 | `qt/NewProjectStore.qml:316` ~ `studio/NewProjectScreen.tsx:319` | Same upload warning; the two Qt slots are file count and detail, rendered separately on web. |
| Studio tạo sách | Máy thấy {} | Máy thấy | 1.00 | `qt/NewVolumes.qml:58` ~ `studio/VolumeSplit.tsx:101` | Same volume-detection sentence; web renders the count/source after the label. |
| Studio tạo sách | Studio chưa xong{} | Studio chưa xong | 1.00 | `qt/StudioSetupCard.qml:28` ~ `studio/StudioSetup.tsx:162` | Same setup status; Qt appends optional details in the expression. |
| Studio tạo sách | Tách theo {} | Tách theo | 1.00 | `qt/NewHints.qml:88` ~ `studio/NewProjectScreen.tsx:878` | Same chapter-split description; web renders the chosen rule after the label. |
| Studio tạo sách | Đã có mẫu “{}” | Đã có mẫu “ | 1.00 | `qt/TemplateLogic.js:52` ~ `studio/TemplateBar.tsx:171` | Same duplicate-template error; web renders the user-entered template name between JSX quote fragments. |
| Studio tạo sách | Máy này {}. | Máy thấy | 0.80 | `qt/StudioSetupLogic.js:17` ~ `studio/VolumeSplit.tsx:101` | Different subjects: Qt describes machine setup/capability, the matched web text describes detected book volumes. |
| Studio việc duyệt | Bỏ qua mọi việc từ | Bỏ qua mọi việc từ {}? | 1.00 | `qt/PhoneEdits.qml:154` ~ `studio/PhoneEdits.tsx:246` | Same destructive-confirmation question; Qt places the phone name and question mark in separate children. |
| Studio việc duyệt | Dùng “{}” | Dùng “ | 1.00 | `qt/ReadingProblem.qml:40` ~ `studio/ReadingProblem.tsx:27` | Same use-reading action; web renders the reading value between separate JSX quote fragments. |
| Studio việc duyệt | Máy nghe ra: “{}” | Máy nghe ra: “ | 1.00 | `qt/ReviewLogic.js:42` ~ `studio/ReviewQueue.tsx:223` | Same ASR transcript caption; web renders the transcript as another child. |
| Studio việc duyệt | Mọi việc đã có quyết định | Mọi việc đã có quyết định{}. | 1.00 | `qt/WorkLogic.js:280` ~ `studio/WorkInbox.tsx:1300` | Same completed-review state; web appends an optional pending-change count. |
| Studio việc duyệt | Sẽ đọc là “{}” | Sẽ đọc là “ | 1.00 | `qt/ReviewLogic.js:47` ~ `studio/ReviewQueue.tsx:231` | Same proposed-reading caption; web renders the reading as another child. |
| Studio việc duyệt | Đã dùng | Dùng “ | 1.00 | `qt/WorkStore.qml:325` ~ `studio/ReadingProblem.tsx:27` | Different states: Qt past-tense confirmation after saving, the matched web phrase is the action to use a proposed reading. |
| Studio việc duyệt | Đúng rồi, giữ “{}” | Đúng rồi, giữ “ | 1.00 | `qt/WorkPronunciation.qml:35` ~ `studio/WorkInbox.tsx:381` | Same keep-reading action; web renders the reading between separate JSX quote fragments. |
| Studio việc duyệt | Đoạn này do | Đoạn này do {} kể | 0.88 | `qt/WorkLogic.js:50` ~ `studio/workText.ts:23` | Same narrator-result sentence; Qt composes prefix, narrator and suffix from separate catalog keys. |
| Studio việc duyệt | Tải tiếp · còn | Tải tiếp · còn {} câu | 0.86 | `qt/ReviewLogic.js:60` ~ `studio/ReviewQueue.tsx:499` | Same review pagination; Qt renders remaining count and unit in separate items. |
| Studio việc duyệt | Nghe liền {} câu | Nghe liền | 0.82 | `qt/ReviewQueue.qml:254` ~ `studio/ReviewQueue.tsx:453` | Same continuous-listening action; web renders the count in a separate child. |
| Studio việc duyệt | Xem {} câu | Sửa {} câu | 0.57 | `qt/WorkSpeaker.qml:237` ~ `studio/reviewText.ts:21` | Different actions: Qt opens read-only context, the matched web label opens an editor for repeated lines. |
| Studio xuất và áp dụng | Cỡ ước tính: khoảng {} | Cỡ ước tính: khoảng | 1.00 | `qt/ExportBook.qml:244` ~ `studio/ExportBook.tsx:527` | Same export-size estimate; web renders the size in a separate child. |
| Studio xuất và áp dụng | Xuất “ | Xuất “{}” | 1.00 | `qt/ExportBook.qml:58` ~ `studio/ExportBook.tsx:395` | Same export heading; Qt renders the title and closing quote in separate items. |
| Studio xuất và áp dụng | Đang thêm chữ sáng… {} | Đang thêm chữ sáng… {}% | 1.00 | `qt/ExportLogic.js:259` ~ `studio/WordTimings.tsx:43` | Same catalog key as web (s_dang_them_chu_sang_0); the Qt reader renders the slotted call as {} without the catalog's percent sign. |
| Studio xuất và áp dụng | Đã xuất | Xuất “{}” | 0.73 | `qt/ExportLogic.js:112` ~ `studio/ExportBook.tsx:395` | Different states: Qt completed-export confirmation, matched web text is an export-dialog heading. |
| Thanh phát | Nghe bằng giọng đọc. | Nghe bằng giọng đọc.{} | 1.00 | `qt/PlayerLabels.js:18` ~ `listen/labels.ts:149` | Same sentence; web appends an optional platform-specific pointer/editing hint. |
| Trang sách | Lần nghe | Lần nghe {} | 1.00 | `qt/RecordLogic.js:10` ~ `listen/BookScreen.tsx:720` | Same listening-record name prefix; Qt renders the record number separately. |
| Trang sách | Hồ sơ nghe: {} | Đã nghe {} | 0.59 | `qt/RecordChip.qml:14` ~ `listen/BookScreen.tsx:1196` | Different data: Qt accessibility name for a listening profile, the matched web label is listening progress. |

## b. Cùng nhãn khác icon, cùng icon khác nhãn

**Cùng nhãn, khác icon** (4 nhãn Qt có icon mà icon ấy không đi với nhãn này ở bất cứ đâu trên web máy tính):

| nhãn | web | Qt | nơi | giải thích |
|---|---|---|---|---|
| Bắt đầu | headphones | wand-sparkles | `qt/NewProjectScreen.qml:185` ~ `desktop/AudiobookDialog.tsx:216` | Different operations: Qt starts a Studio production job (wand-sparkles); the matched web dialog starts a read-aloud export (headphones). |
| Chi tiết | info | chevron-right | `qt/MyMusicDetails.qml:29` (+1) ~ `studio/ProjectScreen.tsx:757` | Different controls: Qt rotates a disclosure chevron to expand the music details; the matched web item opens project information. |
| Quay lại | chevron-left | arrow-left | `qt/ScreenHeader.qml:14` (+1) ~ `listen/LineWishes.tsx:224` (+2) | Different navigation depth: the web chevron returns one step inside a sentence editor; the Qt arrow returns to the previous screen. |
| Tạm dừng {} | check, circle-dashed, play | pause | `qt/BookCell.qml:87` ~ `listen/BookScreen.tsx:187` (+3) | Scanner pairing ambiguity: the web book row has status check/circle icons beside its transport action. Its actual pause action and the Qt book cell use pause. |

**Cùng icon, khác nhãn** (67 cặp Qt; web cùng màn dùng cùng icon với nhãn khác):

| màn | icon | Qt | web cùng màn | nơi |
|---|---|---|---|---|
| Thêm sách | copy | Thêm bản riêng | Thêm bản riêng / Vẫn thêm bản mới | `qt/AddBook.qml:458` |
| Thêm sách | copy | Vẫn thêm bản mới | Thêm bản riêng / Vẫn thêm bản mới | `qt/AddBook.qml:458` |
| Thêm sách | file-text | Chọn file sách | Đang đọc / Chọn file sách | `qt/AddBook.qml:551` |
| Thêm sách | file-text | Đang đọc | Đang đọc / Chọn file sách | `qt/AddBook.qml:551` |
| Cài đặt | download | Cập nhật ABook | Cài Studio, Cài tiếp, Có ABook {} | `qt/AdvancedUpdate.qml:96` |
| Cài đặt | download | Đang tải bản mới | Cài Studio, Cài tiếp, Có ABook {} | `qt/AdvancedUpdate.qml:96` |
| Thư viện | play | Nghe ngay {} | Đọc {} | `qt/BookCell.qml:87` |
| Thư viện | play | Nghe {} | Đọc {} | `qt/BookCell.qml:87` |
| Thư viện | pause | Tạm dừng {} | Đọc {} | `qt/BookCell.qml:87` |
| Trang sách | check-check | Chưa nghe xong | Chưa nghe / Đã nghe xong, Chưa nghe xong / Đã nghe xong | `qt/BookPage.qml:173` |
| Trang sách | check-check | Đã nghe xong | Chưa nghe / Đã nghe xong, Chưa nghe xong / Đã nghe xong | `qt/BookPage.qml:173` |
| Trang sách | circle-dashed | Chưa nghe | Chưa nghe / Đã nghe xong, Tạm dừng {} | `qt/BookPage.qml:304` |
| Trang sách | check-check | Đã nghe xong | Chưa nghe / Đã nghe xong, Chưa nghe xong / Đã nghe xong | `qt/BookPage.qml:304` |
| Trang sách | git-merge | Gộp | Gộp vào người khác | `qt/CastMerge.qml:163` |
| Đang nghe | play | Nghe từ đầu chương | Dừng / Nghe thử, Nghe {} | `qt/ChapterList.qml:45` |
| Đang nghe | book-open | Đọc chương này | Trang sách | `qt/ChapterList.qml:46` |
| Studio tạo sách | image-plus | Chọn ảnh | Đổi ảnh bìa | `qt/CoverEditor.qml:146` |
| Studio tạo sách | image-plus | Đổi bìa | Đổi ảnh bìa | `qt/CoverEditor.qml:146` |
| Studio tạo sách | image-plus | Đặt ảnh bìa | Đổi ảnh bìa | `qt/CoverEditor.qml:155` |
| Studio tạo sách | trash | Bỏ ảnh bìa | Bỏ chương {}, Bỏ cắt trước {}, Dùng bìa vẽ | `qt/CoverEditor.qml:182` |
| Sửa sách | image-plus | Chọn ảnh bìa | Đổi ảnh bìa / Chọn ảnh bìa | `qt/EditBook.qml:248` |
| Sửa sách | image-plus | Đổi ảnh bìa | Đổi ảnh bìa / Chọn ảnh bìa | `qt/EditBook.qml:248` |
| Sửa sách | file-down | Lưu thành | Lưu | `qt/EditBookItems.qml:82` |
| Sửa sách | trash | Bỏ cách đọc {} | Bỏ ảnh bìa | `qt/EditBookReadings.qml:124` |
| Thêm sách | book-plus | Thả để thêm sách | Thêm vào thư viện | `qt/ImportDrop.qml:49` |
| Thư viện | play | Nghe tiếp | Đọc {} | `qt/LibraryContinue.qml:46` |
| Thư viện | pause | Tạm dừng | Đọc {} | `qt/LibraryContinue.qml:46` |
| Thư viện | x | Đóng ô tìm | Xoá ô tìm | `qt/LibraryScreen.qml:212` |
| Thư viện | search | Chưa có cuốn nào nghe xong. | Thử tên sách hoặc tác giả khác., Tìm sách | `qt/LibraryScreen.qml:519` |
| Nhạc | square | Dừng nghe | Dừng nghe thử, Dừng tải | `qt/MusicScreen.qml:252` |
| Nhạc | download | Tải tiếp | Lưu tất cả ({}), Tải cả danh sách ({}), Tải tiếp / Tải về | `qt/MusicTrackDetail.qml:106` |
| Nhạc | download | Tải về | Lưu tất cả ({}), Tải cả danh sách ({}), Tải tiếp / Tải về | `qt/MusicTrackDetail.qml:106` |
| Nhạc | download | Dừng tải | Lưu tất cả ({}), Tải cả danh sách ({}), Tải tiếp / Tải về | `qt/MusicTrackRow.qml:103` |
| Nhạc | download | Thử lại | Lưu tất cả ({}), Tải cả danh sách ({}), Tải tiếp / Tải về | `qt/MusicTrackRow.qml:103` |
| Nhạc | download | Tải về | Lưu tất cả ({}), Tải cả danh sách ({}), Tải tiếp / Tải về | `qt/MusicTrackRow.qml:103` |
| Nhạc | download | Đã tải, xoá | Lưu tất cả ({}), Tải cả danh sách ({}), Tải tiếp / Tải về | `qt/MusicTrackRow.qml:103` |
| Cài đặt | upload | Đang thêm {}/{} | Thêm nhạc của bạn | `qt/MyMusicSettings.qml:146` |
| Studio tạo sách | layers | Phần | Chia thành nhiều phần, Chia thành {} phần / Chia thành mấy phần? | `qt/NewChapters.qml:204` |
| Studio tạo sách | layers | Chọn {} tập | Chia thành nhiều phần, Chia thành {} phần / Chia thành mấy phần? | `qt/NewDrop.qml:211` |
| Studio tạo sách | scissors | Tách thành {} chương | Tách thành chương | `qt/NewHints.qml:94` |
| Studio tạo sách | wand-sparkles | Bắt đầu | Bắt đầu / Tạo sách | `qt/NewProjectScreen.qml:185` |
| Đang nghe | moon | Hẹn giờ | {} trên {} | `qt/NowPlaying.qml:440` |
| Đang nghe | moon | Hết chương | {} trên {} | `qt/NowPlaying.qml:440` |
| Cài đặt | bluetooth | Dùng Bluetooth | Dùng Bluetooth cho {}, · bản thử | `qt/OtherComputersBluetooth.qml:23` |
| Cài đặt | refresh-cw | Làm mới | Hỏi lại, Hỏi lại thư viện | `qt/PhoneDiagnostics.qml:68` |
| Cài đặt | save | Lưu nhật ký | Gửi nhật ký | `qt/PhoneDiagnostics.qml:69` |
| Đọc theo | user-round | Ai nói câu này | Ai nghĩ câu này | `qt/PlayerLineEditor.qml:133` |
| Studio dự án | ellipsis | Thêm tuỳ chọn | Thêm tuỳ chọn Studio, Thêm tuỳ chọn: {} | `qt/ProjectScreen.qml:333` |
| Studio dự án | circle-alert | Chưa khởi động được: {} | Chưa mở được sách, Cuốn này đã bị xoá hoặc chuyển đi khỏi thư … | `qt/ProjectScreen.qml:473` |
| Studio việc duyệt | list-music | Nghe liền {} câu | Nghe liền câu | `qt/ReviewQueue.qml:253` |
| Studio việc duyệt | rotate-ccw | Cần thu lại | Cần thu lại / Thu lại câu này, Hoàn tác, Khôi phục tất cả | `qt/ReviewRow.qml:282` |
| Studio việc duyệt | rotate-ccw | Thu lại câu này | Cần thu lại / Thu lại câu này, Hoàn tác, Khôi phục tất cả | `qt/ReviewRow.qml:282` |
| Studio kịch bản | refresh-cw | Thu lại | Thu lại câu: {}, Thu lại {} câu / Chưa có bản thu | `qt/ScriptRow.qml:311` |
| Studio kịch bản | refresh-cw | Chưa có bản thu | Thu lại câu: {}, Thu lại {} câu / Chưa có bản thu | `qt/ScriptTab.qml:485` |
| Studio kịch bản | refresh-cw | Thu lại {} câu | Thu lại câu: {}, Thu lại {} câu / Chưa có bản thu | `qt/ScriptTab.qml:485` |
| Studio kịch bản | check | Duyệt {} câu | Duyệt câu | `qt/ScriptTab.qml:589` |
| Cài đặt | trash | Gỡ Studio | Bỏ cách đọc “{}”, Xoá, Xoá khoá | `qt/StudioSettings.qml:124` |
| Cài đặt | trash | Xác nhận gỡ | Bỏ cách đọc “{}”, Xoá, Xoá khoá | `qt/StudioSettings.qml:124` |
| Cài đặt | trash | Đang gỡ | Bỏ cách đọc “{}”, Xoá, Xoá khoá | `qt/StudioSettings.qml:124` |
| Studio tạo sách | clapperboard | Tạo trên {} | Tạo trên | `qt/StudioSetupNotice.qml:99` |
| Studio việc duyệt | pause | Dừng | Dừng / Nghe thử | `qt/TryButton.qml:12` |
| Studio việc duyệt | volume-2 | Nghe thử | Dừng / Nghe thử | `qt/TryButton.qml:12` |
| Cài đặt | play | Nghe thử | Dừng / Nghe thử | `qt/VoiceRow.qml:106` |
| Studio việc duyệt | check | Giữ {} thẻ | Giữ cả thẻ, Giữ thẻ, Giữ “{}” - không cần áp dụng. / Đã ghi “{}”… | `qt/WorkBulkKeep.qml:26` |
| Studio việc duyệt | user-plus | Người khác | Người kể khác, Đặt tên / Người khác | `qt/WorkSpeaker.qml:215` |
| Studio việc duyệt | user-plus | Đặt tên | Người kể khác, Đặt tên / Người khác | `qt/WorkSpeaker.qml:215` |
| Studio việc duyệt | search | Xem {} câu | Tìm người khác, Xem câu | `qt/WorkSpeaker.qml:236` |

Số cặp: web máy tính 307, Qt 254. Nhãn Qt có icon (199): `Ai nghĩ câu này`, `Ai nói câu này`, `Bài nhạc`, `Bấm để cập nhật`, `Bấm để đổi tên chương`, `Bật tiếng`, `Bắt đầu`, `Bỏ chương này`, `Bỏ cách đọc {}`, `Bỏ cách đọc “{}”`, `Bỏ ghép`, `Bỏ qua tất cả`, `Bỏ qua việc này`, `Bỏ ảnh bìa`, `Chi tiết`, `Chia thành nhiều phần`, `Chưa có bản thu`, `Chưa có cuốn nào nghe xong.`, `Chưa khởi động được: {}`, `Chưa nghe`, `Chưa nghe xong`, `Chương`, `Chương sau`, `Chương sau chưa có audio`, `Chương trước`, `Chẩn đoán`, `Chọn`, `Chọn file`, `Chọn file sách`, `Chọn lại nhạc`, `Chọn người`, `Chọn thư mục`, `Chọn thư mục TXT`, `Chọn từng file`, `Chọn {} tập`, `Chọn ảnh`, `Chọn ảnh bìa`, `Cài Studio`, `Cài đặt`, `Cách đọc câu`, `Có ABook`, `Cần thu lại`, `Cập nhật ABook`, `Cửa sổ mini`, `Duyệt {} câu`, `Dùng Bluetooth`, `Dùng {} cách đọc chung`, `Dừng`, `Dừng nghe`, `Dừng nghe liền`, `Dừng tải`, `Dự án mới`, `Ghim trên cùng`, `Ghép thiết bị mới`, `Giảm`, `Giọng {} đang không dùng được.`, `Giọng đọc`, `Giữ {} thẻ`, `Gộp`, `Gộp vào người khác`, `Gộp vào phần trước`, `Gỡ Studio`, `Gợi ý đọc`, `Gửi nhật ký`, `Hoàn tác`, `Huỷ tải`, `Hẹn giờ`, `Hết chương`, `Hỏi lại thư viện`, `Khôi phục tất cả`, `Khôi phục việc này`, `Không có mạng -`, `Khởi động lại`, `Kiểm tra`, `Làm mới`, `Lưu`, `Lưu nhật ký`, `Lưu thay đổi`, `Lưu thành`, `Lưu thành mẫu`, `Lưu tất cả ({})`, `Mở cuốn đó`, `Mở file sách`, `Mở Kịch bản`, `Mở rộng`, `Mở Studio`, `Mở tab Nhạc nền`, `Mở thư mục`, `Mở thư mục nhật ký`, `Mở trình phát`, `Nghe liền {} câu`, `Nghe lại`, `Nghe ngay {}`, `Nghe thử`, `Nghe tiếp`, `Nghe từ đầu chương`, `Nghe {}`, `Người khác`, `Người kể khác`, `Nhạc`, `Nhạc nền`, `Nên dùng`, `Phát`, `Phát trên`, `Phím tắt`, `Phần`, `Quay lại`, `Quyết định riêng`, `Studio`, `Sửa cách đọc {}`, `Sửa sách`, `Sửa thông tin`, `Thu gọn`, `Thu lại`, `Thu lại câu này`, `Thu lại {} câu`, `Thu nhỏ`, `Thêm`, `Thêm bản riêng`, `Thêm cách đọc`, `Thêm file`, `Thêm nhạc của bạn`, `Thêm sách`, `Thêm tuỳ chọn`, `Thêm tuỳ chọn Studio`, `Thêm tuỳ chọn: {}`, `Thêm vào thư viện`, `Thư viện`, `Thả để thêm sách`, `Thử lại`, `Trang sách`, `Tách thành {} chương`, `Tìm`, `Tìm bìa`, `Tìm bìa trên mạng`, `Tìm người khác`, `Tìm sách`, `Tăng`, `Tạm dừng`, `Tạm dừng {}`, `Tạo sách nói`, `Tạo trên {}`, `Tạo âm sắc`, `Tải cả danh sách ({})`, `Tải thêm (3,2 GB)`, `Tải tiếp`, `Tải về`, `Tắt tiếng`, `Tới câu đang nghe`, `Tự tìm`, `Vẫn cài`, `Vẫn thêm bản mới`, `Về chỗ vừa nghe`, `Về Cài đặt`, `Về màn trước`, `Về Studio`, `Về Thư viện`, `Xem tất cả`, `Xem {} câu`, `Xoá`, `Xoá bản tải`, `Xoá khoá`, `Xoá ô tìm`, `Xác nhận gỡ`, `Xếp theo`, `Áp dụng trước`, `Áp dụng tất cả`, `Áp dụng việc này`, `Âm thanh`, `Đang chọn lại`, `Đang gỡ`, `Đang mở`, `Đang thêm {}/{}`, `Đang tải bản mới`, `Đang đệm`, `Đang đọc`, `Đang đọc không khí`, `Đang đổi`, `Đây là chương cuối`, `Đã nghe xong`, `Đã tải, xoá`, `Đóng`, `Đóng lời báo`, `Đóng trình phát`, `Đóng ô tìm`, `Đặt tên`, `Đặt ảnh bìa`, `Đọc chương này`, `Đọc lại ngữ cảnh`, `Đọc {}`, `Đổi bài`, `Đổi bìa`, `Đổi giọng người kể`, `Đổi giọng {}`, `Đổi giới tính`, `Đổi tên`, `Đổi tên chương`, `Đổi ảnh bìa`, `Ổn`.

## c. Nhãn chỉ có một bên, theo màn

Nhãn ngắn (<= 6 chữ). **Chỉ Qt**: không có ở web cùng màn; `*` = web có ở màn khác. **Chỉ web**: nhãn web của màn không có ở đâu trong Qt - phần lớn là tính năng Qt chưa làm (bản thử), chỉ đếm và kể 15 đầu.

### Lịch sử phân vai

- chỉ Qt (0): (không có)
- chỉ web (0): (không có)

### Âm thanh

- chỉ Qt (4): Tắt* (`qt/AudioFxPanel.qml:14`); Tự chỉnh (chưa lưu)* (`qt/AudioFxPanel.qml:14`); Âm thanh* (`qt/AudioFxPanel.qml:51`); Chọn nhạc* (`qt/AudioFxPanel.qml:66`)
- chỉ web (3): 1 kHz (`22`); 250 Hz (`22`); Kéo để sắp xếp (`66`)

### Khay và cửa sổ mini

- chỉ Qt (13): Ghim trên cùng (`qt/MiniPlayer.qml:54`); Mở rộng (`qt/MiniPlayer.qml:60`); Lùi {} giây* (`qt/MiniPlayer.qml:89`); Phát* (`qt/MiniPlayer.qml:90`); Tạm dừng* (`qt/MiniPlayer.qml:90`); Đang đệm* (`qt/MiniPlayer.qml:90`); Phát trên* (`qt/MiniPlayer.qml:91`); Tới {} giây* (`qt/MiniPlayer.qml:92`); Chương sau* (`qt/TrayMenuModel.qml:14`); Chương trước* (`qt/TrayMenuModel.qml:14`); Cửa sổ mini (`qt/TrayMenuModel.qml:14`); Mở ABook (`qt/TrayMenuModel.qml:14`); Thoát ABook (`qt/TrayMenuModel.qml:14`)
- chỉ web (0): (không có)

### Nhạc

- chỉ Qt (2): Dừng nghe (`qt/MusicScreen.qml:252`); Đã tải, xoá (`qt/MusicTrackRow.qml:107`)
- chỉ web (1): Nhanh (`100`)

### Thư viện

- chỉ Qt (9): Tạm dừng* (`qt/LibraryContinue.qml:44`); Mới thêm* (`qt/LibraryScreen.qml:48`); Tác giả* (`qt/LibraryScreen.qml:48`); Tên sách* (`qt/LibraryScreen.qml:48`); Đang mở ABook* (`qt/LibraryScreen.qml:416`); Chưa mở được ABook (`qt/LibraryScreen.qml:465`); Chưa tải được thư viện (`qt/LibraryScreen.qml:465`); Thử lại* (`qt/LibraryScreen.qml:483`); Không thấy “{}”* (`qt/LibraryScreen.qml:520`)
- chỉ web (7): Đang tạm dừng {} (`334`); Đang làm {} (`335`); Đang tạm dừng{} (`339`); Chưa có chương nghe được{} (`341`); Đang làm · {} (`341`); Thư viện chưa có sách nào. (`462`); Chữ bìa trên hoạ tiết sóng (`86`)

### Thanh phát

- chỉ Qt (11): Không có mạng - (`qt/PlayerAlert.qml:10`); Giọng {} đang không dùng được.* (`qt/PlayerAlert.qml:25`); Cửa sổ mini (`qt/PlayerBar.qml:128`); Chỉnh* (`qt/PlayerBar.qml:156`); Âm thanh* (`qt/PlayerBar.qml:156`); Hẹn giờ* (`qt/PlayerBar.qml:157`); Giọng đọc* (`qt/PlayerBar.qml:160`); Hẹn lại {} phút* (`qt/PlayerFade.qml:16`); Nghe bằng giọng đọc. (`qt/PlayerLabels.js:18`); Thêm giọng* (`qt/PlayerVoicePopover.qml:31`); Tua nhạc (`qt/SeekBar.qml:29`)
- chỉ web (8): Shift+← (`284`); Sắp tắt · (`1267`); Chưa nghe · {} chương (`69`); Nghe tiếp · {} (`88`); Shift+→ (`106`); Chưa có audio (`116`); Chạm (`127`); Nghe bằng giọng đọc.{} (`149`)

### Đang nghe

- chỉ Qt (20): Tạm dừng {}* (`qt/ChapterList.qml:27`); Đọc {}* (`qt/ChapterList.qml:27`); Đọc chương này* (`qt/ChapterList.qml:46`); Đọc* (`qt/ChapterReader.qml:15`); Chưa có chương để đọc. (`qt/ChapterReader.qml:35`); Đang tải chương (`qt/ChapterReader.qml:89`); Đã nghe* (`qt/ChapterRow.qml:76`); Thêm tuỳ chọn: {}* (`qt/ChapterRow.qml:127`); Thêm tuỳ chọn* (`qt/NowPlaying.qml:241`); Giọng {}* (`qt/NowPlaying.qml:297`); Thử lại* (`qt/NowPlaying.qml:341`); Danh sách chương* (`qt/NowPlaying.qml:463`); Nhạc nền* (`qt/NowPlaying.qml:474`); Chỉnh* (`qt/NowPlaying.qml:611`); Âm thanh* (`qt/NowPlaying.qml:611`); Cửa sổ mini (`qt/NowPlaying.qml:620`); Gợi ý phần đọc* (`qt/ReadingSuggestions.qml:9`); Bỏ dòng (`qt/ReadingSuggestions.qml:57`); Đóng* (`qt/ReadingSuggestions.qml:80`); Số chương* (`qt/SleepPopover.qml:98`)
- chỉ web (17): Shift+← (`284`); Đã chọn tốc độ đọc {} (`519`); Phím (`522`); Đã chọn giọng {} (`786`); Hẹn giờ đã tắt tiếng lúc (`981`); Bật lại (`989`); Tiếng nhỏ dần (`995`); Hẹn giờ ngủ trên {} (`1069`); Về chế độ nghe (`2137`); Chưa nghe · {} chương (`69`); Nghe tiếp · {} (`88`); Shift+→ (`106`); Chưa có audio (`116`); Chạm (`127`); Nghe bằng giọng đọc.{} (`149`); ...

### Đọc theo

- chỉ Qt (2): Đang tải kịch bản* (`qt/PlayerLineEditor.qml:115`); Đang mở văn bản chương (`qt/ReadAlongView.qml:480`)
- chỉ web (12): Người nói: {} (`101`); Cách đọc câu - {} (`104`); Các từ trong câu (`165`); Cách đọc “{}”: “{}” (`398`); Đọc từ này là (`400`); Đang chờ máy làm sách (`418`); Sửa cách đọc “{}” (`424`); Bỏ: {} (`437`); Sửa cách đọc từ (`491`); Đang tải chữ (`1752`); Nghe từ “{}” (`59`); Shift F10: sửa cách đọc. (`423`)

### Trang sách

- chỉ Qt (64): Chưa tải được giọng* (`qt/CastEngine.qml:72`); Tải giọng* (`qt/CastEngine.qml:80`); Chưa huỷ được việc tải giọng* (`qt/CastEngine.qml:116`); Giới tính của {}* (`qt/CastGender.qml:17`); Hiện đang là nhân vật {}.* (`qt/CastGender.qml:18`); Chưa đổi được giới tính* (`qt/CastGender.qml:26`); Giới tính* (`qt/CastGender.qml:48`); Nữ* (`qt/CastGender.qml:50`); Nếu giọng* (`qt/CastGender.qml:67`); Ghi lại* (`qt/CastGender.qml:83`); Thôi* (`qt/CastGender.qml:83`); Đang tải nhân vật (`qt/CastList.qml:97`); Gộp nhân vật* (`qt/CastMerge.qml:18`); Chưa gộp được* (`qt/CastMerge.qml:29`); Đã ghi:* (`qt/CastMerge.qml:29`); Tìm người trong truyện* (`qt/CastMerge.qml:51`); Gộp vào ai* (`qt/CastMerge.qml:68`); Không có ai khớp “{}”. (`qt/CastMerge.qml:137`); Gộp* (`qt/CastMerge.qml:159`); Chưa hoàn tác được* (`qt/CastModal.qml:24`); Hoàn tác* (`qt/CastModal.qml:24`); Đã hoàn tác* (`qt/CastModal.qml:24`); Đã hoàn tác. {} (`qt/CastModal.qml:24`); Bỏ gộp {} vào {} (`qt/CastPerson.qml:120`); Đổi tên {}* (`qt/CastRename.qml:14`); Chưa đổi được tên* (`qt/CastRename.qml:26`); Đã trở về tên gốc: {}* (`qt/CastRename.qml:26`); Đã đổi tên thành {}* (`qt/CastRename.qml:26`); Tên mới của {}* (`qt/CastRename.qml:48`); Tên gốc:* (`qt/CastRename.qml:58`); Về tên gốc* (`qt/CastRename.qml:64`); Chưa bỏ gộp được* (`qt/CastUnmerge.qml:14`); Đã bỏ gộp {}* (`qt/CastUnmerge.qml:14`); Chưa đổi được giọng* (`qt/CastVoice.qml:70`); Giọng (`qt/CastVoice.qml:70`); Chưa bỏ được lựa chọn* (`qt/CastVoice.qml:89`); Đã bỏ lựa chọn giọng* (`qt/CastVoice.qml:89`); Đã bỏ lựa chọn {}* (`qt/CastVoice.qml:89`); Đang tải giọng đọc* (`qt/CastVoice.qml:117`); Chờ áp dụng: đổi sang* (`qt/CastVoice.qml:151`); Giữ* (`qt/CastVoice.qml:158`); Giữ như cũ* (`qt/CastVoice.qml:198`); Lọc giọng theo giới* (`qt/CastVoice.qml:205`); Tất cả* (`qt/CastVoice.qml:207`); Đang dùng* (`qt/CastVoice.qml:328`); Máy gợi ý* (`qt/CastVoice.qml:342`); Giữ giọng này* (`qt/CastVoice.qml:365`); Dùng chung giọng* (`qt/CastVoice.qml:386`); Tìm hiểu thêm* (`qt/CastVoice.qml:386`); Thử lại* (`qt/Clip.qml:18`); Mạng chậm, thử nghe lại. (`qt/Clip.qml:61`); Chưa nghe thử được lúc này.* (`qt/Clip.qml:72`); Đang tải lịch sử (`qt/HistoryList.qml:62`); Chủ Nhật (`qt/HistoryLogic.js:10`); Thứ Ba (`qt/HistoryLogic.js:10`); Thứ Bảy (`qt/HistoryLogic.js:10`); Thứ Hai (`qt/HistoryLogic.js:10`); Thứ Năm (`qt/HistoryLogic.js:10`); Thứ Sáu (`qt/HistoryLogic.js:10`); Thứ Tư (`qt/HistoryLogic.js:10`); Hồ sơ nghe: {} (`qt/RecordChip.qml:14`); Lần nghe (`qt/RecordLogic.js:10`); Đổi tên hồ sơ này (`qt/RecordLogic.js:39`); Hồ sơ mới “ (`qt/RecordLogic.js:104`)
- chỉ web (13): Đã làm sẵn (`212`); Tách {} khỏi {} (`471`); Chờ áp dụng: giọng (`578`); Nghe tiếp từ (`697`); Lần nghe {} (`720`); Chia sẻ (`1267`); Đã nghe {} {} · {} (`37`); Chưa nghe · {} chương (`69`); Nghe tiếp · {} (`88`); Shift+→ (`106`); Chưa có audio (`116`); Chạm (`127`); Nghe bằng giọng đọc.{} (`149`)

### Cài đặt

- chỉ Qt (113): Chưa làm được lúc này. (`qt/BookTemplates.qml:28`); Chưa lưu được mẫu{} (`qt/BookTemplates.qml:28`); Chưa kết nối* (`qt/DevicesLogic.js:62`); Đang nối qua Bluetooth* (`qt/DevicesLogic.js:64`); Đang nối qua Tailscale* (`qt/DevicesLogic.js:69`); Đang nối qua Wi-Fi nhà* (`qt/DevicesLogic.js:70`); Đang nối qua mạng* (`qt/DevicesLogic.js:72`); Gửi trước rồi bỏ ghép* (`qt/DevicesLogic.js:109`); Thử gửi trước rồi bỏ ghép* (`qt/DevicesLogic.js:111`); Vẫn bỏ ghép, bỏ thay đổi* (`qt/DevicesLogic.js:115`); Tải sách* (`qt/DevicesLogic.js:140`); Xuất M4B* (`qt/DevicesLogic.js:140`); Xuất MP3* (`qt/DevicesLogic.js:140`); Xuất sách nói* (`qt/DevicesLogic.js:140`); Việc nền* (`qt/DevicesLogic.js:149`); Việc* (`qt/DevicesLogic.js:150`); Bản ABook* (`qt/DevicesLogic.js:176`); Giờ trên máy* (`qt/DevicesLogic.js:184`); Mạng* (`qt/DevicesLogic.js:192`); Chỗ trống* (`qt/DevicesLogic.js:198`); Thông báo* (`qt/DevicesLogic.js:202`); Chạy nền* (`qt/DevicesLogic.js:203`); Đang nghe* (`qt/DevicesLogic.js:207`); Cho máy khác nghe thư viện* (`qt/DevicesLogic.js:219`); Lần tắt gần nhất* (`qt/DevicesLogic.js:223`); Lần văng* (`qt/DevicesLogic.js:227`); Phục hồi dữ liệu* (`qt/DevicesLogic.js:228`); Chưa có dòng nào.* (`qt/DevicesLogic.js:242`); Đang tải* (`qt/DevicesSkeleton.qml:9`); Chưa lưu được cài đặt{} (`qt/ListenSave.qml:11`); Phím một chữ cái đang tắt (`qt/LookShortcuts.qml:12`); Cửa sổ mini (`qt/LookShortcuts.qml:15`); Tải lại ({}) (`qt/MyMusicModule.qml:35`); Bật đo cảm xúc (`qt/MyMusicModule.qml:39`); Tải tiếp ({}) (`qt/MyMusicModule.qml:39`); Tắt đo cảm xúc (`qt/MyMusicModule.qml:39`); Phân tích nhạc (`qt/MyMusicModule.qml:75`); Tải Phân tích nhạc (`qt/MyMusicModule.qml:92`); Cảm xúc chính xác (`qt/MyMusicModule.qml:148`); Xoá file ({}) (`qt/MyMusicModule.qml:188`); Chưa đổi được* (`qt/MyMusicSettings.qml:96`); Chọn nhạc của bạn (`qt/MyMusicSettings.qml:120`); Đang phân tích nhạc đã thêm (`qt/MyMusicText.js:32`); Đang nghe kỹ bài vừa thêm (`qt/MyMusicText.js:64`); Chạy (`qt/MyMusicText.js:68`); Tự chọn (`qt/MyMusicText.js:80`); Chưa phân tích (`qt/MyMusicText.js:81`); Có lời* (`qt/MyMusicText.js:89`); Hợp không khí đoạn này (`qt/MyMusicText.js:92`); Không tự chọn* (`qt/MyMusicText.js:92`); Chưa thêm được nhạc* (`qt/MyMusicText.js:116`); Đã thêm: {} (`qt/MyMusicText.js:121`); Chưa có bản đọc đã lưu.* (`qt/MyMusicText.js:131`); Ghi chú cho người bảo trì* (`qt/MyMusicText.js:147`); Phát* (`qt/MyMusicTrack.qml:77`); Tạm dừng* (`qt/MyMusicTrack.qml:77`); Đang đệm* (`qt/MyMusicTrack.qml:77`); Chất lượng cao* (`qt/NewBookDefaults.qml:12`); Cân bằng* (`qt/NewBookDefaults.qml:12`); Kết nối Wi-Fi* (`qt/OtherComputers.qml:38`); Chưa bỏ ghép được* (`qt/OtherComputers.qml:130`); Mã 6 số (`qt/OtherComputers.qml:314`); Chưa ghép được: {} (`qt/OtherComputers.qml:352`); Dùng Bluetooth cho (`qt/OtherComputersBluetooth.qml:28`); Vân tay {} (`qt/OtherComputersRow.qml:99`); Mở Studio của (`qt/OtherComputersRow.qml:112`); Chưa lưu được nhật ký* (`qt/PhoneDiagnostics.qml:50`); Lưu nhật ký* (`qt/PhoneDiagnostics.qml:50`); Đã lưu nhật ký* (`qt/PhoneDiagnostics.qml:50`); Làm mới* (`qt/PhoneDiagnostics.qml:68`); Chi tiết kỹ thuật* (`qt/PhoneDiagnostics.qml:107`); Nhật ký ({} dòng)* (`qt/PhoneDiagnostics.qml:121`); Nhật ký máy ({} dòng) (`qt/PhoneDiagnostics.qml:129`); Mở {}* (`qt/PhoneSync.qml:198`); Cho {} (`qt/PhoneSyncDevice.qml:88`); Địa chỉ: {} (`qt/PhoneSyncPairing.qml:59`); Mã ghép nối: (`qt/PhoneSyncPairing.qml:72`); Hết hạn sau {}:{} (`qt/PhoneSyncPairing.qml:81`); Dùng được · (`qt/ProviderKey.qml:42`); Khoá (`qt/ProviderKey.qml:141`); Tự chọn nhạc nền* (`qt/SettingsListen.qml:15`); Đóng vào khay (`qt/SettingsLook.qml:14`); Tự mở mini (`qt/SettingsLook.qml:19`); Giấy* (`qt/SettingsLook.qml:34`); Ngà* (`qt/SettingsLook.qml:34`); Đêm* (`qt/SettingsLook.qml:34`); Xác nhận gỡ (`qt/StudioSettings.qml:125`); Cần cập nhật* (`qt/StudioSettings.qml:141`); Mất {} (`qt/StudioSettings.qml:141`); Giọng của máy* (`qt/VoiceLogic.js:39`); Nữ* (`qt/VoiceLogic.js:44`); Mỹ Duyên* (`qt/VoiceLogic.js:92`); Ngọc Linh (`qt/VoiceLogic.js:92`); Quỳnh Anh (`qt/VoiceLogic.js:92`); Thanh Bình* (`qt/VoiceLogic.js:92`); Thục Đoan (`qt/VoiceLogic.js:92`); Đoan Trang (`qt/VoiceLogic.js:92`); Đức Trí* (`qt/VoiceLogic.js:92`); Ái Hân* (`qt/VoiceLogic.js:93`); Ngọc Huyền (`qt/VoiceLogic.js:96`); Ngọc Trân (`qt/VoiceLogic.js:96`); Trúc Ly (`qt/VoiceLogic.js:96`); Giọng VieNeu* (`qt/VoiceLogic.js:130`); Giọng Supertonic* (`qt/VoiceLogic.js:135`); Giọng VieNeu Nano* (`qt/VoiceLogic.js:139`); Đang đọc bằng bản thường.* (`qt/VoiceLogic.js:217`); Đang đọc bằng bản tăng tốc.* (`qt/VoiceLogic.js:219`); Máy này chưa dùng được {}. (`qt/VoiceLogic.js:252`); Chất lượng giọng* (`qt/VoiceLogic.js:275`); Chất lượng cao nhất* (`qt/VoiceLogic.js:278`); Nhanh hơn* (`qt/VoiceLogic.js:279`); Gỡ (`qt/VoiceModule.qml:271`); Thử* (`qt/VoiceRow.qml:109`)
- chỉ web (28): Chưa lưu được mẫu (`24`); Vân tay (`204`); Mở Studio của {} (`212`); Hỏi lại (`232`); Dùng Bluetooth cho {} (`358`); Bluetooth (`367`); Địa chỉ: (`155`); Mã ghép nối: {} (`160`); Hết hạn sau (`168`); Kết nối lần cuối (`343`); Cho {} điều khiển (`346`); Chưa đổi được lịch đêm (`30`); ABook{} là bản mới nhất. (`22`); Xoá: {} (`169`); Space (`19`); ...

### Thêm sách

- chỉ Qt (26): Chưa mở được file sách* (`qt/AddBook.qml:224`); Đã mở (`qt/AddBook.qml:235`); Bỏ qua* (`qt/AddBook.qml:402`); Đang đọc file tiếp (`qt/AddBook.qml:529`); Đang đọc file sách (`qt/AddBook.qml:587`); Bỏ số gọi* (`qt/AddBook.qml:877`); Lời chú* (`qt/AddBook.qml:888`); Bỏ lời chú* (`qt/AddBook.qml:900`); Cuối chương* (`qt/AddBook.qml:900`); Giữ nguyên* (`qt/AddBook.qml:900`); Bỏ đọc dòng* (`qt/AddBook.qml:966`); Đang thêm {} (`qt/AddBook.qml:1007`); Tất cả file (*) (`qt/AddBook.qml:1039`); Đưa vào sách: (`qt/ImportChapters.qml:101`); Bấm để đổi tên chương* (`qt/ImportChapters.qml:136`); Tên chương* (`qt/ImportChapters.qml:175`); Thả để thêm sách* (`qt/ImportDrop.qml:53`); Tách theo {} dòng “Chương N” (`qt/ImportQueue.js:119`); File này có bản thu khác* (`qt/ImportQueue.js:198`); Sách đã có* (`qt/ImportQueue.js:198`); Đã cập nhật* (`qt/ImportQueue.js:198`); Sách của Studio* (`qt/ImportQueue.js:199`); Đã khôi phục file* (`qt/ImportQueue.js:199`); Đã mở dự án* (`qt/ImportQueue.js:199`); Đã gộp {} sửa từ file* (`qt/ImportQueue.js:206`); Đang tải* (`qt/ImportSkeleton.qml:11`)
- chỉ web (2): Xem trước (`544`); Tách chương (`702`)

### Sửa sách

- chỉ Qt (22): Mức nhạc nền* (`qt/BookMusicSettings.qml:114`); Sắp xếp quyển* (`qt/EditBook.qml:223`); Chưa đọc được file ảnh* (`qt/EditBook.qml:414`); Lưu thay đổi* (`qt/EditBookItems.qml:71`); Chưa nối được {} (`qt/EditBookLogic.js:68`); Chưa bỏ được cách đọc* (`qt/EditBookReadings.qml:28`); Chưa lưu được cách đọc* (`qt/EditBookReadings.qml:28`); Đang tải cách đọc* (`qt/EditBookReadings.qml:71`); Sửa cách đọc {}* (`qt/EditBookReadings.qml:116`); Bỏ cách đọc {}* (`qt/EditBookReadings.qml:126`); Cách đọc cho {}* (`qt/EditBookReadings.qml:145`); Lưu cho cả cuốn* (`qt/EditBookReadings.qml:156`); Đọc nguyên chữ (`qt/EditBookReadings.qml:164`); Xoá “{}”?* (`qt/EditBookReadings.qml:175`); Đổi tên chương* (`qt/EditBookRename.qml:19`); Số chương hay nhãn (`qt/EditBookRename.qml:44`); Tên chương (tuỳ chọn) (`qt/EditBookRename.qml:44`); Chọn nơi lưu* (`qt/EditBookSaveAs.qml:52`); Đang tải* (`qt/EditBookSkeleton.qml:11`); Đang tải bài nhạc* (`qt/EditBookSwap.qml:39`); Chọn* (`qt/EditBookSwap.qml:93`); Xem cả kho (`qt/EditBookSwap.qml:109`)
- chỉ web (6): Bỏ thay đổi ({}) (`474`); Nhãn (`548`); Tên (`558`); Chưa chia sẻ được sách (`613`); Google Books (`14`); Open Library (`14`)

### Thanh bên

- chỉ Qt (10): Trạng thái ABook (`qt/ConnectionChip.qml:10`); Gặp lỗi (`qt/ConnectionChip.qml:55`); Sẵn sàng (`qt/ConnectionChip.qml:55`); Đang mở* (`qt/ConnectionChip.qml:55`); Bản {} (`qt/ConnectionPopover.qml:73`); Khởi động lại (`qt/ConnectionPopover.qml:85`); Mở thư mục nhật ký (`qt/ConnectionPopover.qml:93`); Mở rộng (`qt/Sidebar.qml:93`); Thu gọn* (`qt/Sidebar.qml:93`); Duyệt* (`qt/SidebarProgress.qml:37`)
- chỉ web (1): Thanh bên (`176`)

### Studio dự án

- chỉ Qt (43): Làm* (`qt/OnComputerPill.qml:10`); Chưa gộp được* (`qt/ProjectScreen.qml:138`); Chưa làm được lúc này. (`qt/ProjectScreen.qml:138`); Thêm tuỳ chọn* (`qt/ProjectScreen.qml:335`); Chưa khởi động được: {} (`qt/ProjectScreen.qml:477`); Chưa có chương nào (`qt/ProjectScreen.qml:743`); Đang tải nhật ký (`qt/ProjectScreen.qml:765`); Không thấy thư viện* (`qt/ProjectsScreen.qml:229`); Chọn thư mục* (`qt/ProjectsScreen.qml:232`); Chọn lại thư viện* (`qt/ProjectsScreen.qml:233`); Mở dự án có sẵn (`qt/ProjectsScreen.qml:259`); Nghe* (`qt/StudioChapterRow.qml:49`); Chi tiết lỗi (`qt/StudioChapterRow.qml:122`); Đóng* (`qt/StudioDialogs.qml:63`); 0 phút* (`qt/StudioLogic.js:21`); Còn* (`qt/StudioLogic.js:95`); Sắp tới lượt (`qt/StudioLogic.js:95`); Chờ bạn duyệt (`qt/StudioLogic.js:100`); Mất kết nối tới ABook. (`qt/StudioLogic.js:120`); Đang tạm dừng* (`qt/StudioLogic.js:217`); Sách vẫn đang tạm dừng (`qt/StudioLogic.js:222`); Đang làm tiếp (`qt/StudioLogic.js:228`); Card đồ hoạ hết bộ nhớ.* (`qt/StudioLogic.js:263`); Ổ đĩa hết chỗ trống.* (`qt/StudioLogic.js:277`); Có lỗi khi làm sách.* (`qt/StudioLogic.js:294`); Cài Studio* (`qt/StudioLogic.js:429`); Cập nhật Studio* (`qt/StudioLogic.js:429`); Sửa Studio* (`qt/StudioLogic.js:429`); Bộ phân tích bản {}* (`qt/StudioLogic.js:491`); Bộ phân tích tuỳ chọn* (`qt/StudioLogic.js:491`); Tạo {} (`qt/StudioLogic.js:504`); Mất file audio (`qt/StudioLogic.js:528`); Lỗi {} (`qt/StudioStore.qml:49`); Chưa bắt đầu được (`qt/StudioStore.qml:132`); Chưa làm tiếp được (`qt/StudioStore.qml:150`); Chưa tạm dừng được (`qt/StudioStore.qml:150`); Chưa dừng được (`qt/StudioStore.qml:161`); Chưa bỏ xếp hàng được (`qt/StudioStore.qml:172`); Chưa mở được thư mục (`qt/StudioStore.qml:180`); Hoàn tác* (`qt/StudioStore.qml:195`); Chưa hoàn tác được* (`qt/StudioStore.qml:206`); Đã khôi phục “{}”* (`qt/StudioStore.qml:206`); Chưa đổi được* (`qt/StudioStore.qml:243`)
- chỉ web (6): Chưa khởi động được: (`198`); Làm tiếp từ chỗ ấy (`370`); Phân tích của “ (`370`); Chờ lượt (`764`); Chưa tải được (`1374`); Chưa đọc được dự án này (`41`)

### Studio tạo sách

- chỉ Qt (37): Đặt ảnh bìa (`qt/CoverEditor.qml:159`); Tìm ảnh bìa* (`qt/CoverEditor.qml:207`); Chọn ảnh bìa* (`qt/CoverPicker.qml:13`); Gợi ý: {} chương có {} (`qt/NewCredits.qml:60`); Chọn {} tập (`qt/NewDrop.qml:216`); Tách theo {} (`qt/NewHints.qml:88`); Truyện (*.txt *.epub *.docx *.pdf) (`qt/NewPicker.qml:20`); Tất cả file (*) (`qt/NewPicker.qml:20`); Đang đọc nguồn (`qt/NewProjectLogic.js:49`); Nhân vật tự kể* (`qt/NewProjectLogic.js:193`); Thứ tự lệch: {} (`qt/NewProjectLogic.js:234`); Có vẻ thiếu {} (`qt/NewProjectLogic.js:235`); Quyển {}* (`qt/NewProjectLogic.js:314`); Bản thử nghiệm (`qt/NewProjectLogic.js:371`); Chưa làm được lúc này. (`qt/NewProjectStore.qml:60`); Chưa đọc được:* (`qt/NewProjectStore.qml:157`); Đã áp (`qt/NewProjectStore.qml:227`); Có file không gửi{} (`qt/NewProjectStore.qml:273`); Chưa gửi được. (`qt/NewProjectStore.qml:288`); Không gửi hết các chương{} {} (`qt/NewProjectStore.qml:316`); Tìm hiểu thêm* (`qt/NewTemplateBar.qml:144`); Dùng lại {} (`qt/NewVoice.qml:211`); Chia {} phần? (`qt/NewVolumes.qml:52`); Máy thấy {} (`qt/NewVolumes.qml:58`); Studio chưa xong{} (`qt/StudioSetupCard.qml:28`); Tiến độ:* (`qt/StudioSetupCard.qml:209`); Máy này {}. (`qt/StudioSetupLogic.js:17`); Tải lại {} (`qt/StudioSetupLogic.js:61`); Tạo trên {} (`qt/StudioSetupNotice.qml:98`); Mặc định* (`qt/TemplateLogic.js:12`); Đặt cho mẫu một cái tên (`qt/TemplateLogic.js:49`); Tên mẫu tối đa {} chữ (`qt/TemplateLogic.js:50`); Đã có mẫu “{}” (`qt/TemplateLogic.js:52`); Giọng máy đề xuất* (`qt/TemplateLogic.js:57`); Tải lên {} (`qt/UploadLogic.js:29`); Chưa gửi file nào. (`qt/UploadLogic.js:93`); Đã gửi {}/{} file, giữ lại (`qt/UploadLogic.js:95`)
- chỉ web (29): Bản thử nghiệm{} (`53`); Bản thử nghiệm ({}) (`59`); Nhanh (`95`); Có file không gửi (`312`); Không gửi hết các chương (`319`); Gửi các chương từ máy này (`451`); Sẽ bỏ (`790`); Gợi ý: (`795`); Gợi ý: “ (`877`); Tách theo (`878`); Tách thành (`890`); Nam (`1122`); Giọng kể phần trước: (`1215`); Đang chọn: (`1240`); Tham khảo: (`1326`); ...

### Studio việc duyệt

- chỉ Qt (39): Đã hoàn tác* (`qt/DecisionLogic.js:32`); Đã hoàn tác. {} (`qt/DecisionLogic.js:32`); Trước đó chưa ai quyết khác (`qt/DecisionLogic.js:40`); Trước đó đang là {} (`qt/DecisionLogic.js:40`); Xem thêm {} tên (`qt/NameLogic.js:34`); Thêm* (`qt/NameLogic.js:46`); Đã bỏ qua ({}) (`qt/PhoneEdits.qml:84`); Bỏ qua mọi việc từ (`qt/PhoneEdits.qml:154`); Dùng “{}” (`qt/ReadingProblem.qml:40`); Máy nghe ra: “{}” (`qt/ReviewLogic.js:42`); Sẽ đọc là “{}” (`qt/ReviewLogic.js:47`); Tải tiếp · còn (`qt/ReviewLogic.js:60`); Nghe liền {} câu (`qt/ReviewQueue.qml:254`); Nghe câu: (`qt/ReviewRow.qml:83`); Đang đọc là: <span style="color:{}">{} (`qt/ReviewRow.qml:212`); Máy đọc thành (`qt/ReviewSpoken.qml:42`); Ảnh hưởng <b><span style="color:{}">{} (`qt/WorkCard.qml:150`); Đang mở* (`qt/WorkCard.qml:351`); Đang đóng (`qt/WorkCard.qml:351`); Xem thêm {} việc (`qt/WorkInbox.qml:220`); Đoạn này do (`qt/WorkLogic.js:50`); Đang chọn cả {} câu* (`qt/WorkLogic.js:158`); Đang chọn {}/{} câu* (`qt/WorkLogic.js:160`); Xem thêm (đang hiện {}/{} câu)* (`qt/WorkLogic.js:169`); Giọng nam* (`qt/WorkLogic.js:225`); Giọng nữ* (`qt/WorkLogic.js:225`); Mọi việc đã có quyết định (`qt/WorkLogic.js:280`); Cần trước chương sắp thu. (`qt/WorkLogic.js:316`); Chỉ áp khi làm lại sách. (`qt/WorkLogic.js:317`); Phạm vi đầu: {} (`qt/WorkLogic.js:320`); Ước {} (`qt/WorkLogic.js:321`); Lúc áp: {}. (`qt/WorkLogic.js:323`); Đúng rồi, giữ “{}” (`qt/WorkPronunciation.qml:35`); Cách đọc mới cho {} (`qt/WorkPronunciation.qml:54`); Cả chuỗi (`qt/WorkSpeaker.qml:74`); Xem {} câu (`qt/WorkSpeaker.qml:237`); Chưa hoàn tác được* (`qt/WorkStore.qml:89`); Mới hoàn tác được {}/{} việc (`qt/WorkStore.qml:89`); Đã dùng (`qt/WorkStore.qml:325`)
- chỉ web (20): Tìm hoặc thêm tên (`126`); Không khớp “ (`164`); Bỏ qua mọi việc từ {}? (`232`); Dùng “ (`27`); Máy nghe ra: “ (`223`); Sẽ đọc là “ (`231`); Đang đọc là: (`235`); Nghe liền (`453`); Tải tiếp · còn {} câu (`499`); Chưa nghe thử được: (`147`); Đúng rồi, giữ “ (`381`); Xem (`628`); Nam (`653`); Ảnh hưởng (`945`); Giữ cả {} thẻ “{}”? (`1090`); ...

### Studio nhân vật

- chỉ Qt (1): Đổi giọng kể* (`qt/TellerLogic.js:38`)
- chỉ web (8): Nam (`92`); Giọng đọc của (`153`); Áp dụng sẽ thu lại (`160`); Không có ai khớp “ (`123`); Tên nào cũng ổn (`165`); Không câu nào nghi (`166`); Nghe và chỉnh giọng cho (`228`); Giọng của {} (`253`)

### Studio kịch bản

- chỉ Qt (7): Người nghĩ (`qt/ScriptRow.qml:98`); Người nói (`qt/ScriptRow.qml:98`); Gán cho {} (`qt/ScriptRow.qml:259`); Thu lại* (`qt/ScriptRow.qml:305`); Lấy của máy kia (`qt/ScriptStore.qml:54`); Đang chọn {} câu (`qt/ScriptTab.qml:467`); Duyệt {} câu (`qt/ScriptTab.qml:591`)
- chỉ web (9): Vui (`191`); Nam (`872`); Đổi {}: {} (`930`); Đang chọn. (`1075`); Cách đọc mới không áp được: (`1113`); Gán cho (`1127`); Yêu cầu (`1152`); Thu lại (R) (`1160`); Chưa có câu: {} (`1403`)

### Studio xuất và áp dụng

- chỉ Qt (30): Xuất “ (`qt/ExportBook.qml:58`); Các quyển* (`qt/ExportBook.qml:198`); Cả sách* (`qt/ExportBook.qml:199`); Kèm nhạc nền* (`qt/ExportBook.qml:231`); Cỡ ước tính: khoảng {} (`qt/ExportBook.qml:244`); Xuất {} chương đổi (`qt/ExportBook.qml:326`); Đang đóng gói* (`qt/ExportLogic.js:51`); Đã xuất vào máy tính* (`qt/ExportLogic.js:96`); Đã xuất vào máy tính {}* (`qt/ExportLogic.js:96`); Đã xuất (`qt/ExportLogic.js:112`); Phần {}* (`qt/ExportLogic.js:170`); Đã xuất MP3* (`qt/ExportLogic.js:190`); Đã xuất M4B* (`qt/ExportLogic.js:192`); Đang tải nhạc nền {}/{} bài* (`qt/ExportLogic.js:201`); Đang kiểm đỉnh âm* (`qt/ExportLogic.js:203`); Chương {}/{}* (`qt/ExportLogic.js:207`); Đang ghi chương {}/{}* (`qt/ExportLogic.js:209`); Đang trộn nhạc chương {}/{}* (`qt/ExportLogic.js:211`); Đang chờ mạng* (`qt/ExportLogic.js:216`); Đang thêm chữ sáng… {} (`qt/ExportLogic.js:259`); Bỏ cách đọc “{} (`qt/ExportLogic.js:277`); Ghép âm thanh* (`qt/FfmpegNeeded.qml:25`); Cập nhật công cụ* (`qt/FfmpegNeeded.qml:30`); Thiếu công cụ ghép* (`qt/FfmpegNeeded.qml:30`); Dừng* (`qt/FfmpegNeeded.qml:50`); Đang tải công cụ* (`qt/FfmpegNeeded.qml:71`); Tải công cụ ghép âm thanh* (`qt/FfmpegNeeded.qml:76`); Thử lại* (`qt/FfmpegNeeded.qml:97`); Tải công cụ* (`qt/FfmpegNeeded.qml:97`); Nghe thử* (`qt/PendingRow.qml:82`)
- chỉ web (4): File .abook (`57`); Xuất “{}” (`378`); Cỡ ước tính: khoảng (`527`); Đang thêm chữ sáng… {}% (`43`)

### Studio máy khác

- chỉ Qt (1): Studio* (`qt/StudioScreen.qml:208`)
- chỉ web (0): (không có)

### Thanh tiêu đề

- chỉ Qt (2): ABook vẫn chạy ở khay (`qt/Main.qml:28`); Chưa tải được bản mới* (`qt/Main.qml:348`)
- chỉ web (3): Mở rộng (Ctrl+B) (`260`); Thu gọn (Ctrl+B) (`260`); Điều hướng (`277`)

### Chung

- chỉ Qt (2): Chưa làm được lúc này. (`qt/Api.qml:61`); Quay lại* (`qt/ScreenHeader.qml:14`)
- chỉ web (4): Đang tải điều hướng (`582`); Thông báo (Alt+T) (`699`); Xem các tab trước (`557`); Xem các tab sau (`562`)

File QML chưa xếp màn (thêm vào SCREENS): `desktop_qt/qml/AvatarEditor.qml`, `desktop_qt/qml/BookLogic.js`, `desktop_qt/qml/CastLogic.js`, `desktop_qt/qml/DestructiveConfirm.qml`, `desktop_qt/qml/FindInBook.qml`, `desktop_qt/qml/FindLogic.js`, `desktop_qt/qml/MusicCredit.qml`, `desktop_qt/qml/MusicLevelSlider.qml`, `desktop_qt/qml/MusicPopover.qml`, `desktop_qt/qml/PeerStudio.js`, `desktop_qt/qml/PlayerConsent.qml`, `desktop_qt/qml/PlayerLineLogic.js`, `desktop_qt/qml/ProjectSteps.qml`, `desktop_qt/qml/ScriptScope.qml`, `desktop_qt/qml/StudioChapterHead.qml`, `desktop_qt/qml/StudioMusic.qml`, `desktop_qt/qml/StudioMusicLogic.js`, `desktop_qt/qml/StudioMusicMoods.qml`, `desktop_qt/qml/StudioMusicScene.qml`, `desktop_qt/qml/StudioMusicSwap.qml`, `desktop_qt/qml/StudioMusicTrackRow.qml`, `desktop_qt/qml/ToneLabels.js`, `desktop_qt/qml/UiNumber.js`, `desktop_qt/qml/ValuePicker.qml`, `desktop_qt/qml/ValuePickerLogic.js`, `desktop_qt/qml/VolumeEditor.qml`.

## d. Bo góc QML không theo token

Hợp lệ: `Theme.radiusControl / radiusCover / radiusSheet` (DESIGN.md 5.5, `desktop_qt/tools/gen_theme.py`), `0`, tròn (`width / 2`, `height / 2`), lấy lại bo khung chứa (`parent.radius`), vòng đồng tâm ngoài (`Theme.radiusCover + 8` của bóng, vòng tiêu điểm). Còn lại (0):

| nơi | radius |
|---|---|
| (không có) | |

## e. Dấu thanh kiểu mới và dấu ba chấm cuối nhãn

**Dấu thanh kiểu mới (`òa óa úy`)** trong chữ Qt (0); web và native đa số viết kiểu cũ (`oà oá uý`, UI_PARITY.md d2):

- (không có)

**Nhãn kết thúc bằng `…` / `...`** (0): DESIGN.md chỉ cho `…` ở chữ đang chờ ("Đang mở…"), không cho nhãn nút.

- (không có)

## f. Phím tắt trong chú thích

Chú thích Qt ghi phím tắt sau nhãn; web ghép bằng `withShortcut(nhãn, phím)`. Phím khác nhau là khác HÀNH VI (phím thật trong `Main.qml` / `player.tsx`), không chỉ khác chữ.

| nhãn | Qt | web | nơi |
|---|---|---|---|
| Thu nhỏ | `Esc` | (không ghi) | `qt/NowPlaying.qml:255` |
| Chương trước | `Shift+←` | (không ghi) | `qt/NowPlaying.qml:399` |
| Chương sau | `Shift+→` | (không ghi) | `qt/NowPlaying.qml:410` |
| Phát | `Space` | (không ghi) | `qt/PlayButton.qml:14` |
| Tạm dừng | `Space` | (không ghi) | `qt/PlayButton.qml:14` |
| {} | `Esc` | (không ghi) | `qt/ScreenHeader.qml:26` |
| Thu lại | `R` | (không ghi) | `qt/ScriptRow.qml:305` |
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
| cast-history-0 | Lịch sử | Web, Qt, Android |
| cast-history-1 | Hoàn tác | Web, Qt, Android |
| cast-history-2 | Chờ áp dụng | Web, Qt, Android |
| cast-history-3 | Đã hoàn tác | Web, Qt, Android |
| cast-history-4 | Không có trạng thái trước; hãy tách thủ công. | Web, Qt, Android |
| cast-history-5 | Giọng đọc chưa đổi; chờ thu lại. | Web, Qt, Android |
| record-create | Tạo và nghe | Qt, Web, Android |
| record-delete | Xoá hồ sơ | Qt, Web, Android |
| record-move | Chuyển | Qt, Web, Android |
| mini-enter | Cửa sổ mini | Qt, Android |
| mini-auto | Tự mở mini | Qt, Android |

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
