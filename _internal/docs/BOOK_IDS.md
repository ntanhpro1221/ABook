# Mã sách không mang đường dẫn

Soát UX 29-09 (agent phần nghe, mục 23): mã sách trong đường dẫn `#/book/<mã>` và trong API từng là **đường dẫn thư mục
dự án mã hoá base64**. Giải ra được đường dẫn đầy đủ - thư mục thư viện mặc định nằm dưới thư mục người dùng, tức có
**tên tài khoản Windows**, cùng tên các truyện. Lộ qua thanh địa chỉ của trình duyệt khi nghe từ xa (iPhone, iPad, máy
khác), link người dùng chia sẻ, ảnh chụp màn hình. File `.abook` không mang mã nào (`bookfile.py`) nên không lộ qua đó.

## Cách làm

- **Mã = HMAC-SHA256 của đường dẫn** (dạng chuẩn: `resolve`, không phân biệt hoa thường trên Windows) với **khoá bí mật
  của máy** - 24 ký tự hex (`library.book_id`). Khoá: 32 byte ngẫu nhiên trong `book_ids.key` cạnh `preferences.json`,
  tạo lần đầu cần tới (O_EXCL: hai tiến trình cùng mở lần đầu vẫn ra một khoá). Không cần sổ mã: cùng thư mục thì cùng
  mã, như trước - chỉ là không giải ngược được, và không đoán được bằng cách băm thử tên tài khoản (khoá bí mật).
- Khoá đi cùng dữ liệu nó đánh khoá: sao lưu / chép thư mục dữ liệu của app thì mã giữ nguyên. Mất khoá mà còn dữ liệu
  nghe thì dữ liệu ấy mồ côi (như mất chính `listening.json`).
- **Cổng đồng bộ** (`sync.py`): `/sync/v1/match` so audio từng chương để điện thoại biết cuốn nó mở từ file là cuốn nào của
  máy tính (mã máy tính); khoá đã là mã của máy tính thì trả thẳng.
- **Điện thoại** (`Store.adopt`): cuốn mở từ file mà máy tính cũng có thì đổi thư mục, gói sách, liên kết hồ sơ, sổ dấu
  vân tay sang mã máy tính. Đã có bản tải hẳn mang mã mới: để nguyên cả hai.

## Giới hạn

- API của Studio vẫn trả đường dẫn thư mục (`path`) cho giao diện trên chính máy tính (nút "Mở thư mục"); phía Nghe không
  có trường ấy.

Test: `tests/test_book_ids_hide_the_path.py` (máy tính), `mobile/android/app/src/test/.../StoreRekeyTest.kt` (điện thoại).
