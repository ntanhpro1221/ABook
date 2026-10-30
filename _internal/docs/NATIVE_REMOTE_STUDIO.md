# Studio từ xa viết lại bằng Kotlin/Compose — thiết kế (chưa có mã)

> Đặc tả thiết kế, không phải mã. Viết 30-10 trên nhánh `dev/native-studio-spec` (từ `dev/int149`). Cùng giọng với `NATIVE_PHONE_UI.md` (viết tắt **NPU**) và theo `DESIGN.md` (viết tắt **DS**).
>
> **Vì sao có tài liệu này.** Chủ sách: điện thoại viết lại Kotlin/Compose native, cấm WebView, cấm port lười. Bản `-PnativeUi` hiện vẫn mở "Studio từ xa" bằng `StudioActivity.kt` — một `WebView` hiển thị trang React của máy tính qua cổng `remote_studio.py`. Chừng nào nó còn, pha **P4** của NPU §6 (gỡ Capacitor/WebView) không làm được, và cũng không đạt ngân sách NPU §1 (một WebView thêm hàng chục MB RSS và khởi động Chromium).
>
> **Phạm vi.** Chỉ phía điện thoại. Không đụng `_internal/abook/` (máy tính). Chỗ máy tính cần thêm JSON thì liệt ở §9 để phiên khác làm.
> **Không có đường tương thích cũ**: app chưa ai dùng; `StudioActivity` bị xoá hẳn, không giữ làm đường lui.
> Chỗ nào tôi chưa chắc thì ghi **[chưa chắc]**.

## 0. Tóm tắt

- Thêm gói `vn.abook.player.ui.studio` (≈ 45 file mới, ~12.700 dòng mã + ~3.900 dòng test, §11) và một client `StudioApi.kt` đặt trên **`SyncLink.request` + `StudioLink.link` sẵn có** (đã Bearer + ghim vân tay). Không thêm HTTP client thứ hai.
- 9 màn: **Studio** (danh sách dự án), **Dự án** (tab Chương · Việc cần duyệt · Cần nghe lại · Nhân vật · Nhạc nền), **Kịch bản**, **Duyệt trước khi thu**, **Xuất**, **Sách mới**, **Cách đọc tên**, **Bìa** (dùng lại màn cắt/tìm bìa của sửa sách), **Nhật ký**. Phần còn lại là sheet.
- Máy tính phải thêm JSON ở vài chỗ nhỏ (§9); không chỗ nào trả HTML mà điện thoại cần.
- `StudioActivity` đã bị xoá ở S5; xong thì `activity_main.xml`, `MainActivity` + các Plugin (nếu P4 làm cùng), Capacitor, thư mục `assets/public` đều gỡ được (§10).
- Đi theo pha **S1–S5** (§11); S1–S4 phát hành được riêng, bản `-PnativeUi` giữ lối "Mở trang Studio" (WebView) tới hết S4. **S5 đã xoá `StudioActivity` và `LibraryPlugin.openStudio`** (hàm này tham chiếu `StudioActivity` nên không còn biên dịch được), nên bản WebView (không cờ `-PnativeUi`) **không còn Studio từ S5**; vì vậy S5 **được gộp cùng P4**, không phát hành trước nó.

---

## 1. Kiểm kê: trang Studio từ xa đang làm được gì

### 1.1 Đường truyền và quyền (đọc từ mã)

| Điều | Hiện trạng (nguồn) | Hệ quả cho native |
|---|---|---|
| Cổng | `abook/webui/sync.py` — TLS-only, chứng chỉ tự ký. `remote_studio.py` đứng sau, chuyển tiếp `/api/*` và `/media/*` sang máy chủ giao diện cục bộ (127.0.0.1) kèm header `X-Abook-Remote`. | Dùng đúng cổng này; không cần trang HTML nào của nó. |
| Xác thực | `sync._device(cookie=True)`: **`Authorization: Bearer <mã thiết bị>` được ưu tiên**; cookie `abook_device` (HttpOnly, SameSite=Strict, Secure) chỉ cho trình duyệt. | Native dùng Bearer, **không cần cookie**. `StudioActivity` đặt cookie vào `CookieManager` chỉ vì WebView. |
| Ghim | Điện thoại ghim vân tay chứng chỉ (`Pin.kt`, `SyncLink.exchange`). | `StudioApi` đi qua `SyncLink.request` nên thừa hưởng. |
| Quyền | Cần **cả** công tắc toàn cục `remoteStudio` (máy tính, tắt mặc định) **và** quyền `studio` của thiết bị; đọc lại mỗi yêu cầu (`sync._studio()`). Thiếu một trong hai → **403 `{"listenOnly": true}`** trên mọi đường ngoài `LISTEN_ROUTES`. | Mã `StudioError.ListenOnly`; mọi màn Studio dùng chung một trạng thái "Máy tính chưa cho bạn sửa" (§3.4). Web làm y vậy (`polling.ts isListenOnly`). |
| Danh sách trắng | `remote_studio.ALLOWED` (1.2). Ngoài danh sách (chọn file `/api/dialog/*`, mở Explorer, xoá dự án, khôi phục bản lưu, đổi thư mục thư viện, ghép/gỡ thiết bị) → bị chặn. | Màn native **không có** các nút này. Chọn file dùng bộ chọn của Android rồi tải lên. |
| POST | Chỉ nhận JSON (`read_body`). Trần thân yêu cầu `MAX_FORWARD_BODY = 24 MiB`, `FORWARD_SECONDS = 120`. | Tải nguồn lên bằng JSON base64 — xem 1.5. |
| Danh sách nhẹ | `GET /sync/v1/studio` (Bearer, cần quyền studio) trả JSON gọn danh sách dự án; `StudioAlerts.kt` đang dùng cho thông báo. | Dùng làm nguồn cho huy hiệu và danh sách đầu của màn **Studio** (không phải kéo cả `/api/library`). |

### 1.2 Mọi đường có thể gọi (`ALLOWED`) gom theo chức năng

Cột "Bề mặt web" là component trong `_internal/ui/src/studio/` đang dùng đường đó. Dạng JSON từng đường nằm ở kiểu TS cạnh component (`data.ts`, `WorkInbox.tsx WorkItem`...) — **bản Kotlin phải kiểm bằng cùng fixture hợp đồng** như `LocalStudio.kt` đang làm với `tests/fixtures/book_edits/contract` (§12).

| Chức năng | Đường | R/W | Bề mặt web | Nhịp hỏi (web) |
|---|---|---|---|---|
| Danh sách dự án | `GET /api/library` → `{root, rootMissing?, books[]}` | R | `ProjectsScreen` | 5 s khi có sách chạy, 15 s rảnh (`IDLE_MS`), 20 s khi không ở Studio |
| Trang một dự án | `GET /api/books/<id>` → `{book, chapters[]}` | R | `ProjectScreen` | 3 s khi chạy (`LIVE_MS·1,5`), 15 s rảnh; 404 dừng hẳn; lỗi khác lùi gấp đôi tới 120 s (`pollDelay`) |
| Điều khiển chạy | `POST /api/books/<id>/start` · `/stop` · `/dequeue` · `/pause` | W | `Actions`, `primaryKind` | — (xong thì làm mới `book`) |
| Đổi tên/tác giả sách, tên chương | `PUT .../title` · `.../author` · `.../chapters/<n>/title` | W | `ProjectMenu`, `ProjectInfo` | — |
| Làm lại chương | `POST .../chapters/<n>/retake` → `{lines}` | W | `ProjectScreen` | — |
| Tạo sách | `POST /api/sources/upload` · `/api/sources/split` · `/api/scan` · `/api/first-person` · `GET /api/analysis-models` · `GET/POST /api/book-templates` · `POST /api/books` | R/W | `NewProjectScreen` (2.049 dòng), `upload.ts` | `scan` một lần |
| Giọng | `GET /api/voices` (**mảng**) · `GET .../voices` · `POST .../voice` · `POST .../voice/preview` · `GET /media/voices/<id>` · `GET /media/books/<id>/samples/<n>` · `GET /media/books/<id>/reading-previews/<hash>.wav` | R/W | `VoicePicker`, `CastEdits` | 1 s khi mẫu giọng `downloading` |
| Nhân vật | `GET .../cast` · `POST .../characters/rename` · `POST .../characters/merge` · `GET .../casting`, `.../casting/<n>`, `.../casting/stamp` | R/W | tab Nhân vật | `cast` 20 s khi chạy; `stamp` 6 s (`STAMP_MS`) |
| Việc cần duyệt | `GET .../work` · `GET .../work/examples` · `POST .../speaker` · `POST .../line` · `POST .../narrator-section` · `POST .../voice` · `POST .../pronunciation` · `GET/POST .../shared-readings` | R/W | `WorkInbox` (1.341 dòng), `workText`, `decisions` | như `book`, chỉ khi sách thật sự chạy (`useProducingRefetch`) |
| Cần nghe lại | `GET/POST .../review` (+ `GET /media/books/<id>/chapters/<n>`) | R/W | `ReviewQueue` | như trên |
| Chờ áp dụng | `GET .../pending-changes` · `POST .../pending-changes/withdraw` · `GET .../redo` | R/W | `ApplyChanges` | — |
| Thay đổi từ máy khác | `GET .../edits-inbox` · `POST .../edits-inbox/apply` · `/skip` | R/W | `PhoneEdits` | 15 s |
| Duyệt trước khi thu | `GET/PUT .../precast` | R/W | `PrecastReview` | 15 s |
| Người kể xưng "tôi" | `GET/PUT .../narrator-mode` | R/W | `TellerModeSwitch` | 15 s khi chạy |
| Kịch bản | `GET .../chapters/<n>/script` · `POST .../line` | R/W | `ScriptTab` (1.856 dòng) | — |
| Cách đọc tên | `GET .../pronunciations` · `GET .../pronunciations/reach` · `POST .../pronunciation` · `POST .../pronunciation/preview` · `POST .../pronunciation/check` · `GET/PUT .../readings` · `GET/POST /api/readings` · `PUT .../skip` · `GET .../suggestions` | R/W | `NameReadings` | 1 s khi tính mốc từ (`WordTimings`) |
| Nhạc nền | `GET/PUT .../music` · `POST .../music/rebuild` · `POST .../music/download/cancel` · `POST .../music/moods` · `GET /api/music/moods-model` · `GET .../music/scenes/<id>/alternatives` · `GET .../music/chapters/<n>` · `GET .../music/files/<track>` · `GET /api/music/track` · `GET .../music/playlist` · `GET /api/music/playlists` | R/W | `MusicTab` | 2 s khi `downloading`; 3 s khi `moods.running` |
| Xuất | `POST/GET .../bookfile-job` (+`/cancel`) · `.../m4b-job` (+`/cancel`) · `.../mp3-job` (+`/cancel`) · `GET .../music-export` · `POST .../music-export/cancel` · `GET /api/export-jobs` · `GET .../export-size` · `GET .../export-history` · `GET .../export-music` · `GET /api/ffmpeg` · `POST .../bookfile` | R/W | `ExportBook`, `ExportBookFileJob` | 5 s (`export-jobs`), 1 s đang chạy, 800 ms khi `downloading` |
| Bìa | `GET .../cover/search` · `PUT .../cover` (`{image}` data URL hoặc `{url}`) · `DELETE .../cover` · `GET /media/books/<id>/cover` | R/W | `CoverEditor` | — |
| Nhật ký | `GET .../activity[?technical=1]` (**mảng**) | R | "Thêm → Nhật ký" | 5 s khi chạy |
| Tiếp tục dự án | `GET .../continuation` | R | `ProjectScreen` | — |
| Thông tin máy | `GET /api/app` (có `listenOnly`, `studio.installed/outdated/damaged`) · `GET /api/preferences` | R | `useAppInfo`, `useStudioMissing` | một lần + khi gặp 403 listenOnly |
| Nghe (đã có native) | `GET /api/listen/...`, `/media/...` | R/W | phần **Nghe** | — |

