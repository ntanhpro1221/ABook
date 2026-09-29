# Mã sách không mang đường dẫn (kế hoạch 0.4.1)

Soát UX 29-09 (agent phần nghe, mục 23): mã sách trong đường dẫn `#/book/<mã>` và trong API là **đường dẫn thư mục dự án
mã hoá base64** (`library.book_id`). Giải ra được đường dẫn đầy đủ - thư mục thư viện mặc định nằm dưới
`%LOCALAPPDATA%`, tức có **tên tài khoản Windows**, cùng tên các truyện.

## Lộ ở đâu

- Thanh địa chỉ của trình duyệt khi nghe từ xa (iPhone, iPad, máy khác: `http://<máy>:47630/#/book/<mã>`), link người
  dùng chia sẻ, ảnh chụp màn hình.
- Lưu lượng API trong mạng nhà (không mã hoá - cùng mức với mọi thứ khác của cổng đồng bộ).
- **Không** lộ qua file `.abook`: gói không mang mã nào của app (`bookfile.py`, test "the book carries no id of any app").

## Kế hoạch

1. **Sổ mã** `book_ids.json` cạnh `preferences.json`: `{mã: đường dẫn}`. Mã mới là 16 ký tự hex ngẫu nhiên
   (`secrets.token_hex(8)`), cấp lần đầu thư viện thấy một dự án hay một cuốn đã nhập; ghi nguyên tử như các sổ khác.
2. `library.book_id(path)` tra sổ (cấp nếu chưa có); `Library.resolve(value)` tra sổ trước. **Mã cũ vẫn nhận**: giá trị
   giải base64 ra đúng một dự án đã biết thì trả về dự án ấy - link cũ, điện thoại chưa cập nhật và dữ liệu nghe cũ vẫn
   chạy. Mọi phản hồi dùng mã mới.
3. **Dời khoá dữ liệu cũ một lần** lúc mở app: `listening.json` (`links`), `reviews.json`, bộ đệm bìa/dấu vân tay nếu
   khoá theo mã. Sao lưu trước khi ghi (`*.pre-ids.bak`), như bước nâng cấu trúc của sổ dự án.
4. **Điện thoại**: cổng đồng bộ nhận mã cũ và trả mã mới trong `library`/`manifest`; app Android đổi khoá cục bộ của
   cuốn tải từ máy tính khi thấy mã mới cho cùng một cuốn (khớp bằng dấu vân tay chương, như `Store.rememberChapters`),
   giữ chỗ nghe và dấu trang.
5. Test: mã cũ vẫn mở được sách; sau khi dời, dữ liệu nghe còn nguyên; mã mới không chứa ký tự nào của đường dẫn; điện
   thoại cũ đồng bộ được với máy tính mới.

Vì sao không làm ngay cho 0.4.0: đụng mọi đường dẫn API, dữ liệu nghe đã có và giao thức với điện thoại - quá rộng để đưa
vào ngay trước bản phát hành đầu. Làm SỚM ở 0.4.1, trước khi nhiều người cài.
