# Chữ, icon và bo góc giống nhau giữa các nền tảng giao diện

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Ba thứ, ba nguồn chung, đều có luật máy (`python -X utf8 scripts/ui_parity.py --check`, chạy trong `tests/test_ui_parity.py`):

- **Bo góc**: `docs/DESIGN.md` 5.5 -> `scripts/gen_native_tokens.py` -> `Tokens.kt` (native) + `ui/src/shared/tokens.generated.css` (web:
  `rounded-control` / `rounded-cover` / `rounded-sheet`). Luật máy: `ui/src/shared/radiusRules.test.ts`, `RadiusRulesTest.kt`.
- **Icon**: lucide. `scripts/gen_lucide_icons.py` (MỘT danh sách `ICONS`) sinh nét cho native và Qt từ đúng gói web dùng; luật `IconRulesTest.kt`.
  Một việc = một icon trên mọi nền tảng: bảng "Việc -> icon" dưới đây là luật, `--check` báo nhãn nào dùng icon khác bảng (bên nào cũng vậy).
- **Chữ**: cặp màn `scripts/ui_parity_pairs.json` (mỗi màn native ghép với màn máy tính cùng việc; nhãn có ở một phía mà phía kia không có thì `--check` đỏ, trừ mục
  `allow` / `missing` có lý do; cặp có `only: "native"` chỉ đòi nhãn native phải có ở web vì màn web là bản đầy đủ hơn), luật chữ bên dưới, và bảng đo lệch tự sinh ở cuối file.

## Việc -> icon

Tên icon theo lucide (hai tên một hình, vd `trash` = `trash-2`, tính là một). `*` khớp mọi chữ. Hàng nào thêm vào đây thì mọi chỗ dùng nhãn ấy,
web lẫn native, phải dùng đúng icon này.

<!-- ui_parity:icons -->
| Việc (nhãn) | Icon | Ghi chú |
|---|---|---|
| Bỏ ghép, Bỏ ghép* | `unplug` | gỡ một thiết bị đã ghép |
| Ghép lại | `link-2` | ghép lại thiết bị đã bỏ |
| Xoá, Xoá khoá, Xoá hồ sơ*, Xoá khỏi*, Xoá bản đọc, Bỏ ảnh bìa | `trash-2` | xoá / gỡ hẳn một thứ |
| Xoá ô tìm | `x` | xoá chữ trong ô, không xoá dữ liệu |
| Đọc theo | `text-align-start` | chữ chạy theo giọng |
| Thêm tuỳ chọn* | `ellipsis` | nút "..." của một hàng / màn; nhãn nghe được là "Thêm tuỳ chọn", không bao giờ "Thêm" trơn (đó là dấu cộng) |
| Thêm sách | `plus` | |
| Làm mới | `refresh-cw` | |
| Nhạc nền | `eighth-note` | |
| Sửa thông tin | `pencil` | |
| Tìm | `search` | |
| Từ đầu | `rotate-ccw` | |
<!-- ui_parity:icons:end -->

## Luật chữ

Máy kiểm trong mã nguồn giao diện (web `ui/src`, native `.../ui/`, bỏ thư viện mẫu và chữ giả); chỗ trích sách thật không bị sửa.

1. **Dấu thanh kiểu cũ**: hoà, khoá, xoá, loá, thuý, tuỳ (không hòa, khóa, xóa, tùy...). "quý" giữ nguyên. Máy báo `òa/óa/ỏa/õa/ọa`, `òe/óe/...`, `ùy/úy/...`.
2. **Không `…` hay `...` ở cuối nhãn, trạng thái, nút, gợi ý ô nhập**: "Đang gửi", "Chia sẻ", "Lưu thành". `…` chỉ còn là hình nút "Thêm tuỳ chọn".
3. **Không `:` cuối nhãn** khi giá trị nằm ở thành phần riêng; `:` chỉ nằm giữa câu chạy. Máy chỉ nhắc (nhẹ), chưa đỏ.
4. **Viết hoa đầu nhãn** đứng riêng ("Đang phát"); mảnh dán sau tên bằng " · " cũng viết hoa; tên màn giữa câu giữ hoa ("Mở Cài đặt").
5. **Cùng việc, cùng chữ**: chữ web là chuẩn, trừ khi chữ native rõ ràng hơn theo DESIGN (nhãn 1-4 chữ, giản dị, gọi "bạn") thì đổi cả web.
6. **`allow` hay `missing`** (`scripts/ui_parity_pairs.json`): `allow` chỉ khi nền tảng BẮT BUỘC khác - phím tắt / chuột, tên cho trình đọc màn hình
   của một nút mà chữ thấy được hai bên như nhau, dữ liệu (tên giọng, tên công ty), câu nằm ở lõi native ngoài `ui/` (readaloud/ClipReader.kt).
   Phần màn hay tính năng chỉ một phía có (hộp giải thích quyền của web, tấm "Thiết bị phát" của native, chữ "Đang …" thay vòng quay) là
   `missing`, `side` = phía đang có. Chữ khác cho cùng một việc thì sửa cả hai phía theo từ điển dưới đây, không ghi vào pairs.json.
   Ngoại lệ TẠM: mục `wording_for_lead` (cả hai phía của một cặp chữ khác nhau cho cùng việc, ghi chữ + file:dòng hai bên) để `--check` qua trong lúc Lead chọn chữ
   chuẩn; chọn xong thì sửa một phía và xoá mục. Cột "chờ Lead" ở bảng e đếm các mục này, phải về 0.
7. **Máy dò chỉ đọc chữ nằm thẳng trong mã** (chuỗi, thuộc tính JSX, tham số Kotlin): hằng đứng riêng như `SYNC_SWITCH_LABEL` (shared/syncSwitch.ts) hay nhãn dựng từ số
   (`"$it giờ"`, `"${it}s"`) không thấy được - khi gặp lệch kiểu đó thì ghi vào `wording_for_lead` bằng tay.
8. **Dòng phụ nối bằng " · " qua một hàm** (native `dotJoin` / `dotJoined`, web `DotJoin`): mẩu rỗng biến mất nên không có "4 MB ·" treo cuối hay " · câu 3" mở đầu. Máy: `TextWrapRulesTest` cấm `joinToString(" · ")` và nối " · " bằng tay ngoài `Format.kt`.
9. **Xuống dòng**: dấu ngăn (" · " " - " " – " " | " " / ") không mở và không đóng dòng, chữ + số ngắn ("số 1", "Tập 2") đi liền. Native chạy ở một chỗ: `components/WrapText.kt` thay `BasicText` của foundation (máy quét import); web đã có `DotJoin` + `text-wrap: balance/pretty` cho dấu "·", chưa có luật số và các dấu "- – | /".
10. **Không "Không … được" cụt**: "Chưa … được" kèm việc nên làm. Máy: `CopyRulesTest` (native) và `shared/copyRules.test.ts` (web).

## Từ điển chữ chung

Một việc - một cách viết, cho web (máy tính + điện thoại), native và Qt. Thêm hàng khi chọn chữ cho việc mới; đổi một hàng là đổi mọi nơi.
`{}` = chỗ điền. Cột "thay cho" là các cách viết đã bỏ (đừng dùng lại).

**Lời chung**

| Việc | Viết | Thay cho | Lý do |
|---|---|---|---|
| Làm không được (tiêu đề lỗi) | `Chưa {việc} được`: Chưa xoá được, Chưa làm được, Chưa tải được, Chưa chia sẻ được sách, Chưa thêm được nhạc, Chưa xoá được bài này | "…, bạn thử lại", "Bạn hãy thử lại.", "Không … được", "Không làm được lúc này." | "chưa" nói sẽ làm lại được; thử lại là nút "Thử lại", không phải chữ |
| Lỗi theo việc (lõi không có câu) | Chưa lưu được khoá · Chưa kiểm tra được khoá · Chưa xoá được khoá · Chưa nghe thử được giọng này. · Chưa tải được giọng | một câu chung | nói đúng việc vừa hỏng |
| Đóng bảng trượt (tay nắm, nền tối) | Đóng | Đóng bảng | ngắn, như nút đóng của web |
| Tên bảng "…" của trình phát | Thêm tuỳ chọn | Tuỳ chọn | trùng tên nút "…" (bảng Việc -> icon) |
| Mở cài đặt của Android | Mở cài đặt | Mở Cài đặt, Mở cài đặt để cho phép | "Cài đặt" viết hoa chỉ khi là màn của ABook |
| Máy không có giọng | Máy này chưa có giọng đọc. | Chưa có giọng cài sẵn. Bạn chọn giọng trong Cài đặt. | ngắn, đã dùng ở thanh đọc |
| Thời lượng còn lại | Còn {thời lượng} | "Còn " + … ghép tay | một mẫu cho cả hai |
| Nguồn của sách nghe thẳng | Trên {tên máy} | "Trên máy tính" cố định | máy ghép thêm có tên riêng |
| Thư viện trống | Chưa có sách trên máy · Thêm sách của bạn để bắt đầu nghe. | Chưa có sách nào · Sách nghe được sẽ hiện ở đây. | nói việc kế tiếp |
| Nhãn menu xuất | Xuất MP3 · Xuất M4B · Xuất sách nói | Xuất sách nói (M4B); Xuất sách nói… | luật 2: không "…" cuối nhãn, không ngoặc kiểu file |

**Cài đặt, nhật ký**

| Việc | Viết | Thay cho | Lý do |
|---|---|---|---|
| Tên của máy này ở máy khác | Tên thiết bị (bảng: Đổi tên thiết bị · Tên hiện ở danh sách thiết bị đã ghép của máy này.) | Tên điện thoại; Tên máy này; Đổi tên điện thoại này; Máy tính và các máy đã ghép thấy điện thoại bằng tên này. | một danh từ "thiết bị" cho cả máy tính lẫn điện thoại, như web |
| Nhật ký rỗng | Chưa có dòng nào. | Nhật ký đang trống. | cùng chữ bản chẩn đoán |
| Lịch đêm | Từ · Đến · Hẹn | Số phút hẹn | ba ô, ba tên ngắn |
| Lắc để nghe thêm | Độ nhạy | Độ nhạy lắc | đã nằm trong nhóm "Lắc" |
| Hẹn giờ tắt | Không ai chạm máy chừng này thì nhỏ dần rồi dừng. · Mỗi lần nghe thêm · 5 phút / 10 phút / 15 phút · 10 giây / 30 giây / 1 phút | Không chạm máy chừng này…; Mỗi lần thêm; 5′ 10′ 15′; 10s 30s 60s | chữ đầy đủ, không ký hiệu |
| Mã nguồn mở | Mã nguồn mở (MIT) | Mã nguồn mở (MIT): ; Mã nguồn mở | luật 2: không dấu hai chấm cuối nhãn |
| Có bản mới (thông báo) | Có ABook {phiên bản} | Có ABook {phiên bản} cho điện thoại | cùng chữ với web |
| Gửi nhật ký | Xem lại trước khi gửi; bạn tự gửi đi. · Gồm thông tin máy và nhật ký gần nhất; tự che khoá, mã ghép, đường dẫn và IP nhận ra được. | Bạn chọn gửi cho ai; app không tự gửi.; Có tên sách; che khoá, mã ghép, IP và đường dẫn nhận ra được. Máy ghép đọc được khi bật “Chia sẻ thư viện”. | chữ của web (Lead 31-10) |
| Tóm tắt nhóm Nghe | Tự lùi / Không tự lùi · nhạc tự chọn / không nhạc nền | - | `listenSummary` (web) = `SettingsSummary.listen` (native) |

