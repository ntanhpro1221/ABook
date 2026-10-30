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

Quét: web 5861 chữ (3269 khác nhau), 378 cặp nhãn-icon; native 1319 chữ (1033 khác nhau), 73 cặp nhãn-icon. Nhãn so theo khoá lỏng (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối).

## a. Cùng việc, khác chữ

Cặp nhãn ngắn (<= 6 chữ) mà phía kia KHÔNG có nguyên văn nhưng có nhãn giống (chung từ, gần nhau, hay chung icon). 177 cặp; 40 cặp đầu theo độ giống. `icon` = cùng icon lucide.

| native | web | giống | nơi |
|---|---|---|---|
| Chưa có chương nghe được | Chưa có chương nghe được{} | 1.00 | `native/data/Production.kt:53` ~ `listen/LibraryScreen.tsx:335` |
| Chọn giọng | Chọn một giọng | 1.00 | `native/nowplaying/PlayerSheets.kt:191` ~ `studio/NewProjectScreen.tsx:1273` |
| Không có ai khớp “{}”. | Không có ai khớp “ | 1.00 | `native/screens/BookPeople.kt:224` ~ `studio/MergePeople.tsx:127` |
| Nghe tiếp từ {} | Nghe tiếp từ | 1.00 | `native/data/ListenExtras.kt:98` ~ `listen/BookScreen.tsx:676` |
| Nghe tiếp từ {} | Nghe tiếp · {} | 1.00 | `native/data/ListenExtras.kt:98` ~ `listen/labels.ts:82` |
| Tên gốc: {} | Tên gốc: | 1.00 | `native/addbook/BookForms.kt:97` (+2) ~ `studio/CastEdits.tsx:88` |
| Đã xuất | Xuất | 1.00 | `native/export/ExportScreen.kt:175` ~ `studio/ExportBook.tsx:385` (+2) |
| Đã xuất {} chương | Đã xuất {} chương{} | 1.00 | `native/export/ExportModel.kt:312` ~ `android/ExportMp3.tsx:78` |
| Chưa mở được Studio | Chưa gỡ được Studio | 0.95 | `native/devices/DevicesRepo.kt:145` ~ `studio/StudioSetup.tsx:359` |
| Đang đo. | Đang đổi | 0.93 | `native/screens/SettingsAdvanced.kt:61` ~ `studio/MusicTab.tsx:230` |
| Đã xoá khỏi điện thoại | Xoá {} khỏi điện thoại | 0.93 | `native/data/UndoDelete.kt:155` ~ `android/DevicesScreen.tsx:908` (+1) |
| Cắt ảnh bìa | Đặt ảnh bìa | 0.91 | `native/editbook/CoverCrop.kt:108` ~ `studio/CoverEditor.tsx:112` (+1) |
| Đang đóng | Đang dùng | 0.89 | `native/music/MusicPanel.kt:245` ~ `studio/VoicePicker.tsx:339` (+1) |
| Sách nói | Sách mới | 0.88 | `native/export/ExportModel.kt:381` ~ `desktop/SettingsScreen.tsx:410` |
| Đang mở Studio | Đang mở Studio của {} | 0.88 | `native/devices/DeviceSheets.kt:76` ~ `shared/peerStudio.ts:52` |
| Đang nối {} | Đang đổi | 0.88 | `native/devices/PairScreen.kt:194` ~ `studio/MusicTab.tsx:230` |
| Chọn giọng | Đã chọn giọng {} | 0.87 | `native/nowplaying/PlayerSheets.kt:191` ~ `listen/PlayerViews.tsx:764` |
| Đang đọc ảnh | Đang đọc là: | 0.87 | `native/editbook/CoverCrop.kt:125` ~ `studio/ReviewQueue.tsx:246` |
| Đang đóng file sách | Đang đóng gói sách… | 0.86 | `native/screens/BookSheets.kt:190` ~ `desktop/bookFileExport.ts:28` (+1) |
| Chọn giọng | Chung giọng | 0.86 | `native/nowplaying/PlayerSheets.kt:191` ~ `studio/WorkInbox.tsx:152` |
| Vẫn tải | Vẫn cài | 0.86 | `native/voice/VoiceSheets.kt:124` ~ `studio/StudioSetup.tsx:227` (+1) |
| Đang ghi | Đã ghi | 0.86 | `native/screens/BookPeople.kt:184` ~ `studio/ScriptTab.tsx:1149` (+2) |
| Đang ghi | Đã ghi “{}” - {}. | 0.86 | `native/screens/BookPeople.kt:184` ~ `studio/WorkInbox.tsx:346` |
| Đang ghi | Đã ghi: {} | 0.86 | `native/screens/BookPeople.kt:184` ~ `studio/WorkInbox.tsx:467` (+4) |
| Đang lấy giọng | Đang tải giọng ({}) {}% | 0.86 | `native/screens/SettingsVoice.kt:287` ~ `studio/voiceEngines.ts:81` |
| Đã xuất | Đề xuất | 0.86 | `native/export/ExportScreen.kt:175` ~ `studio/NewProjectScreen.tsx:1016` |
| Đang mở Studio | Đã gỡ Studio | 0.85 | `native/devices/DeviceSheets.kt:76` ~ `studio/StudioSetup.tsx:356` |
| Đã xuất xong | Đã xuất {} chương{} | 0.85 | `native/export/ExportModel.kt:392` ~ `android/ExportMp3.tsx:78` |
| Tìm lại thiết bị phát | Hỏi lại thư viện | 0.84 · icon | `native/devices/CompanionSurfaces.kt:123` ~ `desktop/OtherComputers.tsx:228` (+1) |
| Địa chỉ máy tính | Địa chỉ máy kia | 0.84 | `native/devices/PairScreen.kt:177` ~ `desktop/OtherComputers.tsx:285` |
| Chọn thư mục để lưu trước | Chọn thư mục trước | 0.84 | `native/export/ExportRepo.kt:85` ~ `desktop/LibraryMoveRecovery.tsx:36` |
| Đã nối {} | Ai nói? | 0.83 | `native/devices/DevicesState.kt:69` ~ `studio/ScriptTab.tsx:625` |
| Đã nối {} | Đã tới {} | 0.83 | `native/devices/DevicesState.kt:69` ~ `listen/player.tsx:577` |
| Bạn hãy thử lại. | Bật và thu lại | 0.83 | `native/addbook/ImportQueue.kt:149` (+8) ~ `studio/TellerModeSwitch.tsx:79` |
| Có bản mới · {} | Bản mới | 0.82 | `native/voice/VoiceModel.kt:302` ~ `desktop/SettingsScreen.tsx:182` (+1) |
| Dùng ảnh | Dừng nghe | 0.82 | `native/editbook/CoverCrop.kt:110` ~ `studio/MusicTab.tsx:225` (+1) |
| Dùng ảnh | Dừng nghe {} | 0.82 | `native/editbook/CoverCrop.kt:110` ~ `studio/NewProjectScreen.tsx:989` (+1) |
| Đang đóng | Đang đổi | 0.82 | `native/music/MusicPanel.kt:245` ~ `studio/MusicTab.tsx:230` |
| Chưa đọc được các khoá | Chưa đổi được cách đọc | 0.82 | `native/voice/KeysScreen.kt:35` ~ `listen/VieneuModuleCard.tsx:291` |
| Xuất sách | Xuất sách nói “{}” | 0.82 | `native/export/ExportScreen.kt:91` ~ `android/ExportAudiobook.tsx:254` (+3) |