Không có SSE/WebSocket: **mọi thứ là hỏi định kỳ**. Hai việc dài: `POST .../pronunciation/preview` và `.../voice/preview` giữ kết nối tới ~120 s (card đồ hoạ của máy tính nạp + đọc), trả `wav` qua `/media/.../reading-previews/<hash>.wav`.

### 1.3 Kiểu việc cần duyệt (`WorkKind`)

16 loại trong `WorkInbox.tsx`/`decisions.ts`: `speaker`, `turn`, `gender`, `vocative`, `alias`, `bracket`, `shared-voice`, `pronunciation`, `unnamed`, `audio`, `narrator`, `voice-wish`, `snap`, `teller-voice`, `teller-thought`, `refused`. Mỗi `WorkItem` mang `key, title, problem, affected, doubt, score, options, current, examples[]`; tuỳ loại thêm `surface`, `requested`, `redoOnly`, `lines[]` (`stableId` + `textSha256`), `allLines`, `scopeLabels`, `choices[{label,value,name?}]`. Quyết định ghi bằng các POST ở bảng trên; thân yêu cầu do `decisions.ts` dựng. **Bản Kotlin port nguyên văn hàm dựng thân này**, không tự nghĩ lại: `textSha256` là rào chống áp nhầm câu đã đổi.

### 1.4 Hành vi riêng của `StudioActivity.kt`

| Hành vi | Chi tiết | Native |
|---|---|---|
| Chọn máy + đường trang | Intent extras `computer` (khoá máy) và `path` (`/#/studio[/<id>]`, lọc bởi `StudioLink.safePath`). | Thay bằng `Destination.Studio(computer, book, tab)` trong `Nav.kt` (§4.3). |
| Ghim vân tay | WebView so vân tay với `Peers.Link`; mã thiết bị đặt thành cookie HttpOnly cho đúng máy ấy. | Không cần: `SyncLink` ghim sẵn; không còn cookie. |
| Đổi địa chỉ máy | `StudioLink.rebase` đổi nền URL khi máy tính đổi IP; `StudioLink.Watch` hỏi lại khi máy không trả lời ("… không trả lời - đang chờ nối lại"). | Giữ `Watch`/`silentLine`/`called` (đã có, có test). `StudioApi` lấy `Peers.Link` mới mỗi lần gọi nên đổi IP tự khỏi. |
| Bản lệch | `StudioLink.mismatched(theirs, ours)`. | Dải "Cập nhật máy tính" trong màn Studio. |
| Chọn file | `WebChromeClient.onShowFileChooser` cho nguồn (txt/epub/docx/pdf) và ảnh bìa. | `OpenMultipleDocuments` ở `NativeActivity` + `PendingAnswers` (đã dùng cho nhập sách), xem §6.12. |
| Back | `onBackPressed`: lùi lịch sử WebView rồi thoát. | `BackStack`/`NavState` của NPU §2 (Back dự đoán, `ScreenGeometry` đối xứng). |
| Thông báo | `StudioAlerts.kt:186` tạo `Intent(StudioActivity)` mở đúng cuốn, đúng tab. | Đổi sang `Destination.Studio` qua `NativeActivity` (§4.3). |
| Chỉ nghe | 403 `listenOnly` → trang web thay bằng "Chỉ nghe". | §3.4. |

### 1.5 Lệch đã thấy (báo, chưa sửa)

1. **`SyncLink.responseText` chỉ nhận `JSONObject`** (`SyncLink.kt:276`). Ba đường trả **mảng**: `GET /api/voices`, `GET .../activity`, `GET /api/listen/library`. Đường cuối đang được `ui/data/Production.kt` (`ProductionSource.read()`) dùng, bọc trong `runCatching` → rất có thể thư viện native **không bao giờ thấy trạng thái "đang làm"** của máy tính. **[chưa kiểm trên máy thật]**. Sửa ở §3.1, nên làm trước S1 vì cùng một chỗ.
2. **Tải nguồn lên**: trang web nói tới 40 MB mỗi file (`MAX_SOURCE_UPLOAD = 40 MiB`, `actions.upload_source`) nhưng thân JSON base64 qua cổng bị chặn ở 24 MiB → thực tế ~17 MiB file gốc. Epub/pdf lớn sẽ lỗi giữa chừng. Native phải kiểm trước và nói thẳng (§6.12); §9 đề xuất sửa phía máy tính.
3. Đường cổng thật là `_internal/abook/webui/remote_studio.py`, đặc tả giao việc ghi `_internal/webui/` — tài liệu này dùng đường thật.

---

## 2. Nguyên tắc thiết kế (rút từ NPU §1–§4 và DS §4–§6)

1. **Điện thoại là chỗ ĐIỀU KHIỂN và DUYỆT, không phải chỗ làm việc nặng.** Trang web là bảng điều khiển của máy tính (nhiều cột, bảng, chuột). Điện thoại làm lại theo ba động tác: *xem tiến độ*, *quyết từng việc bằng một ngón*, *nghe thử*. Không bê bảng nhiều cột sang; mỗi việc là một thẻ, mỗi tab là một danh sách một cột.
2. **Một nút chính mỗi màn** (DS §4): trang Dự án có đúng một nút theo trạng thái (Bắt đầu / Tạm dừng / Tiếp tục / Dừng), phần còn lại là hàng chữ hay mục trong "Thêm".
3. **Chữ ngắn, gọi "bạn"**: nhãn 1–4 chữ ("Bắt đầu", "Tạm dừng", "Việc cần duyệt", "Nghe thử", "Đổi giọng"); câu dài chỉ là chú thích `Caption`. Không có chữ kỹ thuật (`segment`, `stableId`, `LUFS`) trên mặt chính; chúng nằm sau "Chi tiết".
4. **Cài đặt tối đa 2 cấp**: màn → sheet. Không có cây ba tầng. Mọi mục "hiếm dùng" nằm trong "Thêm" (sheet) chứ không phải thanh công cụ.
5. **Chuyển động cho mọi mở/đóng** (NPU §4): màn đẩy vào bằng `Motion.PushIn`, tab bằng `Motion.TabSlide`, sheet bằng `SheetHost`/`SheetLayer` (`Motion.SheetIn/Out`), mục mở rộng bằng `Reveal`/`Fold` (`Motion.Expand/Collapse`), thẻ việc biến mất khi đã quyết bằng trượt-và-gập hàng, không bật/tắt cứng. Thẻ việc dùng *chuyển có hướng* (đã quyết trượt sang trái, thẻ kế trượt vào), không chỉ mờ.
6. **Số tự đổi thì đổi tại chỗ** (`ClockLabel`, chữ số bảng): phần trăm tiến độ, "chương 12/48", "còn 2:14", "x/y câu", số việc cần duyệt, số lượt chờ trong hàng. Mọi hàm định dạng số mới phải thêm vào `formatters` của `TickingValuePolicyTest` (đã quy ước trong file ấy).
7. **Cái gì viết rồi thì hoàn tác được** (DS Hoàn tác; `UndoBar`): quyết một việc → thân POST *chưa gửi* 15 giây (đúng như web: ghi theo `requestedAt` + hoàn tác 15 s); bấm "Hoàn tác" thì bỏ, hết 15 s thì gửi. Việc không hoàn tác được (làm lại chương, dừng, đổi giọng đang chạy) đi qua `ConfirmPage` + `DangerButton`.
8. **Mạng chập chờn là chuyện thường**: mọi màn giữ *bản cũ trên màn* kèm dải "đang chờ nối lại" (`StudioLink.silentLine`) thay vì trang lỗi; chỉ khi chưa từng có dữ liệu mới hiện `InlineProblem` + "Thử lại" (web làm vậy: `bookFailure` = `gone/stale/error`).
9. **Chạm ≥ 44 dp**, văn bản không cắt (`TextCutScanTest`), mép cuộn mờ (`ScrollFade`), mọi `Modifier` có `testTag` ổn định cho test.

---

## 3. Tầng truyền thông — dùng lại, chỉ thêm ba thứ nhỏ

### 3.1 Cái đã có và dùng nguyên