**Thiết bị, chia sẻ, tải**

| Việc | Viết | Thay cho | Lý do |
|---|---|---|---|
| Đang dò máy | Đang tìm thiết bị | Đang tìm máy; Đang tìm trong mạng Wi-Fi | dò cả Wi-Fi lẫn Bluetooth; "thiết bị" như web |
| Không thấy máy | Chưa thấy thiết bị | Chưa thấy máy nào; Không thấy máy nào trong mạng này.; Chưa thấy máy tính nào. Kiểm tra…; Không thấy thiết bị nào - … | một câu + nút "Tìm lại" / "Địa chỉ" ngay đó |
| Bluetooth chưa ghép | Chưa có máy nào ghép Bluetooth. Ghép ở Cài đặt Android › Bluetooth rồi thử lại. | ba cách viết | nói cách sửa |
| Thiếu quyền Bluetooth | Cần quyền Thiết bị ở gần + nút "Mở cài đặt" | Quyền “Thiết bị ở gần” của ABook đang tắt. Mở Cài đặt → … | đường đi đã nằm trong nút |
| Thêm máy ghép | Thêm thiết bị | Ghép thiết bị | cùng chữ màn Nối máy tính |
| Máy thấy qua Bluetooth | Qua Bluetooth | Qua Bluetooth · điện thoại/máy tính | biểu tượng đã nói loại máy |
| Công tắc chia sẻ | Kết nối Wi-Fi (dòng phụ của điện thoại: Máy đã ghép nghe được sách bạn thêm từ file, không cần chép sang.) | Cho máy khác nghe; tên "Chia sẻ thư viện" cho công tắc | cùng công tắc với "Kết nối Wi-Fi" của web (`SYNC_SWITCH_LABEL`) |
| Bluetooth khi chia sẻ | Bluetooth: {n} máy đang nối | Cả qua Bluetooth cho máy đã ghép - {n} đang kết nối | chỉ hiện khi mang tin |
| Mã ghép đang hiện | Nhập mã này trên máy kia · Dùng được đến {giờ:phút} | còn {phút:giây} | mốc đứng yên, không đồng hồ đếm ngược |
| Mã bị khoá | Sai 5 lần; chỉ tạo mã mới khi bạn đang ghép thiết bị. | Nhập sai mã quá 5 lần - mã đã bị huỷ. Bấm “Ghép máy mới” để có mã khác.; Mã đã huỷ vì nhập sai nhiều lần. | chữ của web |
| Ghép xong | Đã ghép {tên} | Đã kết nối với {tên} | cùng một sự kiện ở web (máy vừa nhập đúng mã) và điện thoại |
| Việc không làm được ở thiết bị khác | Chưa làm được | Chưa làm được, bạn thử lại | luật "Chưa … được", nút thử lại đã ở ngay đó |
| Phát sang thiết bị khác | Phát trên thiết bị khác · Nghe ở đây | Phát trên máy khác; Phát trên máy kia; Nghe trên máy này | một danh từ "thiết bị" |
| Hàng máy đang phát (tấm "Phát trên") | tên máy làm tiêu đề, dòng phụ "Đang phát" / "Đang dừng" / "Chưa phát sách"; tiêu đề tấm là "Phát trên", không nhắc lại thành chú thích | Đang phát trên / Đang dừng trên (treo, thiếu tên); chú thích "Phát trên thiết bị khác" ngay dưới tiêu đề "Phát trên" | thanh một dòng của web ghép "Đang phát trên {tên máy}" trong cùng câu |
| Nút làm trước | Làm trước chương sau · Làm trước {n} chương | Làm trước {n} chương tới | nhãn nút tối đa 4 chữ; tên việc "{n} chương tới" chỉ nằm trong dòng tiến độ |
| Ghép bằng mã | Ghép thiết bị · Ghép thiết bị mới · Huỷ mã | Ghép (nút khi đã có máy); Ghép máy mới; Huỷ mã này | "Huỷ mã" chỉ huỷ mã đang hiện, không gỡ thiết bị |
| Đường Bluetooth | Qua Bluetooth (dòng phụ của máy) · Dùng Bluetooth (nút trên máy đã ghép) | Dự phòng qua Bluetooth; Đường Bluetooth | ngắn, cùng chữ hai bên |
| Cách nối với máy tính | Tự tìm · Bluetooth · Nhập địa chỉ | Tìm máy trong mạng; Dùng Bluetooth (là tên cách nối); Tự tìm máy tính | ba tên một từ để cả ba nằm trên MỘT hàng ở 360 dp; web nút cùng việc là "Tự tìm" |
| Máy kia không trả lời | Chưa nối được máy kia. | Chưa nối được, bạn thử lại; Chưa nối được máy tính | máy kia có thể là điện thoại |
| Dung lượng (một dòng) | Sách {cỡ} · còn trống {cỡ} | {cỡ} · còn trống {cỡ}; Sách trên máy: … | cùng dòng tóm tắt hai bên |
| Studio chưa nối | Studio trên máy tính · Nối máy tính để làm sách nói và xem tiến độ. | Nối máy tính của bạn để tạo sách nói. | DESIGN L11: xem tiến độ |
| Hàng một máy tính ở Studio | Tạo sách nói từ xa | Studio trên máy tính | nói việc làm được |
| Máy tính chỉ cho nghe | Máy tính {tên} chỉ cho nghe - trên máy tính ấy, bật Cài đặt › Thiết bị › “Điều khiển từ xa”. | đường đi trong hằng riêng | một câu, có dấu chấm |
| Tải sách / giọng | Tải về máy · Đang tải {n}% · Huỷ tải · Đã tải xong - nghe được cả khi không có mạng · Chưa tải được | Tải · {n}%; Huỷ; Đã tải về máy; Không tải được | |
| Huỷ một lượt tải | Đã huỷ - lần tải sau làm tiếp từ chỗ dừng. | Đã huỷ tải - lần sau tải tiếp từ chỗ dở; Đã dừng tải | câu đã dùng cho giọng và Studio |

**Thư viện, xuất sách, Studio**

| Việc | Viết | Thay cho | Lý do |
|---|---|---|---|
| Bỏ sách khỏi máy | Xoá khỏi thư viện · Bỏ “{}” khỏi thư viện? · Đã bỏ “{}” khỏi thư viện | Xoá khỏi điện thoại; Xoá “{}” khỏi điện thoại?; Đã xoá “{}” khỏi điện thoại | chữ của web, hai bên như nhau |
| Vừa thêm sách | Đã thêm “{tên sách}” (chưa rõ tên: Đã thêm) | Đã thêm sách; Đã thêm sách vào thư viện; Đã thêm sách vào Thư viện | nói tên cuốn vừa thêm |
| Tiêu đề xuất sách nói | Xuất sách nói | Xuất sách nói “{tên}” | tên sách đã ở trang; điện thoại: màn Xuất sách nói cho sách chỉ có chữ |
| Chọn nơi lưu | Chọn nơi lưu | Chọn nơi lưu sách nói / bản xuất / file sách / file M4B / file dự án | một tên cho hộp chọn thư mục |
| Dừng một lượt xuất | nút Dừng · Đã dừng xuất | Huỷ (nút của thông báo); Đã huỷ xuất; Đã dừng xuất M4B; Đã dừng xuất sách nói | một chữ cho mọi kiểu xuất |
| Xuất không được | Chưa xuất được MP3 · Chưa xuất được M4B · Chưa xuất được file sách · Chưa xuất được sách nói · Chưa gói được dự án | Không xuất được …; Không gói được dự án | luật "Chưa … được" |
| Đang xuất, có phần trăm | Đang xuất · {n}% | - | một mẫu cho hàng menu của hai bên |
| Hai kiểu file sách nói | MP3 theo chương: Một thư mục, mỗi chương một MP3 kèm danh sách phát. Trình phát nào cũng mở được. · M4B cả cuốn: Một file có mục lục chương, nhớ chỗ nghe dở. Hợp Apple Books, BookPlayer, Smart AudioBook Player. | MP3 · M4B; Mỗi chương một file, kèm bìa và danh sách phát…; Một file có mục lục chương: app nghe sách nói nào cũng mở được… | chữ của web |
| Lời dưới hộp xuất sách nói | Đọc cả cuốn thành file âm thanh, nghe ở máy khác. · Chạy nền; dừng vẫn giữ phần đã làm. | Để nghe ở app sách nói khác, trên xe hơi hay máy khác.; Xuất chạy nền, nhường lúc nghe; dừng rồi làm tiếp được.; Chạy nền; huỷ vẫn giữ phần đã làm. | chữ của web, "dừng" như nút |
| Danh sách dự án (Studio) | Chờ bạn duyệt · Chưa có dự án · Duyệt trước khi thu (công tắc) · Chưa có dàn nhân vật | Cần bạn duyệt; Chưa có dự án nào; Chờ tôi duyệt; Chưa có nhân vật nào | chữ của web |
| Nhật ký của dự án rỗng | Diễn biến sẽ hiện ở đây khi sách bắt đầu chạy. | Diễn biến hiện ở đây khi sách bắt đầu chạy. | chữ của web |
| Bài nhạc cho từng đoạn | Máy chọn lại theo thể loại và mức nhạc ở trên. | Máy chọn lại bài cho từng đoạn theo thể loại và mức nhạc ở trên. | chữ của web |

**Giọng đọc**

