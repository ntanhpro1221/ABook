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

<!-- ui_parity:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity.py - không sửa tay, chạy lại script) -->

Quét: web 5846 chữ (3291 khác nhau), 378 cặp nhãn-icon; native 722 chữ (558 khác nhau), 35 cặp nhãn-icon. Nhãn so theo khoá lỏng (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối).

## a. Cùng việc, khác chữ

Cặp nhãn ngắn (<= 6 chữ) mà phía kia KHÔNG có nguyên văn nhưng có nhãn giống (chung từ, gần nhau, hay chung icon). 415 cặp; 40 cặp đầu theo độ giống. `icon` = cùng icon lucide.

| native | web | giống | nơi |
|---|---|---|---|
| Chương {} · {} | Chương {}/{} | 1.00 | `native/data/DemoPlayback.kt:13` (+1) ~ `desktop/bookFileExport.ts:167` |
| Chọn giọng | Chọn một giọng | 1.00 | `native/nowplaying/PlayerSheets.kt:160` ~ `studio/NewProjectScreen.tsx:1276` |
| Có bản mới · {} | Có bản mới {} | 1.00 | `native/voice/VoiceModel.kt:291` ~ `android/SettingsScreen.tsx:376` (+2) |
| File đã chọn | Các file đã chọn | 1.00 | `native/addbook/ImportModel.kt:13` ~ `listen/AddBook.tsx:825` |
| Giọng thử A | Thử giọng | 1.00 | `native/nowplaying/FakeNowPlayingModel.kt:92` ~ `listen/VoiceSettings.tsx:338` |
| Giọng thử B | Thử giọng | 1.00 | `native/nowplaying/FakeNowPlayingModel.kt:92` ~ `listen/VoiceSettings.tsx:338` |
| Khoá {} | Khoá | 1.00 | `native/voice/VoiceSheets.kt:212` ~ `listen/VoiceSettings.tsx:186` |
| Khuyên dùng · | Khuyên dùng | 1.00 | `native/voice/VoiceModel.kt:274` ~ `listen/VieneuModuleCard.tsx:265` |
| Máy này chưa dùng được. | Máy này chưa dùng được {}. | 1.00 | `native/voice/VoiceModel.kt:254` ~ `listen/vieneuModule.ts:288` |
| Máy này chưa dùng được: {}. | Máy này chưa dùng được {}. | 1.00 | `native/voice/VoiceModel.kt:254` ~ `listen/vieneuModule.ts:288` |
| Sách trên {} | Sách {}/{} | 1.00 | `native/devices/PairScreen.kt:113` ~ `listen/importQueue.ts:87` |
| Tên gốc: {} | Tên gốc: | 1.00 | `native/addbook/BookForms.kt:97` ~ `studio/CastEdits.tsx:88` |
| Đang dùng: {} | Đang dùng: | 1.00 | `native/screens/SettingsVoice.kt:139` ~ `listen/VoiceSettings.tsx:277` (+2) |
| Đang thêm {}/{} | Đang thêm {} | 1.00 | `native/music/MusicPanel.kt:310` (+1) ~ `listen/AddBook.tsx:802` |
| Đang tải {} · {}% | Đang tải {} | 1.00 | `native/voice/VoiceModel.kt:277` ~ `android/DevicesScreen.tsx:314` (+4) |
| Đang tải {} · {}% | Đang tải {} ({}) {}% | 1.00 | `native/voice/VoiceModel.kt:277` ~ `listen/vieneuModule.ts:285` |
| Đang tải {}% | Đang tải {} | 1.00 | `native/screens/RemoteBookSheet.kt:38` ~ `android/DevicesScreen.tsx:314` (+4) |
| Đang tải {}% | Đang tải {} ({}) {}% | 1.00 | `native/screens/RemoteBookSheet.kt:38` ~ `listen/vieneuModule.ts:285` |
| Đã dừng tải | Dừng tải | 1.00 | `native/screens/RemoteBookSheet.kt:38` ~ `desktop/RemoteDownload.tsx:105` |
| Đã dừng tải | Đã dừng tải ({}) | 1.00 | `native/screens/RemoteBookSheet.kt:38` ~ `desktop/remoteDownloadState.ts:59` |
| Đã thêm: {} | Thêm {} | 1.00 | `native/voice/VoiceModel.kt:371` ~ `listen/LibraryScreen.tsx:203` |
| Đã thêm: {} | Đã thêm “{}” | 1.00 | `native/voice/VoiceModel.kt:371` ~ `android/imports.ts:42` |
| Đồng ý | Đóng | 1.00 | `native/voice/VoiceSheets.kt:134` ~ `listen/ProjectFileItems.tsx:204` (+7) |
| Chưa mở được Studio | Chưa gỡ được Studio | 0.95 | `native/devices/DevicesRepo.kt:148` ~ `studio/StudioSetup.tsx:359` |
| Đang đo. | Đang đổi… | 0.93 | `native/screens/SettingsAdvanced.kt:57` ~ `studio/MusicTab.tsx:230` |
| Đã xoá khỏi điện thoại | Xoá {} khỏi điện thoại | 0.93 | `native/components/UndoBar.kt:27` ~ `android/DevicesScreen.tsx:891` (+1) |
| Đang đóng file sách | Đang đọc file sách | 0.92 | `native/screens/BookSheets.kt:150` ~ `listen/AddBook.tsx:668` |
| Chương này chưa có audio. | Chương sau chưa có audio | 0.92 | `native/screens/BookSheets.kt:214` ~ `listen/labels.ts:80` (+1) |
| Đang thêm {}/{} | Thêm | 0.92 · icon | `native/music/MusicPanel.kt:310` (+1) ~ `studio/ProjectScreen.tsx:1092` (+4) |
| Cắt ảnh bìa | Đặt ảnh bìa | 0.91 | `native/editbook/CoverCrop.kt:108` ~ `studio/CoverEditor.tsx:112` (+1) |
| Đang bỏ ghép | Đã bỏ ghép {} | 0.91 | `native/devices/DeviceSheets.kt:136` ~ `android/DevicesScreen.tsx:931` (+2) |
| Chưa thêm được nhạc | Chưa thêm được sách | 0.90 | `native/music/MusicRepo.kt:74` (+1) ~ `listen/AddBook.tsx:477` |
| Đang đóng | Đang dùng: | 0.89 | `native/music/MusicPanel.kt:242` ~ `listen/VoiceSettings.tsx:277` (+2) |
| Chưa nối được máy tính | Chưa nối được máy kia. | 0.88 | `native/devices/DevicesRepo.kt:80` ~ `android/LibraryDownloads.tsx:57` |
| Thêm thiết bị | Tên thiết bị | 0.88 | `native/devices/PairScreen.kt:130` (+1) ~ `desktop/PhoneSync.tsx:482` (+1) |
| Đang mở Studio | Đang mở Studio của {} | 0.88 | `native/devices/DeviceSheets.kt:75` ~ `shared/peerStudio.ts:52` |
| Đang nối {} | Đang đổi… | 0.88 | `native/devices/PairScreen.kt:159` ~ `studio/MusicTab.tsx:230` |
| Đang thêm {}/{} | Đã thêm “{}” | 0.88 | `native/music/MusicPanel.kt:310` (+1) ~ `android/imports.ts:42` |
| Đang tải {} · {}% | Dừng tải | 0.88 | `native/voice/VoiceModel.kt:277` ~ `desktop/RemoteDownload.tsx:105` |
| Đang tải {} · {}% | Đang cài. | 0.88 | `native/voice/VoiceModel.kt:277` ~ `studio/StudioSetup.tsx:326` |

