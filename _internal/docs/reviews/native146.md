# Soát native146: mã Kotlin native gộp 26-10

Phạm vi: `git diff 3a414894..07e84542 -- _internal/mobile/android/app/src/main` (xoá sách có Hoàn tác, `Playback.closeBook`, máy phát khác,
màn Xuất, nhạc nền, cài đặt giọng). Soát lỗi đúng / sai, không soát văn phong. Đường dẫn dưới đây tính từ
`_internal/mobile/android/app/src/main/java/vn/abook/player/`; số dòng theo nhánh `dev/cloud-review146`.

## Đã sửa (test đỏ trước, xanh sau)

| # | Chỗ | Kịch bản | Test |
|---|---|---|---|
| 1 | `ui/export/ExportState.kt` `start` | Việc nền hỏng ngay (vd. mất quyền ghi thư mục) hay xong rất nhanh: tin lỗi / xong tới luồng chính TRƯỚC lời đáp của `startMp3` / `startM4b` / `startAudiobook`. `onEvent` đặt `Failed` / `Done`, rồi `start` đè lại thành `Running` của lượt đã kết thúc - màn kẹt ở "Đang xuất" mãi (không còn tin nào tới), hàng menu nói "Đang xuất". Nay chỉ đặt `Running` khi pha vẫn là `Starting` (hay `Idle` vì bạn vừa vào lại màn) và lượt chưa nằm trong `ended`. | `ExportStateTest`: `a run that ends before the start returns keeps its result` (đỏ trước sửa); `coming back while the core is still starting the run shows it running` (giữ hành vi cũ khi vào lại màn) |
| 2 | `ui/devices/CompanionRepo.kt` `refresh` | Một lượt hỏi máy phát khác hỏng (mạng chập chờn) đặt "Chưa nối được, bạn thử lại"; các lượt sau thành công vẫn chép lại `problem` cũ nên câu lỗi treo mãi trên thanh / tấm máy khác cho tới khi bạn bấm một lệnh. Nay lượt hỏi thành công xoá đúng câu ấy; câu báo lệnh bị máy kia từ chối vẫn giữ. | `ui/devices/CompanionRepoTest.kt` (mới, JVM thuần): `a dropped poll stops saying it once the next poll gets through` (đỏ trước sửa), `a refused command is still reported after the next poll` |