| Việc | Viết | Thay cho | Lý do |
|---|---|---|---|
| Nghe mẫu một giọng | Nghe thử (đang phát: Dừng); tên đọc màn hình: Nghe thử {giọng} | Thử giọng | cùng chữ trình phát, trang sách |
| Giọng đang dùng | Đang dùng: {giọng} | - | một mẫu |
| Ô khoá | Khoá {nhà cung cấp} · Đã lưu {khoá che} - dán khoá mới để thay | {khoá che} · dán khoá mới để đổi | |
| Kết quả khoá | Dùng được · {n} giọng / Chưa dùng được | - | native ghép sau khoá che: `VoiceText.keyStatus` |
| Tóm tắt "Khoá trực tuyến" | tên các nhà cung cấp đã có khoá, hay Chưa có khoá | {n} khoá | nói khoá nào |
| Gỡ một giọng đã tải | Gỡ giọng | Gỡ | rõ gỡ cái gì |
| Đang tải bộ giọng | Đang tải {cỡ} · {n}% | Đang tải giọng x ({cỡ}) {n}% | tên đã ở tiêu đề thẻ / hàng |
| Máy không chạy được bộ giọng | Máy này chưa dùng được. · Máy này chưa dùng được: {lý do}. | tên giọng giữa câu | tên đã ở tiêu đề |
| Lời mời dưới tên bộ giọng | Giọng hay, đọc ngay trên máy, không cần mạng. Chữ của sách không rời máy. · Mười giọng nam nữ, nhẹ máy, không cần mạng. Chữ của sách không rời máy. | - | native thêm (ModuleKind.invite) |
| Nhãn lựa chọn nên tải | Khuyên dùng | Khuyên dùng · (ghép tay) | |
| Khoá bị từ chối | Khoá {X} không dùng được - tạm đọc bằng {Y}. Kiểm tra lại khoá trong Cài đặt. | Khoá X lỗi; tạm dùng Y — bạn kiểm tra khoá trong Cài đặt. | không gạch dài, cùng khuôn các câu "tạm đọc bằng" |
| Chưa giọng nào đọc được | Chưa có giọng nào đọc được - kiểm tra mạng hoặc cài giọng tiếng Việt cho máy. | Không có giọng nào đọc được đoạn này. | nói cách sửa; luật "Chưa … được" |
| Hỏi trước khi gửi chữ đi | tên bảng: Giọng đọc trực tuyến | Gửi chữ ra ngoài? | cùng tên hộp của trình phát web |

<!-- ui_parity:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity.py - không sửa tay, chạy lại script) -->

Quét: web 5265 chữ (3033 khác nhau), 334 cặp nhãn-icon; native 1877 chữ (1452 khác nhau), 74 cặp nhãn-icon. Nhãn so theo khoá lỏng (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối).

## a. Cùng việc, khác chữ

Cặp nhãn ngắn (<= 6 chữ) mà phía kia KHÔNG có nguyên văn nhưng có nhãn giống (chung từ, gần nhau, hay chung icon). 422 cặp; 40 cặp đầu theo độ giống. `icon` = cùng icon lucide.

| native | web | giống | nơi |
|---|---|---|---|
| Chưa có chương nghe được | Chưa có chương nghe được{} | 1.00 | `native/data/Production.kt:64` ~ `listen/LibraryScreen.tsx:336` |
| Chọn giọng | Chọn một giọng | 1.00 | `native/nowplaying/PlayerSheets.kt:201` ~ `studio/NewProjectScreen.tsx:1273` |
| Cỡ ước tính: khoảng {}{}. | Cỡ ước tính: khoảng | 1.00 | `native/studio/StudioExport.kt:243` ~ `studio/ExportBook.tsx:518` |
| Dùng “{}” | Dùng “ | 1.00 | `native/studio/WorkText.kt:78` ~ `studio/ReadingProblem.tsx:26` |
| Dùng “{}” | Đúng là {} | 1.00 | `native/studio/WorkText.kt:78` ~ `studio/ScriptTab.tsx:836` |
| Không có ai khớp “{}”. | Không có ai khớp “ | 1.00 | `native/screens/BookPeople.kt:224` ~ `studio/MergePeople.tsx:127` |
| Máy nghe ra | Máy nghe ra: “ | 1.00 | `native/studio/WorkText.kt:106` ~ `studio/ReviewQueue.tsx:231` |
| Máy đang dùng: {} | Máy đang dùng | 1.00 | `native/studio/WorkText.kt:36` ~ `studio/WorkInbox.tsx:934` |
| Mã ghép nối | Mã ghép nối: {} | 1.00 | `native/devices/PairScreen.kt:185` ~ `desktop/PhoneSync.tsx:161` (+1) |
| Nghe một câu | Nghe từ câu này | 1.00 | `native/studio/WorkText.kt:151` ~ `listen/SentenceMenu.tsx:141` |
| Nghe tiếp từ {} | Nghe tiếp từ | 1.00 | `native/data/ListenExtras.kt:98` ~ `listen/BookScreen.tsx:677` |
| Nghe tiếp từ {} | Nghe tiếp · {} | 1.00 | `native/data/ListenExtras.kt:98` ~ `listen/labels.ts:81` |
| Sẽ đọc là “{}” | Sẽ đọc là “ | 1.00 | `native/studio/ReviewTab.kt:163` ~ `studio/ReviewQueue.tsx:241` |
| Sẽ đọc là “{}” | Đọc {} | 1.00 | `native/studio/ReviewTab.kt:163` ~ `listen/LibraryScreen.tsx:201` (+1) |
| Tách thành {} chương | Đã tách thành {} chương | 1.00 | `native/studio/StudioNew.kt:307` ~ `studio/NewProjectScreen.tsx:1950` |
| Tên gốc: {} | Tên gốc: | 1.00 | `native/addbook/BookForms.kt:97` (+3) ~ `studio/CastEdits.tsx:88` |
| Đang tải phần đọc không khí{} | Đang tải phần đọc không khí | 1.00 | `native/studio/StudioMusic.kt:305` ~ `studio/MusicTab.tsx:454` |
| Đang tải {}% | Đang tải {} | 1.00 | `native/screens/RemoteBookSheet.kt:38` ~ `listen/VieneuModuleCard.tsx:237` (+1) |
| Đúng rồi, giữ “{}” | Đúng rồi, giữ “ | 1.00 | `native/studio/WorkText.kt:74` ~ `studio/WorkInbox.tsx:356` |
| Chưa mở được Studio | Chưa gỡ được Studio | 0.95 | `native/devices/DevicesRepo.kt:146` ~ `studio/StudioSetup.tsx:360` |
| Còn lại | Chọn lại | 0.93 | `native/studio/StudioText.kt:56` ~ `listen/AddBook.tsx:548` (+1) |
| Đang đo. | Đang đổi | 0.93 | `native/screens/SettingsAdvanced.kt:64` ~ `studio/MusicTab.tsx:231` |
| Chưa gửi được {}. {} | Chưa ghi được | 0.92 | `native/studio/StudioNew.kt:308` ~ `listen/LineWishes.tsx:343` (+7) |
| Đang tạo sách | Đã tạo sách | 0.92 | `native/studio/StudioNew.kt:292` ~ `studio/NewProjectScreen.tsx:1857` |
| Cắt ảnh bìa | Đặt ảnh bìa | 0.91 | `native/editbook/CoverCrop.kt:108` ~ `studio/CoverEditor.tsx:112` (+1) |
| Máy tính không còn đoạn này. | Máy tính không có cuốn này | 0.91 | `native/studio/WorkText.kt:23` ~ `desktop/RemotePhone.tsx:603` |
| Chưa gửi được nhật ký | Chưa lưu được nhật ký | 0.91 | `native/NativeActivity.kt:341` ~ `desktop/PhoneDiagnostics.tsx:64` |
| Dung lượng | Dựng xưởng | 0.90 | `native/devices/StorageScreen.kt:48` (+1) ~ `listen/ProjectFileItems.tsx:143` (+1) |
| Đổi chương | Lỗi chương | 0.90 | `native/studio/StudioScript.kt:241` ~ `studio/ChapterError.tsx:17` |
| Chưa kiểm được | Chưa tìm được | 0.89 | `native/studio/WorkText.kt:134` ~ `desktop/OtherComputers.tsx:136` |
| Ghép lại | Nghe lại | 0.88 | `native/devices/DeviceSheets.kt:90` ~ `studio/WorkInbox.tsx:939` |
| Đang mở Studio | Đang mở Studio của {} | 0.88 | `native/devices/DeviceSheets.kt:76` (+1) ~ `shared/peerStudio.ts:52` |
| Đang nối {} | Đang đổi | 0.88 | `native/devices/PairScreen.kt:195` ~ `studio/MusicTab.tsx:231` |
| Đang tải {}% | Đang cài. | 0.88 | `native/screens/RemoteBookSheet.kt:38` ~ `studio/StudioSetup.tsx:327` |
| Chưa mở được Studio | Chưa cài được Studio | 0.87 | `native/devices/DevicesRepo.kt:146` ~ `studio/StudioSetup.tsx:175` (+1) |
| Nhật ký của ABook | Nhật ký của ABook ({} dòng) | 0.87 | `native/screens/SettingsAdvanced.kt:152` ~ `shared/DiagnosticsView.tsx:29` |
| Studio trên máy tính | Studio trên máy này | 0.87 | `native/screens/OtherScreens.kt:62` ~ `studio/StudioSetup.tsx:326` (+1) |
| Chọn giọng | Đã chọn giọng {} | 0.87 | `native/nowplaying/PlayerSheets.kt:201` ~ `listen/PlayerViews.tsx:765` |
| Đang đọc ảnh | Đang đọc là: | 0.87 | `native/editbook/CoverCrop.kt:125` ~ `studio/ReviewQueue.tsx:246` |
| Chưa xoá được nhật ký | Chưa lưu được nhật ký | 0.86 | `native/data/SettingsRepo.kt:251` ~ `desktop/PhoneDiagnostics.tsx:64` |

## b. Cùng nhãn khác icon, cùng icon khác nhãn

**Cùng nhãn, khác icon** (0 nhãn có icon ở cả hai phía mà không chung icon nào):

| nhãn | web | native | nơi |
|---|---|---|---|
| (không có) | | | |

**Cùng icon, khác nhãn** (10 icon dùng ở cả hai phía mà không chung nhãn nào):

| icon | web | native |
|---|---|---|
| audio-lines | Chưa có giọng, Nghe lại | Chưa có dàn nhân vật |
| book-open-text | Chưa mở được chương này, Dừng / Nghe thử, Kịch bản chương này, Phân tích truyện | Không tìm thấy sách này |
| check | Duyệt câu, Giữ cả thẻ, Giữ thẻ, Tạm dừng {} | Chưa nghe, Chưa nghe xong, Đang lấy giọng |
| circle-dashed | Chưa nghe / Đã nghe xong, Tạm dừng {} | Chưa nghe, Chưa nghe xong |
| download | Cài Studio, Cài tiếp, Có ABook {}, Huỷ tải / Tải tiếp | Cập nhật ({}), Tải ABook Windows |
| image-plus | Đổi ảnh bìa | Chọn ảnh |
| laptop | Máy kia không trả lời | Studio máy tính, Đang mở Studio |
| rotate-ccw-clock | Khôi phục, Khôi phục bản sao | Chưa có lịch sử nghe |
| share-2 | Chia sẻ | Đang đóng file sách |
| upload | Chọn file, Nhập nhạc, Thêm file, Thêm nhạc của bạn | Đang thêm {}/{} |

