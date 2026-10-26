# Lệch chữ và icon giữa các nền tảng giao diện

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Ba thứ, ba nguồn chung:

- **Bo góc**: `docs/DESIGN.md` 5.5 -> `scripts/gen_native_tokens.py` -> `Tokens.kt` (native) + `ui/src/shared/tokens.generated.css` (web:
  `rounded-control` / `rounded-cover` / `rounded-sheet`). Luật máy: `ui/src/shared/radiusRules.test.ts`, `RadiusRulesTest.kt`.
- **Icon**: lucide. `scripts/gen_lucide_icons.py` sinh nét cho native và Qt từ đúng gói web dùng; luật `IconRulesTest.kt`.
- **Chữ**: chưa có nguồn chung. Giai đoạn này chỉ ĐO lệch (bảng dưới); chọn dạng chuẩn là việc của Lead, chưa đổi chữ nào.

Bảng dưới do `scripts/ui_parity.py` sinh (`python -X utf8 scripts/ui_parity.py`; `--check` báo lệch, `tests/test_ui_parity.py` chạy `--check`).
Bộ đọc là heuristic trên mã nguồn (không chạy app): chữ nằm trong biểu thức phức tạp hay ghép chuỗi có thể sót; icon của hàng dựng bằng hàm bọc
(vd `GroupIcon(group)`) chưa quy về lucide thì ghi `native:Tên`. Sai lệch được báo cáo chứ KHÔNG làm hỏng test trong giai đoạn này.

<!-- ui_parity:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity.py - không sửa tay, chạy lại script) -->

Quét: web 2264 chữ (1748 khác nhau), 345 cặp nhãn-icon; native 712 chữ (541 khác nhau), 35 cặp nhãn-icon. Nhãn so theo khoá lỏng (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối).

## a. Cùng việc, khác chữ

Cặp nhãn ngắn (<= 6 chữ) mà phía kia KHÔNG có nguyên văn nhưng có nhãn giống (chung từ, gần nhau, hay chung icon). 413 cặp; 40 cặp đầu theo độ giống. `icon` = cùng icon lucide.

| native | web | giống | nơi |
|---|---|---|---|
| Bỏ ghép {}? | Bỏ ghép với {}? | 1.00 | `native/devices/DeviceSheets.kt:129` (+1) ~ `android/DevicesScreen.tsx:991` |
| Chọn giọng | Chọn một giọng | 1.00 | `native/nowplaying/PlayerSheets.kt:160` ~ `studio/NewProjectScreen.tsx:1276` |
| Có bản mới · {} | Có bản mới {} | 1.00 | `native/voice/VoiceModel.kt:291` ~ `android/SettingsScreen.tsx:376` (+1) |
| Cập nhật · {} | Cập nhật | 1.00 | `native/voice/VoiceSheets.kt:79` ~ `android/SettingsScreen.tsx:375` (+2) |
| Cập nhật · {} | Cập nhật ({}) | 1.00 | `native/voice/VoiceSheets.kt:79` ~ `listen/VieneuModuleCard.tsx:324` (+1) |
| File đã chọn | Các file đã chọn | 1.00 | `native/addbook/ImportModel.kt:13` ~ `listen/AddBook.tsx:825` |
| Giọng thử A | Thử giọng | 1.00 | `native/nowplaying/FakeNowPlayingModel.kt:92` ~ `listen/VoiceSettings.tsx:338` |
| Giọng thử B | Thử giọng | 1.00 | `native/nowplaying/FakeNowPlayingModel.kt:92` ~ `listen/VoiceSettings.tsx:338` |
| Khuyên dùng · | Khuyên dùng | 1.00 | `native/voice/VoiceModel.kt:274` ~ `listen/VieneuModuleCard.tsx:265` |
| Khóa {} | Khóa | 1.00 | `native/voice/VoiceSheets.kt:212` ~ `listen/VoiceSettings.tsx:186` |
| Phát | Phát trên | 1.00 | `native/nowplaying/PlayerVisuals.kt:163` (+1) ~ `android/RemotePlayers.tsx:332` (+1) |
| Tên gốc: {} | Tên gốc: | 1.00 | `native/addbook/BookForms.kt:97` ~ `studio/CastEdits.tsx:88` |
| Tải {} | Tải ({}) | 1.00 | `native/voice/VoiceModel.kt:282` ~ `listen/VieneuModuleCard.tsx:329` (+3) |
| Tải {} | Tải · | 1.00 | `native/voice/VoiceModel.kt:282` ~ `android/LibraryDownloads.tsx:20` |
| Tải {} | Đã tải {}% | 1.00 | `native/voice/VoiceModel.kt:282` ~ `desktop/remoteDownloadState.ts:71` |
| Đang dùng: {} | Đang dùng: | 1.00 | `native/screens/SettingsVoice.kt:139` ~ `listen/VoiceSettings.tsx:277` (+2) |
| Đang tải {} · {}% | Đang tải {} | 1.00 | `native/voice/VoiceModel.kt:277` ~ `android/DevicesScreen.tsx:314` (+2) |
| Đang tải {}% | Đang tải {} | 1.00 | `native/screens/RemoteBookSheet.kt:38` ~ `android/DevicesScreen.tsx:314` (+2) |
| Đã bỏ qua | Bỏ qua | 1.00 | `native/addbook/ImportModel.kt:8` ~ `desktop/LibraryMoveRecovery.tsx:43` (+1) |
| Đã có sách | Từ trong sách | 1.00 | `native/addbook/ImportModel.kt:8` ~ `studio/sharedReadings.tsx:105` |
| Đã dừng tải | Dừng tải | 1.00 | `native/screens/RemoteBookSheet.kt:38` ~ `desktop/RemoteDownload.tsx:105` |
| Đã dừng tải | Đã dừng tải ({}) | 1.00 | `native/screens/RemoteBookSheet.kt:38` ~ `desktop/remoteDownloadState.ts:59` |
| Đã thêm: {} | Thêm {} | 1.00 | `native/voice/VoiceModel.kt:371` ~ `listen/LibraryScreen.tsx:203` |
| Đồng ý | Đóng | 1.00 | `native/voice/VoiceSheets.kt:134` ~ `shared/ui.tsx:699` (+2) |
| Đang đo. | Đang đọc… | 0.93 | `native/screens/SettingsAdvanced.kt:57` ~ `listen/AddBook.tsx:630` (+1) |
| Đang đo. | Đang đổi | 0.93 | `native/screens/SettingsAdvanced.kt:57` ~ `studio/MusicTab.tsx:230` |
| Tìm lại thiết bị | Hỏi lại thư viện | 0.93 · icon | `native/devices/PairScreen.kt:209` (+1) ~ `desktop/OtherComputers.tsx:228` (+1) |
| Đang đóng file sách | Đang đọc file sách | 0.92 | `native/screens/BookSheets.kt:150` ~ `listen/AddBook.tsx:668` |
| Chưa gỡ được {} | Chưa mở được: | 0.92 | `native/voice/VoiceRepo.kt:71` (+1) ~ `studio/ProjectsScreen.tsx:69` |
| Theo câu đang nghe | Tới câu đang nghe | 0.91 | `native/nowplaying/ReadAlongPane.kt:111` ~ `listen/ReadAlongText.tsx:177` |
| Cắt ảnh bìa | Đặt ảnh bìa | 0.91 | `native/editbook/CoverCrop.kt:108` ~ `studio/CoverEditor.tsx:112` |
| Chưa bỏ ghép được | Chưa ghép được: | 0.90 | `native/devices/DevicesRepo.kt:107` ~ `desktop/OtherComputers.tsx:317` |
| Dung lượng | Dựng xưởng | 0.90 | `native/devices/StorageScreen.kt:43` (+1) ~ `listen/ProjectFileItems.tsx:142` (+1) |
| Địa chỉ, ví dụ 192.168.1.20 | Địa chỉ, ví dụ 192.168.1.25:47630 | 0.90 | `native/devices/PairScreen.kt:142` ~ `android/DevicesScreen.tsx:552` |
| Đang đóng | Đang dùng: | 0.89 | `native/music/MusicPanel.kt:242` ~ `listen/VoiceSettings.tsx:277` (+2) |
| Chưa nối được máy tính | Chưa nối được máy kia. | 0.88 | `native/devices/DevicesRepo.kt:80` ~ `android/LibraryDownloads.tsx:57` |
| Tới chỗ đang nghe | Tới câu đang nghe | 0.88 | `native/screens/BookScreen.kt:408` ~ `listen/ReadAlongText.tsx:177` |
| Chưa làm được | Chưa mở được: | 0.88 | `native/devices/DevicesRepo.kt:152` (+1) ~ `studio/ProjectsScreen.tsx:69` |
| Thêm thiết bị | Tên thiết bị | 0.88 | `native/devices/PairScreen.kt:130` (+1) ~ `desktop/PhoneSync.tsx:482` |
| Đang nối {} | Đang đổi | 0.88 | `native/devices/PairScreen.kt:159` ~ `studio/MusicTab.tsx:230` |

