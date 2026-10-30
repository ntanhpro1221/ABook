# Chữ web đã đổi (để Qt theo)

Mọi chuỗi giao diện của web đã đổi trong lượt "áp quyết định chữ" (Lead, 31-10). Đường dẫn tính từ `_internal/ui/src/`.
Bên điện thoại (native) đã đổi theo, cùng chữ; từ điển chung nằm ở `docs/UI_PARITY.md` (mục "Từ điển chữ chung").

| File | Cũ | Mới | Ghi chú |
|---|---|---|---|
| desktop/RemotePhone.tsx | Chưa làm được, bạn thử lại | Chưa làm được | |
| desktop/RemotePhone.tsx | Phát trên máy khác (aria-label x2, tooltip) | Phát trên thiết bị khác | `gallery/entries.ts`, `studio139.dom.test.tsx` theo |
| desktop/RemotePhone.tsx | Nghe trên máy này (aria-label, chữ ở màn rộng) | Nghe ở đây | `handOff.test.tsx` theo |
| desktop/RemoteDownload.tsx | Không tải được (toast lỗi) | Chưa tải được | |
| desktop/RemoteDownload.tsx | Dừng tải (nút) | Huỷ tải | |
| desktop/remoteDownloadState.ts | Dừng tải về máy (mục menu) | Huỷ tải | `remoteDownloadState.test.ts` theo |
| desktop/PhoneSync.tsx | Huỷ mã này | Huỷ mã | |
| desktop/OtherComputers.tsx | Không tìm được (toast lỗi) | Chưa tìm được | |
| desktop/OtherComputers.tsx | Không thấy máy nào trong mạng này. | Chưa thấy thiết bị | |
| desktop/OtherComputers.tsx | Dự phòng qua Bluetooth (tooltip) / Dự phòng qua Bluetooth cho {tên} (aria) | Dùng Bluetooth / Dùng Bluetooth cho {tên} | |
| desktop/OtherComputers.tsx | Đường Bluetooth (nhãn menu) | Qua Bluetooth | |
| desktop/SettingsScreen.tsx | Mã nguồn mở (MIT): | Mã nguồn mở (MIT) | bỏ dấu hai chấm cuối nhãn |
| desktop/App.tsx | OPENED_SAID.new "Đã thêm sách" | "Đã thêm" khi chưa rõ tên; thường là Đã thêm “{tên sách}” (hỏi `/api/listen/books/{id}` lấy tên) | toast mở file .abook |
| desktop/App.tsx | pickFolder "Chọn nơi lưu file sách" | Chọn nơi lưu | |
| listen/AddBook.tsx | Đã thêm sách vào thư viện | Đã thêm “{tên sách}” | toast sau khi thêm |
| desktop/AudiobookDialog.tsx | Xuất sách nói “{tên sách}” (tiêu đề hộp) | Xuất sách nói | tên sách không còn trong tiêu đề |
| desktop/AudiobookDialog.tsx | Chạy nền; huỷ vẫn giữ phần đã làm. | Chạy nền; dừng vẫn giữ phần đã làm. | |
| desktop/AudiobookDialog.tsx | pickFolder "Chọn nơi lưu sách nói" | Chọn nơi lưu | |
| desktop/ExportBookFileJob.tsx | Xuất sách nói… (mục menu) | Xuất sách nói | luật "không … cuối nhãn" |
| desktop/ExportBookFileJob.tsx | Huỷ (nút của thông báo đang xuất) | Dừng | `studio139.dom.test.tsx` theo |
| desktop/ExportBookFileJob.tsx | Chọn nơi lưu file sách / file M4B / bản xuất / sách nói / file dự án (5 chỗ `pick`) | Chọn nơi lưu | |
| desktop/bookFileExport.ts | Không xuất được file sách / M4B / MP3 | Chưa xuất được file sách / M4B / MP3 | `bookFileExport.test.ts` theo |
| desktop/bookFileExport.ts | Không gói được dự án | Chưa gói được dự án | |
| desktop/bookFileExport.ts | Đã huỷ xuất (4 bản: file sách, M4B, MP3, dự án) | Đã dừng xuất | `bookFileExport.test.ts`, `listenExport.test.tsx` theo |
| desktop/bookFileExport.ts | dòng phụ menu khi đang xuất: "{busy} - xem thông báo ở góc màn hình" | Đang xuất · {n}% khi máy chủ báo phần trăm; chưa có thì giữ câu cũ | |
| desktop/listenExport.ts | Không xuất được sách nói | Chưa xuất được sách nói | |
| desktop/listenExport.ts | Đã dừng xuất sách nói | Đã dừng xuất | |
| studio/ExportBook.tsx | Chọn nơi lưu bản xuất / file sách / file M4B / file dự án | Chọn nơi lưu | |
| studio/ExportBook.tsx | Không xuất được MP3 / (rỗng "Không xuất được") / M4B / Không gói được dự án | Chưa xuất được MP3 / Chưa xuất được file sách / Chưa xuất được M4B / Chưa gói được dự án | |
| studio/ExportBook.tsx | Đã huỷ xuất (toast) | Đã dừng xuất | |

Không đổi (vẫn là chữ web chuẩn, native đã theo): Kết nối Wi-Fi, Đã ghép {tên}, Chưa có dự án, Chờ bạn duyệt, Chưa có dàn nhân vật,
Diễn biến sẽ hiện ở đây khi sách bắt đầu chạy., Mã nguồn mở (MIT), Có ABook {phiên bản}, Mỗi lần nghe thêm, 5 phút / 10 phút / 15 phút,
10 giây / 30 giây / 1 phút, Không ai chạm máy chừng này thì nhỏ dần rồi dừng., Xem lại trước khi gửi; bạn tự gửi đi., Gồm thông tin máy và nhật ký
gần nhất; tự che khoá, mã ghép, đường dẫn và IP nhận ra được., MP3 theo chương / M4B cả cuốn (và hai dòng mô tả), Máy chọn lại theo thể loại
và mức nhạc ở trên., Đọc cả cuốn thành file âm thanh, nghe ở máy khác., Xoá khỏi thư viện / Bỏ “{}” khỏi thư viện? / Đã bỏ “{}” khỏi thư viện.

Giữ nguyên có chủ ý (nhóm Xuất còn nằm trong `COPY_PENDING_EXPORT` của `scripts/ui_parity.py`): các chữ tiến độ có `…` cuối
("Đang đóng gói sách…", "Đang làm file M4B…", "Đang xuất MP3…", "Đang làm sách nói…", "Đang dừng…") chưa đổi vì nhánh Xuất còn đang gộp
và nhiều test web khoá chúng; sửa cùng lúc khi xoá dòng `COPY_PENDING_EXPORT`.
