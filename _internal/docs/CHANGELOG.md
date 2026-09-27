# Nhật ký thay đổi

Những gì NGƯỜI DÙNG thấy thay đổi ở mỗi bản phát hành (máy tính và điện thoại cùng một số phiên bản). Lý do kỹ thuật và
bằng chứng đo đạc của từng thay đổi dây chuyền nằm ở `VERSIONS.md`; quy trình phát hành ở `RELEASING.md`.

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/); số phiên bản theo `major.minor.patch`.

## [Chưa phát hành]

- **Tên mới: ABook** (trước là Ebook Reader), trên máy tính lẫn điện thoại: lối tắt ở thư mục gốc và Start Menu tên
  "ABook" (lối tắt tên cũ tự gỡ khi mở app), cửa sổ khởi động, dữ liệu app ở `%LOCALAPPDATA%\ABook` (tự chuyển từ thư
  mục tên cũ nếu có).
- **Icon mới**: cuốn sách mở xoè thành cái loa (nền xanh rừng, bìa đất nung), dùng chung cho Windows và Android. File
  `.abook` và `.abookproj` có icon riêng cùng họ - ô icon app gấp góc trang; dự án đang làm thì hai nét sóng là nét đứt
  (sách chưa thành tiếng). Android có icon thích ứng theo mọi dáng launcher và icon đơn sắc nhuộm theo hình nền.
- Windows: file `.abook` và `.abookproj` hiện **bìa sách làm thumbnail** trong Explorer (chế độ icon vừa trở lên), góc
  thumbnail mang icon loại file để phân biệt hai loại. Sách chưa có bìa thì hiện icon. Đăng ký một lần bằng
  `_internal\scripts\register_file_types.ps1` (chỉ cho người dùng hiện tại, không cần quyền quản trị).
- **File sách `.abook`**: mỗi cuốn làm xong là một file duy nhất - bìa, văn bản có tag cảm xúc, audio từng chương, nhân
  vật và câu mẫu giọng - mở bằng ABook ở máy khác. Studio tự ghi file này khi sách xong và có nút "Xuất file sách". File
  được kiểm từng phần khi mở: hỏng hay bị sửa thì từ chối, không bao giờ vào thư viện nửa cuốn.
- **Máy tính mở file `.abook`**: bấm đúp file trong Explorer (kể cả khi ABook đang mở) hoặc nút "Mở file sách" trong
  Thư viện. Cuốn được chép vào thư viện (`Sách đã nhập`) và nghe đầy đủ: chương, đọc theo, nhân vật, câu mẫu, dấu trang,
  hồ sơ nghe. Không thành hai cuốn: file do chính Studio máy này xuất ra mở đúng dự án ấy; mở lại cuốn đã có thì về cuốn
  ấy, bản nhiều chương hơn thì cập nhật tại chỗ (chỗ đang nghe giữ nguyên).
- Máy tính: ABook mở bằng **cửa sổ mới** (giao diện Nghe + Studio mới). Giao diện cũ vẫn mở được bằng
  `app.py --classic`.

### Nghe sách - máy tính và điện thoại

- Giao diện nghe mới, giống nhau trên hai nền tảng: thư viện theo bộ truyện (tập kế tiếp tự nối), trang sách, màn "Đang
  nghe" có **văn bản đọc theo** (tô câu đang đọc), **chế độ đọc sách bằng mắt** đi cùng chỗ đang nghe và ngược lại.
- **Ảnh bìa thật**: đặt từ file, kéo thả hoặc dán; hoặc tìm trên iTunes, Open Library, Google Books rồi chọn. Bìa đi theo
  sách ở mọi nơi (thư viện, trình phát, màn hình khoá, widget); màu bìa nhuộm màn "Đang nghe".
- **Hẹn giờ ngủ** đầy đủ: số phút tuỳ chỉnh, hết chương, nhỏ dần trước khi tắt, lịch tự bật theo giờ, lưới an toàn khi
  ngủ quên (tự dừng sau 2 giờ không chạm máy), thẻ **"Tối qua bạn nghe tới đâu?"** mỗi sáng.
