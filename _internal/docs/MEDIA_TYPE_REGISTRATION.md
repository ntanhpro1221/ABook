# Đăng ký kiểu MIME của file `.abook` với IANA (miễn phí)

Không ai cấp quyền dùng riêng một đuôi file. Thứ đăng ký được là **kiểu MIME** `application/vnd.ngdtuanh.abook+zip` trong
"vendor tree" của IANA - miễn phí, đứng tên người làm app, không ai khác lấy được tên ấy. Cùng với mục `mimetype` ở đầu
mỗi file (xem `ABOOK_FILE_FORMAT.md`), app và hệ điều hành nhận ra file ABook kể cả khi có phần mềm khác dùng trùng
đuôi `.abook`.

`.abookproj` (cả dự án Studio trong một file, đặc tả `ABOOKPROJ_FILE_FORMAT.md`) đăng ký riêng bằng form thứ hai -
bảng cuối file. Cả hai đã gửi ngày 01-10: `.abook` mã hồ sơ IANA #1460837, `.abookproj` #1460846
(trạng thái: https://tools.iana.org/public-view).

## Chủ sách làm (khoảng 10 phút)

1. Mở https://www.iana.org/form/media-types
2. Điền các ô theo bảng dưới (chép nguyên phần tiếng Anh). Ô "Contact" / "Author" / "Change controller" ghi tên và email
   của anh - email này IANA công bố công khai trong sổ đăng ký, nên dùng một địa chỉ anh chịu để lộ.
3. Gửi. IANA gửi thư xác nhận; chuyên gia duyệt có thể hỏi lại bằng thư (thường vài ngày tới vài tuần) - chuyển thư ấy
   cho tôi, tôi soạn câu trả lời.

## Nội dung các ô

| Ô | Điền |
|---|---|
| Type name | `application` |
| Subtype name | `vnd.ngdtuanh.abook+zip` |
| Required parameters | N/A |
| Optional parameters | N/A |
| Encoding considerations | binary |
| Security considerations | The file is a ZIP archive of MP3/WAV audio, a JPEG cover and JSON metadata. It contains no executable or active content and no external references. Readers must reject entry names outside the fixed list in the specification (no absolute paths, no `..`), enforce limits on entry count and sizes against decompression bombs, and verify every entry's size and SHA-256 against `book.json`. Media payloads are handed to the platform's standard decoders. The format carries no personal data about the listener. |
| Interoperability considerations | The first ZIP entry is `mimetype`, stored uncompressed, containing the media type string, so the format can be identified from the first bytes (as in EPUB). The archive also contains a Readium Audiobook manifest (`manifest.json`) so other audiobook players can read the audio. |
| Published specification | https://github.com/ntanhpro1221/ABook/blob/main/_internal/docs/ABOOK_FILE_FORMAT.md |
| Applications that use this media type | ABook, an audiobook production and listening app for Windows and Android (https://github.com/ntanhpro1221/ABook) |
| Fragment identifier considerations | N/A |
| Restrictions on usage | None |
| Provisional registration? | No |
| Additional information - Deprecated alias names | N/A |
| Magic number(s) | `PK\x03\x04` at offset 0; the ASCII string `mimetypeapplication/vnd.ngdtuanh.abook+zip` at offset 30 |
| File extension(s) | `.abook` |
| Macintosh file type code(s) | N/A |
| Person & email address to contact for further information | (tên + email của anh) |
| Intended usage | COMMON |
| Author | (tên của anh) |
| Change controller | (tên của anh) |

## Không bắt buộc, cũng miễn phí

- **PRONOM** (danh bạ định dạng của Lưu trữ Quốc gia Anh, dùng bởi các công cụ nhận dạng file như DROID, Siegfried):
  `.abook` đã nộp ngày 01-10 bằng pull request https://github.com/digital-preservation/PRONOM_Research/pull/185 (nội
  dung ở `PRONOM_SUBMISSION.md`). `.abookproj` nộp sau khi tính năng có trong một bản phát hành.
- Sau khi IANA duyệt: không phải đổi gì trong app - app đã dùng đúng tên kiểu này từ 0.4.0.

## Form thứ hai: `.abookproj`

Cùng trang https://www.iana.org/form/media-types, gửi riêng. Ô nào không có trong bảng thì điền như form `.abook` ở trên
(Type name `application`, Required/Optional parameters N/A, Encoding binary, Fragment N/A, Restrictions None, Provisional
No, Deprecated alias N/A, Macintosh N/A, Intended usage COMMON, tên + email như lần trước).

| Ô | Điền |
|---|---|
| Subtype name | `vnd.ngdtuanh.abookproj+zip` |
| Security considerations | The file is a ZIP archive of audio, images, plain text and an SQLite database. It contains no executable or active content and no external references. Readers must reject entry names outside the rules of the specification (no absolute paths, no `..`), enforce limits on entry count and sizes against decompression bombs, check free space, and verify every entry's size and SHA-256 against `project.json`. The database is read only by the application with fixed queries. The file may contain the full text of the book being produced and the folder paths of the computer that packed it; it carries no listening data. |
| Interoperability considerations | The first ZIP entry is `mimetype`, stored uncompressed, containing the media type string, so the format can be identified from the first bytes (as in EPUB). The related finished-audiobook format is application/vnd.ngdtuanh.abook+zip. |
| Published specification | https://github.com/ntanhpro1221/ABook/blob/main/_internal/docs/ABOOKPROJ_FILE_FORMAT.md |
| Applications that use this media type | ABook, an audiobook production and listening app for Windows and Android (https://github.com/ntanhpro1221/ABook): the Studio packs and opens projects |
| Magic number(s) | `PK\x03\x04` at offset 0; the ASCII string `mimetypeapplication/vnd.ngdtuanh.abookproj+zip` at offset 30 |
| File extension(s) | `.abookproj` |