## b. Cùng nhãn khác icon, cùng icon khác nhãn

**Cùng nhãn, khác icon** (0 nhãn có icon ở cả hai phía mà không chung icon nào):

| nhãn | web | native | nơi |
|---|---|---|---|
| (không có) | | | |

**Cùng icon, khác nhãn** (10 icon dùng ở cả hai phía mà không chung nhãn nào):

| icon | web | native |
|---|---|---|
| audio-lines | Chưa có giọng, Nghe lại | Chưa có dàn nhân vật |
| book-open-text | Dừng / Nghe thử, Không mở được chương này, Kịch bản chương này, Phân tích truyện | Không tìm thấy sách này |
| check | Duyệt câu, Giữ cả thẻ, Giữ thẻ, Tạm dừng {} | Chưa nghe, Chưa nghe xong, Đang lấy giọng |
| circle-dashed | Chưa nghe / Đã nghe xong, Tạm dừng {} | Chưa nghe, Chưa nghe xong |
| download | Cài Studio, Cài tiếp, Có ABook {}, Dừng tải / Tải tiếp | Cập nhật ({}), Tải ABook Windows |
| image-plus | Đổi ảnh bìa | Chọn ảnh |
| laptop | Máy kia không trả lời | Studio máy tính, Đang mở Studio |
| rotate-ccw-clock | Khôi phục, Khôi phục bản sao | Chưa có lịch sử nghe |
| share-2 | Chia sẻ | Đang đóng file sách |
| upload | Chọn file, Nhập nhạc, Thêm file, Thêm nhạc của bạn | Đang thêm {}/{} |

Phủ của bộ ghép: icon dùng ở 134 chỗ trong mã native, ghép được với nhãn chữ ở 71; web 554 chỗ, ghép được 326. Phần còn lại là icon không đi cùng nhãn chữ (nút chỉ icon, chỉ báo) hay nhãn dựng từ model (vd tên nhóm Cài đặt), nên KHÔNG có trong bảng.
Icon native chưa quy về lucide (3): `native:ChevronIcon`, `native:OtherPlayerIcon`, `native:PlayerGlyph`.
Số cặp: web 326, native 71; icon lucide dùng: web 98, native 38.

## c. Nhãn chỉ có ở một phía, theo màn

Nhãn ngắn (<= 6 chữ) không có (theo khoá lỏng) ở phía kia - kể cả chữ giống chữ ở mục a. Để phân biệt tính năng thiếu với chữ trôi: một màn native có nhiều nhãn chỉ-native mà web cùng màn không có thường là tính năng mới; vài nhãn lẻ thường là chữ trôi (mục a).

### c1. Chỉ có ở native (79 nhãn)

