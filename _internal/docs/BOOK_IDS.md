# Mã sách không mang đường dẫn

Soát UX 29-09 (agent phần nghe, mục 23): mã sách trong đường dẫn `#/book/<mã>` và trong API từng là **đường dẫn thư mục
dự án mã hoá base64**. Giải ra được đường dẫn đầy đủ - thư mục thư viện mặc định nằm dưới thư mục người dùng, tức có
**tên tài khoản Windows**, cùng tên các truyện. Lộ qua thanh địa chỉ của trình duyệt khi nghe từ xa (iPhone, iPad, máy
khác), link người dùng chia sẻ, ảnh chụp màn hình. File `.abook` không mang mã nào (`bookfile.py`) nên không lộ qua đó.

Làm ngay trong 0.4.0 (bản phát hành công khai đầu tiên): app Android 0.4.0 đổi mã gói nên điện thoại cài mới hoàn toàn và
chưa bao giờ thấy mã kiểu cũ; link nghe từ xa của bản công khai sạch ngay từ đầu.

## Cách làm

- **Mã = HMAC-SHA256 của đường dẫn** (dạng chuẩn: `resolve`, không phân biệt hoa thường trên Windows) với **khoá bí mật
  của máy** - 24 ký tự hex (`library.book_id`). Khoá: 32 byte ngẫu nhiên trong `book_ids.key` cạnh `preferences.json`,
  tạo lần đầu cần tới (O_EXCL: hai tiến trình cùng mở lần đầu vẫn ra một khoá). Không cần sổ mã: cùng thư mục thì cùng
  mã, như trước - chỉ là không giải ngược được, và không đoán được bằng cách băm thử tên tài khoản (khoá bí mật).
- Khoá đi cùng dữ liệu nó đánh khoá: sao lưu / chép thư mục dữ liệu của app thì mã giữ nguyên. Mất khoá mà còn dữ liệu
  nghe thì dữ liệu ấy mồ côi (như mất chính `listening.json`).
- **Mã cũ vẫn được nhận**: `Library.resolve` thử mã mới rồi mới giải mã kiểu cũ (phải ra một đường dẫn tuyệt đối trong
  thư viện). `Library.canonical` đổi mã cũ sang mã hiện hành; máy chủ giao diện gọi nó ở MỘT chỗ - bộ định tuyến, cho
  mọi đường `/api/books/<mã>`, `/api/listen/books/<mã>`, `/media/books/<mã>` - và ở các thân JSON mang mã sách (gạt thẻ
  "Tối qua", chuyển hồ sơ nghe). Mọi phản hồi mang mã mới.
- **Dữ liệu lưu theo mã cũ đổi khoá một lần** lúc mở app (`App._adopt_new_book_ids`): `listening.json` (bảng liên kết;
  hồ sơ giữ nguyên mã - điện thoại gộp theo mã hồ sơ), `preferences.json` (`positions`), `reviews.json`. Sao lưu từng
  file trước lần ghi đầu (`*.pre-ids.bak`). Đường dẫn trong mã cũ đủ để tính mã mới, nên thư mục đã mất vẫn đổi được.
- **Cổng đồng bộ** (`sync.py`): điện thoại chưa đổi khoá gọi bằng mã cũ vẫn được phục vụ - dữ liệu nghe lưu theo mã
  hiện hành, lời đáp nói lại đúng mã nó dùng (không thì nó tưởng hồ sơ đã chuyển sang cuốn khác và gỡ khỏi cuốn đang
  nghe). `/sync/v1/match` nhận ra mã cũ của chính máy này và trả mã mới, không cần audio.
- **Điện thoại** (`LibraryPlugin.matchImported`, `Store.rekey`): cuốn của máy tính chính (tải hẳn hay nghe thẳng) không
  có trong danh sách máy tính vừa trả thì hỏi `/sync/v1/match`; có mã mới thì đổi thư mục, gói sách, liên kết hồ sơ,
  sổ dấu vân tay sang mã ấy. Đã có bản tải hẳn mang mã mới: để nguyên cả hai.
- **Máy tính ↔ máy tính** (`remote_books._follow_renamed`): cuốn ảo dựng theo mã cũ của máy kia hỏi máy kia mã mới rồi
  đổi trong `book.json`; thư mục giữ nguyên nên mã ở máy này, chỗ nghe, file đã tải đều giữ.

## Giới hạn

- Điện thoại chép sách từ **điện thoại khác** (thiết bị ghép, mã `p<khoá>_<mã bên ấy>`) trước khi nâng cấp: máy phục vụ
  (điện thoại) chưa có `/sync/v1/match`, nên bản chép cũ và cuốn mang mã mới hiện thành hai. Bản cũ vẫn nghe được; xoá
  bản cũ rồi tải lại là xong.
- API của Studio vẫn trả đường dẫn thư mục (`path`) cho giao diện trên chính máy tính (nút "Mở thư mục"); phía Nghe không
  có trường ấy.

Test: `tests/test_book_ids_hide_the_path.py` (máy tính, cổng đồng bộ, máy tính ↔ máy tính),
`mobile/android/app/src/test/.../StoreRekeyTest.kt` (điện thoại).
