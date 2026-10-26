# Soát native146: mã Kotlin native gộp 26-10

Phạm vi: `git diff 3a414894..07e84542 -- _internal/mobile/android/app/src/main` (xoá sách có Hoàn tác, `Playback.closeBook`, máy phát khác,
màn Xuất, nhạc nền, cài đặt giọng). Soát lỗi đúng / sai, không soát văn phong. Đường dẫn dưới đây tính từ
`_internal/mobile/android/app/src/main/java/vn/abook/player/`; số dòng theo nhánh `dev/cloud-review146`.

## Đã sửa (test đỏ trước, xanh sau)

| # | Chỗ | Kịch bản | Test |
|---|---|---|---|
| 1 | `ui/export/ExportState.kt` `start` | Việc nền hỏng ngay (vd. mất quyền ghi thư mục) hay xong rất nhanh: tin lỗi / xong tới luồng chính TRƯỚC lời đáp của `startMp3` / `startM4b` / `startAudiobook`. `onEvent` đặt `Failed` / `Done`, rồi `start` đè lại thành `Running` của lượt đã kết thúc - màn kẹt ở "Đang xuất" mãi (không còn tin nào tới), hàng menu nói "Đang xuất". Nay chỉ đặt `Running` khi pha vẫn là `Starting` (hay `Idle` vì bạn vừa vào lại màn) và lượt chưa nằm trong `ended`. | `ExportStateTest`: `a run that ends before the start returns keeps its result` (đỏ trước sửa); `coming back while the core is still starting the run shows it running` (giữ hành vi cũ khi vào lại màn) |
| 2 | `ui/devices/CompanionRepo.kt` `refresh` | Một lượt hỏi máy phát khác hỏng (mạng chập chờn) đặt "Chưa nối được, bạn thử lại"; các lượt sau thành công vẫn chép lại `problem` cũ nên câu lỗi treo mãi trên thanh / tấm máy khác cho tới khi bạn bấm một lệnh. Nay lượt hỏi thành công xoá đúng câu ấy; câu báo lệnh bị máy kia từ chối vẫn giữ. | `ui/devices/CompanionRepoTest.kt` (mới, JVM thuần): `a dropped poll stops saying it once the next poll gets through` (đỏ trước sửa), `a refused command is still reported after the next poll` |

## Chắc chắn nhưng chưa sửa (môi trường không chạy được Robolectric)

| Chỗ | Kịch bản | Mức |
|---|---|---|
| `ui/NativeActivity.kt:83-84` | `app.exportLinks` (mới) và `app.deviceLinks` giữ lambda bắt `this` của Activity; không có `onDestroy` gỡ ra. Bạn bấm Back thoát app trong lúc sách vẫn phát nền: Application giữ Activity đã huỷ (cả cây Compose) tới lần mở app sau. Sửa: trong `onDestroy`, `if (app.exportLinks === exportLinks) app.exportLinks = ExportLinks()` (tương tự `deviceLinks`). Cần test Robolectric (`ActivityScenario` -> destroy -> so tham chiếu) nên để lại. | trung bình (rò bộ nhớ khi phát nền, đúng lúc ngân sách RAM 50 MB áp) |

## Không chắc - ghi lại, không sửa