## b. Cùng nhãn khác icon, cùng icon khác nhãn

**Cùng nhãn, khác icon** (0 nhãn có icon ở cả hai phía mà không chung icon nào):

| nhãn | web | native | nơi |
|---|---|---|---|
| (không có) | | | |

**Cùng icon, khác nhãn** (8 icon dùng ở cả hai phía mà không chung nhãn nào):

| icon | web | native |
|---|---|---|
| check | Duyệt câu, Giữ cả thẻ, Giữ thẻ, Tạm dừng {} | Chưa nghe, Chưa nghe xong, Đang lấy giọng |
| circle-dashed | Chưa nghe / Đã nghe xong, Tạm dừng {} | Chưa nghe, Chưa nghe xong |
| download | Cài Studio, Cài tiếp, Có ABook {}, Dừng tải / Tải tiếp | Cập nhật ({}) |
| file-down | Lưu, Lưu thành | Xuất MP3 hay M4B |
| image-plus | Đổi ảnh bìa | Chọn ảnh |
| laptop | Máy kia không trả lời | Đang mở Studio |
| share-2 | Chia sẻ | Đang đóng file sách |
| upload | Chọn file, Nhập nhạc, Thêm file | Đang thêm {}/{} |

Phủ của bộ ghép: icon dùng ở 78 chỗ trong mã native, ghép được với nhãn chữ ở 35; web 554 chỗ, ghép được 325. Phần còn lại là icon không đi cùng nhãn chữ (nút chỉ icon, chỉ báo) hay nhãn dựng từ model (vd tên nhóm Cài đặt), nên KHÔNG có trong bảng.
Icon native chưa quy về lucide (3): `native:ChevronIcon`, `native:OtherPlayerIcon`, `native:PlayerGlyph`.
Số cặp: web 325, native 35; icon lucide dùng: web 96, native 22.

## c. Nhãn chỉ có ở một phía, theo màn

Nhãn ngắn (<= 6 chữ) không có (theo khoá lỏng) ở phía kia - kể cả chữ giống chữ ở mục a. Để phân biệt tính năng thiếu với chữ trôi: một màn native có nhiều nhãn chỉ-native mà web cùng màn không có thường là tính năng mới; vài nhãn lẻ thường là chữ trôi (mục a).

### c1. Chỉ có ở native (115 nhãn)

- `native/addbook/AddBookScreen.kt` (8): Chọn sách từ máy bạn (`91`); Xem trước (`160`); Đang xử lý (`164`); Dùng sách có (`165`); Tách chương (`185`); Bỏ đọc dòng (`194`); Bỏ số gọi (`211`); Lời chú (`215`)
- `native/addbook/BookForms.kt` (1): Tên gốc: {} (`97`)
- `native/addbook/ImportModel.kt` (1): File đã chọn (`13`)
- `native/addbook/ImportQueue.kt` (2): Bạn hãy thử lại. (`82`); Bạn hãy chọn lại file. (`138`)
- `native/addbook/ImportRepo.kt` (1): Bạn hãy nhập tên sách. (`89`)
- `native/components/Confirm.kt` (1): Đang xoá (`95`)
- `native/components/ListParts.kt` (1): Sắp có (`380`)
- `native/components/UndoBar.kt` (1): Đã xoá khỏi điện thoại (`27`)
- `native/data/DemoPlayback.kt` (1): Chương {} · {} (`13`)
- `native/data/Library.kt` (1): Chưa làm được, bạn thử lại (`119`)
- `native/data/Settings.kt` (1): Không tự lùi (`168`)
- `native/data/UndoDelete.kt` (1): Chưa xoá được, bạn thử lại (`47`)
- `native/devices/CompanionRepo.kt` (2): Chưa nối được, bạn thử lại (`88`); Chưa làm được, bạn thử lại (`141`)
- `native/devices/CompanionSurfaces.kt` (5): Chọn nơi phát (`38`); Đang gửi lệnh (`54`); Chưa phát sách (`66`); Phát ở đây (`107`); Tìm lại thiết bị phát (`116`)
- `native/devices/DeviceParts.kt` (1): Dùng được đến {} (`125`)
- `native/devices/DeviceSheets.kt` (3): Đang mở Studio (`75`); Đang bỏ ghép (`136`); Đang lưu (`158`)
- `native/devices/DevicesModel.kt` (3): Bluetooth: {} máy đang nối (`231`); Chưa thấy (`290`); Thấy {} (`290`)
- `native/devices/DevicesRepo.kt` (2): Chưa nối được máy tính (`80`); Chưa mở được Studio (`148`)
- `native/devices/DevicesState.kt` (4): Chưa nối (`69`); Đã nối {} (`69`); Đang bật · {} máy (`71`); Bạn hãy thử lại. (`121`)
- `native/devices/PairScreen.kt` (9): Thêm thiết bị (`79`); Máy đã nối (`97`); Sách trên {} (`113`); Cách nối (`135`); Địa chỉ máy tính (`142`); Đang nối {} (`159`); Đang tìm máy (`170`); Chưa thấy máy nào (`171`); Cần quyền Thiết bị ở gần (`180`)
- `native/devices/ShareScreen.kt` (2): Cho máy khác nghe (`57`); Cần quyền Thiết bị ở gần (`78`)
- `native/devices/StorageScreen.kt` (2): Còn trống {} (`48`); Chưa có gì trên máy (`52`)
- `native/editbook/BookEditor.kt` (2): Bạn hãy thử lại. (`33`); Bạn hãy thử lưu lại. (`65`)
- `native/editbook/CoverCrop.kt` (6): Bạn hãy chọn lại ảnh. (`105`); Cắt ảnh bìa (`108`); Dùng ảnh (`110`); Đang lưu (`110`); Đang đọc ảnh (`125`); Phóng to (`149`)
- `native/editbook/EditBookScreen.kt` (4): Đang đọc sách (`85`); Gửi phần sửa (`104`); Gốc: {} (`116`); Nhãn (`153`)
- `native/editbook/EditModel.kt` (2): Bạn hãy nhập tên sách. (`54`); Bạn hãy nhập tên chương. (`55`)
- `native/music/MusicModel.kt` (1): Rất nhỏ (dễ nghe lời nhất) (`159`)
- `native/music/MusicPanel.kt` (3): Đang đóng (`242`); Đang thêm {}/{} (`310`); Trang của bài (`448`)
- `native/music/MusicRepo.kt` (2): Chưa tìm được bài để đổi (`68`); Chưa thêm được nhạc (`74`)
- `native/music/MusicState.kt` (1): Chưa thêm được nhạc (`138`)
- `native/nowplaying/FakeNowPlayingModel.kt` (5): Chương 1 · Một buổi sớm (`70`); Những ngày gió hát (`70`); Chương {} · {} (`72`); Giọng thử A (`92`); Giọng thử B (`92`)
- `native/nowplaying/NowPlayingScreen.kt` (1): Về chế độ nghe (`97`)
- `native/nowplaying/PlayerSheets.kt` (3): Đóng bảng (`70`); Chọn giọng (`160`); Giọng thu sẵn (`160`)
- `native/screens/BookScreen.kt` (1): Tới chỗ đang nghe (`408`)
- `native/screens/BookSheets.kt` (3): Đang đóng file sách (`150`); Xuất MP3 hay M4B (`177`); Chương này chưa có audio. (`214`)
- `native/screens/LibraryScreen.kt` (1): Trên máy tính (`249`)
- `native/screens/RemoteBookSheet.kt` (2): Đang tải {}% (`38`); Đã dừng tải (`38`)
- `native/screens/SettingsAdvanced.kt` (5): Đang đo. (`57`); Đang đọc nhật ký. (`138`); Nhật ký đang trống. (`139`); Đang mở danh sách (`159`); Chưa mở được danh sách. (`160`)
- `native/screens/SettingsGroups.kt` (1): Tên máy này (`277`)
- `native/screens/SettingsParts.kt` (1): Sắp có (`87`)
- `native/screens/SettingsVoice.kt` (2): Đang dùng: {} (`139`); Đang lấy giọng (`263`)
- `native/voice/KeysScreen.kt` (1): Chưa đọc được các khoá (`35`)
- `native/voice/MyMusicScreen.kt` (3): Thêm nhạc (`57`); Đang thêm {}/{} (`57`); Chưa đọc được kho nhạc (`72`)
- `native/voice/VoiceModel.kt` (9): Supertonic nhanh hơn (`219`); Máy này chưa dùng được. (`254`); Máy này chưa dùng được: {}. (`254`); Khuyên dùng · (`274`); Đang tải {} · {}% (`277`); Có bản mới · {} (`291`); Đã có trên máy (`294`); Chưa có khoá (`344`); Đã thêm: {} (`371`)
- `native/voice/VoiceRepo.kt` (4): Chưa lưu được khoá (`90`); Chưa xoá được khoá (`94`); Chưa kiểm tra được khoá (`98`); Chưa nhập được nhạc (`116`)
- `native/voice/VoiceSheets.kt` (10): Đang đo tốc độ (`83`); Đang xoá (`102`); Dữ liệu di động (`120`); Vẫn tải (`121`); Gửi chữ ra ngoài? (`133`); Đang lưu (`134`); Đồng ý (`134`); Khoá {} (`212`); Xoá bài này? (`297`); Xoá bài (`298`)
- `native/voice/VoiceState.kt` (5): Chưa lưu được khoá (`229`); Chưa kiểm tra được khoá (`244`); Chưa xoá được khoá (`254`); Chưa nhập được nhạc (`318`); Chưa xoá được bài này (`327`)

