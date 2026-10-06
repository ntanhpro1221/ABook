# Giao diện: Nghe (máy tính + Android) và Studio (máy tính)

Ngày 26-09 chủ sách yêu cầu làm lại UI/UX thành một sản phẩm: *"không chỉ đẹp về mặt giao diện mà luồng dùng,
cách dùng của app cũng phải ngon, phải trực quan"*, rồi thêm một trình nghe Android, rồi tách phần sản xuất và
phần tiêu thụ *"để phần tiêu thụ sẽ có sự đồng nhất với bản trên android"*. Tài liệu này là kiến trúc kết quả.

## Hai khu, một mã Nghe

| khu | ở đâu | làm gì |
|---|---|---|
| **Nghe** | máy tính **và** Android, cùng một mã React (`ui/src/listen`) | thư viện, trang sách, trình phát, đọc theo, dấu trang, nhân vật |
| **Studio** | chỉ máy tính (`ui/src/studio`) | dự án, trình tạo 4 bước, tiến trình sản xuất, nhật ký |

Phía Nghe không biết dữ liệu đến từ đâu: nó nói chuyện với `ListenSource` (`ui/src/listen/source.tsx`) và phát
bằng `AudioEngine` (`ui/src/listen/engine.ts`).

| | máy tính | Android |
|---|---|---|
| `ListenSource` | HTTP tới server cục bộ (`desktop/httpSource.ts`) | sách đã tải trên máy (`android/androidSource.ts`) |
| `AudioEngine` | `<audio>` của trình duyệt | lõi Media3 native (`android/nativeEngine.ts` -> `Playback.kt`) |

Hợp đồng dữ liệu chung là `book.json` (`abook/webui/listen_view.py`): tên, người đọc, các chương nghe
được kèm thời lượng, trạng thái nghe. Máy tính dựng nó từ project đang sản xuất (chương nào xong là nghe được
chương đó); điện thoại tải nó về cùng các file.

## Những gì người dùng có (26-09)

Nghe (máy tính + Android):
- Thư viện gom các tập cùng bộ, thẻ "Đang nghe dở" nói chương + giờ + lần nghe cuối, thẻ "Tối qua" buổi sáng, sách
  đang làm mà chưa có chương nào hiện dạng "Đang làm · chương đầu sau khoảng X"; tìm không dấu.
- Trình phát: hẹn giờ ngủ chỉ đếm khi đang phát, nhỏ dần theo dB, nghe thêm bằng phím/chuột (máy tính) hoặc lắc máy
  (điện thoại); lịch đêm tự hẹn giờ; lưới an toàn: phát liên tục N giờ không ai chạm máy thì tự dừng và ghi nhật ký
  đêm; tự lùi theo độ dài lần dừng (0/10/30 giây); "Quay lại chỗ vừa nghe" sau cú nhảy xa; hỏi khi thiết bị khác đã
  nghe xa hơn; tiến độ cả cuốn; nghe xong một tập thì mời tập kế.
- Chế độ đọc (`/book/:id/read/:chapterId`): đọc cả chương chưa thu âm, nhớ chỗ đọc, "Nghe từ đây" đúng câu.
- Dấu trang kèm câu văn, gộp dấu trùng, hoàn tác khi xoá; phím Space/←/→/Shift/B/M/[ ]/Esc.

Studio (máy tính):
- Trình tạo 4 bước: bước nằm trong URL, nháp giữ khi rời trang, gợi ý thư mục con, ước lượng thời gian đo trên máy
  này, cảnh báo đừng ngắt pha phân tích.
- Hàng đợi sản xuất: cuốn thứ hai xếp hàng, tự chạy khi cuốn kia xong.
- "Cần nghe lại" (`webui/reviews.py`): câu hỏng / chưa kiểm được / tên riêng lệch nhiều, nghe từng câu, bấm Ổn hoặc
  Cần thu lại; phán quyết ở `reviews.json` (không ghi vào SQLite của sách).
- "Xuất MP3 để nghe ở app khác" (`webui/export.py`): chép luồng âm thanh kèm tag ID3 đúng + bìa + `.m3u8`.
- "Xuất M4B cho app sách nói" (`webui/export.export_m4b`, việc nền `POST/GET /api/books/<id>/m4b-job`): giải mã từng chương
  ra PCM đổ liên tục vào một bộ mã hoá AAC (64 kb/s mono, 96 kb/s stereo), đếm mẫu để mốc chương đúng từng mẫu, rồi chép luồng
  sang `.m4b` kèm mục lục chương, bìa và tag như bản MP3. Chỉ chương đã xong.
