# Giao diện điện thoại native

Chủ sách 26-10: "tôi không cần biết bạn dùng nền tảng gì để code. tôi chỉ quan tâm nó phải nhanh, nhẹ, tốn ít ram. hiệu năng
phải cực nhanh, thậm chí là thừa thãi hiệu năng. đừng có lười mà dùng mấy phương pháp port code vớ vẩn".

Giao diện điện thoại hiện là React trong WebView (Capacitor). Đo trên OPPO CPH2121 (26-10, app mở nền): tiến trình app 140 MB PSS
(232 MB RSS) + tiến trình vẽ WebView riêng ~154 MB RSS. Khựng là trần của WebView: dàn trang cả cây trên một luồng, chụp tài liệu
70-140 ms cho mỗi chuyển cảnh, Đang nghe ~120 thành phần dựng hơn 100 ms. Lõi (phát, thư viện, xuất, nhạc nền, đọc máy) vốn đã là
Kotlin. Việc này: viết lại GIAO DIỆN bằng Kotlin + Jetpack Compose trên lõi ấy, rồi gỡ hẳn WebView, Capacitor và gói web khỏi APK.

Không bọc, không chuyển mã tự động, không màn lai nửa WebView nửa native trong bản phát hành. Logic đang nằm ở TypeScript được viết
lại bằng Kotlin cho đúng nền tảng, mang theo các ca test của nó.

## 1. Ngân sách (tiêu chí chấp nhận, máy đo chặn)

Đo trên OPPO CPH2121 (máy tầm trung của chủ sách), bản release có R8 + baseline profile.

| Chỉ số | Ngân sách | Cách đo |
|---|---|---|
| Mở nguội tới khung đầu có nội dung (Thư viện) | ≤ 500 ms | Macrobenchmark `StartupTimingMetric`, trung vị 10 lần |
| Mở ấm | ≤ 200 ms | như trên, `StartupMode.WARM` |
| Thời gian khung (mọi luồng kịch bản) | p95 ≤ 8 ms, p99 ≤ 12 ms, 0 khung > 16 ms | `FrameTimingMetric` |
| RAM khi đang phát, Đang nghe mở | ≤ 80 MB PSS (một tiến trình) | `dumpsys meminfo` sau kịch bản |
| RAM phát nền, giao diện đã đóng | ≤ 50 MB PSS | như trên, sau `TRIM_MEMORY_UI_HIDDEN` |
| APK release | nhỏ hơn bản WebView cuối | `apkanalyzer` |

Kịch bản đo (module `:benchmark`): mở nguội; cuộn Thư viện 200 cuốn; mở + đóng Đang nghe; bật / tắt Đọc theo; đổi ba tab; vào trang
sách rồi Back; kéo thanh tua; mở bảng tốc độ / hẹn giờ. Vượt ngân sách = không gộp.

## 2. Kiến trúc

- **Một Activity** (`ComponentActivity` + `setContent`). Không Fragment, không WebView, không navigation-compose: ngăn xếp màn tự quản
  (danh sách `Destination` trong một state holder) để mọi chuyển cảnh và Back dự đoán (`PredictiveBackHandler`) do mình điều khiển.
- **Tầng**: lõi sẵn có (`Store`, `Playback`/`PlaybackService`, `BookImport`, `Playlists`, `MusicBed`, `ReadAloud`...) ← kho dữ liệu
  phơi `StateFlow` (`LibraryRepo`, `PlayerRepo` qua `MediaController` của media3, `SettingsRepo`...) ← state holder từng màn ← màn Compose.
- **Plugin Capacitor**: logic nào đang nằm trong thân phương thức plugin (không ở lớp lõi) thì dời vào lớp lõi; plugin chỉ còn là bộ
  chuyển tiếp cho tới khi gỡ. Hai giao diện dùng chung đúng một lõi trong thời gian chuyển.
- **Logic ở TypeScript phải viết lại bằng Kotlin** (kèm ca test cũ): `listen/model.ts`, `labels.ts`, `sleep.ts`, `night.ts`, `format.ts`,
  `cover.ts`, `playlistBed.ts`, `musicBed.ts`, `readAloud.ts` (phần còn ở TS), `bookSearch.ts`, `readings.ts`... Danh sách đủ lập ở P0
  bằng cách lần mọi lời gọi plugin từ `ui/src/android` + `ui/src/listen`.
