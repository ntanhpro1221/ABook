# Chữ, icon và bo góc giống nhau giữa các nền tảng giao diện

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Ba thứ, ba nguồn chung, đều có luật máy (`python -X utf8 scripts/ui_parity.py --check`, chạy trong `tests/test_ui_parity.py`):

- **Bo góc**: `docs/DESIGN.md` 5.5 -> `scripts/gen_native_tokens.py` -> `Tokens.kt` (native) + `ui/src/shared/tokens.generated.css` (web:
  `rounded-control` / `rounded-cover` / `rounded-sheet`). Luật máy: `ui/src/shared/radiusRules.test.ts`, `RadiusRulesTest.kt`.
- **Icon**: lucide. `scripts/gen_lucide_icons.py` (MỘT danh sách `ICONS`) sinh nét cho native và Qt từ đúng gói web dùng; luật `IconRulesTest.kt`.
  Một việc = một icon trên mọi nền tảng: bảng "Việc -> icon" dưới đây là luật, `--check` báo nhãn nào dùng icon khác bảng (bên nào cũng vậy).
- **Chữ**: cặp màn `scripts/ui_parity_pairs.json` (nhãn có ở một phía mà phía kia không có thì `--check` đỏ, trừ mục `allow` có lý do),
  luật chữ bên dưới, và bảng đo lệch tự sinh ở cuối file.

## Việc -> icon

Tên icon theo lucide (hai tên một hình, vd `trash` = `trash-2`, tính là một). `*` khớp mọi chữ. Hàng nào thêm vào đây thì mọi chỗ dùng nhãn ấy,
web lẫn native, phải dùng đúng icon này.

<!-- ui_parity:icons -->
| Việc (nhãn) | Icon | Ghi chú |
|---|---|---|
| Bỏ ghép, Bỏ ghép* | `unplug` | gỡ một thiết bị đã ghép |
| Ghép lại | `link-2` | ghép lại thiết bị đã bỏ |
| Xoá, Xoá khoá, Xoá hồ sơ*, Xoá khỏi*, Xoá bản đọc, Bỏ ảnh bìa | `trash-2` | xoá / gỡ hẳn một thứ |
| Xoá ô tìm | `x` | xoá chữ trong ô, không xoá dữ liệu |
| Đọc theo | `text-align-start` | chữ chạy theo giọng |
| Thêm tuỳ chọn* | `ellipsis` | nút "..." của một hàng / màn; nhãn nghe được là "Thêm tuỳ chọn", không bao giờ "Thêm" trơn (đó là dấu cộng) |
| Thêm sách | `plus` | |
| Làm mới | `refresh-cw` | |
| Nhạc nền | `eighth-note` | |
| Sửa thông tin | `pencil` | |
| Tìm | `search` | |
| Từ đầu | `rotate-ccw` | |
<!-- ui_parity:icons:end -->

## Luật chữ

Máy kiểm trong mã nguồn giao diện (web `ui/src`, native `.../ui/`, bỏ thư viện mẫu và chữ giả); chỗ trích sách thật không bị sửa.

1. **Dấu thanh kiểu cũ**: hoà, khoá, xoá, loá, thuý, tuỳ (không hòa, khóa, xóa, tùy...). "quý" giữ nguyên. Máy báo `òa/óa/ỏa/õa/ọa`, `òe/óe/...`, `ùy/úy/...`.
2. **Không `…` hay `...` ở cuối nhãn, trạng thái, nút, gợi ý ô nhập**: "Đang gửi", "Chia sẻ", "Lưu thành". `…` chỉ còn là hình nút "Thêm tuỳ chọn".
3. **Không `:` cuối nhãn** khi giá trị nằm ở thành phần riêng; `:` chỉ nằm giữa câu chạy. Máy chỉ nhắc (nhẹ), chưa đỏ.
4. **Viết hoa đầu nhãn** đứng riêng ("Đang phát"); mảnh dán sau tên bằng " · " cũng viết hoa; tên màn giữa câu giữ hoa ("Mở Cài đặt").
5. **Cùng việc, cùng chữ**: chữ web là chuẩn, trừ khi chữ native rõ ràng hơn theo DESIGN (nhãn 1-4 chữ, giản dị, gọi "bạn") thì đổi cả web.
6. **`allow` hay `missing`** (`scripts/ui_parity_pairs.json`): `allow` chỉ khi nền tảng BẮT BUỘC khác - phím tắt / chuột, tên cho trình đọc màn hình
   của một nút mà chữ thấy được hai bên như nhau, dữ liệu (tên giọng, tên công ty), câu nằm ở lõi native ngoài `ui/` (readaloud/ClipReader.kt).
   Phần màn hay tính năng chỉ một phía có (hộp giải thích quyền của web, tấm "Thiết bị phát" của native, chữ "Đang …" thay vòng quay) là
   `missing`, `side` = phía đang có. Chữ khác cho cùng một việc thì sửa cả hai phía theo từ điển dưới đây, không ghi vào pairs.json.

## Từ điển chữ chung

Một việc - một cách viết, cho web (máy tính + điện thoại), native và Qt. Thêm hàng khi chọn chữ cho việc mới; đổi một hàng là đổi mọi nơi.
`{}` = chỗ điền. Cột "thay cho" là các cách viết đã bỏ (đừng dùng lại).

**Lời chung**

| Việc | Viết | Thay cho | Lý do |
|---|---|---|---|
| Làm không được (tiêu đề lỗi) | `Chưa {việc} được`: Chưa xoá được, Chưa làm được, Chưa tải được, Chưa chia sẻ được sách, Chưa thêm được nhạc, Chưa xoá được bài này | "…, bạn thử lại", "Bạn hãy thử lại.", "Không … được", "Không làm được lúc này." | "chưa" nói sẽ làm lại được; thử lại là nút "Thử lại", không phải chữ |
| Lỗi theo việc (lõi không có câu) | Chưa lưu được khoá · Chưa kiểm tra được khoá · Chưa xoá được khoá · Chưa nghe thử được giọng này. · Chưa tải được giọng | một câu chung | nói đúng việc vừa hỏng |
| Đóng bảng trượt (tay nắm, nền tối) | Đóng | Đóng bảng | ngắn, như nút đóng của web |
| Tên bảng "…" của trình phát | Thêm tuỳ chọn | Tuỳ chọn | trùng tên nút "…" (bảng Việc -> icon) |
| Mở cài đặt của Android | Mở cài đặt | Mở Cài đặt, Mở cài đặt để cho phép | "Cài đặt" viết hoa chỉ khi là màn của ABook |
| Máy không có giọng | Máy này chưa có giọng đọc. | Chưa có giọng cài sẵn. Bạn chọn giọng trong Cài đặt. | ngắn, đã dùng ở thanh đọc |
| Thời lượng còn lại | Còn {thời lượng} | "Còn " + … ghép tay | một mẫu cho cả hai |
| Nguồn của sách nghe thẳng | Trên {tên máy} | "Trên máy tính" cố định | máy ghép thêm có tên riêng |
| Thư viện trống | Chưa có sách trên máy · Thêm sách của bạn để bắt đầu nghe. | Chưa có sách nào · Sách nghe được sẽ hiện ở đây. | nói việc kế tiếp |
| Nhãn menu xuất | Xuất MP3 · Xuất M4B · Xuất sách nói (M4B) | "… (M4B)…" | luật 2: không "…" cuối nhãn |

**Cài đặt, nhật ký**

| Việc | Viết | Thay cho | Lý do |
|---|---|---|---|
| Tên của điện thoại ở máy khác | Tên điện thoại | Tên máy này | cùng chữ với bảng "Đổi tên điện thoại này" |
| Nhật ký rỗng | Chưa có dòng nào. | Nhật ký đang trống. | cùng chữ bản chẩn đoán |
| Lịch đêm | Từ · Đến · Hẹn | Số phút hẹn | ba ô, ba tên ngắn |
| Lắc để nghe thêm | Độ nhạy | Độ nhạy lắc | đã nằm trong nhóm "Lắc" |
| Tóm tắt nhóm Nghe | Tự lùi / Không tự lùi · nhạc tự chọn / không nhạc nền | - | `listenSummary` (web) = `SettingsSummary.listen` (native) |

**Thiết bị, chia sẻ, tải**