## b. Cùng nhãn khác icon, cùng icon khác nhãn

**Cùng nhãn, khác icon** (6 nhãn có icon ở cả hai phía mà không chung icon nào):

| nhãn | web | native | nơi |
|---|---|---|---|
| Bỏ ghép | unplug | x | `android/DevicesScreen.tsx:989` ~ `native/devices/DeviceSheets.kt:92` |
| Bỏ ảnh bìa | trash | trash-2 | `listen/EditBook.tsx:450` ~ `native/editbook/EditBookScreen.kt:68` |
| Ghép lại | link-2 | plus | `android/DevicesScreen.tsx:588` (+1) ~ `native/devices/DeviceSheets.kt:89` |
| Thêm | plus | ellipsis | `studio/VolumeSplit.tsx:229` ~ `native/screens/BookScreen.kt:317` |
| Xóa khóa | trash | trash-2 | `listen/VoiceSettings.tsx:216` ~ `native/voice/VoiceSheets.kt:249` |
| Đọc theo | text-align-start | book-open-text | `listen/PlayerViews.tsx:2096` ~ `native/screens/BookSheets.kt:165` |

**Cùng icon, khác nhãn** (11 icon dùng ở cả hai phía mà không chung nhãn nào):

| icon | web | native |
|---|---|---|
| book-open-text | Dừng / Nghe thử, Không mở được chương này, Kịch bản chương này, Phân tích truyện | Đọc theo |
| check | Duyệt câu, Giữ thẻ…, Tạm dừng {}, Áp dụng tất cả | Chưa nghe, Chưa nghe xong, Đang lấy giọng |
| circle-dashed | Chưa nghe / Đã nghe xong, Tạm dừng {} | Chưa nghe, Chưa nghe xong |
| download | Cài Studio, Cài tiếp, Có ABook {}, Dừng tải / Tải tiếp | Cập nhật · {} |
| ellipsis | Thêm tuỳ chọn cho {}, Thêm tuỳ chọn cho đoạn này, Tuỳ chọn dự án {}, Tuỳ chọn Studio | Thêm |
| file-down | Lưu, Lưu thành… | Xuất MP3 hay M4B |
| image-plus | Đổi ảnh bìa | Chọn ảnh |
| laptop | Máy kia không trả lời | Đang mở Studio |
| share-2 | Chia sẻ… | Đang đóng file sách |
| upload | Chọn file, Thêm file | Đang thêm {}/{} |
| x | Bỏ, Bỏ chọn câu, Bỏ qua tất cả, Bỏ qua việc này | Bỏ ghép |

Phủ của bộ ghép: icon dùng ở 78 chỗ trong mã native, ghép được với nhãn chữ ở 35; web 510 chỗ, ghép được 295. Phần còn lại là icon không đi cùng nhãn chữ (nút chỉ icon, chỉ báo) hay nhãn dựng từ model (vd tên nhóm Cài đặt), nên KHÔNG có trong bảng.
Icon native chưa quy về lucide (3): `native:ChevronIcon`, `native:OtherPlayerIcon`, `native:PlayerGlyph`.
Số cặp: web 295, native 35; icon lucide dùng: web 96, native 21.

## c. Nhãn chỉ có ở một phía, theo màn

