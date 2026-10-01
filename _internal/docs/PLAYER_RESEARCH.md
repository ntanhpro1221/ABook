# Học từ các trình nghe sách nói (26-09)

Chủ sách: *"càng học, càng tìm hiểu nhiều càng tốt"*, và hỏi riêng về các app có cả bản Windows lẫn Android. Đã dùng
thử trên máy ảo Android 16 (Play Store): **Smart AudioBook Player** (SABP, 5 triệu lượt tải, 4,8★), **Voice**
(mã nguồn mở, F-Droid). **AntennaPod** đã cài nhưng chưa thử (hạn mức token); phần của nó lấy từ tài liệu. Các app
đa nền tảng (Audible, Libby, Audiobookshelf, Spotify) tìm hiểu qua tài liệu chính thức.

## Tìm được gì

### Smart AudioBook Player - app nhiều tính năng nhất

- **Hẹn giờ ngủ**: mặc định 10 phút; mỗi lần lắc máy thì đặt lại từ đầu. Có **lịch tự bật** (tự bật/tắt theo giờ), độ
  nhạy lắc, "theo dõi chuyển động: luôn / chỉ lúc sắp tắt", báo khi bắt đầu nhỏ dần, rung khi được đặt lại.
- **Force stop sau 2 giờ phát liên tục** - lưới an toàn cho người ngủ quên mà không hẹn giờ.
- **Tự lùi theo độ dài lần dừng**, tối đa 30 giây ("Big"). Đây đúng là cách ta vừa làm (0 / 10 / 30 giây).
- Tự phát khi cắm tai nghe; tạm dừng khi có tin nhắn hoặc chỉ đường; tự phát lại sau cuộc gọi; dừng khi app khác phát.
- Dòng tiến độ **cả cuốn** ngay trên trình phát: "Đã nghe 15:00 / 45:00 · 33% · Còn 30:00".
- Trình phát có: danh sách nhân vật (người dùng tự nhập), dấu trang (nhấn giữ = thêm nhanh), tăng âm lượng, bộ cân bằng,
  lặp đoạn (học ngoại ngữ), **úp máy để dừng, lật lên để nghe tiếp**, khoá nút (bỏ túi), tua 10 giây và 1 phút.
- Nút tai nghe Bluetooth: Trước/Sau = lùi/tới 10 giây (không đổi chương).
- Hỗ trợ chương trong m4b/mp3, **phụ đề .srt** (đọc theo), bỏ đoạn đầu/cuối lặp lại, nén sang Opus để tiết kiệm chỗ.
- Thư viện: Tất cả / Mới / Đang nghe / Nghe xong (ta cũng vậy). Mỗi cuốn phải nằm trong một thư mục riêng.
- Mở app vài lần là hiện hộp thoại chấm sao của Play - khó chịu, ta không làm thế.

### Voice - tối giản, đẹp

- Lúc thêm sách hỏi **"file của bạn sắp xếp thế nào?"** (thư mục con là sách / một thư mục là một sách / tác giả rồi
  sách) và **xem trước ngay** kết quả: "sẽ nhận ra các sách sau: … 3 file âm thanh".
- Hẹn giờ ngủ dạng tấm trượt từ dưới lên, lời chào "Sweet dreams! 🌙": 5/15/30/60 phút, một số tuỳ chỉnh có nút
  "Ngắn hơn / Dài hơn", và "Hết chương".
- Bỏ khoảng lặng, tăng âm lượng. Thư viện chia "Chưa nghe / Đang nghe", có ô tìm ở đầu.
- **Voice đọc tên sách và tên chương từ tag ID3** - và MP3 của ta hiện ra thành sách "lo16", chương "645" (xem mục ⚠).

### AntennaPod (theo tài liệu)

Hẹn giờ ngủ: lắc để đặt lại, rung trước khi hết giờ, **tự bật trong khung giờ**, nút gia hạn nhanh.