| Việc | Viết | Thay cho | Lý do |
|---|---|---|---|
| Đang dò máy | Đang tìm máy | Đang tìm trong mạng Wi-Fi | dò cả Wi-Fi lẫn Bluetooth |
| Không thấy máy | Chưa thấy máy nào | Chưa thấy máy tính nào. Kiểm tra…; Không thấy thiết bị nào - … | một câu + nút "Tìm lại" / "Địa chỉ" ngay đó |
| Bluetooth chưa ghép | Chưa có máy nào ghép Bluetooth. Ghép ở Cài đặt Android › Bluetooth rồi thử lại. | ba cách viết | nói cách sửa |
| Thiếu quyền Bluetooth | Cần quyền Thiết bị ở gần + nút "Mở cài đặt" | Quyền “Thiết bị ở gần” của ABook đang tắt. Mở Cài đặt → … | đường đi đã nằm trong nút |
| Thêm máy ghép | Thêm thiết bị | Ghép thiết bị | cùng chữ màn Nối máy tính |
| Máy thấy qua Bluetooth | Qua Bluetooth | Qua Bluetooth · điện thoại/máy tính | biểu tượng đã nói loại máy |
| Công tắc chia sẻ | Cho máy khác nghe (dòng phụ: Máy đã ghép nghe được sách bạn thêm từ file, không cần chép sang.) | tên "Chia sẻ thư viện" cho công tắc | tên màn là "Chia sẻ thư viện", công tắc nói việc nó làm |
| Bluetooth khi chia sẻ | Bluetooth: {n} máy đang nối | Cả qua Bluetooth cho máy đã ghép - {n} đang kết nối | chỉ hiện khi mang tin |
| Mã ghép đang hiện | Nhập mã này trên máy kia · Dùng được đến {giờ:phút} | còn {phút:giây} | mốc đứng yên, không đồng hồ đếm ngược |
| Mã bị huỷ | Nhập sai mã quá 5 lần - mã đã bị huỷ. Bấm “Ghép máy mới” để có mã khác. | Mã đã huỷ vì nhập sai nhiều lần. | nói cách lấy mã mới |
| Hộp đổi tên điện thoại | dòng phụ: Máy tính và các máy đã ghép thấy điện thoại bằng tên này. | - | native thêm dòng của web |
| Máy kia không trả lời | Chưa nối được máy kia. | Chưa nối được, bạn thử lại; Chưa nối được máy tính | máy kia có thể là điện thoại |
| Dung lượng (một dòng) | Sách {cỡ} · còn trống {cỡ} | {cỡ} · còn trống {cỡ}; Sách trên máy: … | cùng dòng tóm tắt hai bên |
| Studio chưa nối | Studio trên máy tính · Nối máy tính để làm sách nói và xem tiến độ. | Nối máy tính của bạn để tạo sách nói. | DESIGN L11: xem tiến độ |
| Hàng một máy tính ở Studio | Tạo sách nói từ xa | Studio trên máy tính | nói việc làm được |
| Máy tính chỉ cho nghe | Máy tính {tên} chỉ cho nghe - trên máy tính ấy, bật Cài đặt › Thiết bị › “Điều khiển từ xa”. | đường đi trong hằng riêng | một câu, có dấu chấm |
| Tải sách / giọng | Tải về máy · Đang tải {n}% · Huỷ tải · Đã tải xong - nghe được cả khi không có mạng · Chưa tải được | Tải · {n}%; Huỷ; Đã tải về máy; Không tải được | |
| Huỷ một lượt tải | Đã huỷ - lần tải sau làm tiếp từ chỗ dừng. | Đã huỷ tải - lần sau tải tiếp từ chỗ dở; Đã dừng tải | câu đã dùng cho giọng và Studio |

**Giọng đọc**

| Việc | Viết | Thay cho | Lý do |
|---|---|---|---|
| Nghe mẫu một giọng | Nghe thử (đang phát: Dừng); tên đọc màn hình: Nghe thử {giọng} | Thử giọng | cùng chữ trình phát, trang sách |
| Giọng đang dùng | Đang dùng: {giọng} | - | một mẫu |
| Ô khoá | Khoá {nhà cung cấp} · Đã lưu {khoá che} - dán khoá mới để thay | {khoá che} · dán khoá mới để đổi | |
| Kết quả khoá | Dùng được · {n} giọng / Chưa dùng được | - | native ghép sau khoá che: `VoiceText.keyStatus` |
| Tóm tắt "Khoá trực tuyến" | tên các nhà cung cấp đã có khoá, hay Chưa có khoá | {n} khoá | nói khoá nào |
| Gỡ một giọng đã tải | Gỡ giọng | Gỡ | rõ gỡ cái gì |
| Đang tải bộ giọng | Đang tải {cỡ} · {n}% | Đang tải giọng x ({cỡ}) {n}% | tên đã ở tiêu đề thẻ / hàng |
| Máy không chạy được bộ giọng | Máy này chưa dùng được. · Máy này chưa dùng được: {lý do}. | tên giọng giữa câu | tên đã ở tiêu đề |
| Lời mời dưới tên bộ giọng | Giọng hay, đọc ngay trên máy, không cần mạng. Chữ của sách không rời máy. · Mười giọng nam nữ, nhẹ máy, không cần mạng. Chữ của sách không rời máy. | - | native thêm (ModuleKind.invite) |
| Nhãn lựa chọn nên tải | Khuyên dùng | Khuyên dùng · (ghép tay) | |
| Khoá bị từ chối | Khoá {X} không dùng được - tạm đọc bằng {Y}. Kiểm tra lại khoá trong Cài đặt. | Khoá X lỗi; tạm dùng Y — bạn kiểm tra khoá trong Cài đặt. | không gạch dài, cùng khuôn các câu "tạm đọc bằng" |
| Không giọng nào đọc được | Không có giọng nào đọc được - kiểm tra mạng hoặc cài giọng tiếng Việt cho máy. | Không có giọng nào đọc được đoạn này. | nói cách sửa |
| Hỏi trước khi gửi chữ đi | tên bảng: Giọng đọc trực tuyến | Gửi chữ ra ngoài? | cùng tên hộp của trình phát web |

<!-- ui_parity:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity.py - không sửa tay, chạy lại script) -->

Quét: web 5861 chữ (3277 khác nhau), 378 cặp nhãn-icon; native 902 chữ (708 khác nhau), 50 cặp nhãn-icon. Nhãn so theo khoá lỏng (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối).

## a. Cùng việc, khác chữ

Cặp nhãn ngắn (<= 6 chữ) mà phía kia KHÔNG có nguyên văn nhưng có nhãn giống (chung từ, gần nhau, hay chung icon). 201 cặp; 40 cặp đầu theo độ giống. `icon` = cùng icon lucide.