| Chỗ | Kịch bản | Mức |
|---|---|---|
| `ui/data/UndoDelete.kt:38`, `ui/data/Library.kt` `delete` | Khác bản web: WebView dời sách vào thùng rác NGAY (`Store.holdBook`, bền qua tắt app), native chỉ ẩn trong bộ nhớ 28 giây rồi mới xoá đĩa. Xoá rồi vuốt app khỏi danh sách gần đây (tiến trình chết) trong 28 giây: sách quay lại ở lần mở sau. An toàn dữ liệu nhưng hai nền làm khác nhau. | trung bình (hành vi khác web) |
| `ui/data/Library.kt:55` + `ui/data/PlayerRepo.kt:280` (`reconcile`, gọi ở `ui/shell/Shell.kt:154`) | Đọc thư viện lỗi (`readAll` ném) thì `refresh` công bố `Ready(emptyList())`; `reconcile` thấy cuốn đang phát không có trong danh sách và gọi `bookRemoved` -> `Playback.closeBook` dừng hẳn và xoá hàng phát. Một lần đọc đĩa hỏng làm mất cuốn đang nghe. Cũng thế nếu `playerState.bookId` đổi sang cuốn vừa nhập trước khi lượt `refresh` sau nhập xong (cần đo thứ tự thật). | trung bình |
| `ui/export/ExportRepo.kt:110-112` | `callbackFlow` mặc định đệm 64 tin, `trySend` bỏ tin khi đầy. Tin tiến độ dày + luồng chính bận lâu thì có thể rơi cả tin cuối (xong / lỗi) -> màn kẹt "Đang xuất". Nên dùng `Channel.UNLIMITED` (hay `buffer(UNLIMITED)`) hoặc gộp tin tiến độ, giữ tin cuối. | thấp |
| `ui/export/ExportState.kt:229-231` + `ui/NativeActivity.kt:182` | Kết quả bộ chọn thư mục / hộp tạo file nằm ở biến của Activity. Activity bị huỷ trong lúc hộp hệ thống mở (thiếu RAM, "Không giữ hoạt động"): Activity mới nhận kết quả với `pickFolderResult == null`, `suspendCancellableCoroutine` không bao giờ resume - coroutine treo trong `uiScope`, màn ở "Starting" tới khi vào lại (open() đưa về Idle); thư mục / file bạn vừa chọn bị bỏ, file M4B rỗng vừa tạo không bị dọn. | thấp |
| `ui/export/ExportState.kt:253` | Sách chỉ có chữ: `Started.chapters` null, nên dòng đầu lấy `book.chaptersAvailable` rồi `chaptersTotal`; nếu cả hai 0 thì "Chương 1/0 · 0%". `ui.plan?.chapters` là số đúng. | thấp |
| `ui/export/ExportState.kt:89` | `hint(bookId)` tạo một `stateIn(Eagerly)` sống mãi cho mỗi cuốn từng mở menu; không gỡ. Giới hạn theo số sách, nhỏ. | thấp |
| `ui/music/MusicState.kt:75,125` | Đang thêm nhạc từ bảng của cuốn A, mở bảng cuốn B: `open` dựng `BookMusicUi` mới nên `importing=false` - bấm "Thêm nhạc của bạn" lần nữa chạy lượt thứ hai song song; lượt A xong đặt câu báo của A vào bảng của B. | thấp |
| `AbookApplication.kt:89` + `MusicStore.kt:180` | Hai đường thêm nhạc độc lập (`app.voice` ở Cài đặt > Nhạc của tôi, `app.music` ở bảng Nhạc nền, mỗi bên một `VoiceRepo` và cờ `importing` riêng). Chạy hai lượt cùng lúc: `importStream` của lượt sau xoá mọi file tạm `TEMPORARY*` - kể cả file đang ghi dở của lượt trước -> lượt trước hỏng giữa chừng. Thêm nhạc ở bảng xong thì danh sách Nhạc của tôi (VoiceState) cũng chưa đọc lại. | thấp |
| `ui/devices/CompanionRepo.kt:82,110` | Khác web (`android/RemotePlayers.tsx`): câu lệnh bị từ chối không có message là "Chưa làm được lệnh" (web "không làm được lệnh này"); "sleep" không cập nhật lạc quan hẹn giờ của máy kia (web có `remoteSleepAfter`); "skip" kẹp ở thời lượng (web chỉ kẹp ở 0). | thấp (đồng nhất chữ / hành vi) |

## Đã xem, không thấy lỗi

`UndoDelete` (hạn chót từng cuốn, nhận hạn trước I/O, Back chỉ khép thanh), `PlayerRepo.loadGeneration` (mọi lượt nạp dở bị bỏ khi xoá),
`Playback.closeBook`, `ExportStart` (dời nguyên logic của `LibraryPlugin`, giữ dọn file rỗng khi lỗi), `ExportLive.listen` (gỡ được, tin tới
sau khi bảng trạng thái đổi), `MusicRepo` / `LocalStudio.bookMusic|setBookMusic|musicAlternatives` (cùng khoá `lock`), `MusicJson`,
`RemoteBookSheet`, phần chữ / bo góc của `ui/voice` và `SettingsVoice`.

## Cách đã kiểm

Phiên cloud không tới được Google Maven (`dl.google.com` bị proxy chặn 403, `maven.google.com` chuyển hướng về đó), nên không dựng được
`:app` (AGP, androidx, media3 đều chỉ có ở Google Maven) và không chạy được `testDebugUnitTest` / `assembleDebug -PnativeUi` / Roborazzi.
Thay vào đó: một dự án Gradle Kotlin/JVM tạm (ngoài repo) biên dịch NGUYÊN VĂN các file `ExportState.kt`, `ExportModel.kt`, `ExportSource.kt`,
`CompanionRepo.kt`, `ListenModel.kt`, `ListenLogic.kt`, `Format.kt`, `Settings.kt`, `VoiceModel.kt` cùng `ExportStateTest.kt`,
`FakeExportSource.kt`, `FakeCompanionCore.kt`, `CompanionRepoTest.kt` (coroutines + org.json từ Maven Central; `@Immutable` / `@Stable`,
`Context`, `SystemClock`, `PhoneCast` / `RemotePlayers` / `StudioAlerts`, `PlayerState` là stub). Trước sửa: 32 test, 2 hỏng (đúng hai
test mới); sau sửa: 33 test, 0 hỏng, 0 lỗi. Cần chạy lại `./gradlew :app:testDebugUnitTest` và `:app:assembleDebug -PnativeUi` trên máy
có Google Maven trước khi gộp.