Phủ của bộ ghép: icon dùng ở 149 chỗ trong mã native, ghép được với nhãn chữ ở 72; web 483 chỗ, ghép được 290. Phần còn lại là icon không đi cùng nhãn chữ (nút chỉ icon, chỉ báo) hay nhãn dựng từ model (vd tên nhóm Cài đặt), nên KHÔNG có trong bảng.
Icon native chưa quy về lucide (3): `native:ChevronIcon`, `native:OtherPlayerIcon`, `native:PlayerGlyph`.
Số cặp: web 290, native 72; icon lucide dùng: web 94, native 39.

## c. Nhãn chỉ có ở một phía, theo màn

Nhãn ngắn (<= 6 chữ) không có (theo khoá lỏng) ở phía kia - kể cả chữ giống chữ ở mục a. Để phân biệt tính năng thiếu với chữ trôi: một màn native có nhiều nhãn chỉ-native mà web cùng màn không có thường là tính năng mới; vài nhãn lẻ thường là chữ trôi (mục a).

### c1. Chỉ có ở native (244 nhãn)

- `native/NativeActivity.kt` (2): Chưa mở được trình duyệt (`329`); Chưa gửi được nhật ký (`341`)
- `native/addbook/BookForms.kt` (1): Tên gốc: {} (`97`)
- `native/addbook/ImportModel.kt` (2): Chưa mở được file (`86`); File không có sách nào. (`87`)
- `native/addbook/ImportQueue.kt` (1): Bạn hãy thử lại. (`149`)
- `native/addbook/ImportRepo.kt` (1): Bạn hãy nhập tên sách. (`97`)
- `native/addbook/PackageReviewScreen.kt` (1): Mở sách (`15`)
- `native/components/Confirm.kt` (2): Xoá phần đã tải của “{}”? (`93`); Đang xoá (`94`)
- `native/data/AndroidSettingsCore.kt` (1): Accept (`58`)
- `native/data/DemoPlayback.kt` (1): Chương {} · {} (`13`)
- `native/data/Library.kt` (1): Bạn hãy thử lại. (`161`)
- `native/data/ListenExtras.kt` (1): Nghe tiếp từ {} (`98`)
- `native/data/PrepareState.kt` (1): Chưa rõ vì sao (`74`)
- `native/data/Production.kt` (1): Chưa có chương nghe được (`64`)
- `native/data/Settings.kt` (3): Cộng thêm (`47`); Nhẹ tay (`52`); Mạnh tay (`54`)
- `native/data/SettingsRepo.kt` (6): Mở Cài đặt (`127`); Tải (`132`); Đã xoá bản lưu cũ (`137`); Chưa lưu ra được (`138`); Đã xoá nhật ký (`250`); Chưa xoá được nhật ký (`251`)
- `native/data/UndoDelete.kt` (1): Đã bỏ khỏi thư viện (`155`)
- `native/devices/CompanionRepo.kt` (1): Chưa nối được máy kia. (`95`)
- `native/devices/CompanionSurfaces.kt` (6): Chọn nơi phát (`40`); Đang gửi lệnh (`57`); Chưa phát sách (`70`); Tìm lại thiết bị phát (`122`); Báo từ Studio (`132`); Mở cài đặt (`139`)
- `native/devices/DeviceParts.kt` (3): Nhập mã này trên máy kia (`132`); Dùng được đến {} (`135`); Phần đã tải, chưa thành sách (`150`)
- `native/devices/DeviceSheets.kt` (4): Đang mở Studio (`76`); Ghép lại (`90`); Đang bỏ ghép (`137`); Đang lưu (`161`)
- `native/devices/DevicesJson.kt` (1): Sách tải dở (`59`)
- `native/devices/DevicesModel.kt` (11): Tải (`119`); Cập nhật bản thu (`121`); Cập nhật bìa (`122`); Cập nhật tên (`123`); Cập nhật chữ (`124`); Nhập địa chỉ (`179`); Chưa vào mạng Wi-Fi nào (`224`); Bluetooth: {} máy đang nối (`233`); Chưa ghép với máy tính nào (`276`); Chưa thấy (`312`); Thấy {} (`312`)
- `native/devices/DevicesRepo.kt` (4): Chưa dùng được Bluetooth (`58`); Chưa kết nối được (`65`); Chưa nối được máy kia. (`80`); Chưa mở được Studio (`146`)
- `native/devices/DevicesState.kt` (4): Chưa nối (`69`); Đã nối {} (`69`); Đang bật · {} máy (`71`); Chưa huỷ được (`384`)
- `native/devices/PairScreen.kt` (23): Nối máy tính (`80`); Thêm thiết bị (`95`); Máy đã nối (`114`); Nghe khi ra ngoài (`130`); Sách trên {} (`139`); Thiết bị khác (`156`); Cách lấy mã (`163`); Ghép Bluetooth (`169`); Cách nối (`171`); Địa chỉ máy tính (`178`); Địa chỉ, ví dụ 192.168.1.20:47630 (`178`); Mã ghép nối (`185`); Đang nối {} (`195`); Máy tính tìm thấy (`205`); Quyền Bluetooth (`216`); Cần quyền Thiết bị ở gần (`224`); Mở cài đặt (`225`); Máy tính đã ghép Bluetooth (`235`); Cài trên máy tính (`267`); Studio máy tính (`269`); Tải ABook Windows (`274`); Đã chép địa chỉ (`275`); Chép địa chỉ (`277`)
- `native/devices/ShareScreen.kt` (4): Chia sẻ thư viện (`58`); Cần quyền Thiết bị ở gần (`97`); Mở cài đặt (`98`); Cho ABook chạy nền (`103`)
- `native/devices/StorageScreen.kt` (3): Dung lượng (`48`); Còn trống {} (`54`); Chưa có gì trên máy (`58`)
- `native/editbook/BookEditor.kt` (1): Bạn hãy thử lại. (`46`)
- `native/editbook/CoverCrop.kt` (5): Bạn hãy chọn lại ảnh bìa. (`105`); Cắt ảnh bìa (`108`); Dùng ảnh (`110`); Đang lưu (`110`); Đang đọc ảnh (`125`)
- `native/editbook/EditBookScreen.kt` (1): Tên gốc: {} (`182`)
- `native/editbook/EditModel.kt` (2): Bạn hãy nhập tên sách. (`57`); Bạn hãy nhập tên chương. (`58`)
- `native/export/ExportModel.kt` (8): Chương 1/{} · 0% (`285`); Vào {} (`313`); Đã xuất {} chương (`313`); File dở đã xoá (`326`); Còn mới (`371`); Sách nói (`380`); Đã xuất xong (`391`); Chưa xuất được (`392`)
- `native/export/ExportRepo.kt` (1): Chọn thư mục để lưu trước (`85`)
- `native/export/ExportScreen.kt` (9): Xuất sách (`92`); Nơi lưu (`135`); Chỉ {} chương đổi (`152`); Có chương đã đổi (`154`); Đã xuất (`176`); Cho ABook chạy nền (`239`); Vào {} (`286`); Xuất lại (`356`); Gửi (`373`)
- `native/export/ExportState.kt` (1): Bạn hãy thử lại. (`103`)
- `native/music/MusicModel.kt` (1): Rất nhỏ (rõ lời) (`160`)
- `native/music/MusicPanel.kt` (1): Đang đóng (`245`)
- `native/music/MusicRepo.kt` (1): Chưa tìm được bài để đổi (`65`)
- `native/nowplaying/FakeNowPlayingModel.kt` (5): Chương 1 · Một buổi sớm (`80`); Những ngày gió hát (`80`); Chương {} · {} (`82`); Giọng thử A (`102`); Giọng thử B (`102`)
- `native/nowplaying/NowPlayingScreen.kt` (2): Về chế độ nghe (`132`); Cửa sổ mini (`211`)
- `native/nowplaying/PlayerSheets.kt` (2): Chọn giọng (`201`); Giọng thu sẵn (`201`)
- `native/screens/BookPeople.kt` (5): Tên gốc: {} (`134`); Đang lưu (`137`); Đang ghi (`184`); Không có ai khớp “{}”. (`224`); Đang gộp (`244`)
- `native/screens/BookSaveUi.kt` (1): Đang lưu (`133`)
- `native/screens/BookScreen.kt` (1): Tới chỗ đang nghe (`572`)
- `native/screens/BookSheets.kt` (4): Đang lưu (`186`); Đang đóng file sách (`191`); Chiếm {} (`250`); Chương này chưa có audio. (`288`)
- `native/screens/LibraryScreen.kt` (1): Nối máy (`180`)
- `native/screens/OtherScreens.kt` (5): Tạo sách nói từ xa (`36`); Mở Studio của máy nào? (`52`); Studio trên máy tính (`62`); Chưa ghép với máy tính nào (`64`); Nối máy tính (`65`)
- `native/screens/RemoteBookSheet.kt` (1): Đang tải {}% (`38`)
- `native/screens/SettingsAdvanced.kt` (8): Đã xoá nhật ký. (`58`); Đang đo. (`64`); Gửi (`95`); Xoá nhật ký (`99`); Phiên bản (`104`); Chưa đọc được nhật ký (`148`); Nhật ký của ABook (`152`); Đang đọc nhật ký. (`161`)
- `native/screens/SettingsGroups.kt` (13): Nút tai nghe lùi/tới (`106`); Tự mở cửa sổ mini (`109`); Cử chỉ (`166`); Lắc để nghe thêm (`167`); Khi lắc (`172`); Độ nhạy (`177`); Úp máy để dừng (`183`); Khi sắp tắt (`185`); Rung (`261`); Nối máy tính (`276`); Chia sẻ thư viện (`278`); Dung lượng (`280`); Điện thoại này (`283`)
- `native/screens/SettingsMaintenance.kt` (4): Bản lưu cũ ({}) (`26`); Lưu ra (`31`); Xoá bản lưu cũ? (`35`); Tải (`49`)
- `native/screens/SettingsVoice.kt` (1): Đang lấy giọng (`288`)
- `native/studio/MusicTab.kt` (1): Đang dùng ở {} đoạn (`253`)
- `native/studio/ReviewTab.kt` (1): Sẽ đọc là “{}” (`163`)
- `native/studio/StudioCover.kt` (1): Sách đã có ảnh bìa. (`104`)
- `native/studio/StudioDecisions.kt` (1): Mới ghi được {}/{} việc. {} (`133`)
- `native/studio/StudioExport.kt` (10): Đã gom {}/{} chương (`196`); Cỡ ước tính: khoảng {}{}. (`243`); Còn mới (`284`); Xuất sách (`295`); Xuất lại (`300`); Đang mở hộp Xuất (`301`); Máy tính chưa có ffmpeg (`307`); Đã xuất (`309`); Tiếp tục xuất (`312`); Chưa xuất được (`314`)
- `native/studio/StudioLog.kt` (3): Thông tin (`53`); Dài (`56`); Đang mở nhật ký (`59`)
- `native/studio/StudioMusic.kt` (5): Chọn lại nhạc cho cả cuốn? (`265`); Bài đã bỏ (`291`); Ghi công (`300`); Chọn thể loại (`301`); Đang tải phần đọc không khí{} (`305`)
- `native/studio/StudioNew.kt` (16): Nguồn (`48`); Chọn tệp (`256`); Dán chữ (`257`); Dán chữ truyện vào đây (`258`); Thêm chữ này (`259`); Tiếp (`260`); Chưa có chương nào (`266`); Chưa có tệp nào (`267`); Đã gửi (`269`); Trang phụ - chưa vào sách (`272`); Đang tạo sách (`292`); Bước {}/{} (`304`); Đang gửi {} (`305`); Tách thành {} chương (`307`); Chưa gửi được {}. {} (`308`); Chữ dán.txt (`419`)
- `native/studio/StudioPrecast.kt` (2): Duyệt xong (`146`); Bước {}/{} (`154`)
- `native/studio/StudioReadings.kt` (6): Đang tải cách đọc tên (`209`); Máy tính đang đọc thử (`215`); Cách đọc mới (`217`); Dòng nên bỏ khỏi phần đọc (`222`); Xem thêm {} tên (`228`); Dùng {} cách đọc chung (`230`)
- `native/studio/StudioScript.kt` (4): Máy nghi (`121`); Giữ nguyên: câu này của {} (`187`); Chương này chưa có câu nào. (`239`); Đổi chương (`241`)
- `native/studio/StudioText.kt` (5): Gói gửi lên quá lớn. (`20`); Máy tính chưa cho bạn sửa (`35`); Đang mở Studio (`51`); Còn lại (`56`); Chưa có chương nào (`76`)
- `native/studio/WorkText.kt` (43): Chọn khác (`17`); Máy tính không còn đoạn này. (`23`); Đang mở danh sách việc (`27`); Đã duyệt hết (`28`); Còn {} việc (`32`); Ảnh hưởng {} câu (`34`); Máy đang dùng: {} (`36`); Chọn người nói (`42`); Chọn câu (`52`); Bỏ hết (`54`); Câu xen kẽ (`57`); Cả chuỗi (`58`); Máy đang đọc thử (`71`); Đúng rồi, giữ “{}” (`74`); Dùng “{}” (`78`); Mở Cần nghe lại (`85`); Đang mở danh sách câu (`95`); Không còn câu nào cần xem (`96`); Bạn chưa xem câu nào. (`100`); Máy nghe ra (`106`); Máy không nghe ra chữ nào (`107`); Chưa có bản thu để nghe (`108`); Hiện cả câu lệch nhẹ (`109`); Chỉ câu lệch nhiều (`110`); Giữ của tôi (`112`); ... +18
- `native/voice/KeysScreen.kt` (1): Chưa đọc được các khoá (`36`)
- `native/voice/VoiceModel.kt` (2): Supertonic nhanh hơn (`229`); Có bản mới · {} (`303`)
- `native/voice/VoiceSheets.kt` (7): Đang đo tốc độ (`86`); Đang xoá (`105`); Dữ liệu di động (`123`); Vẫn tải (`124`); Đang lưu (`137`); Đồng ý (`137`); Xoá bài này? (`302`)