- `native/addbook/BookForms.kt` (1): Tên gốc: {} (`97`)
- `native/addbook/ImportQueue.kt` (1): Bạn hãy thử lại. (`149`)
- `native/addbook/ImportRepo.kt` (1): Bạn hãy nhập tên sách. (`97`)
- `native/components/Confirm.kt` (1): Đang xoá (`95`)
- `native/components/ListParts.kt` (1): Sắp có (`440`)
- `native/data/AndroidSettingsCore.kt` (1): Accept (`59`)
- `native/data/DemoPlayback.kt` (1): Chương {} · {} (`13`)
- `native/data/Library.kt` (1): Bạn hãy thử lại. (`161`)
- `native/data/ListenExtras.kt` (1): Nghe tiếp từ {} (`98`)
- `native/data/PrepareState.kt` (1): Chưa rõ vì sao (`74`)
- `native/data/Production.kt` (1): Chưa có chương nghe được (`53`)
- `native/data/UndoDelete.kt` (1): Đã xoá khỏi điện thoại (`155`)
- `native/devices/CompanionSurfaces.kt` (4): Chọn nơi phát (`40`); Đang gửi lệnh (`58`); Chưa phát sách (`71`); Tìm lại thiết bị phát (`123`)
- `native/devices/DeviceSheets.kt` (3): Đang mở Studio (`76`); Đang bỏ ghép (`137`); Đang lưu (`161`)
- `native/devices/DevicesModel.kt` (2): Chưa thấy (`313`); Thấy {} (`313`)
- `native/devices/DevicesRepo.kt` (1): Chưa mở được Studio (`145`)
- `native/devices/DevicesState.kt` (3): Chưa nối (`69`); Đã nối {} (`69`); Đang bật · {} máy (`71`)
- `native/devices/PairScreen.kt` (5): Máy đã nối (`113`); Sách trên {} (`138`); Cách nối (`170`); Địa chỉ máy tính (`177`); Đang nối {} (`194`)
- `native/devices/StorageScreen.kt` (2): Còn trống {} (`53`); Chưa có gì trên máy (`57`)
- `native/editbook/BookEditor.kt` (1): Bạn hãy thử lại. (`46`)
- `native/editbook/CoverCrop.kt` (5): Bạn hãy chọn lại ảnh bìa. (`105`); Cắt ảnh bìa (`108`); Dùng ảnh (`110`); Đang lưu (`110`); Đang đọc ảnh (`125`)
- `native/editbook/EditBookScreen.kt` (1): Tên gốc: {} (`182`)
- `native/editbook/EditModel.kt` (2): Bạn hãy nhập tên sách. (`57`); Bạn hãy nhập tên chương. (`58`)
- `native/export/ExportModel.kt` (9): Chương 1/{} · 0% (`284`); Đã xuất {} chương (`312`); File dở đã xoá (`325`); Đã dừng xuất (`331`); Đã dừng xuất M4B (`332`); Còn mới (`372`); Sách nói (`381`); Đang xuất · {}% (`391`); Đã xuất xong (`392`)
- `native/export/ExportRepo.kt` (1): Chọn thư mục để lưu trước (`85`)
- `native/export/ExportScreen.kt` (4): Xuất sách (`91`); Nơi lưu (`134`); Đã xuất (`175`); Xuất lại (`355`)
- `native/export/ExportState.kt` (1): Bạn hãy thử lại. (`103`)
- `native/music/MusicModel.kt` (1): Rất nhỏ (rõ lời) (`159`)
- `native/music/MusicPanel.kt` (1): Đang đóng (`245`)
- `native/music/MusicRepo.kt` (1): Chưa tìm được bài để đổi (`65`)
- `native/nowplaying/FakeNowPlayingModel.kt` (5): Chương 1 · Một buổi sớm (`80`); Những ngày gió hát (`80`); Chương {} · {} (`82`); Giọng thử A (`102`); Giọng thử B (`102`)
- `native/nowplaying/NowPlayingScreen.kt` (2): Về chế độ nghe (`120`); Cửa sổ mini (`193`)
- `native/nowplaying/PlayerSheets.kt` (2): Chọn giọng (`191`); Giọng thu sẵn (`191`)
- `native/screens/BookPeople.kt` (5): Tên gốc: {} (`134`); Đang lưu (`137`); Đang ghi (`184`); Không có ai khớp “{}”. (`224`); Đang gộp (`244`)
- `native/screens/BookSaveUi.kt` (1): Đang lưu (`133`)
- `native/screens/BookScreen.kt` (1): Tới chỗ đang nghe (`541`)
- `native/screens/BookSheets.kt` (3): Đang lưu (`185`); Đang đóng file sách (`190`); Chương này chưa có audio. (`287`)
- `native/screens/SettingsAdvanced.kt` (2): Đang đo. (`61`); Đang đọc nhật ký. (`153`)
- `native/screens/SettingsGroups.kt` (1): Tự mở cửa sổ mini (`109`)
- `native/screens/SettingsParts.kt` (1): Sắp có (`89`)
- `native/screens/SettingsVoice.kt` (1): Đang lấy giọng (`287`)
- `native/voice/KeysScreen.kt` (1): Chưa đọc được các khoá (`35`)
- `native/voice/VoiceModel.kt` (2): Supertonic nhanh hơn (`228`); Có bản mới · {} (`302`)
- `native/voice/VoiceSheets.kt` (7): Đang đo tốc độ (`86`); Đang xoá (`105`); Dữ liệu di động (`123`); Vẫn tải (`124`); Đang lưu (`137`); Đồng ý (`137`); Xoá bài này? (`302`)