### c2. Chỉ có ở web phía điện thoại - listen/, android/, shared/ (609 nhãn)

- `android/App.tsx` (7): Điều hướng (`189`); Nối máy (`215`); Đang tải về máy (`236`); Không tải được (`237`); Chiếm {} (`259`); Chưa xoá được (`297`); Đóng thông báo (`416`)
- `android/DevicesScreen.tsx` (43): Đã chép địa chỉ (`41`); Studio máy tính (`47`); Tải ABook Windows (`53`); Chép địa chỉ (`55`); Đã kết nối với {} (`136`); Cách lấy mã (`167`); Máy tính tìm thấy (`173`); Đang tìm trong mạng Wi-Fi (`199`); Quyền Bluetooth (`210`); Để sau (`221`); Dùng Bluetooth (`228`); Máy tính đã ghép Bluetooth (`232`); Nhập địa chỉ (`260`); Tự tìm máy tính (`260`); Chưa huỷ được (`300`); Đang tải {} (`314`); Huỷ tải {} (`326`); Chưa đổi được (`367`); Vân tay (`400`); Thiết bị ở gần (`408`); Đã ghép {} (`451`); Chưa ghép được (`458`); Thiết bị khác (`489`); Ghép thiết bị (`492`); Ghép Bluetooth (`504`); ... +18
- `android/Diagnostics.tsx` (3): Không đọc được nhật ký (`33`); Chưa gửi được nhật ký (`43`); Chưa xoá được nhật ký (`54`)
- `android/ExportAudiobook.tsx` (6): Dừng (`90`); Đang tính độ dài… (`174`); Xuất sách nói “{}” (`254`); Để sau (`255`); Bắt đầu (`258`); Xuất sách nói (M4B)… (`283`)
- `android/ExportM4b.tsx` (6): Đang chuẩn bị… (`43`); Dừng (`63`); Xuất M4B “{}” (`157`); Để sau (`158`); Bắt đầu (`161`); Xuất M4B (`181`)
- `android/ExportMp3.tsx` (12): Đang xuất sách… (`36`); Đổi thư mục (`43`); Không xuất được (`67`); Đã xuất {} chương{} (`78`); Mở thư mục (`101`); Có chương đã đổi (`178`); Cả cuốn (`179`); Chỉ {} chương đổi (`183`); Xuất MP3 “{}” (`208`); Để sau (`209`); Bắt đầu (`212`); Xuất MP3 (`234`)
- `android/ExportRevisions.tsx` (2): Xuất lại các chương đã đổi (`18`); Xuất lại cả file M4B (`19`)
- `android/LibraryDownloads.tsx` (3): Tải · (`20`); Đang tải {} (`21`); Chưa nối được máy kia. (`57`)
- `android/OldSaves.tsx` (6): Xoá bản lưu cũ? (`18`); Xoá (`29`); Chưa lưu ra được (`44`); Đã xoá bản lưu cũ (`53`); Chưa xoá được (`56`); Lưu ra (`88`)
- `android/RemotePlayers.tsx` (8): Google Cast (`32`); Đang phát trên {} (`145`); Đang dừng trên (`151`); Đang phát trên (`151`); Đang mở trên {} (`288`); Phát trên {}{} (`305`); Phát trên thiết bị khác (`321`); Phát trên (`332`)
- `android/SettingsScreen.tsx` (7): Số phút hẹn (`189`); Độ nhạy lắc (`225`); Bản lưu cũ ({}) (`300`); Xem (`314`); Xoá (`330`); Cập nhật (`375`); Có bản mới {} (`376`)
- `android/StudioOpen.tsx` (2): Chưa ghép với máy tính nào (`34`); Mở Studio của máy nào? (`125`)
- `android/StudioScreen.tsx` (1): Tạo sách nói từ xa (`31`)
- `android/UpdateNotice.tsx` (2): Không mở được trình duyệt (`11`); Có ABook {} cho điện thoại (`21`)
- `android/backLayers.ts` (1): Escape (`48`)
- `android/downloads.ts` (1): Tải bị gián đoạn (`40`)
- `android/imports.ts` (10): Không mở được file (`17`); File không có sách nào. (`25`); Không mở được file sách (`25`); File này có bản thu khác (`30`); Thay bằng file này (`32`); Chưa thay được sách (`33`); Đã thêm sách vào Thư viện (`42`); Đã thêm “{}” (`42`); Mở sách (`43`); Không mở được bộ chọn file (`57`)
- `android/localStudio.ts` (1): Lỗi {} (`25`)
- `android/nativeEngine.ts` (1): Chưa lưu được chỗ đang nghe (`53`)
- `android/plugins.ts` (3): EbookPlayer (`701`); ReadAloud (`702`); EbookLibrary (`703`)
- `android/textImport.ts` (2): Không đọc được file này. (`42`); Không đọc được PDF này: {} (`56`)
- `listen/AddBook.tsx` (26): Không mở được file sách này. (`293`); Đã mở (`293`); Mở cuốn đó (`312`); Chưa đọc lại được file (`385`); Đã thêm sách vào thư viện (`471`); Chưa thêm được sách (`477`); Đã thêm từ file này rồi (`492`); Bỏ qua (`517`); Chọn lại (`544`); Thêm phần còn lại (`549`); Vẫn thêm bản mới (`556`); Thêm vào thư viện (`566`); Đóng khi còn sách chưa thêm (`585`); Bỏ phần còn lại (`608`); Bỏ và chọn lại (`608`); Quay lại thêm sách (`610`); Đang đọc file tiếp (`619`); Đường dẫn file hay thư mục (`647`); Đang đọc file sách (`668`); Tên hiển thị trong thư viện (`682`); Chọn hết (`707`); Bỏ chọn hết (`710`); Định dạng (`763`); Đang thêm {} (`802`); Chưa đọc được (`817`); ... +1
- `listen/BookScreen.tsx` (70): Nghe {} (`84`); Tạm dừng {} (`84`); Đọc {} (chưa có audio) (`103`); Đã làm sẵn (`119`); Đọc chương này (`150`); Đổi tên chương (`160`); Danh sách chương (`183`); Dừng (`227`); Dừng nghe thử (`228`); Chưa có giọng (`312`); Chờ áp dụng (`317`); Đang chờ máy làm sách (`317`); Bỏ gộp {} vào {} (`327`); Bỏ gộp (`332`); Nghe {} nói (`345`); Đổi giọng {} (`347`); Gộp vào người khác (`364`); Đổi tên (`369`); Đổi giới tính (`374`); Chưa có dàn nhân vật (`426`); Người kể chuyện (`438`); Mặc định (`439`); Chờ áp dụng: giọng (`441`); Nghe giọng {} (`447`); Đổi giọng người kể (`448`); ... +45
- `listen/DropToAdd.tsx` (1): Thả để thêm sách (`36`)
- `listen/EditBook.tsx` (43): Không đọc được file ảnh (`73`); Chưa chỉnh được nhạc nền (`160`); Đang tải nhạc nền (`175`); Đã đổi tên sách (`330`); Chưa đổi được tên sách (`331`); Đã bỏ tên tác giả (`335`); Đã đổi tác giả (`335`); Chưa đổi được tác giả (`336`); Đã đặt ảnh bìa (`340`); Chưa đặt được ảnh bìa (`341`); Chưa bỏ được ảnh bìa (`346`); Chưa bỏ được thay đổi (`355`); Lưu tên (`408`); Không rõ tác giả (`423`); Lưu tác giả (`431`); Chọn ảnh bìa (`444`); Tìm bìa (`446`); Đang đặt ảnh bìa (`455`); Mở tab Nhạc nền (`466`); Tên riêng (`476`); Cách đọc tên (`481`); Bỏ mọi thay đổi ({}) (`486`); Bỏ hết thay đổi (`489`); Thôi (`492`); Bỏ mọi thay đổi (`497`); ... +18
- `listen/FootnoteChoices.tsx` (2): Không đọc số chú thích (`55`); Đọc lời chú ở cuối chương (`63`)
- `listen/LibraryScreen.tsx` (22): Chỉ có chữ (`73`); Còn {} (`85`); Mở {} (`160`); Nghe ngay {} (`163`); Nghe {} (`163`); Tạm dừng {} (`163`); Đọc {} (`163`); Thêm {} (`203`); Nghe tiếp {}{} (`248`); Đang tạm dừng {} (`291`); Đang làm {} (`292`); Đang tạm dừng{} (`296`); Chưa có chương nghe được{} (`298`); Đang làm · {} (`298`); Mở bộ {} (`376`); Có sách trên máy khác (`384`); Chưa có sách nào (`519`); Lọc sách (`532`); Nghe xong (`534`); Xếp theo: {} (`542`); Gõ không dấu cũng được (`560`); Xoá ô tìm (`561`)
- `listen/LineWishes.tsx` (28): Người kể (`106`); Người nói: {} (`125`); Cách đọc câu - {} (`128`); Thu lại câu này (`130`); Đang chờ máy làm sách (`136`); Các từ trong câu (`194`); Bỏ cách đọc “{}” (`226`); Đã ghi: câu này của {} (`346`); Chưa ghi được người nói (`352`); Chưa lấy lại được (`365`); Đã ghi cách đọc câu này (`368`); Chưa ghi được (`374`); Đã ghi: thu lại câu này (`393`); Không hoàn tác được (`403`); Không bỏ được thay đổi này (`419`); Cách đọc “{}”: “{}” (`428`); Ai nghĩ câu này? (`430`); Ai nói câu này? (`430`); Cách đọc câu này (`430`); Sửa câu này (`430`); Đọc từ này là (`430`); Sửa cách đọc “{}” (`457`); Sửa (`465`); Bỏ: {} (`472`); Đang chờ máy làm sách: {} (`501`); ... +3
- `listen/MorningRecap.tsx` (12): Tối qua (`41`); Vừa hẹn giờ (`45`); Lần cuối chạm máy (`72`); Lần cuối dùng máy (`72`); Máy bắt đầu nằm yên (`74`); Tự dừng (`75`); Ẩn thẻ này (`154`); Nghe tới đâu rồi thiếp đi? (`163`); Nghe từ đây (`207`); Thu gọn (`211`); Tìm đúng câu (`211`); Chọn câu cuối cùng còn nhớ: (`219`)
- `listen/MyMusic.tsx` (14): Đang tải bài nhạc (`70`); Đang nhập nhạc thì dừng (`119`); Đã xoá khỏi Nhạc của tôi (`135`); Không xoá được bài này (`137`); Nhập nhạc của tôi… (`146`); Đang nhập {}/{}… (`146`); Nhạc riêng (`152`); Nhập nhạc (`154`); Đang tải nhạc riêng (`154`); Xoá khỏi kho (`175`); Xoá khỏi kho: {} (`175`); Giữ lại: {} (`178`); Xoá (`183`); Xoá: {} (`183`)
- `listen/OnlineVoicePrompt.tsx` (6): Chọn giọng đọc (`35`); Giọng đọc trực tuyến (`35`); Dừng (`75`); Nghe thử (`75`); Tải giọng chạy trên máy (`95`); Chọn giọng khác (`101`)
- `listen/PlayerViews.tsx` (55): Tốc độ đọc: {} (`89`); Giọng đọc: {} (`92`); Shift+← (`260`); Đã chọn tốc độ đọc {} (`463`); Phím (`478`); Đang chuẩn bị nhạc nền (`578`); Danh sách nhạc nền (`592`); Đang tải các danh sách nhạc (`618`); Kéo xuống còn giọng khác (`671`); Đã chọn giọng {} (`762`); Dừng (`790`); Thử (`790`); Thêm giọng (`808`); Chưa làm trước được (`884`); Dừng làm trước (`898`); Làm trước chương sau (`904`); Làm trước {} chương tới (`904`); Chỉ khi đang sạc (`915`); Chưa xoá được bản đọc (`945`); Xoá bản đọc (`956`); Xoá (`959`); Hẹn giờ đã tắt tiếng lúc (`994`); Bật lại (`1003`); Tiếng nhỏ dần (`1011`); Hẹn giờ ngủ trên {} (`1077`); ... +30
- `listen/PlaylistChoice.tsx` (9): Nhạc nền: {} (`67`); Nhạc nền: để máy chọn{} (`67`); Đã lưu lựa chọn (`74`); Chưa chỉnh được mức nhạc (`92`); Đang thêm nhạc (`100`); Đang thêm nhạc {}/{}… (`100`); Đang thêm nhạc thì dừng (`113`); Không mở được hộp chọn file (`115`); Đang tải danh sách (`206`)
- `listen/ProjectFileItems.tsx` (18): Mở dự án (`40`); Chưa dựng được xưởng (`43`); Cần cài Studio (card NVIDIA) - (`81`); Cần cập nhật Studio - (`81`); Studio cần sửa - (`81`); Mở dự án Studio (`102`); Tạo sách nói (`106`); Việc của xưởng (`134`); Mở xưởng đã dựng (`139`); Dựng xưởng (`142`); Việc cần duyệt (`189`); Kịch bản (`190`); Cách đọc tên (`191`); Đóng (`204`); Màn (`214`); Đang tải việc xưởng (`217`); Không còn việc nào cần quyết. (`255`); Ngoài ra: (`257`)
- `listen/ReadAlongText.tsx` (1): Nghe từ “{}” (`55`)
- `listen/ReadAloudStorage.tsx` (2): Đã dọn bản đọc đã làm (`52`); Chưa dọn được bản đọc (`56`)
- `listen/ReaderScreen.tsx` (9): Không mở được chương này (`279`); Về trang sách (`279`); Điều khiển đọc (`357`); Nghe từ đây (`365`); Cỡ chữ và giãn dòng (`370`); Cỡ chữ (`376`); Cỡ chữ {} (`380`); Giãn dòng (`392`); Chương tiếp theo (`459`)
- `listen/ReadingSuggestions.tsx` (6): Bỏ dòng này khỏi phần đọc (`75`); Chưa đổi được phần đọc (`121`); Bỏ dòng khỏi phần đọc (`160`); Gợi ý cho phần đọc (`187`); Bỏ qua gợi ý (`223`); Đóng (`227`)
- `listen/SendEdits.tsx` (6): Chưa gửi được về {} (`40`); Gửi về {} (`59`); Gửi về {} ({} thay đổi) (`59`); Đặt lại bản của máy này (`104`); Đã hiểu (`110`); Gửi về (`170`)
- `listen/SentenceMenu.tsx` (9): Đã chép câu (`117`); Chưa chép được (`119`); Nghe từ đây (`136`); Nghe từ câu này (`137`); Sửa cách đọc (`152`); Sửa câu này (`167`); Sửa trong Studio (`167`); Chép câu (`171`); Bỏ chọn câu (`173`)
- `listen/Shortcuts.tsx` (11): Phát / tạm dừng (`17`); Space (`17`); Lùi / tới 15 giây (`18`); Chương trước / sau (`19`); Shift (`19`); Tắt / bật tiếng (`20`); Giảm / tăng tốc độ đọc (`21`); Esc (`22`); Thu nhỏ màn hình đang nghe (`22`); Xem các phím tắt này (`23`); Phím tắt (`86`)
- `listen/VieneuDownload.tsx` (3): Chưa tải được giọng VieNeu (`35`); Đang tải giọng VieNeu (`60`); Xem trong Cài đặt (`108`)
- `listen/VieneuModuleCard.tsx` (12): Bộ giọng (`89`); Tải, đo và quản lý (`101`); Đã chuyển sang giọng VieNeu Nano (`204`); Đã chuyển sang giọng trực tuyến (`204`); Đang tải {} (`237`); Chưa huỷ được việc tải {} (`239`); Khuyên dùng (`265`); Đã có (`271`); Đã có sẵn (`271`); Gỡ (`275`); Chưa đổi được cách đọc (`291`); Dùng bản tăng tốc (`293`)
- `listen/VoiceSettings.tsx` (11): Không làm được lúc này. (`73`); Chưa dùng được (`175`); Dùng được · {} giọng (`175`); Tô đúng từng chữ đang đọc. (`181`); Nhận khoá (`183`); Khoá (`186`); Đang dùng: (`277`); Đang tải giọng đọc (`278`); Mặc định (`326`); Dừng (`338`); Thử giọng (`338`)
- `listen/VoiceSpeedSetting.tsx` (2): Chưa đổi được tốc độ giọng (`63`); Chưa tải được bản nhanh hơn (`72`)
- `listen/WishesDialog.tsx` (6): Không bỏ được thay đổi này (`46`); Việc chờ Studio (`52`); Việc chờ gửi (`52`); Đóng (`53`); Đang xem các thay đổi (`69`); Chưa có việc nào đang chờ. (`73`)
- `listen/WordReadings.tsx` (20): Dừng nghe thử (`35`); Dừng (`43`); Nghe thử (`43`); Không hoàn tác được (`76`); Chưa lưu được cách đọc (`83`); Cách đọc cho {} (`97`); Lưu cho cả cuốn (`111`); Đọc như chữ trong sách (`115`); Đọc từ này là (`149`); Gõ cách đọc cho (`156`); Các từ trong câu (`167`); Nối thành cụm (`193`); Thôi (`200`); Bấm một chữ để chọn. (`205`); Đang tải cách đọc (`229`); Chưa có từ nào. (`230`); Sửa cách đọc {} (`252`); Bỏ cách đọc {} (`254`); Chưa bỏ được cách đọc (`262`); Sửa cách đọc (`278`)
- `listen/bookSearch.ts` (1): Máy chủ không trả chương nào (`112`)
- `listen/clip.tsx` (1): Chưa nghe thử được (`92`)
- `listen/follow.ts` (6): ArrowDown (`66`); ArrowUp (`66`); End (`66`); Home (`66`); PageDown (`66`); PageUp (`66`)
- `listen/importQueue.ts` (5): Đã mở (`73`); Sách {}/{} (`87`); Đã thêm từ file này rồi (`109`); Đã thêm {} sách (`133`); Không thêm cuốn nào (`140`)
- `listen/labels.ts` (15): Đang chuẩn bị giọng đọc (`9`); Đã nghe hết cả cuốn (`27`); Đã nghe {} {} · {} (`31`); Chưa nghe · {} chương (`40`); Nghe tiếp · {} (`59`); Đang tải âm thanh (`65`); Đây là chương cuối (`79`); Chương sau chưa có audio (`80`); Shift+→ (`80`); Đang thu âm (`90`); Bấm (`101`); Chạm (`101`); Máy này chưa có giọng đọc. (`121`); Nghe bằng giọng đọc.{} (`123`); Các chương sau chưa có audio. (`145`)
- `listen/liveClip.ts` (2): Đã bỏ đoạn này. (`156`); Giọng đọc không phản hồi. (`192`)
- `listen/liveTestKit.ts` (1): QuotaExceeded (`12`)
- `listen/model.ts` (3): Phần {} · {} (`364`); Dự án (`497`); Đã nhập (`497`)
- `listen/musicBed.ts` (1): Content-Type (`139`)
- `listen/onlineConsent.ts` (1): Microsoft (`14`)
- `listen/player.tsx` (8): Đã tới câu chọn (`575`); Đã tới {} (`575`); Chưa tải được nhạc (`635`); Đã nghe hết sách (`948`); Chương sau chưa có audio (`1162`); Đọc chương ấy (`1164`); Nghe thêm {} phút (`1257`); Vẫn đang nghe (`1721`)
- `listen/playlistBed.ts` (4): Đã thêm {} bài (`357`); Không thêm được file nào (`359`); Không thêm được file này (`359`); Danh sách đã chọn (`388`)
- `listen/prepareAhead.ts` (8): Chưa lưu bản đọc nào. (`73`); Vừa chỗ trống cho {} chương: (`145`); Đã sẵn sàng {}/{} chương (`162`); Đang làm trước {}{}: {}/{} đoạn{}. (`169`); Đã làm trước {}{}: {}{}. (`175`); Làm trước bị dừng. (`177`); Đã dừng làm trước ({}{}). (`178`); Đã dừng làm trước. (`178`)
- `listen/readAloud.ts` (4): Không tải được đoạn giọng đọc. (`58`); ReadAloudEngine cần track.speech (`485`); Không phát được clip giọng đọc. (`1772`); Giọng đọc không phản hồi. (`1943`)
- `listen/readAloudVoice.ts` (10): Không có mạng - giọng (`33`); Giọng {} đang không dùng được. (`48`); Ngọc Linh (`204`); Phạm Tuyên (`204`); Thanh Bình (`204`); Mỹ Duyên (`205`); Ái Hân (`205`); Đức Trí (`205`); Giọng đọc của máy (`242`); Máy này chưa có giọng đọc. (`362`)
- `listen/readings.ts` (1): Chưa nghe thử được lúc này. (`161`)
- `listen/saveFailure.ts` (1): Chưa lưu được chỗ đang nghe (`16`)
- `listen/sleep.ts` (2): Hẹn giờ ngủ: còn {} giây (`82`); Hẹn giờ ngủ: còn {} phút (`82`)
- `listen/textImport.ts` (1): Tách theo {} dòng “Chương N” (`180`)
- `listen/vieneuModule.ts` (5): Đang đọc bằng bản thường. (`131`); Đang đọc bằng bản tăng tốc. (`133`); Đang tải {} ({}) {}% (`285`); Máy này chưa dùng được {}. (`288`); Đang tải {} (`302`)
- `listen/voiceGroups.ts` (2): Nam (`23`); Nữ (`23`)
- `shared/BookCover.tsx` (1): Chữ bìa trên hoạ tiết sóng (`74`)
- `shared/ChapterPreview.tsx` (2): Đưa vào sách: {} (`91`); Bấm để đổi tên chương (`129`)
- `shared/CoverSearch.tsx` (7): Google Books (`11`); Open Library (`11`); Đã đặt ảnh bìa (`74`); Tên sách để tìm bìa (`115`); Đang tìm ảnh bìa (`129`); Bạn hãy chọn ảnh trên máy (`165`); Tìm ảnh bìa (`184`)
- `shared/DiagnosticsView.tsx` (2): Chi tiết kỹ thuật (`23`); Nhật ký của ABook ({} dòng) (`26`)
- `shared/ErrorDetails.tsx` (1): Chi tiết (`9`)
- `shared/MissingLibrary.tsx` (3): Chọn lại thư mục thư viện (`19`); Không thấy thư mục thư viện (`19`); Chọn thư mục (`27`)
- `shared/OnComputerOnly.tsx` (1): Làm (`16`)
- `shared/RowBoundary.tsx` (1): Hàng danh sách lỗi (`13`)
- `shared/SettingsNav.tsx` (3): Nhóm cài đặt (`52`); Về Cài đặt (`79`); Tìm hiểu thêm (`123`)
- `shared/ToastDetails.tsx` (2): Chi tiết (`36`); Chi tiết thông báo (`39`)
- `shared/diagnostics.ts` (19): Tải sách (`50`); Xuất M4B (`50`); Xuất MP3 (`50`); Xuất sách nói (`50`); Việc nền (`58`); Việc {} (`59`); Pha: {} (`61`); Bản ABook (`103`); Điện thoại (`107`); Giờ trên máy (`111`); Pin (`115`); Mạng (`119`); Chỗ trống (`125`); Chạy nền (`130`); Cho máy khác nghe thư viện (`146`); Lần tắt gần nhất (`150`); Lần văng (`154`); Phục hồi dữ liệu (`155`); Chưa có dòng nào. (`173`)
- `shared/editsKept.ts` (1): Đã gộp {} sửa từ file (`12`)
- `shared/editsSync.ts` (2): Đã gửi về {} {} (`70`); Đã gửi về {} (`77`)
- `shared/latestRequest.ts` (1): AbortError (`20`)
- `shared/musicLevels.ts` (1): Rất nhỏ (`10`)
- `shared/pdfPages.ts` (1): PasswordException (`38`)
- `shared/peerStudio.ts` (1): Đang mở Studio của {} (`52`)
- `shared/syncSwitch.ts` (1): Kết nối Wi-Fi (`3`)
- `shared/title.ts` (1): ABook (`3`)
- `shared/trashUndo.ts` (3): Đã khôi phục “{}” (`16`); Chưa mang theo chỗ nghe. (`24`); Chưa hoàn tác được (`98`)
- `shared/ui.tsx` (3): Xem các tab trước (`514`); Xem các tab sau (`519`); Đóng (`699`)
- `shared/unpair.ts` (1): Đã bỏ ghép {} (`35`)