### c2. Chỉ có ở web phía điện thoại - listen/, shared/ (240 nhãn)

- `listen/AddBook.tsx` (4): Chưa mở được file sách này. (`296`); Chọn lại (`548`); Đường dẫn file hay thư mục (`651`); Chưa đọc được (`814`)
- `listen/BookScreen.tsx` (19): Tạm dừng {} (`151`); Đọc {} (chưa có audio) (`170`); Đọc chương này (`259`); Danh sách chương (`291`); Bỏ gộp {} vào {} (`441`); Bỏ gộp (`446`); Đổi giọng {} (`461`); Chờ áp dụng: giọng (`555`); Nghe giọng {} (`561`); Đổi giọng người kể (`562`); 7 ngày qua: (`655`); Nghe tiếp từ (`677`); Chuyển sang cuốn (`723`); Đang mở thư viện (`723`); Đọc (`1055`); Đọc tiếp (`1055`); Đã nghe {} (`1146`); Việc với sách (`1175`); Mục của sách (`1249`)
- `listen/DropToAdd.tsx` (1): Thả để thêm sách (`36`)
- `listen/EditBook.tsx` (11): Chưa chỉnh được nhạc nền (`160`); Đã đổi tên sách (`332`); Đã bỏ tên tác giả (`337`); Đã đổi tác giả (`337`); Đã đặt ảnh bìa (`342`); Lưu tên (`410`); Lưu tác giả (`433`); Mở tab Nhạc nền (`468`); Tên riêng (`478`); Chọn thư mục (`711`); Mặc định: thư mục Đã xuất (`714`)
- `listen/LibraryScreen.tsx` (13): Mở {} (`198`); Nghe ngay {} (`201`); Tạm dừng {} (`201`); Đọc {} (`201`); Thêm {} (`241`); Đang tạm dừng{} (`334`); Chưa có chương nghe được{} (`336`); Sách (`373`); Mở bộ {} (`415`); Lọc sách (`574`); Nghe xong (`576`); Xếp theo: {} (`584`); Gõ không dấu cũng được (`602`)
- `listen/LineWishes.tsx` (22): Người nói: {} (`98`); Cách đọc câu - {} (`101`); Thu lại câu này (`103`); Các từ trong câu (`162`); Bỏ cách đọc “{}” (`194`); Chưa ghi được người nói (`321`); Chưa lấy lại được (`334`); Đã ghi cách đọc câu này (`337`); Chưa ghi được (`343`); Đã ghi: thu lại câu này (`362`); Chưa bỏ được thay đổi này (`388`); Cách đọc “{}”: “{}” (`397`); Ai nghĩ câu này? (`399`); Cách đọc câu này (`399`); Sửa câu này (`399`); Đọc từ này là (`399`); Sửa cách đọc “{}” (`426`); Bỏ: {} (`441`); Đang chờ máy làm sách: {} (`470`); Hiện là {} (`471`); Cách đọc câu (`476`); Sửa cách đọc một từ (`483`)
- `listen/MorningRecap.tsx` (1): Lần cuối dùng máy (`73`)
- `listen/MyMusic.tsx` (7): Đang tải bài nhạc (`71`); Đang thêm nhạc thì dừng (`120`); Đã xoá khỏi Nhạc của tôi (`136`); Đang tải nhạc riêng (`155`); Xoá bài: {} (`176`); Giữ lại: {} (`179`); Xoá: {} (`184`)
- `listen/PlayerViews.tsx` (23): Tốc độ đọc: {} (`92`); Giọng đọc: {} (`95`); Shift+← (`264`); Đã chọn tốc độ đọc {} (`465`); Phím (`480`); Đang chuẩn bị nhạc nền (`581`); Danh sách nhạc nền (`595`); Đang tải các danh sách nhạc (`621`); Đã chọn giọng {} (`765`); Chưa xoá được bản đọc (`948`); Xoá bản đọc (`959`); Hẹn giờ ngủ trên {} (`1080`); Âm lượng (`1184`); Âm lượng {}% (`1186`); Bật tiếng (`1196`); Tắt tiếng (`1196`); Nghe kiểm (`1338`); Đóng trình phát (`1671`); Esc (`2044`); Phím tắt (`2054`); Gợi ý đọc (`2055`); Điều khiển phụ (`2086`); Bảng (`2258`)
- `listen/PlaylistChoice.tsx` (9): Nhạc nền: {} (`67`); Nhạc nền: để máy chọn{} (`67`); Đã lưu lựa chọn (`74`); Chưa chỉnh được mức nhạc (`92`); Đang thêm nhạc (`100`); Đang thêm nhạc {}/{} (`100`); Đang thêm nhạc thì dừng (`113`); Chưa mở được hộp chọn file (`115`); Đang tải danh sách (`200`)
- `listen/ProjectFileItems.tsx` (14): Mở dự án (`41`); Chưa dựng được xưởng (`44`); Cần cài Studio (card NVIDIA) - (`82`); Cần cập nhật Studio - (`82`); Studio cần sửa - (`82`); Mở dự án Studio (`103`); Tạo sách nói (`107`); Việc của xưởng (`135`); Mở xưởng đã dựng (`140`); Dựng xưởng (`143`); Màn (`216`); Đang tải việc xưởng (`219`); Không còn việc nào cần quyết. (`257`); Ngoài ra: (`259`)
- `listen/ReadAlongText.tsx` (2): Nghe từ “{}” (`55`); Shift F10: sửa cách đọc. (`339`)
- `listen/ReaderScreen.tsx` (3): Chưa mở được chương này (`264`); Về trang sách (`264`); Điều khiển đọc (`342`)
- `listen/ReadingSuggestions.tsx` (5): Chưa đổi được phần đọc (`121`); Bỏ dòng khỏi phần đọc (`160`); Xem lại gợi ý (`181`); Gợi ý cho phần đọc (`187`); Bỏ qua gợi ý (`194`)
- `listen/SendEdits.tsx` (1): Đã hiểu (`113`)
- `listen/SentenceMenu.tsx` (8): Đã chép câu (`121`); Chưa chép được (`123`); Nghe từ câu này (`141`); Sửa cách đọc (`156`); Sửa câu này (`171`); Sửa trong Studio (`171`); Chép câu (`175`); Bỏ chọn câu (`177`)
- `listen/Shortcuts.tsx` (11): Phát / tạm dừng (`17`); Space (`17`); Lùi / tới 15 giây (`18`); Chương trước / sau (`19`); Shift (`19`); Tắt / bật tiếng (`20`); Giảm / tăng tốc độ đọc (`21`); Esc (`22`); Thu nhỏ màn hình đang nghe (`22`); Xem các phím tắt này (`23`); Phím tắt (`86`)
- `listen/VieneuModuleCard.tsx` (3): Đang tải {} (`237`); Chưa đổi được cách đọc (`291`); Dùng bản tăng tốc (`293`)
- `listen/VoiceSettings.tsx` (2): Đang tải giọng đọc (`284`); Dừng nghe thử {} (`334`)
- `listen/WishesDialog.tsx` (5): Chưa bỏ được thay đổi này (`46`); Việc chờ Studio (`52`); Việc chờ gửi (`52`); Đang xem các thay đổi (`69`); Chưa có việc nào đang chờ. (`73`)
- `listen/WordReadings.tsx` (6): Đọc từ này là (`149`); Gõ cách đọc cho (`156`); Các từ trong câu (`167`); Nối thành cụm (`193`); Bấm một chữ để chọn. (`205`); Sửa cách đọc (`278`)
- `listen/bookSearch.ts` (1): Máy chủ không trả chương nào (`112`)
- `listen/clip.tsx` (1): Chưa nghe thử được (`92`)
- `listen/follow.ts` (6): ArrowDown (`66`); ArrowUp (`66`); End (`66`); Home (`66`); PageDown (`66`); PageUp (`66`)
- `listen/labels.ts` (3): Nghe tiếp · {} (`81`); Shift+→ (`99`); Bấm (`120`)
- `listen/liveClip.ts` (2): Đã bỏ đoạn này. (`156`); Giọng đọc không phản hồi. (`192`)
- `listen/liveTestKit.ts` (1): QuotaExceeded (`12`)
- `listen/model.ts` (2): Phần {} · {} (`364`); Đã nhập (`497`)
- `listen/musicBed.ts` (1): Content-Type (`139`)
- `listen/onlineConsent.ts` (1): Microsoft (`14`)
- `listen/player.tsx` (6): Đã tới câu chọn (`580`); Đã tới {} (`580`); Chưa tải được nhạc (`640`); Đọc chương ấy (`1169`); Nghe thêm {} phút (`1262`); Vẫn đang nghe (`1746`)
- `listen/playlistBed.ts` (1): Đã thêm {} bài (`357`)
- `listen/prepareAhead.ts` (1): Chưa lưu bản đọc nào. (`73`)
- `listen/readAloud.ts` (4): Chưa tải được đoạn giọng đọc. (`59`); ReadAloudEngine cần track.speech (`486`); Chưa phát được clip giọng đọc. (`1773`); Giọng đọc không phản hồi. (`1944`)
- `listen/readAloudVoice.ts` (6): Ngọc Linh (`204`); Phạm Tuyên (`204`); Thanh Bình (`204`); Mỹ Duyên (`205`); Ái Hân (`205`); Đức Trí (`205`)
- `listen/readings.ts` (1): Chưa nghe thử được lúc này. (`161`)
- `listen/saveFailure.ts` (1): Chưa lưu được chỗ đang nghe (`16`)
- `listen/sleep.ts` (2): Hẹn giờ ngủ: còn {} giây (`84`); Hẹn giờ ngủ: còn {} phút (`84`)
- `listen/vieneuModule.ts` (3): Đang đọc bằng bản thường. (`132`); Đang đọc bằng bản tăng tốc. (`134`); Đang tải {} (`303`)
- `shared/BookCover.tsx` (1): Chữ bìa trên hoạ tiết sóng (`78`)
- `shared/ChapterPreview.tsx` (2): Đưa vào sách: {} (`91`); Bấm để đổi tên chương (`131`)
- `shared/CoverSearch.tsx` (3): Google Books (`12`); Open Library (`12`); Đã đặt ảnh bìa (`76`)
- `shared/DiagnosticsView.tsx` (1): Nhật ký của ABook ({} dòng) (`29`)
- `shared/MissingLibrary.tsx` (3): Chọn lại thư mục thư viện (`19`); Không thấy thư mục thư viện (`19`); Chọn thư mục (`27`)
- `shared/OnComputerOnly.tsx` (1): Làm (`16`)
- `shared/RowBoundary.tsx` (1): Hàng danh sách lỗi (`13`)
- `shared/SettingsNav.tsx` (2): Nhóm cài đặt (`52`); Về Cài đặt (`79`)
- `shared/ToastDetails.tsx` (1): Chi tiết thông báo (`42`)
- `shared/backLayers.ts` (1): Escape (`48`)
- `shared/diagnostics.ts` (16): Tải sách (`50`); Việc nền (`58`); Việc {} (`59`); Pha: {} (`61`); Bản ABook (`103`); Điện thoại (`107`); Giờ trên máy (`111`); Pin (`115`); Mạng (`119`); Wi-Fi (`122`); Chỗ trống (`125`); Chạy nền (`130`); Cho máy khác nghe thư viện (`146`); Lần tắt gần nhất (`150`); Lần văng (`154`); Phục hồi dữ liệu (`155`)
- `shared/editsKept.ts` (1): Đã gộp {} sửa từ file (`12`)
- `shared/hostWait.ts` (1): Máy chưa trả lời kịp. (`44`)
- `shared/latestRequest.ts` (1): AbortError (`20`)
- `shared/musicLevels.ts` (1): Rất nhỏ (`10`)
- `shared/peerStudio.ts` (1): Đang mở Studio của {} (`52`)
- `shared/trashUndo.ts` (1): Chưa mang theo chỗ nghe. (`24`)
- `shared/ui.tsx` (2): Xem các tab trước (`516`); Xem các tab sau (`521`)