### c2. Chỉ có ở web phía điện thoại - listen/, android/, shared/ (276 nhãn)

- `android/App.tsx` (3): Điều hướng (`189`); Đang tải về máy (`236`); Đóng thông báo (`416`)
- `android/DevicesScreen.tsx` (5): Đang tải {} (`317`); Huỷ tải {} (`329`); Thiết bị ở gần (`411`); Xoá phần đã tải của {} (`908`); Xoá {} khỏi điện thoại (`908`)
- `android/ExportAudiobook.tsx` (1): Xuất sách nói “{}” (`254`)
- `android/ExportM4b.tsx` (1): Xuất M4B “{}” (`157`)
- `android/ExportMp3.tsx` (3): Đổi thư mục (`43`); Đã xuất {} chương{} (`78`); Xuất MP3 “{}” (`208`)
- `android/ExportRevisions.tsx` (2): Xuất chương đã đổi (`18`); Xuất lại M4B (`19`)
- `android/LibraryDownloads.tsx` (1): Đang tải {} (`21`)
- `android/RemotePlayers.tsx` (1): Đang phát trên {} (`145`)
- `android/backLayers.ts` (1): Escape (`48`)
- `android/imports.ts` (1): Không mở được bộ chọn file (`57`)
- `android/localStudio.ts` (1): Lỗi {} (`25`)
- `android/nativeEngine.ts` (1): Chưa lưu được chỗ đang nghe (`53`)
- `android/plugins.ts` (3): EbookPlayer (`701`); ReadAloud (`702`); EbookLibrary (`703`)
- `android/textImport.ts` (3): Sách (`22`); Không đọc được file này. (`42`); Không đọc được PDF này: {} (`56`)
- `listen/AddBook.tsx` (4): Không mở được file sách này. (`296`); Chọn lại (`548`); Đường dẫn file hay thư mục (`651`); Chưa đọc được (`814`)
- `listen/BookScreen.tsx` (21): Tạm dừng {} (`150`); Đọc {} (chưa có audio) (`169`); Đọc chương này (`258`); Danh sách chương (`290`); Chờ áp dụng (`430`); Bỏ gộp {} vào {} (`440`); Bỏ gộp (`445`); Đổi giọng {} (`460`); Chờ áp dụng: giọng (`554`); Nghe giọng {} (`560`); Đổi giọng người kể (`561`); Từ phần trước (`589`); 7 ngày qua: (`654`); Nghe tiếp từ (`676`); Chuyển sang cuốn (`722`); Đang mở thư viện (`722`); Đọc (`1054`); Đọc tiếp (`1054`); Đã nghe {} (`1145`); Việc với sách (`1174`); Mục của sách (`1248`)
- `listen/DropToAdd.tsx` (1): Thả để thêm sách (`36`)
- `listen/EditBook.tsx` (11): Chưa chỉnh được nhạc nền (`160`); Đã đổi tên sách (`332`); Đã bỏ tên tác giả (`337`); Đã đổi tác giả (`337`); Đã đặt ảnh bìa (`342`); Lưu tên (`410`); Lưu tác giả (`433`); Mở tab Nhạc nền (`468`); Tên riêng (`478`); Chọn thư mục (`711`); Mặc định: thư mục Đã xuất (`714`)
- `listen/LibraryScreen.tsx` (13): Mở {} (`197`); Nghe ngay {} (`200`); Tạm dừng {} (`200`); Đọc {} (`200`); Thêm {} (`240`); Đang tạm dừng{} (`333`); Chưa có chương nghe được{} (`335`); Sách (`372`); Mở bộ {} (`414`); Lọc sách (`573`); Nghe xong (`575`); Xếp theo: {} (`583`); Gõ không dấu cũng được (`601`)
- `listen/LineWishes.tsx` (27): Người kể (`79`); Người nói: {} (`98`); Cách đọc câu - {} (`101`); Thu lại câu này (`103`); Các từ trong câu (`162`); Bỏ cách đọc “{}” (`194`); Bỏ (`200`); Đã ghi: câu này của {} (`315`); Chưa ghi được người nói (`321`); Chưa lấy lại được (`334`); Đã ghi cách đọc câu này (`337`); Chưa ghi được (`343`); Đã ghi: thu lại câu này (`362`); Không bỏ được thay đổi này (`388`); Cách đọc “{}”: “{}” (`397`); Ai nghĩ câu này? (`399`); Ai nói câu này? (`399`); Cách đọc câu này (`399`); Sửa câu này (`399`); Đọc từ này là (`399`); Sửa cách đọc “{}” (`426`); Sửa (`434`); Bỏ: {} (`441`); Đang chờ máy làm sách: {} (`470`); Hiện là {} (`471`); ... +2
- `listen/MorningRecap.tsx` (1): Lần cuối dùng máy (`73`)
- `listen/MyMusic.tsx` (8): Đang tải bài nhạc (`70`); Đang thêm nhạc thì dừng (`119`); Đã xoá khỏi Nhạc của tôi (`135`); Nhạc riêng (`152`); Đang tải nhạc riêng (`154`); Xoá bài: {} (`175`); Giữ lại: {} (`178`); Xoá: {} (`183`)
- `listen/PlayerViews.tsx` (23): Tốc độ đọc: {} (`91`); Giọng đọc: {} (`94`); Shift+← (`263`); Đã chọn tốc độ đọc {} (`464`); Phím (`479`); Đang chuẩn bị nhạc nền (`580`); Danh sách nhạc nền (`594`); Đang tải các danh sách nhạc (`620`); Đã chọn giọng {} (`764`); Chưa xoá được bản đọc (`947`); Xoá bản đọc (`958`); Hẹn giờ ngủ trên {} (`1079`); Âm lượng (`1183`); Âm lượng {}% (`1185`); Bật tiếng (`1195`); Tắt tiếng (`1195`); Nghe kiểm (`1337`); Đóng trình phát (`1670`); Esc (`2043`); Phím tắt (`2053`); Gợi ý đọc (`2054`); Điều khiển phụ (`2085`); Bảng (`2257`)
- `listen/PlaylistChoice.tsx` (9): Nhạc nền: {} (`67`); Nhạc nền: để máy chọn{} (`67`); Đã lưu lựa chọn (`74`); Chưa chỉnh được mức nhạc (`92`); Đang thêm nhạc (`100`); Đang thêm nhạc {}/{} (`100`); Đang thêm nhạc thì dừng (`113`); Không mở được hộp chọn file (`115`); Đang tải danh sách (`200`)
- `listen/ProjectFileItems.tsx` (16): Mở dự án (`41`); Chưa dựng được xưởng (`44`); Cần cài Studio (card NVIDIA) - (`82`); Cần cập nhật Studio - (`82`); Studio cần sửa - (`82`); Mở dự án Studio (`103`); Tạo sách nói (`107`); Việc của xưởng (`135`); Mở xưởng đã dựng (`140`); Dựng xưởng (`143`); Việc cần duyệt (`191`); Kịch bản (`192`); Màn (`216`); Đang tải việc xưởng (`219`); Không còn việc nào cần quyết. (`257`); Ngoài ra: (`259`)
- `listen/ReadAlongText.tsx` (2): Nghe từ “{}” (`55`); Shift F10: sửa cách đọc. (`339`)
- `listen/ReaderScreen.tsx` (3): Không mở được chương này (`264`); Về trang sách (`264`); Điều khiển đọc (`342`)
- `listen/ReadingSuggestions.tsx` (5): Chưa đổi được phần đọc (`121`); Bỏ dòng khỏi phần đọc (`160`); Xem lại gợi ý (`181`); Gợi ý cho phần đọc (`187`); Bỏ qua gợi ý (`194`)
- `listen/SendEdits.tsx` (1): Đã hiểu (`113`)
- `listen/SentenceMenu.tsx` (8): Đã chép câu (`121`); Chưa chép được (`123`); Nghe từ câu này (`141`); Sửa cách đọc (`156`); Sửa câu này (`171`); Sửa trong Studio (`171`); Chép câu (`175`); Bỏ chọn câu (`177`)
- `listen/Shortcuts.tsx` (11): Phát / tạm dừng (`17`); Space (`17`); Lùi / tới 15 giây (`18`); Chương trước / sau (`19`); Shift (`19`); Tắt / bật tiếng (`20`); Giảm / tăng tốc độ đọc (`21`); Esc (`22`); Thu nhỏ màn hình đang nghe (`22`); Xem các phím tắt này (`23`); Phím tắt (`86`)
- `listen/VieneuModuleCard.tsx` (3): Đang tải {} (`237`); Chưa đổi được cách đọc (`291`); Dùng bản tăng tốc (`293`)
- `listen/VoiceSettings.tsx` (2): Đang tải giọng đọc (`284`); Dừng nghe thử {} (`334`)
- `listen/WishesDialog.tsx` (5): Không bỏ được thay đổi này (`46`); Việc chờ Studio (`52`); Việc chờ gửi (`52`); Đang xem các thay đổi (`69`); Chưa có việc nào đang chờ. (`73`)
- `listen/WordReadings.tsx` (6): Đọc từ này là (`149`); Gõ cách đọc cho (`156`); Các từ trong câu (`167`); Nối thành cụm (`193`); Bấm một chữ để chọn. (`205`); Sửa cách đọc (`278`)
- `listen/bookSearch.ts` (1): Máy chủ không trả chương nào (`112`)
- `listen/clip.tsx` (1): Chưa nghe thử được (`92`)
- `listen/follow.ts` (6): ArrowDown (`66`); ArrowUp (`66`); End (`66`); Home (`66`); PageDown (`66`); PageUp (`66`)
- `listen/labels.ts` (3): Nghe tiếp · {} (`82`); Shift+→ (`103`); Bấm (`124`)
- `listen/liveClip.ts` (2): Đã bỏ đoạn này. (`156`); Giọng đọc không phản hồi. (`192`)
- `listen/liveTestKit.ts` (1): QuotaExceeded (`12`)
- `listen/model.ts` (3): Phần {} · {} (`364`); Dự án (`497`); Đã nhập (`497`)
- `listen/musicBed.ts` (1): Content-Type (`139`)
- `listen/onlineConsent.ts` (1): Microsoft (`14`)
- `listen/player.tsx` (6): Đã tới câu chọn (`577`); Đã tới {} (`577`); Chưa tải được nhạc (`637`); Đọc chương ấy (`1166`); Nghe thêm {} phút (`1259`); Vẫn đang nghe (`1723`)
- `listen/playlistBed.ts` (1): Đã thêm {} bài (`357`)
- `listen/prepareAhead.ts` (1): Chưa lưu bản đọc nào. (`73`)
- `listen/readAloud.ts` (4): Không tải được đoạn giọng đọc. (`58`); ReadAloudEngine cần track.speech (`485`); Không phát được clip giọng đọc. (`1772`); Giọng đọc không phản hồi. (`1943`)
- `listen/readAloudVoice.ts` (6): Ngọc Linh (`204`); Phạm Tuyên (`204`); Thanh Bình (`204`); Mỹ Duyên (`205`); Ái Hân (`205`); Đức Trí (`205`)
- `listen/readings.ts` (1): Chưa nghe thử được lúc này. (`161`)
- `listen/saveFailure.ts` (1): Chưa lưu được chỗ đang nghe (`16`)
- `listen/sleep.ts` (2): Hẹn giờ ngủ: còn {} giây (`84`); Hẹn giờ ngủ: còn {} phút (`84`)
- `listen/vieneuModule.ts` (3): Đang đọc bằng bản thường. (`132`); Đang đọc bằng bản tăng tốc. (`134`); Đang tải {} (`303`)
- `shared/BookCover.tsx` (1): Chữ bìa trên hoạ tiết sóng (`78`)
- `shared/ChapterPreview.tsx` (2): Đưa vào sách: {} (`91`); Bấm để đổi tên chương (`131`)
- `shared/CoverSearch.tsx` (3): Google Books (`12`); Open Library (`12`); Đã đặt ảnh bìa (`76`)
- `shared/DiagnosticsView.tsx` (2): Chi tiết kỹ thuật (`26`); Nhật ký của ABook ({} dòng) (`29`)
- `shared/MissingLibrary.tsx` (3): Chọn lại thư mục thư viện (`19`); Không thấy thư mục thư viện (`19`); Chọn thư mục (`27`)
- `shared/OnComputerOnly.tsx` (1): Làm (`16`)
- `shared/RowBoundary.tsx` (1): Hàng danh sách lỗi (`13`)
- `shared/SettingsNav.tsx` (2): Nhóm cài đặt (`52`); Về Cài đặt (`79`)
- `shared/ToastDetails.tsx` (1): Chi tiết thông báo (`42`)
- `shared/diagnostics.ts` (18): Tải sách (`50`); Xuất sách nói (`50`); Việc nền (`58`); Việc {} (`59`); Pha: {} (`61`); Bản ABook (`103`); Điện thoại (`107`); Giờ trên máy (`111`); Pin (`115`); Mạng (`119`); Bluetooth (`122`); Wi-Fi (`122`); Chỗ trống (`125`); Chạy nền (`130`); Cho máy khác nghe thư viện (`146`); Lần tắt gần nhất (`150`); Lần văng (`154`); Phục hồi dữ liệu (`155`)
- `shared/editsKept.ts` (1): Đã gộp {} sửa từ file (`12`)
- `shared/latestRequest.ts` (1): AbortError (`20`)
- `shared/musicLevels.ts` (1): Rất nhỏ (`10`)
- `shared/pdfPages.ts` (1): PasswordException (`38`)
- `shared/peerStudio.ts` (1): Đang mở Studio của {} (`52`)
- `shared/trashUndo.ts` (1): Chưa mang theo chỗ nghe. (`24`)
- `shared/ui.tsx` (2): Xem các tab trước (`515`); Xem các tab sau (`520`)