### c3. Chỉ có ở web phía máy tính / Studio (chỉ đếm)

| thư mục | nhãn |
|---|---|
| desktop/ | 256 |
| studio/ | 747 |

## d. Chữ hoa, dấu câu, `…` và `...`, dấu thanh, số

**d1. Cùng nhãn (theo khoá lỏng) nhưng khác nguyên văn giữa hai phía** (11):

| web | native | khác ở | nơi |
|---|---|---|---|
| chưa vào mạng Wi-Fi nào | Chưa vào mạng Wi-Fi nào | chữ hoa | `android/DevicesScreen.tsx:732` ~ `native/devices/DevicesModel.kt:222` |
| chờ Wi-Fi | Chờ Wi-Fi | chữ hoa | `listen/prepareAhead.ts:152` ~ `native/voice/VoiceSheets.kt:123` |
| cuối chương | Cuối chương | chữ hoa | `studio/credits.ts:80` ~ `native/addbook/AddBookScreen.kt:143` |
| Giấy phép: | Giấy phép | dấu câu cuối | `listen/PlayerViews.tsx:1299` ~ `native/music/MusicPanel.kt:444` (+1) |
| hẹn | Hẹn | chữ hoa | `android/SettingsScreen.tsx:188` (+1) ~ `native/screens/SettingsGroups.kt:153` |
| Lùi {} giây | Lùi 15 giây | dấu thanh / ký tự | `listen/PlayerViews.tsx:261` ~ `native/nowplaying/NowPlayingScreen.kt:158` |
| Mở Cài đặt | Mở cài đặt | chữ hoa | `android/DevicesScreen.tsx:217` (+1) ~ `native/devices/CompanionSurfaces.kt:133` (+2) |
| Tới {} giây | Tới 15 giây | dấu thanh / ký tự | `listen/PlayerViews.tsx:286` ~ `native/nowplaying/NowPlayingScreen.kt:160` |
| {} - Đang dùng: {} ({}) | {} - Đang dùng: {} ({}). | dấu câu cuối | `listen/voiceSpeed.ts:68` ~ `native/data/SettingsRepo.kt:260` |
| đang phát | Đang phát | chữ hoa | `android/RemotePlayers.tsx:361` (+1) ~ `native/devices/CompanionSurfaces.kt:66` (+1) |
| Đã xoá nhật ký | Đã xoá nhật ký. | dấu câu cuối | `android/Diagnostics.tsx:51` ~ `native/screens/SettingsAdvanced.kt:53` |

