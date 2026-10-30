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

## Lượt soát hình ảnh native-p4 (31-10)

Sửa cả LOẠI lỗi sau khi soát 245 ảnh; mỗi chữ web dưới đây đổi cùng chữ native. Đường dẫn tính từ `_internal/ui/src/`.

| File | Cũ | Mới | Ghi chú |
|---|---|---|---|
| desktop/OtherComputers.tsx | Tìm máy trong mạng (cách nối, 3 lựa chọn) | Tự tìm | ba lựa chọn nằm trọn một dòng ở 360 dp: Tự tìm · Bluetooth · Nhập địa chỉ |
| listen/PhoneDiagnostics.tsx | Trên điện thoại: Cài đặt › Thiết bị › Chia sẻ thư viện › bật tên sách... (câu chỉ công tắc cũ) | ... bật “Kết nối Wi-Fi”. Cùng Wi-Fi hay Tailscale. | công tắc tên “Kết nối Wi-Fi”, cùng nhật ký native |
| listen/PlayerViews.tsx | Làm trước {n} chương tới (nút bắt đầu) | Làm trước {n} chương | nhãn tối đa 4 chữ; tên việc “{n} chương tới” trong tiến độ giữ nguyên |

Mọi câu cụt `Không … được` thành `Chưa … được` (chuỗi chữ trong mã giao diện; `copyRules.test.ts` quét giữ luật này; chuỗi do máy chủ Python trả về không đổi, nên `SendEdits.tsx` khớp cả hai):

| File | Cũ | Mới | Ghi chú |
|---|---|---|---|
| desktop/App.tsx | Không mở được | Chưa mở được | |
| desktop/BookTemplates.tsx | Không lưu được | Chưa lưu được | |
| desktop/httpSource.ts | Không đọc được / Không gọi được | Chưa đọc được / Chưa gọi được | |
| gallery/desktopApi.ts | Không đọc được | Chưa đọc được | |
| listen/AddBook.tsx | Không mở được | Chưa mở được | |
| listen/BookScreen.tsx | Không phát được | Chưa phát được | |
| listen/EditBook.tsx | Không đọc được | Chưa đọc được | |
| listen/engine.ts | Không phát được | Chưa phát được | |
| listen/LineWishes.tsx | Không hoàn tác được / Không bỏ được | Chưa hoàn tác được / Chưa bỏ được | |
| listen/player.tsx | Không phát được | Chưa phát được | |
| listen/PlaylistChoice.tsx | Không mở được | Chưa mở được | |
| listen/readAloud.ts | Không tải được / Không phát được | Chưa tải được / Chưa phát được | |
| listen/readAloudVoice.ts | Không dùng được | Chưa dùng được | |
| listen/ReaderScreen.tsx | Không mở được | Chưa mở được | |
| listen/SendEdits.tsx | Không kết nối được | Chưa kết nối được | |
| listen/WishesDialog.tsx | Không bỏ được | Chưa bỏ được | |
| listen/WordReadings.tsx | Không hoàn tác được | Chưa hoàn tác được | |
| studio/ApplyChanges.tsx | Không bỏ được | Chưa bỏ được | |
| studio/AutoPickNote.tsx | Không đổi được | Chưa đổi được | |
| studio/CoverEditor.tsx | Không đọc được | Chưa đọc được | |
| studio/data.ts | Không bắt đầu được / Không dừng được / Không tạm dừng được / Không làm tiếp được / Không mở được | Chưa bắt đầu được / Chưa dừng được / Chưa tạm dừng được / Chưa làm tiếp được / Chưa mở được | |
| studio/decisions.ts | Không hoàn tác được | Chưa hoàn tác được | |
| studio/MusicTab.tsx | Không xoá được / Không tải được / Không đọc lại được / Không đổi được / Không dừng được / Không chọn lại được | Chưa xoá được / Chưa tải được / Chưa đọc lại được / Chưa đổi được / Chưa dừng được / Chưa chọn lại được | |
| studio/NewProjectScreen.tsx | Không đọc được / Không mở được / Không tạo được / Không tách được | Chưa đọc được / Chưa mở được / Chưa tạo được / Chưa tách được | |
| studio/projectPacking.ts | Không ghi được | Chưa ghi được | |
| studio/ProjectScreen.tsx | Không khởi động được / Không mở được | Chưa khởi động được / Chưa mở được | |
| studio/ProjectsScreen.tsx | Không đọc được / {busy ? "Chưa mở được: " : "Không đọc đư / Không mở được | Chưa đọc được / {busy ? "Chưa mở được: " : "Chưa đọc đượ / Chưa mở được | |
| studio/ScriptTab.tsx | Không hoàn tác được | Chưa hoàn tác được | |
| studio/StudioSetup.tsx | Không cài được | Chưa cài được | |
| studio/NewProjectScreen.tsx | Không đổi được sau khi tạo, để mọi chương đọc giống nhau. | Cố định sau khi tạo, để mọi chương đọc giống nhau. | nói điều gì xảy ra thay vì phủ định |
| studio/NewProjectScreen.tsx | Không làm lại với thiết lập khác được nữa. | Không thể làm lại với thiết lập khác nữa. | câu mô tả, không phải lỗi |
| studio/PhoneEdits.tsx | Không có việc nào ghi được | Chưa ghi được việc nào | |
| studio/WorkInbox.tsx | Không còn việc nào sửa được ngay - những việc bên dưới ... | Hết việc sửa được ngay - những việc bên dưới ... | |