### c3. Chỉ có ở web phía máy tính / Studio (chỉ đếm)

| thư mục | nhãn |
|---|---|
| desktop/ | 213 |
| studio/ | 688 |

## d. Chữ hoa, dấu câu, `…` và `...`, dấu thanh, số

**d1. Cùng nhãn (theo khoá lỏng) nhưng khác nguyên văn giữa hai phía** (19):

| web | native | khác ở | nơi |
|---|---|---|---|
| Chưa bỏ được ảnh bìa | Chưa bỏ được ảnh bìa. | dấu câu cuối | `listen/EditBook.tsx:348` (+1) ~ `native/editbook/BookEditor.kt:85` |
| Chưa gửi được về {} | Chưa gửi được về {}. | dấu câu cuối | `listen/SendEdits.tsx:43` ~ `native/editbook/BookEditor.kt:104` |
| Chưa làm trước được | Chưa làm trước được. | dấu câu cuối | `listen/PlayerViews.tsx:886` ~ `native/nowplaying/PrepareBlock.kt:63` |
| Chưa thêm được sách | Chưa thêm được sách. | dấu câu cuối | `listen/AddBook.tsx:481` ~ `native/addbook/ImportQueue.kt:86` (+1) |
| Chưa đặt được ảnh bìa | Chưa đặt được ảnh bìa. | dấu câu cuối | `listen/EditBook.tsx:343` (+1) ~ `native/editbook/BookEditor.kt:85` |
| Chưa đọc lại được file | Chưa đọc lại được file. | dấu câu cuối | `listen/AddBook.tsx:388` ~ `native/addbook/ImportQueue.kt:60` |
| Chưa đổi được tác giả | Chưa đổi được tác giả. | dấu câu cuối | `listen/EditBook.tsx:338` ~ `native/editbook/EditModel.kt:67` |
| Chưa đổi được tên sách | Chưa đổi được tên sách. | dấu câu cuối | `listen/EditBook.tsx:333` ~ `native/editbook/EditModel.kt:66` |
| Chữ của cả cuốn được gửi tới {} để đọc, bằn… | Chữ của cả cuốn được gửi tới {} để đọc, bằn… | dấu thanh / ký tự | `desktop/listenExport.ts:85` ~ `native/export/ExportModel.kt:197` |
| Giấy phép: | Giấy phép | dấu câu cuối | `listen/PlayerViews.tsx:1301` ~ `native/music/MusicPanel.kt:447` (+1) |
| vào {} | Vào {} | chữ hoa | `android/ExportMp3.tsx:77` ~ `native/export/ExportModel.kt:312` (+1) |
| {} - Đang dùng: {} ({}) | {} - Đang dùng: {} ({}). | dấu câu cuối | `listen/voiceSpeed.ts:68` ~ `native/data/SettingsRepo.kt:319` |
| Đang chuẩn bị… | Đang chuẩn bị | dấu câu cuối | `android/ExportM4b.tsx:43` (+2) ~ `native/export/ExportModel.kt:273` |
| Đang chờ mạng… | Đang chờ mạng | dấu câu cuối | `desktop/bookFileExport.ts:182` ~ `native/export/ExportModel.kt:256` |
| Đang làm file M4B… | Đang làm file M4B | dấu câu cuối | `desktop/bookFileExport.ts:37` (+1) ~ `native/export/ExportModel.kt:290` |
| Đang làm sách nói… | Đang làm sách nói | dấu câu cuối | `desktop/listenExport.ts:13` ~ `native/export/ExportModel.kt:284` (+1) |
| đang phát | Đang phát | chữ hoa | `android/RemotePlayers.tsx:361` (+1) ~ `native/music/MusicPanel.kt:438` |
| Đang tính độ dài… | Đang tính độ dài | dấu câu cuối | `android/ExportAudiobook.tsx:174` (+1) ~ `native/export/ExportScreen.kt:216` |
| đang xuất | Đang xuất | chữ hoa | `shared/diagnostics.ts:47` ~ `native/export/ExportModel.kt:391` |

