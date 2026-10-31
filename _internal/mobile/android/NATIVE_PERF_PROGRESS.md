# Native phone UI - hiệu năng đổi tab - tiến độ

Cây: ABook_native, nhánh dev/native1 (HEAD 42f7d70c = P1a). Không commit. Máy đo: OPPO CPH2121 (Android 12, 60 Hz), gói thử com.ngdtuanh.abook.dev.
Mục tiêu NATIVE_PHONE_UI.md §1: không khung > 16,7 ms, p95 <= 8 ms phía app. Mọi số: 60 sách giả, 18 lần chạm ba tab trong 15 s (S/native_trace.sh).

## Bước 1 - cái gì chậm khi đổi tab (XONG)
- Cờ `-PcomposeTrace` (app/build.gradle + variables.gradle): thêm runtime-tracing 1.11.4 + tracing-perfetto 1.0.1 vào bản đang dựng; bật bằng
  `am broadcast -a androidx.tracing.perfetto.action.ENABLE_TRACING -n <gói>/androidx.tracing.perfetto.TracingReceiver` + nguồn dữ liệu `track_event` trong cấu hình Perfetto
  (S/pf_trace.sh, COMPOSE_TRACE=1). Không cờ thì không có gì thay đổi (APK +13 MB khi có cờ, chỉ để soi).
- Bằng chứng: trong MỌI khung chậm lúc trượt không có một lát composition nào (RootTabs / LibraryScreen chỉ dựng lại ở khung chạm, 1-4 ms). Thời gian nằm ở
  `AndroidOwner:measureAndLayout` (8-16 ms) + `AndroidOwner:draw` (7-12 ms) của khung ĐẦU tiên Thư viện lộ ra - lặp lại ở MỌI lần vào Thư viện (cứ 3 lần chạm, đúng
  lượt chạm vào tab 0), giảm dần theo thời gian (16 -> 11 -> 10 -> 8 -> 7,6 ms qua 5 lần) = mã lạnh bị thông dịch rồi JIT dần, không phải dựng lại.
- Gốc 1: không có AOT. Mỗi lần "đặt lại" cây Thư viện chạy mã dàn trang/vẽ chỉ chạy một lần mỗi lượt chạm -> không bao giờ nóng đủ để JIT, nên thông dịch mãi (bước 2 sửa).
- Gốc 2: TabHost chỉ ĐẶT tab đang lộ (low..high). Tab ra khỏi vùng đặt rồi vào lại = cả cây của nó bị đánh dấu đặt lại + vẽ lại (kể cả đã AOT: layout 2 ms + draw 3 ms
  mỗi lần vào Thư viện). Sửa: đặt MỌI tab đã dựng, tab ngoài màn nằm ngoài vùng cắt (HWUI bỏ qua); ẩn khỏi trợ năng bằng `hideFromAccessibility` đọc trạng thái trong khối semantics.
- Thử rồi bỏ: kết cấu GPU (`CompositingStrategy.Offscreen` lúc trượt): GPU t_gpu 3 -> 4,7 ms (blit hai kết cấu toàn màn đắt hơn vẽ lại trên GPU MediaTek), khung đầu +30 ms (flush layers). Đã gỡ.

## Bước 2 - baseline profile + cài bằng .dm (XONG)
- Máy ảo mới `abook_bp_api34` (google_apis_playstore x86_64, API 34, cổng 5584, adb -P 5038 qua ANDROID_ADB_SERVER_PORT; KHÔNG đụng emulator-5554). Gradle cần
  `ANDROID_SERIAL=emulator-5584 ANDROID_ADB_SERVER_PORT=5038` (serial dạng host:port làm UTP hỏng vì dấu ":" trong tên file) và
  `-Pandroid.testInstrumentationRunnerArguments.androidx.benchmark.suppressErrors=EMULATOR`:
  `gradlew :app:generateBaselineProfile` ~14 phút, ra app/src/release/generated/baselineProfiles/{baseline,startup}-prof.txt (19.5k dòng mỗi file).
- `baselineprofile/.../BaselineProfileGenerator.kt` viết lại: chờ dựng trước ba tab, cuộn lưới, 3 vòng x 6 lần đổi tab (kề và nhảy cách), trang sách, bảng bộ nhiều tập,
  menu Xếp theo, ô Tìm, bảng Thêm sách, mỗi bước thiếu phần tử thì bỏ qua.