| native | web | giống | nơi |
|---|---|---|---|
| Chọn giọng | Chọn một giọng | 1.00 | `native/nowplaying/PlayerSheets.kt:166` ~ `studio/NewProjectScreen.tsx:1273` |
| Có bản mới · {} | Có bản mới {} | 1.00 | `native/voice/VoiceModel.kt:293` ~ `android/SettingsScreen.tsx:374` (+2) |
| Tên gốc: {} | Tên gốc: | 1.00 | `native/addbook/BookForms.kt:97` (+1) ~ `studio/CastEdits.tsx:88` |
| Đã xuất | Xuất | 1.00 | `native/export/ExportScreen.kt:175` ~ `studio/ExportBook.tsx:385` (+2) |
| Đã xuất {} chương | Đã xuất {} chương{} | 1.00 | `native/export/ExportModel.kt:310` ~ `android/ExportMp3.tsx:78` |
| Chưa mở được Studio | Chưa gỡ được Studio | 0.95 | `native/devices/DevicesRepo.kt:148` ~ `studio/StudioSetup.tsx:359` |
| Đang đo. | Đang đổi | 0.93 | `native/screens/SettingsAdvanced.kt:59` ~ `studio/MusicTab.tsx:230` |
| Đã xoá khỏi điện thoại | Xoá {} khỏi điện thoại | 0.93 | `native/components/UndoBar.kt:27` ~ `android/DevicesScreen.tsx:908` (+1) |
| Chương này chưa có audio. | Chương sau chưa có audio | 0.92 | `native/screens/BookSheets.kt:246` ~ `listen/labels.ts:103` (+1) |
| Cắt ảnh bìa | Đặt ảnh bìa | 0.91 | `native/editbook/CoverCrop.kt:108` ~ `studio/CoverEditor.tsx:112` (+1) |
| Đang bỏ ghép | Đã bỏ ghép {} | 0.91 | `native/devices/DeviceSheets.kt:137` ~ `android/DevicesScreen.tsx:948` (+2) |
| Đang đóng | Đang dùng | 0.89 | `native/music/MusicPanel.kt:245` ~ `studio/VoicePicker.tsx:339` (+1) |
| Sách nói | Sách mới | 0.88 | `native/export/ExportModel.kt:379` ~ `desktop/SettingsScreen.tsx:410` |
| Đang mở Studio | Đang mở Studio của {} | 0.88 | `native/devices/DeviceSheets.kt:76` ~ `shared/peerStudio.ts:52` |
| Đang nối {} | Đang đổi | 0.88 | `native/devices/PairScreen.kt:188` ~ `studio/MusicTab.tsx:230` |
| Đã có trên máy | Đã có {}% trên máy này{} | 0.88 | `native/voice/VoiceModel.kt:296` ~ `desktop/remoteDownloadState.ts:78` |
| Chọn giọng | Đã chọn giọng {} | 0.87 | `native/nowplaying/PlayerSheets.kt:166` ~ `listen/PlayerViews.tsx:765` |
| Đang đọc ảnh | Đang đọc là: | 0.87 | `native/editbook/CoverCrop.kt:125` ~ `studio/ReviewQueue.tsx:246` |
| Đang đóng file sách | Đang đóng gói sách… | 0.86 | `native/screens/BookSheets.kt:156` ~ `desktop/bookFileExport.ts:28` (+1) |
| Chọn giọng | Chung giọng | 0.86 | `native/nowplaying/PlayerSheets.kt:166` ~ `studio/WorkInbox.tsx:152` |
| Vẫn tải | Vân tay | 0.86 | `native/voice/VoiceSheets.kt:122` ~ `android/DevicesScreen.tsx:403` (+3) |
| Vẫn tải | Vẫn cài | 0.86 | `native/voice/VoiceSheets.kt:122` ~ `studio/StudioSetup.tsx:227` (+1) |
| Đang lấy giọng | Đang tải giọng ({}) {}% | 0.86 | `native/screens/SettingsVoice.kt:274` ~ `studio/voiceEngines.ts:80` |
| Đã xuất | Đề xuất | 0.86 | `native/export/ExportScreen.kt:175` ~ `studio/NewProjectScreen.tsx:1016` |
| Chương này chưa có audio. | Các chương sau chưa có audio. | 0.85 | `native/screens/BookSheets.kt:246` ~ `listen/labels.ts:168` |
| Đang mở Studio | Đã gỡ Studio | 0.85 | `native/devices/DeviceSheets.kt:76` ~ `studio/StudioSetup.tsx:356` |
| Đã xuất xong | Đã xuất {} chương{} | 0.85 | `native/export/ExportModel.kt:390` ~ `android/ExportMp3.tsx:78` |
| Tìm lại thiết bị phát | Hỏi lại thư viện | 0.84 · icon | `native/devices/CompanionSurfaces.kt:118` ~ `desktop/OtherComputers.tsx:228` (+1) |
| Địa chỉ máy tính | Địa chỉ máy kia | 0.84 | `native/devices/PairScreen.kt:171` ~ `desktop/OtherComputers.tsx:285` |
| Chọn thư mục để lưu trước | Chọn thư mục trước | 0.84 | `native/export/ExportRepo.kt:86` ~ `desktop/LibraryMoveRecovery.tsx:36` |
| Chọn giọng | Chọn giọng đọc | 0.83 | `native/nowplaying/PlayerSheets.kt:166` ~ `listen/OnlineVoicePrompt.tsx:37` (+1) |
| Đã nối {} | Ai nói? | 0.83 | `native/devices/DevicesState.kt:69` ~ `studio/ScriptTab.tsx:625` |
| Đã nối {} | Đã tới {} | 0.83 | `native/devices/DevicesState.kt:69` ~ `listen/player.tsx:577` |
| Bạn hãy thử lại. | Bật và thu lại | 0.83 | `native/addbook/ImportQueue.kt:108` (+5) ~ `studio/TellerModeSwitch.tsx:79` |
| Còn mới | Có bản mới {} | 0.82 | `native/export/ExportModel.kt:370` ~ `android/SettingsScreen.tsx:374` (+2) |
| Có bản mới · {} | Bản mới | 0.82 | `native/voice/VoiceModel.kt:293` ~ `desktop/SettingsScreen.tsx:182` (+1) |
| Dùng ảnh | Dừng nghe | 0.82 | `native/editbook/CoverCrop.kt:110` ~ `studio/MusicTab.tsx:225` (+1) |
| Dùng ảnh | Dừng nghe {} | 0.82 | `native/editbook/CoverCrop.kt:110` ~ `studio/NewProjectScreen.tsx:989` (+1) |
| Đang đóng | Đang đổi | 0.82 | `native/music/MusicPanel.kt:245` ~ `studio/MusicTab.tsx:230` |
| Chưa đọc được các khoá | Chưa đổi được cách đọc | 0.82 | `native/voice/KeysScreen.kt:35` ~ `listen/VieneuModuleCard.tsx:291` |

## b. Cùng nhãn khác icon, cùng icon khác nhãn

**Cùng nhãn, khác icon** (0 nhãn có icon ở cả hai phía mà không chung icon nào):

| nhãn | web | native | nơi |
|---|---|---|---|
| (không có) | | | |

**Cùng icon, khác nhãn** (7 icon dùng ở cả hai phía mà không chung nhãn nào):

| icon | web | native |
|---|---|---|
| check | Duyệt câu, Giữ cả thẻ, Giữ thẻ, Tạm dừng {} | Chưa nghe, Chưa nghe xong, Đang lấy giọng |
| circle-dashed | Chưa nghe / Đã nghe xong, Tạm dừng {} | Chưa nghe, Chưa nghe xong |
| download | Cài Studio, Cài tiếp, Có ABook {}, Dừng tải / Tải tiếp | Cập nhật ({}), Tải ABook Windows |
| image-plus | Đổi ảnh bìa | Chọn ảnh |
| laptop | Máy kia không trả lời | Studio máy tính, Đang mở Studio |
| share-2 | Chia sẻ | Đang đóng file sách |
| upload | Chọn file, Nhập nhạc, Thêm file, Thêm nhạc của bạn | Đang thêm {}/{} |

Phủ của bộ ghép: icon dùng ở 94 chỗ trong mã native, ghép được với nhãn chữ ở 48; web 554 chỗ, ghép được 326. Phần còn lại là icon không đi cùng nhãn chữ (nút chỉ icon, chỉ báo) hay nhãn dựng từ model (vd tên nhóm Cài đặt), nên KHÔNG có trong bảng.
Icon native chưa quy về lucide (3): `native:ChevronIcon`, `native:OtherPlayerIcon`, `native:PlayerGlyph`.
Số cặp: web 326, native 48; icon lucide dùng: web 98, native 27.

## c. Nhãn chỉ có ở một phía, theo màn

Nhãn ngắn (<= 6 chữ) không có (theo khoá lỏng) ở phía kia - kể cả chữ giống chữ ở mục a. Để phân biệt tính năng thiếu với chữ trôi: một màn native có nhiều nhãn chỉ-native mà web cùng màn không có thường là tính năng mới; vài nhãn lẻ thường là chữ trôi (mục a).

### c1. Chỉ có ở native (74 nhãn)

- `native/addbook/BookForms.kt` (1): Tên gốc: {} (`97`)
- `native/addbook/ImportQueue.kt` (1): Bạn hãy thử lại. (`108`)
- `native/addbook/ImportRepo.kt` (1): Bạn hãy nhập tên sách. (`91`)
- `native/components/Confirm.kt` (1): Đang xoá (`95`)
- `native/components/ListParts.kt` (1): Sắp có (`429`)
- `native/components/UndoBar.kt` (1): Đã xoá khỏi điện thoại (`27`)
- `native/data/DemoPlayback.kt` (1): Chương {} · {} (`13`)
- `native/devices/CompanionSurfaces.kt` (5): Chọn nơi phát (`39`); Đang gửi lệnh (`55`); Chưa phát sách (`68`); Phát ở đây (`109`); Tìm lại thiết bị phát (`118`)
- `native/devices/DeviceSheets.kt` (3): Đang mở Studio (`76`); Đang bỏ ghép (`137`); Đang lưu (`161`)
- `native/devices/DevicesModel.kt` (2): Chưa thấy (`302`); Thấy {} (`302`)
- `native/devices/DevicesRepo.kt` (1): Chưa mở được Studio (`148`)
- `native/devices/DevicesState.kt` (3): Chưa nối (`69`); Đã nối {} (`69`); Đang bật · {} máy (`71`)
- `native/devices/PairScreen.kt` (5): Máy đã nối (`111`); Sách trên {} (`136`); Cách nối (`164`); Địa chỉ máy tính (`171`); Đang nối {} (`188`)
- `native/devices/StorageScreen.kt` (2): Còn trống {} (`51`); Chưa có gì trên máy (`55`)
- `native/editbook/BookEditor.kt` (1): Bạn hãy thử lại. (`46`)
- `native/editbook/CoverCrop.kt` (5): Bạn hãy chọn lại ảnh bìa. (`105`); Cắt ảnh bìa (`108`); Dùng ảnh (`110`); Đang lưu (`110`); Đang đọc ảnh (`125`)
- `native/editbook/EditBookRepo.kt` (1): Bạn hãy thử lại. (`118`)
- `native/editbook/EditBookScreen.kt` (1): Tên gốc: {} (`180`)
- `native/editbook/EditModel.kt` (2): Bạn hãy nhập tên sách. (`56`); Bạn hãy nhập tên chương. (`57`)
- `native/export/ExportModel.kt` (9): Chương 1/{} · 0% (`282`); Đã xuất {} chương (`310`); File dở đã xoá (`323`); Đã dừng xuất (`329`); Đã dừng xuất M4B (`330`); Còn mới (`370`); Sách nói (`379`); Đang xuất · {}% (`389`); Đã xuất xong (`390`)
- `native/export/ExportRepo.kt` (1): Chọn thư mục để lưu trước (`86`)
- `native/export/ExportScreen.kt` (4): Xuất sách (`91`); Nơi lưu (`134`); Đã xuất (`175`); Xuất lại (`355`)
- `native/export/ExportState.kt` (1): Bạn hãy thử lại. (`102`)
- `native/music/MusicModel.kt` (1): Rất nhỏ (dễ nghe lời nhất) (`159`)
- `native/music/MusicPanel.kt` (1): Đang đóng (`245`)
- `native/music/MusicRepo.kt` (1): Chưa tìm được bài để đổi (`65`)
- `native/nowplaying/FakeNowPlayingModel.kt` (5): Chương 1 · Một buổi sớm (`70`); Những ngày gió hát (`70`); Chương {} · {} (`72`); Giọng thử A (`92`); Giọng thử B (`92`)
- `native/nowplaying/NowPlayingScreen.kt` (2): Về chế độ nghe (`98`); Cửa sổ mini (`169`)
- `native/nowplaying/PlayerSheets.kt` (2): Chọn giọng (`166`); Giọng thu sẵn (`166`)
- `native/screens/BookScreen.kt` (1): Tới chỗ đang nghe (`420`)
- `native/screens/BookSheets.kt` (2): Đang đóng file sách (`156`); Chương này chưa có audio. (`246`)
- `native/screens/SettingsAdvanced.kt` (2): Đang đo. (`59`); Đang đọc nhật ký. (`142`)
- `native/screens/SettingsGroups.kt` (1): Tự mở cửa sổ mini (`109`)
- `native/screens/SettingsParts.kt` (1): Sắp có (`89`)
- `native/screens/SettingsVoice.kt` (1): Đang lấy giọng (`274`)
- `native/voice/KeysScreen.kt` (1): Chưa đọc được các khoá (`35`)
- `native/voice/VoiceModel.kt` (3): Supertonic nhanh hơn (`219`); Có bản mới · {} (`293`); Đã có trên máy (`296`)
- `native/voice/VoiceSheets.kt` (7): Đang đo tốc độ (`84`); Đang xoá (`103`); Dữ liệu di động (`121`); Vẫn tải (`122`); Đang lưu (`135`); Đồng ý (`135`); Xoá bài này? (`299`)

