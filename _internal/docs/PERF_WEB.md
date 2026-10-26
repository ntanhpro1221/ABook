# Hiệu năng web máy tính

Chủ sách: hiệu năng trên hết - nhanh, nhẹ, ít RAM. Tài liệu này giữ cách đo và số trước / sau cho giao diện web của app máy tính
(`ui/src`, chạy trong vỏ Tauri). Đổi gì ở bốn chỗ dưới đây thì chạy lại bài đo và cập nhật bảng.

## Cách đo (lặp lại được)

```text
cd _internal/ui
node scripts/perf_web.mjs --runs 3          # bốn bài đo src/perf/*.perf.dom.test.tsx, in bảng trung vị
node scripts/bundle_report.mjs              # dựng bản máy tính vào thư mục tạm kèm sourcemap, in cỡ chunk + nhóm nguồn
npx vitest run src/perf                     # như trên một lần, test đỏ khi vượt trần số lần vẽ
```

- Bài đo dựng đúng component của app (BookScreen, LibraryScreen, ChapterPanel, ReadAlongText) trong happy-dom với dữ liệu lớn giả: 3000 cuốn,
  2500 chương, chương 40.000 chữ có mốc từng chữ. Trình phát, thư viện, cuốn sách là cửa hàng nhỏ (`src/perf/harness.tsx` `Store`): chỉ
  component đăng ký vẽ lại, như truy vấn / context thật. Cuộn = IntersectionObserver giả báo khối nào vào khung (`FakeIntersections`).
- Số lần vẽ đếm theo tên component qua móc DevTools của React (`src/perf/renderCount.ts`, cùng luật "fiber đã vẽ" với DevTools). Số này
  tất định - là số chính. "Ảnh chuyển cảnh" = số lần MotionRegion chụp lại một vùng DOM để mờ chéo (và số nút trong ảnh).
- Thời gian (ms) là happy-dom + React bản dev trên máy cloud 4 nhân: chỉ để so trước / sau trên CÙNG máy, không phải số của WebView thật
  (WebView nhanh hơn nhiều lần; tỉ lệ mới là thứ đáng tin).
- Số "trước" đo ở `origin/dev/native1` (c5aca867) với cùng `src/perf` chép vào.

## 1. Thư viện 3000 cuốn

| pha | ms trước | ms sau | bìa (BookTile) vẽ lại trước → sau | mọi component trước → sau |
|---|---|---|---|---|
| dựng | 879 | 638 | 116 → 58 | 603 → 352 |
| nhịp đồng hồ (×20) | 0,4 | 1,3 | 0 → 0 | 0 → 0 |
| phát → dừng | 461 | 300 | 58 → 1 | 297 → 51 |
| dừng → phát | 351 | 221 | 58 → 1 | 299 → 53 |
| hỏi lại thư viện (30 giây/lần) | 142 | 113 | 58 → 1 | 299 → 71 |
| lọc "Nghe dở" | 1411 | 1454 | 59 → 1 | 294 → 61 |
| gõ tìm (mỗi phím) | 955 | 871 | 70 → 0 | 354 → 63 |
| cuộn (mỗi khối 60 cuốn) | 283 | 194 | 179 → 57 | 717 → 231 |

Đã sửa:
- `BookTile` nhớ (memo), nhận `current` / `playingHere` / `speaks` thành giá trị; trạng thái trình phát và danh sách giọng đọc lấy MỘT lần ở cấp
  lưới (`useShelfState`), không mỗi bìa một `usePlayer()` + một truy vấn giọng. Hành động (mở, đọc, phát) qua một context cố định
  (`useTileActions`).
- `bookExtras` mặc định là một hằng (`{}` mới mỗi lần vẽ làm mọi bìa thấy context đổi).
- `librarySections` (gom bộ, `seriesIndex` cả thư viện) nhớ theo danh sách; ô bộ sách (`SeriesTile`) nhớ.
- Tìm: chữ đã gấp dấu của từng cuốn nhớ theo đối tượng cuốn (`model.bookMatchesQuery`) - một phím không gấp dấu lại 3000 lần.

Còn lại (cố ý): lọc và gõ tìm vẫn tốn vì vùng kết quả CHỤP lưới (~1200-1500 nút) để mờ chéo / trượt theo tab - chuyển cảnh đã thiết kế, không
đổi. Gõ một phím mà kết quả y hệt vẫn mờ chéo (motionKey có cả chữ tìm); bỏ được nếu chủ sách đồng ý (đổi chuyển động nhìn thấy).

## 2. Trang sách 2500 chương (máy tính)

| pha | ms trước | ms sau | hàng chương vẽ lại trước → sau | mọi component trước → sau | ảnh chuyển cảnh (nút) trước → sau |
|---|---|---|---|---|---|
| dựng | 829 | 635 | 80 → 80 | 2543 → 623 | 0 → 0 |
| nhịp đồng hồ (×20) | 0,1 | 0,2 | 0 → 0 | 0 → 0 | 0 → 0 |
| phát → dừng | 2099 | 404 | 80 → 1 | 1955 → 121 | 1321 → 61 |
| dừng → phát | 1481 | 247 | 80 → 1 | 1955 → 121 | 1301 → 50 |
| tiến độ mới từ máy chủ (mỗi lần) | 569 | 59 | 80 → 1 | 1955 → 121 | 0 → 0 |
| sang chương kế | 547 | 113 | 80 → 2 | 1955 → 127 | 29 → 29 |
| cuộn (mỗi khối 40 chương) | 244 | 88 | 156 → 38 | 3861 → 232 | 0 → 0 |