| Có sẵn | Việc | Dùng cho Studio |
|---|---|---|
| `SyncLink.request(method, path, body, root, token)` | HTTPS có ghim vân tay + `Authorization: Bearer`, JSON | Mọi lời gọi `/api/*` JSON. |
| `StudioLink.link(context, key)` → `Peers.Link` | Máy đã ghép + địa chỉ + vân tay + token đúng máy ấy | Chọn máy tính nào. |
| `StudioLink.computers(...)` / `Devices.studioComputers/studioTarget` / `DevicesSource.studio()` | Danh sách máy cho phép Studio | Màn **Studio** liệt kê máy. |
| `StudioLink.Watch`, `silentLine`, `called` | Theo dõi máy im lặng | Dải nối lại. |
| `SyncLink.bookFile(...)` | GET nhị phân có ghim (Range/If-Range) | Phần nền cho tải audio mẫu, bìa. |
| `PeerTransfer.openGet` (`JSON_BYTES = 16 MiB`) | GET có giới hạn cỡ | Trần JSON của Studio. |
| `StudioAlerts` + `StudioAlertWorker` + `GET /sync/v1/studio` | Thông báo "cần duyệt/đã xong" | Giữ nguyên, chỉ đổi đích bấm (§4.3). |
| `ui/voice/AndroidSamplePlayer.kt` | Phát mẫu giọng | Nghe thử giọng/cách đọc/câu cần nghe lại. |
| `ui/editbook/CoverSearchScreen.kt`, `CoverCrop.kt`, `EditBookRepo.EditSource` | Tìm/cắt bìa cho sách **trên điện thoại** | Dùng lại màn, đổi nguồn (6.13). |
| `ui/export/*` (`ExportSource`/`ExportRepo`/`ExportModel`/`ExportScreen`) | Xuất sách **trên điện thoại** | Khung mẫu cho Xuất từ xa (6.11); không dùng lại logic. |
| `ui/music/*`, `ui/voice/*` | Nhạc/giọng trên điện thoại | Bộ phận hiển thị chọn giọng/bài dùng lại được; dữ liệu khác nguồn. |
| `LocalStudio.kt` (809 dòng) | Cài đặt *trên điện thoại* của đúng hợp đồng `/api/books/<id>/...` | **Mẫu hợp đồng** và fixture kiểm; xem 12. Không gọi nó cho Studio từ xa. |

### 3.2 Ba bổ sung vào `SyncLink`/lớp mạng (nhỏ, có test)

| Bổ sung | Vì sao | Cỡ |
|---|---|---|
| **A. Nhận mảng JSON**: `SyncLink.requestJson(...)` trả `JsonValue` (hoặc `requestArray`) thay vì ép `JSONObject` trong `responseText`. | `/api/voices`, `.../activity`, `/api/listen/library` trả mảng (1.5). Đồng thời **sửa lỗi `ProductionSource`**. | ~30 dòng + 3 test. |
| **B. GET nhị phân có ghim ra file tạm**: tổng quát hoá `bookFile` thành `SyncLink.download(link, path, dest, limit)` (đường `/media/...` bất kỳ). | `MediaPlayer`/`ExoPlayer` của hệ thống **không** ghim vân tay → không phát thẳng URL được. Phát = tải vào `cacheDir/studio_clips/`, rồi `AndroidSamplePlayer`. Dọn khi đóng màn và khi app khởi động (trần 50 MB). | ~60 dòng + 2 test. |
| **C. Tải lên JSON base64 kiểu dòng chảy**: `SyncLink.uploadJson(link, path, build: (Writer)->Unit)` ghi thẳng ra `OutputStream` (chunked, không dựng cả chuỗi 24 MiB trong RAM) và bắt `HTTP 413`/ngắt kết nối thành `StudioError.TooBig`. | Nguồn sách tới ~17 MiB, bìa tới ~21 MiB (data URL). Dựng `String` + `JSONObject` cả cục là đỉnh RAM hàng chục MB, vi phạm NPU §1. | ~90 dòng + 3 test. |

**Không** thêm HTTP client mới, không `OkHttp`, không `HttpsURLConnection` ngoài `SyncLink`/`PeerTransfer` (đúng quy ước của NPU §2 và các lần sửa 0.4.x).

### 3.3 `StudioApi` (một file mới, `vn.abook.player.StudioApi`)

```
class StudioApi(context, computerKey) {
  suspend fun get(path): Json      // object hoặc mảng
  suspend fun send(method, path, body: JSONObject? = null): Json
  suspend fun download(path, dest): File   // B
  suspend fun upload(path, build): Json    // C
  // mọi hàm: Dispatchers.IO, huỷ được, ném StudioError
}
sealed class StudioError { Offline, ListenOnly, Gone /*404*/, Unauthorized /*401: thiết bị bị gỡ*/, TooBig, Busy /*409/423*/, Server(message, status) }
```

- Hàm *thuần* (không `Context`) dựng đường và đọc lỗi, để test JVM không cần Android: `StudioPaths` (dựng `/api/books/<id>/...`, kiểm `[A-Za-z0-9_-]+` giống `StudioLink.BOOK`), `StudioErrors.classify(status, body)` (đọc `{"listenOnly":true}`, `{"error":...}`, `{"detail":...}` — **[chưa chắc]** tên khoá lỗi chính xác; port từ `api.ts ApiError`).
- Lời lỗi tiếng Việt đi qua một hàm duy nhất `StudioText.failure(error)`: `Offline` → "Mất kết nối tới ABook."; `Gone` → "Sách có thể đã bị chuyển hoặc xoá." — **giữ y chữ** của `polling.ts failureText` để hai nền tảng đồng nhất (NPU quy tắc "một nguồn chữ").

### 3.4 Chỉ nghe (403 `listenOnly`)

Một nơi duy nhất (`StudioState.permission`): lần gọi đầu bị 403 `listenOnly` → trạng thái `ListenOnly`; **mọi** màn Studio hiện cùng một thẻ: tiêu đề "Máy tính chưa cho bạn sửa", dòng chú "Bật *Cho phép điều khiển sản xuất* trên {tên máy} rồi quay lại." và một nút duy nhất "Thử lại". Dừng mọi nhịp hỏi (như web: `pollDelay` trả `false` khi `isListenOnly`). Không có nút nào bị tắt xám rải rác: thấy quyền thì dùng, không thì cả Studio là một thẻ.

### 3.5 Hỏi định kỳ

Một lớp `StudioPoller` (thuần, test được bằng đồng hồ giả):

- Port nguyên `pollDelay` (cơ sở → 404 dừng; ListenOnly dừng; lỗi → gấp đôi tới 120 s) và các hằng `LIVE_MS = 2000`, `IDLE_MS = 15000`, 5000/20000, `STAMP_MS = 6000`.
- Chạy trong `repeatOnLifecycle(Lifecycle.State.STARTED)`: **không hỏi khi màn không hiển thị hay app ở nền** (web cũng dừng ở tab ẩn). Khi trở lại thì hỏi ngay một lần.
- Gộp: nhiều màn cùng hỏi `/api/books/<id>` thì chung một vòng (`StateFlow` theo khoá đường) — web có cache TanStack; native có `StudioCache` (LRU 8 mục, chỉ trong RAM, không ghi đĩa; dữ liệu truyện không rơi vào đĩa điện thoại ngoài việc người dùng chủ động tải).
- Khi sách không chạy thì chỉ hỏi 15 s/lần (hoặc không, tuỳ tab); **đây cũng là cách tiết kiệm pin và máy tính**: nhịp 2–3 s chỉ khi `running || starting`.

---

## 4. Điều hướng

### 4.1 Cây màn

```
Tab "Thiết bị" ─ Studio (danh sách dự án)       [Destination.Studio]
                    ├─ Sách mới                  [Destination.StudioNew]
                    └─ Dự án (5 tab)             [Destination.StudioProject(computer, book, tab)]
                          ├─ Chương · Việc cần duyệt · Cần nghe lại · Nhân vật · Nhạc nền  (tab = cùng màn, vuốt ngang)
                          └─ "Thêm" (sheet) → Duyệt trước khi thu · Kịch bản · Cách đọc tên · Xuất · Bìa · Nhật ký · Thông tin
```

Vào Studio từ đúng chỗ trang `OtherScreens.StudioScreen` đã có (`DisclosureRow` theo từng máy), nên **không thêm tab đáy mới**. Theo NPU "ngăn xếp chỉ sâu 3": Studio → Dự án → (Kịch bản | Xuất | Cách đọc tên | Bìa | Sách mới). Mọi thứ khác là sheet.

### 4.2 `Destination` thêm

```kotlin
data object Studio : Destination                                            // danh sách máy + dự án
data class StudioProject(val computer: String, val book: String, val tab: StudioTab = StudioTab.Chapters) : Destination
data class StudioScript(val computer: String, val book: String, val chapter: Int?) : Destination
data class StudioPrecast / StudioExport / StudioReadings / StudioNew(val computer: String, ...)
```
`Cover` dùng lại `Destination.CoverSearch`/`CropCover` nhưng với nguồn từ xa (6.13). Mỗi `Destination` là `@Immutable`, `Entry.key` ổn định để Compose giữ cuộn khi màn xuống dưới (`BackStack`, NPU §2).

### 4.3 Mở từ ngoài (thay `StudioActivity`)

- `NativeActivity.kt:229` hiện `openStudio = { computer, path -> open(Intent(StudioActivity)) }` → đổi thành `openStudio = { computer, book, tab -> nav.push(Destination.StudioProject(computer, book, tab)) }`.
- `StudioAlerts.kt:186` dựng `PendingIntent` tới `NativeActivity` với extras `studio_computer`, `studio_book`, `studio_tab` (đã có sẵn nơi `StudioLink.bookPath` → thay bằng `StudioTab` enum). `NativeActivity.onNewIntent` đọc rồi `nav.push`. **Mã thiết bị không bao giờ nằm trong Intent** (quy ước hiện có).
- `Devices.studioTarget(context, book, computer)` giữ để chọn máy giữ cuốn ấy; chỉ bỏ phần dựng `path` web.

### 4.4 Back

`BackStack` có Back dự đoán và `ScreenGeometry` đối xứng sẵn. Quy tắc riêng: hàng đợi 15 s hoàn tác **không bị huỷ** khi Back (người dùng quyết rồi thoát là chuyện thường) — thân chưa gửi được đưa cho `StudioOutbox` (một `WorkManager` job một lần, mạng bất kỳ, retry lùi) để vẫn gửi sau 15 s kể cả khi màn đã đóng; Hoàn tác chỉ hiện khi còn ở màn. **[chưa chắc]** có nên đưa ra `WorkManager` hay giữ trong `viewModelScope` của `NativeActivity`: giữ trong scope Activity đơn giản hơn, nhưng mất nếu hệ thống giết tiến trình trong 15 s; mất việc quyết 15 s là chấp nhận được (người dùng quyết lại) → **chọn scope Activity**, không WorkManager.