**d2. Kiểu viết theo phía** (số chữ khớp / tổng; chữ quét ở trên):

| kiểu | web | native |
|---|---|---|
| dấu ba chấm ASCII `...` | 8 / 5846 | 0 / 722 |
| dấu ba chấm `…` | 62 / 5846 | 0 / 722 |
| kết thúc bằng dấu chấm `.` | 1005 / 5846 | 122 / 722 |
| kết thúc bằng `!` | 0 / 5846 | 0 / 722 |
| kết thúc bằng `:` | 55 / 5846 | 0 / 722 |
| dấu thanh kiểu cũ `oà oá uý` | 466 / 5846 | 74 / 722 |
| dấu thanh kiểu mới `òa óa úy` | 1 / 5846 | 0 / 722 |
| số thập phân dấu phẩy `1,5` | 1 / 5846 | 0 / 722 |
| số thập phân dấu chấm `1.5` | 0 / 5846 | 0 / 722 |
| nhân bằng `×` | 0 / 5846 | 0 / 722 |
| nhân bằng `x` sau số | 0 / 5846 | 0 / 722 |
| ngăn cách `·` | 132 / 5846 | 23 / 722 |
| ngăn cách ` - ` | 296 / 5846 | 20 / 722 |
| gạch dài `—`/`–` | 10 / 5846 | 1 / 722 |
| giờ `1:30` hay `1 giờ 30` | 4 / 5846 | 2 / 722 |
| dấu `%` dính số | 0 / 5846 | 0 / 722 |
| dấu `%` cách số | 0 / 5846 | 0 / 722 |