### c3. Chỉ có ở web phía máy tính / Studio (chỉ đếm)

| thư mục | nhãn |
|---|---|
| desktop/ | 169 |
| studio/ | 519 |

## d. Chữ hoa, dấu câu, `…` và `...`, dấu thanh, số

**d1. Cùng nhãn (theo khoá lỏng) nhưng khác nguyên văn giữa hai phía** (32):

| web | native | khác ở | nơi |
|---|---|---|---|
| bắt đầu ngay | Bắt đầu ngay | chữ hoa | `desktop/BookTemplates.tsx:107` (+2) ~ `native/studio/StudioNew.kt:289` |
| Chưa bỏ được ảnh bìa | Chưa bỏ được ảnh bìa. | dấu câu cuối | `listen/EditBook.tsx:348` (+1) ~ `native/editbook/BookEditor.kt:85` |
| Chưa gửi được về {} | Chưa gửi được về {}. | dấu câu cuối | `listen/SendEdits.tsx:43` ~ `native/editbook/BookEditor.kt:104` |
| Chưa làm trước được | Chưa làm trước được. | dấu câu cuối | `listen/PlayerViews.tsx:887` ~ `native/nowplaying/PrepareBlock.kt:64` |
| Chưa thêm được sách | Chưa thêm được sách. | dấu câu cuối | `listen/AddBook.tsx:481` ~ `native/addbook/ImportQueue.kt:86` (+1) |
| Chưa đặt được ảnh bìa | Chưa đặt được ảnh bìa. | dấu câu cuối | `listen/EditBook.tsx:343` (+1) ~ `native/editbook/BookEditor.kt:85` |
| Chưa đọc lại được file | Chưa đọc lại được file. | dấu câu cuối | `listen/AddBook.tsx:388` ~ `native/addbook/ImportQueue.kt:60` |
| Chưa đổi được tác giả | Chưa đổi được tác giả. | dấu câu cuối | `listen/EditBook.tsx:338` ~ `native/editbook/EditModel.kt:67` |
| Chưa đổi được tên sách | Chưa đổi được tên sách. | dấu câu cuối | `listen/EditBook.tsx:333` ~ `native/editbook/EditModel.kt:66` |
| Chờ áp dụng | chờ áp dụng | chữ hoa | `listen/BookScreen.tsx:431` (+2) ~ `native/studio/StudioScript.kt:253` |
| Chữ của cả cuốn được gửi tới {} để đọc, bằn… | Chữ của cả cuốn được gửi tới {} để đọc, bằn… | dấu thanh / ký tự | `desktop/listenExport.ts:85` ~ `native/export/ExportModel.kt:198` |
| cả cuốn | Cả cuốn | chữ hoa | `listen/labels.ts:28` ~ `native/export/ExportScreen.kt:152` |
| Giấy phép: | Giấy phép | dấu câu cuối | `listen/PlayerViews.tsx:1302` ~ `native/music/MusicPanel.kt:447` (+1) |
| Giới (bấm để lưu): | Giới (bấm để lưu) | dấu câu cuối | `studio/WorkInbox.tsx:622` ~ `native/studio/WorkText.kt:45` |
| hay đặt tên một người mới: | hay đặt tên một người mới | dấu câu cuối | `studio/WorkInbox.tsx:610` ~ `native/studio/WorkText.kt:43` |
| Kể bằng “tôi”? | Kể bằng “tôi” | dấu câu cuối | `studio/NewProjectScreen.tsx:1110` ~ `native/studio/StudioNew.kt:277` |
| Làm sách trên pin chậm và hao pin. Bấm “Tiế… | Làm sách trên pin chậm và hao pin. Bấm “Tiế… | dấu câu cuối | `studio/ProjectScreen.tsx:832` ~ `native/studio/StudioText.kt:119` |
| Lùi {} giây trên {} | Lùi 15 giây trên {} | dấu thanh / ký tự | `desktop/RemotePhone.tsx:246` ~ `native/devices/CompanionSurfaces.kt:80` |
| Tới {} giây trên {} | Tới 15 giây trên {} | dấu thanh / ký tự | `desktop/RemotePhone.tsx:261` ~ `native/devices/CompanionSurfaces.kt:87` |
| {} - Đang dùng: {} ({}) | {} - Đang dùng: {} ({}). | dấu câu cuối | `listen/voiceSpeed.ts:68` ~ `native/data/SettingsRepo.kt:319` |
| đang chuẩn bị | Đang chuẩn bị | chữ hoa | `listen/LibraryScreen.tsx:332` (+1) ~ `native/export/ExportModel.kt:274` |
| Đang chờ mạng… | Đang chờ mạng | dấu câu cuối | `desktop/bookFileExport.ts:182` ~ `native/export/ExportModel.kt:257` |
| đang làm | Đang làm | chữ hoa | `studio/StudioSetup.tsx:266` ~ `native/studio/StudioText.kt:54` |
| Đang làm file M4B… | Đang làm file M4B | dấu câu cuối | `desktop/bookFileExport.ts:37` (+1) ~ `native/export/ExportModel.kt:291` |
| Đang làm sách nói… | Đang làm sách nói | dấu câu cuối | `desktop/listenExport.ts:13` ~ `native/export/ExportModel.kt:285` (+1) |
| đang phát | Đang phát | chữ hoa | `desktop/RemotePhone.tsx:482` ~ `native/devices/CompanionSurfaces.kt:70` (+1) |
| Đang tính độ dài… | Đang tính độ dài | dấu câu cuối | `desktop/AudiobookDialog.tsx:132` ~ `native/export/ExportScreen.kt:217` |
| đang xuất | Đang xuất | chữ hoa | `shared/diagnostics.ts:47` ~ `native/export/ExportModel.kt:390` |
| Đang đóng gói sách… | Đang đóng gói sách | dấu câu cuối | `desktop/bookFileExport.ts:28` (+1) ~ `native/studio/StudioExport.kt:303` |
| Đã nghe hết các câu trong danh sách | Đã nghe hết các câu trong danh sách. | dấu câu cuối | `studio/ReviewQueue.tsx:333` ~ `native/studio/WorkText.kt:104` |
| Địa chỉ: | Địa chỉ | dấu câu cuối | `desktop/PhoneSync.tsx:155` ~ `native/devices/ShareScreen.kt:77` |
| Đọc là: | Đọc là | dấu câu cuối | `listen/WordReadings.tsx:241` (+4) ~ `native/studio/StudioScript.kt:252` |