- Cài đặt: điện thoại (ghép bằng mã 6 số, huỷ mã sau 5 lần sai), hẹn giờ ngủ, lịch đêm, lưới an toàn.

## Máy tính: web trong Qt WebEngine

- Cửa sổ: `abook/desktop.py` - `QWebEngineView` (PySide6 đã có sẵn, **không thêm gói Python**: đổi
  `pyproject.toml`/`uv.lock` là đổi hash chất lượng của dây chuyền giữa cuốn sách). Là cửa sổ mặc định của lối tắt
  (`app.py`; giao diện cũ: `app.py --classic`). Phục vụ bản dựng `webui/static/` - dựng tại máy, không commit.
- File sách `.abook` (`webui/packages.py`): bấm đúp trong Explorer (`register_file_types.ps1` đăng ký lệnh mở:
  `ABook.vbs "<file>"` -> `start_windows.ps1 -OpenFile` -> `app.py "<file>"`) hay nút "Mở file sách". Cuốn giải
  nén vào `<thư viện>/Sách đã nhập/`, `book.json` của gói đã là hình dạng phía nghe. Mở lần hai khi app đang chạy: đường
  dẫn đi qua khoá một phiên bản (`desktop_shell.open_file_message`), cửa sổ báo trang web bằng sự kiện `abook-opened`.
  Chống trùng bằng dấu vân tay audio: file do dự án trong thư viện xuất -> mở dự án ấy; đã nhập -> về cuốn ấy (bản nhiều
  chương hơn thay tại chỗ, giữ mã và dữ liệu nghe).
- Server: `abook/webui/server.py`, stdlib `ThreadingHTTPServer`, chỉ nghe `127.0.0.1`, mọi `/api` và
  `/media` cần mã phiên, `Host` phải là chính server (chặn DNS rebinding).
- Dữ liệu sách: `webui/store.py` chỉ đọc (`mode=ro` + `query_only`), không dùng `_ReadOnlyProjectDB` của CLI vì
  nó chép cả file DB (136 MB/lô) mỗi lần mở.