Đã sửa:
- Hàng chương tách thành `ChapterLine` nhớ (memo), chỉ nhận giá trị của riêng nó (đã nghe bao nhiêu, đang nạp / đang phát, đang thu); việc
  (phát, đọc, đánh dấu, đổi tên) qua một đối tượng cố định `useChapterActions`. Trước đây mỗi hàng `usePlayer()` và nhận cả `book`: phát / dừng
  hay cuốn được hỏi lại là vẽ lại mọi hàng đang dựng.
- Menu "…" của hàng (Radix, ~20 component mỗi hàng) dựng lười: nút trơn cùng hình, cùng `aria-haspopup` / `data-state` cho tới khi rê chuột,
  Tab vào (tiêu điểm giữ ở nút, Enter / Space / ↓ như cũ) hay bấm thẳng (mở ngay) - `ChapterMenu`, test `listen/chapterMenu.dom.test.tsx`.
- `MotionRegion.contentSignature`: dấu nội dung từng đi qua cả dữ liệu cuốn sách trong props (chuỗi 3,5 triệu ký tự, hai lần mỗi lần trang vẽ
  lại). Giờ mỗi nhánh là một mã băm 53 bit, nhớ theo đối tượng (WeakMap) - cùng phép so bằng.
- Cột nút của đầu trang là vùng chuyển cảnh riêng: đổi nhãn nút chính ("Tạm dừng" / "Nghe tiếp · …") không còn làm vùng cả trang chụp lại
  1300 nút DOM rồi bỏ đi (nhãn nằm trong vùng riêng của `Button`, vùng cả trang không mờ). Thay đổi khác trong cột ấy giờ mờ chéo đúng cột,
  không cả trang (DESIGN 5.2: đổi nội dung tại chỗ, đúng vùng).

Bảng "Chương" của màn Đang nghe (`ChapterPanel`, cùng 2500 chương):

| pha | ms trước | ms sau | mọi component trước → sau |
|---|---|---|---|
| phát → dừng | 49 | 25 | 100 → 3 |
| tiến độ mới (mỗi lần) | 31 | 8 | 101 → 2 |
| sang chương kế | 55 | 38 | 101 → 5 |

Hàng tách thành `PanelChapterRow` nhớ (trước đây là JSX trong vòng lặp: mọi hàng cùng hai MotionRegion của nó vẽ lại mỗi lần).

## 3. Đang nghe + Đọc theo, chương 40.000 chữ (2667 câu, 889 đoạn, 6774 nút DOM)

| pha | ms | đoạn vẽ lại | mọi component |
|---|---|---|---|
| dựng | ~1100 | 889 | 1463 |
| nhịp đồng hồ trong câu (chữ đang đọc đổi) | 1,6 | 0 | 2,5 (LitWords + 2 Word) |
| sang câu kế | 11 | 1,3 | 21 |
| nhảy xa (câu 100 → 2000) | ~380 | 631 | 1042 |
| chọn / bỏ chọn câu | 3-20 | 1 | 4 |

Không cần sửa: đồng hồ đã tách khỏi context trình phát (`listen/clock.ts`), đoạn và nhóm đoạn đã nhớ (`ReadAlongText` Chunk / Paragraph), chữ
đang đọc chỉ vẽ lại hai `Word`. Nhảy xa vẽ lại đúng các đoạn vừa thành "đã nghe" (nhạt đi) - không thừa. Bài đo giữ trần cho cả ba.

## 4. Bundle (vite build, bản máy tính)

| | trước | sau |
|---|---|---|
| trang đầu (JS + CSS phải tải trước khi vẽ) | 1639 KB, gzip 486 KB | 1257 KB, gzip 385 KB (−23 % / −21 %) |
| chunk JS | 2 (một khối 1511 KB) | 14 |
| mọi JS | 1532 KB, gzip 465 KB | 1551 KB, gzip 489 KB |

Tải lười (`shared/lazyScreen.tsx` `lazyComponent`, nạp sẵn lúc rảnh 1,5 giây sau khi app vẽ - `preloadWhenIdle`, nên bấm sang vẫn tức thì;
chunk đã về thì dựng thẳng, không qua Suspense):
- Studio: `ProjectsScreen`, `NewProjectScreen`, `ProjectScreen` (kèm ScriptTab, WorkInbox, MusicTab, ExportBook, ReviewQueue, NameReadings…).
- Cài đặt (cả Thiết bị, Giọng đọc, Nhạc của tôi): `SettingsScreen`.
- Hộp "Sửa câu này" của trang đọc (`LineWishDialog`, kéo các bảng chọn của tab Kịch bản).

Để chúng tách được, các thứ nhỏ mà màn chính cần được đưa khỏi mô-đun lớn: `PICK_SOURCE` → `studio/pickSource.ts`, lời mời duyệt trước khi
thu → `studio/precastInvites.ts`, công tắc → `desktop/Switch.tsx`, ý muốn chờ Studio + dấu cạnh câu → `listen/lineWishData.tsx`,
`isOpenWork` đọc thẳng từ `studio/precast`.

Nhóm lớn nhất còn ở trang đầu: react-dom 203 KB, PlayerViews 57, react-router 36, query-core 32, sonner 33, player 33, BookScreen 32,
readAloud 31, lucide 28, tailwind-merge 27.