### App có cả Windows và Android

- **Audible (Whispersync for Voice)**: vị trí đẩy lên mây mỗi lần dừng. Mở trên thiết bị khác thì **hỏi "tới vị trí xa
  nhất?"** thay vì lặng lẽ nhảy. Chuyển qua lại **đọc ebook ⇄ nghe** đúng chỗ (Kindle + Audible).
- **Libby**: ghép thiết bị bằng **mã cài đặt** (giống mã 6 số của ta). Vị trí, dấu trang, ghi chú đồng bộ. Thanh tiến độ
  cả cuốn hiện vạch chương và dấu trang. Có **Timeline** (lịch sử mượn/đọc), xuất ra được.
- **Audiobookshelf** (máy chủ tự dựng + web + Android, gần kiến trúc của ta nhất): tải về nghe offline, vị trí lưu trên
  máy và **gửi lên khi máy chủ liên lạc lại được**, ghi **phiên nghe** (thiết bị, bắt đầu/kết thúc, vị trí) và thống
  kê nghe. Người dùng than một lỗi: chuyển từ máy tính sang điện thoại thì điện thoại vẫn ở vị trí cũ tới khi thoát ra vào
  lại → **đồng bộ phải xảy ra lúc mở sách, không chỉ lúc mở app**.
- **Spotify Connect**: điều khiển thiết bị đang phát từ thiết bị khác, chuyển phát liền mạch giữa các thiết bị.

## ⚠ Lỗi của chính ta lộ ra khi nghe bằng app khác

MP3 chương mang tag ID3 của dây chuyền: **album = tên project lô ("lo16"), title = tên file nguồn ("645")**, không
tên sách, không tên chương thật ("Chương 646 - Trở về (1)"), không ảnh bìa, không số thứ tự. Ai chép MP3 sang điện
thoại hay mở bằng trình nghe khác sẽ thấy rác. Code ghi MP3 nằm trong file bị khoá (đang chạy sách) nên **không sửa ở
dây chuyền**; sửa ở khâu **xuất**: một lệnh "Xuất sách" ghi bản sao MP3 có tag đúng (album, title, artist = giọng kể,
track, ảnh bìa) hoặc gộp thành một file M4B có mốc chương.

## Áp dụng - theo thứ tự đáng làm

Đã làm tối 26-09 (nhánh ui/redesign): #1 (máy tính + lõi Android), #2, #3 (máy tính), #4 (chế độ đọc),
#5, #6 (xuất MP3 có tag), #7 (lịch sử nghe), #10 (số phút tuỳ chỉnh). Ngày 27-09: #8 (lắc = cộng thêm/đặt lại + độ nhạy),
#9 (úp máy để dừng - chỉ tính khi úp VÀ nằm yên, cầm tay giơ lên xem không tính), #11 (nút tai nghe lùi/tới 15 giây),
#13-#15 bên dưới; tất cả thử trên máy ảo bằng cảm biến/phím media giả lập. Chiều 27-09: #12 - xong cả danh sách.