- Dấu trang có ghi chú, **lịch sử nghe** theo ngày, tiến độ cả cuốn ("còn 3 giờ 48 ở 1,5×"), tốc độ đọc theo từng sách.
- Hỏi khi thiết bị kia đã nghe xa hơn, thay vì lặng lẽ nhảy chỗ.
- **Hồ sơ nghe**: một cuốn có nhiều hồ sơ, mỗi hồ sơ giữ chỗ nghe, dấu trang và lịch sử riêng. Ô "Hồ sơ nghe" trong trang
  sách: đổi hồ sơ, **nghe lại từ đầu bằng hồ sơ mới** (lần nghe trước còn nguyên), đổi tên, xoá. Dùng được cả khi cuốn
  đang phát - chỗ đang nghe lưu vào hồ sơ cũ rồi trình phát chuyển sang chỗ của hồ sơ mới. Hồ sơ, tên và việc xoá đồng bộ
  giữa máy tính và điện thoại; chọn hồ sơ ở máy này thì máy kia theo (đang phát thì chờ dừng rồi mới theo).
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
- **Mở file `.abook`** từ trình quản lý file, Zalo, Drive, email ("Mở bằng" hoặc "Chia sẻ" sang ABook), hoặc nút "Mở file
  sách" trong app.

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
- **Sửa "ai nói câu này" ngay trong "Việc cần anh"**: mỗi người máy nghi là một nút (cùng "Người kể", "Vai phụ không
  tên", "Giữ nguyên"). Câu chuyển sang đúng giọng sẵn có của người ấy và được thu lại ở chương kế tiếp.

### Sửa lỗi

- Android: nút Back đóng màn "Đang nghe" thay vì thoát app; không còn crash khi thoát.
- Windows: shortcut Start Menu mang mã nhận diện của app, để bảng media và thanh tác vụ hiện đúng tên, biểu tượng.
- Sách không còn kẹt ở lần chạy tiếp theo sau khi một câu từng được thu lại cho rõ bị thu lại lần nữa (khi chữ đọc đổi,
  bản thu hỏng, hay người nghe sửa cách đọc tên).
- Điện thoại: một cuốn mở từ file `.abook` và cùng cuốn ấy trên máy tính không còn thành hai cuốn trong thư viện - gộp
  làm một, chỗ nghe đồng bộ tiếp với máy tính, audio đã có không phải tải lại.
- Điện thoại: nghe bằng trình phát (màn hình khoá, tai nghe) giờ báo chỗ nghe về máy tính - mỗi phút khi đang phát và
  ngay khi dừng. Trước đây chỉ dấu trang và thao tác trên màn hình mới đồng bộ.
- Máy tính: mở lại app không còn ghi chỗ nghe dở của cuốn gần nhất về 0:00 của chương (trình phát nạp sẵn cuốn ấy nhưng
  lưu vị trí trước khi kịp nạp audio).
- Điện thoại: mở trang sách là hỏi máy tính chỗ nghe, hồ sơ mới nhất - trước đây chỉ biết khi chính điện thoại phát hay
  dừng cuốn ấy.
- Truyện Trung, Việt: nhân vật được gọi bằng tên ("Du", "Tháo") không còn thành giọng thứ hai của chính người ấy (Chu
  Du, Tào Tháo). Thử trên Tam quốc diễn nghĩa: số câu đọc đúng giọng người nói tăng rõ ở mọi model phân tích.
- Danh sách nhân vật viết tên theo đúng chữ của sách ("HOÀNG CÁI", không còn "HOANG CAI" hay "KHỐNG MINH" khi model phân
  tích viết thiếu hay sai dấu).
- Dựng sổ nhân vật cho cuốn dài nhanh hơn khoảng 20 giây (đếm tên trong sách).

### Lưu ý khi nâng cấp

- Sách đang làm dở từ bản trước **không tiếp tục được** (khâu phân tích đã đổi) - tạo sách mới từ cùng nguồn.
- Dữ liệu nghe (chỗ đang nghe, dấu trang, lịch sử) chuyển sang dạng **hồ sơ nghe** độc lập với sách, tự động khi mở app:
  mỗi cuốn đang nghe thành một hồ sơ "Mặc định", máy tính và điện thoại nhận ra là cùng một hồ sơ. Không mất gì.
- Android: app đổi mã thành `com.ngdtuanh.abook`, nên ABook cài thành **một app mới** bên cạnh "Ebook Reader" cũ, không
  mang theo sách đã tải hay chỗ đang nghe. Ghép nối lại với máy tính, tải lại sách (chỗ nghe đồng bộ từ máy tính về), rồi
  gỡ app cũ.

## [0.3.0] và trước

Các bản dây chuyền trước đây (alpha) ghi ở `VERSIONS.md`, kèm lý do và bằng chứng đo cho từng thay đổi.
