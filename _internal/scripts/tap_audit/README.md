# Kiểm chạm thật trước phát hành

## Player geometry: sheetgeo

From the task/repository root, one command builds this tree's real gallery and runs Edge:

```text
D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe -X utf8 _internal/scripts/tap_audit/run_sheetgeo.py
D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe -X utf8 _internal/scripts/tap_audit/run_sheetgeo.py --no-build --inject-fault
D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe -X utf8 -m pytest -q -rf _internal/scripts/tap_audit/test_sheetgeo.py
```

Exit 0 = PASS; 1 = FAIL; 2 = Edge missing (pytest skips). `--output PATH` saves full
JSON (default `sheetgeo.json` / `sheetgeo-fault.json` in this task tree). `--no-build`
is only for a gallery just built from the current sources. Edge only; `--edge PATH`
can select its executable. No models, real audio, GPU, owner profile or visible window.

Uses existing `gallery_browser.mjs` launch/CDP/server and `gallery_inspect_sheet.mjs`
catalog replay, geometry probe, native coordinate mouse input, hit-testing and settling.
Phone journeys use the same hit-test with native CDP touch input.
Every width uses an isolated context and the real app, with the existing playing
audiobook and text/speech fixtures. Profiles live under this task root with
`--inprivate --disable-sync --disable-extensions`; cleanup matches their unique
profile path in browser command lines. The node_modules junction is never modified.
If its lucide-react differs from this branch's lockfile, the build downloads the
locked tarball with integrity verification into `.sheetgeo-deps` under this task root.
Only that package is resolved locally; the normal gallery entry/components stay real.

Six windows (390/840/1080/1280/1440/1840×900) cover all **five content-width classes**
after the sidebar. Thresholds are read from `widthClass.generated.ts` (generated from
DESIGN §5.5), not copied into a second policy table.

Player open/close captures raw `getBoundingClientRect()`, computed inset clip,
visible clipped rectangle, ancestor opacity and timestamps every rAF, plus the
same-task first prepaint mutation sample. The existing `nowPlayingMorph.ts` grows
the **clip**, so its raw layout DOMRect intentionally stays full size. Assertions
apply to its visible rectangle: origin ≤3 px, destination ≤0.5 px, monotonic edges
and sizes, ≥3 intermediate rectangles, opacity ≥0.99. A fade/jump alone fails.

In Nghe and Đọc theo, sample frame/header/text column/stage/transport/secondary
controls before, throughout and after opening/closing Tốc độ, Hẹn giờ, Chương
(stacked layout), and Thêm tuỳ chọn. Inline voice/music sections of More are measured
too. Underlay changes over 0.5 px or missing anchors fail. Bottom sheet x/width/height
must stay fixed while y moves monotonically; desktop popovers and inline expansions
only require fixed underlay. Mode switching keeps the player frame within 0.5 px
and confirms the reading element belongs to that player.
The player splits into controls and text from the `large` content class; stacked
layout bounds use computed margins (the scroll box has intentional focus gutters).
The reading text measure must be ≤640 px. Sampling waits for measured boxes and
view transitions to finish and three identical rAFs, with a 2.5s deadline; unrelated
word highlights and toasts cannot hold that geometry deadline open.

`--inject-fault` adds CSS **only in the fixture document**: an open dialog translates
the underlying player column up 32 px over 220 ms. It must fail underlay geometry,
not merely navigation or execution. Pytest launches the normal and injected journeys,
checks every width, and requires an actual geometry failure for the negative control.
Comparator negative cases (fade, jump, reversal, push, missing anchor, horizontal
motion and resize) are in `ui/scripts/sheetgeo.test.mjs`.

## Tap audit

Từ `_internal/ui`, dựng chính cây hiện tại bằng `node node_modules/vite/bin/vite.js build`
(dùng dependency sẵn có). Từ `_internal`:

```text
python scripts/tap_audit/run.py
python scripts/tap_audit/run.py --inject-fault
python -m pytest -p no:cacheprovider -rf scripts/tap_audit/test_tap_audit.py
```

Lượt đầu phải PASS 21/21, exit 0. Đối chứng âm phải FAIL, exit 1: đặt
`pointer-events:none` trên lớp đang mở, gồm cả modal khóa body (lỗi 0.4.134) và popover không modal.
Exit 2 nghĩa là không tìm thấy Edge/Chrome; có thể truyền `--edge PATH`.
`--only "Add book"` lọc theo tên (không khớp thì FAIL), `--json` chỉ in JSON,
`--output report.json` lưu bằng chứng đầy đủ; `--static-dir PATH` đè bản UI.

Mỗi bước mở lớp tạo toast thật qua sự kiện `abook-update-failed` của vỏ, xác nhận toast đã mount,
rồi hit-test điều khiển của lớp trên từng khung chuyển động. `toast never covers a layer control during motion`
phải PASS; không đóng toast để né lỗi. Luật TAP REACH của gallery còn kiểm toaster luôn nằm dưới mọi
dialog / alertdialog / menu / listbox, kể cả story không có thông báo đang hiện.

Server fixture dùng backend của cây chứa script, cổng hệ điều hành cấp và FakeRunner.
Sách/SQLite/preferences giả nằm trong thư mục tạm mới; không chạy model hay tạo audio.
Edge/Chrome headless có profile tạm mới và các cờ riêng tư; kết thúc chỉ thu hồi cây PID
do audit mở, rồi xóa profile và dữ liệu fixture. Giới hạn affinity tối đa bốn CPU logic,
các pool tính toán tối đa bốn luồng, tắt GPU. Trình duyệt vẫn có các luồng quản lý riêng.

Audit dùng CDP để bấm tọa độ bằng chuột và touch, kiểm trusted click, nhập chữ,
đóng lớp, giải phóng khóa body và hit-test nút nền. Không gọi DOM `.click()`.
Control disabled được ghi SKIP_DISABLED. Body `pointer-events:none` của Radix là hợp lệ
khi nút phục hồi hit-testing; ghi mọi tổ tiên `none`, kiểm pointer-events thực của nút và `elementFromPoint`.
Nếu toast tạm che nút trên trang thường, audit chạm ✕ bằng CDP (hoặc chờ hết giờ khi không có ✕),
rồi đo lại; ghi thao tác vào `toastDismissals`. Không đóng hộ toast che điều khiển trong bảng đang mở:
đó vẫn là lỗi vị trí thông báo, phải sửa trong app.

Phạm vi: 21 kịch bản ở mobile 412×915 và desktop 1280×900; hit-test tại tâm
control đang hiện, một probe vô hại mỗi lớp bằng cả chuột/touch. Bước mở lớp trên điện thoại
dùng touch thật; không gọi DOM `.click()`. Ngoài các hộp sách/Studio, kiểm các bảng của màn
Đang nghe (giọng, nhạc, tốc độ, hẹn giờ, chương), menu từng chương,
xoá sách, chọn hồ sơ và bốn popover tương ứng trên máy tính. `probe.expect` xác nhận hiệu ứng
trên UI sau chạm; `touchProbe` chọn thao tác thứ hai, `reopenSteps` mở lại lớp từ màn hiện tại.
Fixture có hai chương, hai hồ sơ, hai giọng giả; mọi yêu cầu tạo audio bị từ chối
trong fixture, không chạy model hay đọc truyện thật. Không chứng minh
Android/WebView vật lý, hộp chọn file native, audio, toàn diện tích chạm hay mọi lớp UI.
Pytest kiểm schema kịch bản, cổng rảnh, phân tích báo cáo và đối chứng chỉ đóng toast trên trang thường;
không mở trình duyệt.