---

## 5. Thành phần dùng lại và thành phần mới

**Dùng lại, không viết lại** (`ui/components/`): `PageHeader`, `ListSection`/`SectionTitle`/`RowLine`, `ListRow`/`ListItem`, `SwitchRow`, `ActionRow`/`DisclosureRow`/`TextAction`, `Reveal`/`Fold`/`MoreInfo`, `Caption`/`RowHint`/`InlineProblem`/`QuoteSample`, `StageProgress`, `SheetHost`/`SheetLayer`/`SheetPages`, `ConfirmPage`/`DangerButton`/`QuietButton`, `UndoBar`, `ClockLabel`, `BookCover`, `ScrollFade` (`fadeEdges`), `IconAction`, icon trong `Icons.kt`/`LucidePaths.kt`; chuyển động `Motion.*`/`MotionMs`, `motion/Presence.kt`.

**Mới** (`ui/studio/parts/`, mỗi cái dùng ≥ 2 màn — nếu chỉ một màn dùng thì nằm trong màn đó):

| Thành phần | Việc | Dùng ở |
|---|---|---|
| `StudioTabs` | Thanh tab chữ, gạch chân trượt (`Motion.TabSlide`), vuốt ngang đổi tab, giữ cuộn từng tab | Dự án |
| `PrimaryAction` | Nút chính duy nhất, đổi nhãn/biểu tượng theo trạng thái bằng `GlyphMorph`, giữ chiều rộng | Dự án, Duyệt trước, Xuất |
| `ProgressBlock` | Vòng/thanh tổng + "chương 12/48 · còn 2:14" bằng `ClockLabel`; không nhảy khi số đổi | Studio, Dự án, Xuất |
| `DecisionCard` | Thẻ việc: tiêu đề, "vì sao hỏi", câu ví dụ có nút nghe, 2–4 nút trả lời lớn, "Bỏ qua" | Việc cần duyệt, Cần nghe lại, Duyệt trước |
| `LineSample` | Một câu thoại + người nói + nút phát (tải clip rồi phát, `AndroidSamplePlayer`) | Thẻ việc, Kịch bản, Nhân vật |
| `CardDeck` | Xếp thẻ: thẻ trên cùng lớn, thẻ kế ló ra; trượt-và-gập khi đã quyết; đếm còn lại (`ClockLabel`) | Việc cần duyệt, Cần nghe lại |
| `VoiceSheet` | Chọn giọng: danh sách theo nhóm, nghe thử, lọc giới/độ tuổi | Nhân vật, thẻ voice-wish |
| `PermissionCard` | Thẻ "Máy tính chưa cho bạn sửa" (3.4) | mọi màn |
| `LinkBanner` | Dải "{máy} không trả lời - đang chờ nối lại" (`StudioLink.silentLine`) trượt xuống | mọi màn |
| `UploadRow` | Hàng tệp đang tải: tên, cỡ, % (`ClockLabel`), Huỷ | Sách mới, Bìa |

---

## 6. Từng màn: mỗi điều khiển ở đâu, vì sao

Quy ước bảng: **Giữ** = giữ chức năng, đổi hình; **Gộp** = gộp vào điều khiển khác; **Bỏ** = không có trên điện thoại (có lý do).

### 6.1 Studio (danh sách máy + dự án) — `StudioHomeScreen`

Web: `ProjectsScreen` — bảng dự án nhiều cột, lọc, dải trạng thái, "Dự án mới".

Bố cục: nếu chỉ một máy tính cho phép Studio, không có bước chọn máy (mở thẳng danh sách); nhiều máy thì tên máy là tiêu đề, nhấn mở sheet chọn máy. Dưới là một cột thẻ dự án.

| Điều khiển | Vị trí | Vì sao |
|---|---|---|
| Thẻ dự án (bìa nhỏ, tên, trạng thái một dòng, thanh tiến độ) | Cột chính, cuộn dọc | Một thẻ = một ngón chạm; tiến độ là thứ người dùng nhìn đầu tiên. Thanh + "chương 12/48" tự đổi tại chỗ (`ClockLabel`). |
| Nhóm "Đang chạy" ở đầu, "Cần duyệt" kế, "Còn lại" cuối | Tiêu đề nhóm (`SectionTitle`) | Web dùng cột lọc; điện thoại sắp theo *điều cần làm ngay*. Không có ô lọc: danh sách dự án một người thường < 30. |
| Huy hiệu số việc cần duyệt trên thẻ | Góc thẻ | Là điều khiến người dùng mở app (thông báo cũng dẫn tới đây). |
| "Sách mới" | Một nút chính ở cuối danh sách + hàng trống khi chưa có dự án | Nút chính duy nhất của màn (DS §4). |
| Chọn máy | Tiêu đề (chỉ hiện khi ≥ 2 máy) | Ít người có hai máy. |
| Dải lệch phiên bản (`StudioLink.mismatched`) | Đầu danh sách, `LinkBanner` | Báo "Máy tính cần cập nhật" thay vì để lỗi lạ giữa chừng. |
| Hàng chờ ("đang chờ lượt 2") | Dòng trạng thái của thẻ | Từ `book.starting`/hàng đợi, không cần màn riêng. |
| Bỏ: lọc theo trạng thái, sắp theo cột, chọn nhiều để xoá, "Mở thư mục", đổi thư mục thư viện | — | Không có trong `ALLOWED` hoặc không có nghĩa trên điện thoại. |

Dữ liệu: `GET /sync/v1/studio` cho lần mở đầu (gọn), rồi `GET /api/library` khi cần tiến độ chi tiết. Nhịp: 5 s khi có sách chạy, 15 s rảnh.
Mở thẻ → `Destination.StudioProject` (đẩy vào `Motion.PushIn`).

### 6.2 Dự án — `StudioProjectScreen` (khung + tab)

Web: `ProjectScreen` (1.566 dòng): đầu trang, ba hàng nút, tab, bảng chương.

| Điều khiển | Vị trí | Vì sao |
|---|---|---|
| Bìa + tên + tác giả + trạng thái | Đầu trang gập được khi cuộn (`fadeEdges`) | Chiếm màn khi không cần. |
| **Nút chính theo trạng thái** (`primaryKind`): chưa chạy → "Bắt đầu"; đang chạy → "Tạm dừng"; đã tạm dừng → "Tiếp tục"; xếp hàng → "Bỏ xếp hàng"; xong → "Nghe" (mở sách trong phần Nghe) | Dưới đầu trang, một nút rộng | Một nút chính. `POST start/pause/dequeue`. |
| "Dừng" | Trong "Thêm" → `ConfirmPage`: *Dừng khi đang phân tích là bỏ cả pha phân tích* (luật AGENTS: dừng giữa phân tích đổi cả quyển sách) | Không đặt gần "Tạm dừng" để khỏi bấm nhầm. `DangerButton`. **Nút "Tạm dừng" luôn là chọn đầu** — khớp luật dự án. |
| Tiến độ cả sách (`ProgressBlock`) | Ngay dưới nút chính | Số tự đổi. |
| Tab: Chương · Việc cần duyệt · Cần nghe lại · Nhân vật · Nhạc nền (`StudioTabs`) | Dưới tiến độ | Đúng 5 tab của DS §7. Số ở nhãn tab là `ClockLabel`. |
| "Thêm" (sheet): Duyệt trước khi thu · Kịch bản · Cách đọc tên · Xuất · Bìa · Nhật ký · Thông tin · Đổi tên · Dừng | Nút góc phải `PageHeader.trailing` | Hiếm dùng. 9 mục là mức tối đa của một sheet; nhóm bằng `SectionTitle`. |
| "Thay đổi từ máy khác" (PhoneEdits) | Hàng ở đầu tab Chương khi `edits-inbox` còn mục, mở `SheetPages` | Điện thoại ít khi cần xem việc *chính nó gửi*, nhưng máy tính thứ hai gửi thì có. |
| "Chờ áp dụng" (`pending-changes`) | Dải dưới nút chính: "N thay đổi chờ áp dụng" + "Áp dụng" / "Rút lại" (`pending-changes/withdraw`) | Quyết định mà *chỉ áp khi làm lại* — người dùng phải thấy. |
| "Sửa thiết lập" / "Làm lại phân tích" (`GET .../redo`) | Trong "Thêm" → hộp xác nhận | Hiếm; bắt buộc `ConfirmPage` vì đổi cả quyển. |
| Bỏ: "Mở thư mục", "Xoá dự án", "Dùng pin" (công tắc pin của máy tính) | — | Không có trong `ALLOWED` (xoá, mở Explorer); "Dùng pin" của máy tính do máy tính tự quản. |

Lỗi: 404 → thẻ "Dự án này không còn" + "Về Studio" (không hỏi tiếp); lỗi mạng có bản cũ → `LinkBanner`; chưa có bản cũ → `InlineProblem` + "Thử lại".

### 6.3 Tab Chương — `ChaptersTab`

| Điều khiển | Vị trí | Vì sao |
|---|---|---|
| Hàng chương (tên, độ dài hoặc số câu, trạng thái: chưa/đang/đã thu/cần nghe) | Cột chính | Web có bảng 6 cột; điện thoại giữ tên + một trạng thái + độ dài. |
| Đang làm chương nào: hàng sáng + "đang thu 38/120 câu" (`ClockLabel`) | Hàng hiện tại | Một thứ đổi theo thời gian. |
| Chạm hàng | Mở sheet chương: Nghe · Kịch bản · Thu lại · Đổi tên · "Chạy phần này trước" | Hiếm dùng nên không đặt nút trên từng hàng. |
| "Thu lại chương" (`POST .../retake`) | Sheet chương → `ConfirmPage` ("Câu đã thu sẽ bị thay") | Không hoàn tác được. |
| Đổi tên chương (`PUT .../chapters/<n>/title`) | Sheet chương | Nhập một dòng (`BookEditor` mẫu). |
| Nghe chương | Sheet chương | Tải clip `/media/books/<id>/chapters/<n>` rồi phát; cho sách đã có audio. [chưa chắc] chương dài tải lâu: dùng phần Nghe của app (kéo sách về) thay vì tự phát. |
| Bỏ: sắp theo cột, chọn nhiều | — | Không cần. |