Nhãn ngắn (<= 6 chữ) không có (theo khoá lỏng) ở phía kia - kể cả chữ giống chữ ở mục a. Để phân biệt tính năng thiếu với chữ trôi: một màn native có nhiều nhãn chỉ-native mà web cùng màn không có thường là tính năng mới; vài nhãn lẻ thường là chữ trôi (mục a).

### c1. Chỉ có ở native (226 nhãn)

- `native/NativeActivity.kt` (2): Settings (`190`); Diagnostics (`201`)
- `native/addbook/AddBookScreen.kt` (11): Thư mục TXT (`87`); Chọn sách từ máy bạn (`91`); Cuối chương (`143`); Xem trước (`160`); Đang xử lý (`164`); Dùng sách có (`165`); Thêm bản riêng (`182`); Tách chương (`185`); Bỏ đọc dòng (`194`); Bỏ số gọi (`211`); Lời chú (`215`)
- `native/addbook/BookForms.kt` (2): Tên gốc: {} (`97`); Về tên gốc (`98`)
- `native/addbook/ImportModel.kt` (7): Chờ bạn xem (`7`); Đang thêm sách (`7`); Đang đọc file (`7`); Đã bỏ qua (`8`); Đã có sách (`8`); Đã thêm (`8`); File đã chọn (`13`)
- `native/addbook/ImportQueue.kt` (2): Bạn hãy thử lại. (`82`); Bạn hãy chọn lại file. (`138`)
- `native/addbook/ImportRepo.kt` (1): Bạn hãy nhập tên sách. (`89`)
- `native/components/Confirm.kt` (2): Xoá khỏi máy? (`94`); Đang xoá (`95`)
- `native/components/ListParts.kt` (1): Sắp có (`380`)
- `native/components/UndoBar.kt` (1): Đã bỏ sách (`26`)
- `native/data/AndroidSettingsCore.kt` (1): Diagnostics (`92`)
- `native/data/BookDetail.kt` (2): Chưa nghe · {} (`147`); Chưa có audio (`153`)
- `native/data/BookSearch.kt` (3): Gõ ít nhất {} ký tự. (`157`); Đang tìm (`158`); Không thấy “{}” trong sách.{} (`161`)
- `native/data/CoverArt.kt` (1): Phần {} (`51`)
- `native/data/DemoPlayback.kt` (1): Chương {} · {} (`13`)
- `native/data/Library.kt` (5): Không đọc được thư viện: {} (`54`); Library (`54`); Không đọc được trang sách: {} (`70`); Không sửa được sách: {} (`118`); Chưa làm được, bạn thử lại (`119`)
- `native/data/LibraryView.kt` (2): Nghe dở (`9`); Xong (`11`)
- `native/data/ListenLogic.kt` (1): Trên {} (`262`)
- `native/data/Settings.kt` (12): Hẹn giờ ngủ (`18`); Giao diện (`19`); Nâng cao (`21`); Sáng (`32`); Tối (`33`); Cộng thêm (`47`); Nhẹ tay (`52`); Vừa (`53`); Mạnh tay (`54`); Không tự lùi (`168`); Lịch đêm {}–{} (`173`); Tự tắt sau {} giờ (`174`)
- `native/data/SettingsRepo.kt` (1): Ghi chú cho người bảo trì (`266`)
- `native/data/UndoDelete.kt` (1): Chưa xoá được, bạn thử lại (`43`)
- `native/devices/CompanionRepo.kt` (2): Chưa nối được, bạn thử lại (`88`); Chưa làm được, bạn thử lại (`141`)
- `native/devices/CompanionSurfaces.kt` (6): Chọn nơi phát (`38`); Đang gửi lệnh (`54`); Chưa phát sách (`66`); Hết chương (`98`); Phát ở đây (`107`); Tìm lại thiết bị phát (`116`)
- `native/devices/DeviceParts.kt` (2): Dùng được đến {} (`125`); Phần đã tải, chưa thành sách (`139`)
- `native/devices/DeviceSheets.kt` (5): Đang mở Studio (`75`); Bỏ ghép {}? (`129`); Đang bỏ ghép (`136`); Tên máy này (`150`); Đang lưu (`158`)
- `native/devices/DevicesJson.kt` (1): Sách tải dở (`59`)
- `native/devices/DevicesModel.kt` (13): Wi-Fi (`178`); Bluetooth: {} máy đang nối (`231`); Chưa kết nối (`275`); Đang nối qua Bluetooth (`276`); Đang nối qua Tailscale (`282`); Đang nối qua Wi-Fi nhà (`283`); Đang nối qua mạng (`285`); Chưa thấy (`290`); Thấy {} (`290`); Gửi trước rồi bỏ ghép (`319`); Thử gửi trước rồi bỏ ghép (`321`); Bỏ ghép {}? (`325`); Vẫn bỏ ghép, bỏ thay đổi (`325`)
- `native/devices/DevicesRepo.kt` (6): Chưa dùng được Bluetooth (`58`); Chưa kết nối được (`65`); Chưa nối được máy tính (`80`); Chưa bỏ ghép được (`107`); Chưa mở được Studio (`148`); Chưa làm được (`152`)
- `native/devices/DevicesState.kt` (4): Chưa nối (`69`); Đã nối {} (`69`); Đang bật · {} máy (`71`); Bạn hãy thử lại. (`121`)
- `native/devices/PairScreen.kt` (13): Thêm thiết bị (`79`); Tìm lại thiết bị (`90`); Máy đã nối (`97`); Sách trên {} (`113`); Cách nối (`135`); Địa chỉ máy tính (`142`); Địa chỉ, ví dụ 192.168.1.20 (`142`); 6 số trên máy tính (`149`); Mã ghép (`149`); Đang nối {} (`159`); Đang tìm máy (`170`); Chưa thấy máy nào (`171`); Cần quyền Thiết bị ở gần (`180`)
- `native/devices/ShareScreen.kt` (4): Cho máy khác nghe (`57`); Tạo mã ghép (`67`); Cần quyền Thiết bị ở gần (`78`); Cho ABook chạy nền (`84`)
- `native/devices/StorageScreen.kt` (3): Dung lượng (`43`); Còn trống {} (`48`); Chưa có gì trên máy (`52`)
- `native/editbook/BookEditor.kt` (2): Bạn hãy thử lại. (`33`); Bạn hãy thử lưu lại. (`65`)
- `native/editbook/CoverCrop.kt` (6): Bạn hãy chọn lại ảnh. (`105`); Cắt ảnh bìa (`108`); Dùng ảnh (`110`); Đang lưu (`110`); Đang đọc ảnh (`125`); Phóng to (`149`)
- `native/editbook/EditBookScreen.kt` (5): Chọn ảnh (`67`); Đang đọc sách (`85`); Gửi phần sửa (`104`); Gốc: {} (`116`); Nhãn (`153`)
- `native/editbook/EditModel.kt` (2): Bạn hãy nhập tên sách. (`54`); Bạn hãy nhập tên chương. (`55`)
- `native/music/MusicModel.kt` (6): Để máy chọn (`184`); Theo cảnh (`186`); Máy chọn (`227`); Chưa có nhạc (`228`); Danh sách đã chọn (`231`); Hợp không khí đoạn này (`318`)
- `native/music/MusicPanel.kt` (2): Đang đóng (`242`); Trang của bài (`448`)
- `native/music/MusicRepo.kt` (3): Chưa đổi được nhạc nền (`46`); Chưa tìm được bài để đổi (`68`); Chưa thêm được nhạc (`74`)
- `native/music/MusicState.kt` (2): Chưa thêm được nhạc (`138`); Chưa đổi được nhạc nền (`170`)
- `native/nowplaying/FakeNowPlayingModel.kt` (5): Chương 1 · Một buổi sớm (`70`); Những ngày gió hát (`70`); Chương {} · {} (`72`); Giọng thử A (`92`); Giọng thử B (`92`)
- `native/nowplaying/NowPlayingModel.kt` (1): Hết chương (`95`)
- `native/nowplaying/NowPlayingScreen.kt` (5): Về chế độ nghe (`97`); Lùi 15 giây (`158`); Tới 15 giây (`160`); Vị trí nghe (`208`); Về chỗ cũ (`301`)
- `native/nowplaying/PlayerSheets.kt` (7): Đóng bảng (`70`); Hết chương (`126`); Chọn giọng (`160`); Giọng (`160`); Giọng thu sẵn (`160`); Hẹn giờ ngủ (`182`); Đồng hồ cũng tạm dừng. (`212`)
- `native/nowplaying/PlayerVisuals.kt` (1): Phát (`163`)
- `native/nowplaying/ReadAlongPane.kt` (2): Đang tải chữ (`69`); Theo câu đang nghe (`111`)
- `native/player/MiniPlayer.kt` (1): Phát (`109`)
- `native/screens/BookScreen.kt` (2): Thêm việc với sách (`317`); Tới chỗ đang nghe (`408`)
- `native/screens/BookSheets.kt` (5): Chia sẻ file sách (`150`); Đang đóng file sách (`150`); Xuất MP3 hay M4B (`177`); Xoá khỏi máy (`179`); Chương này chưa có audio. (`214`)
- `native/screens/LibraryChrome.kt` (1): Đóng ô tìm (`228`)
- `native/screens/LibraryScreen.kt` (3): Thêm sách để bắt đầu nghe. (`160`); Không có sách nào (`178`); Trên máy tính (`240`)
- `native/screens/RemoteBookSheet.kt` (3): Trên {} (`26`); Đang tải {}% (`38`); Đã dừng tải (`38`)
- `native/screens/SettingsAdvanced.kt` (11): Việc app làm gần đây (`49`); Bạn chọn gửi cho ai (`51`); Đã xoá nhật ký. (`53`); Đang đo. (`57`); Chưa có bản đọc đã lưu. (`59`); Dọn (`78`); Làm mới nhật ký (`133`); Đang đọc nhật ký. (`138`); Nhật ký đang trống. (`139`); Đang mở danh sách. (`159`); Bản này chưa gói danh sách. (`160`)
- `native/screens/SettingsGroups.kt` (6): Không (`59`); Im khi đang nghe. (`72`); Nút tai nghe (`99`); Tự chọn nhạc nền (`102`); Dung lượng (`269`); Tên máy này (`272`)
- `native/screens/SettingsParts.kt` (1): Sắp có (`87`)
- `native/screens/SettingsScreen.kt` (1): Phiên bản {} (`104`)
- `native/screens/SettingsVoice.kt` (4): Chưa tải được giọng (`132`); Đang dùng: {} (`139`); Khóa giọng trực tuyến (`191`); Đang lấy giọng (`263`)
- `native/voice/AndroidSamplePlayer.kt` (1): Voice (`33`)
- `native/voice/KeysScreen.kt` (3): Khóa giọng trực tuyến (`28`); Chưa đọc được các khóa (`35`); Khóa chỉ lưu trên máy này. (`36`)
- `native/voice/VoiceModel.kt` (18): Khóa chưa dùng được. (`144`); Giọng VieNeu Nano (`214`); Supertonic nhanh hơn (`219`); Dùng giọng VieNeu Nano (`243`); Tải giọng VieNeu Nano (`244`); Dùng giọng trực tuyến (`246`); Máy này chưa dùng được. (`254`); Máy này chưa dùng được: {}. (`254`); Khuyên dùng · (`274`); Đang tải {} · {}% (`277`); Tải {} (`282`); Có bản mới · {} (`291`); Đã có trên máy (`294`); Azure Speech (`305`); Google Cloud (`305`); Viettel AI (`305`); Chưa có khóa (`344`); Đã thêm: {} (`371`)
- `native/voice/VoiceRepo.kt` (7): Chưa tải được {} (`54`); Chưa gỡ được {} (`71`); Chưa lưu được khóa (`90`); Chưa xoá được khóa (`94`); Chưa kiểm tra được khóa (`98`); Chưa nghe thử được giọng này (`106`); Chưa thêm được nhạc (`116`)
- `native/voice/VoiceSheets.kt` (16): Cập nhật · {} (`79`); Đang đo tốc độ (`83`); Đo lại tốc độ (`83`); Xoá khỏi máy (`88`); Đang xoá (`102`); Dữ liệu di động (`120`); Vẫn tải (`121`); Chờ Wi-Fi (`123`); Gửi chữ ra ngoài? (`133`); Đang lưu (`134`); Đồng ý (`134`); Không (`136`); Khóa {} (`212`); Dán khóa (`213`); Dán khóa trước đã. (`240`); Xoá bài này? (`297`)
- `native/voice/VoiceState.kt` (10): Chưa tải được {} (`161`); Chưa gỡ được {} (`184`); Chưa đổi được giọng (`200`); Dán khóa trước đã. (`226`); Chưa lưu được khóa (`229`); Chưa kiểm tra được khóa (`244`); Chưa xoá được khóa (`254`); Chưa nghe thử được giọng này. (`274`); Chưa thêm được nhạc (`318`); Chưa xoá được bài này (`327`)

