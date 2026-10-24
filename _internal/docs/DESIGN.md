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
2. Điều khiển khi đang nghe: tua, chương, tốc độ, hẹn giờ ngủ, dấu trang, đọc theo chữ.
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
| L6 | Dấu trang | 1 | trình phát -> nút dấu trang; toast có "Hoàn tác" |
| L7 | Đọc theo chữ | 1 | trình phát -> "Đọc theo"; thanh điều khiển tự mờ khi đọc, chạm hiện lại |
| L8 | Chọn cuốn khác | 2 | Thư viện -> chạm bìa (vào trang sách) -> "Nghe" ; hay chạm giữ bìa -> phát ngay |
| L9 | Sách ở máy kia | 2 | máy đã ghép: sách máy kia nằm NGAY trong Thư viện (dấu nhỏ "Trên máy tính"), chạm là nghe (stream) hay tải; chưa ghép: Cài đặt > Thiết bị > Nối máy (một lần) |
| L10 | Tạo sách nói (máy tính) | ≤ 3 | Studio -> "Tạo sách nói" -> chọn file -> "Bắt đầu" (giọng, nhạc nền chọn sẵn theo mặc định tốt; chỉnh được nhưng không bắt chỉnh) |
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

Màu giữ bộ hiện có trong `ui/src/styles.css` (nền xám lạnh, hổ phách, sáng/tối) - không phải vấn đề. Siết phần còn lại:

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
- **Hàng danh sách**: trái biểu tượng/bìa nhỏ hay trạng thái, giữa tên (16) + phụ (14, `--fg-2`), phải một hành động hay "…".
  Hàng đang phát: chữ hổ phách + vạch tiến độ mảnh, không tô nền cả hàng.
- **Lưới bìa**: bìa 2:3, bo 12, tên dưới bìa tối đa 2 dòng, phụ một dòng. Điện thoại 2-3 cột, máy tính tự giãn 160-200 px.
- **Bộ lọc**: hàng chữ có gạch chân hổ phách (không hộp segmented); "Xếp theo" là menu nhỏ, không select toàn chiều rộng;
  Tìm là icon mở rộng thành ô.
- **Tab trong trang**: chữ + gạch chân, số đếm nhỏ cạnh. Nội dung tab không lặp lại tên tab làm tiêu đề.
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
  "Nghe"); hàng phụ cùng kiểu: Đọc · Tìm · Từ đầu · Thêm(…). Tab Chương / Dấu trang / Lịch sử / Nhân vật; danh sách phẳng.
- **Trình phát đầy đủ**: bìa lớn; tên chương (18) + tên sách; thanh tiến độ + thời gian; hàng điều khiển 5 nút (chương trước ·
  lùi 15 · phát · tới 15 · chương sau); hàng phụ 4 nút có nhãn (Tốc độ · Hẹn giờ · Dấu trang · Thêm); đáy: Đọc theo · Chương.
  Máy tính: trình phát bên trái, đọc theo bên phải như hiện nay.
- **Đọc theo**: chữ 20/1.7, rộng ≤ 68 ký tự; đầu màn chỉ nút về + tên chương (nền đặc, không chồng lên chữ); thanh dưới mờ
  khi cuộn đọc, chạm hiện lại; câu đang đọc tô nhạt, từ đang đọc tô đậm hơn.
- **Studio (máy tính)**: danh sách dự án là bảng gọn (tên · trạng thái · tiến độ · cập nhật); dự án: tiêu đề + trạng thái +
  MỘT nút chính theo trạng thái (Bắt đầu / Tạm dừng / Nghe trong Thư viện), còn lại vào "…"; tab tối đa 5 hiện, phần còn
  lại vào "Thêm".
- **Cài đặt**: danh sách nhóm phẳng (Giọng đọc · Nghe · Hẹn giờ ngủ · Giao diện · Thiết bị · Nâng cao), máy tính hai cột.

## 8. Kiểm trước khi gộp một thay đổi giao diện

1. Ảnh `gallery:shots` trước/sau các mục bị ảnh hưởng, cả sáng và tối, điện thoại và máy tính.
2. Đếm lại số chạm các luồng ở mục 2 bị ảnh hưởng - không dài thêm.
3. Mỗi màn: đúng một nút chính; không thẻ lồng thẻ; nhãn 1-4 chữ; không thứ gì hiện/ẩn cứng; Back đóng lớp trên cùng.
4. Test DOM cho chuyển động/Back như hiện có; bản phát hành đính kèm bộ ảnh mọi màn.
