# Nhật ký thay đổi

Những gì NGƯỜI DÙNG thấy thay đổi ở mỗi bản phát hành (máy tính và điện thoại cùng một số phiên bản). Lý do kỹ thuật và
bằng chứng đo đạc của từng thay đổi dây chuyền nằm ở `VERSIONS.md`; quy trình phát hành ở `RELEASING.md`.

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/); số phiên bản theo `major.minor.patch`.

## [Chưa phát hành]

### Mạng giữa các máy

- Máy tính dùng thư viện của điện thoại qua Bluetooth khi không chung Wi-Fi (trước đây chỉ điện thoại gọi máy tính được). Ghép
  một điện thoại mới: ở "Máy tính khác" chọn điện thoại trong danh sách thiết bị Bluetooth đã ghép với máy tính (ghép trong Cài
  đặt Windows trước, và trên điện thoại bật "Cho máy khác nghe thư viện này"), gõ mã 6 số. Nghe sách, chỗ nghe và điều khiển trình
  phát đi qua Bluetooth như qua Wi-Fi, vẫn chỉ tin đúng máy đã ghép lúc đầu.
- Điện thoại đã ghép qua Wi-Fi mà Wi-Fi hỏng: máy tính tự tìm điện thoại ấy trong các thiết bị Bluetooth đã ghép (trùng tên) rồi
  đi Bluetooth; Wi-Fi quay lại thì tự về Wi-Fi. Không tự tìm ra thì bấm biểu tượng Bluetooth cạnh máy ấy ("Dự phòng qua
  Bluetooth…") để chọn một lần, hay chọn "Không dùng". Máy chỉ đọc danh sách đã ghép của Windows, không dò sóng. Đã thử trên
  sóng Bluetooth thật với một điện thoại Android (ghép bằng mã, đọc thư viện, tải sách, nối lại sau khi đứt); khi thử tìm ra và sửa
  một lỗi khiến máy tính không thấy ABook trên điện thoại.
- "Máy tính khác": lời hướng dẫn tách riêng hai đoạn "Cùng Wi-Fi" và "Không chung Wi-Fi" (Bluetooth); ở màn hẹp ô địa chỉ máy kia
  rộng cả hàng nên đọc được hết gợi ý.
- Điện thoại: khi bật "Cho máy khác nghe thư viện này", ABook hiện một thông báo thường trực ("Đang cho máy khác nghe thư viện này",
  có nút "Tắt chia sẻ"; bấm nút ấy thì công tắc trong app tắt theo, kể cả khi đang mở app). Trên OPPO (ColorOS) app vẫn bị hệ thống
  "đóng băng" ~30 giây sau khi tắt màn hình dù có thông báo: máy tính gọi qua Wi-Fi được trả lời sau ~19 giây, qua Bluetooth thì
  phải chờ tới lần hệ thống tình cờ đánh thức app (đo thật: tới vài phút). Điện thoại cũng báo tên Bluetooth của nó, nên máy tính
  tự nhận ra điện thoại trong các thiết bị đã ghép dù tên Bluetooth khác tên máy.
- Qua Bluetooth, đang tải sách lớn thì những việc nhỏ (thư viện, chỗ nghe, điều khiển trình phát) vẫn về ngay: trước đây tải 3 MB
  làm chúng chờ 3-4 giây, nay khoảng nửa giây (đo trên điện thoại thật; tải sách chậm đi chừng 15%). Máy tính và điện thoại phải
  cùng bản mới.
- "Máy tính khác": khi điện thoại đang ngủ (ABook trên điện thoại bị hệ thống tạm dừng), máy tính không báo lỗi mà ghi "Điện thoại
  đang ngủ - mở ABook trên điện thoại để trả lời ngay", chờ thêm tối đa 5 phút qua Bluetooth / 1 phút qua Wi-Fi, có nút "Thôi chờ".
- Điện thoại, màn Tải sách: khi đang cho máy khác nghe thư viện, nút "Để máy tính khỏi phải chờ: cho ABook chạy nền" mở trang cài
  đặt của ABook, kèm lời chỉ đường theo hãng máy (OPPO/realme/OnePlus, Xiaomi, Samsung).

### Nhạc nền

- Tab Nhạc nền: "Đổi từ đây" ở đoạn nối tiếp thẳng hàng với "Đổi bài" của các dòng khác; ở màn hẹp, thể loại truyện dài được ghi đủ tên dưới ô
  chọn thay vì bị cắt giữa chữ.
- Tab Nhạc nền của dự án: mỗi đoạn chỉ còn một nút "Đổi bài" và một nút "…" (im lặng, bỏ ghim, không dùng bài này cho cả cuốn), nên các cột thẳng hàng ở mọi dòng. Đoạn dài được cắt mảnh mà vẫn chơi
  tiếp một bài hiện gọn "↳ tiếp bài của đoạn trên"; "Đổi từ đây" ở đó đổi bài từ chỗ ấy trở đi. Sửa một đoạn chỉ hiện "Đang lưu lựa chọn…"; "Chọn lại nhạc" (và đổi thể loại) nói "Đang chọn lại nhạc cho cả cuốn - cỡ nửa phút"
  thay vì lặng lẽ khoá nút (các đoạn khác có thể đổi bài theo cách máy chọn lại - đó là cách chọn nhạc, không phải lỗi). "Thế giới của truyện" đổi thành "Thể loại truyện" và ô chọn không còn bị cắt chữ;
  các nút đọc không khí bằng AI nói theo điều người nghe được ("Chọn nhạc sát không khí hơn", "Đọc lại không khí các đoạn").
- Nhạc của tôi: "Đổi bài" ở từng đoạn cũng hiện "Có vẻ có lời" / "Máy không tự chọn bài này" như Cài đặt; Cài đặt > Nhạc nền hiện dòng "Chưa phân tích" như tab dự án; hai nơi nói cùng một câu
  về bài đã ghim đi theo file sách (.abook / .abookproj, cả sang điện thoại); mô tả không còn nhắc "Sửa sách".
- "Đổi bài" -> "Chọn" cho một đoạn giờ xong gần như ngay (trước đây phải chờ dựng lại nhạc cả cuốn, sách 43 chương ~35 giây), và chỉ cảnh của
  đoạn ấy đổi - các chương khác giữ nguyên cả bài lẫn các bài nối tiếp. Đoạn được chọn lại không lấy trùng bài của cảnh liền trước hay liền sau.

### Studio

- Tạo sách từ file TXT cả truyện: dòng tên truyện đứng một mình ở đầu file không còn thành một chương "Mở đầu" riêng - ở Thư viện nó thành tên sách (có ghi chú), ở Studio nó thành tên sách khi trùng
  Tên sách bạn đã nhập, còn khác thì giữ làm chương để không mất chữ nào. "Tách thành N chương" không còn đặt lại Tên sách bạn đã có. Thư viện "Thêm sách từ file…" tự tích tách chương khi file chắc chắn có
  từ ba dòng "Chương N" và lấy tên truyện từ dòng đầu thay vì tên file; điện thoại làm giống hệt.
- Tạo sách: "Chia thành mấy phần?" thay "Chia thành 1 phần" và ô nhập ghi "từ 2 đến N"; lời mô tả bộ phân tích truyện bỏ chữ kỹ thuật ("model", tên thẻ Ollama chỉ còn là ghi chú nhỏ).
- Hộp "Việc cần duyệt": mỗi mục "Đã quyết, chờ áp dụng" có nút "Hoàn tác" riêng (vai phụ, giới, giọng, người nói, người kể, cách đọc),
  còn đó đến khi máy áp - không chỉ vài giây của thông báo. Thẻ người kể của một đoạn ghi "câu 6" khi chỉ một câu, "Chọn người kể…"
  gợi sẵn các tên có trong đoạn và nhân vật đã có (vẫn gõ tự do được), và sau khi quyết thì tiêu đề nói kết quả ("Đoạn này do Mai kể").
  Thẻ vai phụ cả cuốn không còn mời "Người kể" trước với một lính gác ngôi ba, mà có lựa chọn "Là một người mới tên “Lính gác”".
- "Duyệt trước khi thu" > "Nhân vật và giọng": các dòng cùng tên (ba “Lính gác”) hiện "Cùng tên với người khác trong sách - một người?"
  kèm nút "Gộp vào…". Ở màn điện thoại, phần giới thiệu gập lại để bốn bước hiện ngay màn đầu.
- Sách đang "chờ bạn duyệt" mà máy chủ vừa khởi động lại không còn hiện "Tạm ngưng lúc phân vai" cùng "Tiếp tục tạo" song song khung
  "Duyệt ngay": trang ghi "Chờ bạn duyệt" và nút chính là "Thu âm".
- Trang dự án: chỉ ghi "sắp xong" khi thật sự gần xong; cảnh báo khi dừng giữa lúc phân tích ngắn lại còn vài câu bằng lời thường;
  câu đầu hộp việc không còn tự mâu thuẫn khi sách đang dừng; ở màn hẹp phần đầu trang gọn hơn (các chi tiết phụ gập vào "Chi tiết"),
  nút "Xuất…" không bị cắt và thông báo hiện ở đáy, không đè đầu trang.
- "Nghe thử" cách đọc tên cho biết đang phát, đã xong hay lỗi; lúc máy đang thu sách thì nói rõ nghe thử sau khi xong chương đang làm.
- "Cần nghe lại": dòng phím tắt chỉ hiện khi đang nghe liền; "khớp" nói rõ là khớp với chữ của câu; nút "Sửa chữ đem đọc" nói lời tự
  nhiên; câu hỏng không còn nút nghe vô nghĩa. Thẻ nhân vật xuống dòng thay vì cắt tên và giọng, và "trầm hẳn/sáng hẳn" ghi rõ là
  chỉnh so với giọng gốc.
- Ở màn hẹp (Studio từ xa trên điện thoại, cửa sổ nhỏ): thông báo không còn đè lên thanh tab dưới cùng; ô "Chia thành mấy phần?" không cắt
  tên sách; gợi ý tách file TXT cả truyện hết dấu chấm thừa sau "Chương 3”…".

### Đọc từ và tên tiếng Anh

- Đọc từ và tên tiếng Anh đúng hơn khi giọng chỉ nói được âm tiết Việt (máy tính và điện thoại như nhau; giọng nói được tiếng Anh vẫn
  giữ nguyên chữ Anh): "Beatrice" thành "Bi-a-trít", "Jaxon" thành "Giác-xơn", "Party" thành "Pa-ti", "Lich" thành "Lích", "video"
  thành "vi-đê-ô", "Fire" thành "Phai", "Lyle-kun" thành "Lai-ồ cun"; tên bịa có chữ o như "Docora" đọc "Đo-co-ra" thay vì "Đô-cô-ra";
  OK và TV đọc "ô-kê", "ti-vi". Trên bộ nhãn đo, tên và từ Anh đọc đúng từ 86% lên 91% ở phần dùng để chỉnh luật và từ 73% lên 77% ở
  phần để riêng.

## [0.4.32] - 2026-10-08

### Nhạc nền

- Nhạc của bạn: bài có lời hát được nhận ra và không tự phát làm nền dưới giọng đọc (lời át chữ). Bài ấy hiện nhãn "Có vẻ có lời". Bạn vẫn có thể ghim hay bấm "Vẫn cho máy tự chọn".
- Nhạc của bạn: mỗi bài có một nút để bạn quyết máy có được tự chọn nó làm nhạc nền hay không. "Đừng tự chọn bài này" cho bài nào bạn chỉ muốn ghim tay (kể cả bài máy không nhận ra là có lời); "Cho máy tự chọn lại" để trả về như cũ. Bài đã tắt hiện nhãn "Máy không tự chọn bài này", ghim tay vẫn được.

### Studio

- Chọn người nói ở thẻ "Vai phụ không tên" (hay đọc tên, ai nói câu này) của một sách đã làm xong không còn làm cả trang dự án
  hiện "Không mở được sách" - quyết định vẫn được ghi như trước, nay trang giữ nguyên.
- Phân tích cùng một cuốn bằng cùng một model không còn đổi theo câu hỏi đứng trước: Studio khởi Ollama với bộ đệm câu
  hỏi trong RAM tắt (bộ đệm ấy lấy lại phần đã tính cho câu trước, kể cả sau câu mồi của 0.4.31), và câu mồi không còn
  chung chữ nào với câu hỏi thật. Dừng giữa lúc phân tích rồi làm tiếp giờ ra đúng cùng một cuốn: thử 4 chương, dừng ở
  đoạn 624/955, hai lượt trùng từng chữ (0.4.31: 10 đoạn khác, 4 đoạn đổi người nói). Phân tích chậm hơn khoảng 7–12%.
- Card đồ hoạ hết bộ nhớ giữa lúc phân tích (vd một app khác vừa lấy thêm bộ nhớ card) không còn làm hỏng chương: Ollama
  báo lỗi trước khi trả lời thì máy chờ một lúc cho card trống rồi hỏi lại câu ấy, tối đa hai lần.
- Giọng làm sách đọc chữ như "Nghe ngay": số La Mã ("Chương IV" thành "Chương bốn", "Thế chiến II"), viết tắt ("HP" thành "hát pê"), tiếng reo kéo dài ("Aaaa"),
  kính ngữ ("Ariel-sama"), "~", số kiểu Anh "1,000", mũi tên và ký hiệu theo ngữ cảnh. Chữ đã có trong bảng cách đọc của cuốn vẫn đọc theo bảng. Trên bộ 612 câu
  thử, câu đọc đúng từng chữ tăng từ 31% lên 65%, đọc đúng chữ (bỏ dấu câu) từ 43% lên 86%; ngang với Nghe ngay.
- Truyện kể ngôi thứ nhất mà có đoạn do người khác kể (chương đổi người kể, đoạn chèn giữa hai dòng ngắt cảnh): hộp "Việc cần duyệt"
  hiện thẻ "Chương 195, câu 40–112: có vẻ không phải <tên> kể" ngay sau khi chia câu, với ba nút "Đúng, đổi người kể", "Không, giữ
  nguyên" và "Chọn người kể…". Đồng ý thì phần chưa phân tích của đoạn ấy được nói đúng người kể, máy thôi gán lời người khác cho
  "tôi"; chưa trả lời thì máy giữ nguyên. Chương đã phân tích xong thì thẻ nói rõ lựa chọn chỉ áp khi làm lại sách, và đồng ý một
  đoạn không bắt cả cuốn phân tích lại. Dùng được từ điện thoại điều khiển máy tính; việc hiện thẻ này trong app điện thoại độc lập
  chưa có.

## [0.4.31] - 2026-10-07

### Nghe

- File TXT cả truyện: ô tách chương giờ ghi đúng số dòng "Chương N" có trong file, và nói riêng khi phần chữ trước chương đầu thành một chương "Mở đầu" (ví dụ "Tách theo
  3 dòng “Chương N” (thêm phần Mở đầu - 4 chương)"); trước đây nó gộp cả phần ấy vào số chương nên trông như đếm sai. Máy tính và điện thoại như nhau.
- Bớt chữ "Studio" ở những chỗ người nghe hay gặp: thay đổi chưa áp ghi "Đang chờ máy làm sách" (hay "chờ gửi về máy tính" với sách tải từ máy tính), nghe hết phần đã có thì
  "Chương tiếp theo sẽ nghe được khi máy làm xong chương ấy", và sách đọc bằng giọng có sẵn của máy ghi "Giọng đọc của máy" như trong Cài đặt.
- Sách chỉ có chữ: giọng đọc đọc sai một tên hay một từ thì giữ ngón tay vào chữ ấy ở màn đọc (máy tính: bấm chuột phải) và chọn "Đọc từ này là…": gõ cách đọc
  (vd "Ha ru tô"), bấm "Nghe thử" để nghe bằng giọng đang đọc cuốn này, rồi "Lưu cho cả cuốn" - mọi chỗ có đúng từ ấy đọc theo cách mới, chữ trong sách giữ
  nguyên và chữ đang đọc vẫn sáng đúng chỗ. Danh sách "Cách đọc tên" trong hộp "Sửa sách" để xem, sửa, nghe thử hay bỏ từng từ; cách đọc đi theo file sách khi
  xuất. Hộp "Sửa câu này" của sách nói chưa có Studio cũng nghe thử được cách đọc tên bằng giọng đọc của máy. Máy tính và điện thoại như nhau.
- Hồ sơ nghe chuyển được sang cuốn khác ("Chuyển sang cuốn khác…" trong menu hồ sơ nghe; cuốn chỉ có một hồ sơ thì "Chuyển chỗ nghe sang cuốn khác…" ở menu "…"):
  chỗ nghe, dấu trang và lịch sử đi theo, thành hồ sơ đang dùng ở cuốn kia - tiện khi có bản làm lại của cùng truyện. Máy tính và điện thoại như nhau.

### Điện thoại

- Giọng Supertonic có cả trên điện thoại, đọc như trên máy tính: 10 giọng nam nữ, âm thanh 44 kHz, số và ngày giờ được đọc thành chữ. Giọng không có sẵn
  trong app: vào Cài đặt › Nghe, bấm tải "Giọng Supertonic" (khoảng 400 MB), có thanh tiến độ và nút gỡ. Tải xong máy tự đo xem điện thoại đọc kịp
  không; không kịp thì thẻ nói rõ và chỉ sang "Làm trước" (máy làm sẵn trước khi nghe), hay giọng trực tuyến. Máy tính cũng vậy khi máy chậm.
- Giọng VieNeu, giọng Supertonic và Phân tích nhạc dùng chung phần chạy model (giọng đọc còn dùng chung bộ đọc số, ngày giờ): tải cái nào trước thì
  cái sau không tải lại phần ấy, và gỡ một cái không làm hỏng cái còn lại. Ai đã có Giọng VieNeu hay Phân tích nhạc thì sau khi cập nhật bấm tải lại
  phần dùng chung một lần (khoảng 40 MB với VieNeu, 12 MB với Phân tích nhạc); bản cũ của phần ấy được xoá khỏi máy.
- "Xuất MP3 để nghe ở app khác" có ở điện thoại (menu "…" của trang sách), ra đúng bản xuất của máy tính: một thư mục mang tên sách, mỗi chương đã xong một file
  MP3 có tên sách, tên chương, giọng kể, số thứ tự và ảnh bìa, kèm danh sách phát. Lần đầu bạn chọn thư mục lưu (vd Music), lần sau máy nhớ; muốn đổi thì bấm
  "Đổi thư mục" lúc đang xuất. Việc chạy nền - ra khỏi app vẫn tiếp, tiến độ và nút "Dừng" ở thông báo. Chương chưa làm xong không có trong bản xuất.
- Báo "Sẵn sàng duyệt" khi máy tính phân tích xong một cuốn và đang chờ bạn duyệt giọng, tên lạ, câu chưa chắc trước khi thu; bấm thông báo là mở thẳng màn duyệt. Cuốn đứng
  chờ duyệt không bị báo nhầm là "Đã dừng".
- "Chia sẻ…" trong menu "…" của trang sách: gửi file sách (.abook, kèm những thay đổi của bạn) qua Zalo, Drive, email hay bất kỳ app nào trong bảng chia sẻ của điện thoại.
- Mở được file EPUB, Word (DOCX), PDF và TXT từ app khác: chọn ABook trong "Mở bằng" hay chia sẻ file tới ABook là hộp "Thêm sách từ file" mở sẵn danh sách chương để xem
  trước rồi thêm.
- Cài đặt có nhóm "Giới thiệu": phiên bản đang cài, mã nguồn mở (giấy phép MIT, mở trang GitHub) và danh sách thành phần bên thứ ba cùng giấy phép của từng thứ.
  Máy tính có cùng danh sách ở mục "Giới thiệu" của Cài đặt (nút "Thành phần bên thứ ba").

### Máy tính

- Menu "…" của trang sách có thêm "Xuất M4B cho app sách nói": cả cuốn thành một file `.m4b` mà Apple Books, Smart AudioBook Player, BookPlayer... mở là thấy
  đủ danh sách chương (tên chương thật, nhảy đúng đầu chương), có bìa, tên sách và giọng kể. Máy làm ở nền như "Xuất file sách" - sách dài mất vài phút, tải
  lại trang vẫn thấy tiến độ, xong thì báo nơi file nằm. Chỉ chương đã làm xong được đưa vào; thiếu chương thì thông báo nói rõ có bao nhiêu chương trong file.
- Sách "Trên máy khác" (máy tính): menu "…" của sách có "Tải về máy", như trên điện thoại - máy tải cả cuốn ở nền, tiến độ hiện ngay dưới tên sách, dừng được; xong thì nghe trọn cả khi máy kia đã tắt. Máy kia tắt hay mất mạng giữa chừng thì phần đã tải vẫn giữ, bấm "Tải tiếp" chỉ lấy phần còn thiếu; máy kia thu lại một chương thì "Tải nốt về máy" lấy đúng chương ấy.
- Sách của một máy tính khác giờ sửa được ngay ở máy tính đang nghe (tên sách, bìa, tên nhân vật, tên chương, nhạc nền, cách đọc, người nói...), như điện thoại với máy tính: phần sửa tự gửi về máy giữ sách (hay bấm "Gửi về máy tính"), sửa áp ngay thì máy ấy áp liền, việc cần Studio vào hộp "Thay đổi từ máy khác" (trước đây "Thay đổi từ điện thoại") trong Studio của máy ấy, chờ chủ máy duyệt. Máy kia đang tắt thì phần sửa nằm chờ ở máy này, gửi khi tới được.

### Phát trên loa / TV

- Phát trên loa / TV có hẹn giờ tắt: thanh "Đang phát trên <thiết bị>" (máy tính và điện thoại) có nút trăng như trình phát trong app - chọn 5 tới 90 phút, số phút tự đặt,
  hay "Dừng khi hết chương này"; nút đếm ngược, thêm được 10 phút, tắt được. Đồng hồ chỉ chạy khi loa / TV đang phát. Hết giờ thì thiết bị tạm dừng và chỗ đang nghe
  được lưu; hẹn "hết chương" thì dừng ở cuối chương và lần nghe sau vào thẳng chương kế.
- Điện thoại phát lên loa / TV: màn hình khoá, nút tai nghe / Bluetooth và đồng hồ điều khiển được thiết bị - phát / tạm dừng, lùi / tới 15 giây, chương trước / sau -
  và hiện tên chương, tên sách. Phím âm lượng và thanh âm lượng ở màn hình khoá chỉnh âm lượng của chính loa / TV (khi thiết bị cho chỉnh từ xa; loa, TV giữ
  âm lượng riêng thì phím vẫn chỉnh điện thoại).
- Máy tính phát lên loa / TV mà điện thoại đang hiện thanh "Đang phát trên…": màn hình khoá, tai nghe của điện thoại cũng điều khiển được - phát / tạm dừng, lùi / tới,
  chương trước / sau, dừng. Hết khi máy tính thôi phát.

### Nhạc nền

- Cài đặt có mục "Nhạc nền": kho "Nhạc của tôi" (nhập, xoá, "Phân tích nhạc") dùng chung cho mọi cuốn nên giờ mở thẳng từ đây, trước chỉ có trong hộp "Sửa sách"
  của từng cuốn. Máy tính và điện thoại như nhau.
- Nhạc nền đổi bài khi truyện đổi cảnh, không còn cứ vài phút lại đổi: ở dòng ngăn cảnh, tiêu đề, tiêu đề phụ ("Góc nhìn
  của…", "— Phần hai —") hay câu chuyển thời gian ("Sáng hôm sau…", "Vài ngày sau…"). Trong một cảnh dài, bài đang chơi
  chơi tiếp; hết bài thì chuyển êm sang một bài cùng không khí đúng lúc bài kết thúc, và máy ưu tiên bài đủ dài cho cả
  cảnh, nên ít phải nghe lại một bài. Trong cảnh, nhạc nhích to hay nhỏ dần theo độ căng của truyện. Sách xuất ra mang
  theo các thay đổi ấy, nghe trên máy tính hay điện thoại đều như nhau.
- Nhạc nền đổi bài ít sai chỗ hơn: không còn đổi ở dòng hệ thống / thông báo trong ngoặc (`[…]`, `【…】`) hay ở câu mở đầu
  bằng "trong khi đó", "lúc ấy"; chỉ tiêu đề góc nhìn, dòng bao gạch và dòng ngắt cảnh của sách mới đánh dấu cảnh mới.
- Nhạc nền chọn không khí sát truyện hơn: độ vui/buồn và độ căng của nhạc được đặt theo mức của cả chương, rồi mới thay đổi
  nhẹ theo từng đoạn. Không còn nhảy mạnh giữa các đoạn, và bớt hẳn kiểu chương bình thường mà nhạc vẫn căng. Sách đã dựng
  nhạc từ bản trước vẫn giữ cách chọn cũ cho tới khi bấm "Tính lại cảm xúc nhạc" ở thẻ nhạc của cuốn một lần (cũng để AI đọc
  lại những đoạn vừa đổi chỗ vì cách chia cảnh mới); chương nào AI chưa đọc xong thì vẫn chơi theo cách cũ.
- Nghe trên máy tính: một bài nhạc không tải được (mất mạng) thì 5 phút sau máy tự thử lại như trên
  điện thoại, không còn im đến khi sang đoạn khác.

### Làm sách

- "Cần nghe lại": câu có bản thu riêng đã được dọn sau khi ghép chương giờ vẫn nghe được - máy phát đúng đoạn ấy trong file chương rồi dừng ở cuối câu, nên bấm
  được "Ổn" hay "Cần thu lại", và "Nghe liền" cũng đi qua những câu ấy. Trước đây nút nghe bị tắt.
- "Việc cần duyệt": một vai phụ không tên xuất hiện ở nhiều chương (như "lính gác" ở bốn chương, mỗi chỗ một giọng) giờ
  là một thẻ cho cả cuốn thay vì một thẻ mỗi chương. Thẻ liệt kê mọi câu kèm chương; bỏ chọn câu nào không phải rồi chọn
  một lần: một nhân vật có sẵn, người kể, hay người mới (gõ tên + giới). "Mỗi chỗ một người" giữ nguyên như máy đang làm.
  Một nút "Hoàn tác" lấy lại cả nhóm; sách vẫn chạy tiếp, không phải chờ.

### Studio

- Câu hỏi "'Tôi' là ai?" lúc tạo sách gợi ý đúng người kể ở vị trí đầu thường hơn hẳn: 16/17 truyện ngôi thứ nhất
  để riêng không dùng khi chỉnh (trước 12/17), và người kể luôn nằm trong ba gợi ý đầu. Trước đây gợi ý đầu hay là tước
  hiệu hay tên người khác ("Quỷ Vương", "Lôi Long").
- Dừng giữa lúc phân tích rồi làm tiếp (hay app tắt đột ngột) không còn tự đổi cách app hỏi model: mỗi câu trả lời của
  model được ghi lại, làm tiếp thì dùng lại đúng câu trả lời cũ, và danh sách nhân vật, lượt thử, lời góp ý mang sang
  được dựng lại y như lúc chưa dừng.
- Phân tích cùng một cuốn bằng cùng một model ít đổi theo câu hỏi đứng trước hơn: trước mỗi câu hỏi app gửi một câu
  ngắn không liên quan, để câu hỏi sau không nối tiếp phần Ollama vừa tính cho câu trước (phần ấy làm câu trả lời đổi
  theo câu hỏi đứng trước - người nói, giọng, audio đổi theo). Thời gian phân tích không đổi. Chưa bảo đảm: Ollama
  vẫn có thể lấy lại phần đã tính từ bộ đệm riêng của nó, và việc này chỉ có tác dụng khi không có app khác hỏi cùng
  Ollama trong lúc ấy.

### Cách đọc tên

- Tên bị máy tách thành từng âm tiết ("Kim Jae Hun") trong khi sách viết liền ("Kim Jaehun") không còn thành hai nhân vật hai
  giọng: app gộp về cách viết của sách, nhưng chỉ khi sách viết liền như thế ít nhất ba lần và không chỗ nào viết đúng như máy.

### Âm thanh

- Dòng chỉ có ký hiệu ngăn cảnh trong truyện ("***", "◆", "———", "~~~") giờ là chỗ nghỉ thật: sách nói dừng khoảng 1,5 giây
  khi đổi cảnh thay vì nghỉ ngắn như hết một câu, và nhạc nền đổi đoạn đúng chỗ ấy. Chữ của truyện không bị đổi.
  Nghe ngay (máy tính và điện thoại) cũng vậy: ở dòng ngăn cảnh, trình phát im 1,5 giây thay vì đi tiếp ngay.
  Một dấu "*" hay "-" đứng riêng một đoạn cũng được tính là ngăn cảnh.

## [0.4.30] - 2026-10-07

### Studio

- Dự án mở từ `.abookproj` ở máy cài Studio chỗ khác (hay sau khi thư mục app đổi chỗ) **làm tiếp được**: app tìm model
  cùng tên trong Studio của máy này thay vì báo thiếu model / từ chối làm tiếp. Cài đặt khoá theo sách không đổi.

### Phân vai giọng đọc

- Ngoặc mở mà truyện quên đóng không còn kéo cả đoạn lời kể phía sau thành lời thoại hay nội tâm: ngoặc ‘ đóng bằng
  dấu ' thẳng được nhận, và ngoặc thiếu dấu đóng tự đóng ở cuối đoạn của nó khi đoạn sau mở ngoặc mới.
- Cả dòng bọc trong cặp ' thẳng ('Chắc mình phải chăm chỉ thêm thôi.') đọc bằng giọng nội tâm của người đang nghĩ,
  như ‘…’ - trước đây đọc bằng giọng người kể.
- Câu nói có dấu chấm đặt ngoài ngoặc (“…”.), hai lời thoại liền nhau trên một dòng, và câu nói có ngoặc lồng
  (“… “…” …”) được tách và gán giọng đúng; "vui lòng" không còn bị hiểu là giọng vui, lời tự giới thiệu ("Tôi, Liz, ...")
  không bị nhầm là đang gọi người khác.

### Cách đọc tên

- Tên viết kiểu nói lắp ("A-Azuma-san") không còn làm dừng cả lượt phân tích sách: cách đọc "A A-du-ma-xan" được
  khoá như mọi tên khác. Một cách đọc tên nào đó không khoá được thì app ghi cảnh báo và đọc tiếp cuốn, không dừng.

## [0.4.29] - 2026-10-06

### Studio

- Đổi giọng một nhân vật: ngoài câu mẫu chung, mỗi giọng có thêm nút nghe giọng ấy đọc một câu của chính nhân vật trong sách (máy chọn một câu thoại vừa dài, giọng
  bình thường) trước khi chọn; nghe rồi thì bấm lại là phát lại ngay. Danh sách giọng lọc được Nam / Nữ / Tất cả, và hộp nói trước đổi giọng sẽ thu lại bao nhiêu câu
  đã thu, mất chừng bao lâu. Hộp "Áp dụng N thay đổi" cũng có nút "Nghe thử" cho giọng đang chờ áp, và nói rõ khi thời gian chỉ là ước chừng (cuốn chưa xong chương
  nào để đo). Đang làm sách hay card đồ hoạ bận thì máy báo để nghe thử sau, không chen vào việc đang làm.
- Mở Studio trong trình duyệt hay từ điện thoại, bước "Nội dung" của "Tạo sách nói" có nút "Chọn file", "Chọn thư mục" (trình duyệt máy tính) và kéo thả
  file hay cả thư mục truyện vào khung - thay cho ô dán đường dẫn, ô ấy lui vào "Nâng cao". File gửi lên máy tính, có thanh tiến độ và dung lượng; file không
  phải truyện hay quá 8 MB được nói rõ tên. Chọn cả thư mục thì tên thư mục thành tên sách gợi ý; thư mục chỉ có các thư mục tập con thì mỗi thư mục là một tập.

### Nhạc nền

- "Nhạc của tôi" (máy tính) có thêm tuỳ chọn "Đo cảm xúc nhạc chính xác hơn", mặc định tắt: máy nghe kỹ từng bài bạn nhập hơn (tải thêm 1,27 GB một lần, chỉ khi bạn bật, và chỉ hiện ở máy có từ 8 GB RAM) để chọn nhạc nền
  vui / buồn đúng không khí truyện hơn. Bài nhập vào vẫn dùng được và có số ngay; việc nghe kỹ chạy ngầm vài giây mỗi bài, nhẹ máy, bài chưa tới lượt giữ số cũ, tắt máy giữa chừng thì mở lại làm tiếp.
- Bài nhập đo vui / buồn khớp thang của nhạc có sẵn hơn: ABook cập nhật bộ nghe nhạc ("Phân tích nhạc" báo có bản mới, chỉ tải phần đổi), bài đã phân tích bằng bản cũ vẫn dùng được và bạn bấm "Phân tích lại" khi muốn. Máy có Studio và điện thoại dùng chung một bộ như nhau.

### Nghe

- Nghe hết một cuốn rồi quay lại nghe một đoạn: trang sách giờ có "Nghe tiếp" đúng chỗ bạn dừng (trước đây chỉ còn "Nghe lại từ đầu"), cuốn ấy trở lại thẻ "Đang nghe dở", và thanh tiến độ theo chỗ đang nghe thay vì đứng ở 100%. Máy tính và điện thoại như nhau.
- Màn "Đã nghe hết" không còn mời tập kế hai lần.
- "Xuất file sách" chạy ngầm: bấm là máy đóng gói ở nền, thông báo đếm thời gian; tải lại trang giữa chừng thì mở lại trang sách vẫn thấy nó đang đóng gói, xong rồi thì báo "Đã xuất" kèm nơi file nằm (và nút "Mở thư mục"), mục trong menu "…" ghi lần xuất gần nhất.
- Sách nói có nhạc nền: nút nhạc ♪ ở trình phát (thanh dưới và màn "Đang nghe") bật/tắt nhạc và chọn mức nhạc dưới giọng đọc ngay lúc nghe, khỏi vào "Sửa tên, bìa, nhạc nền…"; trong hộp sửa sách, công tắc ghi rõ "Nhạc nền: Bật" / "Nhạc nền: Tắt".
- "Phát trên thiết bị khác" có cả ở màn "Đang nghe", nên cửa sổ hẹp hay trình duyệt điện thoại cũng chuyển được sang loa / TV / máy khác; khi chưa thấy máy nào, menu nhắc máy kia cần bật và cùng Wi-Fi.
- Màn "Đang nghe" ở cửa sổ thấp: bìa co lại vừa chỗ, không còn đè lên chữ "ĐANG NGHE" và tên chương; nghe hết sách thì dòng tiến độ ghi "Đã nghe hết cả cuốn" thay vì "98%".
- Hẹn giờ tắt: lúc mở lại, tiêu điểm nằm ở mức đang đặt (và mức ấy được tô sáng), không nhảy về "5′" như thể đang chọn; ghi chú trong Cài đặt nói đúng cách nghe thêm trên màn cảm ứng ("chạm màn hình").
- Dấu trang: giờ trong thông báo "Đã thêm dấu trang" trùng với giờ trong danh sách dấu trang (trước đây có thể lệch 1 giây).
- Hộp "Thêm sách từ file…" (máy tính) giờ mở được cả file sách .abook / dự án .abookproj, kể cả khi dán đường dẫn từ trình duyệt; trước đây nó báo "Chưa đọc được file .abook" mà không chỉ sang "Mở file sách".
- Cài đặt gọn hơn trên điện thoại: đầu trang có hàng mục lục bấm nhảy tới từng mục, bốn khung khoá giọng trực tuyến (Azure, Google Cloud, FPT.AI, Viettel AI) gập sẵn - đã dán khoá thì tự mở -, mục "Phím tắt" không hiện trên màn chỉ có cảm ứng. Lời mô tả mục Thư viện nói theo người nghe ("sách thêm vào hay mới làm đều nằm ở đây"), và nút bật kết nối đổi thành "Cho phép thiết bị khác kết nối qua Wi-Fi" - đúng với cả điện thoại lẫn máy tính khác cần ghép.
- Menu "…" của trang sách: mục "Đổi giọng, sửa lời đọc, thu lại chương" bị mờ chỉ còn một dòng nói thiếu gì ("Cần cài Studio", "Cuốn này chưa có dự án Studio"), không còn ba dòng chữ nội bộ.
- Tab Nhân vật: "Gộp vào người khác…" nằm trong menu "…" của từng người với chữ rõ ràng thay cho nút chỉ có biểu tượng; "từ Chương 1" không còn gãy dòng giữa chữ và số.
- Thư viện: hai bản cùng tên không số (bản chỉ-chữ và bản sách nói của một truyện, hay một file nhập hai lần) không còn bị gom thành "4 tập" không số - chỉ cuốn nghe được duy nhất mới tính là Tập 1 của bộ. Tập 1 không đánh số trong tên giờ cũng có nhãn "TẬP 1" trên bìa như Tập 2.
- Thư viện trên điện thoại: tiêu đề "Thư viện" luôn một dòng, hai nút "Thêm sách từ file…" và "Mở file sách" xuống dòng dưới.
- Bìa tự vẽ co chữ theo cỡ bìa: bìa nhỏ (thẻ "Đang nghe dở", hộp "Sửa sách") hiện đủ tên, không cắt chữ giữa chừng hay đè nhãn "TẬP"; bìa sách chỉ-chữ không còn bị kéo dài thành hình chữ nhật dọc.
- "Xuất file sách": menu ghi sẵn file sẽ nằm ở đâu (hay "Bạn chọn thư mục lưu ở bước kế"), và lúc đóng gói thông báo đếm thời gian đã trôi để biết máy chưa treo.

## [0.4.28] - 2026-10-05

### Giọng đọc

- Câu nội tâm (nghĩ thầm) giờ đọc bằng giọng của chính người đang nghĩ, như chủ sách đã quyết; chỉ câu nào không rõ ai nghĩ mới do người kể đọc.
- "Nghe ngay" (máy tính và điện thoại, mọi giọng) đọc ký hiệu theo chỗ nó đứng thay vì một kiểu cố định: "sinh nhật 7/9" là ngày, "10 người/ngày" là "mỗi ngày", "x4" là "nhân bốn", "3x" là "gấp ba", "-20" sau "Độ thiện cảm:" là "âm hai mươi" còn "-50% Nhanh nhẹn" là "trừ", "Q&A" là "hỏi đáp", "★★★☆☆" là "ba sao", "Aki × Rin" là "Aki và Rin", đường dẫn gọn thành "đường dẫn"; dấu chấm giữa, "^", "#", "@", mặt cười và dấu "===" trang trí không còn bị đọc ra thành tiếng nữa, chỉ ngắt nhịp.

### Studio

- Model đọc hiểu truyện mặc định đổi sang `abook-analyzer:v4`: gán đúng người nói hơn hẳn bản cũ - đo trên 11 chương truyện Nhật F1 giọng
  56,0 -> 61,8, 8 chương truyện Hàn 61,4 -> 68,5 (cùng cỡ 4,3 GB). Sách tạo trước giữ model của nó; sách mới tự tải bản mới.
- Truyện dịch dùng ngoặc vuông cho lời nói - "[Về thôi.]", câu nghĩ thầm, bảng thông báo game "[Bạn nhận được 30 điểm kinh nghiệm]", tiếng quái vật "[GDESAAAAA!!]" -
  nay mỗi dòng như thế là một giọng riêng thay vì bị người kể đọc hết (có cuốn gần như cả quyển bị đọc bằng một giọng); ai nói thì máy phân tích đoán như với lời thoại
  thường. Dòng bảng hệ thống trong 【…】 cũng vậy. Dấu ngoặc ấy không được đọc thành tiếng. Ngoặc nằm giữa câu kể ("kỹ năng [Hỏa Cầu]") vẫn là lời người kể.
- Máy phân tích thấy ai vừa nói ở 9 đoạn ngay trước mỗi lượt nó đọc, nên đối đáp không lời dẫn vắt qua hai lượt ít bị gán nhầm người
  hơn (đo trên truyện Nhật: ít hơn hẳn lỗi "câu sau lặp người nói câu trước"); thời gian phân tích như cũ.
- Phân tích bị ngắt giữa chừng (bấm Dừng, tắt máy): trang dự án nay đưa "Làm lại phân tích từ đầu" làm nút chính - chạy tiếp từ chỗ ngắt ra một
  cuốn sách khác so với chạy liền một mạch (người nói và giọng đoạn sau có thể đổi). "Tiếp tục" vẫn còn, kèm lời cảnh báo; hộp "Dừng" nói thẳng là dừng
  giữa lúc phân tích thì mất phần đã phân tích, còn "Tạm dừng" thì giữ.
- Bước "Xác nhận" khi tạo sách ghi rõ model sẽ đọc hiểu truyện (cả khi là mặc định), nói truyện dài có thể mất nhiều giờ, và nhắc nếu còn gợi ý bỏ dòng ghi công chưa chọn.
- "Duyệt trước khi thu": câu mẫu chưa thu không còn nút ▶ báo lỗi - ghi "chưa thu" thay vào đó. Tab "Kịch bản" của chương chưa thu nói rõ vì sao chưa có nút ▶ cạnh câu.
- Hộp "Xuất" ghi cỡ file .abook đã tính cả nhạc nền đi kèm (trước đây báo "khoảng 0 MB" trong khi file thật hàng chục MB); nhạc chưa tải về máy thì nói còn bao nhiêu bài.
- Người nói không tên không còn hiện chữ "Unknown" trong các thẻ "Việc cần duyệt" - gọi là "Vai phụ không tên" như tab Kịch bản - và không bị hỏi "nam hay nữ?".
- Bảng chương: cột "Độ dài" giải thích khi rê chuột là số phút (chương đã thu) hay số câu (chưa thu).
- Hộp "Xuất": nói trước file sẽ lưu ở đâu; lúc đóng gói hiện thanh chạy kèm số chương ngay trong hộp (đóng hộp vẫn được, việc chạy tiếp và báo
  khi xong); xong thì hộp ghi đường file đã lưu và có nút "Mở thư mục". "Chữ sáng theo giọng đọc" nói rõ là tuỳ chọn, mất khoảng vài phút, nút
  đổi thành "Thêm chữ sáng".
- Tạo sách, bước chọn file: gõ đường dẫn có dấu "/" (hay khác dạng với đường máy quét) vẫn nhận ra file đã tách chương - không còn giữ cả file
  lẫn thư mục tách ("0000 Mở đầu", "2 tập") - và thông báo sau khi tách không còn hiện đường dẫn hệ thống. Ô đường dẫn ngắn gọn hơn ở điện
  thoại, nút "Lấy chương" thay cho "Mở"; phần hướng dẫn thành ba gạch đầu dòng, bỏ đoạn lặp trong khung thả file.
- "Nâng cao: model đọc hiểu truyện": model mặc định đứng đầu kèm một dòng giải thích; các model khác nằm riêng dưới "Model khác (thử nghiệm)",
  mỗi cái ghi cỡ tham số, bộ nhớ card cần và nặng / nhẹ hơn mặc định.
- Trang dự án trên điện thoại gọn lại: bìa nhỏ nằm cạnh tên sách, nút gom ít hàng hơn, hàng tab có mũi tên báo còn tab ("Nhân vật", "Nhạc
  nền", "Nhật ký"...) và tự cuộn tới tab đang mở. Giữ chờ duyệt: chỉ còn MỘT nút "Thu âm" ở đầu trang (trước đây "Tiếp tục" và "Thu âm"
  cùng làm một việc), chip ghi "Chờ bạn duyệt"; thẻ đã nằm ở "Duyệt trước khi thu" không hiện lặp ở "Việc cần duyệt".
- Chọn giọng: giọng đang dùng không còn ghi "Chưa ai dùng"; nhóm giọng gọi "Giọng chính" / "Giọng thêm" thay vì tên máy đọc.
- Tên sách gợi ý lấy từ dòng tiêu đề của truyện khi cả truyện nằm trong một file (thay vì tên file); tên chương bỏ số thứ tự đầu file ("0000 Mở
  đầu" thành "Mở đầu").
- Danh sách dự án không ghi tên thư mục thư viện; cùng trạng thái thì chip cùng màu ở danh sách và trang dự án. Tab Nhạc nền: ô chọn không còn
  bị cắt chữ. Tab Kịch bản: không lặp "Bình thường · vừa" dưới mọi câu (chỉ hiện khi khác mặc định hay khi chọn câu), tên người viết giống tab
  Nhân vật. Thông báo nổi dời lên góc trên bên phải, không che nút ở đáy trang.

## [0.4.27] - 2026-10-04

### Studio

- "Duyệt trước khi thu": phân tích xong là Studio báo (thông báo Windows, và ngay trong Studio trên máy tính lẫn điện thoại) và mở một màn
  duyệt ba bước - giọng của những người nói nhiều nhất, cách đọc tên lạ, rồi câu "ai nói" máy chưa chắc ở các chương sắp thu - lúc sửa chưa phải
  thu lại gì. Bật "Chờ tôi duyệt trước khi thu" (lúc tạo sách hay ở trang dự án) thì sách tạm dừng ở đó tới khi bấm "Thu âm"; mặc định không chờ.

### Giọng đọc

- "Nghe ngay" (máy tính và điện thoại, mọi giọng) đọc đúng thêm vài chỗ hay gặp: tiếng gọi viết hoa cả ("ONII-CHAN" thành "o-ni-chan", "OPPA" thành "óp-pa"), "Mr. Lyle" / "Dr. Stone" thành "mister Lyle" / "doctor Stone", mũi tên chữ "1780 --> 1940" hay "A -> B" thành "thành" (mũi tên ngược "<-" thì bỏ).
- "Nghe ngay": mũi tên chữ đọc theo ngữ cảnh - đổi giá trị thì "thành" ("HP: 1780 --> 1940", "Lv 5 -> Lv 6"), chỉ hướng đi, giờ, trang, bước thì "đến" ("Tokyo -> Osaka", "8h -> 10h", "Bước 1 -> Bước 2"); giọng không nói được tiếng Anh đọc "Mr." là "mít-tơ", "Mrs." là "mít-xịt", "Ms." là "mít", "Dr." là "đốc-tơ".

## [0.4.26] - 2026-10-04

### Giọng đọc

- Studio: hộp "Đổi giọng" của một nhân vật có thêm các giọng chủ sách đã nghe đạt của hai máy đọc khác - năm giọng ZeroTTS (Bảo Trang, Kim Oanh,
  Gia Huy, Hữu Đức, Quang Minh) và bốn giọng Supertonic (F1, F3, M4, M5) - xếp thành nhóm riêng sau các giọng VieNeu, có nghe thử. Mỗi máy tải
  thêm một lần ngay trong hộp (ZeroTTS khoảng 860 MB; Supertonic dùng chung bản tải với "Nghe ngay") và chỉ đến tay nhân vật khi người nghe chọn -
  phân vai tự động vẫn y như trước. Tốc độ và độ to của các giọng này được đưa về cùng mức với giọng VieNeu; câu ngắn của Supertonic đọc chậm lại
  cho khỏi nuốt chữ, câu dài của ZeroTTS đọc từng đoạn cho đỡ tốn bộ nhớ.
- Sách làm trong Studio đọc tên theo cùng cách với "Nghe ngay": cuốn gốc Nhật / Hàn đọc tên theo phiên âm chủ sách đã chốt ("Haruto-kun" thành "Ha-ru-tô-cun", "Kyouko" thành
  "Ki-âu-cô"), còn tên tiếng Anh như "Kate", "Michael", "Washington" được đọc nguyên tiếng Anh thay vì Việt hoá thành "Mai-cồ", với mọi giọng. Cách đọc bạn đã chọn cho
  một tên không đổi.
- Thêm cách đọc tên Nhật / Hàn theo tai chủ sách (máy tính và điện thoại): "Ohto" thành "Ô-tô", "Ohka" thành "Ô-ca", "Sanjyo" thành "Xan-giô", "Hiiraghi" thành "Hi-ra-ghi",
  "tokki" thành "tô-ki", "Gangwon" thành "Cang-guôn", "Shinomiya" thành "Si-nô-mi-a", "Futayo" thành "Phu-ta-giô", "Koizumi" thành "Coi-du-mi", "Yejin" thành "Gie-gin",
  "Chaeyeon" thành "Che-gion", "oppa" thành "óp-pa", "unnie" thành "un-ni"; tên "Gesunoh", "Theia", "Fina", "Tio" đọc cố định ("Ghét-xu-nô", "Thi-a", "Phi-na", "Ti-ô").
  Chữ hiện trên màn hình không đổi.
- Dạng Việt hoá từ / tên tiếng Anh (cho giọng không nói được tiếng Anh) theo hơn 150 cách đọc của chủ sách: "William" thành "Guy-li-am", "water" thành "Guốt-tờ",
  "nation" thành "Nây-sừn", "Scotland" thành "Xờ-cót-lừn", "taxi" thành "tắc-xi".
- "Nghe ngay" (máy tính và điện thoại, mọi giọng) đọc đúng thêm nhiều chỗ hay gặp trong truyện dịch: tiếng cười ("haha" thành "ha ha", "fufu" thành "phu phu"), nói lắp ("T-tôi" thành
  "tờ… tôi", "E-em" thành "e… em"), từ quen đọc như người Việt ("sofa" thành "xô-pha", "anime" thành "a-ni-me", "ninja" thành "nin-gia", "3 triệu won" thành "guôn"), "Lv 5" thành "level 5"
  (không đi với số thì đọc "lờ vê"), "1/3" thành "một phần ba", "3-4000" thành "ba đến bốn nghìn", "x2" thành "nhân hai", "$5" thành "năm đô la"; dấu "*" và mặt cười ":3" không còn bị đọc
  ra, gạch ngang dính chữ và khung 【Kỹ năng】 có nhịp ngắt, "ssi" thành "xi". Chữ hiện trên màn hình không đổi.

### Nhạc nền

- "Nghe ngay" (máy tính và điện thoại): sách chỉ có chữ giờ TỰ CÓ nhạc nền hợp với truyện, không cần chọn. App đọc tên sách và vài nghìn chữ đầu của phần truyện rồi chọn một danh sách
  nhạc (tu tiên thì nhạc phương Đông, kinh dị thì nhạc rùng rợn, dị giới thì nhạc phiêu lưu...); trên nửa số sách đo thử, danh sách máy chọn hợp tai hơn danh sách cố định khoảng 24 điểm phần
  trăm (đúng 84% so với 60%). Menu "Nhạc nền" hiện "Máy chọn: <tên danh sách>"; muốn khác thì chọn một danh sách cụ thể, "Tắt" để không nhạc, hoặc "Để máy chọn" để máy chọn lại. Máy mới
  chưa tải danh mục nhạc vẫn chọn được ngay (tên danh sách có ngay, bài nhạc tải khi có mạng). Sách đã chọn nhạc từ trước giữ nguyên lựa chọn; sách nhạc do người làm sách gắn không đổi.
- Danh mục nhạc nền giờ có chữ ký (máy tính và điện thoại): app chỉ dùng danh mục và các mảnh danh sách nhạc đúng bản của ABook, nên không ai tráo được bài hay link nhạc giữa đường tải về.
  Danh mục đổi giữa chừng, bị sửa, hay là bản cũ dựng lại thì app giữ danh mục đã tải trước đó và không bao giờ mở link lạ; lần đầu mà chưa có bản hợp lệ thì "Nghe ngay" vẫn chọn được danh sách
  nhạc, bài nhạc chỉ tải khi có danh mục hợp lệ. Điện thoại cũng đọc nơi đặt danh mục từ cấu hình từ xa có chữ ký như máy tính (làm mới mỗi 6 giờ), nên đổi chỗ đặt danh mục không cần cập nhật app.
  Bản APK nặng thêm khoảng 1 MB.

### Điện thoại

- App điện thoại nhẹ hơn nhiều khi tải về: file cài đặt giảm từ khoảng 9,5 MB xuống khoảng 4 MB (bỏ phần mã và hình ảnh không dùng tới). Mọi việc app làm
  vẫn như cũ: thêm sách từ file, mở .abook, nghe ngay bằng giọng Edge hay VieNeu, nhạc nền, phát nền và tai nghe.

- Widget trình phát trên màn hình chính dùng được trở lại: trước đây không thêm được (khung xem trước xám), và bấm nút trên widget làm app đóng
  đột ngột. Giờ widget hiện bìa, tên sách, tiến độ; các nút phát / dừng, tua 15 giây và hẹn giờ 30 phút đều chạy.

## [0.4.25] - 2026-10-04

### Giọng đọc

- "Nghe ngay" bằng giọng VieNeu (máy tính và điện thoại) đọc tên Nhật / Hàn theo cách người Việt quen thay vì âm tiếng Anh: cuốn mà tên nhân vật là romaji ("Haruto-kun", "Kyouko", "Yamato")
  được app tự nhận ra, và các tên ấy đọc thành "Ha-ru-tô-cun", "Ki-âu-cô", "Gia-ma-tô". Tên Anh / Âu (Kate, Mike, Rose, Anne, Emma), từ tiếng Anh và tiếng Việt vẫn đọc như cũ; cuốn
  không rõ gốc thì không đổi gì. Chữ hiện trên màn hình không đổi.

- "Nghe ngay" (máy tính và điện thoại) đọc thêm những tên Nhật / Hàn viết không theo mẫu: tên viết hoa hết ("KANATA" thành "Ca-na-ta", "NEE-SAN" thành "Ne-xan"), dính liền kiểu CamelCase ("OkabeRintarou" thành "O-ca-be Rin-ta-râu"), có gạch nối và hậu tố ("Seol-Ah", "Tenshi-chwan", "Vương-sama" thành "Vương-xa-ma"; phần chữ Việt, chữ Anh hay viết tắt như "PD-nim" giữ nguyên), và các cách viết quen của tên Hàn ("Shinhyun", "Joo", "Jaemoon", "Ahn"). Tên nào không chắc cách đọc thì vẫn để nguyên. Chữ hiện trên màn hình không đổi.

- Mỗi giọng của "Nghe ngay" giờ ghi rõ nó có nói được âm tiếng Anh hay không. Đo trên 2.040 đoạn (60 từ và tên tiếng Anh, 7 giọng): VieNeu, ZeroTTS,
  Edge và Supertonic đều đọc chữ Anh để nguyên rõ ngang dạng Việt hoá, nên mọi giọng vẫn giữ nguyên chữ Anh như trước. Giọng nào sau này cần thì app chuyển
  sang đọc âm tiết Việt cho riêng giọng đó.

- "Nghe ngay" (máy tính và điện thoại) không còn đọc sai bốn kiểu ký hiệu: "Hmm~" không còn thành "hmm khoảng" ("~" kéo giọng thì bỏ, "3~5" và
  "10,000 ~ 15,000" đọc "đến", "~50" vẫn là "khoảng"); "500,000" và "100,000 yen" đọc đủ "năm trăm nghìn" thay vì "năm trăm"; tên kỹ năng trong
  "<Angel Wings>" đọc trơn, ngắt hai bên, không còn "nhỏ hơn ... lớn hơn"; "Đóng băng / yếu" ngắt ở dấu gạch chéo thay vì "trên". Chữ hiện trên màn hình
  không đổi.

- "Nghe ngay" (máy tính và điện thoại, mọi giọng) đọc đúng ba thứ hay gặp trong truyện dịch: chữ viết tắt toàn hoa đọc bằng tên chữ cái ("HP" thành "hát pê", "NPC" thành "en pê xê";
  "VIP", "ID", "OK", "TV" đọc như từ, còn "LINE", "MAX" vẫn là chữ), tiếng kêu kéo dài thành một tiếng ngân ("Aaaa" thành "a… a", "Hmmm" thành "hừm…", "rồiiii" thành "rồi… ì"),
  và hậu tố gọi dù app chưa nhận ra gốc của cuốn ("Ariel-sama" thành "Ariel-xa-ma", "hiệp sĩ-sama" thành "hiệp sĩ-xa-ma", "Oppa" thành "ốp-pa"). Chữ hiện trên màn hình không đổi.

- Chuẩn bị cho giọng chỉ nói được tiếng Việt (chưa dùng khi đọc): app biết đọc từ / tên tiếng Anh bằng âm tiết Việt theo cách chủ sách chọn - "level" thành
  "le-vồ", "Michael" thành "Mai-cồ", "skill" thành "xờ-kiu", "Mike" thành "Mi-ke"; tên tự đặt không có trong từ điển đọc theo mặt chữ ("Encrid" thành
  "En-cơ-rít"). Bản máy tính mang theo từ điển phát âm gọn (0,8 MB); điện thoại sẽ tải khi cần.

- Cách đọc tên và từ nước ngoài bằng âm tiết Việt (máy tính và điện thoại) chỉ ra những âm tiết viết đúng chính tả tiếng Việt: "queen" thành "quin" thay vì
  "quyn", "Wayne" thành "Oen" thay vì "Uên", "quick" thành "quích"; tên nào máy không viết nổi cho đúng thì giữ chữ gốc thay vì đọc một âm tiết không có trong tiếng Việt.

### Studio: cân bằng giọng

- Các giọng trong cùng một cuốn nghe đều nhau hơn: mỗi giọng VieNeu có sẵn một bộ hằng số đo trước (tốc độ so với điểm giữa của các giọng, độ to về một
  mức chung, màu giọng giữ như đã chọn) và Studio tự áp khi thu âm, thay vì cân từng câu. Câu giận vẫn to hơn, câu thì thầm vẫn nhỏ hơn, câu gấp vẫn nhanh
  hơn - cảm xúc trong một giọng được giữ nguyên.
- Kéo tốc độ giọng bằng một cách mới (WSOLA) giữ giọng tự nhiên: đo trên 3 giọng, kéo 5% không còn mất gì, kéo 10-15% mất rất ít; cách cũ (WORLD) làm giọng
  kém tự nhiên rõ (Mỹ Duyên tụt từ 3,17 xuống 2,10 điểm) và làm nhỏ tiếng một số giọng không đều.
- Sửa lỗi: một bản thu quá ngắn (vài mẫu âm thanh) có thể làm tắt hẳn tiến trình thu âm; nay nó được để nguyên cho bước kiểm loại bỏ.

**Lưu ý khi nâng cấp:** bản này đổi mã khoá chất lượng, nên một cuốn đang làm dở ở bản cũ không tiếp tục được ở bản này - làm lại từ đầu (sách đã xong
không ảnh hưởng).

### Nhạc nền

- Studio (máy tính) chọn nhạc nền sát không khí hơn nếu bạn bật "Đọc không khí cả đoạn bằng AI" ở tab Nhạc (tải thêm một model 3,2 GB, chỉ khi bấm).
  - Một model nhỏ đọc trọn mỗi đoạn để chấm vui / buồn và căng thẳng, thay vì cộng cảm xúc từng câu. Trên 20 chương thử, độ khớp với người chấm tăng ở 15 chương.
  - Việc này chạy ngay sau bước phân tích, khoảng 1 phút GPU cho mỗi giờ sách, và dừng / tạm dừng cùng cuốn sách.
  - Nút "Tính lại cảm xúc nhạc" làm lại cho cuốn đã làm xong. Các đoạn chấm bằng AI có nhãn "AI".
  - Chưa tải model, hoặc trên điện thoại, thì nhạc nền chọn như cũ.

## [0.4.24] - 2026-10-04

### Giọng đọc

- **Giọng Supertonic cho "Nghe ngay" (máy tính)**: Cài đặt › Giọng đọc có thêm "Giọng Supertonic" - mười giọng nam nữ (Supertonic F1, F3, M4,
  M5 xếp đầu) đọc ngay trên máy, không cần mạng, chữ của sách không rời khỏi máy. Bấm "Tải" một lần (khoảng 400 MB; bộ cài không mang gì), tải
  xong máy tự thử vài giây xem có kịp đọc trực tiếp không, và bấm "Gỡ" là lấy lại chỗ. Số, ngày, giờ được đổi thành chữ trước khi đọc. Giọng
  này đọc nhanh nên không cần "Làm trước"; lỗi thì đoạn ấy tạm đọc bằng giọng của máy như các giọng khác.
- **Mất mạng nói gọn và đưa đúng nút**: "Không có mạng - giọng Hoài My cần mạng." Đã tải giọng chạy trên máy (VieNeu…) thì nút chính là "Đọc bằng
  …" (đổi giọng cuốn này rồi đọc tiếp); chưa tải thì "Tải giọng VieNeu" đưa thẳng tới thẻ tải giọng trong Cài đặt. Có mạng lại là khung tự ẩn; ở màn
  Cài đặt khung không che nữa. "Thử giọng" gặp lỗi thì lỗi hiện ngay dưới giọng vừa bấm.
- Thư viện ghi giọng đang đọc từng cuốn ("Đức Trí (VieNeu)", "Hoài My (Edge)") thay cho "Giọng máy đọc". Menu giọng trong trình phát có bóng mờ và dòng
  nhắc khi còn giọng ở dưới. Lúc tải giọng VieNeu, phần trăm không lùi và cỡ mỗi giọng đứng yên (không nhảy từ 313 xuống 297 MB).
- Điện thoại: gỡ giọng VieNeu (hay xoá khoá giọng) khi cuốn đang nhớ giọng ấy thì bấm nghe đọc luôn bằng giọng đang hiển thị (Hoài My), không còn ra
  "Giọng VieNeu chưa tải"; tải lại giọng thì cuốn tự về giọng cũ.
- "Nghe ngay" đọc số La Mã sau danh từ chung thành số ("Trường Phổ thông II" thành "hai", "Chương IV" thành "bốn", "Thế chiến II" thành "hai") thay vì
  đánh vần "i i"; đề mục "I. Mở đầu" đọc "một". Chữ cái đơn chỉ thành số sau từ dùng để đánh số ("Phần V", "thế kỷ X"), nên "ông X", "tia X" vẫn
  là chữ; chữ "I" đầu câu và các chữ viết tắt (CV, MC, VIP) giữ như cũ. Chữ hiện trên màn hình không đổi.

### Thư viện

- Thêm lại cùng một file mà chọn chương khác: bước xem trước nói "Bạn đã thêm file này thành “…” (N chương)" kèm "Mở cuốn đó" / "Vẫn thêm bản mới"
  (máy tính và điện thoại), thay vì lặng lẽ thành cuốn thứ hai cùng tên.
- Tích "Bỏ dòng này khỏi phần đọc" ở trang sách: màn đọc và giọng đọc bỏ dòng ấy ngay cả khi cuốn đang nằm trong trình phát (trước đây kịch bản dựng
  sẵn theo bản cũ có thể ở lại). Chương đang nghe đổi từ lần nghe sau.
- Màn "Đang nghe" phủ kín thì phần bên dưới ra khỏi cây trợ năng (đọc màn hình và phím Tab không lạc xuống đó).
- **Hết sách thì có chỗ đi tiếp (máy tính và điện thoại)**: màn "Đã nghe hết sách" ngoài "Nghe lại từ đầu" còn mời tối đa ba cuốn khác (cuốn đang nghe dở
  trước, rồi cuốn chưa nghe; có bìa nhỏ, tên và tiến độ; bấm là nghe tiếp từ chỗ đã dừng) và nút "Về thư viện".
- **Thêm nhạc của bạn ngay từ menu "Nhạc nền" của trình phát (máy tính và điện thoại)**: mục "Thêm nhạc của bạn…" mở hộp chọn file, nhập xong tự chọn
  "Nhạc của tôi" cho cuốn đang nghe và báo "Đã thêm N bài". Máy không thêm nhạc được (điện thoại nghe thư viện máy tính) thì menu chỉ đường sang máy tính.

### Điện thoại

- Quyền thông báo (Android 13+) không còn chặn lần nghe đầu: tiếng phát trước, rồi một câu nói vì sao ("để có nút tạm dừng và tua ở khay thông báo
  và màn khoá") với nút "Cho phép". Từ chối hay bỏ qua thì Cài đặt › Nghe có một dòng và nút mở cài đặt thông báo của ABook.

## [0.4.23] - 2026-10-03

### Thư viện

- **File TXT cả truyện tách được thành từng chương khi thêm sách (máy tính và điện thoại)**: "Thêm sách từ file…" với một file TXT có từ hai
  dòng "Chương N" trở lên hiện ô "Tách thành N chương theo các dòng “Chương N”", không tích sẵn. Tích thì danh sách chương xem trước đổi theo
  và sách vào Thư viện có N chương (chữ trước chương đầu thành chương "Mở đầu"); không tích thì cả file vẫn là một chương như trước. Chữ của
  truyện không đổi, chỉ chỗ cắt.
- **Chọn chương và đổi tên chương trước khi thêm sách (máy tính và điện thoại)**: bước xem trước của "Thêm sách từ file…" cho tích / bỏ tích từng
  chương (có "Chọn hết" / "Bỏ chọn hết"; bỏ hết thì nút Thêm mờ và nói lý do), bấm tên chương để sửa (Enter lưu, Esc huỷ), và tên dài xuống dòng
  thay vì bị cắt. Mục rất ngắn mà trước đây bị bỏ âm thầm (bìa, trang bản quyền) nay hiện ra đúng chỗ của nó, chưa tích, ghi "rất ngắn - có thể là
  bìa / trang bản quyền" - tích là đưa vào sách. Đổi tên chỉ đổi tên hiện ở thư viện và trang sách; chữ của chương không đổi.
- **Thư viện trống mời thêm sách trước**: nút chính là "Thêm sách từ file…" (nghe ngay), "Tạo sách nói" là nút phụ. Menu "…" của trang sách
  không còn rộng cả màn hình, mô tả tự xuống dòng. Sách chỉ có chữ ghi "Chỉ có chữ · nghe bằng giọng đọc" thay cho dòng nghe như lỗi.

### Giọng đọc

- Khi mất mạng mà máy chưa có giọng đọc không cần mạng, thông báo nói rõ cài giọng ở đâu (Cài đặt của Windows) và có nút "Mở Cài đặt › Giọng
  đọc" để tải Giọng VieNeu. Danh sách giọng trong Cài đặt gom theo mô-đun (không lặp "(VieNeu Nano)" ở từng giọng); giọng VieNeu ghi nam / nữ.
  Giọng VieNeu Nano được mô tả đúng: đọc tốn ít bộ nhớ hơn nhưng file tải nặng hơn. "Sáng đúng từng chữ" đổi thành "Tô đúng từng chữ đang
  đọc"; hướng dẫn lấy khoá giọng trực tuyến giữ tên nút của hãng kèm giải nghĩa tiếng Việt.
- Menu chọn giọng trong trình phát gom giọng theo nhóm như Cài đặt, ghi nam / nữ, có nút "Thử" cho từng giọng và dòng "Thêm giọng…" mở
  Cài đặt › Giọng đọc. Hộp chọn giọng lần đầu chỉ nói "không gửi chữ đi đâu" khi trong danh sách có giọng chạy trên máy.

### Trình phát

- **"Làm trước" giọng trực tuyến trên máy tính**: như trên điện thoại, chọn giọng Edge hay giọng dùng khoá riêng rồi bấm "Làm trước N
  chương tới" trong menu giọng - máy đọc sẵn vào bộ đệm, lên tàu hay máy bay không có mạng vẫn nghe tiếp được (đến khoảng 14 giờ nghe).
- Thẻ "Đang nghe dở" ở Thư viện theo đúng cuốn đang phát. Đang mở màn nghe thì không còn hiện thêm thông báo "Đã nghe hết sách". Dòng
  tiến độ nói rõ: "Đã nghe 10% phần đã có · còn khoảng 33 phút ở tốc độ 1,5×".
- Menu nhạc nền: mô tả không bị cắt, độ dài danh sách phát ghi "dài 8 giờ", chọn xong có xác nhận. Hẹn giờ ngủ: "Dừng khi hết chương
  này" là một nút rõ ràng.

### Sửa lỗi

- **File Word có câu bị xuống dòng giữa chừng không còn đọc thành hai đoạn (máy tính và điện thoại)**: chữ dán từ web hay PDF vào Word
  thường xuống dòng cứng (Shift+Enter) ở cuối mỗi dòng hiển thị, nên một câu bị tách làm hai đoạn và giọng đọc ngừng ở giữa câu. Giờ
  dòng chưa hết câu mà dòng sau viết thường thì được nối lại; thơ (mỗi dòng viết hoa) và thoại từng dòng vẫn giữ nguyên. Chữ của
  truyện không đổi, chỉ chỗ ngắt đoạn.

## [0.4.22] - 2026-10-03

### Thư viện

- **Thêm sách từ file EPUB, Word, PDF hay thư mục TXT để đọc ngay (máy tính và điện thoại)**: ở Thư viện bấm "Thêm sách từ file…", chọn
  file (hay thư mục mà mỗi file TXT là một chương), xem danh sách chương - tên, số chữ, số ký tự - rồi "Thêm vào thư viện". Sách vào Thư viện với nhãn "Chỉ có chữ": mở ra
  đọc được từng chương như một cuốn ebook và nghe ngay bằng giọng máy (mục dưới). Đặt lại tên sách,
  bìa, tên chương như mọi cuốn, và "Lưu thành .abook" ghi ra file sách chỉ có chữ để chép sang máy khác. Thêm lại đúng file đã thêm thì về
  cuốn cũ, không nhân đôi. Máy không bao giờ tự sửa chữ của truyện: dòng ghi công người dịch chỉ hiện ở bước xem trước như một gợi ý.
  PDF phải có chữ (PDF chụp từ máy quét thì nói rõ là chưa đọc được). Trên máy tính có Studio, "Làm sách nói từ cuốn này" ở menu của sách tạo một
  dự án Studio từ đúng chữ các chương ấy.

- **Bỏ dòng ghi công khỏi phần đọc - chỉ khi bạn chọn (máy tính và điện thoại)**: dòng ghi công của người dịch, biên tập ở đầu chương
  ("Trans: …", "Dịch: …") hiện ở bước xem trước kèm ô "Bỏ dòng này khỏi phần đọc", mặc định không chọn. Một dòng lặp ở đầu cả trăm chương
  chỉ cần chọn một lần. Chọn rồi thì màn đọc và giọng đọc bỏ qua dòng ấy; chữ trong sách vẫn còn nguyên, đổi ý lúc nào cũng được ở mục
  "Gợi ý cho phần đọc" trên trang sách.

- **Thêm sách từ file: biết ngay cuốn đã có, tên chương và tác giả đúng như lúc xem trước (máy tính và điện thoại)**: cuốn đã có trong thư
  viện thì bước xem trước nói luôn, kèm "Mở cuốn đó" hay "Thêm bản riêng" (bản riêng giữ tên bạn vừa đặt). Thư mục TXT: tên chương lấy từ
  dòng tiêu đề đầu chương ("Chương 1: Buổi sáng") thay vì tên file, và trang sách, trình phát, màn đọc thấy đúng tên đã xem trước. Tác giả
  trong file EPUB / Word / PDF hiện trên trang sách. Bước xem trước gọn hơn: mỗi chương một con số (số chữ), mục lục tự sinh của file Word
  không còn bị đọc như một chương, file TXT trống được nói ra thay vì lặng lẽ biến mất, PDF chụp từ máy quét báo "PDF này là ảnh chụp, chưa
  có chữ để đọc." Máy tính và điện thoại đọc cùng một file ra cùng một cuốn (kể cả EPUB viết chữ có dấu bằng mã HTML, file Word lưu bằng
  công cụ khác Word, tên chương rất dài trên điện thoại). Nhập cuốn hơn nghìn chương nhanh gấp đôi.
  EPUB gói nhiều chương trong một file (mục lục trỏ vào từng đoạn của file ấy) giờ tách đúng thành từng chương theo mục lục, thay vì gộp
  thành một chương dài mang tên chương đầu. Trên điện thoại, bước xem trước không tự bật bàn phím che mất nút "Thêm vào thư viện".

- **Nghe ngay: file TXT mỗi dòng một đoạn không còn dồn cả chương thành một đoạn (máy tính và điện thoại)**: file chỉ có một dòng trống
  (sau tên chương) trước đây bị đọc như một đoạn khổng lồ - chờ rất lâu mới có tiếng, có khi không đọc được. Nay mỗi dòng là một đoạn.

- **Nghe ngay: máy đọc to sách chỉ có chữ, chữ đang đọc sáng lên (máy tính và điện thoại)**: sách vừa thêm từ file có nút "Nghe ngay" -
  không cần phân tích hay cài thêm gì. Giọng mặc định là Hoài My của Microsoft Edge (cần mạng; có thêm giọng Nam Minh), lần đầu dùng app
  hỏi trước khi chữ của đoạn đang đọc được gửi tới Microsoft (kể cả khi chương có audio vừa hết và sắp tự sang một chương chỉ có chữ: app
  đứng ở đầu chương ấy chờ bạn bấm phát); mất mạng thì đoạn ấy chuyển sang giọng của máy (Windows hay Android) mà không dừng.
  Màn đọc sáng đoạn và từng chữ đang đọc như "Đọc to" của Edge; bấm vào chữ nào thì đọc từ đúng chữ ấy. Đọc trước vài đoạn nên không
  phải chờ giữa các đoạn, đoạn đã đọc được giữ lại để nghe lại không cần mạng. Tốc độ, hẹn giờ ngủ, nhớ chỗ đang nghe như
  sách nói; trên điện thoại tắt màn hình vẫn đọc tiếp và tự sang chương sau, điều khiển được ở màn hình khoá và tai nghe, thanh tiến
  độ trong thông báo kéo được theo cả chương. Giọng sang chương sau thì màn đọc đang mở chương ấy cũng sang theo. Đọc hết cuốn rồi bấm
  Phát ở màn hình khoá là nghe lại từ đầu, như nút "Nghe lại" trong app.

- **Giọng VieNeu: nghe ngay bằng giọng hay mà không cần mạng (máy tính)**: Cài đặt → Giọng đọc có mục "Giọng VieNeu" để tải thêm giọng VieNeu
  đọc ngay trên máy - chữ của sách không rời khỏi máy. Chọn Giọng VieNeu (25 giọng, âm thanh 48 kHz), Giọng VieNeu Nano (11 giọng, nhẹ
  hơn cho máy yếu) hay cả hai; app ghi "Khuyên dùng" cho loại hợp với máy của bạn. "Sáng đúng từng chữ" (đánh dấu sẵn) tải thêm bộ căn
  chữ để chữ đang đọc sáng đúng lúc; không tải thì máy ước theo âm tiết. Dung lượng ghi là phần máy còn thiếu - phần đã có (của Phân
  tích nhạc hay Studio) không tải lại. Tải xong máy tự thử vài giây và nói giọng có kịp tốc độ nghe không; không kịp thì đề nghị đổi
  sang giọng nhẹ hơn - chỉ đổi khi bạn bấm. Giọng mới hiện ngay trong nút Giọng đọc lúc nghe. Có bản mới thì một lần bấm chỉ tải
  phần đổi. Máy không kịp đọc trực tiếp vẫn nghe được giọng VieNeu: nút Giọng đọc có "Làm trước các chương tới" - máy đọc sẵn ở nền
  (việc đang nghe luôn được ưu tiên), nói rõ còn bao lâu, bấm "Dừng làm trước" là thôi. Trên điện thoại "Làm trước" có cho cả giọng
  trực tuyến (Edge, giọng dùng khóa của bạn): làm sẵn ở nhà rồi nghe trên tàu điện, máy bay mà không cần mạng. Điện thoại làm cả khi app
  đã đóng, mặc định chỉ khi đang cắm sạc (tắt được ở ô "Chỉ khi đang sạc"), giọng trực tuyến chỉ làm khi có Wi-Fi, pin yếu thì chờ; báo
  "Đã sẵn sàng 3/5 chương · còn khoảng 12 phút" ở nút Giọng đọc và ở thông báo, nói đang chờ gì (cắm sạc, Wi-Fi), và trước khi bấm cho
  biết máy cần bao lâu. Chương đã làm xong có dấu "Đã làm sẵn" trong danh sách chương; nghe trực tiếp không đẩy chúng ra khỏi bộ nhớ
  trước khi bạn nghe tới. Tắt app hay khởi động lại máy thì làm tiếp đúng chỗ. Mất mạng giữa chừng thì dừng và nói rõ - phần đã xong vẫn
  giữ; chương làm trước luôn đọc bằng đúng giọng bạn chọn, không bao giờ xen giọng khác.

- **Giọng VieNeu trên điện thoại**: Cài đặt → Giọng đọc có cùng mục "Giọng VieNeu" để tải giọng đọc ngay trên điện thoại, không cần mạng.
  Điện thoại được khuyên Giọng VieNeu Nano (nhẹ hơn); Giọng VieNeu chỉ được khuyên khi lần tự thử sau khi tải cho thấy máy đủ nhanh. Dung
  lượng ghi là phần điện thoại còn thiếu (thư viện chạy model của "Gói nhạc" đã có thì không tải lại); đang dùng dữ liệu di động thì app
  nhắc trước. Mỗi giọng gỡ được để lấy lại chỗ. Điện thoại tầm trung chưa đọc kịp trực tiếp (máy đo thử đọc chậm khoảng 1,8 lần so với tốc độ nghe) - app nói rõ và gợi ý "Làm trước", cách dùng tốt nhất trên máy loại này. Giọng
  VieNeu chưa đọc được (chưa tải xong, thiếu bộ nhớ) thì đoạn ấy tạm đọc bằng giọng của máy, không bao giờ gửi chữ ra mạng.

- **Cài đặt → Giọng đọc: chọn giọng mặc định, nghe thử, và dùng giọng trực tuyến bằng khóa của bạn (máy tính và điện thoại)**: mục mới
  liệt kê mọi giọng đọc được cho "Nghe ngay" - Edge, giọng của máy, và giọng của các dịch vụ bạn có tài khoản - kèm gợi ý giọng nam / nữ,
  nút "Thử giọng" đọc một câu mẫu, và chọn một giọng làm mặc định cho các cuốn chưa chọn giọng riêng (giọng riêng của từng cuốn vẫn đổi ở
  nút "Giọng đọc" trong trình phát). Ở "Giọng trực tuyến dùng khóa của bạn", dán khóa của Azure Speech (kèm vùng), Google Cloud, FPT.AI hay
  Viettel AI rồi bấm "Kiểm tra": khóa dùng được thì giọng tiếng Việt của dịch vụ ấy hiện trong danh sách giọng. Azure và Google sáng đúng
  từng chữ khi đọc; FPT.AI và Viettel AI sáng từng chữ theo ước lượng. Khi đọc, chữ của sách được gửi tới dịch vụ đó và dịch vụ có thể tính
  tiền vào tài khoản của bạn khi vượt phần miễn phí - app nói rõ điều này; khóa chỉ lưu trên máy (trên điện thoại được mã hoá), chỉ hiện 4
  ký tự cuối. Khóa hết hạn mức hay bị từ chối thì đoạn ấy tạm đọc bằng giọng Edge, rồi giọng của máy, không dừng, và app báo một lần.

- **Nghe ngay có nhạc nền: chọn một danh sách nhạc cho cả cuốn (máy tính và điện thoại)**: sách chỉ có chữ có mục "Nhạc nền" ở menu
  của sách và ở trình phát lúc đang nghe: Tắt (mặc định), một trong 12 danh sách nhạc theo kiểu truyện - kỳ ảo phiêu lưu, kỳ ảo êm
  đềm, học đường, lãng mạn, hài hước, hành động, kinh dị, trinh thám, tiên hiệp - cổ phong, khoa học viễn tưởng, buồn, êm để ngủ -
  hay "Nhạc của tôi". Các bài nối nhau, chuyển êm, nằm dưới giọng đọc như nhạc của sách nói, và chơi tiếp qua các chương thay vì
  bắt đầu lại mỗi chương; mở lại sách là nghe tiếp đúng bài. Lựa chọn nằm trong phần sửa của cuốn nên đi theo khi "Lưu thành .abook"
  hay gửi sang máy kia. Lần đầu cần mạng để tải danh sách và bài; bài đã tải thì nghe lại không cần mạng.

### Cài đặt

- **Bộ cài ABook trên Windows chỉ còn mang phần nghe (bớt khoảng 16 MB)**: từ điển phát âm tiếng Anh và 21 bản nghe thử giọng
  đọc chỉ Studio dùng nên không còn nằm trong bộ cài; khi bạn bấm "Cài Studio" chúng được tải cùng (bước đầu tiên, 15 MB) và
  nghe thử giọng vẫn nghe được như cũ. Máy chưa cài Studio thì danh sách giọng không hiện nút nghe thử, thay vì báo lỗi. Bộ cài
  cũng bỏ phần thư viện ảnh và Python không dùng đến (codec ảnh AVIF, bộ vẽ chữ, công cụ gỡ lỗi...); đặt ảnh bìa vẫn nhận PNG,
  JPEG, WebP, GIF và BMP, đúng cỡ và chất lượng như trước.

### Studio

- **Nghe sách, chữ đang đọc sáng lên**: ở chế độ đọc theo (máy tính và điện thoại), trong câu đang đọc chữ nào đang vang lên thì sáng riêng
  chữ ấy, đi theo giọng đọc từng chữ một. Studio căn từng chữ vào audio lúc đóng gói sách (model nhận dạng tiếng Việt chạy ngay trên máy,
  khoảng 1-2 giây cho mỗi phút audio; máy chưa có model thì chia theo âm tiết và tự dò chỗ ngắt hơi), nhớ kết quả nên đóng gói lại không
  căn lại. Sách đã làm từ trước: hộp Xuất > File .abook có nút "Căn từ cho sách đã làm". Sách chưa căn vẫn sáng cả câu như cũ. Model nằm
  trong Studio (thêm một bước 122 MB), không nằm trong bộ cài chỉ-nghe.

- **Tạo sách từ file Word (DOCX) và PDF, không chỉ TXT và EPUB**: chọn một file `.docx` hay `.pdf` (hay cả thư mục chứa chúng) ở bước chọn
  chương, máy tách thành các chương rồi bạn xem danh sách - tên chương, số chữ và số ký tự - trước khi tạo. Word: chia theo tiêu đề
  "Heading 1/2" (không có thì theo các dòng "Chương N"). PDF: bỏ tiêu đề chạy và số trang lặp ở đầu / cuối mỗi trang, nối các dòng
  bị ngắt thành đoạn văn, chia chương theo các dòng "Chương N". PDF chụp từ máy quét (chỉ có ảnh, không có chữ) thì nói rõ là cần OCR,
  chưa đọc được. EPUB giờ cũng lấy tên tác giả, ngôn ngữ và bìa, và nói trang nào chỉ có ảnh nên bị bỏ. Máy không bao giờ tự sửa chữ của
  truyện: dòng ghi công người dịch ở đầu chương chỉ được GỢI Ý bỏ, bạn bấm đồng ý mới bỏ. Đọc file TXT cũng nhận thêm UTF-16.

- **Thay đổi từ điện thoại gửi về, và hộp thư chờ duyệt**: điện thoại đã ghép giờ gửi được phần sửa của một cuốn về máy tính.
  Tên sách, bìa, tên nhân vật, tên chương và nhạc nền (kể cả bài "Nhạc của tôi" điện thoại đã ghim - ABook chép bài vào kho nhạc
  của máy này) được áp NGAY, bằng đúng các hàm Studio dùng. Còn những việc cần Studio - cách đọc tên, ai nói câu nào, giọng,
  thu lại một câu - thì tuỳ điện thoại: nếu bạn đã cho nó điều khiển sản xuất từ xa (Cài đặt) chúng thành yêu cầu thật trong
  "Áp dụng thay đổi"; nếu không, chúng nằm trong khung "Thay đổi từ điện thoại" ở tab "Việc cần duyệt" của cuốn, mỗi việc có
  nút Áp dụng / Bỏ qua (và "Áp dụng tất cả" / "Bỏ qua tất cả" cho từng điện thoại). Không việc nào tự áp; "Áp dụng" cũng chỉ
  biến việc thành yêu cầu - chưa thu lại gì. Hai nơi cùng sửa một mục thì bản đến sau thắng, nhưng nếu bạn đã đổi mục ấy kể từ
  lần điện thoại gửi trước thì khung ghi rõ "máy tính đã có bản riêng, đã thay bằng bản từ điện thoại". Chỉ điện thoại đã ghép,
  chỉ sách có trong thư viện, và gói gửi bị kiểm như một file sách của người lạ (sai một chỗ là từ chối cả gói, không áp gì).

- **Mở file `.abook` đã sửa của chính dự án**: bài nhạc người nghe ghim vào sách giờ cũng được áp - bài được nhập vào "Nhạc của tôi" của máy này (không trùng bản) rồi ghim đúng đoạn; bài nào thiếu file thì bỏ qua và nói rõ lý do.

- **Nhập nhạc không còn phải đợi tải gì, và bộ cài nhẹ hơn**: nhập “Nhạc của tôi” đọc tên bài, nghệ sĩ, độ dài ngay trên máy, không cần ffmpeg
  nữa. Phần nghe nhạc để hiểu không khí của bài (ffmpeg, thư viện chạy model, model: ~117 MB) giờ là một mô-đun “Phân tích nhạc” gộp một
  nút, một thanh tiến độ, một dung lượng; chỉ tải khi bạn bấm, không nằm trong bộ cài (bộ cài không còn mang numpy và onnxruntime, ~25 MB).
  Chưa tải thì bài nhập vẫn nghe, ghim tay, đi theo sách .abook như thường - chỉ chưa có “Đã phân tích” và chưa đo độ to (nhạc nền dùng mức
  mặc định). Máy có Studio chỉ tải phần model. Có bản mới thì báo “có bản mới - N MB”, một lần bấm chỉ tải phần đổi, và không tự phân tích
  lại các bài cũ (nút “Phân tích lại N bài bằng bản mới”).

- **File dự án `.abookproj` nhỏ hơn, mở được và lưu được cả trên điện thoại**: audio chương, câu mẫu và bìa không còn nằm hai lần trong file (bản chép giống hệt chỉ còn là một dòng ghi chú). File thêm ba bản chụp chỉ đọc của "Việc cần duyệt", mục lục kịch bản và "Cách đọc tên", nên điện thoại (hay máy Windows chưa cài Studio) cho xem được mà không mở sổ dự án. Điện thoại mở file dự án để nghe, sửa tên sách / bìa / tên nhân vật / nhạc như mọi cuốn, rồi "Lưu" ra lại đúng file dự án - phần xưởng đi theo nguyên vẹn. Mở file của một dự án đã có trên máy tính thì không tạo dự án thứ hai: các thay đổi trong file chờ bạn bấm "áp vào dự án". Một cuốn sách `.abook` cũng lưu thành `.abookproj` được: file chỉ có phần nghe, và máy có Studio mời "Dựng xưởng" - tạo dự án mới từ chữ, giọng nhân vật, tên bạn đặt và những việc bạn ghi cho Studio (làm lại toàn bộ audio; nguồn chương gốc, lịch sử phân tích, từng câu đã thu không có trong file). File dự án của các bản dev cũ không còn đọc được: mở bằng bản đã gói rồi gói lại.

### Điện thoại và thiết bị

- **Điện thoại tự nghe nhạc bạn nhập để hiểu không khí của bài**: ở “Nhạc của tôi” có nút “Phân tích nhạc (N MB)” - một nút, một dung
  lượng, tải một lần, chỉ khi bạn bấm (không bao giờ tự tải, và app nhắc nếu bạn đang dùng dữ liệu di động). Tải xong, các bài đã
  nhập từ trước được nghe nốt ngay trên điện thoại, bài nhập sau được nghe ngay lúc nhập, không cần mạng và không gửi nhạc đi đâu.
  Bài chưa nghe được (quá ngắn, file lạ) vẫn hiện “Chưa phân tích”, ghim tay như trước; việc nhập không bao giờ phải chờ việc phân tích.
  Phần chạy model không nằm trong app (app vẫn ~7 MB, không phải 31 MB): nó là một phần của gói tải ấy.
- **“Phân tích nhạc” có bản mới thì báo và chỉ tải phần đổi**: khi bản app mới mang model hay thư viện khác, “Nhạc của tôi” hiện “Phân tích
  nhạc có bản mới - N MB”; bấm một lần chỉ tải phần đổi. Bản cũ vẫn chạy cho tới lúc đó. Các bài đã phân tích giữ kết quả cũ - app KHÔNG
  tự phân tích lại; có nút “Phân tích lại N bài bằng bản mới” để bạn quyết.

- **Nhạc nền đi theo khi điện thoại chia sẻ thư viện**: máy tính hay điện thoại khác nghe sách từ điện thoại của bạn giờ nghe cả
  nhạc nền dưới giọng đọc, như khi nghe từ máy tính - gồm nhạc người làm sách đã gắn và bài "Nhạc của tôi" bạn đã ghim vào sách,
  theo đúng cách bạn đã chỉnh (tắt nhạc, mức, đoạn im lặng). Chỉ những bài sách đang dùng mới được chia sẻ, không bao giờ cả kho
  "Nhạc của tôi". Sách tải về điện thoại từ máy tính hay điện thoại khác cũng tải luôn nhạc nền (đủ byte mới giữ; bài nào hỏng thì
  bỏ bài ấy, sách vẫn tải xong), nên nghe được nhạc cả khi không có mạng và chia sẻ tiếp được cho máy khác.

- **Tìm ảnh bìa trên mạng, ngay trên điện thoại**: trong "Sửa sách", cạnh "Chọn ảnh bìa…" có "Tìm ảnh bìa trên mạng…" - hỏi iTunes,
  Open Library và Google Books theo tên bộ truyện (như trên máy tính), bấm một ảnh là đặt làm bìa. Ảnh chỉ lấy từ các nguồn ấy,
  tối đa 16 MB, và là gợi ý để bạn chọn - không bao giờ tự đặt. Nguồn nào không trả lời thì báo tên nguồn, các nguồn khác vẫn
  hiện. Máy tính cũng có nút này trong "Sửa sách" của cuốn không có xưởng.

## [0.4.21] - 2026-10-03

### Studio

- **Nhập nhạc của tôi làm nhạc nền**: trong tab "Nhạc nền" của một cuốn có phần "Nhạc của tôi" - bấm "Nhập nhạc của tôi…",
  chọn một hay nhiều file nhạc (mp3, m4a, ogg, opus, flac, wav). File được chép vào kho nhạc riêng của máy này (nhập lại cùng
  một bài thì không thành hai bản), ABook đọc sẵn tên bài, nghệ sĩ, độ dài trong file và đo độ to để nhạc nằm đúng dưới giọng
  đọc. Danh sách cho xem từng bài, nghe thử, xoá. Ở "Đổi bài" có thêm nhóm "Nhạc của tôi": ghim được bài nào cho đoạn nào,
  kể cả bài mới nhập. Máy chưa có bộ phân tích âm thanh nên bài nhập vào hiện "Chưa phân tích - máy chưa tự chọn, bạn vẫn ghim
  được": máy không tự đoán không khí của bài, và chưa tự chọn nó cho đoạn nào. Bài bạn ghim đi cùng file sách `.abook` /
  `.abookproj` (không ai khác tải được nó) và sang điện thoại khi nghe hay đồng bộ; nơi ghi công chỉ hiện tên bài và nghệ sĩ có
  sẵn trong file, không nói gì về giấy phép. Xoá một bài khỏi kho thì sách đã xuất vẫn giữ bản của nó. Điện thoại phát được
  những bài này khi chúng nằm trong sách hay đến qua đồng bộ; điện thoại cũng tự nhập được nhạc của riêng nó (xem mục
  "Điện thoại và thiết bị").

- **Xuất cả bộ nhiều phần thành MỘT file `.abook`**: trong hộp Xuất, chọn "Cả bộ" rồi file `.abook` - có hai cách,
  "Một file" (mặc định: cả bộ gộp trong một file, mở ra là nghe liền từ phần 1 sang phần 2, danh sách chương chia theo
  "Phần N · tên") hay "Mỗi phần một file". Hộp báo cỡ ước tính và cảnh báo khi quá 4 GB (thẻ nhớ / USB định dạng FAT32 không
  chứa nổi một file lớn như vậy - khi đó chọn "Mỗi phần một file"). Thông báo sau khi xuất nói đúng "một file" hay "N file".
  Mở file cả bộ ở máy khác (Windows hay điện thoại) thì nhân vật gộp theo tên, nhạc nền dùng chung chỉ nằm một lần; xuất lại
  bộ dài hơn rồi mở đè lên thì chỗ đang nghe và dấu trang vẫn còn. Mở file trên máy mà ổ đĩa không đủ chỗ thì báo rõ cần bao
  nhiêu thay vì chép dở. File `.abook` không còn mang mã nội bộ của máy xuất ra nó.

### Điện thoại và thiết bị

- **Sửa cuốn tải từ máy tính, và "Gửi về máy tính"**: cuốn đã tải về từ máy tính giờ sửa được ngay trên điện thoại như cuốn mở
  từ file - đổi tên sách, bìa, tên nhân vật, tên chương, nhạc nền, ghi việc cần Studio (cách đọc, người nói, giọng, thu lại).
  Phần sửa tự gửi về máy tính vài giây sau khi sửa, và mỗi lần điện thoại tới được máy tính; hoặc bấm "Gửi về máy tính" trong
  menu của sách. Dưới tên sách có dòng tình trạng: "N thay đổi đang chờ gửi về máy tính" (và vì sao chưa gửi được nếu lần trước
  hỏng), hay "Đã gửi về máy tính lúc …" kèm máy tính đã làm gì: bao nhiêu thay đổi đã áp, bao nhiêu việc đang chờ chủ máy
  duyệt (không việc nào tự áp), bao nhiêu mục máy tính đã đổi khác. Máy tính nhận xong thì điện thoại tải lại sách từ máy tính
  (bản ấy đã mang các sửa) rồi gỡ phần đã gửi; sửa nào bạn làm trong lúc đang gửi thì ở lại, gửi ở lần sau. Mất kết nối thì
  phần sửa vẫn nằm trên máy, thử lại sau 1 phút, 5 phút, và mỗi lần mở thư viện. Cuốn tải từ máy tính không có "Lưu thành file"
  (sách là của máy tính). Cuốn nghe thẳng chưa tải và cuốn của thiết bị ghép khác vẫn sửa ở máy giữ chúng.

- **Nhập nhạc của tôi ngay trên điện thoại, và đổi nhạc nền của một cuốn sách đã mở**: trong "Sửa sách" của một cuốn nhập từ file
  (cả điện thoại lẫn máy tính) có mục "Nhạc của tôi" - bấm "Nhập nhạc của tôi…", chọn một hay nhiều bản (mp3, m4a, ogg, opus,
  flac, wav) trong hộp chọn file của hệ thống; điện thoại chép chúng vào kho nhạc riêng của máy (nhập lại cùng một bài thì
  không thành hai bản), đọc tên bài, nghệ sĩ, độ dài trong file và đo độ to để nhạc nằm đúng dưới giọng đọc. Ở từng đoạn nhạc
  của sách có nút "Đổi bài": chọn một bài của bạn thay cho bài người làm sách gắn, "Về bài gốc" để trả lại. Bài bạn chọn đi cùng
  file sách khi "Lưu" hay "Lưu thành…", nên máy khác mở file là nghe được đúng bài ấy dù không có nó trong kho; xoá bài khỏi kho thì
  sách đã chọn nó vẫn giữ bản của nó. ABook chỉ hiện tên bài và nghệ sĩ có sẵn trong file, không nói gì về giấy phép. Máy chưa có
  bộ phân tích âm thanh nên bài nhập vào là "chưa phân tích": ABook không đoán không khí của bài và không tự chọn nó - bạn chọn.
- **Ghi ý muốn cho Studio ngay trên sách nhập từ file, không cần Studio**: trong tab "Nhân vật" của một cuốn không có
  xưởng, đổi giới tính hay gộp hai tên thành một người nay ghi lại được - giọng đọc và chữ truyện chưa đổi gì, chỉ có dấu
  "Đang chờ Studio" cạnh người ấy. "Tuỳ chọn khác" có thêm "Việc đang chờ Studio (N)" liệt kê từng việc, bỏ được từng việc
  một. "Lưu" và "Lưu thành…" mang các ý muốn đi cùng file; mở lại file ở máy khác thì hợp với những gì máy ấy đã ghi (chỗ hai
  bên khác nhau thì theo máy đang mở). Máy của người làm sách mở file sẽ hỏi có áp vào dự án không, và đồng ý thì các ý muốn
  thành những thay đổi thật chờ "Áp dụng thay đổi" - audio chỉ đổi khi người làm sách áp. Trong trang Đọc, chạm vào một
  câu rồi bấm "Sửa câu này": đổi người nói, loại câu / cảm xúc / chữ đem đọc, sửa cách đọc một từ (tên riêng), hay thu lại câu
  - cùng những việc tab Kịch bản của Studio làm. Câu có việc đang chờ hiện dấu đồng hồ "Đang chờ Studio", mỗi việc bỏ được
  ngay trong hộp; "Nghe thử" cách đọc và "Dùng cho mọi sách" vẫn hiện nhưng mờ, nói rõ cần Studio. Cuốn nghe thẳng từ máy
  tính khác hiện nút mờ kèm lý do (sửa ở máy ấy); cuốn có xưởng thì nút mở đúng câu ấy trong Kịch bản của Studio.
- **Sửa sách đã nhập ngay trên trang nghe, cả máy tính lẫn điện thoại, không cần Studio**: trong "Tuỳ chọn khác" của một
  cuốn nhập từ file `.abook`, đổi được tên sách, bìa, nhạc nền (bật/tắt, to nhỏ, im lặng một đoạn); trong danh sách chương
  đổi được tên chương, trong "Nhân vật" đổi được tên hiển thị. Đổi xong là thấy ngay ở thư viện, thông báo, widget, màn
  hình xe và máy khác nghe qua mạng nhà; chữ truyện và audio không bao giờ bị đụng tới. Mở lại cùng một file sách (bản mới
  hơn) thì phần đã sửa vẫn còn. "Lưu" và "Lưu thành…" ghi các thay đổi ra một file `.abook` mới để chuyển sang máy khác; máy
  của người làm sách mở file ấy sẽ hỏi có áp thay đổi vào dự án không. Cuốn đã có Studio vẫn sửa như trước (thêm đổi tên
  chương); những việc cần Studio ghi rõ "cần cài Studio".
- **File dự án `.abookproj` giờ nghe được ở mọi nơi nghe được file sách `.abook`**: điện thoại mở file dự án (từ trình
  quản lý file, Zalo, Drive...) là các chương đã xong vào Thư viện để nghe, không chép sổ dự án hay nguồn chương và chỉ cần
  chỗ trống cho phần nghe, không phải cho cả dự án. File dự án cũng mang theo cả nhạc nền của sách, nên mở ở máy khác là
  nghe đúng bản có nhạc, không phải tải lại. Mở file dự án trên máy tính vẫn ra thẳng dự án trong Studio; máy chưa cài Studio
  vẫn xem, nghe, sửa cách đọc, nhạc nền, bìa và xuất được - chỉ phần phân tích và thu âm cần cài Studio, và các nút ấy nói rõ
  điều đó.

## [0.4.20] - 2026-10-02

### Điện thoại và thiết bị

- **Ở ngoài nhà dùng mạng riêng ảo nào cũng được**: Cài đặt nhận ra địa chỉ "dùng khi ở ngoài" trên mọi mạng riêng ảo
  (Tailscale, ZeroTier, NetBird, WireGuard, OpenVPN...) theo card mạng của nó, không còn chỉ nhận Tailscale; chữ hướng dẫn
  nói "mạng riêng ảo" và chỉ lấy Tailscale làm một ví dụ.
- Máy tính: **phát lên Chromecast, TV Google TV và loa Nest** (Google Cast) trong mạng nhà, bên cạnh loa / TV DLNA. Mở
  "Phát trên…" là thấy thiết bị, ghi "Google Cast" cạnh tên; bấm là phát đúng chương, đúng giây đang nghe. Thiết bị tự tải
  chương từ máy tính, máy tính lưu chỗ nghe và tự sang chương sau, thanh "Đang phát trên…" có tạm dừng / tua / "Nghe trên
  máy này" (bấm thì màn hình TV, loa trở về như cũ). Có người khác phát gì đó lên thiết bị, hay tắt nó đi, thì ABook thôi
  điều khiển và giữ chỗ nghe ở đó. Chỉ phát ở tốc độ 1x và giọng đọc thôi - nhạc nền không đi theo sang thiết bị, như loa /
  TV DLNA. Điện thoại cũng tự tìm thấy các thiết bị này và phát sách đã có trên máy, không cần mở máy tính (ghi "Google
  Cast" cạnh tên, bấm "Nghe ở đây" thì thiết bị trở về như cũ); sách của máy tính thì điện thoại đã ghép vẫn điều khiển
  được thiết bị qua máy tính.
- **Vân tay máy đã ghép hiện ngay trong danh sách** ("Máy tính khác" trên máy tính; thẻ máy tính và "Thiết bị khác" trên
  điện thoại) để đối chiếu với dòng "Vân tay" đang hiện bên máy kia. Và nút **"Phát trên…" không biến mất** khi chưa thấy
  loa / TV nào: mở ra là "Không thấy loa / TV nào trong mạng" cùng nút "Tìm lại".

## [0.4.19] - 2026-10-02

### Studio

- **Nghe thử cách đọc tên trước khi lưu**: sửa cách đọc một tên (tab Nhân vật, hay thẻ "Cách đọc tên" ở Việc cần duyệt) có
  nút "Nghe thử" cạnh "Lưu" - máy đọc thử một câu ngắn có tên ấy bằng cách đang gõ, đúng giọng của người nói câu, không ghi
  gì vào sách. Bản thu thật có thể khác đôi chút (âm thanh không phải lúc nào cũng giống từng chi tiết), nên đó là "bản thu
  đầu sẽ gần như vầy". Nghe thử cần máy rảnh: đang làm sách hay card đồ hoạ đang bận thì máy nói rõ, và bấm "Bắt đầu" một cuốn
  thì phần nghe thử tự nhả card. Lần đầu mất vài chục giây nạp giọng; các lần sau trong vài phút thì tức thì. Điều khiển từ xa
  nghe thử được khi thiết bị có quyền điều khiển sản xuất.
- **Mẫu thiết lập cho sách mới**: làm nhiều kiểu truyện (light novel, tiên hiệp...) thì lưu bộ lựa chọn - giọng kể, chất lượng,
  model đọc hiểu, có bắt đầu ngay không - thành một mẫu có tên ("Lưu thành mẫu…" ở trình tạo sách), lần sau chọn lại một cú
  bấm. Chọn mẫu chỉ đổi các lựa chọn ấy, không đụng tới truyện hay tên sách; đổi tay sau khi chọn thì tên mẫu hiện "(đã sửa)".
  Đổi tên hay xoá mẫu (có "Hoàn tác") ở Cài đặt > Studio. Việc bỏ dòng ghi công vẫn do bạn đồng ý riêng từng cuốn, không nằm
  trong mẫu. Điều khiển từ xa chỉ chọn được mẫu có sẵn.


## [0.4.18] - 2026-10-02

### Studio

- **Chia thành nhiều phần**: truyện nhiều tập (mỗi tập một thư mục hay một file EPUB, hay chương có dòng "Tập 2", "Volume 2"...)
  được máy đề xuất chia; bấm đồng ý thì tạo một lượt cả bộ, sửa chỗ cắt theo số chương. Phần 1 như sách thường, các phần sau
  nối tiếp, tự xếp hàng và mang giọng nhân vật, cách đọc tên từ phần trước khi tới lượt chạy.
- **Xuất cả bộ**: truyện chia nhiều phần ("Làm tiếp cuốn này") có thêm lựa chọn "Cả bộ (N phần)" trong hộp Xuất - thư
  mục MP3 mỗi phần một thư mục con, hay mỗi phần một file `.abook` trong thư mục của bộ; phần chưa có chương xong được
  bỏ qua và kể tên.

### Điện thoại và thiết bị

- **Kết nối giữa các máy được mã hoá**: điện thoại, máy tính và trình duyệt trong cùng Wi-Fi nói chuyện qua kênh mã hoá thay
  vì chữ rõ, nên người lạ cùng mạng không đọc trộm được mã thiết bị rồi dùng lại. Lúc ghép, mỗi máy ghi nhớ "vân tay" của
  máy kia; sau đó chỉ nói chuyện với đúng máy đó - máy kia cài lại ABook hay có ai giả mạo thì app báo rõ và bảo ghép lại,
  không âm thầm nối vào. Cài đặt hiện vân tay của máy này để đối chiếu. Máy đã ghép từ bản trước phải ghép lại một lần.
  Trình duyệt mở Studio từ xa sẽ báo trang "không an toàn" vì chứng chỉ do chính máy tính cấp - chọn tiếp tục.
- **Nhạc nền trong Studio từ xa**: điện thoại và trình duyệt điều khiển máy tính giờ mở được tab Nhạc nền - nghe thử,
  chỉnh, "Đổi bài" cho từng đoạn - và trình phát ở xa phát cả nhạc nền như trên máy tính. Trước đây các yêu cầu này bị
  chặn nên tab trống.

## [0.4.17] - 2026-10-02

### Studio

- Tab Nhân vật: nút "…" ở mỗi người có **Đổi tên** (chỉ đổi tên trên màn hình, kịch bản và file sách; không thu lại câu
  nào, có hiệu lực ngay, mang sang phần sau; "Về tên gốc" để bỏ) và **Đổi giới tính** (một thay đổi chờ "Áp dụng thay
  đổi"; hộp nói trước số câu đã thu sẽ phải thu lại nếu giọng đang đọc không hợp giới mới).

### Nhạc nền

- Độ to nhạc so với giọng tính đúng như lúc phát ra hai loa: giọng đọc một kênh được tính to hơn 3 dB, nhạc đo hai kênh
  thay vì trộn xuống một kênh (trước lệch 0,5-3 dB tuỳ bài), và bài đã có trên máy dùng số đo thật thay cho số ước lượng
  của danh mục. Nhạc ở mức "Vừa" vì thế to hơn trước tới khoảng 2,5 dB, đúng khoảng cách 20 LU đã chọn.
- Bài nhạc tải từ nguồn gốc như trước; nguồn gốc hỏng (mất mạng tới nguồn, bài bị gỡ) thì tải bản dự phòng trên
  archive.org mà danh mục ghi kèm, chỉ nhận bản dự phòng khớp đúng bản gốc.

### Phát triển

- Gói Python và mọi tên bên trong đã đổi theo tên app: `ebook_reader` thành `abook` (`python -m abook.cli`, lệnh `abook-headless`),
  biến môi trường `EBOOK_READER_*` thành `ABOOK_*`, và các tên lưu trữ nội bộ cũng theo. Mã chất lượng bị khoá đổi hash theo.

## [0.4.16] - 2026-10-02

### Studio

- Bước chọn chương soát **số chương**: chương trùng (hai file cùng "Chương 11"), chương thiếu (14 rồi 18), thứ tự lùi, và
  phần nối tiếp không bắt đầu ngay sau chương cuối của phần trước - máy chỉ nhắc, không bỏ file nào.
- Cài đặt > Studio: chọn **giọng kể và chất lượng mặc định cho sách mới** - trình tạo sách điền sẵn ("Làm tiếp cuốn này" vẫn
  theo phần trước).
- **Cần nghe lại** có nút **Nghe liền N câu**: phát lần lượt mọi câu nghe được; đang nghe thì phím **O** = Ổn, **R** = Cần
  thu lại, rồi sang câu kế ngay.
- **Gói cả dự án thành một file `.abookproj`** (Xuất > Cả dự án): sổ dự án, audio đã thu, nguồn chương, bìa - để sao lưu
  hay chuyển sang máy khác. Bấm đúp file (hay Mở file sách) là có lại dự án ấy trong Studio, luôn thành một dự án MỚI,
  không đè dự án đang có. Nguồn chương đã bị dời hay xoá thì vẫn gói được, app báo rõ thiếu file nào. Dự án đang chạy
  thì gói sau khi nó chạy xong hoặc đã dừng.
- Sách đã tạo mà **chưa bắt đầu** có nút **Sửa thiết lập**: trình tạo sách mở lại với mọi lựa chọn cũ (chương, tên, giọng kể,
  chất lượng, người xưng "tôi", model đọc hiểu) để đổi; tạo xong thì bản cũ vào Thùng rác, bìa đã chọn đi theo.

### Nhạc nền

- Mỗi cuốn có **rãnh nhạc nền**, mặc định bật, máy tự chọn bài theo không khí từng đoạn (danh mục nhạc CC0 / CC BY đã phân
  tích sẵn, cập nhật qua mạng). Tab **Nhạc nền** của dự án: bật / tắt, thế giới của truyện, mức nhạc dưới giọng đọc, im
  lặng một đoạn, không dùng một bài nữa, chọn lại nhạc - mọi chỉnh là tuỳ chọn và được giữ khi máy chọn lại.
- Trình nghe trên máy tính phát nhạc nền dưới giọng đọc: đổi bài mờ dần khi sang đoạn mới, dừng và tua theo giọng.
- Đoạn nhạc dài tối đa khoảng **3 phút**: nhạc đổi theo không khí trong chương thay vì một bài cho cả chương (đo trên 13
  chương có đáp án cảnh, docs/MUSIC_RESEARCH.md).
- **File sách `.abook` mang theo nhạc nền** người sản xuất đã gắn (cả file nhạc và ghi công): mở ở máy khác vẫn nghe đúng
  nhạc ấy. Sách có nhạc dùng định dạng mới - app bản cũ sẽ nhắc cập nhật; sách không nhạc vẫn mở được ở app cũ.
- **Điện thoại cũng phát nhạc nền** (sách tải từ máy tính hay file `.abook`), mờ dần khi đổi bài, dừng và tua theo giọng.
- Màn đang nghe có dòng **Nhạc nền: tên bài · tác giả**, chạm để xem ghi công đầy đủ (giấy phép, trang của bài).
- **Đổi bài** cho một đoạn: danh sách bài hợp không khí khác, **Nghe thử** khoảng 20 giây trước khi chọn.
- Sửa một đoạn (ghim, im lặng, bỏ bài, bật / tắt, mức nhạc) **không làm đổi nhạc các đoạn khác**; chỉ "Chọn lại nhạc" hay đổi
  thế giới của truyện mới chọn lại cả cuốn. Bỏ một bài có **Hoàn tác** và danh sách **Bài đã bỏ** để dùng lại.
- **Nhạc luôn nằm dưới giọng đọc một khoảng như nhau**, bài to hay nhỏ máy tự bù (trước đây khoảng cách lệch 10-27 LU tuỳ
  bài, 1/5 số bài sát giọng quá). Mức nhạc nay chọn theo "nhỏ hơn giọng bao nhiêu", mặc định 20 LU.
- Danh mục nhạc thêm bài từ Jamendo và Freesound (CC0 / CC BY), mỗi bài ghi công và dẫn về trang gốc.

## [0.4.15] - 2026-10-01

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
- Tab Nhân vật: **Gộp vào người khác** khi máy tách một người thành hai tên ("Heit" và "Heidi") - mọi câu của người này
  đọc bằng giọng người kia, và các phần sau của truyện cũng hiểu hai tên là một. Như mọi sửa khác: chờ "Áp dụng", bỏ
  được trong hộp ấy (bỏ là bỏ cả bí danh).
- Một lần bấm cho nhiều câu (cả nhóm vai phụ, Shift-chọn ở Kịch bản, gộp nhân vật, thu lại cả chương) tính là **một**
  thay đổi trên nút "Áp dụng", không phải mỗi câu một.
- **Làm tiếp cuốn này**: tab Nhân vật của phần mới hiện dàn mang từ phần trước (giọng giữ nguyên) thay cho "Chưa có dàn"; bấm ở một phần cũ khi cuốn đã có phần sau thì trình tạo nói rõ phần mới nối sau phần MỚI
  NHẤT (không lặng lẽ nhảy "Phần 1" → "Phần 3"); phần mới đọc bằng đúng model đọc hiểu của phần trước (bước Xác nhận
  ghi "như phần trước", báo nếu máy không còn model ấy); khung "chưa có chương mới" tự tắt khi đã có file.
- Trang dự án có nút **Xuất…**: chọn thư mục MP3 hay file .abook ngay trong Studio, và hộp nói trước bản xuất có gì -
  bao nhiêu chương chưa có audio, sách đang chạy, còn thay đổi chưa áp (kèm nút "Áp dụng trước").
- Mỗi chương có menu **…**: nghe chương, mở **Kịch bản chương này**, và **Thu lại cả chương** (mọi câu đã thu, hạt giống
  mới - khi cả chương nghe không ổn). Cả chương tính là một thay đổi trong hộp "Áp dụng", bỏ được bằng một nút.
- Trình tạo sách: bấm "Nghe thử" một giọng kể không còn đổi luôn giọng đang chọn; chế độ "Nhanh" vẫn có ước thời gian
  (trần trên); cảnh báo giai đoạn phân tích nhắc **Tạm dừng** là cách an toàn; tắt "Bắt đầu tạo ngay" thì lời mô tả nói
  đúng điều sẽ xảy ra. Chữ dễ hiểu hơn ở vài chỗ ("4 tỉ tham số", nguồn bìa nào chưa trả lời, "máy nghe khớp 15%").
- **Việc cần duyệt** có phím tắt: **J / K** chọn thẻ, **1–9** bấm lựa chọn thứ N của thẻ ấy - duyệt cả trăm thẻ không cần
  chuột; quyết xong thì thẻ kế đứng vào đúng chỗ.
- Lọc theo một loại thẻ thì có nút **Giữ như máy đang làm - cả N thẻ** (hỏi lại trước, hoàn tác được): soát vài thẻ thấy
  máy đúng thì khỏi bấm "giữ" từng thẻ một.
- **Cần nghe lại**: câu hỏng sau mọi lần thử (tượng thanh "Tách tách tách", "Coong…", chữ lạ) có nút **Sửa chữ đem đọc**
  ngay trên thẻ - viết lại cách đọc thành tiếng, lưu cho một câu hay cả các câu cùng chữ; chữ của sách giữ nguyên. Câu đã
  ghi chữ mới rời mục "Chưa xem" và hiện "Sẽ đọc là …" cho tới khi áp.
- Phân vai: tên có chức danh tiếng Anh mà model đọc hiểu viết thêm ("Professor Glast", "Lady Marla", "Sir …") gộp về
  đúng người ("Glast") - không còn thành nhân vật thứ hai với giọng khác.

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