### c2. Chỉ có ở web phía điện thoại - listen/, android/, shared/ (493 nhãn)

- `android/App.tsx` (5): Điều hướng (`189`); Nối máy (`215`); Đang tải về máy (`236`); Chiếm {} (`259`); Đóng thông báo (`416`)
- `android/DevicesScreen.tsx` (29): Đã kết nối với {} (`136`); Máy tính tìm thấy (`173`); Quyền Bluetooth (`210`); Để sau (`221`); Dùng Bluetooth (`228`); Máy tính đã ghép Bluetooth (`232`); Nhập địa chỉ (`260`); Tự tìm máy tính (`260`); Chưa huỷ được (`303`); Đang tải {} (`317`); Huỷ tải {} (`329`); Chưa đổi được (`370`); Vân tay (`403`); Thiết bị ở gần (`411`); Đã ghép {} (`467`); Chưa ghép được (`474`); Thiết bị khác (`505`); Ghép Bluetooth (`520`); Ghép (`582`); Tiếp tục (`699`); Chi tiết (`745`); Đã đổi tên thành “{}” (`827`); Chưa đổi được tên (`831`); Đổi tên (`846`); Để nguyên (`851`); ... +4
- `android/Diagnostics.tsx` (3): Không đọc được nhật ký (`33`); Chưa gửi được nhật ký (`43`); Chưa xoá được nhật ký (`54`)
- `android/ExportAudiobook.tsx` (2): Xuất sách nói “{}” (`254`); Để sau (`255`)
- `android/ExportM4b.tsx` (2): Xuất M4B “{}” (`157`); Để sau (`158`)
- `android/ExportMp3.tsx` (4): Đổi thư mục (`43`); Đã xuất {} chương{} (`78`); Xuất MP3 “{}” (`208`); Để sau (`209`)
- `android/ExportRevisions.tsx` (2): Xuất lại các chương đã đổi (`18`); Xuất lại cả file M4B (`19`)
- `android/LibraryDownloads.tsx` (1): Đang tải {} (`21`)
- `android/OldSaves.tsx` (5): Xoá bản lưu cũ? (`18`); Xoá (`29`); Chưa lưu ra được (`44`); Đã xoá bản lưu cũ (`53`); Lưu ra (`88`)
- `android/RemotePlayers.tsx` (8): Google Cast (`32`); Đang phát trên {} (`145`); Đang dừng trên (`151`); Đang phát trên (`151`); Đang mở trên {} (`288`); Phát trên {}{} (`305`); Phát trên thiết bị khác (`321`); Phát trên (`332`)
- `android/SettingsScreen.tsx` (5): Bản lưu cũ ({}) (`298`); Xem (`312`); Xoá (`328`); Cập nhật (`373`); Có bản mới {} (`374`)
- `android/StudioOpen.tsx` (2): Chưa ghép với máy tính nào (`32`); Mở Studio của máy nào? (`123`)
- `android/UpdateNotice.tsx` (2): Không mở được trình duyệt (`11`); Có ABook {} cho điện thoại (`21`)
- `android/backLayers.ts` (1): Escape (`48`)
- `android/downloads.ts` (1): Tải bị gián đoạn (`40`)
- `android/imports.ts` (10): Không mở được file (`17`); File không có sách nào. (`25`); Không mở được file sách (`25`); File này có bản thu khác (`30`); Thay bằng file này (`32`); Chưa thay được sách (`33`); Đã thêm sách vào Thư viện (`42`); Đã thêm “{}” (`42`); Mở sách (`43`); Không mở được bộ chọn file (`57`)
- `android/localStudio.ts` (1): Lỗi {} (`25`)
- `android/nativeEngine.ts` (1): Chưa lưu được chỗ đang nghe (`53`)
- `android/plugins.ts` (3): EbookPlayer (`701`); ReadAloud (`702`); EbookLibrary (`703`)
- `android/textImport.ts` (3): Sách (`22`); Không đọc được file này. (`42`); Không đọc được PDF này: {} (`56`)
- `listen/AddBook.tsx` (10): Không mở được file sách này. (`296`); Mở cuốn đó (`315`); Đã thêm sách vào thư viện (`475`); Đã thêm từ file này rồi (`496`); Chọn lại (`548`); Thêm phần còn lại (`553`); Vẫn thêm bản mới (`560`); Bỏ và chọn lại (`612`); Đường dẫn file hay thư mục (`651`); Chưa đọc được (`814`)
- `listen/BookScreen.tsx` (69): Nghe {} (`150`); Tạm dừng {} (`150`); Đọc {} (chưa có audio) (`169`); Đã làm sẵn (`185`); Đọc chương này (`258`); Đổi tên chương (`268`); Danh sách chương (`290`); Dừng nghe thử (`341`); Chưa có giọng (`425`); Chờ áp dụng (`430`); Đang chờ máy làm sách (`430`); Bỏ gộp {} vào {} (`440`); Bỏ gộp (`445`); Nghe {} nói (`458`); Đổi giọng {} (`460`); Gộp vào người khác (`477`); Đổi tên (`482`); Đổi giới tính (`487`); Chưa có dàn nhân vật (`539`); Người kể chuyện (`551`); Mặc định (`552`); Chờ áp dụng: giọng (`554`); Nghe giọng {} (`560`); Đổi giọng người kể (`561`); Vai chính (`564`); ... +44
- `listen/DropToAdd.tsx` (1): Thả để thêm sách (`36`)
- `listen/EditBook.tsx` (22): Chưa chỉnh được nhạc nền (`160`); Đã đổi tên sách (`332`); Đã bỏ tên tác giả (`337`); Đã đổi tác giả (`337`); Đã đặt ảnh bìa (`342`); Lưu tên (`410`); Lưu tác giả (`433`); Chọn ảnh bìa (`446`); Mở tab Nhạc nền (`468`); Tên riêng (`478`); Đã đổi tên chương: {} (`544`); Đã lưu file sách (`614`); Chưa lưu được file sách (`622`); Lưu thành (`685`); Loại file (`691`); Sách nghe (.abook) (`693`); Dự án (.abookproj) (`694`); Chọn thư mục (`711`); Mặc định: thư mục Đã xuất (`714`); Giọng và lời đọc (`732`); Làm ở Studio trên máy tính (`733`); Sửa ở máy gốc. (`748`)
- `listen/LibraryScreen.tsx` (21): Chỉ có chữ (`106`); Mở {} (`197`); Nghe ngay {} (`200`); Nghe {} (`200`); Tạm dừng {} (`200`); Đọc {} (`200`); Thêm {} (`240`); Nghe tiếp {}{} (`285`); Đang tạm dừng {} (`328`); Đang làm {} (`329`); Đang tạm dừng{} (`333`); Chưa có chương nghe được{} (`335`); Đang làm · {} (`335`); Sách (`372`); Mở bộ {} (`414`); Có sách trên máy khác (`422`); Lọc sách (`573`); Nghe xong (`575`); Xếp theo: {} (`583`); Gõ không dấu cũng được (`601`); Xoá ô tìm (`602`)
- `listen/LineWishes.tsx` (29): Người kể (`79`); Người nói: {} (`98`); Cách đọc câu - {} (`101`); Thu lại câu này (`103`); Các từ trong câu (`162`); Bỏ cách đọc “{}” (`194`); Bỏ (`200`); Đã ghi: câu này của {} (`315`); Chưa ghi được người nói (`321`); Chưa lấy lại được (`334`); Đã ghi cách đọc câu này (`337`); Chưa ghi được (`343`); Đã ghi: thu lại câu này (`362`); Không hoàn tác được (`372`); Không bỏ được thay đổi này (`388`); Cách đọc “{}”: “{}” (`397`); Ai nghĩ câu này? (`399`); Ai nói câu này? (`399`); Cách đọc câu này (`399`); Sửa câu này (`399`); Đọc từ này là (`399`); Đang chờ máy làm sách (`419`); Sửa cách đọc “{}” (`426`); Sửa (`434`); Bỏ: {} (`441`); ... +4
- `listen/MorningRecap.tsx` (12): Tối qua (`42`); Vừa hẹn giờ (`46`); Lần cuối chạm máy (`73`); Lần cuối dùng máy (`73`); Máy bắt đầu nằm yên (`75`); Tự dừng (`76`); Ẩn thẻ này (`156`); Nghe tới đâu rồi thiếp đi? (`165`); Nghe từ đây (`209`); Thu gọn (`213`); Tìm đúng câu (`213`); Chọn câu cuối cùng còn nhớ: (`221`)
- `listen/MyMusic.tsx` (9): Đang tải bài nhạc (`70`); Đang thêm nhạc thì dừng (`119`); Đã xoá khỏi Nhạc của tôi (`135`); Nhạc riêng (`152`); Đang tải nhạc riêng (`154`); Xoá bài: {} (`175`); Giữ lại: {} (`178`); Xoá (`183`); Xoá: {} (`183`)
- `listen/OnlineVoicePrompt.tsx` (4): Chọn giọng đọc (`37`); Nghe thử (`77`); Tải giọng chạy trên máy (`97`); Chọn giọng khác (`103`)
- `listen/PlayerViews.tsx` (53): Tốc độ đọc: {} (`90`); Giọng đọc: {} (`93`); Shift+← (`262`); Đã chọn tốc độ đọc {} (`465`); Phím (`480`); Đang chuẩn bị nhạc nền (`581`); Danh sách nhạc nền (`595`); Đang tải các danh sách nhạc (`621`); Kéo xuống còn giọng khác (`674`); Đã chọn giọng {} (`765`); Thử (`793`); Thêm giọng (`811`); Chưa làm trước được (`887`); Dừng làm trước (`901`); Làm trước chương sau (`907`); Làm trước {} chương tới (`907`); Chỉ khi đang sạc (`918`); Chưa xoá được bản đọc (`948`); Xoá bản đọc (`959`); Xoá (`962`); Hẹn giờ đã tắt tiếng lúc (`997`); Bật lại (`1006`); Tiếng nhỏ dần (`1014`); Hẹn giờ ngủ trên {} (`1080`); Dừng khi (`1100`); ... +28
- `listen/PlaylistChoice.tsx` (9): Nhạc nền: {} (`67`); Nhạc nền: để máy chọn{} (`67`); Đã lưu lựa chọn (`74`); Chưa chỉnh được mức nhạc (`92`); Đang thêm nhạc (`100`); Đang thêm nhạc {}/{} (`100`); Đang thêm nhạc thì dừng (`113`); Không mở được hộp chọn file (`115`); Đang tải danh sách (`200`)
- `listen/ProjectFileItems.tsx` (16): Mở dự án (`41`); Chưa dựng được xưởng (`44`); Cần cài Studio (card NVIDIA) - (`82`); Cần cập nhật Studio - (`82`); Studio cần sửa - (`82`); Mở dự án Studio (`103`); Tạo sách nói (`107`); Việc của xưởng (`135`); Mở xưởng đã dựng (`140`); Dựng xưởng (`143`); Việc cần duyệt (`191`); Kịch bản (`192`); Màn (`216`); Đang tải việc xưởng (`219`); Không còn việc nào cần quyết. (`257`); Ngoài ra: (`259`)
- `listen/ReadAlongText.tsx` (2): Nghe từ “{}” (`55`); Shift F10: sửa cách đọc. (`339`)
- `listen/ReadAloudStorage.tsx` (2): Đã dọn bản đọc đã làm (`52`); Chưa dọn được bản đọc (`56`)
- `listen/ReaderScreen.tsx` (9): Không mở được chương này (`279`); Về trang sách (`279`); Điều khiển đọc (`357`); Nghe từ đây (`365`); Cỡ chữ và giãn dòng (`370`); Cỡ chữ (`376`); Cỡ chữ {} (`380`); Giãn dòng (`392`); Chương tiếp theo (`459`)
- `listen/ReadingSuggestions.tsx` (4): Chưa đổi được phần đọc (`121`); Bỏ dòng khỏi phần đọc (`160`); Gợi ý cho phần đọc (`187`); Bỏ qua gợi ý (`223`)
- `listen/SendEdits.tsx` (2): Đặt lại bản của máy này (`107`); Đã hiểu (`113`)
- `listen/SentenceMenu.tsx` (9): Đã chép câu (`121`); Chưa chép được (`123`); Nghe từ đây (`140`); Nghe từ câu này (`141`); Sửa cách đọc (`156`); Sửa câu này (`171`); Sửa trong Studio (`171`); Chép câu (`175`); Bỏ chọn câu (`177`)
- `listen/Shortcuts.tsx` (11): Phát / tạm dừng (`17`); Space (`17`); Lùi / tới 15 giây (`18`); Chương trước / sau (`19`); Shift (`19`); Tắt / bật tiếng (`20`); Giảm / tăng tốc độ đọc (`21`); Esc (`22`); Thu nhỏ màn hình đang nghe (`22`); Xem các phím tắt này (`23`); Phím tắt (`86`)
- `listen/VieneuDownload.tsx` (3): Chưa tải được giọng VieNeu (`35`); Đang tải giọng VieNeu (`60`); Xem trong Cài đặt (`108`)
- `listen/VieneuModuleCard.tsx` (10): Bộ giọng (`89`); Tải, đo và quản lý (`101`); Đã chuyển sang giọng VieNeu Nano (`204`); Đã chuyển sang giọng trực tuyến (`204`); Đang tải {} (`237`); Chưa huỷ được việc tải {} (`239`); Đã có (`271`); Đã có sẵn (`271`); Chưa đổi được cách đọc (`291`); Dùng bản tăng tốc (`293`)
- `listen/VoiceSettings.tsx` (6): Tô đúng từng chữ đang đọc. (`187`); Nhận khoá (`189`); Đang tải giọng đọc (`284`); Mặc định (`332`); Dừng nghe thử {} (`334`); Nghe thử (`344`)
- `listen/VoiceSpeedSetting.tsx` (2): Chưa đổi được tốc độ giọng (`63`); Chưa tải được bản nhanh hơn (`72`)
- `listen/WishesDialog.tsx` (5): Không bỏ được thay đổi này (`46`); Việc chờ Studio (`52`); Việc chờ gửi (`52`); Đang xem các thay đổi (`69`); Chưa có việc nào đang chờ. (`73`)
- `listen/WordReadings.tsx` (9): Dừng nghe thử (`35`); Nghe thử (`43`); Không hoàn tác được (`76`); Đọc từ này là (`149`); Gõ cách đọc cho (`156`); Các từ trong câu (`167`); Nối thành cụm (`193`); Bấm một chữ để chọn. (`205`); Sửa cách đọc (`278`)
- `listen/bookSearch.ts` (1): Máy chủ không trả chương nào (`112`)
- `listen/clip.tsx` (1): Chưa nghe thử được (`92`)
- `listen/follow.ts` (6): ArrowDown (`66`); ArrowUp (`66`); End (`66`); Home (`66`); PageDown (`66`); PageUp (`66`)
- `listen/importQueue.ts` (3): Đã thêm từ file này rồi (`110`); Đã thêm {} sách (`134`); Không thêm cuốn nào (`141`)
- `listen/labels.ts` (14): Đang chuẩn bị giọng đọc (`9`); Đã nghe hết cả cuốn (`27`); Đã nghe {} {} · {} (`31`); Chưa nghe · {} chương (`63`); Nghe tiếp · {} (`82`); Đang tải âm thanh (`88`); Đây là chương cuối (`102`); Chương sau chưa có audio (`103`); Shift+→ (`103`); Đang thu âm (`113`); Bấm (`124`); Chạm (`124`); Nghe bằng giọng đọc.{} (`146`); Các chương sau chưa có audio. (`168`)
- `listen/lineWishData.tsx` (1): Đang chờ máy làm sách (`40`)
- `listen/liveClip.ts` (2): Đã bỏ đoạn này. (`156`); Giọng đọc không phản hồi. (`192`)
- `listen/liveTestKit.ts` (1): QuotaExceeded (`12`)
- `listen/model.ts` (3): Phần {} · {} (`364`); Dự án (`497`); Đã nhập (`497`)
- `listen/musicBed.ts` (1): Content-Type (`139`)
- `listen/onlineConsent.ts` (1): Microsoft (`14`)
- `listen/player.tsx` (8): Đã tới câu chọn (`577`); Đã tới {} (`577`); Chưa tải được nhạc (`637`); Đã nghe hết sách (`950`); Chương sau chưa có audio (`1164`); Đọc chương ấy (`1166`); Nghe thêm {} phút (`1259`); Vẫn đang nghe (`1723`)
- `listen/playlistBed.ts` (1): Đã thêm {} bài (`357`)
- `listen/prepareAhead.ts` (8): Chưa lưu bản đọc nào. (`73`); Vừa chỗ trống cho {} chương: (`145`); Đã sẵn sàng {}/{} chương (`162`); Đang làm trước {}{}: {}/{} đoạn{}. (`169`); Đã làm trước {}{}: {}{}. (`175`); Làm trước bị dừng. (`177`); Đã dừng làm trước ({}{}). (`178`); Đã dừng làm trước. (`178`)
- `listen/readAloud.ts` (4): Không tải được đoạn giọng đọc. (`58`); ReadAloudEngine cần track.speech (`485`); Không phát được clip giọng đọc. (`1772`); Giọng đọc không phản hồi. (`1943`)
- `listen/readAloudVoice.ts` (8): Không có mạng - giọng (`33`); Giọng {} đang không dùng được. (`48`); Ngọc Linh (`204`); Phạm Tuyên (`204`); Thanh Bình (`204`); Mỹ Duyên (`205`); Ái Hân (`205`); Đức Trí (`205`)
- `listen/readings.ts` (1): Chưa nghe thử được lúc này. (`161`)
- `listen/saveFailure.ts` (1): Chưa lưu được chỗ đang nghe (`16`)
- `listen/sleep.ts` (2): Hẹn giờ ngủ: còn {} giây (`84`); Hẹn giờ ngủ: còn {} phút (`84`)
- `listen/vieneuModule.ts` (3): Đang đọc bằng bản thường. (`131`); Đang đọc bằng bản tăng tốc. (`133`); Đang tải {} (`302`)
- `listen/voiceGroups.ts` (2): Nam (`23`); Nữ (`23`)
- `shared/BookCover.tsx` (1): Chữ bìa trên hoạ tiết sóng (`74`)
- `shared/ChapterPreview.tsx` (2): Đưa vào sách: {} (`91`); Bấm để đổi tên chương (`131`)
- `shared/CoverSearch.tsx` (3): Google Books (`12`); Open Library (`12`); Đã đặt ảnh bìa (`76`)
- `shared/DiagnosticsView.tsx` (2): Chi tiết kỹ thuật (`26`); Nhật ký của ABook ({} dòng) (`29`)
- `shared/ErrorDetails.tsx` (1): Chi tiết (`9`)
- `shared/MissingLibrary.tsx` (3): Chọn lại thư mục thư viện (`19`); Không thấy thư mục thư viện (`19`); Chọn thư mục (`27`)
- `shared/OnComputerOnly.tsx` (1): Làm (`16`)
- `shared/RowBoundary.tsx` (1): Hàng danh sách lỗi (`13`)
- `shared/SettingsNav.tsx` (3): Nhóm cài đặt (`52`); Về Cài đặt (`79`); Tìm hiểu thêm (`123`)
- `shared/ToastDetails.tsx` (2): Chi tiết (`38`); Chi tiết thông báo (`42`)
- `shared/diagnostics.ts` (16): Tải sách (`50`); Xuất sách nói (`50`); Việc nền (`58`); Việc {} (`59`); Pha: {} (`61`); Bản ABook (`103`); Điện thoại (`107`); Giờ trên máy (`111`); Pin (`115`); Mạng (`119`); Chỗ trống (`125`); Chạy nền (`130`); Cho máy khác nghe thư viện (`146`); Lần tắt gần nhất (`150`); Lần văng (`154`); Phục hồi dữ liệu (`155`)
- `shared/editsKept.ts` (1): Đã gộp {} sửa từ file (`12`)
- `shared/editsSync.ts` (2): Đã gửi về {} {} (`70`); Đã gửi về {} (`77`)
- `shared/latestRequest.ts` (1): AbortError (`20`)
- `shared/musicLevels.ts` (1): Rất nhỏ (`10`)
- `shared/pdfPages.ts` (1): PasswordException (`38`)
- `shared/peerStudio.ts` (1): Đang mở Studio của {} (`52`)
- `shared/trashUndo.ts` (3): Đã khôi phục “{}” (`16`); Chưa mang theo chỗ nghe. (`24`); Chưa hoàn tác được (`98`)
- `shared/ui.tsx` (2): Xem các tab trước (`515`); Xem các tab sau (`520`)
- `shared/unpair.ts` (1): Đã bỏ ghép {} (`35`)