- AGP tự sinh .dm cho APK benchmarkRelease (app/build/outputs/apk/benchmarkRelease/baselineProfiles/0 = API 31+, 1 = API 28-30; trong đó primary.prof + primary.profm).
  Cài: `adb install-multiple -r app.apk app.dm` (đặt tên cùng gốc: app.apk / app.dm) -> `dumpsys package ... Dexopt state`: `[status=speed-profile] [reason=install-dm]` (trước đó `verify`).
- Cài thường (`adb install`) vẫn không AOT trên ColorOS; người dùng thật dùng Play (bundletool đưa .dm) hoặc profileinstaller + bg-dexopt.

## Bước 3 - bộ nhớ đệm shader (XONG)
- HWUI GIỮ bộ nhớ đệm shader qua các lần mở: lần mở nguội thứ hai chỉ còn 4 lát shader_compile tổng 5-6 ms (cache_hit), không còn cache_miss 75-80 ms.
  Chỉ lần chạy ĐẦU sau khi cài mới compile 46-80 ms (rơi vào khung trượt đầu). Chưa làm khởi động ấm shader: một lần mỗi máy, lợi ít, chưa đo ra lợi.
- Còn lại ở khung trượt đầu tiên của mỗi lần mở: RenderThread `flush commands` 19 ms (tải ảnh chữ lên kết cấu: Studio / Cài đặt vẽ lần đầu).

(Bước 4 - số đo, bước 5 - test: xem cuối file.)

## Bước 4 - số đo (OPPO, 60 sách giả, 18 chạm, trung vị [min-max]; script S/pf_cycle.sh, S/final.py; trace trong S/ntrace/{before_,bp1_,fin_,fin2_}N)
| bản | số lượt | janky % (gfxinfo) | main p95 ms | main > 16,7 ms | App Deadline Missed |
|---|---|---|---|---|---|
| trước (P1a, JIT, `install`) | 6 | 4,8 [3,4-10,6] | 11,1 [7,5-16,0] | 5 [3-7] | 5 [3-5] |
| chỉ AOT (mã P1a + .dm) | 7 | 4,1 [0,7-7,7] | 5,7 [3,2-14,2] | 1 [1-2] | 1 [0-2] |
| cuối (AOT + mọi tab luôn được đặt) | 10 | 1,0 [0-4,3] | 2,7 [2,6-4,1] | 1 [0-2] | 1 [0-1] |
- main = Choreographer#doFrame luồng chính; p50 4,6 -> 2,2 -> 2,4 ms. bản cũ (đã gỡ ở P4) (Lead đo): janky 4,1 %, p50 12, p90 20, p99 34 ms.
- gfxinfo p50/p90 cuối: 8 [8-9] / 16 [15-30] ms (trước 11 / 22).
- Khung còn > 16,7 ms: đúng 1 khung mỗi lần mở app = lần trượt ĐẦU TIÊN: RenderThread `flush commands` 20-23 ms (4 shader cache_hit ~1 ms mỗi cái, tải kết cấu chữ 492x79,
  driver tạo pipeline), luồng chính chờ đồng bộ. Không có trong lượt sau của cùng tiến trình.
- Phần "janky" còn lại của gfxinfo là hệ thống: frametimeline chỉ có 0-1 "App Deadline Missed" mỗi lượt; còn lại Buffer Stuffing / Prediction Error / SurfaceFlinger
  Scheduling, RenderThread chờ dequeueBuffer / queueBuffer 14-20 ms dù t_gpu chỉ 3 ms (cùng hiện tượng với thư viện rỗng - Lead đã thấy). Biến thiên giữa lượt tốt / xấu không
  tương quan với t_gpu (cùng 2,7-3,0 ms ở lượt 0,7 % và 7,7 %).

## Bước 5 - test
- `:app:testDebugUnitTest`: 1883 test, 0 lỗi, 7 bỏ qua (JUnit XML), exit 0. MotionScanTest + TextCutScanTest xanh. Thêm test ở TabHostTest (tab ngoài màn ẩn khỏi trợ năng, mọi tab đã
  hiện ở lại trong cây). Không đổi hình nên không ghi lại ảnh Roborazzi.