**d2. Kiểu viết theo phía** (số chữ khớp / tổng; chữ quét ở trên):

| kiểu | web | native |
|---|---|---|
| dấu ba chấm ASCII `...` | 8 / 5861 | 0 / 1319 |
| dấu ba chấm `…` | 42 / 5861 | 0 / 1319 |
| kết thúc bằng dấu chấm `.` | 991 / 5861 | 266 / 1319 |
| kết thúc bằng `!` | 0 / 5861 | 0 / 1319 |
| kết thúc bằng `:` | 55 / 5861 | 3 / 1319 |
| dấu thanh kiểu cũ `oà oá uý` | 467 / 5861 | 129 / 1319 |
| dấu thanh kiểu mới `òa óa úy` | 1 / 5861 | 0 / 1319 |
| số thập phân dấu phẩy `1,5` | 1 / 5861 | 0 / 1319 |
| số thập phân dấu chấm `1.5` | 0 / 5861 | 0 / 1319 |
| nhân bằng `×` | 0 / 5861 | 0 / 1319 |
| nhân bằng `x` sau số | 0 / 5861 | 0 / 1319 |
| ngăn cách `·` | 132 / 5861 | 33 / 1319 |
| ngăn cách ` - ` | 287 / 5861 | 54 / 1319 |
| gạch dài `—`/`–` | 10 / 5861 | 1 / 1319 |
| giờ `1:30` hay `1 giờ 30` | 4 / 5861 | 2 / 1319 |
| dấu `%` dính số | 0 / 5861 | 1 / 1319 |
| dấu `%` cách số | 0 / 5861 | 0 / 1319 |

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

