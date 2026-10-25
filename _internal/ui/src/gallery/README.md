# Phòng trưng bày màn hình (chỉ dùng khi phát triển)

Xem và chụp **mọi màn + trạng thái** của app (Nghe trên điện thoại, Nghe + Studio trên máy tính) mà không cần server Python
hay điện thoại thật. Mỗi mục là **cây thật của app** (`android/App.tsx`, `desktop/App.tsx`) chạy trên dữ liệu giả.
Không thuộc bản dựng phát hành: `vite.config.ts` / `vite.android.config.ts` không biết tới `gallery.html`.

## Chạy

```text
cd _internal/ui
npm run gallery                 # vite dev, mở http://localhost:5174/gallery.html#/
npm run gallery:build           # dựng tĩnh ra ui/dist/gallery (dist/ bị .gitignore bỏ qua)
npm run gallery:shots -- --browser "C:/Program Files/Google/Chrome/Application/chrome.exe" --out ../../shots
```

URL:

| URL | là gì |
|---|---|
| `gallery.html#/` | mục lục mọi mục, nút Sáng / Tối |
| `gallery.html#/phone/library-full?theme=dark` | khung xem một mục: app trong iframe đúng khổ (điện thoại 412×915, máy tính 1440×900), Trước / Sau |
| `gallery.html?frame=phone/library-full&theme=dark` | chỉ app, chiếm cả cửa sổ - trang script chụp mở; tự đặt cửa sổ đúng khổ |

Trang khung báo ra `window.__gallery = { ready, errors, missing, known }`: `ready` khi app đã dựng, thao tác của mục đã chạy và trang
thôi chuyển động; `missing` là đường API / phương thức native mà dữ liệu giả chưa có (trả rỗng / 404); `known` là cảnh báo bản dev
của chính app (xem dưới).

## Chụp ảnh: `scripts/gallery_shots.mjs`

Mở Chrome / Edge headless qua CDP (WebSocket có sẵn của Node 22 - không thêm thư viện), cờ `--headless=new --no-first-run
--user-data-dir=<tạm> --disable-extensions` (thêm `--no-sandbox` khi chạy dưới root trên Linux). Không có `--base` thì tự phục vụ
`dist/gallery` (nhớ `npm run gallery:build` trước); có `--base http://localhost:5174/gallery.html` thì chụp từ `npm run gallery`.

```text
node scripts/gallery_shots.mjs --browser PATH --out DIR [--only phone/library,desktop/studio] [--theme light|dark|both] [--scale 2]
```

Mỗi mục: đặt khổ (điện thoại: `mobile` + màn cảm ứng thật cho CSS `pointer: coarse`, tỉ lệ 2; máy tính: tỉ lệ 1), múi giờ
Asia/Ho_Chi_Minh, `prefers-color-scheme` theo chủ đề, chờ `__gallery.ready`, chờ phông chữ và mọi chuyển động hữu hạn chạy xong,
chụp `<platform>__<tên>-<chủ đề>.png`. Ra kèm `index.html` (lưới ảnh theo nhóm, ghi lỗi dưới ảnh) và `report.json`. Mã thoát 1
khi có mục lỗi.

## Soi chi tiết: `scripts/gallery_inspect.mjs`

```text
npm run gallery:build
npm run gallery:inspect -- --browser "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --out ../../inspect --theme both
node scripts/gallery_inspect.mjs --out ../../inspect --fail-on rule1,rule2,rule3
node scripts/gallery_inspect_fixture.mjs --out ../../inspect/skip-fixture
```

Mặc định quét cả hai chủ đề. Cùng cờ `--browser`, `--out`, `--only`, `--theme`, `--base`, `--dist`, `--timeout` với công cụ chụp;
dùng chung `scripts/gallery_browser.mjs` (máy chủ loopback, CDP, Edge riêng tư, dọn hồ sơ tạm bằng Python sau khi đóng trình duyệt).
Không cần thêm dependency. Chờ phông app tải và chuyển động hữu hạn kết thúc; spinner vô hạn được giữ khung rồi huỷ, có ghi vào JSON.

Bảy quy tắc: chữ đè hình, chữ đè chữ, chữ bị cắt, chữ dưới 11 CSS px, vùng bấm điện thoại dưới 44×44, tương phản WCAG,
và SVG không nhất quán trong cùng hàng flex. Chữ lấy từng dòng bằng `Range`, bỏ phần khuất/`sr-only` và các lớp dialog/menu/tooltip
khác nhau; tính vùng bấm cả pseudo và nhãn checkbox; chữ trên ảnh/gradient không chấm tương phản.
Vùng chồng lớp có chủ ý phải có `data-overlay` trên tổ tiên chung của chữ và hình, kèm lý do bằng tiếng Việt; không miễn cả trang.

Ra `findings.json` (phát hiện, rect CSS, phông thực nạp, vùng bấm, tỉ lệ tương phản, lỗi chạy), `index.html` nhóm theo quy tắc rồi story,
`contacts/*.html` chứa mọi điều khiển/SVG nhìn thấy, và `crops/*.png` qua CDP `clip.scale=4`, lề 8 CSS px.
Ảnh điện thoại @2x có 8 điểm ảnh/CSS px sau phóng 4 lần; máy tính @1x có 4. Mở ảnh gốc hoặc bật nguyên cỡ trên bảng chi tiết.
Đây là bộ tìm ứng viên: SVG khác mục đích/độ ưu tiên và chữ disabled vẫn có thể cần được loại khi duyệt ảnh.