- Chạy sách: `background_runner` như CLI - đóng cửa sổ không dừng sách.
- GPU của trang bị tắt (`--disable-gpu`): phân tích cần ~6,2 GB trên card 8 GB (xem THROUGHPUT.md, mục Unity).
- Tên chương lấy từ dòng tiêu đề trong văn bản, không từ tên file: nguồn cuốn 2 đánh số file lệch một.
- Đọc theo: mốc từng câu dựng từ `wav_duration + break_ms` (lệch 0,14 s trên 13 phút), co giãn theo độ dài MP3.
- **Studio từ xa** (`webui/remote_studio.py`, 28-09): cổng đồng bộ (`sync.py`, nghe trên LAN) phục vụ luôn bản dựng
  giao diện web và CHUYỂN TIẾP API của nó về máy chủ cục bộ ở trên - không viết lại đường nào, mọi kiểm tra đầu vào
  giữ nguyên. Điện thoại, máy tính bảng, máy tính khác mở `https://<máy>:47630` trong trình duyệt: cả Studio lẫn phần
  Nghe. Ba lớp chặn: thiết bị đã ghép (mã thiết bị; trình duyệt ghép bằng mã 6 số, mã về cookie HttpOnly SameSite=Strict
  qua `/sync/v1/pair-browser`), công tắc `remoteStudio` (tắt mặc định, đọc lại mỗi yêu cầu), và danh sách trắng
  `ALLOWED` - hộp thoại chọn file, mở Explorer, đổi cài đặt, ghép / gỡ thiết bị, điều khiển điện thoại, mở file theo
  đường dẫn không bao giờ đi qua (test `test_every_allowed_route_exists_on_the_computer` giữ danh sách khớp `ROUTES`).
  POST chỉ nhận JSON (trang lạ không gửi được JSON qua CORS). `/api/app` trả `remote: true, dialogs: false` để giao
  diện ẩn nút "Mở thư mục", thanh điện thoại đang phát, cài đặt của máy.
  Soát bảo mật 28-09 (agent đối kháng, 13 phát hiện) thêm: danh sách trắng lọc ĐƯỜNG nhưng tham số thì không - nên máy
  chủ cục bộ nhận biết yêu cầu từ xa (header `X-Abook-Remote` chỉ `forward` gắn) và khi ấy `paths` phải nằm trong
  `<thư viện>/Nguồn tải lên` (từ chối UNC và đường thiết bị trước khi chạm đĩa - Windows tự nối SMB), `target` của xuất
  sách bị bỏ qua; quyền Studio theo TỪNG thiết bị (`devices.json` `studio`, công tắc trên dòng thiết bị; ghép lúc Studio
  từ xa đang bật thì có sẵn); `Host` phải là IP hay tên máy (chống DNS rebinding); lệnh ghi mang cookie phải có
  `Sec-Fetch-Site: same-origin` hay `Origin` trùng `Host`; cookie chỉ được nhận ở đường Studio, không ở `/sync/v1`;
  `Content-Length` âm bị từ chối; tải lên không ghi đè và không nhận tên thiết bị của Windows.
  **TLS ghim vân tay** (`webui/tls.py`): mọi cổng nghe trên LAN - cổng đồng bộ của máy tính và `LibraryServer.kt` của điện
  thoại chia sẻ thư viện - chỉ nói HTTPS với MỘT chứng chỉ tự ký ECDSA P-256 sinh một lần (máy tính: `sync-tls.pem` cạnh
  `preferences.json`, sinh bằng số học thuần Python vì `cryptography` không nằm trong Python nhúng và thêm gói là đổi `uv.lock`;
  điện thoại: khoá trong AndroidKeyStore, `ShareTls.kt`). HTTP thường gửi tới cổng ấy bị cắt ngay lúc bắt tay. Lời đáp
  `/sync/v1/pair` mang `fingerprint` (SHA-256 của chứng chỉ, 64 hex thường); bên ghép nhận chứng chỉ lần đầu, đối chiếu với
  vân tay máy kia tự báo, rồi ghi cùng thiết bị (`computers.json`, Android `sync`/`peers` `fingerprint`). Từ đó mọi kết nối -
  Python `tls.PinnedHTTPSConnection`, Android `Pin.kt` (HttpsURLConnection mặc định, nên cả trình phát Media3 và đường hầm
  Bluetooth) - kiểm vân tay NGAY sau bắt tay, trước khi gửi mã thiết bị; khác là lỗi bảo ghép lại, không bao giờ rơi về HTTP hay
  tự nhận chứng chỉ mới. Trình duyệt (Studio từ xa) không ghim được: báo "không an toàn" một lần, và Cài đặt hiện vân tay để đối
  chiếu; cookie mang `Secure`. Giới hạn: kẻ chen vào đúng 5 phút ghép (người dùng tự bấm "Ghép thiết bị mới") vẫn có thể được ghi
  nhận như máy kia - sau lần ghép đầu thì hết cách chen. Máy chủ giao diện cục bộ `127.0.0.1` (cửa sổ app) vẫn HTTP.

## Android: `mobile/`

Capacitor bọc giao diện Nghe; mọi thứ phải chạy khi tắt màn hình nằm ở native (WebView bị treo lúc đó):

- `Playback.kt` + `PlaybackService.kt` (Media3 1.11.1): cả cuốn là một hàng đợi, lưu vị trí mỗi 5 giây, tự lùi
  khi nghe lại, thông báo + màn hình khoá (lùi 15 / tới 15 / dấu trang / +10 phút khi đang hẹn giờ), nút tai
  nghe, dừng khi rút tai nghe, tiếp tục phát sau khi khởi động lại máy.
- `SleepTimer.kt`: phút hoặc hết chương, nhỏ dần 30 giây, **lắc máy để nghe thêm** (và để phát tiếp trong 2 phút
  sau khi đã tự dừng), rung xác nhận.
- `Bedtime.kt`: nhật ký đêm cho thẻ **"Tối qua bạn nghe tới đâu?"** (`android/MorningRecap.tsx`): lúc hẹn giờ,
  lần cuối chạm/lắc máy, lúc điện thoại bắt đầu nằm yên (cảm biến), lúc tự dừng - mỗi mốc kèm câu văn đang đọc.