**d4. native: cùng nhãn nhưng viết khác nhau trong chính phía này** (13); 15 đầu:

- `Chưa nghe thử được giọng này` | `Chưa nghe thử được giọng này.` (`native/voice/VoiceRepo.kt:106`, `native/voice/VoiceState.kt:303` (+1))
- `Chưa tải được` | `Chưa tải được.` (`native/devices/DevicesRepo.kt:119`, `native/screens/RemoteBookSheet.kt:38`)
- `Chưa đổi được tên chương` | `Chưa đổi được tên chương.` (`native/editbook/BookEditor.kt:90`, `native/editbook/EditModel.kt:68` (+1))
- `Hết chương này` | `hết chương này` (`native/nowplaying/PlayerSheets.kt:150`, `native/nowplaying/SleepText.kt:23`)
- `Hồ sơ nghe` | `Hồ sơ nghe:` (`native/screens/BookRecords.kt:101`, `native/screens/BookTabs.kt:172`)
- `Lùi 15 giây` | `Lùi {} giây` (`native/nowplaying/NowPlayingScreen.kt:181`, `native/pip/PipParams.kt:47`)
- `Mở Cài đặt` | `Mở cài đặt` (`native/data/SettingsRepo.kt:127`, `native/devices/CompanionSurfaces.kt:140` (+2))
- `Nữ` | `nữ` (`native/data/ListenExtras.kt:361`, `native/data/ListenExtras.kt:407` (+1))
- `Tới 15 giây` | `Tới {} giây` (`native/nowplaying/NowPlayingScreen.kt:183`, `native/pip/PipParams.kt:49`)
- `Xoá khoá` | `Xoá khoá?` (`native/voice/VoiceSheets.kt:254`, `native/voice/VoiceSheets.kt:278` (+1))
- `Xoá phần đã tải` | `Xoá phần đã tải?` (`native/components/Confirm.kt:95`, `native/voice/VoiceSheets.kt:102` (+2))
- `ĐANG NGHE` | `Đang nghe` (`native/data/BookDetail.kt:171`, `native/nowplaying/NowPlayingScreen.kt:86` (+1))
- `Đã xoá nhật ký` | `Đã xoá nhật ký.` (`native/data/SettingsRepo.kt:250`, `native/screens/SettingsAdvanced.kt:57` (+1))
## e. Cặp màn web <-> native (luật cứng, scripts/ui_parity_pairs.json)