**d2. Kiểu viết theo phía** (số chữ khớp / tổng; chữ quét ở trên):

| kiểu | web | native |
|---|---|---|
| dấu ba chấm ASCII `...` | 8 / 5265 | 0 / 1877 |
| dấu ba chấm `…` | 36 / 5265 | 0 / 1877 |
| kết thúc bằng dấu chấm `.` | 891 / 5265 | 386 / 1877 |
| kết thúc bằng `!` | 0 / 5265 | 0 / 1877 |
| kết thúc bằng `:` | 53 / 5265 | 3 / 1877 |
| dấu thanh kiểu cũ `oà oá uý` | 386 / 5265 | 172 / 1877 |
| dấu thanh kiểu mới `òa óa úy` | 1 / 5265 | 0 / 1877 |
| số thập phân dấu phẩy `1,5` | 1 / 5265 | 0 / 1877 |
| số thập phân dấu chấm `1.5` | 0 / 5265 | 0 / 1877 |
| nhân bằng `×` | 0 / 5265 | 0 / 1877 |
| nhân bằng `x` sau số | 0 / 5265 | 0 / 1877 |
| ngăn cách `·` | 120 / 5265 | 34 / 1877 |
| ngăn cách ` - ` | 261 / 5265 | 81 / 1877 |
| gạch dài `—`/`–` | 10 / 5265 | 1 / 1877 |
| giờ `1:30` hay `1 giờ 30` | 0 / 5265 | 2 / 1877 |
| dấu `%` dính số | 0 / 5265 | 1 / 1877 |
| dấu `%` cách số | 0 / 5265 | 0 / 1877 |

**d3. Nhãn ngắn bắt đầu bằng chữ thường** (web 147, native 0); 15 đầu mỗi phía:

- web: bạn đã chọn · (`listen/ProjectFileItems.tsx:292`); bắt đầu (`studio/NewProjectScreen.tsx:701`); bắt đầu ngay (`desktop/BookTemplates.tsx:107`); bắt đầu. (`studio/NewProjectScreen.tsx:708`); bỏ chọn (`studio/WorkInbox.tsx:1281`); chưa cài (`studio/ProjectScreen.tsx:819`); chưa nghe (`listen/BookScreen.tsx:820`); chưa phân tích tới (`studio/NameReadings.tsx:289`); chưa thu - không tốn gì (`studio/ApplyChanges.tsx:93`); chương (`listen/AddBook.tsx:700`); chương (`studio/NewProjectScreen.tsx:643`); chương (`studio/NewProjectScreen.tsx:895`); chương (`studio/NewProjectScreen.tsx:910`); chương (`studio/ProjectScreen.tsx:788`); chương (`studio/VolumeSplit.tsx:173`)
- native: (không có)

**d3b. Chữ dùng dấu thanh kiểu mới (`òa óa úy`) - kiểu thiểu số** (DESIGN.md chưa chọn kiểu nào); 12 đầu mỗi phía:

- web: Chữ của cả cuốn được gửi tới {} để đọc, bằng khóa của bạn -… (`desktop/listenExport.ts:85`)
- native: (không có)

**d4. web: cùng nhãn nhưng viết khác nhau trong chính phía này** (58); 15 đầu:

- `Ai nghĩ câu này` | `Ai nghĩ câu này?` (`listen/LineWishes.tsx:399`, `listen/LineWishes.tsx:461` (+2))
- `Ai nói câu này` | `Ai nói câu này?` (`listen/LineWishes.tsx:399`, `listen/LineWishes.tsx:461` (+4))
- `Buồn` | `buồn` (`studio/ScriptTab.tsx:184`, `studio/musicScenes.ts:29` (+1))
- `Bắt đầu` | `bắt đầu` | `bắt đầu.` (`desktop/AudiobookDialog.tsx:216`, `studio/NewProjectScreen.tsx:2041` (+3))
- `Bỏ ghép {}` | `Bỏ ghép {}?` (`desktop/OtherComputers.tsx:232`, `desktop/OtherComputers.tsx:233` (+3))
- `Chưa cài` | `Chưa cài.` | `chưa cài` (`desktop/SettingsScreen.tsx:516`, `studio/ProjectScreen.tsx:819` (+1))
- `Chưa có bài nào` | `chưa có bài nào` (`listen/MyMusic.tsx:143`, `listen/MyMusic.tsx:155` (+1))
- `Chưa ghép được` | `Chưa ghép được:` (`desktop/OtherComputers.tsx:101`, `desktop/OtherComputers.tsx:317`)
- `Chưa gói được dự án` | `Chưa gói được dự án.` (`desktop/bookFileExport.ts:57`, `studio/ExportBook.tsx:75` (+2))
- `Chưa nghe` | `chưa nghe` (`listen/BookScreen.tsx:1146`, `listen/BookScreen.tsx:264` (+2))
- `Chưa nghe thử được` | `Chưa nghe thử được:` (`listen/clip.tsx:92`, `studio/TryReading.tsx:146`)
- `Chưa thêm được chữ sáng` | `Chưa thêm được chữ sáng.` (`studio/WordTimings.tsx:34`, `studio/WordTimings.tsx:43`)
- `Chưa đọc được` | `Chưa đọc được:` (`listen/AddBook.tsx:814`, `studio/ProjectsScreen.tsx:70`)
- `Chương` | `chương` | `chương.` (`listen/AddBook.tsx:695`, `listen/AddBook.tsx:700` (+15))
- `Chương {}` | `chương {}` (`listen/ProjectFileItems.tsx:271`, `listen/ReadingSuggestions.tsx:52` (+4))

**d4. native: cùng nhãn nhưng viết khác nhau trong chính phía này** (16); 15 đầu:

- `Chưa nghe thử được giọng này` | `Chưa nghe thử được giọng này.` (`native/voice/VoiceRepo.kt:106`, `native/voice/VoiceState.kt:303` (+1))
- `Chưa tải được` | `Chưa tải được.` (`native/devices/DevicesRepo.kt:120`, `native/screens/RemoteBookSheet.kt:38`)
- `Chưa đổi được tên chương` | `Chưa đổi được tên chương.` (`native/editbook/BookEditor.kt:90`, `native/editbook/EditModel.kt:68` (+1))
- `Huỷ xuất` | `Huỷ xuất?` (`native/studio/StudioExport.kt:310`, `native/studio/StudioExport.kt:311`)
- `Hết chương này` | `hết chương này` (`native/nowplaying/PlayerSheets.kt:160`, `native/nowplaying/SleepText.kt:23`)
- `Hồ sơ nghe` | `Hồ sơ nghe:` (`native/screens/BookRecords.kt:101`, `native/screens/BookTabs.kt:197`)
- `Lùi 15 giây` | `Lùi {} giây` (`native/nowplaying/NowPlayingScreen.kt:199`, `native/pip/PipParams.kt:47`)
- `Mở Cài đặt` | `Mở cài đặt` (`native/data/SettingsRepo.kt:127`, `native/devices/CompanionSurfaces.kt:139` (+2))
- `Nữ` | `nữ` (`native/data/ListenExtras.kt:361`, `native/data/ListenExtras.kt:407` (+3))
- `Tới 15 giây` | `Tới {} giây` (`native/nowplaying/NowPlayingScreen.kt:201`, `native/pip/PipParams.kt:49`)
- `Xoá khoá` | `Xoá khoá?` (`native/voice/VoiceSheets.kt:254`, `native/voice/VoiceSheets.kt:278` (+1))
- `Xoá nhật ký` | `Xoá nhật ký?` (`native/screens/SettingsAdvanced.kt:132`, `native/screens/SettingsAdvanced.kt:99`)
- `Xoá phần đã tải` | `Xoá phần đã tải?` (`native/components/Confirm.kt:94`, `native/voice/VoiceSheets.kt:102` (+2))
- `Áp dụng {} thay đổi` | `Áp dụng {} thay đổi?` (`native/studio/StudioText.kt:165`, `native/studio/StudioText.kt:86`)
- `ĐANG NGHE` | `Đang nghe` (`native/data/BookDetail.kt:171`, `native/nowplaying/NowPlayingScreen.kt:95` (+1))
## e. Cặp màn web <-> native (luật cứng, scripts/ui_parity_pairs.json)

Trong một cặp, mỗi nhãn ngắn phải có ở cả hai phía (khoá lỏng) trừ khi nằm trong `allow` (nền tảng bắt buộc khác, có lý do) hay `missing` (tính năng / phần màn chỉ có ở một phía - Lead xếp lịch). Cột lệch phải bằng 0 thì `--check` mới qua. Cột "chờ Lead" (`wording_for_lead`) là chữ khác nhau cho cùng một việc, chưa chọn chuẩn: TẠM, mục nào có ở đó là nợ.

| cặp | nhãn web | nhãn native | lệch web | lệch native | cho phép | thiếu thật | chờ Lead |
|---|---|---|---|---|---|---|---|
| now-playing | 101 | 102 | 0 | 0 | 32 | 7 | 0 |
| shared-labels | 30 | 1267 | 0 | 0 | 7 | 0 | 0 |
| library-book | 203 | 211 | 0 | 0 | 66 | 10 | 0 |
| settings | 122 | 142 | 0 | 0 | 22 | 84 | 0 |
| devices | 143 | 168 | 0 | 0 | 18 | 167 | 0 |
| voice | 133 | 122 | 0 | 0 | 28 | 20 | 0 |
| add-edit-book | 163 | 138 | 0 | 0 | 69 | 4 | 0 |
| studio | 2104 | 423 | 0 | 0 | 59 | 90 | 0 |
| export | 78 | 81 | 0 | 0 | 28 | 43 | 0 |
| music | 34 | 46 | 0 | 0 | 11 | 8 | 0 |

