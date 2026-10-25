# ABook - Hệ thiết kế

Chuẩn cho mọi màn của app máy tính và app điện thoại. Mục tiêu của chủ sách: **tối giản nhưng sang trọng, hợp lý, đủ tính
năng, chuyển động mượt** - và **luồng sử dụng được thiết kế hẳn hoi**. Thứ tự làm: luồng (mục 2) -> kiến trúc thông tin
(mục 3) -> nguyên tắc + token (4, 5) -> thành phần (6) -> từng màn (7). Sửa giao diện mà không khớp tài liệu này thì sửa
tài liệu trước (có lý do), không lệch âm thầm.

Ảnh hiện trạng: `npm run gallery:build` rồi `npm run gallery:shots` (`ui/src/gallery/README.md`) - mọi màn, mọi trạng thái,
sáng và tối. Mỗi thay đổi giao diện kèm ảnh trước/sau của các mục bị ảnh hưởng.

## 1. Người dùng và việc chính

Một người nghe sách nói tiếng Việt, chủ yếu trên điện thoại, đôi khi trên máy tính; sách là file của họ (EPUB, TXT, DOCX,
PDF) hoặc sách nói `.abook`. Máy tính có thể dựng sách nói bằng Studio (lâu, chạy nền). Việc theo tần suất:

1. **Nghe tiếp** cuốn đang nghe (mỗi ngày, nhiều lần) - phải nhanh nhất.
2. Điều khiển khi đang nghe: tua, chương, tốc độ, hẹn giờ ngủ, đọc theo chữ.
3. Chọn cuốn khác trong thư viện.
4. Thêm sách (file mới, hay sách từ máy kia).
5. Tạo sách nói từ truyện (Studio) và theo dõi tiến độ; sửa cách đọc / ai nói khi cần.
6. Cài đặt (hiếm).

Hệ quả: màn đầu tiên là thư viện với "nghe tiếp" một chạm; trình phát là lớp luôn sẵn; Studio và Cài đặt lùi về sau.

## 2. Luồng sử dụng (đích, đếm số chạm từ màn mở app)

Mỗi luồng có: điểm vào, các bước, số chạm đích, trạng thái rỗng/lỗi. Đổi giao diện mà làm một luồng dài thêm là lùi.

| # | Luồng | Đích | Các bước |
|---|---|---|---|
| L1 | **Lần đầu mở** -> nghe được | ≤ 4 chạm | Thư viện trống: một lời mời "Thêm sách" (nút chính) + dòng phụ "Có máy tính? Nối máy" -> chọn file -> hộp xác nhận (tên, bìa đoán sẵn; chỉ hỏi khi thật cần) -> trang sách -> "Nghe ngay" (đọc máy) hay "Tạo sách nói" (Studio, máy tính) |
| L2 | **Nghe tiếp** | 1 chạm | Đầu Thư viện: hàng "Đang nghe" (bìa, tên, chương, còn bao lâu, nút phát). Thanh phát thu nhỏ luôn ở đáy mọi màn |
| L3 | Mở trình phát | 1 | chạm thanh phát thu nhỏ -> trình phát trượt lên; vuốt xuống / Back để thu |
| L4 | Nhảy chương | 2 | trình phát -> "Chương" -> chạm chương |
| L5 | Hẹn giờ ngủ / tốc độ | 2 | trình phát -> nút -> chọn mức (bảng trượt, Back đóng) |
| L7 | Đọc theo chữ | 1 | trình phát -> "Đọc theo"; thanh điều khiển tự mờ khi đọc, chạm hiện lại |
| L8 | Chọn cuốn khác | 2 | Thư viện -> chạm bìa (vào trang sách) -> "Nghe" ; hay chạm giữ bìa -> phát ngay |
| L9 | Sách ở máy kia | 2 | máy đã ghép: sách máy kia nằm NGAY trong Thư viện (dấu nhỏ "Trên máy tính"), chạm là nghe (stream) hay tải; chưa ghép: Cài đặt > Thiết bị > Nối máy (một lần) |
| L10 | Tạo sách nói (máy tính) | ≤ 3 | Studio -> "Dự án mới" -> chọn file -> "Bắt đầu" (một trang; giọng, chất lượng, cách bắt đầu chọn sẵn theo mặc định tốt, gập dưới "Tuỳ chọn"; chỉnh được nhưng không bắt chỉnh) |
| L11 | Theo dõi / can thiệp Studio | 1 | tiến độ ở thanh bên (máy tính) và ở Studio (điện thoại ghép); "Việc cần bạn" chỉ hiện khi có, không chặn dây chuyền |
| L12 | Sửa cách đọc / ai nói | 2 | đang đọc theo -> chạm giữ câu -> sửa -> ghi vào hàng chờ Studio (mọi player đều sửa được) |
| L13 | Cài đặt | ≤ 2 cấp | Cài đặt -> nhóm -> mục. Không cấp ba |

