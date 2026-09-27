# Nhật ký thay đổi

Những gì NGƯỜI DÙNG thấy thay đổi ở mỗi bản phát hành (máy tính và điện thoại cùng một số phiên bản). Lý do kỹ thuật và
bằng chứng đo đạc của từng thay đổi dây chuyền nằm ở `VERSIONS.md`; quy trình phát hành ở `RELEASING.md`.

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/); số phiên bản theo `major.minor.patch`.

## [Chưa phát hành]

### Nghe sách - máy tính và điện thoại

- Giao diện nghe mới, giống nhau trên hai nền tảng: thư viện theo bộ truyện (tập kế tiếp tự nối), trang sách, màn "Đang
  nghe" có **văn bản đọc theo** (tô câu đang đọc), **chế độ đọc sách bằng mắt** đi cùng chỗ đang nghe và ngược lại.
- **Ảnh bìa thật**: đặt từ file, kéo thả hoặc dán; hoặc tìm trên iTunes, Open Library, Google Books rồi chọn. Bìa đi theo
  sách ở mọi nơi (thư viện, trình phát, màn hình khoá, widget); màu bìa nhuộm màn "Đang nghe".
- **Hẹn giờ ngủ** đầy đủ: số phút tuỳ chỉnh, hết chương, nhỏ dần trước khi tắt, lịch tự bật theo giờ, lưới an toàn khi
  ngủ quên (tự dừng sau 2 giờ không chạm máy), thẻ **"Tối qua bạn nghe tới đâu?"** mỗi sáng.
- Dấu trang có ghi chú, **lịch sử nghe** theo ngày, tiến độ cả cuốn ("còn 3 giờ 48 ở 1,5×"), tốc độ đọc theo từng sách.
- Hỏi khi thiết bị kia đã nghe xa hơn, thay vì lặng lẽ nhảy chỗ.
- Xuất MP3 có tag đúng (sách, chương, giọng kể, ảnh bìa) để nghe ở app khác.
- Hoạt ảnh: bìa bay vào trình phát, trang và kệ sách chuyển mượt; theo chế độ sáng/tối của hệ thống.

### Điện thoại (Android)

- Trình phát chạy nền: màn hình khoá, thanh thông báo, tai nghe Bluetooth, widget; tự dừng khi rút tai nghe hay có cuộc
  gọi; phát tiếp sau khi khởi động lại máy.
- **Lắc máy** để nghe thêm hoặc đặt lại hẹn giờ (ba độ nhạy); **úp máy để dừng**, lật lên trong 10 phút là nghe tiếp;
  tuỳ chọn nút Trước/Sau của tai nghe thành lùi/tới 15 giây.
- Tải sách từ máy tính qua Wi-Fi: tự tìm máy tính, ghép nối bằng mã 6 số dùng một lần, đồng bộ chỗ nghe và dấu trang
  hai chiều.
- **Nghe thẳng thư viện máy tính, không cần tải về**: sách trên máy tính hiện trong Thư viện điện thoại (nhãn "Máy tính")
  và dùng được đầy đủ - chương, đọc theo, chế độ đọc, nhân vật và câu mẫu giọng, dấu trang, lịch sử. Có bộ nhớ đệm; mất
  kết nối thì báo đúng lý do và bấm phát lại là nghe tiếp đúng chỗ. "Tải về máy" để nghe cả khi không có mạng.

### Liên kết máy tính và điện thoại

- **Điều khiển điện thoại đang phát từ máy tính**: thanh "Đang phát trên <điện thoại>" với phát/dừng, lùi/tới 15 giây.
- **Chuyển máy đang nghe**: "Nghe trên máy tính" (dừng điện thoại, máy tính phát tiếp đúng giây) và "Phát trên điện
  thoại" (ngược lại) - với mọi cuốn, kể cả cuốn điện thoại chưa tải.
- Máy tính: trình phát hiện ở bảng media của Windows (Windows+A) và nhận phím media.

### Studio (sản xuất sách nói)

- Studio mới: tạo sách theo từng bước, **hàng đợi sản xuất** (cuốn thứ hai chờ thay vì tranh GPU), tiến trình từng giai
  đoạn (phân tích, phân vai, thu âm và kiểm tra).
- **Truyện kể ngôi thứ nhất**: Studio hỏi "Người kể xưng 'tôi' là ai?" và gợi ý tên; model phân tích nhận đúng người nói
  hơn hẳn (thử trên một chương: 34% lên 89%).
- **"Cần nghe lại"**: nghe các câu khâu tự kiểm tra nghi ngờ, bấm Ổn hoặc Cần thu lại.
- **"Việc cần anh"**: những chỗ máy không chắc, xếp theo lợi trên mỗi lần bấm - cách đọc tên riêng, nhân vật nam hay nữ,
  người gọi hay người nói, vai phụ không tên, ai nói câu này, bản thu lỗi. Máy vẫn tự quyết và chạy tiếp.
- **Sửa cách đọc tên ngay trong "Việc cần anh"**: nghe máy đang đọc tên ấy thế nào, bấm "Đúng rồi" hoặc gõ cách đọc khác.
  Không phải dừng sách: dây chuyền áp ở chương kế tiếp và thu lại đúng những câu đã thu có tên ấy - kể cả sách đã xong.

### Sửa lỗi

- Android: nút Back đóng màn "Đang nghe" thay vì thoát app; không còn crash khi thoát.
- Windows: shortcut Start Menu mang mã nhận diện của app, để bảng media và thanh tác vụ hiện đúng tên, biểu tượng.
- Sách không còn kẹt ở lần chạy tiếp theo sau khi một câu từng được thu lại cho rõ bị thu lại lần nữa (khi chữ đọc đổi,
  bản thu hỏng, hay người nghe sửa cách đọc tên).

### Lưu ý khi nâng cấp

- Sách đang làm dở từ bản trước **không tiếp tục được** (khâu phân tích đã đổi) - tạo sách mới từ cùng nguồn.

## [0.3.0] và trước

Các bản dây chuyền trước đây (alpha) ghi ở `VERSIONS.md`, kèm lý do và bằng chứng đo cho từng thay đổi.