### c3. Chỉ có ở web phía máy tính / Studio (chỉ đếm)

| thư mục | nhãn |
|---|---|
| desktop/ | 235 |
| studio/ | 729 |

## d. Chữ hoa, dấu câu, `…` và `...`, dấu thanh, số

**d1. Cùng nhãn (theo khoá lỏng) nhưng khác nguyên văn giữa hai phía** (21):

| web | native | khác ở | nơi |
|---|---|---|---|
| Chưa bỏ được ảnh bìa | Chưa bỏ được ảnh bìa. | dấu câu cuối | `listen/EditBook.tsx:348` (+1) ~ `native/editbook/BookEditor.kt:85` |
| Chưa gửi được về {} | Chưa gửi được về {}. | dấu câu cuối | `listen/SendEdits.tsx:43` ~ `native/editbook/BookEditor.kt:104` |
| Chưa thêm được sách | Chưa thêm được sách. | dấu câu cuối | `listen/AddBook.tsx:481` ~ `native/addbook/ImportQueue.kt:82` |
| Chưa đặt được ảnh bìa | Chưa đặt được ảnh bìa. | dấu câu cuối | `listen/EditBook.tsx:343` (+1) ~ `native/editbook/BookEditor.kt:85` |
| Chưa đọc lại được file | Chưa đọc lại được file. | dấu câu cuối | `listen/AddBook.tsx:388` ~ `native/addbook/ImportQueue.kt:60` |
| Chưa đổi được tác giả | Chưa đổi được tác giả. | dấu câu cuối | `listen/EditBook.tsx:338` ~ `native/editbook/EditModel.kt:66` |
| Chưa đổi được tên chương | Chưa đổi được tên chương. | dấu câu cuối | `listen/EditBook.tsx:547` ~ `native/editbook/BookEditor.kt:90` (+1) |
| Chưa đổi được tên sách | Chưa đổi được tên sách. | dấu câu cuối | `listen/EditBook.tsx:333` ~ `native/editbook/EditModel.kt:65` |
| chờ Wi-Fi | Chờ Wi-Fi | chữ hoa | `listen/prepareAhead.ts:152` ~ `native/voice/VoiceSheets.kt:124` |
| Chữ của cả cuốn được gửi tới {} để đọc, bằn… | Chữ của cả cuốn được gửi tới {} để đọc, bằn… | dấu thanh / ký tự | `desktop/listenExport.ts:85` ~ `native/export/ExportModel.kt:195` |
| Giấy phép: | Giấy phép | dấu câu cuối | `listen/PlayerViews.tsx:1302` ~ `native/music/MusicPanel.kt:447` (+1) |
| vào {} | Vào {} | chữ hoa | `android/ExportMp3.tsx:77` ~ `native/export/ExportModel.kt:310` (+1) |
| {} - Đang dùng: {} ({}) | {} - Đang dùng: {} ({}). | dấu câu cuối | `listen/voiceSpeed.ts:68` ~ `native/data/SettingsRepo.kt:260` |
| Đang chuẩn bị… | Đang chuẩn bị | dấu câu cuối | `android/ExportM4b.tsx:43` (+2) ~ `native/export/ExportModel.kt:271` |
| Đang chờ mạng… | Đang chờ mạng | dấu câu cuối | `desktop/bookFileExport.ts:182` ~ `native/export/ExportModel.kt:254` |
| Đang làm file M4B… | Đang làm file M4B | dấu câu cuối | `desktop/bookFileExport.ts:37` (+1) ~ `native/export/ExportModel.kt:288` |
| Đang làm sách nói… | Đang làm sách nói | dấu câu cuối | `desktop/listenExport.ts:13` ~ `native/export/ExportModel.kt:282` (+1) |
| đang phát | Đang phát | chữ hoa | `android/RemotePlayers.tsx:361` (+1) ~ `native/devices/CompanionSurfaces.kt:68` (+1) |
| Đang tính độ dài… | Đang tính độ dài | dấu câu cuối | `android/ExportAudiobook.tsx:174` (+1) ~ `native/export/ExportScreen.kt:216` |
| đang xuất | Đang xuất | chữ hoa | `shared/diagnostics.ts:47` ~ `native/export/ExportModel.kt:389` |
| Đã xoá nhật ký | Đã xoá nhật ký. | dấu câu cuối | `android/Diagnostics.tsx:51` ~ `native/screens/SettingsAdvanced.kt:55` |