- **Không DI framework, không reflection lúc mở app**: dựng đồ trong `AbookApplication` bằng tay, lười (`by lazy`).
- **Ảnh bìa**: bộ nạp riêng nhỏ (giải mã thu nhỏ đúng cỡ ô bằng `inSampleSize`, `LruCache` theo byte ~1/16 heap, giải mã ngoài luồng chính);
  không thư viện ảnh.
- **Chữ**: Be Vietnam Pro 400/500/700 trong `res/font`. Màu, cỡ, khoảng cách, bo góc: hằng số Kotlin sinh từ DESIGN.md §5 (một nguồn).

## 3. Quy tắc hiệu năng khi viết Compose

- State là lớp bất biến (`@Immutable`, danh sách `ImmutableList`/`List` không đổi); màn nhận đúng phần state nó vẽ.
- Giá trị chạy theo khung (tiến độ phát, vị trí cuộn, tiến trình chuyển cảnh) đọc trong pha vẽ / dàn trang: `Modifier.graphicsLayer { }`,
  `Modifier.offset { }`, `drawBehind { }` - không đọc trong thân composable (tránh dựng lại mỗi khung). Tiến độ phát là `State<Long>`
  riêng, chỉ thanh tua và đồng hồ đọc nó.
- `LazyColumn` / `LazyVerticalGrid` luôn có `key` + `contentType`. Không cấp phát trong `draw`. `derivedStateOf` cho thứ suy từ cuộn.
- Đọc theo: mỗi đoạn một mục lazy; câu / từ đang đọc tô bằng `drawBehind` trên `TextLayoutResult` của đoạn ấy, không dựng lại cả chương.
- Baseline profile + startup profile (module `:baselineprofile`), R8 full mode. Bật `composeCompiler { reportsDestination }` khi soát độ ổn định.

## 4. Chuyển động (DESIGN.md §5.2, đè lên các dòng "mờ qua" cũ ở đó)

Chủ sách 26-10: "trong các loại chuyển cảnh, loại fade là tôi ghét nhất". Không chuyển cảnh nào chỉ có alpha.

- **Màn con**: vào = trượt từ phải (màn dưới lùi trái 30 %); Back = đúng đường ngược lại, kể cả khi Back dự đoán kéo dở. Mọi cặp tới /
  lui đối xứng (test).
- **Tab đáy**: nội dung trượt ngang theo chiều chỉ số tab; vạch chỉ tab trượt theo.
- **Đang nghe**: `SharedTransitionLayout`. Khung thanh nhỏ nở thành cả màn (`sharedBounds`, cắt bo góc từ góc thanh về 0); bìa, tên chương,
  tên sách, nút phát là `sharedElement` bay riêng (đổi chỗ, đổi cỡ, đổi màu); phần chỉ có ở màn lớn nhô lên + lớn dần từ 40 % tiến trình.
  Vuốt xuống / Back dự đoán kéo ngược đúng đường ấy theo ngón tay.