| # | Ý tưởng | Học từ | Vì sao với ta |
|---|---|---|---|
| 1 | **Tự dừng khi nghe liên tục quá lâu mà không chạm máy** (mặc định 2 giờ), ghi luôn mốc "tự dừng" vào nhật ký đêm | SABP | Ngủ quên KHÔNG hẹn giờ là trường hợp tệ nhất cho nỗi đau "sáng dậy tìm chỗ"; lưới này làm thẻ "Tối qua" chạy cả khi quên hẹn giờ |
| 2 | **Lịch tự bật hẹn giờ** (vd 22:00-06:00) | SABP, AntennaPod | Người nghe buồn ngủ hay quên bấm hẹn giờ |
| 3 | **Hỏi khi thiết bị kia nghe xa hơn**: "Trên điện thoại bạn đã nghe tới Chương 726 · 12:40 (23:41 tối qua) - Nghe tiếp từ đó?" | Audible, Audiobookshelf | Hiện ta lặng lẽ lấy bản mới hơn khi đồng bộ; hỏi thì không ai bị nhảy chỗ bất ngờ. Đồng bộ lúc mở sách |
| 4 | **Đọc ⇄ nghe cùng một chỗ**: chế độ đọc sách (không tiếng) đi theo đúng câu đang nghe, và ngược lại | Whispersync (Kindle + Audible) | Ta đã có văn bản kèm mốc từng câu - thứ Audible phải bán hai sản phẩm mới có. App tên "Ebook Reader" |
| 5 | **Tiến độ cả cuốn trên trình phát** ("Đã nghe 5 giờ 12 / 9 giờ · Còn 3 giờ 48 ở 1,5×") | SABP, Libby | Người nghe muốn biết còn bao lâu hết sách |
| 6 | **Xuất sách có tag đúng / M4B** | (lỗi phát hiện được) | Mục ⚠ |
| 7 | **Lịch sử nghe** theo ngày (phiên: giờ, thiết bị, từ đâu tới đâu) + thống kê | Audiobookshelf, Libby | Cũng là một cách tìm lại chỗ; nền cho thống kê |
| 8 | Lắc để **đặt lại** (thay vì cộng thêm) - để người dùng chọn | SABP | Hai thói quen khác nhau; ta đang cộng 10 phút |
| 9 | Úp máy để dừng / lật lên nghe tiếp; khoá nút khi bỏ túi | SABP | Điện thoại |
| 10 | Tấm hẹn giờ có số tuỳ chỉnh + "Ngắn hơn/Dài hơn"; báo rung khi bắt đầu nhỏ dần | Voice, SABP | Tinh chỉnh |
| 11 | Nút tai nghe Bluetooth Trước/Sau = lùi/tới (tuỳ chọn) | SABP | Sách nói ít khi cần nhảy chương |
| 12 | **Điều khiển điện thoại đang phát từ máy tính**: thanh "Đang phát trên <điện thoại>" (phát/dừng, lùi/tới 15 giây), **"Nghe trên máy tính"** (dừng điện thoại, máy tính phát tiếp đúng giây) và ngược lại **"Phát trên điện thoại"** ở thanh phát máy tính | Spotify Connect | Điện thoại không mở cổng nào: nó "hỏi dài" máy tính (treo 25 giây, có lệnh là trả ngay) khi app đang mở, đang phát hoặc vừa dừng dưới 10 phút. Lệnh quá 15 giây chưa tới tay thì bỏ. Đã làm 27-09, thử trên máy ảo |
| 13 | **Ảnh bìa thật**: đặt từ file/kéo thả/dán, hoặc **tìm trên mạng** (iTunes, Open Library, Google Books) rồi chọn; màu chủ đạo nhuộm màn "Đang nghe" | SABP (cover art downloader), Audiobookshelf (match bìa qua nhiều nguồn) | Sách TXT không có bìa; truyện mạng dịch hiếm khi có trên các nguồn - chỉ gợi ý, không tự đặt. Đã làm 27-09 |
| 14 | Chạm vào bìa lớn để phát/dừng | SABP | Mục tiêu to nhất màn hình. Đã làm 27-09 |
| 15 | Độ nhạy lắc (nhẹ tay / vừa / mạnh tay) | SABP (rất thấp → rất cao) | Trở mình bị tính là lắc, hoặc lắc mãi không ăn. Đã làm 27-09 |

## Liên kết giữa các máy (chủ sách 27-09)

Chủ sách: "một bên có thể play, xem, sử dụng lib của một bên khác mà không cần phải thực sự có lib đó trong bộ nhớ",
qua LAN, Wi-Fi, USB - và giữa MỌI cặp: điện thoại <-> máy tính, điện thoại <-> điện thoại, máy tính <-> máy tính. Hướng:
mỗi app là một trạm hai vai (phục vụ thư viện của mình cho máy đã ghép + kết nối trạm khác).