### 6.4 Tab Việc cần duyệt — `WorkTab` (lõi của Studio từ xa)

Web: `WorkInbox` — danh sách 16 loại thẻ, tất cả cùng mở rộng tại chỗ.

**Thiết kế cho điện thoại:** một **bộ bài** (`CardDeck`): mỗi lần *một* thẻ, to, với các nút trả lời lớn ở đáy tầm ngón cái; trượt sang là thẻ kế. Đếm còn lại ("Còn 12") bằng `ClockLabel`. Hết thẻ → trạng thái "Đã duyệt hết" kèm nút "Tiếp tục" hay "Nghe cuốn" tuỳ trạng thái. Sách đang chạy thì thẻ mới tự rơi vào cuối bộ (hỏi 3 s/lần), không xáo thứ tự.

16 `WorkKind` gom thành **5 mẫu thẻ** (một `@Composable` mỗi mẫu; kiểu → mẫu bằng một bảng trong `WorkCardKinds.kt`):

| Mẫu thẻ | Các kiểu | Điều khiển | Gửi |
|---|---|---|---|
| **Chọn một** | `speaker`, `turn`, `gender`, `vocative`, `alias`, `bracket`, `narrator`, `teller-voice`, `teller-thought`, `unnamed` | Câu ví dụ (`LineSample`, có câu trước/sau khi `before/after`), nút `choices[]` (≤ 4 nút lớn; nhiều hơn thì "Chọn khác…" mở `SheetPages`), phạm vi nếu có `scopeLabels` ("Câu xen kẽ" · "Cả chuỗi") là hai chip | `POST .../speaker`, `.../line`, `.../narrator-section` theo `decisions.ts` |
| **Cách đọc** | `pronunciation` | Chữ gốc (`surface`), ô nhập cách đọc, "Nghe thử" (`pronunciation/preview`, tải wav rồi phát), "Giữ như cũ"; kiểm trước `pronunciation/check` | `POST .../pronunciation`, `.../shared-readings` |
| **Giọng** | `voice-wish`, `shared-voice` | Tên nhân vật, giọng hiện tại, "Nghe giọng" (`voice/preview`), `VoiceSheet` để đổi | `POST .../voice` |
| **Nghe lại** | `audio`, `snap` | Nút phát lớn, "Ổn", "Đọc lại", hiển thị "Sẽ đọc là “…”" | `POST .../review` |
| **Bị từ chối** | `refused` | Giải thích một câu + "Bỏ qua", "Sửa chữ" (mở Kịch bản tại câu) | `POST .../line` |

Mỗi thẻ có chung: tiêu đề `title` (một câu), `problem` ở `MoreInfo` ("Vì sao hỏi"), `affected`/`doubt` chỉ là chấm nhỏ "ảnh hưởng 14 câu" (không hiện điểm `score`), "Bỏ qua" (chuyển thẻ cuối bộ, không gửi gì), "Hoàn tác" 15 s (`UndoBar`).

**Rào bắt buộc** (port nguyên từ `decisions.ts`): thân yêu cầu chứa `lines[{stableId, textSha256}]` — máy tính từ chối câu đã đổi chữ. Lỗi 409 → thẻ hiện "Câu này đã đổi, bạn xem lại" và nạp lại bộ bài; **không** tự gửi lại.

**Bỏ**: lọc theo loại/điểm, "xem tất cả ví dụ" (`work/examples` chỉ nạp khi bấm "Xem thêm câu" ở `MoreInfo`), kéo thả chọn nhiều câu cho `unnamed` (thay bằng danh sách có ô chọn trong `SheetPages` "Chọn câu").

Nhịp: `GET .../work` mỗi 3 s khi sách chạy, tắt khi tạm dừng hay xong.

### 6.5 Tab Cần nghe lại — `ReviewTab`

Web: `ReviewQueue` — danh sách câu có chấm sai, bộ lọc.

| Điều khiển | Vị trí | Vì sao |
|---|---|---|
| Danh sách câu: chữ, người nói, điểm nghi ngờ (chấm màu), nút phát | Cột chính | Cùng `LineSample`. |
| Phát | Nút ở hàng | Web phát qua `useClip` với nguồn `urls.chapterAudio` + cửa sổ `chapterClip` (bắt đầu/kết thúc trong chương). Native: tải chương một lần (3.2-B) vào cache rồi `AndroidSamplePlayer` phát cửa sổ ấy; mọi câu cùng chương dùng lại tệp. Nút "Phát tiếp" tự sang câu kế có audio (như `ReviewQueue` dòng 329). |
| "Ổn" / "Đọc lại" | Hai nút dưới câu đang mở (`Reveal`) | Hai nút to thay cho menu; `POST .../review`. |
| Lọc (`label="Lọc"`) | Chip hàng ngang ở đầu (Tất cả · Chưa nghe · Của {nhân vật}) | Giữ bộ lọc quan trọng nhất, bỏ phần còn lại. |

### 6.6 Tab Nhân vật — `CastTab`

| Điều khiển | Vị trí | Vì sao |
|---|---|---|
| Danh sách nhân vật: tên, số câu, giọng hiện tại, nút nghe giọng | Cột chính, nhóm "Chính" · "Phụ" | Web là bảng; điện thoại một hàng. |
| Đổi giọng | Chạm hàng → `VoiceSheet` (nhóm giọng, nghe thử bằng `/media/voices/<id>`, lọc giới/tuổi) → `POST .../voice` | Nghe trước khi chọn (DS "nghe mới tin"). |
| Đổi tên (`characters/rename`) · Gộp vào… (`characters/merge`) | Sheet nhân vật | Hiếm; gộp là không hoàn tác được → `ConfirmPage`. |
| "Người kể xưng tôi tự kể chuyện" (`narrator-mode`) | `SwitchRow` ở đầu tab, kèm giá ("tốn thêm …" từ GET) | Công tắc có hậu quả → chú thích giá ngay dưới. |
| Cách đọc tên của nhân vật | Mục trong sheet nhân vật → mở màn 6.10 | Đường vào theo ngữ cảnh. |

### 6.7 Tab Nhạc nền — `MusicTab`

Web: `MusicTab` — thể loại, mức nhạc, bài từng đoạn, nhạc của tôi, nhập nhạc, mood AI.

| Điều khiển | Vị trí | Vì sao |
|---|---|---|
| Công tắc "Nhạc nền" (bật/tắt cuốn) và "Mức nhạc nền" (thanh) | Đầu tab | Hai điều người dùng chạm nhiều nhất. `PUT .../music`. |
| "Thể loại truyện" | `DisclosureRow` → `SheetPages` chọn một | Hiếm đổi. |
| Danh sách đoạn (cảnh) → bài đang dùng + nghe thử | Cột chính | Bài là `GET .../music/files/<track>`: tải vào cache rồi phát. |
| "Đổi bài" cho một đoạn | Chạm hàng → `SheetPages` danh sách ứng viên (`music/scenes/<id>/alternatives`), nghe thử, chọn | `PUT .../music`. |
| "Dựng lại" (`music/rebuild`) | `TextAction` cuối tab → `ConfirmPage` | Tốn công máy tính. |
| Tải sẵn nhạc nền (đang tải, "Huỷ tải" `music/download/cancel`) | Hàng tiến độ `StageProgress` + "Huỷ tải" | Hỏi 2 s khi `downloading`. |
| "Đọc không khí cả đoạn bằng AI" (`music/moods`) | `Fold` "Nâng cao" | Chỉ hiện khi `moods-model` đã tải trên máy tính (điện thoại không *tải* 3,2 GB về máy tính — không có trong `ALLOWED`). |
| Bỏ: "Nhập nhạc" / "Nhạc của tôi" (nhạc riêng nằm trên máy tính), "Thêm tuỳ chọn cho đoạn" | — | `/api/music/local/...` không có trong `ALLOWED` (nhạc cá nhân không ra khỏi máy tính). |

### 6.8 Kịch bản — `ScriptScreen` (từ "Thêm")

Web: `ScriptTab` (1.856 dòng) — văn bản chương theo dòng, sửa người nói, sửa chữ, nghe từng câu.

| Điều khiển | Vị trí | Vì sao |
|---|---|---|
| Chọn chương | `PageHeader` có tên chương, chạm → sheet chương | Một màn một chương. |
| Danh sách câu: người nói (nhãn màu), chữ, nút phát | Cột chính, `LazyColumn` | Chữ chương dài: **chỉ phần thấy được** (không nạp 5.000 dòng vào Compose). |
| Sửa người nói câu | Chạm nhãn → sheet nhân vật (`POST .../line`) | Hai chạm. |
| Sửa chữ câu | Chạm chữ → hộp nhập (có `textSha256`) | Chữ truyện: **không bao giờ tự sửa**; chỉ khi người dùng bấm sửa (luật "không tự sửa nội dung"). |
| Bỏ: tìm-thay thế cả cuốn, chọn nhiều câu, kéo | — | Việc của máy tính. |

### 6.9 Duyệt trước khi thu — `PrecastScreen`

Web: `PrecastReview` + công tắc "Chờ tôi duyệt" / nút "Thu âm".

| Điều khiển | Vị trí | Vì sao |
|---|---|---|
| Các bước duyệt (bước i/N) | `StageProgress` + `ClockLabel` | Số đổi tại chỗ. |
| Mỗi bước là một thẻ `DecisionCard` (cách đọc tên, giọng…) | Cột chính | Cùng mẫu thẻ 6.4. |
| "Chờ tôi duyệt" | `SwitchRow` đầu màn (`PUT .../precast`) | Bật = dây chuyền dừng ở cổng này. |
| **"Thu âm"** | Nút chính khi đã duyệt xong (`POST .../pause` để tiếp) | Một nút chính; nhãn đổi từ "Duyệt xong" sang "Thu âm". |
| "Khi áp dụng" (`applyWhen`) | Chip trong `SheetPages` "Áp dụng lúc nào" (ngay / lần làm lại sau) | Giữ nguyên ý web; mặc định đúng. |

### 6.10 Cách đọc tên — `ReadingsScreen`