### c2. Chỉ có ở web phía điện thoại - listen/, android/, shared/ (360 nhãn)

- `android/App.tsx` (6): Điều hướng (`189`); Chưa có sách trên máy (`207`); Xoá khỏi điện thoại… (`257`); Chiếm {} (`259`); Xoá phần đã tải của “{}”? (`303`); Xoá “{}” khỏi điện thoại? (`303`)
- `android/DevicesScreen.tsx` (43): Studio máy tính (`47`); Tải ABook Windows (`53`); Chép địa chỉ (`55`); Cách lấy mã (`167`); Máy tính tìm thấy (`173`); Tìm lại (`175`); Đang tìm trong mạng Wi-Fi… (`199`); Quyền Bluetooth (`210`); Để sau (`221`); Dùng Bluetooth (`228`); Máy tính đã ghép Bluetooth (`232`); Nhập địa chỉ (`260`); Tự tìm máy tính (`260`); Ví dụ 192.168.1.20:47630 (`263`); Mã ghép nối (`273`); Đang tải {} (`314`); Huỷ tải {} (`326`); Vân tay (`400`); Thiết bị khác (`489`); Ghép thiết bị (`492`); Ghép Bluetooth (`504`); Qua Bluetooth · (`520`); Địa chỉ, ví dụ 192.168.1.25:47630 (`552`); Mã 6 số (`559`); Ghép (`566`); ... +18
- `android/ExportAudiobook.tsx` (3): Đang tính độ dài… (`174`); Xuất sách nói “{}” (`254`); Xuất sách nói (M4B)… (`283`)
- `android/ExportM4b.tsx` (2): Xuất M4B “{}” (`157`); Xuất M4B (`181`)
- `android/ExportMp3.tsx` (3): Có chương đã đổi (`178`); Xuất MP3 “{}” (`208`); Xuất MP3 (`234`)
- `android/ExportRevisions.tsx` (2): Xuất lại các chương đã đổi (`18`); Xuất lại cả file M4B (`19`)
- `android/LibraryDownloads.tsx` (3): Tải · (`20`); Đang tải {} (`21`); Chưa nối được máy kia. (`57`)
- `android/OldSaves.tsx` (3): Xoá bản lưu cũ? (`18`); Xoá (`29`); Lưu ra… (`88`)
- `android/RemotePlayers.tsx` (6): Đang phát trên {} (`145`); Đang dừng trên (`151`); Đang phát trên (`151`); Phát trên thiết bị khác (`321`); Phát trên (`332`); Tìm lại (`347`)
- `android/SettingsScreen.tsx` (9): Nút tai nghe lùi/tới (`130`); Tắt thì nút Trước/Sau chuyển chương. (`130`); Số phút hẹn (`189`); Độ nhạy lắc (`225`); Nền của chữ khi đọc theo. (`280`); Bản lưu cũ ({}) (`300`); Xoá (`330`); Cập nhật (`375`); Có bản mới {} (`376`)
- `android/StudioOpen.tsx` (1): Mở Studio của máy nào? (`125`)
- `android/StudioScreen.tsx` (1): Tạo sách nói từ xa (`31`)
- `android/imports.ts` (2): Thay bằng file này (`32`); Mở sách (`43`)
- `listen/AddBook.tsx` (20): Đóng khi còn sách chưa thêm (`585`); Bỏ phần còn lại (`608`); Bỏ và chọn lại (`608`); Quay lại thêm sách (`610`); Đang đọc file tiếp (`619`); Chọn file sách (`630`); Đang đọc… (`630`); Chọn thư mục TXT (`632`); Đường dẫn file hay thư mục (`647`); Đang đọc file sách (`668`); Tên hiển thị trong thư viện (`682`); Chọn hết (`707`); Bỏ chọn hết (`710`); Định dạng (`763`); Gợi ý phần đọc (`775`); Đang thêm {} (`802`); Các file đã chọn (`825`); Chờ (`833`); Đang thêm (`833`); Đang xem (`833`)
- `listen/BookScreen.tsx` (56): Nghe {} (`84`); Tạm dừng {} (`84`); Đọc {} (chưa có audio) (`103`); Đã làm sẵn (`119`); Đọc chương này (`150`); Đổi tên chương… (`160`); Danh sách chương (`183`); Dừng (`227`); Dừng nghe thử (`228`); Chưa có giọng (`312`); Chờ áp dụng (`317`); Đang chờ máy làm sách (`317`); Bỏ gộp {} vào {} (`327`); Bỏ gộp (`332`); Nghe {} nói (`345`); Đổi giọng {} (`347`); Thêm tuỳ chọn cho {} (`352`); Gộp vào người khác… (`364`); Đổi tên (`369`); Đổi giới tính (`374`); Chưa có dàn nhân vật (`426`); Người kể chuyện (`438`); Mặc định (`439`); Chờ áp dụng: giọng (`441`); Nghe giọng {} (`447`); ... +31
- `listen/DropToAdd.tsx` (1): Thả để thêm sách (`36`)
- `listen/EditBook.tsx` (21): Đang tải nhạc nền (`175`); Lưu tên (`408`); Không rõ tác giả (`423`); Lưu tác giả (`431`); Chọn ảnh bìa… (`444`); Tìm bìa… (`446`); Đang đặt ảnh bìa (`455`); Mở tab Nhạc nền (`466`); Tên riêng (`476`); Cách đọc tên (`481`); Bỏ mọi thay đổi ({}) (`486`); Bỏ hết thay đổi (`489`); Bỏ mọi thay đổi… (`497`); Đổi tên chương (`548`); Số chương hay nhãn (`573`); Tên chương (có thể để trống) (`584`); Chọn thư mục… (`707`); Mặc định: thư mục Đã xuất (`710`); Giọng và lời đọc (`728`); Làm ở Studio trên máy tính (`729`); Sửa ở máy gốc. (`744`)
- `listen/FootnoteChoices.tsx` (2): Không đọc số chú thích (`55`); Đọc lời chú ở cuối chương (`63`)
- `listen/LibraryScreen.tsx` (17): Mở {} (`160`); Nghe ngay {} (`163`); Nghe {} (`163`); Tạm dừng {} (`163`); Đọc {} (`163`); Thêm {} (`203`); Nghe tiếp {}{} (`248`); Mở bộ {} (`376`); Có sách trên máy khác (`384`); Chưa có sách nào (`519`); Lọc sách (`532`); Nghe xong (`534`); Xếp theo: {} (`542`); Gõ không dấu cũng được (`560`); Tên sách, tác giả, giọng (`560`); Xoá ô tìm (`561`); Đóng tìm kiếm (`561`)
- `listen/LineWishes.tsx` (11): Đang chờ máy làm sách (`136`); Các từ trong câu (`194`); Bỏ cách đọc “{}” (`226`); Sửa cách đọc “{}” (`457`); Sửa (`465`); Bỏ: {} (`472`); Ai nghĩ câu này (`492`); Ai nói câu này (`492`); Cách đọc câu (`507`); Sửa cách đọc một từ (`514`); Thu lại câu này (`515`)
- `listen/MorningRecap.tsx` (6): Ẩn thẻ này (`154`); Nghe tới đâu rồi thiếp đi? (`163`); Nghe từ đây (`207`); Thu gọn (`211`); Tìm đúng câu (`211`); Chọn câu cuối cùng còn nhớ: (`219`)
- `listen/MyMusic.tsx` (7): Đang tải bài nhạc (`70`); Nhạc riêng (`152`); Đang tải nhạc riêng (`154`); Xoá bài: {} (`175`); Giữ lại: {} (`178`); Xoá (`183`); Xoá: {} (`183`)
- `listen/OnlineVoicePrompt.tsx` (6): Chọn giọng đọc (`35`); Giọng đọc trực tuyến (`35`); Dừng (`75`); Nghe thử (`75`); Tải giọng chạy trên máy… (`95`); Chọn giọng khác (`101`)
- `listen/PlayerViews.tsx` (51): Vị trí trong chương (`181`); Shift+← (`260`); Lùi {} giây (`261`); Tới {} giây (`286`); Phím (`478`); Đang chuẩn bị nhạc nền… (`578`); Danh sách nhạc nền (`592`); Đang tải các danh sách nhạc… (`618`); Kéo xuống còn giọng khác (`671`); Dừng (`790`); Thử (`790`); Thêm giọng… (`808`); Dừng làm trước (`898`); Làm trước chương sau (`904`); Làm trước {} chương tới (`904`); Chỉ khi đang sạc (`915`); Xoá bản đọc (`956`); Xoá (`959`); Hẹn giờ tắt (`1075`); Dừng khi (`1097`); Tắt sau (`1097`); Dừng phát sau (`1124`); Hết chương này (`1128`); Âm lượng (`1181`); Bật tiếng (`1193`); ... +26
- `listen/PlaylistChoice.tsx` (1): Đang tải danh sách (`200`)
- `listen/ProjectFileItems.tsx` (12): Cần cài Studio (card NVIDIA) - (`81`); Cần cập nhật Studio - (`81`); Studio cần sửa - (`81`); Mở dự án Studio (`102`); Tạo sách nói (`106`); Việc của xưởng (`134`); Mở xưởng đã dựng (`139`); Dựng xưởng (`142`); Màn (`214`); Đang tải việc xưởng (`217`); Không còn việc nào cần quyết. (`255`); Ngoài ra: (`257`)
- `listen/ReadAlongText.tsx` (1): Tới câu đang nghe (`177`)
- `listen/ReadAloudStorage.tsx` (1): Dọn bản đọc (`68`)
- `listen/ReaderScreen.tsx` (9): Không mở được chương này (`279`); Điều khiển đọc (`357`); Nghe từ đây (`365`); Cỡ chữ và giãn dòng (`370`); Cỡ chữ (`376`); Cỡ chữ {} (`380`); Giãn dòng (`392`); Về trang sách (`419`); Chương tiếp theo (`459`)
- `listen/ReadingSuggestions.tsx` (2): Bỏ dòng này khỏi phần đọc (`75`); Gợi ý cho phần đọc (`187`)
- `listen/SendEdits.tsx` (5): Gửi về {} (`59`); Gửi về {} ({} thay đổi) (`59`); Đặt lại bản của máy này (`104`); Đã hiểu (`110`); Gửi về (`170`)
- `listen/SentenceMenu.tsx` (7): Nghe từ đây (`136`); Nghe từ câu này (`137`); Sửa cách đọc (`152`); Sửa câu này (`167`); Sửa trong Studio (`167`); Chép câu (`171`); Bỏ chọn câu (`173`)
- `listen/Shortcuts.tsx` (4): Space (`17`); Shift (`19`); Esc (`22`); Phím tắt (`86`)
- `listen/VieneuDownload.tsx` (2): Đang tải giọng VieNeu (`60`); Xem trong Cài đặt (`108`)
- `listen/VieneuModuleCard.tsx` (11): Bộ giọng (`89`); Đang tải {} (`237`); Khuyên dùng (`265`); Đã có (`271`); Đã có sẵn (`271`); Gỡ (`275`); Dùng bản tăng tốc (`293`); Cập nhật ({}) (`324`); Tải ({}) (`329`); Thử lại tốc độ (`333`); Gỡ “{}” khỏi máy này? (`339`)
- `listen/VoiceSettings.tsx` (10): Tô đúng từng chữ đang đọc. (`181`); Nhận khoá (`183`); Khóa (`186`); Dán khóa của bạn (`187`); Đang dùng: (`277`); Đang tải giọng đọc (`278`); Mặc định (`326`); Dừng (`338`); Thử giọng (`338`); Khoá trực tuyến (`361`)
- `listen/VoiceSpeedSetting.tsx` (1): Tải ({}) (`94`)
- `listen/WishesDialog.tsx` (4): Việc chờ Studio (`52`); Việc chờ gửi (`52`); Đang xem các thay đổi… (`69`); Chưa có việc nào đang chờ. (`73`)
- `listen/WordReadings.tsx` (15): Dừng nghe thử (`35`); Nghe thử {}{} (`35`); Dừng (`43`); Nghe thử (`43`); Cách đọc cho {} (`97`); Lưu cho cả cuốn (`111`); Đọc như chữ trong sách (`115`); Đọc từ này là… (`149`); Các từ trong câu (`167`); Nối thành cụm (`193`); Bấm một chữ để chọn. (`205`); Đang tải cách đọc (`229`); Chưa có từ nào. (`230`); Sửa cách đọc {} (`252`); Bỏ cách đọc {} (`254`)
- `listen/playlistBed.ts` (1): Đã thêm {} bài (`357`)
- `listen/readAloud.ts` (1): Giọng đọc không phản hồi. (`1943`)
- `shared/ChapterPreview.tsx` (2): Đưa vào sách: {} (`91`); Bấm để đổi tên chương (`129`)
- `shared/CoverSearch.tsx` (3): Tên sách để tìm bìa (`115`); Đang tìm ảnh bìa (`129`); Bạn hãy chọn ảnh trên máy (`165`)
- `shared/DiagnosticsView.tsx` (2): Chi tiết kỹ thuật (`23`); Nhật ký của ABook ({} dòng) (`26`)
- `shared/ErrorDetails.tsx` (1): Chi tiết (`9`)
- `shared/MissingLibrary.tsx` (2): Chọn lại thư mục thư viện (`19`); Không thấy thư mục thư viện (`19`)
- `shared/SettingsNav.tsx` (1): Nhóm cài đặt (`52`)
- `shared/ToastDetails.tsx` (2): Chi tiết (`36`); Chi tiết thông báo (`39`)
- `shared/diagnostics.ts` (1): Việc {} (`59`)
- `shared/editsSync.ts` (2): Đã gửi về {} {} (`70`); Đã gửi về {} (`77`)
- `shared/ui.tsx` (3): Xem các tab trước (`514`); Xem các tab sau (`519`); Đóng (`699`)