Trạng thái chung cho mọi luồng: **đang tải** = khung xám mờ đúng hình nội dung (không xoay vòng giữa màn); **rỗng** = một
câu + một nút dẫn tới việc tạo nội dung; **lỗi** = tại chỗ, một câu nói cách sửa + "Thử lại"; **mất mạng** = dải mảnh đầu
màn, nội dung đã có vẫn dùng được. Không bao giờ hộp thoại chặn cho lỗi không cần quyết định.

## 3. Kiến trúc thông tin

Hai nền tảng cùng một mô hình; khác nhau ở bố cục, không ở chỗ để đồ.

- **Thư viện** - mọi cuốn nghe được: file trên máy này + sách của máy đã ghép (một danh sách, dấu nguồn nhỏ). Thêm sách
  ở đây. Trang sách là tầng con.
- **Studio** - dự án tạo sách nói. Máy tính: đầy đủ. Điện thoại: Studio từ xa khi đã ghép máy tính; chưa ghép thì thẻ
  Studio giải thích một câu + "Nối máy tính".
- **Cài đặt** - gồm cả Thiết bị (ghép máy, chẩn đoán).
- **Trình phát** - lớp nổi trên mọi màn (thu nhỏ / đầy đủ), không phải một tab.

Điện thoại: thanh tab đáy 3 mục **Thư viện · Studio · Cài đặt** (bỏ tab "Tải sách": sách máy kia vào Thư viện, ghép máy vào
Cài đặt > Thiết bị, nút Studio vào tab Studio). Máy tính: thanh bên **Thư viện · Studio** (+ danh sách dự án đang chạy rút
gọn dưới Studio) và **Cài đặt** ở đáy; không nhóm tiêu đề "NGHE / STUDIO" thừa.
Tab đang mở của thanh tab đáy điện thoại: icon + chữ hổ phách (quy ước nền tảng). Mọi điều hướng khác theo mục "Điều hướng" ở §6.

## 4. Nguyên tắc

1. **Một việc chính mỗi màn** - đúng MỘT nút chính (nền hổ phách). Còn lại là phụ.
2. **Khoảng trắng thay khung** - không thẻ/viền/bóng quanh nhóm trừ vật thể độc lập (bìa, thanh phát, hộp thoại, bảng
   trượt, menu). Nhóm bằng khoảng cách + tiêu đề nhỏ. Không thẻ lồng thẻ.
3. **Tiết lộ dần** - hiện 3-5 điều khiển hay dùng; còn lại vào "Thêm" (…) đặt CÙNG hàng với nút khác.
4. **Nội dung là trung tâm** - bìa thật lớn, chữ đọc thoáng; chrome mảnh, lùi lại.
5. **Không che nội dung** - gợi ý/thông báo nằm trong dòng chảy (đẩy nội dung, có chuyển động) hay toast ngắn có Back;
   không thẻ nổi có nút x đè lên nội dung hay thanh phát.
6. **Chuyển động ở mọi nơi** - không gì hiện/ẩn/đổi cỡ cứng; dùng MotionPresence / MotionRegion / Collapse /
   useListPresence và token MOTION. Mọi lớp vào ngăn xếp Back; Back không bao giờ thoát app khi còn lớp mở.
7. **Chữ ngắn** - nhãn 1-4 chữ, mô tả tối đa một dòng; xưng "bạn".
8. **Hai nền tảng một giọng** - cùng tên, cùng biểu tượng, cùng thứ tự cho cùng một việc.