| Điều khiển | Vị trí | Vì sao |
|---|---|---|
| Danh sách tên cần chốt (chữ gốc → cách đọc hiện tại) | Cột chính | `GET .../pronunciations`. |
| Sửa cách đọc | Chạm hàng → hộp một dòng + "Nghe thử" + "Lưu" | Nghe trước lưu. |
| "Nghe thử" | Nút trong hộp | `POST .../pronunciation/preview` ~tới 120 s: nút thành vòng tiến độ có "Huỷ"; hết hạn thì nói rõ "Máy tính chưa kịp đọc". |
| "Tác động" (`pronunciations/reach`) | Dòng chú dưới ô nhập: "Đổi sẽ ảnh hưởng 23 câu" | Biết hậu quả trước khi lưu. |
| Gợi ý bỏ dòng ghi công (`suggestions`, `skip`) | Mục riêng cuối màn, **mặc định không áp** | Luật: app không tự sửa chữ, chỉ đề xuất. |
| Chia sẻ cách đọc giữa các sách (`shared-readings`, `/api/readings`) | `SwitchRow` "Dùng cho mọi sách" | Giữ chức năng. |

### 6.11 Xuất — `StudioExportScreen`

Web: `ExportBook` — kiểu bản xuất, phạm vi, cách chia file, nhạc nền, ffmpeg, lịch sử.
Khung mẫu: `ui/export/ExportScreen.kt` (xuất trên điện thoại), **cùng hình dáng, khác nguồn**: việc chạy *trên máy tính*, file nằm *trên máy tính* ("Đã xuất" trong thư viện của máy tính).

| Điều khiển | Vị trí | Vì sao |
|---|---|---|
| Kiểu: File sách (.abook) · M4B · Thư mục MP3 | Ba hàng chọn một | Đúng ba job của `ALLOWED`. Chữ lấy từ `ExportCopy` (giữ nguyên chữ web: "Đang đóng gói sách…", "Đã xuất file sách"…). |
| Phạm vi (cả sách / chương) và cách chia | `SheetPages` "Tuỳ chọn" (cấp 2) | Hiếm đổi; mặc định là cả sách. |
| "Kèm nhạc nền" | `SwitchRow` + dòng cỡ thêm (`export-music`, `export-size`) | Cỡ là điều người ta cân nhắc. |
| ffmpeg chưa có | Thẻ "Máy tính chưa có ffmpeg" (`GET /api/ffmpeg`), **không có nút tải** (tải ffmpeg chỉ ở máy tính) | Không có trong `ALLOWED`. |
| **"Xuất"** | Nút chính | Một nút. |
| Tiến độ: pha + "chương 5/48" + (M4B) thời gian đã trôi | `ProgressBlock` (`ClockLabel`) | Hỏi 1 s khi chạy, 5 s đọc `export-jobs`. |
| "Huỷ" | Nút phụ khi chạy → `ConfirmPage` nhẹ | Job M4B/MP3 huỷ được ở mọi pha. |
| Lịch sử (`export-history`) | `Fold` cuối màn | Có thì xem. |
| Sau khi xong | "Đã xuất. File nằm ở {tên thư mục} trên {máy}." + "Kéo về điện thoại" (đưa sang luồng tải sách của phần Nghe) | Tên thư mục chỉ là TÊN (`without_local_paths`). |

### 6.12 Sách mới — `StudioNewScreen`

Web: `NewProjectScreen` (2.049 dòng) — nguồn, tách chương, mẫu thiết lập, người kể xưng tôi, mô hình phân tích, bìa.

Làm thành **ba bước** có `StageProgress` (Nguồn → Chương → Bắt đầu), mỗi bước một màn con trong cùng `Destination` (trượt ngang). Mặc định đúng, nên người dùng thường chỉ chạm "Tiếp" hai lần.

| Điều khiển | Bước | Vì sao |
|---|---|---|
| "Chọn tệp" (txt/epub/docx/pdf; nhiều tệp) | 1 | `OpenMultipleDocuments`; hàng `UploadRow` có % và "Huỷ". |
| Dán chữ | 1 | `Fold` "Dán chữ" (tiện trên điện thoại). |
| Nhắc cỡ: > ~17 MiB báo trước | 1 | Lệch 24 MiB/40 MB (1.5): nói "Tệp quá lớn để gửi qua Wi-Fi, hãy chọn từ máy tính" thay vì lỗi giữa chừng. |
| Tên sách, tác giả | 1 → 3 | `scan` đoán sẵn, người dùng sửa. |
| Danh sách chương tách (`sources/split`) | 2 | Gộp/tách chương trên điện thoại là việc khó: chỉ cho **đổi tên**, **bỏ chương**; "Tách lại" (đổi cách tách) mở `SheetPages`. |
| Mẫu thiết lập (`book-templates`) | 3 | `DisclosureRow` "Mẫu thiết lập"; lưu/đổi tên/xoá mẫu ở `SheetPages` cấp 2. |
| Người kể xưng "tôi" (`first-person`) | 3 | `SwitchRow`, chú thích giá. |
| Mô hình phân tích (`analysis-models`) | 3 | `ChoiceSetting`; mặc định theo máy tính. |
| **"Bắt đầu"** | 3 | `POST /api/books` rồi `POST .../start` — một nút chính. |

Bỏ: kéo-thả thư mục, nhập từ đường dẫn máy tính (`/api/dialog/*`), mở sách theo đường dẫn. Mọi `paths` do máy tính ép nằm trong thư mục tải lên (`X-Abook-Remote`).

### 6.13 Bìa — dùng lại `CoverSearchScreen` + `CoverCrop`

Nguồn hiện tại là `EditSource` (sửa sách cục bộ). Thêm `StudioCoverSource : EditSource` gọi `GET .../cover/search`, `PUT .../cover {image|url}`, `DELETE .../cover`, `GET /media/books/<id>/cover`. `PUT {image}` dùng tải lên dòng chảy (3.2-C), thu nhỏ ảnh về ≤ 1.600 px trước khi gửi (cắt từ `CoverCrop` đã có). **Ít mã nhất, không màn mới.**

### 6.14 Nhật ký và Thông tin

- **Nhật ký** (`GET .../activity`, mảng): sheet dạng danh sách giờ + việc; nhịp 5 s khi chạy; "Chi tiết kỹ thuật" công tắc (`?technical=1`) ở `Fold`.
- **Thông tin**: số chương, độ dài, xong lúc, trạng thái — `ListRow` chỉ đọc.

---

## 7. Logic TypeScript phải port sang Kotlin (không viết lại từ trí nhớ)

Chỗ này là nơi "port lười" dễ sai nhất. Mỗi mục là hàm *thuần* ở web, có test; bản Kotlin sinh test từ **cùng bảng ví dụ** (xuất JSON một lần từ test TS, đặt dưới `app/src/test/resources/studio_contract/`, kiểm ở cả hai phía — kiểu `LocalStudio` đang làm).

| Logic web | Nguồn | Vì sao phải khớp từng chữ |
|---|---|---|
| Dựng thân quyết định cho 16 `WorkKind` | `decisions.ts` | `textSha256`, phạm vi, `requestedAt`; sai là áp nhầm câu |
| Chữ thẻ việc ("Vì sao hỏi", "ảnh hưởng N câu") | `workText.ts` | Chữ hai nền tảng đồng nhất |
| `primaryKind` (nút chính theo trạng thái) và `Actions` | `ProjectScreen.tsx` | Điều kiện nút nào hiện |
| `pollDelay`, `isGone`, `isListenOnly`, `isOffline`, `failureText`, `bookFailure` | `polling.ts` | Nhịp + lời lỗi |
| `producingRefetch` (khi nào nhịp nhanh) | `liveRefresh.ts` | Tránh hỏi vô ích |
| `packView`/`BOOK_FILE_SPAN`, `ExportCopy` (`BOOK_FILE_COPY`, `M4B_COPY`, `MP3_COPY`), `lastExportHint` | `projectPacking.ts`, `ExportBookFileJob.tsx` | Chữ "Đang đóng gói sách…" |
| Quy tắc ghi theo `requestedAt` + hoàn tác 15 s; phép kiểm `seen` | `ApplyChanges.tsx`, `CastEdits.tsx`, `PhoneEdits.tsx` | Không gửi quyết định cũ đè quyết định mới |
| Kiểm cỡ/loại tệp nguồn, tách chương | `upload.ts`, `NewProjectScreen.tsx` | Báo đúng lỗi |
| `applyWhen` / `precast` hold | `PrecastReview.tsx`, `ApplyChanges.tsx` | Ngữ nghĩa "Chờ tôi duyệt" |

Không port: dựng URL băm (`#/studio/...`), TanStack Query, `MotionRegion` (đã có `Reveal`), CSS.

---

## 8. Kotlin: file thêm, file sửa, file xoá

### 8.1 Thêm (đường gốc `_internal/mobile/android/app/src/main/java/vn/abook/player/`)

| File | Việc |
|---|---|
| `StudioApi.kt`, `StudioErrors.kt` | Client trên `SyncLink` (3.3); phân loại lỗi |
| `StudioPoller.kt`, `StudioCache.kt` | Nhịp hỏi + cache RAM (3.5) |
| `StudioClips.kt` | Tải clip vào `cacheDir/studio_clips/`, phát qua `AndroidSamplePlayer`, dọn cache |
| `ui/studio/StudioSource.kt` (interface), `StudioRepo.kt` (cài đặt qua `StudioApi`), `StudioFake.kt` (test dir) | Mẫu `Source/Repo/Fake` của `ui/devices`, `ui/export` |
| `ui/studio/StudioJson.kt` | Kiểu dữ liệu + phân tích (`Project`, `Chapter`, `WorkItem`, `Cast`, `MusicPlan`, `ExportJob`...) — strict như `StrictJson.kt` |
| `ui/studio/StudioState.kt`, `StudioModel.kt` | Trạng thái màn, hoàn tác 15 s, xếp thân chưa gửi |
| `ui/studio/StudioText.kt` | Mọi chữ tiếng Việt của Studio (một nguồn, test chiều dài nhãn 1–4 chữ) |
| `ui/studio/StudioHomeScreen.kt` | 6.1 |
| `ui/studio/ProjectScreen.kt`, `ProjectSheets.kt` | 6.2 |
| `ui/studio/ChaptersTab.kt` | 6.3 |
| `ui/studio/WorkTab.kt`, `WorkCards.kt`, `WorkCardKinds.kt`, `WorkDecisions.kt` | 6.4 |
| `ui/studio/ReviewTab.kt` | 6.5 |
| `ui/studio/CastTab.kt`, `VoiceSheet.kt` | 6.6 |
| `ui/studio/MusicTab.kt` | 6.7 |
| `ui/studio/ScriptScreen.kt` | 6.8 |
| `ui/studio/PrecastScreen.kt` | 6.9 |
| `ui/studio/ReadingsScreen.kt` | 6.10 |
| `ui/studio/StudioExportScreen.kt`, `StudioExportModel.kt` | 6.11 |
| `ui/studio/StudioNewScreen.kt`, `StudioNewModel.kt` | 6.12 |
| `ui/studio/StudioCoverSource.kt` | 6.13 |
| `ui/studio/ActivitySheet.kt` | 6.14 |
| `ui/studio/parts/` (`StudioTabs`, `PrimaryAction`, `ProgressBlock`, `DecisionCard`, `LineSample`, `CardDeck`, `PermissionCard`, `LinkBanner`, `UploadRow`, `VoiceRow`) | §5 |