**d3. Nhãn ngắn bắt đầu bằng chữ thường** (web 159, native 0); 15 đầu mỗi phía:

- web: bạn đã chọn · (`listen/ProjectFileItems.tsx:290`); bắt đầu (`studio/NewProjectScreen.tsx:704`); bắt đầu ngay (`desktop/BookTemplates.tsx:107`); bắt đầu. (`studio/NewProjectScreen.tsx:711`); bỏ chọn (`studio/WorkInbox.tsx:1279`); chưa cài (`studio/ProjectScreen.tsx:817`); chưa nghe (`listen/BookScreen.tsx:706`); chưa phân tích tới (`studio/NameReadings.tsx:289`); chưa thu - không tốn gì (`studio/ApplyChanges.tsx:91`); chưa vào mạng Wi-Fi nào (`android/DevicesScreen.tsx:732`); chương (`listen/AddBook.tsx:696`); chương (`studio/NewProjectScreen.tsx:646`); chương (`studio/NewProjectScreen.tsx:898`); chương (`studio/NewProjectScreen.tsx:913`); chương (`studio/ProjectScreen.tsx:786`)
- native: (không có)

**d3b. Chữ dùng dấu thanh kiểu mới (`òa óa úy`) - kiểu thiểu số** (DESIGN.md chưa chọn kiểu nào); 12 đầu mỗi phía:

- web: Chữ của cả cuốn được gửi tới {} để đọc, bằng khóa của bạn -… (`desktop/listenExport.ts:85`)
- native: (không có)

**d4. web: cùng nhãn nhưng viết khác nhau trong chính phía này** (63); 15 đầu:

- `Ai nghĩ câu này` | `Ai nghĩ câu này?` (`listen/LineWishes.tsx:430`, `listen/LineWishes.tsx:492` (+2))
- `Ai nói câu này` | `Ai nói câu này?` (`listen/LineWishes.tsx:430`, `listen/LineWishes.tsx:492` (+4))
- `Buồn` | `buồn` (`studio/ScriptTab.tsx:183`, `studio/musicScenes.ts:29` (+1))
- `Bắt đầu` | `bắt đầu` | `bắt đầu.` (`android/ExportAudiobook.tsx:258`, `android/ExportM4b.tsx:161` (+6))
- `Bỏ ghép {}` | `Bỏ ghép {}?` (`android/DevicesScreen.tsx:1007`, `android/DevicesScreen.tsx:775` (+7))
- `Chưa cài` | `Chưa cài.` | `chưa cài` (`desktop/SettingsScreen.tsx:513`, `studio/ProjectScreen.tsx:817` (+1))
- `Chưa ghép được` | `Chưa ghép được:` (`android/DevicesScreen.tsx:458`, `desktop/OtherComputers.tsx:101` (+1))
- `Chưa nghe` | `chưa nghe` (`listen/BookScreen.tsx:1027`, `listen/BookScreen.tsx:155` (+2))
- `Chưa nghe thử được` | `Chưa nghe thử được:` (`listen/clip.tsx:92`, `studio/TryReading.tsx:146`)
- `Chưa thêm được chữ sáng` | `Chưa thêm được chữ sáng.` (`studio/WordTimings.tsx:33`, `studio/WordTimings.tsx:42`)
- `Chương {}` | `chương {}` (`listen/ProjectFileItems.tsx:269`, `listen/ReadingSuggestions.tsx:52` (+4))
- `Chất lượng` | `chất lượng` (`desktop/SettingsScreen.tsx:94`, `studio/NewProjectScreen.tsx:1340` (+4))
- `Cách đọc chung` | `cách đọc chung` (`desktop/SettingsScreen.tsx:413`, `studio/sharedReadings.tsx:170`)
- `Cả cuốn` | `cả cuốn` (`android/ExportMp3.tsx:179`, `listen/labels.ts:29`)
- `Dịu dàng` | `dịu dàng` (`studio/ScriptTab.tsx:187`, `studio/musicScenes.ts:29`)

**d4. native: cùng nhãn nhưng viết khác nhau trong chính phía này** (4); 15 đầu:

- `Chưa nghe thử được giọng này` | `Chưa nghe thử được giọng này.` (`native/voice/VoiceRepo.kt:106`, `native/voice/VoiceState.kt:274` (+1))
- `Xoá khoá` | `Xoá khoá?` (`native/voice/VoiceSheets.kt:249`, `native/voice/VoiceSheets.kt:273` (+1))
- `Xoá phần đã tải` | `Xoá phần đã tải?` (`native/components/Confirm.kt:95`, `native/voice/VoiceSheets.kt:102` (+2))
- `ĐANG NGHE` | `Đang nghe` (`native/nowplaying/NowPlayingScreen.kt:68`, `native/nowplaying/PlayerSheets.kt:139`)
## e. Cặp màn web <-> native (luật cứng, scripts/ui_parity_pairs.json)

Trong một cặp, mỗi nhãn ngắn phải có ở cả hai phía (khoá lỏng) trừ khi nằm trong `allow` (có lý do) hay `missing` (tính năng native chưa có thật - Lead xếp lịch). Cột lệch phải bằng 0 thì `--check` mới qua.

| cặp | nhãn web | nhãn native | lệch web | lệch native | cho phép | thiếu thật |
|---|---|---|---|---|---|---|
| now-playing | 100 | 41 | 0 | 0 | 34 | 38 |
| shared-labels | 30 | 491 | 0 | 0 | 7 | 13 |
| library-book | 196 | 81 | 0 | 0 | 49 | 103 |
| settings | 125 | 96 | 0 | 0 | 17 | 34 |
| devices | 137 | 119 | 0 | 0 | 96 | 10 |
| voice | 130 | 98 | 0 | 0 | 94 | 15 |
| add-edit-book | 180 | 71 | 0 | 0 | 93 | 39 |