Trong một cặp, mỗi nhãn ngắn phải có ở cả hai phía (khoá lỏng) trừ khi nằm trong `allow` (nền tảng bắt buộc khác, có lý do) hay `missing` (tính năng / phần màn chỉ có ở một phía - Lead xếp lịch). Cột lệch phải bằng 0 thì `--check` mới qua.

| cặp | nhãn web | nhãn native | lệch web | lệch native | cho phép | thiếu thật |
|---|---|---|---|---|---|---|
| now-playing | 101 | 102 | 0 | 0 | 32 | 6 |
| shared-labels | 30 | 913 | 0 | 0 | 7 | 0 |
| library-book | 220 | 185 | 0 | 0 | 67 | 8 |
| settings | 126 | 116 | 0 | 0 | 7 | 3 |
| devices | 142 | 172 | 0 | 0 | 6 | 27 |
| voice | 133 | 121 | 0 | 0 | 27 | 19 |
| add-edit-book | 174 | 139 | 0 | 0 | 70 | 0 |

Thiếu thật ở web - `now-playing`: Chưa tải được chữ. Bạn thử lại.; Chương chưa có chữ. Bạn thử lại sau.; Chọn giọng; Giọng thu sẵn; Về chế độ nghe; Đang chọn

Thiếu thật ở web - `library-book`: Chương này chưa có audio.; Chương {}; Sách chưa có chương nào nghe được trên …; Sắp có; Tới chỗ đang nghe; Đang xoá; Đang đóng file sách; Đã xoá khỏi điện thoại

Thiếu thật ở web - `settings`: Sắp có; Đang đo.; Đang đọc nhật ký.

Thiếu thật ở web - `devices`: Chưa có gì trên máy; Chưa mở được Studio; Chưa nối; Chưa phát sách; Chưa thấy; Chưa thấy máy khác. Bạn kiểm tra kết nố…; Chọn nơi phát; Cách nối; Còn trống {}; Huỷ; Máy tính; Máy đã ghép; Máy đã nối; Sách trên {}; Thấy {}; Tìm lại thiết bị phát; Đang bật; Đang bật · {} máy; Đang bỏ ghép; Đang gửi lệnh; Đang kiểm tra; Đang lưu; Đang mở Studio; Đang nối {}; Đang tắt; Đã nối {}; Địa chỉ máy tính

Thiếu thật ở web - `voice`: Chưa đọc được các khoá; Chưa đổi được giọng; Chờ Wi-Fi; Có bản mới · {}; Dữ liệu di động; Hiện; Khoá {} sẽ bị xoá khỏi máy này và các g…; Phần đã tải dở sẽ bị xoá khỏi máy này.; Supertonic nhanh hơn; Vẫn tải; Xoá bài này?; Đang gỡ; Đang kiểm tra; Đang lưu; Đang lấy giọng; Đang xoá; Đang đo tốc độ; Đồng ý; Ẩn


<!-- ui_parity:end -->