Thiếu thật ở web - `now-playing`: Chưa tải được chữ. Bạn thử lại.; Chương chưa có chữ. Bạn thử lại sau.; Chọn; Chọn giọng; Giọng thu sẵn; Về chế độ nghe; Đang chọn

Thiếu thật ở web - `library-book`: Chiếm {}; Chương này chưa có audio.; Chương {}; Nối máy; Sách chưa có chương nào nghe được trên …; Tới chỗ đang nghe; Xoá phần đã tải; Xoá phần đã tải của “{}”?; Đang xoá; Đang đóng file sách

Thiếu thật ở native - `settings`: ABook {}; ABook{} là bản mới nhất.; Bản mới; Bật Điều khiển sản xuất trên máy tính đ…; Chưa cài; Chưa cập nhật được; Chưa thấy trả lời từ trang phát hành - …; Chưa đổi được lịch đêm; Chất lượng; Chọn thư mục thư viện; Cài đặt chính nằm trên máy tính đang kế…; Cách đọc chung; Cập nhật ABook; Cắm sạc lại thì tự làm tiếp đúng chỗ.; Giọng kể; Kiểm tra bản mới; Lúc đang nhỏ dần: {}.; Máy chủ chưa nhận lịch. Thử lại sau.; Máy này; Máy tính khác; Máy đề xuất; Mẫu thiết lập; Sách mới; Số phút nghe thêm; Thư viện; Tuỳ chọn ở trang này dùng khi đã cài St…; Tạm dừng dùng pin; Đang kiểm tra; Đang tải bản mới; Đang tắt; Đã bật tự chọn nhạc nền; Đã cài; Đã tắt tự chọn nhạc nền; Đã đổi thư mục thư viện; Đổi; Đổi thư mục; Độ dài nhỏ dần

Thiếu thật ở web - `settings`: Bản lưu cũ ({}); Bản trước của một lần lưu hỏng. Lưu ra …; Bật: nút Trước/Sau lùi/tới 15 giây. Tắt…; Chia sẻ thư viện; Cho phép; Cho phép thông báo để biết khi sách xon…; Chưa lưu ra được; Chưa mở được trình duyệt; Chưa xoá được nhật ký; Chưa đọc được nhật ký; Cài đè; sách và chỗ đang nghe giữ nguyê…; Cộng thêm; Cử chỉ; Dung lượng; Gồm cả các lần văng đã ghi.; Khi lắc; Khi sắp tắt; Lưu ra; Lật lên trong 10 phút là nghe tiếp.; Lắc để nghe thêm; Mạnh tay; Mở Cài đặt; Nhật ký; Nhật ký của ABook; Nhẹ tay; Nút tai nghe lùi/tới; Nối máy tính; Phiên bản; Rung; Rung nhẹ khi bạn chọn hay giữ.; Tải; Việc app làm gần đây, để tìm lỗi. Xem l…; Vừa; Xem; Xoá bản lưu cũ?; Xoá nhật ký; Úp máy để dừng; Đang hẹn giờ, lắc nhẹ hai lần để thêm g…; Đang tắt: không báo khi sách xong. Nút …; Đang đo.

Thiếu thật ở native - `devices`: Bluetooth: điện thoại đã ghép nối được …; Bạn hãy kiểm tra kết nối rồi tải lại th…; Bạn hãy thử tải lại cài đặt kết nối.; Bật máy kia và nối cùng Wi-Fi để phát.; Bật quyền riêng cho từng thiết bị để mở…; Bật Studio từ xa?; Chưa bật được đồng bộ; Chưa chọn được; Chưa lưu được nhật ký; Chưa mở được cổng đồng bộ.; Chưa tải xong về máy ({}); Chẩn đoán; Chẩn đoán {}; Chọn nơi lưu nhật ký; Cách dùng mã; Cần kiểm tra; Dừng tải và đồng bộ; giữ sách đã tải.; Ghép thiết bị trong Cài đặt Windows trư…; Hỏi lại; Hỏi lại thư viện; Không dùng; Không dùng Bluetooth dự phòng nữa; Kết nối lần cuối; Lưu nhật ký; Lần cuối {}; Máy cùng mạng thấy máy này là “{}”.; Máy kia không trả lời; Máy này; Máy tính không có cuốn này; Mã bị khoá; Mở; Mở Studio của {}; Nghe sách của máy tính khác; Nghe được cả khi {} tắt; Ngoài nhà: nghe sách đã tải, hoặc nối m…; Nhật ký có tên sách; thông tin riêng đư…; Phát trên thiết bị khác; Phần đã tải vẫn giữ trên máy này.; Quyền điều khiển; Thôi chờ

Thiếu thật ở web - `devices`: Android đang chặn thông báo của ABook.; Bluetooth: {} máy đang nối; Báo từ Studio; Bật lại trong Cài đặt của máy > Ứng dụn…; Bật Điều khiển từ xa trên máy tính.; Chi tiết; Chia sẻ thư viện; Cho ABook chạy nền; Cho hai máy vào cùng một mạng riêng ảo …; Cho phép “Thiết bị ở gần” để tìm máy đã…; Chép địa chỉ; Chưa có gì trên máy; Chưa có máy nào ghép Bluetooth. Ghép ở …; Chưa dùng được Bluetooth; Chưa ghép với máy tính nào; Chưa huỷ được; Chưa kết nối được; Chưa mở được Studio; Chưa nối; Chưa nối được máy kia.; Chưa phát sách; Chưa thấy; Chưa thấy máy khác. Bạn kiểm tra kết nố…; Chưa vào mạng Wi-Fi nào; Chưa đổi được; Chưa đổi được tên; Chỉ tìm máy đã ghép Bluetooth để nhận s…; Chọn nơi phát; Cài trên máy tính; Các máy tính đã ghép đều chỉ cho nghe -…; Cách lấy mã; Cách nối; Còn trống {}; Cùng Wi-Fi, mở Thiết bị trên máy tính.; Cần quyền Thiết bị ở gần; Cập nhật bìa; Cập nhật bản thu; Cập nhật chữ; Cập nhật tên; Dung lượng

Thiếu thật ở web - `voice`: Chưa đọc được các khoá; Chưa đổi được giọng; Chờ Wi-Fi; Có bản mới · {}; Dữ liệu di động; Hiện; Khoá {} sẽ bị xoá khỏi máy này và các g…; Không; Phần đã tải dở sẽ bị xoá khỏi máy này.; Supertonic nhanh hơn; Vẫn tải; Xoá bài này?; Đang gỡ; Đang kiểm tra; Đang lưu; Đang lấy giọng; Đang xoá; Đang đo tốc độ; Đồng ý; Ẩn

Thiếu thật ở web - `add-edit-book`: Chưa mở được file; File không có sách nào.; File này không có chữ để đọc.; Mở sách

Thiếu thật ở web - `studio`: Bài bạn đã ghim vẫn được giữ. Máy tính …; Bước {}/{}; Bạn chưa xem câu nào.; Bản thu hỏng; Bấm “Sách mới” để làm sách nói từ một f…; Bật “Cho phép điều khiển sản xuất” trên…; Bắt đầu ngay; Bỏ chương không muốn đọc. Tên chương sử…; Bỏ hết; Chưa có bản thu để nghe; Chưa có chương nào; Chưa có tệp nào; Chương này chưa có câu nào.; Chương {} sẽ được thu lại khi bạn áp dụ…; Chỉ câu lệch nhiều; Chỉ sửa chữ đem đọc; sách giữ nguyên ch…; Chọn file truyện; máy tính đọc ra chươn…; Chọn lại nhạc cho cả cuốn?; Chọn thể loại; Chọn tệp; Chờ gộp vào {}; Chờ lượt {}, tự chạy khi cuốn trước xon…; Chữ dán.txt; Chữ lệch nhiều; Chữ lệch nhẹ; Cuốn này chưa có tên nào cần chốt cách …; Cách đọc mới; Câu này đã đổi, bạn xem lại.; Còn lại; Còn {} câu chưa xem; Cần ffmpeg để ghép âm thanh. Bạn tải nó…; Dài; Dán chữ; Dán chữ truyện vào đây; Dòng nên bỏ khỏi phần đọc; Dữ liệu máy gửi không hợp lệ; bạn hãy t…; File này gộp nhiều chương. Máy tính tác…; Giọng bạn chọn đang chờ vào sách.; Giọng {} đang chờ vào sách.; Giới này chưa có giọng nào

Thiếu thật ở native - `export`: Chưa có file dự án nào được ghi.; Chưa có file M4B nào được ghi.; Chưa có file sách nào được ghi.; Chưa gói được dự án; Chưa tải được công cụ; Chưa xuất được file sách; Công cụ ghép âm thanh; Cập nhật công cụ; Dự án; File sách; Kiểu file; Lần xuất gần nhất: {}; Thiếu công cụ ghép; Tải công cụ; Tải công cụ ghép âm thanh; Xuất file sách; Đang đóng gói dự án…; Đang đóng gói sách…; Đã gói dự án; Đã xuất file sách; Đã xuất vào máy tính; Đã xuất vào máy tính {}; Để sau

Thiếu thật ở web - `export`: Bản MP3 bạn xuất trước đây có {} chương…; Cho ABook chạy nền; Chỉ {} chương đổi; Chọn thư mục để lưu trước; Cuốn dài: nên cắm sạc trong lúc làm - t…; Các chương chưa làm xong sẽ không có tr…; Còn mới; Có chương đã đổi; Có nhạc nền thì mỗi chương là file .m4a…; Cả cuốn; Giọng đọc của máy; Gửi; Lúc làm cần khoảng {} trống trong điện …; Máy chưa có giọng đọc nào - tải giọng ở…; Mở; Trong trang mở ra: Pin → bật “Cho phép …; Trong trang mở ra: Pin → chọn “Không hạ…; Trong trang mở ra: Pin → chọn “Không hạ…; Trong trang mở ra: Tiết kiệm pin → chọn…; Việc chạy nền: bạn có thể rời màn này, …

Thiếu thật ở native - `music`: Chưa xoá được bài này; Máy này chưa thêm nhạc được. Thêm ở ABo…; Thêm và xoá nhạc làm trên máy tính chủ …; Xoá; Đang thêm nhạc thì dừng; Đã thêm {} bài; Đã xoá khỏi Nhạc của tôi

Thiếu thật ở web - `music`: Chưa tìm được bài để đổi


<!-- ui_parity:end -->
