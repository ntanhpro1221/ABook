# Nhật ký thay đổi

Những gì NGƯỜI DÙNG thấy thay đổi ở mỗi bản phát hành (máy tính và điện thoại cùng một số phiên bản). Lý do kỹ thuật và
bằng chứng đo đạc của từng thay đổi dây chuyền nằm ở `VERSIONS.md`; quy trình phát hành ở `RELEASING.md`.

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/); số phiên bản theo `major.minor.patch`.

## [Chưa phát hành]

### Studio

- **Cả truyện trong một file TXT**: trình tạo sách nhận ra các dòng "Chương N" (cả "Hồi", "Chapter", "第N章") và đề nghị
  **Tách thành N chương** - không bấm thì giữ nguyên như file. Tách là ghi các chương ra thư mục mới trong thư viện, file
  gốc không đổi; chữ trước tiêu đề đầu tiên thành chương "Mở đầu". Làm được cả từ Studio trên điện thoại.
- **Áp dụng N thay đổi** mở hộp xem trước: từng thay đổi nói bằng lời (cách đọc tên, ai nói câu này, giọng mới…), bao
  nhiêu câu đã thu phải thu lại, ở những chương nào, và hết khoảng bao lâu theo tốc độ thật của chính cuốn ấy. Nút ✕
  cạnh mỗi mục bỏ riêng thay đổi ấy (lựa chọn trước đó, nếu có, trở lại) - không phải đi tìm lại đúng thẻ ở tab khác.
- Danh sách dự án: cuốn "Hoàn tất" mà còn việc ghi rõ ngay trên dòng ("15 thay đổi chờ áp · 40 chương mất audio"); cuốn
  đang chờ ghi "Xếp hàng · thứ N". Chương "Mất file audio" tô màu cảnh báo thay vì xanh như chương xong.
- Tạo sách khi máy đang bận cuốn khác: thông báo nói rõ cuốn mới đã vào hàng chờ.
- **Kịch bản** sửa nhanh hơn: thanh chọn chương và chú giải người nói (số phím tắt) dính ở đầu khi cuộn; **Shift + ↑ ↓**
  (hay Shift + bấm) chọn nhiều câu rồi một phím số gán cả nhóm; người gán qua ô tìm được thêm vào chú giải với số kế
  tiếp; chọn người trong danh sách xong tự sang câu kế; **Ctrl+Z** hoàn tác lần gán gần nhất; **P** nghe câu đang chọn.
- Mỗi chương có menu **…**: nghe chương, mở **Kịch bản chương này**, và **Thu lại cả chương** (mọi câu đã thu, hạt giống
  mới - khi cả chương nghe không ổn). Cả chương tính là một thay đổi trong hộp "Áp dụng", bỏ được bằng một nút.
- **Cần nghe lại**: câu hỏng sau mọi lần thử (tượng thanh "Tách tách tách", "Coong…", chữ lạ) có nút **Sửa chữ đem đọc**
  ngay trên thẻ - viết lại cách đọc thành tiếng, lưu cho một câu hay cả các câu cùng chữ; chữ của sách giữ nguyên. Câu đã
  ghi chữ mới rời mục "Chưa xem" và hiện "Sẽ đọc là …" cho tới khi áp.

### Nghe

- Điện thoại: thông báo "Đang phát trên <TV>" có nút **Tạm dừng / Phát tiếp / Dừng** - điều khiển loa, TV ngay từ thanh
  thông báo hay màn khoá, không phải mở app. "Dừng" lưu đúng chỗ đang nghe.

## [0.4.14] - 2026-10-01

### Nghe

- Điện thoại **tự phát lên loa / TV** trong nhà, không cần máy tính: sách đã có trên điện thoại (tải về, mở file .abook)
  phát thẳng từ điện thoại; sách nghe thẳng từ máy tính vẫn đi qua máy tính. Mỗi loa / TV một mục trong "Phát trên…",
  điện thoại tự chọn đường. Đang phát lên loa thì điện thoại giữ một thông báo "Đang phát trên <TV>" để không ngủ quên
  giữa chương khi tắt màn hình.

## [0.4.13] - 2026-10-01

### Nghe

- Máy tính: **phát lên loa / TV trong mạng nhà** (DLNA - TV Samsung, LG, Sony, ampli, loa mạng, máy Windows bật điều khiển
  Windows Media Player từ xa). Nút "Phát trên…" ở thanh phát liệt kê cả loa / TV bên cạnh điện thoại; thiết bị tự tải
  chương từ máy tính, máy tính lưu chỗ nghe và tự sang chương sau, thanh "Đang phát trên <TV>" có dừng / tua / "Nghe trên
  máy này". Loa / TV phát ở tốc độ 1x.
- Điện thoại: nút "Phát trên…" ở màn đang nghe liệt kê cả loa / TV mà máy tính (đang mở ABook) thấy trong nhà - phát sách
  của máy tính lên đó, dừng / tua / "Nghe ở đây" từ thanh "Đang phát trên <TV>" của điện thoại. Máy tính phục vụ audio.
- Bấm "Phát trên <máy khác>" rồi đóng hay tải lại app không còn đưa chỗ nghe về chỗ lúc chuyển đi.

## [0.4.12] - 2026-10-01

### Studio (sản xuất sách nói)

- Trình tạo sách, bước Chất lượng: chọn **model đọc hiểu truyện** riêng cho cuốn này (các model đang có trong Ollama của
  Studio) - thử một model mới trên sách thật mà không đổi model mặc định của app. Trang dự án ghi model đã dùng.
- **Tạo sách từ file EPUB**: ở bước chọn chương, chọn (hay gửi từ điện thoại) một file `.epub` - mỗi chương trong EPUB
  thành một chương, tên chương theo mục lục, tên sách theo metadata. Chương tách ra nằm trong thư viện ("Nguồn EPUB"),
  không ghi cạnh file của bạn; EPUB hỏng thì trình tạo sách nói lý do.
- **Cách đọc chung cho mọi sách**: sửa cách đọc một tên rồi tích "Dùng cho mọi sách" (hay thêm trong Cài đặt → Studio →
  Cách đọc chung) - sách mới có tên ấy tự dùng cách đọc này ngay lúc tạo; sách có sẵn hiện dòng "Dùng N cách đọc chung" ở
  tab Nhân vật → Cách đọc tên. Đi đúng đường của một lần sửa tay (cùng phép kiểm, máy áp ở ranh giới chương).
- Thẻ "Hai người chung một tên?" không còn hỏi khi một nhân vật chỉ nói thêm "chúng ta" bên cạnh "tôi… cậu" (một người,
  không phải hai) - đo trên 8 chương một cuốn LN: bớt một thẻ hỏi nhầm, các ca nhập người thật vẫn bắt đủ.
- Trang dự án ghi model đã phân tích cuốn ấy ("Phân tích bằng qwen3:8b") - đổi model mặc định thì biết cuốn nào làm bằng model cũ.

## [0.4.11] - 2026-09-30

### Studio (sản xuất sách nói)

- Tab Kịch bản, chương kể ngôi thứ nhất: dòng gợi ý và nút "Soát câu của …" làm nổi riêng câu máy gán cho người kể "tôi" -
  chỗ máy nhầm nhiều nhất (đo trên bộ truyện thử: khoảng 1/3 câu gán cho người kể là của người khác). Người kể theo từng
  chương nếu truyện đổi người kể.
- Từ Việc cần duyệt sang Kịch bản ("Đọc cả N câu…", "Mở trong Kịch bản") rồi bấm Back hay nút "← Về Việc cần duyệt" là trở
  lại đúng thẻ vừa rời, giữ nguyên bộ lọc.