### c3. Chỉ có ở web phía máy tính / Studio (chỉ đếm)

| thư mục | nhãn |
|---|---|
| desktop/ | 146 |
| studio/ | 453 |

## d. Chữ hoa, dấu câu, `…` và `...`, dấu thanh, số

**d1. Cùng nhãn (theo khoá lỏng) nhưng khác nguyên văn giữa hai phía** (11):

| web | native | khác ở | nơi |
|---|---|---|---|
| chưa vào mạng Wi-Fi nào | Chưa vào mạng Wi-Fi nào | chữ hoa | `android/DevicesScreen.tsx:732` ~ `native/devices/DevicesModel.kt:222` |
| Giấy phép: | Giấy phép | dấu câu cuối | `listen/PlayerViews.tsx:1299` ~ `native/music/MusicPanel.kt:444` (+1) |
| giọng {} | Giọng {} | chữ hoa | `listen/BookScreen.tsx:318` ~ `native/data/BookDetail.kt:115` |
| hẹn | Hẹn | chữ hoa | `android/SettingsScreen.tsx:188` (+1) ~ `native/screens/SettingsGroups.kt:148` |
| Mở Cài đặt | Mở cài đặt | chữ hoa | `android/DevicesScreen.tsx:217` (+1) ~ `native/devices/CompanionSurfaces.kt:133` (+2) |
| Phần | phần | chữ hoa | `studio/NewProjectScreen.tsx:704` (+5) ~ `native/data/ListenLogic.kt:60` (+2) |
| Xóa khóa | Xoá khóa | dấu thanh / ký tự | `listen/VoiceSettings.tsx:216` ~ `native/voice/VoiceSheets.kt:249` (+2) |
| Đang gửi… | Đang gửi | dấu câu cuối | `listen/SendEdits.tsx:59` ~ `native/editbook/EditBookScreen.kt:104` |
| Đang kiểm tra… | Đang kiểm tra | dấu câu cuối | `desktop/SettingsScreen.tsx:185` ~ `native/devices/DevicesModel.kt:84` (+1) |
| Đang mở… | Đang mở | dấu câu cuối | `desktop/App.tsx:436` ~ `native/music/MusicPanel.kt:242` |
| đang phát | Đang phát | chữ hoa | `android/RemotePlayers.tsx:361` (+1) ~ `native/devices/CompanionSurfaces.kt:66` (+1) |