| 3 | `ui/NativeActivity.kt` `onDestroy` | `app.exportLinks` / `app.deviceLinks` giữ lambda bắt `this` của Activity: Back thoát app lúc sách phát nền thì Application giữ cả cây Compose đã huỷ. Nhánh `dev/native1` đã có `onDestroy` gỡ ra; thêm test giữ cho khỏi mất. | `NativeActivityLinksTest`: `a destroyed activity is not kept by the application` (bỏ hai dòng gỡ trong `onDestroy` thì đỏ) |
| 4 | `ui/data/Listeners.kt` (mới) dùng ở `ExportRepo.events`, `DevicesRepo.downloadEvents` / `shareChanges` | `callbackFlow` mặc định đệm 64 tin và `trySend` bỏ tin khi đầy: luồng chính bận lâu thì rơi cả tin cuối (xong / lỗi) -> màn kẹt "Đang xuất" / "Đang tải". Cả ba luồng nay đi qua `listenerFlow` (hàng đợi không giới hạn). | `ListenerFlowTest`: `no news is lost while the collector is busy` (500 tin, đỏ trước sửa: chỉ tới 65) |
| 5 | `ui/PendingAnswers.kt` (mới), `ui/NativeActivity.kt`, `AbookApplication.answers` | Kết quả bộ chọn thư mục / hộp tạo file / xin quyền nằm ở biến của Activity: Activity bị huỷ lúc hộp hệ thống còn mở thì Activity mới nhận kết quả mà không biết ai hỏi - màn Xuất treo ở "Starting", thư mục / file vừa chọn bị bỏ. Nơi đang đợi nay nằm ở Application (sống qua lần dựng lại); đủ bốn hộp (thư mục, tạo file, "Thiết bị ở gần", thông báo). `StudioActivity` (WebView) không đổi được: `ValueCallback` của nó gắn với WebView đã chết cùng Activity. | `NativeActivityLinksTest`: `a folder picked after the activity was rebuilt still reaches who asked`, `a file made after ...` (đỏ trước sửa; dựng lại bằng `ActivityController.recreate`) |
| 6 | `ui/export/ExportState.kt` `start` | Sách chỉ có chữ: `Started.chapters` null, `chaptersAvailable` / `chaptersTotal` đều 0 thì dòng đầu "Chương 1/0 · 0%". Nay lấy số chương của bản ước (`plan.chapters`) trước. | `ExportStateTest`: `a text only book says its chapters from the plan, not from a count it does not have` (đỏ trước sửa) |
| 7 | `ui/export/ExportState.kt` `hint` | `stateIn(Eagerly)` cho mỗi cuốn từng mở menu: một coroutine sống mãi không gỡ. Nay dòng phụ là `MutableStateFlow` nối lại ở `edit` / `setProgress`, không giữ việc nào chạy. | `ExportStateTest`: `asking for a hint starts nothing that lives on` (đỏ trước sửa), `the hint follows the phase and the progress ...` |
| 8 | `ui/data/UndoDelete.kt`, `ui/data/Library.kt`, `ui/components/UndoBar.kt`, `ui/devices/*` | Xoá khỏi điện thoại khác bản web: native chỉ ẩn trong bộ nhớ 28 giây rồi mới xoá đĩa (tiến trình chết trong lúc ấy thì sách quay lại), chữ / lỗi / hoàn tác khác web. Nay đúng như `shared/trashUndo.ts`: dời vào chỗ chờ NGAY (`BookActions.delete` = `Store.holdBook`, bền qua tắt app; lần mở sau `sweepTrash(everything)` dọn hẳn như `LibraryPlugin`), thanh "Đã xoá “X” khỏi điện thoại" / "Đã xoá phần đã tải của “X”" / "Đã bỏ N cuốn" + "Hoàn tác" 28 giây mỗi cuốn, Hoàn tác trả cũ trước (`Store.undoBook`) rồi "Đã khôi phục “X”", không trả được thì "Chưa hoàn tác được - <lý do>" và cuốn vẫn mời Hoàn tác tới hết hạn; cuốn đang tải bị lõi từ chối với câu của lõi. `BookActions.deleteAfterUndo` bỏ (hết người gọi). | `UndoDeleteTest` (mới, 9 test), `LibraryMembershipTest`: `deletingMovesTheBookToTheWaitingPlaceAtOnce...` (đỏ trước sửa: file còn nguyên 28 giây), `aBookStillWaitingWhenTheProcessDiedIsGoneForGoodNextTime`; `GapLogicTest` / `GapReviewTest` / `GapSurfacesTest` viết lại theo ngữ nghĩa mới |
| 9 | `ui/devices/CompanionRepo.kt` | Đồng nhất với `RemotePlayers.tsx`: câu lệnh bị từ chối không lời nay nói "không làm được lệnh này"; "sleep" cập nhật lạc quan hẹn giờ của máy kia (`remoteSleepAfter`). Cái còn lại: "skip" kẹp ở thời lượng (web chỉ kẹp ở 0 nhưng vị trí hiện luôn bị cắt ở thời lượng) - cùng kết quả nhìn thấy, giữ nguyên. | `CompanionRepoTest`: `a refused command without words says what the web says`, `a sleep timer shows on the other player before it answers` (đỏ trước sửa) |
| 10 | `ui/music/MusicState.kt`, `ui/voice/MineImports.kt` | Hai chỗ "Không chắc" về thêm nhạc (lượt chạy song song khi mở bảng cuốn khác; hai đường thêm nhạc độc lập với cờ riêng) đã được sửa ở nhánh `dev/native1` bằng một lượt chung `MineImports`; có test sẵn (`MusicStateTest`: `a book opened while another book adds music shares that turn but not its notice`, `adding from the book panel ... blocks a second turn there`). | đã có |

## Không sửa - ghi lại

| Chỗ | Vì sao chưa sửa | Mức |
|---|---|---|
| `ui/data/Library.kt` `refresh` + `ui/data/PlayerRepo.kt` `reconcile` (gọi ở `ui/shell/Shell.kt`) | Nửa "đọc thư viện lỗi thì công bố danh sách rỗng" đã được chặn ở `refresh` (đã có danh sách thì giữ nguyên); còn lại chỉ là lần đọc ĐẦU hỏng. `readAll` bắt lỗi từng cuốn và `Store.bookIds()` dùng `listFiles()?` nên không dựng được test đỏ (không có đường làm nó ném). Nửa "bookId đổi sang cuốn vừa nhập trước khi `refresh` xong" cũng chưa có kịch bản tái hiện (nhập xong thì `ImportQueue` đã gọi `refresh` trước khi cuốn mở được). Không sửa mò. | thấp |

## Đã xem, không thấy lỗi

`UndoDelete` bản cũ (hạn chót từng cuốn, Back chỉ khép thanh - hai điều này giữ ở bản mới), `PlayerRepo.loadGeneration` (mọi lượt nạp dở bị bỏ khi xoá),
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

Lượt sửa r146b (`dev/r146b`, máy có Google Maven): `:app:testDebugUnitTest -Proborazzi.test.record=true` 2544 test, 0 hỏng, 0 lỗi; `scripts/ui_parity.py` + `tests/test_ui_parity.py` + `tests/test_native_tokens.py` xanh. Ảnh Roborazzi đổi: `gap1b_shell_undo_*` (thanh có tên cuốn) và `gap1b_shell_error_*` (nay là lỗi Hoàn tác, không còn lỗi xoá).