- Hộp "Đổi giọng" hiện giọng đang chờ áp dụng và có "Giữ giọng này" để bỏ lựa chọn bất cứ lúc nào trước khi máy áp - không
  chỉ trong 8 giây của nút Hoàn tác.
- Sách đang tạm dừng: danh sách Dự án ghi "tạm dừng", Thư viện ghi "Đang tạm dừng", thông báo sau mỗi quyết định nói máy áp
  dụng khi sách làm tiếp; hộp "Dừng" nói Dừng hẳn khác Tạm dừng ở chỗ nào (nhả bộ nhớ card đồ hoạ).
- Các phần của một cuốn đứng chung một khung cả khi một phần đang chạy; phần đã đổi tên vẫn mang nhãn "Phần N" trên bìa.
- Bảng chương giữ cột Chương khi cửa sổ hẹp (dưới 1024 px chỉ còn số, tên và trạng thái).
- Sửa nhỏ: hộp Đổi tên đặt con trỏ vào ô tên; tên trong thông báo đổi giọng viết như tiêu đề (không in hoa); tiêu đề thẻ
  dùng nháy cong; câu Hoàn tác của thẻ "Nam hay nữ" nói cụ thể; ô sửa cách đọc tên viết hoa như dòng bên cạnh; màn hẹp: bảng
  chọn người nói / cách đọc trích lại câu vừa chạm, thông báo nằm đầu màn không đè trình phát.

### Điện thoại

- Sách đã tải về điện thoại vẫn gom các phần của "Làm tiếp cuốn này" theo chuỗi thật khi không nối máy tính.
- App điện thoại tự biết có bản mới trên GitHub (hỏi tối đa một lần mỗi ngày): nhắc một lần mỗi bản mới lúc mở app, nút
  "Tải" mở file APK bằng trình duyệt để cài đè - sách và chỗ đang nghe giữ nguyên. Cài đặt có mục "Cập nhật" khi có bản
  mới, và cuối trang ghi bản đang cài.

## [0.4.10] - 2026-09-30

### Studio (sản xuất sách nói)

- Nút "Tạm dừng" / "Tiếp tục" khi sách đang chạy: sách đứng yên sau phần đang làm dở và làm tiếp đúng chỗ ấy, không đổi
  gì - an toàn cả giữa lúc phân tích truyện, nơi "Dừng" rồi chạy tiếp có thể ra một cuốn khác. Hộp thoại "Dừng giữa lúc
  phân tích truyện?" mời tạm dừng thay vì dừng. Tạm dừng vẫn giữ bộ nhớ card đồ hoạ. Lượt chạy bắt đầu bằng bản app cũ
  hơn thì không có nút tạm dừng.
- Máy tính xách tay rút sạc hơn một phút thì Studio tự tạm dừng (chạy pin làm sách rất chậm mà hao pin) và tự làm tiếp
  khi cắm sạc lại; trang sách nói "Tạm dừng · máy đang chạy pin". Bấm "Tiếp tục" để làm tiếp ngay trên pin, hay tắt hẳn ở
  Cài đặt → Studio → "Tạm dừng khi rút sạc". Máy khởi động lại thì sách đã bấm tạm dừng vẫn đứng yên.
- Sách đang làm dở chạy tiếp bằng đúng bản mã đã bắt đầu nó khi app lên bản đổi file khoá chất lượng (trước đây bản mã
  ghim bị bỏ qua); các cuốn khác luôn chạy mã mới nhất của app.
- Danh sách Dự án và Thư viện gom các phần của "Làm tiếp cuốn này" theo chuỗi thật: đổi tên một phần không làm mất nhóm,
  dự án khác tình cờ tên "X · Phần 2" không bị gom vào X.
- Bảng chương ở trang dự án không còn ngắt "2 ngày trước" thành hai dòng.
- Mục "Cách đọc tên", bảng "Tên trong câu" và thẻ "Đọc … là …?" trong Việc cần duyệt hiện cách đọc với chữ đầu mỗi từ viết
  hoa ("Rên-ta-rô" thay cho "rên-ta-rô"); cách đọc đã lưu và ô sửa giữ nguyên.

### Điện thoại

- Studio từ xa trên điện thoại cũng tạm dừng / tiếp tục được sách đang chạy.
- Điện thoại đã bật thông báo Studio báo "Máy tính đang chạy pin" khi máy tính tuột sạc - cả khi máy không làm sách nào
  (điện thoại hỏi mỗi 15 phút và khi mở app).

## [0.4.9] - 2026-09-29

### Nghe sách - máy tính và điện thoại

- Cài đặt → Điện thoại và thiết bị nói cách nghe khi ra khỏi nhà: sách đã tải về điện thoại nghe ở đâu cũng được; muốn
  nghe thẳng từ máy tính hay điều khiển từ xa thì cài Tailscale (hoặc ZeroTier, NetBird) trên cả hai máy, cùng một tài
  khoản, rồi mở Thư viện trên điện thoại một lần ở nhà. Trên điện thoại, màn Tải sách nói điều ấy khi không nối được máy
  tính.

### Studio (sản xuất sách nói)

- "Việc cần duyệt" có thẻ mới "N câu của X ở chương này là của một người khác?": trong truyện kể ngôi thứ nhất, khi một
  nhân vật nói theo hai kiểu xưng hô không bao giờ đi chung câu ("cậu… ta" và "anh… bà") và một kiểu khác hẳn cách người
  ấy nói ở các chương khác - thường là máy đã gán lời một người không tên (bà thầy bói) cho nhân vật có tên (Lucia). Một
  thẻ cho cả nhóm câu: chọn "Vai phụ không tên", một người khác, hay "Người khác…" để đặt tên và có giọng riêng.
- Thẻ nhiều câu (thẻ trên, "Một người hai tên", lời trong 『』) có nút "Đọc cả N câu trong Kịch bản": mở đúng chương tại câu
  đầu của nhóm để đọc đủ ngữ cảnh - không bật ô chọn người nói che chữ như "Tìm trong truyện…".

## [0.4.8] - 2026-09-29

### Nghe sách - máy tính và điện thoại

- Chế độ đọc: "Nghe từ đây" nghe tiếp từ câu đang dừng nếu câu ấy còn trên màn hình, không lùi về câu đầu màn hình.
- Chạm một câu rồi nghe từ câu ấy: thông báo trích câu ("Nghe từ “Cậu ấy nói rằng hôm nay…”") thay cho "Đã tới 0:41";
  nhảy tới dấu trang có ghi chú thì thông báo nói ghi chú ấy. "Quay lại" trên thông báo giữ nguyên.
- Điện thoại học lại các địa chỉ của máy tính mỗi lần mở thư viện: cài Tailscale (hay mạng riêng ảo khác) SAU khi đã ghép
  thì ra khỏi nhà điện thoại vẫn tự nối được. Trước đây địa chỉ chỉ được lưu lúc ghép.

### Studio (sản xuất sách nói)

- Thẻ đã quyết trong "Việc cần duyệt" nói kết quả thay vì lặp câu hỏi: "Giữ: “Arcanist” đọc là “A-rờ-ca-nít”", "Noah là
  nữ", "Câu này của Natasha", "“St. Kati” là Kati". Thẻ gộp tên từng ghi nhầm "“Hai người khác nhau” là Kati".