- **Một nguồn trạng thái phát**: `PlayerRepo` là người nghe `Playback` DUY NHẤT và là chủ đồng hồ duy nhất (`PlayerClock`); thanh nhỏ, trang sách và cửa sổ Đang nghe (`RepoNowPlayingModel`) đều đọc ảnh chụp bất biến của nó, vị trí chỉ đọc trong pha vẽ. Cửa sổ là lớp phủ ở gốc app (trên cả ngăn xếp màn lẫn thanh tab), không phải màn con; thanh phát nhỏ THẬT ở gốc là nguồn của chuyển động nở ra; Back đóng cửa sổ trước mọi màn bên dưới. Menu "Đọc theo" của trang sách nạp cuốn ở trạng thái dừng rồi mở cửa sổ thẳng ở chế độ đọc.
- **Đọc theo là một chế độ của Đang nghe** (chủ sách 26-10: "đọc theo phải là một mode có thể chuyển qua lại như một toggle của cửa sổ
  playing"): bật thì bìa thu về ô nhỏ ở thanh đầu, vùng chữ mở ra tại chỗ, thanh điều khiển giữ nguyên; tắt thì ngược lại. Cùng một cửa sổ.
- **Đổi nội dung tại chỗ** (nhãn nút, số, icon): hình học - chữ cũ trượt lên, chữ mới từ dưới lên (`AnimatedContent` với slide dọc + cắt);
  icon phát / dừng biến hình đường vẽ (path morph), không mờ chéo.
- **Hiện / ẩn khối**: mở / khép chiều cao (`expandVertically` / `shrinkVertically`) kèm trượt; không `fadeIn()` / `fadeOut()` đứng một mình.
- **Gợn chạm**: thu 0,97 khi nhấn; không chấm gợn đọng lại sau khi thả.
- Máy đo: test quét mã nguồn giao diện native, `fadeIn(`/`fadeOut(`/`Crossfade(`/`animateFloatAsState` lên alpha đứng một mình = trượt.
- Giảm chuyển động (hệ điều hành): bỏ bay / trượt dài, giữ chuyển động ngắn ≤ 120 ms.

## 5. Soát giao diện khép kín

- Ảnh chụp mọi màn x mọi trạng thái x sáng / tối bằng Roborazzi (Robolectric, chạy JVM, không cần máy) - thay gallery của bản web.
- Máy dò hình học trên cây semantics trong test: căn giữa theo trục chéo (CROSS CENTER), vùng chạm ≥ 44 dp, chữ không bị cắt "…" ở nhãn
  lựa chọn, một nút chính mỗi màn, nhãn 1-4 chữ.
- Kịch bản bấm thật: test Compose UI (`createAndroidComposeRule`) cho mọi luồng ở DESIGN.md §2, đếm số chạm.

## 6. Giai đoạn

| Giai đoạn | Nội dung | Ra |
|---|---|---|
| P0 | Phụ thuộc Compose, theme từ token, font, ngăn xếp màn + Back dự đoán, bộ chuyển động chung, module `:benchmark` + `:baselineprofile`, script đo RAM; Activity native chỉ bật bằng `-PnativeUi` (bản phát hành vẫn WebView) | khung chạy, số đo khởi động của khung trống |
| P1 | Thư viện (Đang nghe, lưới / danh sách, lọc, xếp, tìm), thanh phát nhỏ, Đang nghe đầy đủ (tua, chương, tốc độ, hẹn giờ, "…") + Đọc theo, thanh tab | so số đo với WebView trên OPPO |
| P2 | Trang sách, Thêm sách / nhập, Sửa sách, Cài đặt, Thiết bị / ghép máy | |
| P3 | Studio từ xa, Xuất (MP3 / M4B), giọng đọc máy, nhạc nền, phần còn lại | danh sách đủ màn = khung `phone/*` của gallery |
| P4 | Gỡ Capacitor, WebView, `ui/src/android`, gói web khỏi APK; bản phát hành native | ngân sách §1 đạt hết |

Trong thời gian P0-P3, bản WebView chỉ nhận sửa lỗi.

Hàng "Sắp có" (SoonRow, MenuRow soon) chỉ là giàn giáo trong lúc làm: chúng đánh dấu việc native chưa làm. Điều kiện của P4 là không còn hàng nào như thế; máy dò sẽ chặn bản phát hành nếu còn.
Mỗi màn native được thiết kế lại cho cách tương tác của điện thoại, không bê điều khiển của bản web sang. Chủ sách 26-10, về nút "Đọc theo" cũ: "đâu phải cứ lấy nút cũ rồi gán vào linh tinh là xong?". Đặc tả mỗi màn phải kê từng điều khiển được giữ lại, đặt ở đâu và vì sao.

## 7. Máy tính

Chủ sách 26-10: "không chỉ bản android mà còn bản window nữa". App Windows cũng bỏ Tauri + WebView2: giao diện native gọi backend
Python qua đúng HTTP API đang có (ranh giới sạch, backend không đổi). Chọn nền bằng thí nghiệm đo cùng một cảnh (lưới 200 bìa, thanh
phát nở thành Đang nghe, tab trượt): Rust + Slint, WinUI 3 (.NET 10), Qt Quick - RAM nghỉ, mở nguội, thời gian khung, cỡ bản phân phối.
Kết quả và lựa chọn ghi vào đây; ngân sách §1 áp tương tự (mở nguội ≤ 500 ms, khung p99 ≤ 12 ms, RAM giao diện nghỉ ≤ 60 MB).

### 7.1 Kết quả đo (26-10, máy chủ sách, GPU đang chạy llama-server) và lựa chọn: Qt Quick

Bản thử và số liệu thô: `D:/Novels/native_desk_proto` (`results/tables_loaded.md`, `readalong_spike.md`, `qt_pacing.md`).

| | Slint 1.x Skia-GL | Qt 6.8.3 Quick | WinUI 3 .NET 10 |
|---|---|---|---|
| Bản phân phối | 17 MB | 34 MB | 272 MB |
| Mở nguội | 364 ms | 354 ms | - |
| RAM riêng (nghỉ / cảnh Đọc theo) | 40-53 MB | 28-40 MB | gấp đôi |
| Khung p50 cảnh nặng | 5,5 ms | 5,6 ms | - |
| CPU mỗi khung, Đọc theo | 3,5 ms | 0,5 ms | - |
| Khung chữ từng dòng cho tô câu / từ | không có API | `QTextLayout` / `positionToRectangle` | - |

- WinUI loại: bản phân phối 272 MB, RAM gấp đôi, NativeAOT văng.
- Slint và Qt hoà về khung và mở nguội. Qt thắng ở Đọc theo: lấy được hình chữ nhật từng dòng chính xác để tô câu và từ, CPU mỗi khung thấp hơn 7 lần, RAM thấp hơn.
- Số Qt 15,5 ms/khung đo trước đó là sai đo: cửa sổ bị một cửa sổ phóng to (Edge) che kín, Windows 11 hạ độ phân giải đồng hồ, Qt 6.8 chuyển bộ dẫn hoạt ảnh sang chế độ đồng hồ. Qt 6.10.3 hết hẳn (5/5 lần 5,6 ms khi bị che). Với 6.8.3 thì tự tắt bằng `SetProcessInformation(ProcessPowerThrottling, IGNORE_TIMER_RESOLUTION)` cho riêng tiến trình.

**Chọn: Qt Quick (QML + C++), Qt ≥ 6.10.3, backend mặc định (D3D11, vòng render luồng riêng, flip model).** Không đặt QSG_RHI_BACKEND, không dùng vòng basic. Liên kết động các DLL Qt (LGPL) và ghi vào THIRD_PARTY. Đo khung luôn ghi cửa sổ trên cùng và bỏ lượt bị che.

### 7.2 Kiến trúc app Windows

- Giao diện: QML cho bố cục và chuyển động, C++ cho mô hình dữ liệu (`QAbstractListModel` cho thư viện / chương / đoạn), ảnh bìa giải mã ngoài luồng chính đúng cỡ hiển thị. Đọc theo vẽ bằng `QQuickPaintedItem` hoặc node scene graph riêng trên `QTextLayout` của từng đoạn, chỉ vẽ lại vùng câu / từ đổi.
- Lõi: backend Python giữ nguyên, nói chuyện qua đúng HTTP API mà app Tauri đang gọi (`_internal/ui/src/studio/api.ts`, `listen/*`). App Qt khởi chạy và giám sát tiến trình backend như vỏ Tauri làm hôm nay.
- Thiết kế: token DESIGN.md (màu, chữ, khoảng, chuyển động §5) sinh ra một `Theme.qml` duy nhất. Luật chung với điện thoại: không fade thuần, Back đối xứng, không cắt chữ người dùng.
- Không bê giao diện web sang: mỗi màn thiết kế lại cho chuột + bàn phím + cửa sổ rộng. Chủ sách 26-10 nhắc với "Đọc theo" trên điện thoại: điều khiển cũ không được gán vào chỗ mới khi cách tương tác đã đổi.
- Thứ tự: D0 khung (cửa sổ, theme, ngăn xếp màn, khởi chạy backend, script đo RAM / mở nguội / khung) -> D1 Thư viện + thanh phát + Đang nghe + Đọc theo -> D2 Trang sách, Thêm / Sửa sách, Cài đặt -> D3 Studio, Xuất, phần còn lại -> D4 gỡ Tauri.