### 8.2 Sửa

| File | Sửa |
|---|---|
| `SyncLink.kt` | A (mảng), B (tải nhị phân), C (tải lên dòng chảy) — 3.2 |
| `ui/data/Production.kt` | `ProductionSource.read()` dùng A (sửa lỗi 1.5-1) |
| `ui/nav/Nav.kt` | `Destination.Studio*` (4.2) |
| `ui/NativeActivity.kt` | `openStudio` đẩy `Destination` thay `Intent(StudioActivity)` (dòng 229); `onNewIntent` đọc extras thông báo; thêm launcher `OpenMultipleDocuments` cho nguồn |
| `ui/PendingAnswers.kt` | Thêm các câu trả lời chọn tệp của Studio nếu dùng cùng cơ chế với nhập sách |
| `ui/screens/OtherScreens.kt` (`StudioScreen`) | Bấm máy → đẩy `Destination.Studio` thay vì `openStudio(path)` |
| `StudioAlerts.kt` | `PendingIntent` về `NativeActivity` (dòng 186) |
| `StudioLink.kt` | Bỏ `bookPath`/`safePath` (không còn đường trang web); giữ `computers/known/rebase/Watch/...` |
| `Devices.kt` | `studioTarget` trả (máy, mã cuốn) thay vì (máy, đường trang) (dòng 219) |
| `ui/editbook/*` | `EditSource` nhận nguồn từ xa (cho 6.13); cảnh giác: giữ giao diện hiện tại |
| `TickingValuePolicyTest.kt` | Thêm các hàm định dạng số mới vào `formatters` |
| `app/src/nativeUi/AndroidManifest.xml`, `app/src/main/AndroidManifest.xml` | Bỏ khai `StudioActivity` (dòng 86–88) |

### 8.3 Xoá (S5)

`StudioActivity.kt` (342 dòng), `StudioLink.bookPath/safePath/rebase/Watch/MISMATCH` và phần test của chúng trong `StudioLinkTest`, khai manifest, `LibraryPlugin.openStudio` (dòng 580–584). **Đã làm ở S5.** `LibraryPlugin.openStudio` phải xoá ngay trong S5 vì nó tạo `Intent` tới `StudioActivity` nên không biên dịch được; việc này làm bản WebView mất Studio (xem §0). `Devices.studioTarget` trả `(mã máy, StudioRoute)` thay cho đường trang chữ, và thông báo `StudioAlerts` luôn mở `NativeActivity`.

---

## 9. Chỗ máy tính phải thêm/đổi (KHÔNG làm ở phiên này; `_internal/abook/` không được đụng)

Điện thoại chỉ cần JSON; **không đường nào của Studio hiện trả HTML cho phần điện thoại cần** (HTML duy nhất là `pairing_page` cho trình duyệt). Các chỗ lệch:

| # | Việc | Đề xuất | Cần hay không |
|---|---|---|---|
| 1 | `GET /api/voices`, `.../activity`, `/api/listen/library` trả **mảng trần** | Hoặc bọc `{items:[...]}`, hoặc giữ nguyên (điện thoại xử lý mảng, 3.2-A) | Không bắt buộc: sửa phía điện thoại là đủ. Bọc đồng nhất vẫn tốt hơn lâu dài; **chủ sách quyết**. |
| 2 | `POST /api/sources/upload` giới hạn 24 MiB thân (~17 MiB tệp) trong khi UI nói 40 MB | Nâng `MAX_FORWARD_BODY` riêng cho đường này, hoặc thêm tải lên **chia khúc** (`POST .../upload/chunk`) | **Nên**: epub/pdf lớn |
| 3 | Mã lỗi: 403 `listenOnly` có; 404/409/413 chưa thống nhất khoá `error` | Quy ước `{"error": "...", "code": "..."}` cho mọi đường Studio | Nên, để lời lỗi không phải đoán |
| 4 | `POST .../voice/preview`, `.../pronunciation/preview` giữ kết nối tới 120 s | Trả `202` + `GET` hỏi trạng thái (kiểu `*-job`) | Nên (di động đổi mạng giữa chừng dễ rớt); không bắt buộc |
| 5 | `GET /api/app` mang quá nhiều cho điện thoại | Giữ; điện thoại chỉ đọc `listenOnly`, `studio.*` | Không |
| 6 | Không có đường "nghe câu" cho thẻ `audio` | Dùng cửa sổ trong audio chương (`chapterClip`) — đã có | Không |
| 7 | Thông báo đẩy từ máy tính | Hiện là hỏi `/sync/v1/studio` bằng `StudioAlertWorker` (định kỳ) | Không |

Hai phát hiện đáng báo ngoài phạm vi Studio: (a) lỗi `ProductionSource` (1.5-1) sửa bằng 3.2-A; (b) `POST` chỉ nhận JSON nên không có `multipart` — mọi nhị phân đi base64 (nặng 33 %).

---

## 10. Danh sách P4: còn gì của WebView/Capacitor/gói web trong APK `-PnativeUi`

Kiểm bằng Grep trên `_internal/mobile/android/`. "Studio" = bị bỏ trực tiếp bởi tài liệu này; "P4" = việc khác của NPU §6 P4 mà danh sách này nêu cho đủ.

| Mục | Vị trí | Gỡ bởi |
|---|---|---|
| `StudioActivity` (`AppCompatActivity` + `WebView`) | `StudioActivity.kt`; manifest chính dòng 86–88 | **Studio (S5) - ĐÃ XOÁ** |
| `LibraryPlugin.openStudio` | `LibraryPlugin.kt` 580–584 | **Studio (S5) - ĐÃ XOÁ** (không biên dịch được sau khi `StudioActivity` đi; bản WebView mất Studio, nên S5 gộp cùng P4) |
| `MainActivity` (`BridgeActivity`, `LaunchSplash`, `textZoomFor`) | `MainActivity.kt`; test `FontScaleAndArtistTest` (`textZoomFor`) | P4 |
| `LibraryPlugin` (1.381 dòng, 109 `PluginCall`), `PlayerPlugin`, `readaloud/ReadAloudPlugin` | `*.kt` | P4 (bắt buộc kiểm: không `ui/` nào gọi Plugin ngoài chú thích) |
| `HeldCallFields` + `HeldCallFieldsTest` | gói gốc | P4 (chỉ dùng cho `PluginCall`) |
| Layout `activity_main.xml` (`WebView` + `CoordinatorLayout`) | `res/layout/` | P4 |
| Theme AppCompat (`AppTheme*`, parent `Theme.AppCompat*`) | `res/values/styles.xml` | P4 → Material/Compose theme |
| `network_security_config.xml` — `cleartextTrafficPermitted` (chú thích cũ) | `res/xml/` | P4: kiểm lại còn cần không |
| Manifest chính khai `MainActivity` (`StudioActivity` đã bỏ ở S5); overlay `src/nativeUi/AndroidManifest.xml` (`removeAll` filter) và `NativeManifestFiltersTest` | manifest | P4 |
| Capacitor: `capacitor.build.gradle`, `capacitor.settings.gradle`, `mobile/package.json`, `mobile/capacitor.config.json` (`webDir: www` → `assets/public` qua `cap copy`) | `mobile/`, `app/` | P4 |
| Phụ thuộc Gradle: `androidx.appcompat`, `androidx.coordinatorlayout`, `capacitor-android`, `capacitor-app`, `cordova-plugins` | `app/build.gradle` | P4 |
| Gói web `ui/dist` + `ui/src/android/` (84 file) + `assets/public` | `_internal/ui/`, APK | P4 (APK `-PnativeUi` không nên chứa; kiểm `NativeManifestFiltersTest` và bước đóng gói) |
| Quy tắc ProGuard: giữ Capacitor, `@JavascriptInterface` | `proguard-rules.pro` | P4 |
| `LocalStudio.kt` (809 dòng) | gốc | **Giữ**: `EditBookRepo` (sửa sách `.abook` cục bộ) vẫn dùng nó; chỉ bỏ cầu `LocalStudio.handle` qua Plugin nếu P4 đưa Plugin đi |
| Cookie: `CookieManager` và `WebView` cho Studio | `StudioActivity` | **Studio (S5) - ĐÃ XOÁ** |

Ghi chú: sau S5 mọi `WebView` còn lại, nếu có, đều thuộc `MainActivity`/Plugin (bản Capacitor), không còn trong luồng `-PnativeUi`. Cổng đã chạy ở S5: `grep -rn "WebView\|CookieManager\|StudioActivity"` trên `main` + `nativeUi` không còn `CookieManager` hay `StudioActivity`; `WebView` chỉ còn ở `MainActivity`, các `*Plugin.kt`, chú thích, regex lọc thẻ log của `Diagnostics.kt` và `res/layout/activity_main.xml` (đều thuộc P4). Cần chạy `grep -rn "WebView\|Capacitor\|BridgeActivity\|PluginCall"` trên cây `ui/` để làm cổng kiểm của P4 (hiện `ui/` không dính ngoài chú thích).

---

## 11. Ước lượng cỡ và pha

### 11.1 Cỡ (số dòng thô, mã Kotlin + Compose, chưa tính test)