- "Đã hoàn tác" nói cụ thể điều gì trở lại ("“Lucien” lại đọc là “Lu-si-en”", "Câu này lại là của Ali", hay "Trở lại
  quyết định trước: …").
- Thông báo sau khi sửa (cách đọc tên, người nói, giọng, cách đọc một câu) chỉ nói điều đúng với sách này: sách đang chạy
  thì "máy áp ở ranh giới chương kế tiếp", sách đang dừng thì "thu lại khi sách chạy tiếp", sách đã xong thì "bấm “Áp dụng
  thay đổi”" - trước đây thông báo nào cũng nói cả hai vế.
- Đổi giọng một nhân vật trong hộp chọn giọng cũng có "Hoàn tác" trên thông báo. Dòng "Đã ghi … - chờ áp dụng" trên thẻ
  và trên từng câu ở tab Kịch bản cũng nói theo tình trạng sách như thông báo.
- Cách đọc tên bị từ chối vì sai chính tả tiếng Việt ("Hên-kơ") nói đúng âm tiết sai ("Tiếng Việt viết “cơ”, không viết
  “kơ”") và có nút "Dùng “Hên-cơ”" ngay dưới ô nhập - trước đây chỉ có một câu báo chung.
- Tab Kịch bản trên điện thoại: bảng cách đọc câu và ô chọn người nói mở thành tấm trượt từ đáy màn, rộng hết màn, thay
  cho bảng nổi bị ép sát mép; ô chọn người nói không tự bật bàn phím che danh sách.
- Tên nhân vật máy gõ nửa hoa nửa thường ("LOUise") hiện đúng dạng tên ("Louise"); tên viết kiểu "McDonald" giữ nguyên.

## [0.4.7] - 2026-09-29

### Nghe sách - máy tính và điện thoại

- Cài đặt → Điện thoại nói rõ địa chỉ nào để làm gì: địa chỉ trong nhà, và địa chỉ Tailscale để mở từ bất cứ đâu khi
  thiết bị kia cũng bật Tailscale cùng tài khoản (trước đây các địa chỉ chỉ nối nhau bằng "hoặc").
- Chế độ đọc: câu được cuộn tới không còn nằm khuất dưới thanh đầu; lời nhắc nói rõ chạm câu rồi bấm "Nghe từ câu này".

### Studio (sản xuất sách nói)

- Tab Kịch bản: chọn người nói cho một câu xong cũng có "Hoàn tác" trên thông báo, như trong Việc cần duyệt.
- Mục "Cách đọc tên": gõ tìm tên không còn bị ô "thêm cách đọc" giành con trỏ (gõ "Lan" + Enter từng ghi nhầm một cách
  đọc cho chữ "L"); tên chưa có chỉ hiện nút "Thêm cách đọc cho …" khi không tên nào khớp. Tìm không dấu hiểu cả "đ" và bỏ
  qua gạch nối ("dac lat" ra "Đác-lát"). "Mọi cách đọc tên…" trên thẻ điền sẵn tên của thẻ vào ô tìm.
- Quyết định "giữ như cũ" không còn bị ghi là "chờ áp dụng": thẻ ghi "Giữ “…” - không cần áp dụng" và không tính vào số
  thay đổi chờ áp.
- Tab Kịch bản: bảng cách đọc của câu có lối xuống "Sửa cách đọc N tên trong câu", nút lưu của câu đổi thành "Lưu cho câu
  này", Esc trong ô sửa tên chỉ đóng ô ấy.
- Trình tạo sách: thanh "Quay lại / Tiếp tục / Tạo" luôn nằm trong màn hình; gợi ý dòng ghi công nói rõ file truyện không
  bị sửa.
- Nút nhỏ dễ chạm hơn trên điện thoại; câu mẫu chưa có bản thu chỉ báo một lần; câu mẫu của sách đã chuyển thư mục vẫn
  nghe được.

## [0.4.6] - 2026-09-29

### Studio (sản xuất sách nói)

- Thẻ cách đọc tên trong "Việc cần duyệt" có nút "Mọi cách đọc tên…" mở thẳng mục "Cách đọc tên" ở tab Nhân vật.
- "Hoàn tác" trên thông báo sau mỗi quyết định trong Việc cần duyệt (người nói, nam hay nữ, cách đọc tên, giữ nguyên) và
  sau mỗi lần sửa ở mục "Cách đọc tên": bấm nhầm "Nữ" cạnh "Nam" thì thẻ trở lại như trước khi bấm, kể cả thẻ đã có quyết
  định cũ (quyết định cũ được trả về chỗ). Máy đã kịp đưa quyết định vào sách thì thông báo nói thật và chỉ chỗ đổi lại;
  riêng cách đọc tên thì máy xin lại cách đọc cũ.
- Trình tạo sách phát hiện dòng ghi công người dịch / biên tập ở đầu chương ("TL : NicK", "*Edit: Lắc", "Translator: …"),
  vốn bị đọc như một câu kể, và đề xuất bỏ chúng khỏi phần đọc. Chỉ áp dụng khi bấm "Bỏ khỏi phần đọc"; không bấm thì sách
  giữ nguyên như file truyện. Sách đã tạo trước đó không đổi gì.
- Cập nhật app không còn bắt kiểm lại âm thanh cả cuốn: trước đây số phiên bản của app nằm trong dấu vân tay chất lượng,
  nên sau mỗi lần cập nhật, lần "Áp dụng thay đổi" hay "Làm tiếp" đầu tiên trên một cuốn cũ nhận dạng giọng lại mọi câu
  và dựng lại mọi chương. Đổi thư viện giọng đọc hay nhận dạng vẫn kiểm lại như trước.

## [0.4.5] - 2026-09-29

### Nghe sách - máy tính và điện thoại

- Thẻ "Đang nghe dở" của sách đã nghe hết phần đã có ghi "Chờ chương mới" thay cho nút phát không phát gì.
- Tab Lịch sử: phiên nghe trong cùng một phút ghi một mốc giờ; nút ghi rõ "Nghe tiếp từ mm:ss".
- Chế độ đọc trên điện thoại có nút "Nghe từ đây" (trước chỉ có trên máy tính), lần đầu nhắc "Chạm vào một câu để nghe
  từ câu ấy"; câu đang chọn được gạch chân thay vì đóng khung từng dòng.

### Studio (sản xuất sách nói)

- Tab Nhân vật có mục "Cách đọc tên": mọi tên riêng máy đọc thế nào, bao nhiêu câu có tên ấy, máy đoán hay đã chọn,
  một câu mẫu để nghe. Sửa ngay trên dòng - kể cả tên máy chắc (Việc cần duyệt không hỏi) và cách đã chọn rồi muốn đổi;
  gõ một tên chưa có trong danh sách để thêm cách đọc cho nó.
- Tab Kịch bản: bảng sửa cách đọc một câu có thêm "Tên trong câu" - nghe sai tên ở câu nào sửa ngay ở câu ấy (cho cả
  cuốn). Bảng cao hơn màn nhỏ giờ cuộn được thay vì tràn ra ngoài màn.

## [0.4.4] - 2026-09-29

### Studio (sản xuất sách nói)

- Trang dự án của một cuốn làm nhiều đợt chỉ sang các phần kia: "Phần 1/2 · Phần 2 →", "Phần 2/2 · ← Phần 1".
- Chương chưa làm tới lấy tên theo dòng đầu file truyện, không theo tên file (nguồn đánh số file lệch một so với truyện
  từng làm ranh giới hai phần trông như lặp chương).
- Điện thoại: bốn bước của trình tạo sách nằm một hàng ngang gọn.
- Hộp "Việc cần duyệt" mở nhanh gấp ba (sách 43 chương: 2,1 -> 0,7 giây). Thẻ cách đọc tên bỏ con số "máy chắc 88%" (gần
  như tên nào máy đoán cũng mang đúng số ấy) và dòng "máy gán: …" không liên quan.
- "Làm tiếp cuốn này…" mờ kèm lý do ở dự án chưa phân tích câu nào (không có gì để mang theo).
- Trình tạo sách: chip "N chương đầu" giữ các chương đã bỏ bằng tay và ghi "còn N chương cho đợt sau"; bước xác nhận ghi
  rõ "Là phần 3 của …, nối sau phần 2 · Chương 768 → Chương 817"; khi thư mục chưa có chương mới thì nêu tên thư mục và file
  chương cuối; tải lại trang ở bước 4 không còn về bước 1.
- Hộp "Việc cần duyệt": thẻ đã quyết ở sách đã xong bảo bấm "Áp dụng thay đổi" (không còn "chờ … chạy tiếp"); thẻ nam/nữ
  ghi đúng giọng đang đọc và thông báo nói đúng cái giá của lựa chọn; thẻ gộp tên ghi "“X” là Y - cả cuốn và các phần sau".
- Sách đã xong còn thay đổi chờ áp: chỉ "Áp dụng thay đổi" là nút chính.
- Chương đã làm xong mà file audio bị mất (dời, xoá tay) được ghi "Mất file audio", và trang dự án chỉ đếm chương nghe
  được thật - trước đây vẫn báo "43/43 chương nghe được".

## [0.4.3] - 2026-09-29

### Studio (sản xuất sách nói)

- Danh sách dự án gom các phần của một cuốn ("Tên", "Tên · Phần 2"...) thành một nhóm theo thứ tự phần - truyện dài
  làm nhiều đợt không còn rải thành hàng chục dòng rời.
- Câu hỏi "“Tôi” là ai?" lúc tạo sách nhận ra truyện kể ngôi thứ nhất theo TỪNG CHƯƠNG: truyện chen chương ngoại truyện
  kể ngôi ba (Nageki, Hướng dẫn sinh tồn trong học viện) trước đây bị coi là ngôi ba nên câu hỏi chỉ hiện thành một dòng
  liên kết nhỏ - mà không biết "tôi" là ai thì lời của nhân vật chính dễ bị gán cho người đang nói chuyện với họ.
- Gợi ý tên cho câu hỏi ấy đưa người kể lên trước: tên người khác hay GỌI trong lời thoại mà lời kể hiếm nhắc (người kể
  xưng "tôi" nên lời kể không có tên họ). Yamiyo no Hotaru: "Tomobe" lên đầu, trước đây không có trong gợi ý.
- Hộp "Việc cần duyệt" hỏi thêm "Ai nói câu này?" theo XƯNG HÔ ở truyện kể ngôi thứ nhất: câu dính người kể "tôi" mà cách
  xưng hô ("ta… ngươi", "tớ… cậu") giống một người khác trong chương hơn hẳn. Đo trên 12 chương light novel có đáp án:
  85-96% câu bị hỏi là máy gán sai thật. Truyện kể ngôi ba không bị hỏi (ở đó ai cũng "ta/ngươi").
- Thẻ "vai phụ không tên" không còn tô cam một nhân vật chính như lựa chọn nên chọn (một cú bấm vội từng làm lời của
  "trộm" đọc bằng giọng nhân vật chính); nút giữ ghi "Đúng là vai phụ". Quyết định giữ nguyên ("Giữ…", "Đúng rồi") không
  còn làm tăng số trên nút "Áp dụng N thay đổi".
- Làm tiếp cuốn này: giọng kể của phần trước đứng đầu bước chọn giọng, chọn giọng khác thì được nhắc kèm nút "Dùng lại";
  "Bỏ nối tiếp…" (phân vai lại từ đầu) có nút Hoàn tác. Điện thoại: chip "Đợt này làm" xuống dòng thay vì làm cả trang
  lắc ngang, đổi bước thì về đầu trang, nút "Bỏ chương" luôn hiện.

### Nghe sách - máy tính và điện thoại

- Các phần của một cuốn làm nhiều đợt ("Tên · Phần 2"...) nghe liền như một cuốn: hết phần này tự nghe tiếp phần sau.
  Tập khác của một bộ ("Tập 17") vẫn chỉ hiện nút mời nghe tiếp.
  Đã thử trên Android lúc tắt màn hình: phần sau tự phát.
- Nút trong thông báo ("Hoàn tác", "Ở lại đây") nhìn thấy được ở giao diện tối.
- Nghe thử giọng nhân vật chỉ dừng sách khi câu mẫu phát được thật; chưa có câu mẫu thì báo, sách vẫn phát tiếp.
- Điện thoại: bốn tab của trang sách vừa màn hình, hàng tab còn tab bị che thì mờ ở mép; nút chính một hàng riêng nên
  "Từ đầu" không nhảy chỗ khi bấm phát/dừng. "Từ đầu" khi đang nghe là một cú nhảy như mọi cú nhảy khác - nút ↺ quay
  lại được chỗ cũ.
- Thanh phát ở máy tính không cắt tên chương khi còn chỗ; sách chưa thu xong ghi "Phần đã có 99%" thay vì "Cả cuốn
  99%"; màn cảm ứng không gợi ý phím tắt; Đọc theo mở ra nhảy thẳng tới câu đang đọc thay vì cuộn dài từ đầu chương.
- App không xưng hô với người dùng nữa (bỏ "bạn" ở 15 chỗ).
- Tab Nhân vật của trang sách không lộ nội dung: người chỉ xuất hiện sau chỗ đang nghe được ẩn tới khi bấm "Hiện N
  người…"; dòng việc của Studio ("Chờ áp dụng") không hiện ở phía nghe.
- Tìm sách theo cả tên giọng kể, có nút xoá ô tìm; nút "Nghe tiếp" ở trang sách ghi rõ chương và phút.
- Màn cảm ứng: nút biểu tượng nhỏ có vùng chạm cao 44 px.

## [0.4.2] - 2026-09-29

### Studio (sản xuất sách nói)

- Trình tạo sách có nút chọn nhanh **"Đợt này làm 20 / 50 / 100 chương đầu"** khi truyện có nhiều chương - làm truyện dài
  từng đợt không phải bỏ từng chương một.
- Thẻ "Lời trong 『』 là của một người?" có phạm vi **"Cả cuốn"**: một lần chọn (vd lời 『』 luôn là của linh thể, hay
  luôn là lời người kể) áp cho mọi chương của sách và các phần sau của cuốn - không phải chọn lại từng chương. Nhiều
  cuốn dùng 『』 theo quy ước riêng mà máy không tự đoán được.
- "Làm tiếp cuốn này" bấm ở phần cũ (khi đã có phần sau) giờ nối tiếp từ phần mới nhất, không làm lại các chương phần
  sau đã làm.

## [0.4.1] - 2026-09-29

### Studio (sản xuất sách nói)

- **Làm tiếp cuốn này**: truyện dài làm được nhiều đợt mà không đổi giọng giữa chừng. Ở trang dự án, nút "Làm tiếp cuốn
  này" (hiện khi thư mục truyện có chương mới sau chương cuối; luôn có trong menu "…") mở trình tạo sách đã điền sẵn các
  chương kế tiếp, tên "· Phần 2", giọng kể, chất lượng và người xưng "tôi" của phần trước. Phần mới mang theo giọng của
  từng nhân vật đã gặp, cách đọc tên (kể cả cách đọc đã chọn trong "Việc cần duyệt"), ghim giới tính/tuổi và danh sách
  nhân vật đã biết cho bước phân tích; trình tạo nói trước sẽ mang theo bao nhiêu. Làm được cả từ Studio từ xa
  (điện thoại, trình duyệt đã ghép): chương mới do máy tính tự tìm trong thư mục truyện. Dòng lệnh: `create --seed-from`.
- Gộp hai tên ở thẻ "Một người hai tên" (ví dụ một danh hiệu luôn đi kèm một nhân vật) giờ được nhớ theo TÊN: các phần
  sau của cuốn tự hiểu danh hiệu ấy là người ấy, câu của danh hiệu không có giọng thứ hai và thẻ không hỏi lại.
- Thư viện nghe xếp các phần của một cuốn cạnh nhau như một bộ ("Tên · 3 phần"), và nghe hết phần này thì mời nghe tiếp
  phần sau - trên máy tính, điện thoại và trình duyệt.

### Điện thoại (Android)

- **Nghe trên màn hình xe bằng Android Auto.** Thư viện trên điện thoại (sách đã tải và sách nghe thẳng từ máy tính)
  hiện trong Android Auto: cuốn nghe gần nhất đứng đầu, bấm một cuốn là nghe tiếp đúng chỗ đang dở, mở cuốn để chọn
  chương. App cài từ file APK (không qua CH Play) thì trong Android Auto phải bật chế độ nhà phát triển rồi bật "Nguồn
  không xác định" thì ABook mới hiện.

## [0.4.0] - 2026-09-29

### Điểm chính

- **Làm sách nói từ truyện chữ ngay trên máy tính (Studio)**: model phân tích tự huấn luyện (`abook-analyzer`) nhận ai
  nói câu nào và nói với cảm xúc gì; mỗi nhân vật một giọng riêng trong 25 giọng tiếng Việt; tự nghe lại để bắt câu đọc
  lỗi. Studio tải về một lần khi cần.
- **Sửa được khi máy không chắc**: hộp "Việc cần duyệt" và tab Kịch bản - cách đọc tên, ai nói câu này, giọng, cách đọc từng
  câu. Chỉ thu lại những câu bị đổi, kể cả khi sách đã xong.
- **Nghe trên máy tính, điện thoại Android và trình duyệt** (iPhone, iPad): văn bản đọc theo, chế độ đọc bằng mắt, hẹn giờ
  ngủ, dấu trang, hồ sơ nghe.
- **Máy tính và điện thoại liên thông**: điện thoại nghe thẳng thư viện máy tính qua Wi-Fi hoặc Bluetooth, đồng bộ chỗ
  nghe, chuyển máy đang nghe, điều khiển trình phát từ xa, Studio từ xa.
- **File sách `.abook`**: mỗi cuốn một file, mở được trên máy tính và điện thoại.
- **Dữ liệu ở lại trên máy của bạn**: sách, audio và chỗ nghe không gửi lên máy chủ nào - chỉ đi giữa các máy bạn đã
  ghép; link sách không còn chứa đường dẫn thư mục.
- App Windows tự báo bản mới và tự cập nhật bằng gói có chữ ký.

- **Riêng tư: mã sách không còn chứa đường dẫn thư mục.** Link một cuốn sách (`#/book/…`, cả khi nghe từ xa bằng trình
  duyệt trên iPhone, iPad) trước đây giải ra được đường dẫn thư mục, tức lộ tên tài khoản Windows và tên truyện qua link
  chia sẻ hay ảnh chụp màn hình. Giờ là một mã ngắn không giải ngược được. Link cũ vẫn mở đúng cuốn.
- Studio: **sửa một cuốn đã xong** giờ có đường áp dụng. Sửa người nói, giọng, cách đọc tên hay cách đọc một câu sau
  khi sách đã "Hoàn tất" thì trang dự án hiện nút **"Áp dụng N thay đổi"**. Bấm là chỉ thu lại những câu bị ảnh hưởng,
  không làm lại cả cuốn. Trước đây các thay đổi ấy chờ mãi một "lần chạy tới" không bao giờ đến. Tab Nhân vật ghi
  "Chờ áp dụng: giọng …" dưới người vừa đổi giọng.
- Studio: **"Cần thu lại" thu lại thật.** Ở tab "Cần nghe lại", câu bấm "Cần thu lại" (hay "Thu lại câu này" với câu
  hỏng) được thu lại thành một bản MỚI khi sách chạy tiếp - sách đã xong thì bấm "Áp dụng thay đổi". Trước đây phán quyết
  chỉ được ghi lại mà không gì thu lại. Đổi ý trước khi áp thì bỏ yêu cầu. Câu đọc sai chữ hay sai tên thì sửa ở tab Kịch
  bản (nút ngay dưới câu).
- Studio: **đổi tên và xoá dự án** (nút "…" cạnh "Mở thư mục sách"). Đổi tên chỉ đổi tên hiện trong thư viện, trên
  điện thoại và trong file xuất. Xoá chuyển cả thư mục dự án vào **Thùng rác** của Windows, nên khôi phục được; file
  truyện gốc không bị đụng. Sách đang chạy phải dừng trước. Chỉ làm được trên chính máy tính, không từ Studio từ xa.
- Sách **mở từ file .abook** giờ bỏ được khỏi thư viện (menu "…" của trang sách → "Xoá khỏi thư viện…"): bản đã nhập
  vào Thùng rác, file .abook gốc giữ nguyên - mở lại là nhập lại.
- Điện thoại: **sách đã tải xoá được khỏi điện thoại** để lấy lại chỗ trống (menu "…" của trang sách → "Xoá khỏi điện
  thoại…"). Sách của máy tính hay thiết bị đã ghép tải lại được bất cứ lúc nào, chỗ nghe đồng bộ lại từ máy ấy.
- Studio: chọn truyện **đã có dự án** thì bước đầu báo "Truyện này đã có dự án" kèm nút mở dự án ấy. So nội dung file,
  nên truyện chép sang thư mục khác vẫn nhận ra. Vẫn tạo được dự án mới, ví dụ để thử một giọng kể khác.
- Hộp "Việc cần duyệt":
  - Việc đã quyết thu vào mục "Đã quyết, chờ áp dụng" và không còn tính vào số đếm; nút tô đúng lựa chọn đã bấm.
  - Thẻ "Ai nói câu này" có **"Tìm trong truyện…"**, mở đúng câu ấy ở tab Kịch bản với ô chọn người nói (tìm được mọi
    nhân vật).
  - Nhiều đoạn thoại liền nhau cùng gán một người giờ là **một thẻ**, không còn mỗi cặp một thẻ chồng lên nhau. Thẻ đổi
    các câu xen kẽ (hai người đối đáp) hoặc **cả chuỗi** (độc thoại của một người khác), câu nào sẽ đổi được đánh dấu.
  - Cách đọc bị từ chối báo lỗi ngay dưới ô nhập.
  - Vai phụ trùng tên ở nhiều chương ghi thêm tên chương.
  - Thanh lọc xuống hàng thay vì bị cắt chữ.
- Nghe trên **trình duyệt điện thoại** (iPhone, iPad nghe thư viện máy tính): thanh phát gọn như app Android thay cho
  thanh đầy đủ (ở 375px các nút chồng lên nhau), màn "Đang nghe" xếp dọc - trước đây tràn ngang và không mở được đọc theo,
  danh sách chương hay dấu trang. Cửa sổ máy tính hẹp (dưới ~1024px) cũng dùng thanh gọn; màn "Đang nghe" co cột trái
  để chừa chỗ cho đọc theo.
- Nghe: dòng "Đã nghe hết phần đã có" biến mất ngay khi tua, lùi hay nhảy về một chỗ trước đó (trước đây còn nguyên tới
  khi tải lại trang). Esc đóng màn "Đang nghe" ở bất kỳ đâu. Thông báo có nút "Hoàn tác", "Ghi chú", "Quay lại chỗ cũ"
  hiện đủ lâu để kịp bấm. **Âm lượng được nhớ** qua các lần mở app (trước đây lần nào cũng về 90%); tắt tiếng thì lần
  mở sau về mức nghe được gần nhất.
- Sửa nhỏ từ đợt soát trước phát hành:
  - Lịch đêm chọn giờ theo **24 giờ** ("22:00", không còn "10:00 Chiều").
  - Ghép thiết bị: địa chỉ nên gõ đứng đầu, không còn địa chỉ card ảo (WSL, Hyper-V…). Ô mã chỉ nhận số. Nút "Huỷ ghép"
    đổi thành "Huỷ mã này".
  - Bật điều khiển sản xuất từ xa phải xác nhận.
  - Công tắc đang tắt thấy rõ ở giao diện sáng.
  - Bảng chương và danh sách dự án không vỡ trên màn hẹp.
  - Câu Whisper "nghe ảo" không hiện ở hàng chờ nghe lại.
  - Câu chưa có bản thu chỉ còn nút "Thu lại câu này".
  - Sách chưa có chương nghe được không còn ghi "Đang làm" khi đang dừng. Không xuất được sách chưa có chương nào.

- Làm sách: Studio phân tích bằng **model riêng của ABook** (`abook-analyzer`, học từ đáp án soát tay của dự án) thay cho
  qwen3:8b - đoán đúng người nói nhiều hơn rõ ở light novel và truyện mạng (bộ đo 6 chương LN chưa học: 64% câu thoại đúng
  người, qwen3:8b 49%), mà nhẹ hơn. Thiếu model thì Studio tự tải từ Hugging Face. Sách đang làm dở giữ model đã bắt đầu nó.
- Làm sách: tên nhân vật mà model phân tích viết sai **ở mọi câu** (vd "GAST" cho Glast) được viết lại theo tên trong sách,
  nên danh sách nhân vật hiện đúng tên.
- Làm sách: lời kể nói về **lời nguyền** ("bị nguyền rủa", "lời nguyền rủa") không còn bị đọc bằng giọng tức giận - chỉ
  người đang nguyền rủa ("thầm nguyền rủa", "đáng nguyền rủa") mới là giận. Câu thoại mở bằng "(" ngay sau lời thoại của
  người khác được hiểu là một lượt nói mới, không gộp vào người vừa nói.
- Hộp **"Việc cần duyệt"** hỏi khi một **danh hiệu hay biệt danh** có giọng riêng mà sách luôn viết nó sát tên một người
  ("Thiên Biến Vạn Hóa Krai", "Krai được mệnh danh Thiên Biến Vạn Hóa"): một cú bấm đọc các câu ấy bằng giọng của
  chính người đó. Trước đây chỉ hỏi khi tên ngắn nằm trong tên dài ("Lucien" / "Lucien Evans").
- **Tự chọn đường Wi-Fi hay Bluetooth**: ghép điện thoại với máy tính một lần (qua Wi-Fi hay Bluetooth) là đủ - khi
  cùng Wi-Fi thì đi Wi-Fi, ra khỏi nhà thì tự đi Bluetooth (nếu hai máy đã ghép Bluetooth và máy tính bật Bluetooth),
  không phải ghép lại. Yêu cầu nào hỏng lúc nối qua Wi-Fi thì thử lại ngay qua Bluetooth.
- Làm sách: **chương đổi người kể**. Light novel hay có chương kể bằng "tôi" của một nhân vật khác ("Chương 11: Yuuko
  Hayase" trong một cuốn Kakeru kể). Ở bước "'Tôi' là ai?", Studio tự tìm những chương như thế (tên chương là tên
  một nhân vật chính và chương kể bằng "tôi") và đề nghị đúng người kể cho từng chương; giữ chọn thì chương ấy được
  phân tích với đúng người kể, lời của người kể đọc bằng đúng giọng của họ. Dòng lệnh: `--first-person-chapter 11=TÊN`.
- **Nghe sách của máy tính trong trình duyệt** của bất kỳ máy nào đã ghép - iPhone, iPad, TV, máy tính khác: mở
  `http://<máy tính>:47630`, nhập mã 6 số như ghép điện thoại. Không cần bật "Cho phép điều khiển sản xuất": thiết bị
  chỉ nghe thấy Thư viện, trình phát, dấu trang, đọc theo - không có Studio, không thấy thư mục trên máy tính. Bật
  quyền điều khiển sản xuất cho thiết bị ấy thì Studio hiện ra như trước.
- Bluetooth và điều khiển từ xa **đáng tin hơn**: tua hay đổi chương khi nghe thẳng qua Bluetooth không còn làm kết nối
  nghẽn dần; trả lời chậm (lệnh điều khiển chờ tới 25 giây) không còn bị cắt ngang; bật Bluetooth trên máy tính hay
  điện thoại sau khi đã mở app là tự kết nối được, không phải tắt mở lại. Lệnh "dừng", "phát"... gửi sang máy khác
  không còn rơi khi mạng chập chờn đúng lúc bấm (máy nhận làm mỗi lệnh đúng một lần). Hai điện thoại cùng đời máy đang
  nghe hai thứ khác nhau hiện hai thanh riêng.
- **Kết nối điện thoại với máy tính qua Bluetooth** khi không chung Wi-Fi: ghép hai máy trong Cài đặt Bluetooth của hệ
  điều hành, rồi trên điện thoại vào Tải sách → "Không chung Wi-Fi? Kết nối qua Bluetooth" → chọn máy tính → nhập mã 6 số
  như thường. Nghe thẳng, tải sách, đồng bộ chỗ nghe và điều khiển trình phát đều chạy qua Bluetooth (tải cả chương chậm
  hơn Wi-Fi, nghe thẳng thì đủ nhanh). Cài đặt trên máy tính cho biết Bluetooth đang bật hay tắt.
- **Điều khiển trình phát giữa mọi máy, hai chiều.** Máy tính đang phát sách thì điện thoại (và máy tính khác) đã ghép
  thấy thanh "Đang phát trên <máy tính>" ngay trên thanh phát: dừng/phát, lùi/tới 15 giây, và **"Nghe ở đây"** - máy tính
  tự dừng, điện thoại nghe tiếp đúng chương, đúng giây (nghe thẳng nếu chưa tải). Ngược lại, máy tính thấy và điều khiển
  điện thoại đang bật "Cho máy khác nghe thư viện này", và máy tính khác ở "Máy tính khác"; "Phát trên <máy kia>" chuyển
  cuốn đang nghe sang máy ấy nếu máy ấy có cuốn đó. Lệnh không làm được thì máy bấm được báo lý do. Máy tính phát được
  ngay khi nhận lệnh từ xa, không cần bấm vào cửa sổ trước.
- Studio: **sửa chữ đem đọc của một câu** - câu có lỗi chữ hay cách viết lạ thì mở bảng cách đọc của câu ấy trong tab
  Kịch bản, sửa ô "Chữ đem đọc" rồi lưu: câu được thu lại theo chữ đã sửa, còn sách và phần đọc theo giữ nguyên chữ gốc.
  Xoá ô (hoặc bấm "Trả về chữ của sách") là bỏ sửa.
- Studio: **tạo người nói mới** khi sửa "ai nói câu này" - gõ tên chưa có trong truyện ở ô tìm người nói (tab Kịch
  bản) hay bấm "Người khác…" trên thẻ của hộp "Việc cần duyệt", chọn Nam / Nữ / Không rõ. Trước đây chỉ chọn được người
  đã có giọng - linh thể chỉ nói trong ngoặc 『』 mà máy chưa từng gán câu nào thì không chọn được. Dây chuyền tạo người
  ấy ở ranh giới chương kế tiếp với một giọng riêng, khác giọng những người cùng chương, rồi thu lại các câu đã chọn.
- Làm sách: câu thoại có lời dẫn kiểu “Được,” Liz gật đầu. giờ **đọc bằng giọng nhân vật**. Trước đây câu ấy chỉ được
  nhận là thoại khi lời dẫn dùng vài động từ quen (nói, hỏi, đáp...); "gật đầu", "lầm bầm", "lên tiếng", "giải thích"...
  thì cả đoạn thành lời kể và câu thoại đọc bằng giọng người kể. Gặp nhiều ở truyện dịch từ tiếng Anh/Hàn: gần 1.800 câu
  trong kho thử (Young Master's POV, Nageki). Sách đang làm dở giữ cách tách cũ; sách tạo mới dùng cách mới.
- Máy tính: **app Windows cài bằng một file (~30 MB)**, không cần quyền quản trị, không cài Python hay gì khác vào máy.
  Bấm đúp file `.abook` là mở sách. App tự tìm bản mới mỗi lần mở: có bản mới thì thanh bên hiện "Có ABook x.y.z" -
  bấm "Cập nhật và mở lại" trong Cài đặt là xong (gói có chữ ký, sai chữ ký thì không cài). Gỡ app không xoá sách hay chỗ
  đang nghe.
- Máy tính: **Studio tải ngay trong app** (Studio > Dự án > "Cài Studio", khoảng 20 GB, cần card NVIDIA): từng bước có
  tiến độ, mất mạng hay tắt máy giữa chừng thì bấm lại là làm tiếp. Studio **mang theo mọi thứ nó cần** - Python, thư
  viện, Ollama và model, Git, thư viện C++ của Microsoft - trong một thư mục riêng, không dùng hay sửa gì đã cài trên máy
  (máy đã có Ollama vẫn giữ nguyên Ollama ấy). Gỡ app là gỡ luôn Studio; sách đã làm và chỗ đang nghe giữ lại, trừ khi
  tích ô xoá dữ liệu. Bản app mới cần phần Studio khác thì thẻ "Cập nhật Studio" hiện ra và chỉ tải lại đúng phần ấy.
  Cuốn đang làm dở tiếp tục bằng đúng bản mã đã bắt đầu nó, kể cả sau khi app tự cập nhật.
- Máy tính: **nghe sách trên máy tính khác** mà không phải chép sang. Cài đặt → "Máy tính khác": bấm "Tìm máy trong
  mạng" (hoặc gõ địa chỉ) rồi nhập mã 6 số đang hiện trên máy kia (đúng mã điện thoại dùng). Sách của máy ấy hiện trong
  Thư viện với nhãn "Trên <tên máy>";
  nghe, đọc theo, nhân vật, dấu trang, hồ sơ nghe đều như sách của máy này. Chương được tải lần đầu nghe tới rồi giữ
  lại, nên phần đã nghe vẫn nghe được khi máy kia tắt. Chỗ đang nghe và dấu trang đi hai chiều: nghe
  ở máy nào thì mở ở máy kia cũng tiếp đúng chỗ. Thôi ghép là xoá phần đã giữ.
- Điện thoại: **nghe thư viện của điện thoại khác** - màn Tải sách → "Thiết bị khác" → "Ghép thiết bị" (tự tìm trong
  mạng, hay gõ địa chỉ) và nhập mã 6 số đang hiện trên máy kia. Sách của máy ấy hiện trong Thư viện với nhãn "Trên <tên
  máy>": nghe thẳng, đọc theo, tải hẳn về; chỗ đang nghe và dấu trang đi hai chiều. Ghép được nhiều máy cùng lúc, cả
  máy tính thứ hai; máy tính chính vẫn như trước.
- Điện thoại: sửa lỗi app tự đóng lặp lại khi mở lại trong lúc trình phát còn giữ sách (đọc trạng thái trình phát sai
  luồng).
- Điện thoại: **cho máy khác nghe thư viện của điện thoại** - màn Tải sách → bật "Cho máy khác nghe thư viện này" →
  "Ghép máy mới" hiện mã 6 số và địa chỉ. Máy tính ghép như ghép một máy tính khác (Cài đặt → Máy tính khác; "Tìm máy
  trong mạng" hiện điện thoại với biểu tượng điện thoại) rồi nghe thẳng những cuốn chỉ có trên điện thoại. Điện thoại
  cần đang mở ABook; chỉ sách đã tải về điện thoại. Chỗ đang nghe, tốc độ và dấu trang đi hai chiều như giữa hai
  máy tính: nghe trên máy tính tới đâu, mở điện thoại là tiếp đúng chỗ ấy.
- Tab **"Kịch bản"**: cuối mỗi chương có nút **"Chương này đúng"** - một lần bấm ghi nhận người nói của mọi câu chưa
  ai quyết (trừ câu máy còn nghi). Mỗi câu xác nhận là một nhãn đúng để máy phân tích học.
- Tab **"Kịch bản"**: mỗi câu có nhãn **cách đọc** (cảm xúc và mức, vd "Sợ · mạnh"); bấm vào để đổi cảm xúc, mức,
  hay loại đoạn - lời kể, lời thoại, nội tâm (phím tắt `e` cho câu đang chọn). Lời kể đổi thành lời thoại thì chọn luôn
  người nói; lời thoại đổi thành lời kể thì câu về giọng người kể. Mức được giữ trong tầm giọng đọc được (thì thầm,
  dịu dàng tối đa "Vừa"). Áp ở ranh giới chương kế tiếp; câu đã thu được thu lại.
- Điện thoại: công tắc **"Báo khi sách xong hay có việc cần duyệt"** (màn Tải sách, dưới nút Studio của máy tính).
  Điện thoại hỏi máy tính mỗi 15 phút (cả khi app đã đóng) và mỗi lần mở app, rồi báo: sách đã xong, dừng vì lỗi,
  dừng giữa chừng, hay có thêm việc cần duyệt. Bấm thông báo mở thẳng Studio từ xa đúng cuốn, đúng tab. Cần máy tính
  bật "Cho phép điều khiển sản xuất" và điện thoại có quyền ấy - như chính trang Studio từ xa. Lần bật đầu chỉ ghi
  mốc, không đổ ra tin cũ.
- Studio, tab **Nhân vật**: nút **"Đổi giọng"** trên mỗi nhân vật mở danh sách mọi giọng dùng được, nghe thử từng
  giọng, thấy giọng đang dùng, giọng máy gợi ý cho giọng nam và giọng nữ, và ai cùng chương đang dùng giọng gốc ấy.
  Chọn giọng khác giới là đổi luôn giới của nhân vật. Áp ở ranh giới chương kế tiếp như các sửa khác; câu đã thu của
  người ấy được thu lại bằng giọng mới.
- Hộp **"Việc cần duyệt"**: thẻ **"Nam hay nữ"** và **"Chung giọng"** giờ bấm được. Thẻ nói máy đang đọc nhân vật bằng
  giọng nam hay nữ và cái giá của từng lựa chọn ("giữ giọng đang đọc" hay "đổi giọng, thu lại 3 câu"). Chọn xong,
  dây chuyền ghim giới cho các lô sau và - khi giọng phải đổi - chọn giọng mới đúng cách bước phân vai chọn (không trùng
  bậc giọng với người cùng chương, mọi người khác giữ nguyên giọng), rồi thu lại đúng các câu của người ấy. "Chung giọng"
  đổi giọng người ít câu hơn trước. Không phải dừng sách.
- Hộp **"Việc cần duyệt"**: thẻ **"Một người hai tên"** bấm được - "Gộp vào X" chuyển mọi câu của tên ít câu hơn
  sang giọng của tên nhiều câu hơn (người nghe đã quen giọng ấy, ít câu phải thu lại nhất), "Hai người khác nhau" thì
  thẻ không hỏi lại. Thẻ giờ bắt cả trường hợp tên NGẮN nói nhiều hơn ("Kati" / "St. Kati") mà trước đây bỏ sót.
- Studio có tab mới **"Kịch bản"**: đọc từng chương như kịch bản - câu nào của ai - và đổi người nói của bất kỳ câu
  thoại hay câu nghĩ nào bằng cách bấm tên ở đầu câu (tìm được mọi nhân vật đã có giọng, gõ không dấu cũng được). Câu
  máy nghi có dấu vàng kèm lý do và gợi ý người đáp lại; bộ lọc "Máy nghi" chỉ hiện những câu ấy cùng câu liền trước.
  Máy tính có phím tắt: ↑ ↓ chọn câu, phím số gán người theo dàn của chương rồi sang câu kế. Sửa không dừng sách: áp ở
  ranh giới chương kế tiếp, câu đã thu thì thu lại bằng giọng người mới; câu nào đã ghi hiện "đang chờ", áp rồi có dấu
  tích. Dùng được cả từ điện thoại qua Studio từ xa.
- Hộp **"Việc cần duyệt"** có loại việc mới **"Lượt đối đáp"**: hai đoạn thoại liền nhau không lời dẫn mà máy gán cho cùng một người - đo trên đáp án 7 truyện, 9/10 cặp như thế là máy bỏ lỡ lượt đổi người. Thẻ hỏi câu sau là của ai; truyện kể ngôi thứ nhất thì "tôi" đứng đầu các lựa chọn.
- **Tên mới: ABook** (trước là Ebook Reader), trên máy tính lẫn điện thoại: lối tắt ở thư mục gốc và Start Menu tên
  "ABook" (lối tắt tên cũ tự gỡ khi mở app), cửa sổ khởi động, dữ liệu app ở `%LOCALAPPDATA%\ABook` (tự chuyển từ thư
  mục tên cũ nếu có). Trình khởi động là `_internal\ABook.vbs`; repo GitHub là `ntanhpro1221/ABook` (địa chỉ cũ
  `EbookReader` tự chuyển hướng). Ai đã đăng ký file `.abook` trước khi đổi tên thì chạy lại
  `_internal\scripts\register_file_types.ps1` và `_internal\scripts\install_windows_shortcut.ps1` để trỏ sang chỗ mới.
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
- Máy tính: ABook mở bằng **cửa sổ mới** (giao diện Nghe + Studio mới). Bản chạy từ mã nguồn vẫn mở được giao diện cũ
  bằng `app.py --classic`.

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
- **Studio từ xa**: điện thoại, máy tính bảng hay máy tính khác cùng mạng mở ABook của máy tính trong trình duyệt
  (`http://<máy tính>:47630`) - xem tiến độ, bắt đầu hay dừng, tạo sách, duyệt "Việc cần duyệt" và "Cần nghe lại", đặt
  bìa, nghe sách. Bật trong Cài đặt → Điện thoại và thiết bị ("Cho phép điều khiển sản xuất từ thiết bị đã ghép"), tắt
  mặc định; trình duyệt ghép bằng mã 6 số như điện thoại. Những gì chỉ có nghĩa trên chính máy tính (mở thư mục, đổi
  cài đặt, ghép thiết bị) không làm được từ xa. App Android có nút **"Studio của máy tính"** trong Tải sách - mở thẳng,
  không phải ghép lần hai. Trên màn hẹp, Studio dùng thanh tab dưới đáy và xếp các bảng thành cột.

### Studio (sản xuất sách nói)

- Studio mới: tạo sách theo từng bước, **hàng đợi sản xuất** (cuốn thứ hai chờ thay vì tranh GPU), tiến trình từng giai
  đoạn (phân tích, phân vai, thu âm và kiểm tra).
- **Truyện kể ngôi thứ nhất**: Studio hỏi "Người kể xưng 'tôi' là ai?" và gợi ý tên; model phân tích nhận đúng người nói
  hơn hẳn (thử trên một chương: 34% lên 89%).
- **"Cần nghe lại"**: nghe các câu khâu tự kiểm tra nghi ngờ, bấm Ổn hoặc Cần thu lại.
- **"Việc cần duyệt"**: những chỗ máy không chắc, xếp theo lợi trên mỗi lần bấm - cách đọc tên riêng, nhân vật nam hay nữ,
  người gọi hay người nói, vai phụ không tên, ai nói câu này, bản thu lỗi. Máy vẫn tự quyết và chạy tiếp.
- **Sửa cách đọc tên ngay trong "Việc cần duyệt"**: nghe máy đang đọc tên ấy thế nào, bấm "Đúng rồi" hoặc gõ cách đọc khác.
  Không phải dừng sách: dây chuyền áp ở chương kế tiếp và thu lại đúng những câu đã thu có tên ấy - kể cả sách đã xong.
- **Sửa "ai nói câu này" ngay trong "Việc cần duyệt"**: mỗi người máy nghi là một nút (cùng "Người kể", "Vai phụ không
  tên", "Giữ nguyên"). Câu chuyển sang đúng giọng sẵn có của người ấy và được thu lại ở chương kế tiếp.

### Sửa lỗi

- Tên giọng theo đúng VieNeu hiện hành: "Minh Quân Pro" giờ là **Hải Đăng**, "Anh Khôi" là **Thiện Minh**, "Mạnh Dũng" là
  **Quốc Tuấn**. Sách đã làm không đổi gì, chỉ đổi tên hiện ra.

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
- Truyện viết thoại bằng gạch đầu dòng (văn Việt): câu trả lời không còn bị đọc bằng giọng của chính người vừa hỏi khi
  hai lượt nói liền nhau không có lời dẫn. Thử trên Tắt đèn: 11 trên 112 câu thoại của ba chương.
- Người được gọi theo tên chồng hay tên con ("chị Dậu", "mẹ Dần") không còn bị gộp chung một giọng với người mang tên ấy.
- Tên nhân vật bị viết sai một chữ cái vẫn về đúng giọng của người ấy, kể cả khi cái tên sai tình cờ nằm trong một chữ
  khác của sách ("An Dậu" trong "Văn Dậu"); tên Việt không còn bị nhập nhầm sang một họ khác chỉ vì lệch một chữ cái
  ("Tương" / "Lương").
- Điện thoại: hướng dẫn "Kết nối với máy tính" nêu đủ bước - bấm "Ghép thiết bị mới" trên máy tính thì mã 6 số mới hiện.

### Lưu ý khi nâng cấp

- Sách đang làm dở từ bản trước **không tiếp tục được** (khâu phân tích đã đổi) - tạo sách mới từ cùng nguồn.
- Dữ liệu nghe (chỗ đang nghe, dấu trang, lịch sử) chuyển sang dạng **hồ sơ nghe** độc lập với sách, tự động khi mở app:
  mỗi cuốn đang nghe thành một hồ sơ "Mặc định", máy tính và điện thoại nhận ra là cùng một hồ sơ. Không mất gì.
- Mã sách đổi sang dạng mới (không chứa đường dẫn). Chỗ nghe, hồ sơ nghe, phán quyết nghe lại tự chuyển sang mã mới khi
  mở app lần đầu; bản trước khi chuyển được giữ cạnh file gốc (`*.pre-ids.bak`). Máy tính khác đã ghép tự nhận ra sách
  cũ của máy này dưới mã mới.
- Android: app đổi mã thành `com.ngdtuanh.abook`, nên ABook cài thành **một app mới** bên cạnh "Ebook Reader" cũ, không
  mang theo sách đã tải hay chỗ đang nghe. Ghép nối lại với máy tính, tải lại sách (chỗ nghe đồng bộ từ máy tính về), rồi
  gỡ app cũ.
- Android: APK phát hành ký bằng khoá phát hành của dự án. Điện thoại đã cài một bản ABook thử (dựng từ mã nguồn) phải
  **gỡ bản ấy trước** - Android không cài đè một app khác chữ ký - rồi ghép lại và tải lại sách như trên.

## [0.3.0] và trước

Các bản dây chuyền trước đây (alpha) ghi ở `VERSIONS.md`, kèm lý do và bằng chứng đo cho từng thay đổi.