- `PlayerWidget.kt`: widget trình phát thu nhỏ (nhỏ: bìa + phát; lớn: chương, tiến độ, lùi/phát/tới, hẹn giờ).
- `LibraryPlugin.kt` + `webui/sync.py`: tìm máy tính bằng UDP broadcast, ghép nối bằng mã 6 số một lần, tải gói
  sách (tải tiếp được), đồng bộ trạng thái nghe hai chiều (mới-hơn-thắng, dấu trang xoá có tombstone).
- `Streaming.kt` (stream play): sách trên máy tính CHƯA tải cũng nằm trong Thư viện điện thoại (nhãn "Máy tính") và dùng
  được đầy đủ - chương, đọc theo, chế độ đọc, nhân vật + câu mẫu, dấu trang, lịch sử, tốc độ, hẹn giờ. Chương nào đã có
  file thì phát file, chưa có thì ExoPlayer phát thẳng `/sync/v1/books/<id>/files/...` (mang mã thiết bị, bộ đệm đĩa
  1 GB, khoá đệm kèm kích thước chương để chương thu lại không phát nhầm bản cũ). Gói sách cất ở `stream.json` (không
  bao giờ bị tính là đã tải); văn bản, dàn nhân vật, câu mẫu, bìa lấy theo nhu cầu và nằm đúng chỗ của sách đã tải, nên
  "Tải về máy" chỉ việc thêm audio + `book.json`. Mất kết nối giữa chừng: báo đúng lý do, bấm phát lại là chuẩn bị lại
  và phát tiếp đúng chỗ. Máy tính không trả lời thì các cuốn ấy tạm ẩn khỏi Thư viện. Điện thoại báo `stream: true`
  nên máy tính mời "Phát trên điện thoại" với MỌI cuốn, không chỉ cuốn đã tải.
- `Remote.kt` + `webui/sync.py: Remote` + `desktop/RemotePhone.tsx`: máy tính điều khiển điện thoại đang phát
  (kiểu Spotify Connect). Điện thoại "hỏi dài" `POST /sync/v1/remote` (trạng thái đang phát + sách đã tải + kết quả
  lệnh, treo tới 25 giây) khi app đang mở, đang phát hoặc vừa dừng dưới 10 phút; đổi trạng thái thì báo thêm một lần
  không chờ. Giao diện máy tính hỏi `GET /api/remote` 1,5 giây/lần và gửi `POST /api/remote/<thiết bị>`
  (`toggle|play|pause|skip|seek|next|previous|jump|rate|load`). Lệnh quá 15 giây chưa giao thì bỏ; điện thoại im quá
  40 giây coi như đã đi. Trình phát máy tính đã đẩy Media Session lên Windows (Windows+A, phím media): Qt WebEngine
  6.11 chuyển nó sang SMTC - đo 27-09.

## Phát triển

```text
# server giao diện trên thư viện sandbox, bộ chạy giả (bấm Bắt đầu không khởi động worker thật)
runtime/.venv/Scripts/python.exe -m abook.webui --dev --port 8765 --library <thư mục> --preferences <file>
# giao diện có hot reload (proxy /api, /media sang 8765)
node ui/node_modules/vite/bin/vite.js ui
# kiểm thử tự động không phát tiếng ra loa: thêm ?mute=1
http://localhost:5173/?mute=1#/

# bản build nhúng vào app máy tính (ra abook/webui/static - không đặt tên dist/, .gitignore bỏ qua nó)
npm --prefix ui run build
# app Android
npm --prefix ui run build:android && cd mobile && npx cap sync android && cd android && gradlew assembleDebug
```

Dev server đồng bộ chỉ nghe `127.0.0.1` khi có `--sync-host 127.0.0.1`: máy ảo Android gọi tới qua `10.0.2.2`
mà Windows không hỏi tường lửa. Chế độ thật (`0.0.0.0`) chỉ mở khi người dùng bật trong Cài đặt.

**Không build Gradle, không chạy máy ảo trong pha phân tích của một lô** (AGENTS.md: đừng chạy việc nặng khi
phân tích). Việc nhẹ - sửa mã, hot reload, xem trong trình duyệt - thì được.