**d2. Kiểu viết theo phía** (số chữ khớp / tổng; chữ quét ở trên):

| kiểu | web | native |
|---|---|---|
| dấu ba chấm ASCII `...` | 8 / 5861 | 0 / 902 |
| dấu ba chấm `…` | 42 / 5861 | 0 / 902 |
| kết thúc bằng dấu chấm `.` | 989 / 5861 | 183 / 902 |
| kết thúc bằng `!` | 0 / 5861 | 0 / 902 |
| kết thúc bằng `:` | 55 / 5861 | 0 / 902 |
| dấu thanh kiểu cũ `oà oá uý` | 469 / 5861 | 89 / 902 |
| dấu thanh kiểu mới `òa óa úy` | 1 / 5861 | 0 / 902 |
| số thập phân dấu phẩy `1,5` | 1 / 5861 | 0 / 902 |
| số thập phân dấu chấm `1.5` | 0 / 5861 | 0 / 902 |
| nhân bằng `×` | 0 / 5861 | 0 / 902 |
| nhân bằng `x` sau số | 0 / 5861 | 0 / 902 |
| ngăn cách `·` | 132 / 5861 | 23 / 902 |
| ngăn cách ` - ` | 291 / 5861 | 41 / 902 |
| gạch dài `—`/`–` | 10 / 5861 | 1 / 902 |
| giờ `1:30` hay `1 giờ 30` | 4 / 5861 | 2 / 902 |
| dấu `%` dính số | 0 / 5861 | 1 / 902 |
| dấu `%` cách số | 0 / 5861 | 0 / 902 |

