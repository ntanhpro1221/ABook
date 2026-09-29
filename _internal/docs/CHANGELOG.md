# Nhật ký thay đổi

Những gì NGƯỜI DÙNG thấy thay đổi ở mỗi bản phát hành (máy tính và điện thoại cùng một số phiên bản). Lý do kỹ thuật và
bằng chứng đo đạc của từng thay đổi dây chuyền nằm ở `VERSIONS.md`; quy trình phát hành ở `RELEASING.md`.

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/); số phiên bản theo `major.minor.patch`.

## [Chưa phát hành]

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
- Hộp "Việc cần anh":
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
  hiện đủ lâu để kịp bấm.
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
- Hộp **"Việc cần anh"** hỏi khi một **danh hiệu hay biệt danh** có giọng riêng mà sách luôn viết nó sát tên một người
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
  bản) hay bấm "Người khác…" trên thẻ của hộp "Việc cần anh", chọn Nam / Nữ / Không rõ. Trước đây chỉ chọn được người
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
- Điện thoại: công tắc **"Báo khi sách xong hay có việc cần anh"** (màn Tải sách, dưới nút Studio của máy tính).
  Điện thoại hỏi máy tính mỗi 15 phút (cả khi app đã đóng) và mỗi lần mở app, rồi báo: sách đã xong, dừng vì lỗi,
  dừng giữa chừng, hay có thêm việc cần anh. Bấm thông báo mở thẳng Studio từ xa đúng cuốn, đúng tab. Cần máy tính
  bật "Cho phép điều khiển sản xuất" và điện thoại có quyền ấy - như chính trang Studio từ xa. Lần bật đầu chỉ ghi
  mốc, không đổ ra tin cũ.
- Studio, tab **Nhân vật**: nút **"Đổi giọng"** trên mỗi nhân vật mở danh sách mọi giọng dùng được, nghe thử từng
  giọng, thấy giọng đang dùng, giọng máy gợi ý cho giọng nam và giọng nữ, và ai cùng chương đang dùng giọng gốc ấy.
  Chọn giọng khác giới là đổi luôn giới của nhân vật. Áp ở ranh giới chương kế tiếp như các sửa khác; câu đã thu của
  người ấy được thu lại bằng giọng mới.
- Hộp **"Việc cần anh"**: thẻ **"Nam hay nữ"** và **"Chung giọng"** giờ bấm được. Thẻ nói máy đang đọc nhân vật bằng
  giọng nam hay nữ và cái giá của từng lựa chọn ("giữ giọng đang đọc" hay "đổi giọng, thu lại 3 câu"). Chọn xong,
  dây chuyền ghim giới cho các lô sau và - khi giọng phải đổi - chọn giọng mới đúng cách bước phân vai chọn (không trùng
  bậc giọng với người cùng chương, mọi người khác giữ nguyên giọng), rồi thu lại đúng các câu của người ấy. "Chung giọng"
  đổi giọng người ít câu hơn trước. Không phải dừng sách.
- Hộp **"Việc cần anh"**: thẻ **"Một người hai tên"** bấm được - "Gộp vào X" chuyển mọi câu của tên ít câu hơn
  sang giọng của tên nhiều câu hơn (người nghe đã quen giọng ấy, ít câu phải thu lại nhất), "Hai người khác nhau" thì
  thẻ không hỏi lại. Thẻ giờ bắt cả trường hợp tên NGẮN nói nhiều hơn ("Kati" / "St. Kati") mà trước đây bỏ sót.
- Studio có tab mới **"Kịch bản"**: đọc từng chương như kịch bản - câu nào của ai - và đổi người nói của bất kỳ câu
  thoại hay câu nghĩ nào bằng cách bấm tên ở đầu câu (tìm được mọi nhân vật đã có giọng, gõ không dấu cũng được). Câu
  máy nghi có dấu vàng kèm lý do và gợi ý người đáp lại; bộ lọc "Máy nghi" chỉ hiện những câu ấy cùng câu liền trước.
  Máy tính có phím tắt: ↑ ↓ chọn câu, phím số gán người theo dàn của chương rồi sang câu kế. Sửa không dừng sách: áp ở
  ranh giới chương kế tiếp, câu đã thu thì thu lại bằng giọng người mới; câu nào đã ghi hiện "đang chờ", áp rồi có dấu
  tích. Dùng được cả từ điện thoại qua Studio từ xa.
- Hộp **"Việc cần anh"** có loại việc mới **"Lượt đối đáp"**: hai đoạn thoại liền nhau không lời dẫn mà máy gán cho cùng một người - đo trên đáp án 7 truyện, 9/10 cặp như thế là máy bỏ lỡ lượt đổi người. Thẻ hỏi câu sau là của ai; truyện kể ngôi thứ nhất thì "tôi" đứng đầu các lựa chọn.
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
  (`http://<máy tính>:47630`) - xem tiến độ, bắt đầu hay dừng, tạo sách, duyệt "Việc cần anh" và "Cần nghe lại", đặt
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
- Android: app đổi mã thành `com.ngdtuanh.abook`, nên ABook cài thành **một app mới** bên cạnh "Ebook Reader" cũ, không
  mang theo sách đã tải hay chỗ đang nghe. Ghép nối lại với máy tính, tải lại sách (chỗ nghe đồng bộ từ máy tính về), rồi
  gỡ app cũ.
- Android: APK phát hành ký bằng khoá phát hành của dự án. Điện thoại đã cài một bản ABook thử (dựng từ mã nguồn) phải
  **gỡ bản ấy trước** - Android không cài đè một app khác chữ ký - rồi ghép lại và tải lại sách như trên.

## [0.3.0] và trước

Các bản dây chuyền trước đây (alpha) ghi ở `VERSIONS.md`, kèm lý do và bằng chứng đo cho từng thay đổi.