Thiếu thật ở native - `now-playing`: Bật lại; Chưa làm trước được; Chưa xoá được bản đọc; Chương này chưa có audio hoàn chỉnh - đ…; Chỉ khi đang sạc; Chọn giọng khác; Dừng; Dừng làm trước; Giữ lại; Gợi ý đọc; Hẹn giờ đã tắt tiếng lúc; Hết giờ thì {} tạm dừng, chỗ đang nghe …; Làm trước chương sau; Làm trước {} chương tới; Nghe cuốn khác; Nghe kiểm; Nghe lại từ đầu; Nghe tiếp; Nghe tiếp từ đó; Nghe tiếp {}; Nghe {}; Sáng hôm sau, thẻ “Tối qua” giúp tìm lạ…; Sắp tắt ·; Sẽ dừng khi hết chương này.; Thêm giọng; Thử; Tiếng nhỏ dần; Tải giọng VieNeu; Về thư viện; Xoá; Xoá bản đọc; Đang làm trước cho một cuốn hay giọng k…; Đã nghe chương này; Đã nghe hết cuốn này.; Đã nghe hết phần đã có; Đã nghe hết sách.; Đóng lời báo; Đọc bằng

Thiếu thật ở native - `shared-labels`: Chưa có audio; bạn vẫn đọc được chữ.; Chương sau chưa có audio; Chương tiếp theo sẽ nghe được khi máy l…; Các chương sau chưa có audio.; Máy này chưa có giọng đọc.; Nghe bằng giọng đọc.{}; Nghe tiếp · {}; Đang chuẩn bị giọng đọc; Đang thu âm; Đang tải âm thanh; Đây là chương cuối; Đã nghe hết cả cuốn; Đã nghe {} {} · {}

Thiếu thật ở native - `library-book`: Bỏ gộp; Bỏ gộp {} vào {}; Chiếm {}; Chuyển; Chuyển hồ sơ; Chuyển sang cuốn; Chuyển sang cuốn khác; Chưa có chương nghe được{}; Chưa có dàn nhân vật; Chưa có giọng; Chưa có lịch sử nghe; Chưa xếp lại hàng chờ làm sách.; Chưa đủ chương; mở file sách mới hơn để…; Chưa đủ chương; đang dừng thu.; Chương sau; Chương tiếp theo; Chương trước; Chỉ có chữ; Chọn cuốn; Chọn câu cuối cùng còn nhớ:; Chờ áp dụng; Chờ áp dụng: giọng; Có sách trên máy khác; Cỡ chữ; Cỡ chữ và giãn dòng; Cỡ chữ {}; Dàn nhân vật hiện ra khi truyện đã được…; Dừng; Dừng nghe thử; Giãn dòng; Gộp vào người khác; Hiện chương sau; Huỷ; Hôm nay; Hôm qua; Hẹn giờ ngủ; Hồ sơ mới; Hồ sơ mới nghe từ đầu; hồ sơ cũ vẫn giữ…; Hồ sơ nghe:; Không mở được chương này

Thiếu thật ở native - `settings`: Bản lưu cũ ({}); Bản trước của một lần lưu hỏng. Lưu ra …; Cho phép thông báo để biết khi sách xon…; Chưa dọn được bản đọc; Chưa gửi được nhật ký; Chưa lưu bản đọc nào.; Chưa lưu ra được; Chưa xoá được; Chưa xoá được nhật ký; Cài đè; sách và chỗ đang nghe giữ nguyê…; Có ABook {} cho điện thoại; Có bản mới {}; Cập nhật; Không mở được trình duyệt; Không đọc được nhật ký; Làm trước bị dừng.; Làm trước để nghe khi không có mạng{}.; Lưu ra; Máy đọc chậm? Làm trước để nghe liền mạ…; Mở Cài đặt; Nghe lại đoạn đã đọc xong thì không phả…; Tìm hiểu thêm; Tải; Vừa chỗ trống cho {} chương:; Xoá; Xoá bản lưu cũ?; Xoá {} bản đọc của cuốn này? Nghe tới đ…; Đang làm trước {}{}: {}/{} đoạn{}.; Đã dọn bản đọc đã làm; Đã dừng làm trước.; Đã dừng làm trước ({}{}).; Đã làm trước {}{}: {}{}.; Đã sẵn sàng {}/{} chương; Đã xoá bản lưu cũ

Thiếu thật ở native - `devices`: Cho hai máy vào cùng một mạng riêng ảo …; Chép địa chỉ; Cài trên máy tính; Cách lấy mã; Cùng Wi-Fi, mở Thiết bị trên máy tính.; Khi chia sẻ, ABook giữ một thông báo nh…; Nghe khi ra ngoài; Sách đã tải vẫn nghe được khi ra ngoài.; Tải ABook Windows; Đã chép địa chỉ

Thiếu thật ở native - `voice`: Bản tăng tốc sẽ dùng từ lần đọc kế.; Bản tăng tốc: máy này không chạy được (…; Chưa cuốn nào dùng giọng này. Bạn tải l…; Chưa tải được bản nhanh hơn; Chưa đổi được cách đọc; Chưa đổi được tốc độ giọng; Các câu đã thu vẫn nghe được.; Dùng bản tăng tốc; Máy này chưa chạy được bản tăng tốc, đa…; Nhận khoá; Tô từng chữ đang đọc theo ước lượng.; Tô đúng từng chữ đang đọc.; Đang đọc bằng bản thường.; Đang đọc bằng bản tăng tốc.; Đã lưu khoá. Bấm “Kiểm tra” để thử.

Thiếu thật ở native - `add-edit-book`: Bạn chọn ảnh từ các nguồn sách hoặc trê…; Bạn hãy chọn ảnh trên máy; Bạn hãy kiểm tra kết nối rồi tìm lại cá…; Bạn hãy kiểm tra kết nối rồi tìm lại ản…; Bạn hãy kiểm tra kết nối rồi đặt lại ản…; Bấm “…” ở dòng chương để đổi tên chương.; Bấm “…” ở dòng chương để đổi tên chương…; Bỏ chọn hết; Bỏ hết thay đổi; Bỏ mọi thay đổi; Bỏ mọi thay đổi ({}); Bỏ phần còn lại; Bỏ và chọn lại; Chưa bỏ được thay đổi; Chưa chọn chương nào - tích ít nhất một…; Chưa nối được {}. Thử lại hoặc chọn ảnh…; Chọn hết; Chọn ảnh bìa; Cách đọc tên; Còn {} cuốn chưa thêm vào thư viện. Chọ…; Còn {} cuốn chưa thêm vào thư viện. Đón…; Dạy cách đọc từ (thường là tên riêng). …; Google Books; Mở cuốn đó; Open Library; Quay lại thêm sách; Sách trở về đúng như người làm sách đã …; Thêm phần còn lại; Thôi; Tên riêng; Tên sách để tìm bìa; Tìm; Tìm bìa; Tìm ảnh bìa; Vẫn thêm bản mới; Đang tìm ảnh bìa; Đang đặt ảnh bìa; Đóng khi còn sách chưa thêm; Đường dẫn file hay thư mục


<!-- ui_parity:end -->