**d3. Nhãn ngắn bắt đầu bằng chữ thường** (web 155, native 0); 15 đầu mỗi phía:

- web: bạn đã chọn · (`listen/ProjectFileItems.tsx:292`); bắt đầu (`studio/NewProjectScreen.tsx:701`); bắt đầu ngay (`desktop/BookTemplates.tsx:107`); bắt đầu. (`studio/NewProjectScreen.tsx:708`); bỏ chọn (`studio/WorkInbox.tsx:1281`); chưa cài (`studio/ProjectScreen.tsx:818`); chưa nghe (`listen/BookScreen.tsx:819`); chưa phân tích tới (`studio/NameReadings.tsx:289`); chưa thu - không tốn gì (`studio/ApplyChanges.tsx:93`); chương (`listen/AddBook.tsx:700`); chương (`studio/NewProjectScreen.tsx:643`); chương (`studio/NewProjectScreen.tsx:895`); chương (`studio/NewProjectScreen.tsx:910`); chương (`studio/ProjectScreen.tsx:787`); chương (`studio/VolumeSplit.tsx:173`)
- native: (không có)

**d3b. Chữ dùng dấu thanh kiểu mới (`òa óa úy`) - kiểu thiểu số** (DESIGN.md chưa chọn kiểu nào); 12 đầu mỗi phía:

- web: Chữ của cả cuốn được gửi tới {} để đọc, bằng khóa của bạn -… (`desktop/listenExport.ts:85`)
- native: (không có)

**d4. web: cùng nhãn nhưng viết khác nhau trong chính phía này** (65); 15 đầu:

- `Ai nghĩ câu này` | `Ai nghĩ câu này?` (`listen/LineWishes.tsx:399`, `listen/LineWishes.tsx:461` (+2))
- `Ai nói câu này` | `Ai nói câu này?` (`listen/LineWishes.tsx:399`, `listen/LineWishes.tsx:461` (+4))
- `Buồn` | `buồn` (`studio/ScriptTab.tsx:184`, `studio/musicScenes.ts:29` (+1))
- `Bắt đầu` | `bắt đầu` | `bắt đầu.` (`android/ExportAudiobook.tsx:258`, `android/ExportM4b.tsx:161` (+6))
- `Bỏ ghép {}` | `Bỏ ghép {}?` (`android/DevicesScreen.tsx:1008`, `android/DevicesScreen.tsx:1024` (+7))
- `Chưa cài` | `Chưa cài.` | `chưa cài` (`desktop/SettingsScreen.tsx:516`, `studio/ProjectScreen.tsx:818` (+1))
- `Chưa có bài nào` | `chưa có bài nào` (`listen/MyMusic.tsx:142`, `listen/MyMusic.tsx:154` (+1))
- `Chưa ghép được` | `Chưa ghép được:` (`android/DevicesScreen.tsx:474`, `desktop/OtherComputers.tsx:101` (+1))
- `Chưa nghe` | `chưa nghe` (`listen/BookScreen.tsx:1145`, `listen/BookScreen.tsx:263` (+2))
- `Chưa nghe thử được` | `Chưa nghe thử được:` (`listen/clip.tsx:92`, `studio/TryReading.tsx:146`)
- `Chưa thêm được chữ sáng` | `Chưa thêm được chữ sáng.` (`studio/WordTimings.tsx:33`, `studio/WordTimings.tsx:42`)
- `Chương` | `chương` | `chương.` (`listen/AddBook.tsx:695`, `listen/AddBook.tsx:700` (+15))
- `Chương {}` | `chương {}` (`listen/ProjectFileItems.tsx:271`, `listen/ReadingSuggestions.tsx:52` (+4))
- `Chất lượng` | `chất lượng` (`desktop/SettingsScreen.tsx:96`, `studio/NewProjectScreen.tsx:1337` (+4))
- `Cuối chương` | `cuối chương` (`listen/FootnoteChoices.tsx:73`, `studio/credits.ts:80`)

**d4. native: cùng nhãn nhưng viết khác nhau trong chính phía này** (6); 15 đầu:

- `Chưa nghe thử được giọng này` | `Chưa nghe thử được giọng này.` (`native/voice/VoiceRepo.kt:106`, `native/voice/VoiceState.kt:297` (+1))
- `Lùi 15 giây` | `Lùi {} giây` (`native/nowplaying/NowPlayingScreen.kt:159`, `native/pip/PipParams.kt:47`)
- `Tới 15 giây` | `Tới {} giây` (`native/nowplaying/NowPlayingScreen.kt:161`, `native/pip/PipParams.kt:49`)
- `Xoá khoá` | `Xoá khoá?` (`native/voice/VoiceSheets.kt:251`, `native/voice/VoiceSheets.kt:275` (+1))
- `Xoá phần đã tải` | `Xoá phần đã tải?` (`native/components/Confirm.kt:95`, `native/voice/VoiceSheets.kt:100` (+2))
- `ĐANG NGHE` | `Đang nghe` (`native/nowplaying/NowPlayingScreen.kt:69`, `native/nowplaying/PlayerSheets.kt:144`)
## e. Cặp màn web <-> native (luật cứng, scripts/ui_parity_pairs.json)

Trong một cặp, mỗi nhãn ngắn phải có ở cả hai phía (khoá lỏng) trừ khi nằm trong `allow` (nền tảng bắt buộc khác, có lý do) hay `missing` (tính năng / phần màn chỉ có ở một phía - Lead xếp lịch). Cột lệch phải bằng 0 thì `--check` mới qua.

| cặp | nhãn web | nhãn native | lệch web | lệch native | cho phép | thiếu thật |
|---|---|---|---|---|---|---|
| now-playing | 101 | 41 | 0 | 0 | 23 | 50 |
| shared-labels | 30 | 625 | 0 | 0 | 7 | 12 |
| library-book | 194 | 81 | 0 | 0 | 27 | 118 |
| settings | 126 | 98 | 0 | 0 | 4 | 39 |
| devices | 142 | 134 | 0 | 0 | 4 | 80 |
| voice | 133 | 102 | 0 | 0 | 21 | 59 |
| add-edit-book | 173 | 110 | 0 | 0 | 68 | 39 |

Thiếu thật ở native - `now-playing`: Bật lại; Chưa làm trước được; Chưa xoá được bản đọc; Chương này chưa có audio hoàn chỉnh - đ…; Chỉ khi đang sạc; Chọn giọng khác; Dừng; Dừng khi; Dừng làm trước; Dừng phát sau; Giữ lại; Gợi ý đọc; Hẹn giờ đã tắt tiếng lúc; Hết giờ thì {} tạm dừng, chỗ đang nghe …; Kéo xuống còn giọng khác; Làm trước chương sau; Làm trước {} chương tới; Nghe cuốn khác; Nghe kiểm; Nghe lại từ đầu; Nghe tiếp; Nghe tiếp từ đó; Nghe tiếp {}; Nghe {}; Sáng hôm sau, thẻ “Tối qua” giúp tìm lạ…; Sắp tắt ·; Sẽ dừng khi hết chương này.; Thêm giọng; Thử; Tiếng nhỏ dần; Tải giọng VieNeu; Tắt sau; Về thư viện; Xoá; Xoá bản đọc; Đang làm trước cho một cuốn hay giọng k…; Đang tải các danh sách nhạc; Đã nghe chương này; Đã nghe hết cuốn này.; Đã nghe hết phần đã có

Thiếu thật ở web - `now-playing`: Chưa tải được chữ. Bạn thử lại.; Chương chưa có chữ. Bạn thử lại sau.; Chọn giọng; Giọng thu sẵn; Về chế độ nghe; Đang chọn