| bước | việc | trạng thái |
|---|---|---|
| 0 | Điều khiển điện thoại đang phát từ máy tính, chuyển chỗ nghe giữa hai máy (#12) | xong 27-09 |
| 1 | Điện thoại nghe thẳng thư viện máy tính, đầy đủ như sách đã tải (Streaming.kt) | xong 27-09 |
| 2 | Điện thoại có vai phục vụ (máy chủ nhỏ trong app, trả lời tìm máy) -> máy tính nghe thư viện điện thoại, điện thoại <-> điện thoại | xong 28-09 (LibraryServer.kt, Peers.kt; qua Bluetooth: BluetoothLink.kt) |
| 3 | Máy tính có vai kết nối (mục "Trên thiết bị khác") -> máy tính <-> máy tính | xong 28-09 (webui/remote_books.py, Cài đặt → Máy tính khác) |
| 4 | Điều khiển từ xa hai chiều trên cùng giao thức (điện thoại điều khiển trình phát máy tính) | xong 28-09 (webui/peer_players.py, RemotePlayers.kt) |

USB: bật chia sẻ kết nối qua USB trên Android là có đường mạng, cùng giao thức. Ngoài nhà: địa chỉ nhập tay qua Tailscale /
ZeroTier / NetBird (không trói vào dịch vụ nào); không đẩy audio lên cloud (một tập ~40 chương ~750 MB).

### Phát lên loa / TV qua Google Cast - thiết kế, chưa làm (29-09)

Mục (3) còn lại của lộ trình đường truyền (Android Auto đã xong ở 0.4.1). Media3 có `CastPlayer`
(`androidx.media3:media3-cast`): cùng giao diện `Player`, cắm thẳng vào `MediaSession` sẵn có, nên thông báo, màn khoá,
nút tai nghe, tốc độ, hẹn giờ vẫn là một đường. Không cần app nhận riêng - dùng Default Media Receiver của Google.

Điểm khó duy nhất: loa/TV phải TỰ tải audio qua HTTP trong mạng nhà.
- Sách đã tải về điện thoại: máy chủ nhỏ sẵn có của điện thoại (LibraryServer.kt, bước 2) phát chương ra LAN. Loa không
  ghép được bằng mã 6 số, nên mỗi lượt phát cấp một địa chỉ BÍ MẬT ngắn hạn (mã ngẫu nhiên trong đường dẫn, chỉ đúng cuốn
  đang phát, hết hạn khi ngắt Cast), cần hỗ trợ `Range` để tua.
- Sách nghe thẳng từ máy tính: loa tải thẳng từ cổng đồng bộ của máy tính cũng bằng địa chỉ bí mật như thế - audio không
  đi vòng qua điện thoại.
- Chuyển qua lại: dừng ở loa thì nghe tiếp trên điện thoại đúng chỗ (lưu vị trí như chuyển máy hiện nay).
- Nút Cast: trình phát React gọi plugin mở hộp chọn thiết bị (MediaRouter); chỉ hiện khi máy có Google Play Services và
  mạng có thiết bị Cast.
- Chỉ Wi-Fi nhà (không qua Tailscale: loa không ở trong tailnet).

### Phát lên loa / TV qua DLNA - máy tính, đã làm (01-10)

Chủ sách không có loa Google, Chromecast hay TV để thử ("giả lập hay gì đó đi"), nên làm trước chuẩn MỞ - DLNA / UPnP AV
(TV Samsung / LG / Sony, ampli, loa mạng, máy Windows bật điều khiển Windows Media Player từ xa) - và thử hoàn toàn bằng
thiết bị giả `scripts/fake_renderer.py` (chỉ thư viện chuẩn, chạy được trên máy khác trong mạng). Mã: `webui/cast.py`.

- Máy tính là bộ não, thiết bị chỉ phát một file: tìm bằng SSDP (M-SEARCH ra từng card mạng, nhịp 30 giây khi giao diện
  đang mở, tìm lại ngay khi mở menu "Phát trên…"), điều khiển bằng SOAP AVTransport, hỏi thiết bị mỗi giây để lưu chỗ nghe
  (hồ sơ nghe như trình phát trong app) và tự sang chương sau khi thiết bị về STOPPED ở cuối chương - kể cả khi không ai
  mở giao diện.
- Audio đi thẳng từ máy tính tới thiết bị qua cổng riêng `CastMedia`: chỉ phục vụ file đã đưa, mỗi file một mã ngẫu nhiên
  128 bit trong đường dẫn, hết hạn 12 giờ, có `Range` và header DLNA. Không đi qua cổng đồng bộ: dùng được cả khi chưa bật
  "Cho phép điện thoại kết nối".
- Thiết bị là một "máy" trong `/api/remote` (`via` cast) như điện thoại: cùng thanh "Đang phát trên…", nút "Phát trên…" (một
  máy: một nút; nhiều máy: một menu), "Nghe trên máy này".
- Chỗ TV thật hay vấp, loa giả bắt chước để thử: chỉ tua khi đã chạy (đưa chương, Play, đợi PLAYING rồi mới Seek), hết bài
  về STOPPED với vị trí 0 (nhớ vị trí xa nhất), không có Pause (dừng hẳn, "phát" đưa lại đúng chỗ), không báo vị trí
  (ước theo đồng hồ), app khác chiếm thiết bị (bỏ phiên). Không ghi DLNA.ORG_PN (PN sai thì TV khó tính từ chối hẳn).
- An toàn: trả lời SSDP là dữ liệu LAN - chỉ đọc mô tả ở đúng địa chỉ đã trả lời và chỉ gửi lệnh tới địa chỉ ấy, không theo
  chuyển hướng, không qua proxy, XML có trần cỡ và không nhận DOCTYPE / ENTITY.
- Đã thử (01-10): 14 bài trong `tests/test_cast.py` (trọn vòng với loa giả: tìm, đọc mô tả, tải đúng file, tua sau khi
  chạy, tự sang chương, thiết bị không Pause / không báo vị trí / bị chiếm, qua HTTP của app); trên mạng thật: loa giả trên
  chính máy này VÀ trên Mac mini (máy khác, tải 23,7 MB qua LAN trong ~2 giây - tường lửa Windows cho qua), giao diện:
  chuyển qua lại máy tính <-> loa <-> loa khác, tự sang chương 725 -> 726 và ghi "đã nghe hết". Trong mạng nhà chủ sách có
  một thiết bị thật: máy Windows "QuangNgocThuy" (Windows Digital Media Renderer) - hiện là máy tính; KHÔNG gửi lệnh nào
  tới nó (sẽ phát ra loa của người khác).
- Lỗi cũ lộ ra khi thử: "Phát trên…" chỉ tạm dừng trình phát trong app, nên lúc rời trang nó lưu lại chỗ cũ đè lên chỗ máy
  kia đã nghe tới (loa dừng 0:56, tải lại trang thành 0:19) - đúng cả với điện thoại. Nay máy kia nhận lệnh thì trình phát
  trong app đóng hẳn (vẫn lưu chỗ trước khi đóng).
- Còn lại: điện thoại phát thẳng lên loa / TV (Kotlin, cùng giao thức; sách đã tải phục vụ từ LibraryServer.kt), Google Cast
  (mục trên - loa Google không có DLNA), âm lượng của thiết bị (RenderingControl - đã đọc địa chỉ, chưa có nút), tốc độ
  khác 1x (DLNA gần như không thiết bị nào nhận).

Không học: hộp thoại xin chấm sao, lặp đoạn (học ngoại ngữ), cân bằng âm (giọng đọc đã được cân mức ở dây chuyền).