## 5. Token

### 5.1 Màu - "phòng nghe ấm"

Bộ hiện có (xám lạnh #f4f5f7 + hổ phách) chỉnh lại có chủ đích: nền ấm như giấy, mực gần đen hơi nâu, hổ phách sẫm như
đồng thau; một màu nhấn duy nhất, mọi màu trạng thái trầm. Tên token giữ như `styles.css` để đổi một chỗ.

| Vai | Sáng | Tối | Dùng cho |
|---|---|---|---|
| `--bg` nền | #f5f3ef | #121110 | nền màn |
| `--panel` mặt nổi | #ffffff | #1b1a18 | thanh phát, bảng trượt, hộp thoại, menu |
| `--bg-sunken` mặt chìm | #ece9e3 | #0c0b0a | ô nhập, rãnh thanh tiến độ |
| `--line` vạch | #e3dfd7 | #2e2b27 | vạch chia hàng |
| `--text` mực | #1a1814 | #ece8e1 | chữ chính, icon chính |
| `--text-2` mực phụ (Tailwind `fg-2`) | #4f4a43 | #bab3a8 | chữ phụ (≥ 4,5:1 trên nền); cách --text-3 rõ một bậc |
| `--text-3` mực ba (Tailwind `fg-3`) | #67615a | #a0998e | chữ phụ bậc ba, cả trên `--bg-sunken` / các lớp `*-soft` (≥ 4,5:1) |
| `--fg-3` mực mờ (Tailwind `fg-faint`) | #8a8478 | #7a746a | chỉ icon phụ / chữ ≥ 18px (≥ 3:1) |
| `--accent` đồng thau | #d4912b | #e9a945 | nút chính, thanh tiến độ, tab đang chọn |
| `--accent-ink` chữ trên nhấn | #1d1304 | #1b1204 | chữ/icon trên nền hổ phách |
| `--accent-text` chữ nhấn | #8a5309 | #f0b961 | chữ màu nhấn trên nền |
| `--accent-soft` nhấn nhạt | #f7ead5 | rgb(233 169 69 / .14) | câu đang đọc, hàng đang phát |
| `--success` / `--danger` | #2a7554 / #b23b33 | #5cc596 / #ef7b70 | chỉ cho trạng thái, kèm chữ/icon |

- Mặt đọc theo có 3 nền riêng, chọn trong Giao diện > "Nền đọc": Giấy #fbfaf7 / mực #1b1a17; Ngà #f3ead8 / #3b2f1e; Đêm #121110 / #d9d3c8
  (mặc định "Tự động" = Giấy khi sáng, Đêm khi tối). Trong vùng đọc, chữ phụ và chữ nhấn theo mặt đọc (`.reading-surface`).
- Trình phát đầy đủ lấy màu chủ đạo của bìa, pha 6 % (sáng) / 12 % (tối) vào `--bg` làm nền màn (trần mà chữ phụ còn ≥ 4,5:1 kể cả với bìa đen / trắng) - mỗi cuốn một không
  khí; đổi cuốn thì mờ chéo màu nền theo `--motion-slow`. Bìa không có màu rõ: giữ `--bg`.
- Mọi cặp chữ/nền kiểm tỉ lệ tương phản bằng test (`ui/src/shared/palette.test.ts`; WCAG AA: 4,5:1 chữ thường, 3:1 chữ lớn/icon) ở cả hai
  chủ đề; test cũng đối chiếu bảng này với `styles.css`. `--success` sẫm hơn bản nháp (#2f7d5b) để chữ trên `--success-soft` đạt 4,5:1.
- `npm run contrast` (`ui/scripts/check_contrast.mjs`) đọc thẳng `styles.css` và đo MỌI cặp token thực dùng: chữ trên từng nền (kể cả lớp `*-soft` chồng lên nền),
  viền / rãnh công tắc / vòng tiêu điểm (3:1), ba mặt đọc x hai giao diện, nền màn Đang nghe với mọi màu bìa, chữ cái đầu nhân vật với mọi sắc. Thoát khác 0 nếu
  một cặp trượt. Không thành phần nào dùng màu thô: chữ / icon trên ảnh bìa dùng `--cover-ink` trên `--cover-overlay`; chữ trên nền đặc trạng thái dùng `--success-ink` /
  `--danger-ink`; núm công tắc dùng `--switch-thumb`. Màn chờ và thanh hệ thống Android lấy `app_bg` (values / values-night) bằng đúng `--bg`.
- Thông tin (`--info`) là xám ấm, không có sắc thứ hai: ngoài hổ phách chỉ có xanh lục / đỏ / vàng đất của trạng thái.
- Không gradient trang trí, không màu thứ hai cho nút. Màu chỉ để nói trạng thái hay hướng mắt tới việc chính.

### 5.2 Chuyển động và hiệu ứng (VFX)

Token có sẵn (`shared/motion.ts` = `--motion-*` trong `styles.css`): nhanh 120/90 ms, vừa 220/150, chậm 300/200 (vào/ra);
đường cong Material 3 (vào = decelerate, ra = accelerate, đổi chỗ = standard). Quy tắc:

- **Vào chậm hơn ra**; ra luôn dùng thời lượng `*Out`.
- **Đổi nội dung tại chỗ = mờ qua** (ảnh cũ mờ hết rồi cái mới mới hiện, không hai lớp chữ chồng nhau); đổi cỡ thì tween chiều
  cao cùng lúc (MotionRegion, Collapse).
- **Phần tử chung giữa hai màn** (shared element): thanh phát thu nhỏ nở thành trình phát đầy đủ (khung + bìa bay từ ô nhỏ ra
  ô lớn); bìa ở Thư viện bay vào vị trí bìa ở trang sách. View Transitions khi WebView có, không thì mờ qua.
- **Danh sách**: thêm/xoá hàng mở/khép tại chỗ (useListPresence), hàng khác trượt theo, không nhảy.
- **Phản hồi chạm**: nhấn = thu 0,97 + tối nền 6 % trong 90 ms, thả = về trong 120 ms; nút phát đổi icon phát/dừng bằng mờ
  chéo tại chỗ. Không nảy, không vượt đích - sang trọng là dứt khoát (mọi `cubic-bezier` giữ tung độ trong [0, 1]).
- **Ai đổi thì người ấy mang chuyển động** (soát 139): `MotionRegion` chỉ thấy cây React truyền vào nó, nên thành phần tự lấy dữ liệu
  (truy vấn, state riêng) tự bọc `MotionPresence` / `MotionRegion` của mình. Hiện / ẩn = `MotionPresence` (lỗi: `open` của
  `InlineError` / `LoadError`), không `{điều kiện && <…>}` trần; vùng có `motionKey` thì thứ đứng ngoài khoá cần vùng riêng; danh sách
  dùng useListPresence, vùng lớn quanh nó mang `data-motion-live` để không mờ cả khối theo từng hàng (`shared/motionLint.test.ts`).
- **Câu đang đọc**: dải tô nhạt trượt sang câu kế (120 ms), từ đang đọc tô đậm hơn; tự cuộn mềm giữ câu ở 1/3 trên màn.
- **Đang tải**: khung xám đúng hình nội dung, nhịp mờ 0,6 <-> 1 chu kỳ 1,6 s; không vòng xoay giữa màn, không ánh lấp lánh.
- **Chỉ animate transform/opacity** (và chiều cao trong Collapse/MotionRegion); 60 fps trên máy Android tầm trung.
- **Giảm chuyển động** (cài đặt hệ điều hành): bỏ trượt/bay/tween cỡ, giữ mờ ≤ 120 ms.
- Không: thị sai, hạt, hiệu ứng nền chạy mãi, chuyển trang kiểu lật sách.

### 5.3 Âm thanh giao diện (SFX)

App nghe sách: âm thanh giao diện KHÔNG bao giờ trộn vào lời đọc.

- **Tự im khi đang phát**: mọi tiếng chạm tắt khi sách đang phát, trừ một: báo hẹn giờ ngủ sắp tắt.
- **Bộ tiếng** (ngắn ≤ 250 ms, mềm, cùng một âm sắc "đồng thau gõ nhẹ", tự tổng hợp bằng mã - Web Audio / Android AudioTrack -
  không file thu âm, không giấy phép ngoài; mức −24 dB so với lời đọc):
  - *chạm* (tick rất khẽ): chỉ cho công tắc, chọn mức tốc độ/hẹn giờ; KHÔNG cho mọi nút.
  - *xác nhận* (hai nốt đi lên, quãng ba): thêm sách xong, ghép máy xong.
  - *xong việc* (ba nốt): sách nói Studio làm xong (máy tính phát; điện thoại qua thông báo).
  - *hẹn giờ* (một nốt trầm, 30 giây trước khi tắt, rồi lời đọc nhỏ dần 10 giây).
  - Lỗi: không tiếng - dùng chữ + rung.
- Theo âm lượng/chế độ im của hệ thống (Android: USAGE_ASSISTANCE_SONIFICATION). Cài đặt > "Âm thanh chạm" bật/tắt, mặc
  định bật.

### 5.4 Rung (điện thoại)

Dùng hằng số phản hồi xúc giác của hệ điều hành (`View.performHapticFeedback`) - tự theo cài đặt rung của máy, cảm giác
giống app hệ thống; không tự chế chuỗi rung dài.

| Lúc | Hằng số Android | Ghi chú |
|---|---|---|
| phát / dừng | CONTEXT_CLICK | nhẹ |
| kéo thanh tiến độ qua mốc chương / mỗi 15 giây | CLOCK_TICK | chỉ khi đang kéo |
| đổi mức tốc độ, hẹn giờ, công tắc | SEGMENT_TICK (API 34+), không có thì CLOCK_TICK | |
| chạm giữ (menu bìa, sửa câu) | LONG_PRESS | |
| vuốt đóng trình phát / bảng trượt qua ngưỡng | GESTURE_THRESHOLD_ACTIVATE (34+) / bỏ qua | |
| thêm sách xong | CONFIRM (30+) | |
| lỗi cần người dùng làm gì | REJECT (30+) | |

- Không rung: hẹn giờ ngủ tắt (người có thể đã ngủ), tiến độ chạy, sự kiện nền, cuộn đọc.
- Cài đặt > "Rung" bật/tắt, mặc định bật. Máy tính không rung.

### 5.5 Kích thước

- **Khoảng cách**: 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 px. Lề màn: điện thoại 20, máy tính 40. Giữa các phần của một màn: 32
  (điện thoại) / 48 (máy tính); trong một phần: 12-16.
- **Chữ** (Be Vietnam Pro): 12 phụ chú · 14 thân phụ · 16 thân · 18 tiêu đề mục · 24 tiêu đề màn điện thoại · 32 tiêu đề màn
  máy tính · 20/1.7 chữ đọc theo. Đậm: 400 / 500 / 700 - tối đa ba mức một màn. Chữ hoa giãn chỉ cho nhãn phần (12, 600, +0.06em).
- **Bo góc**: 8 điều khiển · 12 bìa/ảnh · 20 bảng trượt/hộp thoại · tròn cho nút tròn. Danh sách không bo khung.
- **Viền**: 1px `--line` chỉ làm vạch chia hàng trong danh sách dài, thụt theo nội dung.
- **Bóng**: chỉ lớp nổi (thanh phát, bảng trượt, menu, hộp thoại).
- **Vùng chạm**: tối thiểu 44×44 (điện thoại), 32×32 (máy tính, có tooltip).

## 6. Thành phần

- **Nút**: (a) chính - nền hổ phách, cao 48 / 40, chữ ≤ 3 từ; (b) phụ - icon trơn 44 / 36 kèm nhãn nhỏ dưới (điện thoại)
  hay tooltip (máy tính); (c) chữ - màu `--accent-text`. Không kiểu thứ tư (không nút viền bo tròn lẻ loi).
- **Đầu màn**: mọi màn gốc và màn con dùng `ScreenHeader` (shared/ScreenHeader.tsx) - đệm trên 12 / 32, hàng tiêu đề cao 48 / 40, tiêu đề 24 /
  32, dòng phụ ngay dưới, nút phải căn giữa hàng; chân chữ tiêu đề trùng nhau giữa các màn cùng nền tảng (gallery_inspect: RHYTHM
  `screen-title-baseline`). Màn con: một kiểu nút ← (`BackButton`), nét mũi tên thẳng mép nội dung, tiêu đề sát sau, vùng chạm 48 / 40.
- **Hàng danh sách**: trái biểu tượng/bìa nhỏ hay trạng thái, giữa tên (16) + phụ (14, `--fg-2`), phải một hành động hay "…".
  Hàng đang phát: chữ hổ phách + vạch tiến độ mảnh, không tô nền cả hàng.
  Hàng đang chọn trong danh sách CHỌN (giọng, gộp người, câu đã chọn): chữ hổ phách + dấu tích ĐẦU dòng (`SelectionMark`, luôn giữ chỗ, mờ vào / ra; máy dò SIBLING CONSISTENCY check-mark-trailing). Ô chọn dạng lưới (tốc độ, mức hẹn giờ): ô đang chọn chữ hổ phách đậm, không dấu tích - ô hẹp, dấu tích đè hay đẩy chữ lệch tâm.
- **Điều hướng** (thanh bên máy tính, danh sách nhóm Cài đặt hai cột): mục đang mở = nền trung tính nhạt + chữ đậm màu thường; không dấu tích, không nền hổ phách, không chữ hổ phách (máy dò rule22 NAV ACCENT).
- **Dòng menu** (menu "…", bảng Thêm tuỳ chọn): mọi dòng trọn bề ngang menu, giá trị bên phải ("Tắt", tên giọng) cùng một mép; dòng mở ra tại chỗ không co theo chữ, không bị danh sách con đẩy tràn (máy dò INK EDGE menu-row-short). **Nhãn của lựa chọn** không bao giờ cắt "…" - xuống dòng (máy dò CLIPPED TEXT choice-label-truncated).
- **Nút chữ cuối hàng** chạm mép phải của cột như mọi nút cùng cột (bù đệm bằng `settings-edge-action`); không lặp icon đã có ở đầu hàng (máy dò INK EDGE ink-right, REPEATED LABEL row-icon-twice).
- **Lưới bìa**: bìa 2:3, bo 12, tên dưới bìa tối đa 2 dòng, phụ một dòng. Điện thoại 2-3 cột, máy tính tự giãn 160-200 px.
- **Bộ lọc**: hàng chữ có gạch chân hổ phách (không hộp segmented); "Xếp theo" là menu nhỏ, không select toàn chiều rộng;
  Tìm là icon mở rộng thành ô. Trong code: `FilterRow` (shared/ui.tsx) - mọi bộ lọc hai-ba mục trong tab (Kịch bản, Cần nghe lại, Việc cần duyệt) dùng nó, không `Segmented`. Một tab không chứa tab / bộ lọc thứ hai chỉ để đổi kiểu xem cùng một danh sách (Nhật ký: danh sách diễn biến + nút "Chi tiết kỹ thuật" mở thêm).
- **Mục đang chọn của tab và bộ lọc**: cùng một kiểu - chữ `--text` đậm màu thường + gạch chân hổ phách; hổ phách chỉ ở gạch, không ở chữ (soát 25-10: tab chữ tối, bộ lọc chữ hổ phách trông như hai app).
- **Tab trong trang**: chữ + gạch chân, số đếm nhỏ cạnh: số trơn `--text-2` 12 px thẳng đường chân chữ với tên tab (`TabLabel`), không viên thuốc, cả điện thoại lẫn máy tính, cả nút "Thêm". Nội dung tab không lặp lại tên tab làm tiêu đề. Không đặt nút cùng việc với một tab đang thấy trên cùng màn (máy tính "Đang nghe": "Chương" / "Đọc theo" chỉ là tab của bảng phải; máy dò REPEATED LABEL control-duplicates-tab).
- **Danh sách cuộn trong khung** (chương khi thêm sách): mép dưới mờ dần khi còn hàng chưa thấy, mép trên mờ khi đã cuộn (`useScrollFade`); hàng không bao giờ cụt cứng ở mép khung.
- **Bảng trượt / hộp thoại**: điện thoại = bảng trượt từ đáy có tay nắm; máy tính = hộp giữa màn rộng ≤ 560. Nút chính ở
  đáy, luôn thấy (đáy dính khi nội dung cuộn).
- **Thanh phát thu nhỏ**: điện thoại = bìa · tên chương / tên sách · phát. Máy tính = trái bìa+tên; giữa lùi 15 · phát ·
  tới 15 + thanh tiến độ; phải tốc độ · âm lượng · "…" (hẹn giờ, phát trên thiết bị khác, nhạc nền, giọng...).
- **Toast**: một dòng + tối đa một hành động, tự tắt, Back đóng.

## 7. Từng màn (đích)

- **Thư viện**: tiêu đề "Thư viện" + số cuốn; phải: "Thêm sách" (icon +, phụ). Hàng "Đang nghe" lớn không khung. Hàng bộ lọc
  chữ + "Xếp theo" + Tìm. Lưới bìa luôn MỞ (bộ sách nhiều tập gom thành một bìa xếp chồng, chạm mở bộ) - không kệ thu gọn
  che hết bìa. Sách máy kia có dấu nguồn nhỏ góc bìa.
- **Trang sách**: bìa + tên + tác giả · giọng · thời lượng + tiến độ mảnh; MỘT nút chính "Nghe tiếp · Chương 4" (hay
  "Nghe"); hàng phụ cùng kiểu: Đọc · Tìm · Từ đầu · Thêm(…). Tab Chương / Lịch sử / Nhân vật; danh sách phẳng.
- **Trình phát đầy đủ**: thanh đầu: thu nhỏ · "ĐANG NGHE" · "…"; bìa lớn; tên chương (20) + tên sách; thanh tiến độ + thời gian;
  hàng điều khiển 5 nút (chương trước · lùi 15 · phát tròn 72 · tới 15 · chương sau); hàng phụ 3 nút có nhãn (Tốc độ · Hẹn giờ ·
  Chương); đáy: một nút "Đọc theo" rộng cả hàng. Mọi việc khác (nhạc nền, giọng, âm lượng, quay
  lại chỗ vừa nghe, gợi ý, phát trên thiết bị khác) ở "…" của thanh đầu - "Thêm" ở thanh đầu chứ không chiếm một ô hàng phụ, để
  "Chương" (L4) còn 2 chạm. Điện thoại: "Đọc theo" mở màn đọc của chương đang nghe. Máy tính: trình phát bên trái, đọc theo bên phải.
- **Đọc theo**: chữ 20/1.7, rộng ≤ 68 ký tự; đầu màn chỉ nút về + tên chương (nền đặc, không chồng lên chữ); thanh dưới mờ
  khi cuộn đọc, chạm hiện lại; câu đang đọc tô nhạt, từ đang đọc tô đậm hơn.
- **Studio (máy tính)**: danh sách dự án là bảng gọn (tên · trạng thái · tiến độ · cập nhật); dự án: tiêu đề + trạng thái +
  MỘT nút chính theo trạng thái (Bắt đầu / Tạm dừng / Tiếp tục / Nghe trong Thư viện; sách xong còn sửa chờ áp: "Áp dụng N
  thay đổi"), còn lại vào "…"; tab hiện: Chương · Việc cần duyệt · Cần nghe lại · Nhân vật · Nhạc nền, phần còn lại (Duyệt
  trước khi thu, Kịch bản, Nhật ký) vào "Thêm" - tab đang chọn nằm trong "Thêm" thì nút ấy mang tên tab.
- **Cài đặt**: danh sách nhóm phẳng (Giọng đọc · Nghe · Hẹn giờ ngủ · Giao diện · Thiết bị · Nâng cao), máy tính hai cột.

## 8. Kiểm trước khi gộp một thay đổi giao diện

1. Ảnh `gallery:shots` trước/sau các mục bị ảnh hưởng, cả sáng và tối, điện thoại và máy tính.
2. Đếm lại số chạm các luồng ở mục 2 bị ảnh hưởng - không dài thêm.
3. Mỗi màn: đúng một nút chính; không thẻ lồng thẻ; nhãn 1-4 chữ; không thứ gì hiện/ẩn cứng; Back đóng lớp trên cùng.
4. Test DOM cho chuyển động/Back như hiện có; bản phát hành đính kèm bộ ảnh mọi màn.
5. chạy gallery_inspect, không còn phát hiện thật ở các quy tắc 1-3.