Thiếu thật ở native - `shared-labels`: Chưa có audio; bạn vẫn đọc được chữ.; Chương sau chưa có audio; Chương tiếp theo sẽ nghe được khi máy l…; Các chương sau chưa có audio.; Nghe bằng giọng đọc.{}; Nghe tiếp · {}; Đang chuẩn bị giọng đọc; Đang thu âm; Đang tải âm thanh; Đây là chương cuối; Đã nghe hết cả cuốn; Đã nghe {} {} · {}

Thiếu thật ở native - `library-book`: Bỏ gộp; Bỏ gộp {} vào {}; Chiếm {}; Chuyển; Chuyển hồ sơ; Chuyển sang cuốn; Chuyển sang cuốn khác; Chưa có chương nghe được{}; Chưa có dàn nhân vật; Chưa có giọng; Chưa có lịch sử nghe; Chưa hoàn tác được; Chưa mang theo chỗ nghe.; Chưa tải được; Chưa xếp lại hàng chờ làm sách.; Chưa đủ chương; mở file sách mới hơn để…; Chưa đủ chương; đang dừng thu.; Chương sau; Chương tiếp theo; Chương trước; Chỉ có chữ; Chọn cuốn; Chọn câu cuối cùng còn nhớ:; Chờ áp dụng; Chờ áp dụng: giọng; Có sách trên máy khác; Cỡ chữ; Cỡ chữ và giãn dòng; Cỡ chữ {}; Dàn nhân vật hiện ra khi truyện đã được…; Dừng; Dừng nghe thử; Giãn dòng; Gộp vào người khác; Hiện chương sau; Huỷ; Hôm nay; Hôm qua; Hẹn giờ ngủ; Hồ sơ mới

Thiếu thật ở web - `library-book`: Chương này chưa có audio.; Chương {}; Sách chưa có chương nào nghe được trên …; Sắp có; Tới chỗ đang nghe; Đang xoá; Đang đóng file sách; Đã xoá khỏi điện thoại

Thiếu thật ở native - `settings`: Bản lưu cũ ({}); Bản trước của một lần lưu hỏng. Lưu ra …; Cho phép thông báo để biết khi sách xon…; Chưa dọn được bản đọc; Chưa gửi được nhật ký; Chưa lưu bản đọc nào.; Chưa lưu ra được; Chưa xoá được; Chưa xoá được nhật ký; Cài đè; sách và chỗ đang nghe giữ nguyê…; Có ABook {} cho điện thoại; Có bản mới {}; Cập nhật; Không mở được trình duyệt; Không đọc được nhật ký; Làm trước bị dừng.; Làm trước để nghe khi không có mạng{}.; Lưu ra; Máy đọc chậm? Làm trước để nghe liền mạ…; Mở; Mở Cài đặt; Nghe lại đoạn đã đọc xong thì không phả…; Tìm hiểu thêm; Tải; Vừa chỗ trống cho {} chương:; Xem; Xoá; Xoá bản lưu cũ?; Xoá {} bản đọc của cuốn này? Nghe tới đ…; Đang làm trước {}{}: {}/{} đoạn{}.; Đã dọn bản đọc đã làm; Đã dừng làm trước.; Đã dừng làm trước ({}{}).; Đã làm trước {}{}: {}{}.; Đã sẵn sàng {}/{} chương; Đã xoá bản lưu cũ

Thiếu thật ở web - `settings`: Sắp có; Đang đo.; Đang đọc nhật ký.

Thiếu thật ở native - `devices`: Bật lại trong Cài đặt của máy > Ứng dụn…; Bật Điều khiển từ xa trên máy tính.; Chi tiết; Cho phép; Cho phép “Thiết bị ở gần” để tìm máy đã…; Chưa ghép với máy tính nào; Chưa ghép được; Chưa huỷ được; Chưa đổi được; Chưa đổi được tên; Chỉ tìm máy đã ghép Bluetooth để nhận s…; Các máy tính đã ghép đều chỉ cho nghe -…; Dùng Bluetooth; Ghép; Ghép Bluetooth; Google Cast; Khi chia sẻ, ABook giữ một thông báo nh…; Máy kia chưa tự thấy điện thoại? Địa ch…; Máy tính tìm thấy; Máy tính {} và {} đều chỉ cho nghe - tr…; Máy tính đã ghép Bluetooth; Mở Studio của máy nào?; Nhập địa chỉ; Phát trên; Phát trên thiết bị khác; Phát trên {}{}; Quyền Bluetooth; Sách máy kia hiện trong Thư viện.; Thiết bị khác; Thiết bị ở gần; Tiếp tục; Tên; Tải bị gián đoạn; Tự tìm máy tính; Vân tay; Đang dừng trên; Đang mở trên {}; Đang phát trên; Đang phát trên {}; Điện thoại này

Thiếu thật ở web - `devices`: Bluetooth; Chưa có gì trên máy; Chưa mở được Studio; Chưa nối; Chưa phát sách; Chưa thấy; Chưa thấy máy khác. Bạn kiểm tra kết nố…; Chọn nơi phát; Cách nối; Còn trống {}; Huỷ; Máy tính; Máy đã ghép; Máy đã nối; Phát ở đây; Sách trên {}; Thấy {}; Tìm lại thiết bị phát; Wi-Fi; Đang bật; Đang bật · {} máy; Đang bỏ ghép; Đang dừng; Đang gửi lệnh; Đang kiểm tra; Đang lưu; Đang mở Studio; Đang nối {}; Đang phát; Đang tắt; Đã nối {}; Địa chỉ máy tính

Thiếu thật ở native - `voice`: Bản tăng tốc sẽ dùng từ lần đọc kế.; Bản tăng tốc: máy này không chạy được (…; Bộ giọng; Chưa cuốn nào dùng giọng này. Bạn tải l…; Chưa huỷ được việc tải {}; Chưa tải được bản nhanh hơn; Chưa tải được giọng VieNeu; Chưa đổi được cách đọc; Chưa đổi được tốc độ giọng; Chọn giọng khác; Chọn giọng đọc; Các câu đã thu vẫn nghe được.; Dùng bản tăng tốc; Dừng; Giọng của máy đọc ngay trên máy này, kh…; Giọng Edge gửi chữ của sách tới máy chủ…; Giọng {} gửi chữ của sách tới {} bằng k…; Máy này chưa chạy được bản tăng tốc, đa…; Mặc định; Nam; Nghe; Nghe thử; Nhận khoá; Nên dùng {}; chỉ cần tải một bộ giọng.; Nữ; Tô từng chữ đang đọc theo ước lượng.; Tô đúng từng chữ đang đọc.; Tải giọng chạy trên máy; Tải, đo và quản lý; Xem trong Cài đặt; Đang tải giọng VieNeu; Đang tải {}; Đang đọc bằng bản thường.; Đang đọc bằng bản tăng tốc.; Đã chuyển sang giọng trực tuyến; Đã chuyển sang giọng VieNeu Nano; Đã có; Đã có sẵn; Đã lưu khoá. Bấm “Kiểm tra” để thử.

Thiếu thật ở web - `voice`: Chưa đọc được các khoá; Chưa đổi được giọng; Chờ Wi-Fi; Có bản mới · {}; Dữ liệu di động; Hiện; Khoá {} sẽ bị xoá khỏi máy này và các g…; Phần đã tải dở sẽ bị xoá khỏi máy này.; Supertonic nhanh hơn; Vẫn tải; Xoá bài này?; Đang gỡ; Đang kiểm tra; Đang lưu; Đang lấy giọng; Đang xoá; Đang đo tốc độ; Đã có trên máy; Đồng ý; Ẩn

Thiếu thật ở native - `add-edit-book`: Bạn đã thêm file này thành “{}” ({} chư…; Bỏ và chọn lại; Chưa làm được; Chưa nối được {}. Thử lại hoặc chọn ảnh…; Chưa thay được sách; Chỉnh sửa và chỗ nghe của bạn vẫn được …; Chọn ảnh bìa; Còn {} cuốn chưa thêm vào thư viện. Chọ…; Còn {} thay đổi chưa gửi được - sẽ thử …; File không có sách nào.; File này chưa có chương nào để thêm.; File này chưa có tên sách - thêm riêng …; File này có bản thu khác; File này không có chữ để đọc.; Giọng và lời đọc; Google Books; Không mở được file; Không mở được file sách; Không thêm cuốn nào; Làm ở Studio trên máy tính; Mở cuốn đó; Mở sách; Open Library; Sửa ở máy gốc.; Thay bằng file này; Thêm phần còn lại; Tên trong file là “{}”, khác tên đang d…; Tự gửi khi {} trả lời lại; bấm “Gửi về …; Vẫn thêm bản mới; Đã gửi về {}; Đã gửi về {} {}; Đã hiểu; Đã thêm sách vào Thư viện; Đã thêm từ file này rồi; Đã thêm {} sách; Đã thêm “{}”; Đường dẫn file hay thư mục; Đặt lại bản của máy này; Đổi có hiệu lực ngay trên máy tính {} -…


<!-- ui_parity:end -->