**d2. Kiểu viết theo phía** (số chữ khớp / tổng; chữ quét ở trên):

| kiểu | web | native |
|---|---|---|
| dấu ba chấm ASCII `...` | 1 / 2264 | 0 / 712 |
| dấu ba chấm `…` | 83 / 2264 | 0 / 712 |
| kết thúc bằng dấu chấm `.` | 418 / 2264 | 104 / 712 |
| kết thúc bằng `!` | 0 / 2264 | 0 / 712 |
| kết thúc bằng `:` | 43 / 2264 | 0 / 712 |
| dấu thanh kiểu cũ `oà oá uý` | 154 / 2264 | 49 / 712 |
| dấu thanh kiểu mới `òa óa úy` | 4 / 2264 | 22 / 712 |
| số thập phân dấu phẩy `1,5` | 1 / 2264 | 0 / 712 |
| số thập phân dấu chấm `1.5` | 0 / 2264 | 0 / 712 |
| nhân bằng `×` | 0 / 2264 | 0 / 712 |
| nhân bằng `x` sau số | 0 / 2264 | 0 / 712 |
| ngăn cách `·` | 53 / 2264 | 24 / 712 |
| ngăn cách ` - ` | 74 / 2264 | 15 / 712 |
| gạch dài `—`/`–` | 4 / 2264 | 1 / 712 |
| giờ `1:30` hay `1 giờ 30` | 2 / 2264 | 1 / 712 |
| dấu `%` dính số | 0 / 2264 | 0 / 712 |
| dấu `%` cách số | 0 / 2264 | 0 / 712 |