| Nhóm | Dòng |
|---|---|
| Mạng: `StudioApi`, `StudioErrors`, `StudioPoller`, `StudioCache`, `StudioClips`, bổ sung `SyncLink` (A,B,C) | ~920 |
| Dữ liệu: `StudioSource/Repo`, `StudioJson`, `StudioState/Model`, `StudioText` | ~2.150 |
| Màn: Home 380 · Project+sheet 750 · Chương 350 · Việc 1.100 + `WorkDecisions` 620 · Cần nghe 400 · Nhân vật+giọng 700 · Nhạc 650 · Kịch bản 550 · Duyệt trước 350 · Cách đọc 500 · Xuất 700 · Sách mới 1.050 · Bìa 150 · Nhật ký/Thông tin 200 | ~7.500 |
| `parts/*` | ~900 |
| Sửa ở file có sẵn (Nav, NativeActivity, OtherScreens, StudioAlerts, Devices...) | ~260 |
| **Tổng mã** | **~12.700** (≈ 45 file mới, 12 file sửa, 1 file xoá) |
| Test (JVM Robolectric/Compose, 12) | **~3.900** |

Sau S5 xoá `StudioActivity.kt` (−342) và, ở P4, các Plugin (≈ −3.000) — nên **cỡ app giảm**. Mục tiêu NPU §1: mã Studio không được thêm dịch vụ nền nào (chỉ `StudioAlertWorker` có sẵn).

### 11.2 Pha (mỗi pha phát hành được riêng, mỗi pha có chụp màn + chạy test theo NPU §5)

| Pha | Gồm | Điều kiện xong |
|---|---|---|
| **S1** | 3.2 (A,B,C) + `StudioApi` + `StudioHomeScreen` + `ProjectScreen` (khung, nút chính, tiến độ, tab Chương) + `LinkBanner`/`PermissionCard` + `Destination` + thông báo mở được | Xem + Bắt đầu/Tạm dừng/Tiếp tục/Dừng chạy được, thông báo mở đúng tab; WebView còn là lối "Mở trang Studio" |
| **S2** | `WorkTab` + `ReviewTab` + `CastTab` + `VoiceSheet` + `LineSample`/clip | Duyệt hết việc; nghe thử; hoàn tác 15 s đúng |
| **S3** | `MusicTab`, `ScriptScreen`, `PrecastScreen`, `ReadingsScreen` | Sửa cách đọc/nhạc/kịch bản |
| **S4** | `StudioNewScreen`, `StudioExportScreen`, `StudioCoverSource`, nhật ký/thông tin | Tạo sách + xuất + bìa |
| **S5** | Xoá `StudioActivity`, cookie, manifest, `LibraryPlugin.openStudio`; chạy cổng P4 | `grep WebView` sạch trong luồng `-PnativeUi` (xong). **Gộp cùng P4**: bản WebView không còn Studio từ S5, nên không phát hành S5 trước P4 |

Khác với đặc tả ở S4 (đã làm):

- Sách mới: không đổi tên chương (thân tạo sách không có trường ấy), không mẫu sách (`GET /api/book-templates` chưa được phép), không bỏ dòng ghi công (không bao giờ tự sửa chữ của truyện), không tách tập, không luồng "làm tiếp"/seed, không "Kéo về điện thoại".
- Xuất: ba kiểu (file sách, M4B, thư mục MP3); không `.abookproj`, không xuất cả bộ/series, không phạm vi "chỉ chương đã đổi" của MP3. File luôn nằm ở thư mục "Đã xuất" của máy tính.
- Thông tin dự án gộp vào đầu màn Nhật ký; màn Bìa không vẽ ảnh bìa hiện tại.

Thứ tự theo giá trị: S1+S2 là 80 % lý do dùng Studio từ điện thoại (xem tiến độ, duyệt). Nếu chỉ làm được hai pha, vẫn giữ lối WebView cho phần còn lại và **P4 vẫn bị chặn** — đó là cái giá của "đầy đủ".

---

## 12. Kế hoạch kiểm (JVM, không cần máy thật)

Cùng kiểu với `ui/devices`, `ui/export`, `ShellScreenshotTest`: Robolectric + Compose test + Roborazzi, `StudioFake` thay `StudioSource`.

| Nhóm | Test | Chặn lỗi gì |
|---|---|---|
| Hợp đồng | `StudioContractTest`: mỗi đường trong 1.2 có một tệp mẫu JSON (sao từ đầu ra thật của máy tính; thêm `tests/` phía máy tính sinh chúng) → `StudioJson` phân tích → so | Đổi máy tính làm vỡ điện thoại âm thầm |
| Thuần | `StudioPollerTest` (đồng hồ giả: 404 dừng, lỗi gấp đôi tới 120 s, `ListenOnly` dừng, nền không hỏi), `StudioErrorsTest` (403/404/409/413), `StudioPathsTest` (mã sách xấu bị từ chối), `WorkDecisionsTest` (bảng ví dụ xuất từ `decisions.test.ts`), `StudioTextTest` (nhãn 1–4 chữ, "bạn", không chữ kỹ thuật) | Port sai |
| Mô hình | `StudioModelTest`: hoàn tác trong 15 s không gửi; hết 15 s gửi một lần; Back không mất; 409 nạp lại bộ bài; hai quyết định liên tiếp cùng khoá chỉ giữ cái sau (`requestedAt`) | Gửi quyết định cũ đè mới |
| Mạng | `SyncLinkArrayTest`, `SyncLinkDownloadTest` (cắt giữa chừng, Range), `SyncLinkUploadTest` (413, ngắt), kiểm không dựng chuỗi ≥ 8 MB (đo `Runtime` trong test) | RAM vọt khi tải lên |
| Màn | Mỗi màn: ảnh chụp sáng/tối, cỡ chữ 1,3×, `fadeEdges`, `testTag` ổn định | `ShellScreenshotTest` mẫu |
| Số bấm | **Đếm lần chạm** cho các luồng chính (duyệt một việc ≤ 2 chạm, nghe thử 1, đổi giọng ≤ 3) — kiểu test đếm chạm có sẵn | Làm app "nặng ngón" |
| Chính sách | `TickingValuePolicyTest` (hàm định dạng mới), `MotionScanTest` (không `visible = if`), `TextCutScanTest`, `ScrollFadeRulesTest`, `NavTest` (Back dự đoán, ngăn xếp ≤ 3), `NativeManifestFiltersTest` (không còn `StudioActivity`) | Chống tái phạm |
| Trạng thái đặc biệt | Chỉ nghe (403), mất mạng giữa chừng, 404 dự án biến mất, nhiều máy, phiên bản lệch | `PermissionCard`, `LinkBanner` |

**Không kiểm được trên JVM** (ghi để biết, không chặn): phát âm thanh thật (`AndroidSamplePlayer` dùng `MediaPlayer`), ghim vân tay với chứng chỉ thật, tải lên 17 MiB trên mạng yếu, chọn tệp bằng SAF. Dùng bản giả `StudioFake` và một lần chạy tay trên emulator **khi** có người cho phép (luật: điện thoại thật = cuối cùng).

---

## 13. Câu hỏi mở

1. **`ProductionSource` mảng (1.5-1)**: xác nhận trên máy thật; nếu đúng, sửa riêng một commit trước S1.
2. **Nâng trần tải lên** (§9-2): chủ sách quyết hướng nào (nâng `MAX_FORWARD_BODY` hay tải chia khúc)?
3. **Tải clip rồi phát** (3.2-B): cổng và `server.py` (dòng ~3838) đều hỗ trợ `Range` (byte), nhưng cửa sổ `chapterClip` tính theo *thời gian*, nên không đổi được sang byte nếu audio nén (không có bảng chỉ mục) **[chưa chắc định dạng]**. Đề xuất: tải cả chương (có `Range` để tiếp tục khi rớt), cache tối đa 50 MB, dọn khi đóng màn. Chương dài (≈ 60 MB) cần chủ sách chấp nhận hoặc cắt theo cửa sổ ở máy tính (thêm tham số — việc §9).
4. **Danh sách `choices` của `WorkItem` với `unnamed` (rất nhiều câu)**: chọn câu trong `SheetPages` có đủ dễ không? Cần thử với một sách thật.
5. **Một thẻ mỗi lần hay danh sách?** Thiết kế chọn bộ bài; nếu người duyệt muốn nhìn tổng, thêm "Xem tất cả" (danh sách thẻ) — chưa làm.
6. **Hoàn tác 15 s mà người dùng thoát app**: chấp nhận mất (4.4). Nếu không, phải có hàng đợi bền (WorkManager).
7. **Mẫu thiết lập** (`book-templates`): web dùng "đặt lại/đổi tên/xoá" ở nhiều chỗ; bản điện thoại gom ở `SheetPages` cấp 2 — chưa đối chiếu hết mọi nhánh của `NewProjectScreen` (2.049 dòng). Cần một lượt đối chiếu khi bắt tay S4.
8. **`/api/app.studio.installed/outdated/damaged`**: điện thoại nên báo "Máy tính chưa cài Studio" hay giấu hẳn? Web hiện nói rõ và chỉ chỗ cài; đề xuất giữ lời đó (không hành động được từ điện thoại).

### 13.1 Lead quyết (30-10)

1. Sửa `ProductionSource` / `SyncLink` nhận mảng JSON trước S1, một commit riêng, có test JVM (không cần máy thật để xác nhận: đọc mã + test đủ).
2. Trần tải lên: để tới S4; điện thoại báo rõ giới hạn thật (~17 MiB một tệp) thay vì hỏng giữa chừng. Đổi phía máy tính do Lead quyết sau.
3. Nghe lại: tải cả chương một lần vào cache (nối lại được), phát cửa sổ thời gian tại chỗ; không đổi phía máy tính.
4. `unnamed` nhiều câu: `SheetPages` có danh sách cuộn + ô chọn, đủ cho S2; đo lại với sách thật khi có.
5. Giữ bộ bài; "Xem tất cả" chưa làm.
6. Chấp nhận mất hoàn tác khi app chết; không hàng đợi bền.
7. Theo đề xuất; đối chiếu đủ ở S3.
8. Giữ lời giải thích như web (không giấu Studio).
Mảng trả về từ máy tính: không bọc lại; điện thoại nhận mảng.