`--fail-on` nhận tên quy tắc (tên có dấu cách cần quote), dạng gạch dưới/gạch nối hoặc `rule1`…`rule17`;
mặc định chặn các quy tắc đã kiểm sạch trong `DEFAULT_FAIL_ON`, dùng `--fail-on none` để chỉ báo cáo.
Mã thoát 1 khi có quy tắc được chọn vi phạm. Lỗi tải story/chụp ảnh là 2, luôn ghi riêng để không tạo lượt xanh giả.
Quy tắc 16 `FOCUS RING CLIPPED`: vòng 2 px + offset 2 px, dung sai hình học 0,5 px; bỏ điều khiển cuộn khuất một phần,
tôn trọng `overflow-clip-margin` của `overflow:clip`. Quy tắc 17 `CORNER MISMATCH`: góc lớp phủ tuyệt đối trùng góc hộp bo trong 1 px,
bán kính đã co theo CSS nhỏ hơn quá 1 px, không có tổ tiên cắt theo cùng góc bo. Fixture `focus-corners.html` kiểm cả markup cũ và wrapper mới.
Fixture riêng dựng lại glyph HTML của `0bec019f` cạnh SVG mới `398db035`, dùng phông gallery thật và chính bộ đo trên Edge;
không checkout/sửa component sản phẩm. Có unit test hình học và DOM ở `scripts/gallery_inspect.test.mjs`.

## Cách giả (dữ liệu và nền tảng)

| phần | file | cách |
|---|---|---|
| đồng hồ | `clock.ts` | `Date` bắt đầu ở 21:15 thứ Bảy 24-10-2026 (giờ VN) rồi chạy tiếp; mục đặt được giờ riêng (`clock`) |
| thư viện | `data.ts` | 11 cuốn tiếng Việt tự đặt tên, văn bản tự viết: bộ 3 tập "Thành Phố Sương Mù" (tập 2 nghe dở), vài cuốn nghe dở, một cuốn đang làm, một cuốn tạm dừng vì chạy pin, một cuốn chỉ có chữ, một cuốn trên máy tính (nghe thẳng), một cuốn chưa có chương nào |
| máy chủ máy tính | `desktopApi.ts` | thay `fetch`: `/api/...` đi vào bảng đường, trả JSON cùng hình dạng `abook/webui/server.py` |
| điện thoại | `capacitor.ts`, `phoneNative.ts` | `window.Capacitor.PluginHeaders` như lõi native tự gắn → `@capacitor/core` gọi `nativePromise` / `nativeCallback` vào bản giả của EbookPlayer / EbookLibrary / ReadAloud / App. Tên phương thức đọc thẳng từ `android/plugins.ts`. Lệnh sửa sách (`EbookLibrary.studio`) đi vào cùng máy chủ giả |
| `<audio>` | `fakeAudio.ts` | máy tính: `Audio` giả - có độ dài chương, không phát tiếng, thời gian đứng yên (ảnh "đang phát" giống nhau) |
| cảm ứng | `boot.ts` | điện thoại: `matchMedia("(pointer: coarse)")` đúng |

**Không sửa dòng nào của mã app**: mọi thứ giả ở ranh giới trình duyệt (fetch, Audio, matchMedia, Date) và cầu Capacitor.

## Thêm một mục

Thêm một dòng vào `PHONE` hay `DESKTOP` trong `entries.ts`:

```ts
{ id: "phone/book-history", group: "Trang sách", title: "Tab Lịch sử nghe", route: "/book/suong-mu-2",
  scenario: { library: "full" }, act: () => click("Lịch sử").then(() => undefined) },
```

- `id`: phần sau `#/`, ổn định (là tên file ảnh). Tiền tố `phone/` hay `desktop/`.
- `route`: trang của app (router hash của app).
- `scenario` (`state.ts`): thư viện `full | empty | loading | error`, `paired`, `night` (thẻ "Tối qua"), `playing`, `projects`.
- `act` (`actions.ts`): bấm như người dùng - `click(nhãn | RegExp)` tìm nút theo `aria-label` / `title` / chữ, `type(nhãn, chữ)`, `see(chữ)`.
- Màn cần dữ liệu mới: thêm đường vào `ROUTES` của `desktopApi.ts` (hay phương thức vào `phoneNative.ts`), hình dạng theo
  kiểu TS mà màn ấy đọc. Chạy mục; `__gallery.missing` (và test) nói còn thiếu gì.

Test (`gallery.phone.dom.test.tsx`, `gallery.desktop.dom.test.tsx`, chạy cùng `npx vitest run`) dựng lần lượt mọi mục bằng happy-dom và
đòi: không `console.error`, không lỗi không bắt, thao tác của mục chạy hết, không gọi đường / phương thức chưa giả.

## Giới hạn đã biết

- Xem trong trình duyệt máy tính: CSS `@media (pointer: coarse)` của điện thoại không áp (chỉ phần JS được giả); ảnh của
  `gallery_shots.mjs` thì đúng vì nó giả lập màn cảm ứng.
- Cảnh báo bản dev của chính app, ghi vào `known`, không tính là lỗi của mục (`run.ts` `KNOWN_DEV_WARNINGS`):
  React Query "No queryFn" (`listen/player.tsx` đọc bộ đệm bằng `useQuery({ enabled: false })` không kèm queryFn) và `<div>` trong
  `<p>` ở màn Đang nghe (`listen/PlayerViews.tsx`: TrackSubtitle nằm trong `<p>`).
- Chưa có: trình tạo sách Studio bước 2-4 (cần quét thư mục thật `/api/scan`), ghép điện thoại / máy tính khác, xuất file đang chạy,
  nhạc nền có rãnh nhạc (danh mục nhạc trực tuyến).