**d3. Nhãn ngắn bắt đầu bằng chữ thường** (web 151, native 0); 15 đầu mỗi phía:

- web: bạn đã chọn · (`listen/ProjectFileItems.tsx:290`); bắt đầu (`studio/NewProjectScreen.tsx:704`); bắt đầu ngay (`desktop/BookTemplates.tsx:107`); bắt đầu. (`studio/NewProjectScreen.tsx:711`); bỏ chọn (`studio/WorkInbox.tsx:1279`); chưa cài (`studio/ProjectScreen.tsx:817`); chưa nghe (`listen/BookScreen.tsx:706`); chưa phân tích tới (`studio/NameReadings.tsx:289`); chưa thu - không tốn gì (`studio/ApplyChanges.tsx:91`); chưa vào mạng Wi-Fi nào (`android/DevicesScreen.tsx:732`); chương (`listen/AddBook.tsx:696`); chương (`studio/NewProjectScreen.tsx:646`); chương (`studio/NewProjectScreen.tsx:898`); chương (`studio/NewProjectScreen.tsx:913`); chương (`studio/ProjectScreen.tsx:786`)
- native: (không có)

**d3b. Chữ dùng dấu thanh kiểu mới (`òa óa úy`) - kiểu thiểu số** (DESIGN.md chưa chọn kiểu nào); 12 đầu mỗi phía:

- web: Dán khóa của bạn (`listen/VoiceSettings.tsx:187`); Khóa (`listen/VoiceSettings.tsx:186`); Xóa khóa (`listen/VoiceSettings.tsx:216`); Đã lưu {} - dán khóa mới để thay (`listen/VoiceSettings.tsx:187`)
- native: Chưa có khóa (`native/voice/VoiceModel.kt:344`); Chưa kiểm tra được khóa (`native/voice/VoiceRepo.kt:98`); Chưa kiểm tra được khóa (`native/voice/VoiceState.kt:244`); Chưa lưu được khóa (`native/voice/VoiceRepo.kt:90`); Chưa lưu được khóa (`native/voice/VoiceState.kt:229`); Chưa xoá được khóa (`native/voice/VoiceRepo.kt:94`); Chưa xoá được khóa (`native/voice/VoiceState.kt:254`); Chưa đọc được các khóa (`native/voice/KeysScreen.kt:35`); Dán khóa (`native/voice/VoiceSheets.kt:213`); Dán khóa trước đã. (`native/voice/VoiceSheets.kt:240`); Dán khóa trước đã. (`native/voice/VoiceState.kt:226`); Giọng {} dùng khóa {} của bạn: chữ của đoạn đang đọc được g… (`native/voice/VoiceModel.kt:322`)

**d4. web: cùng nhãn nhưng viết khác nhau trong chính phía này** (34); 15 đầu:

- `Ai nghĩ câu này` | `Ai nghĩ câu này?` (`listen/LineWishes.tsx:492`, `studio/ScriptTab.tsx:943`)
- `Ai nói câu này` | `Ai nói câu này?` (`listen/LineWishes.tsx:492`, `studio/ScriptTab.tsx:943`)
- `Chưa nghe` | `chưa nghe` (`listen/BookScreen.tsx:1027`, `listen/BookScreen.tsx:155` (+1))
- `Chọn giọng khác` | `Chọn giọng khác…` (`listen/OnlineVoicePrompt.tsx:101`, `listen/PlayerViews.tsx:1400` (+1))
- `Chọn thư mục` | `Chọn thư mục…` (`listen/EditBook.tsx:707`, `studio/NewProjectScreen.tsx:457` (+1))
- `Chữ hay câu cần tìm` | `Chữ hay câu cần tìm…` (`listen/FindInBook.tsx:109`)
- `Cách đọc chung` | `cách đọc chung` (`desktop/SettingsScreen.tsx:413`, `studio/sharedReadings.tsx:170`)
- `Dừng` | `Dừng…` (`desktop/AudiobookDialog.tsx:54`, `listen/BookScreen.tsx:227` (+14))
- `Giọng đọc` | `Giọng đọc:` (`android/ExportAudiobook.tsx:166`, `desktop/AudiobookDialog.tsx:124` (+2))
- `Hoàn tác` | `hoàn tác` (`shared/trashUndo.ts:79`, `studio/ScriptTab.tsx:1798` (+2))
- `Làm tiếp cuốn này` | `Làm tiếp cuốn này…` (`studio/NewProjectScreen.tsx:1876`, `studio/ProjectScreen.tsx:655`)
- `Nhạc nền` | `Nhạc nền:` (`android/SettingsScreen.tsx:135`, `desktop/SettingsScreen.tsx:234` (+11))
- `Phần` | `phần?` (`studio/NewProjectScreen.tsx:704`, `studio/NewProjectScreen.tsx:711` (+4))
- `Sửa câu này` | `Sửa câu này:` (`listen/SentenceMenu.tsx:167`, `listen/SentenceMenu.tsx:178`)
- `Thôi ghép {}` | `Thôi ghép {}?` (`android/DevicesScreen.tsx:775`, `desktop/OtherComputers.tsx:232` (+3))

**d4. native: cùng nhãn nhưng viết khác nhau trong chính phía này** (5); 15 đầu:

- `Chưa nghe thử được giọng này` | `Chưa nghe thử được giọng này.` (`native/voice/VoiceRepo.kt:106`, `native/voice/VoiceState.kt:274` (+1))
- `Xoá khóa` | `Xoá khóa?` (`native/voice/VoiceSheets.kt:249`, `native/voice/VoiceSheets.kt:273` (+1))
- `Xoá khỏi máy` | `Xoá khỏi máy?` (`native/components/Confirm.kt:94`, `native/components/Confirm.kt:95` (+4))
- `Xoá phần đã tải` | `Xoá phần đã tải?` (`native/voice/VoiceSheets.kt:102`, `native/voice/VoiceSheets.kt:88` (+1))
- `ĐANG NGHE` | `Đang nghe` (`native/nowplaying/NowPlayingScreen.kt:68`, `native/nowplaying/PlayerSheets.kt:139`)

<!-- ui_parity:end -->
