# Bluetooth - nghe và đồng bộ khi không chung Wi-Fi

Chủ sách, 27-09: *"stream Bluetooth để sau là vẫn phải làm đấy nhé"* - Bluetooth là việc bắt buộc của mạng trạm, sau các
bước Wi-Fi (điện thoại nghe máy tính, điện thoại phục vụ thư viện, máy tính <-> máy tính, điều khiển hai chiều).

## Ý tưởng: đường hầm, không phải giao thức mới

Mọi thứ giữa các máy đã là HTTPS (chứng chỉ tự ký, ghim vân tay lúc ghép - `webui/tls.py`) trên cổng đồng bộ (`webui/sync.py`, điện thoại `LibraryServer.kt`); đường hầm chỉ chuyển byte nên TLS đi nguyên vẹn từ máy này tới máy kia. Bluetooth chỉ thêm một
**đường hầm**: MỘT kết nối RFCOMM mang nhiều luồng TCP.

- Điện thoại mở cổng TCP cục bộ `127.0.0.1:47670-47701` (ổn định theo địa chỉ Bluetooth của máy kia - `BluetoothLink.kt`).
  Ghép qua Bluetooth thì máy tính chính có host `bt:<địa chỉ>`; `SyncLink.base()` trả cổng cục bộ ấy. Trình phát nghe
  thẳng, đồng bộ chỗ nghe, điều khiển từ xa, mã 6 số... đi qua đó như qua Wi-Fi.
- Máy tính nghe RFCOMM với UUID dịch vụ `a1f667fe-352a-49b7-9b91-a5463677cac0`, đăng ký SDP (`WSASetServiceW` qua ctypes),
  mỗi luồng nối thẳng vào cổng đồng bộ của chính nó (`webui/bluetooth.py`, `BluetoothServer`). Bật/tắt cùng "Cho phép điện
  thoại kết nối"; Cài đặt ghi trạng thái (đang nghe / Bluetooth tắt / số kết nối).
- RFCOMM chỉ bật khi có kết nối đầu tiên và mở lại khi đứt: `base()` không bao giờ chặn luồng giao diện.
- An toàn: chỉ máy đã ghép Bluetooth ở hệ điều hành mới kết nối được (máy tính đặt `SO_BTH_AUTHENTICATE`, điện thoại dùng
  socket có xác thực), rồi mới tới mã 6 số và mã thiết bị của app như mọi đường khác.

## Khung

```
loại (1 byte) | luồng (4 byte, big-endian) | độ dài (4 byte, big-endian) | dữ liệu (tối đa 16 KB)
```

| loại | nghĩa |
|---|---|
| 1 OPEN | bên kết nối mở luồng mới (số lẻ: điện thoại; số chẵn dành cho bên kia) |
| 2 DATA | dữ liệu của luồng |
| 3 CLOSE | hết dữ liệu theo chiều này (half-close); luồng xong khi cả hai chiều đã CLOSE |
| 4 WINDOW | trả tín dụng: 4 byte không dấu, trong (0, 256 KB] - số byte vừa ghi xuống socket cục bộ; ngoài khoảng ấy là sai giao thức (RESET) |
| 5 RESET | bỏ luồng ngay, cả hai chiều (29-09): ứng dụng cục bộ đóng ngang, bên phục vụ không mở được cổng cục bộ hay từ chối luồng, bên kia gửi quá tín dụng. DATA tới luồng không còn thì đáp RESET; WINDOW/CLOSE/RESET tới luồng không còn là khung trễ, bỏ qua - không bao giờ đáp RESET cho RESET |

**Cửa sổ tín dụng 256 KB mỗi luồng, mỗi chiều** (như HTTP/2): gửi trong phần tín dụng, trả tín dụng sau khi đã ghi. Trình
phát ngừng đọc khi bộ đệm đầy thì chỉ luồng của nó đứng - lời gọi đồng bộ bên cạnh vẫn về ngay; bộ nhớ đệm mỗi luồng có trần.
Bên kia gửi quá tín dụng là sai giao thức - RESET luồng.

**Vì sao cần RESET** (soát đối kháng 29-09): ExoPlayer đóng kết nối mỗi lần tua ra ngoài bộ đệm, đổi chương, dừng. Chỉ có
CLOSE thì bên phục vụ không biết: nó gửi tới hết tín dụng rồi chờ mãi - mỗi lần giữ một luồng, hai luồng đọc, một socket;
64 lần là đường hầm từ chối mọi luồng, và điện thoại phục vụ còn kẹt luồng của LibraryServer (6 luồng: sáu lần tua là
thôi phục vụ cả Wi-Fi). Cùng đợt: socket nối cổng đồng bộ hết hạn giờ 10 giây sau khi nối (hỏi dài 25 giây bị cắt thành
EOF), quay số cổng cục bộ ở luồng riêng (không chặn luồng đọc), máy chủ Bluetooth của máy tính tự mở lại khi bật
Bluetooth / sau khi tắt sóng, không nghe khi không bật được xác thực, điện thoại nghe lại khi Bluetooth bật
(ACTION_STATE_CHANGED), cổng của điện thoại nhớ lần hỏng 10 giây và đóng RFCOMM sau 60 giây không dùng.

## Đã kiểm

- `tests/test_bluetooth_tunnel.py` (cặp socket thay RFCOMM): ghép mã + thư viện + gói sách qua cổng đồng bộ thật; 8 yêu cầu
  song song về ngay trong khi một luồng 4 MB nghẽn, rồi luồng ấy nhận đủ từng byte; đóng nửa chiều; đứt đường hầm đóng mọi
  luồng; cổng cục bộ chết thì luồng đóng ngay; bố cục `SOCKADDR_BTH` (30 byte) và GUID đúng ws2bth.h. 29-09: trả lời
  chậm hơn hạn nối vẫn về đủ; tải bỏ ngang (đóng thường và RST) giải phóng cả hai đầu; DATA tới luồng lạ được đáp RESET,
  RESET thì không; máy chủ tự mở lại khi Bluetooth bật / sau khi tắt sóng; không nghe khi thiếu xác thực.
- `BtMuxTest.kt` (JVM): cùng các ca ấy cho bản Kotlin (cả tải bỏ ngang, RESET, WINDOW âm), và
  `speaksTheSameProtocolAsThePythonSide` - Kotlin tải 4 MB qua đầu Python thật (`BTMUX_PY_PORT`, chạy tay; 29-09 qua với
  bản có RESET).
- **Chưa thử trên sóng thật** (28-09 đêm: Bluetooth máy tính đang tắt, cần điện thoại thật): bật Bluetooth máy tính, ghép với
  điện thoại trong Cài đặt Android, mở ABook máy tính (đồng bộ bật) → điện thoại: Tải sách → "Không chung Wi-Fi? Kết nối qua
  Bluetooth" → chọn máy tính → mã 6 số. Kiểm: nghe thẳng một chương, đồng bộ chỗ nghe, điều khiển trình phát, tắt Bluetooth
  giữa chừng rồi bật lại.

## Điện thoại phục vụ qua Bluetooth (29-09)

Bật "Cho máy khác nghe thư viện này" thì điện thoại nghe RFCOMM cùng UUID (`BluetoothShare`, BluetoothLink.kt) - mỗi máy
kết nối là một BtMux vai phục vụ nối vào LibraryServer. Điện thoại khác ghép nó ở "Thiết bị khác" → "Không chung Wi-Fi?
Ghép qua Bluetooth" (Peers: host `bt:<địa chỉ>`, đi qua BluetoothLink như máy tính chính).

**Đã thử trên HAI MÁY ẢO ghép Bluetooth ảo (netsim của Android Emulator)** - không cần phần cứng: ghép Bluetooth trong Cài
đặt của máy ảo (một máy "cho tìm thấy", máy kia "Ghép thiết bị mới", xác nhận ở cả hai), rồi trong app: A ghép B bằng mã 6
số qua Bluetooth; A đọc thư viện và trình phát của B; A **nghe thẳng** chương 725 của một cuốn chỉ có trên B (15 giây phát
liền, không đứng đệm); A bấm phát/dừng trình phát của B. Bài học: `BluetoothAdapter.cancelDiscovery()` đòi `BLUETOOTH_SCAN`
trên Android 12+ - mình chỉ xin `BLUETOOTH_CONNECT`, nên gọi nó trong `runCatching`.

**Thử lại 29-09 01:3x với bản có RESET** (cùng hai máy ảo, APK mới cài đè, dữ liệu giữ nguyên): A nghe thẳng chương 725
của B qua Bluetooth rồi tua lùi 6 lần liền (mỗi lần tua ra ngoài bộ đệm, ExoPlayer bỏ kết nối đang tải) - đếm luồng
`bt-pump`/`bt-drain` của app bằng `ps -T`: 4 -> 1-2 -> 0 ở CẢ HAI máy, trình phát vẫn chạy (đã đệm tới 137 giây). Bản
cũ giữ lại mỗi lần tua hai luồng ở bên phục vụ. A bấm "Phát tiếp trên <B>" / "Tạm dừng trên <B>": trình phát của B
PAUSED -> PLAYING -> PAUSED (B lúc ấy nghe thẳng một cuốn của A - hai chiều cùng lúc trên một đường RFCOMM).

## Máy tính KẾT NỐI tới điện thoại (08-10, chưa thử trên sóng thật)

Viết xong, kiểm bằng bộ giả (`tests/test_bluetooth_desktop_client.py`, `tests/test_bluetooth_paired_devices.py`); chưa một byte nào
đi qua sóng Bluetooth thật.

- **Tra SDP** (`bluetooth.py`, `find_channel`): `WSALookupServiceBeginW/NextW/End` qua ctypes (`ws2_32`), `lpServiceClassId` =
  UUID ABook, `lpszContext` = `"(AA:BB:CC:DD:EE:FF)"`, cờ `LUP_FLUSHCACHE | LUP_RETURN_ADDR` (như PyBluez); kênh là `port` của
  `SOCKADDR_BTH` trong `RemoteAddr` của `CSADDR_INFO`. Bố cục cấu trúc và đọc kênh tách phần thuần, test với bộ đệm dựng tay.
  Rồi `socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM).connect((địa chỉ, kênh))`, đặt `SO_BTH_AUTHENTICATE` nếu được.
- **Đường hầm** (`Gateway`, dùng lại `Mux` và `LocalPort`): cổng `127.0.0.1:47670 + (hash & 31)`, cùng cách tính `String.hashCode`
  của `BluetoothLink.kt` (đối chiếu số chạy thật bằng JBR); nối RFCOMM lười ở luồng riêng khi có kết nối đầu tiên (hay `warm`),
  mở lại khi đứt, vừa hỏng thì 10 giây sau mới quay số lại, đóng sau 60 giây không luồng. Bên gọi dùng luồng số lẻ, điện thoại
  (`BluetoothShare`) số chẵn.
- **Chọn đường** (`route.py`, bản `Route.kt`; `remote_books._base` / `_connect`): máy có địa chỉ Bluetooth (host `bt:<địa chỉ>`, hay
  trường `bt` trong computers.json do máy kia báo `routes.bluetooth` lúc ghép / mỗi lần liệt kê thư viện, hay do người dùng chọn)
  thì Wi-Fi trước; nối Wi-Fi hỏng (chưa gửi byte nào) thì yêu cầu ấy đi tiếp qua đường hầm, các yêu cầu sau đi thẳng Bluetooth,
  mỗi phút thử lại Wi-Fi ở nền. Gốc đổi sang `127.0.0.1:<cổng đường hầm>` nhưng `PinnedHTTPSConnection` vẫn kiểm vân tay đã ghim
  (test: vân tay sai/trống bị từ chối, máy khác đứng sau đường hầm không nhận được mã thiết bị).
- **Ghép mới qua Bluetooth**: `Computers.pair("bt:AA:BB:...", mã 6 số)` (hay chỉ địa chỉ Bluetooth) - điện thoại phục vụ cùng
  cổng đồng bộ qua RFCOMM nên mã 6 số chạy y như Wi-Fi. Ô nhập địa chỉ ở "Máy tính khác" nhận địa chỉ Bluetooth; chưa có nút
  chọn từ danh sách trong giao diện.
- **Điện thoại không báo được địa chỉ Bluetooth** (Android 8+ trả `02:00:00:00:00:00`): máy tính liệt kê thiết bị đã ghép ở Windows
  (`paired_devices`: `BluetoothFindFirstDevice/NextDevice/Close` trong `bthprops.cpl`, chỉ đọc danh sách, `fIssueInquiry` = 0, bỏ
  tai nghe/loa theo lớp thiết bị). Khi Wi-Fi của một máy ghép Wi-Fi hỏng mà chưa có `bt`, một luồng nền (mỗi máy tối đa hai phút
  một lần) chọn thiết bị trùng tên máy (ưu tiên điện thoại; trùng nhiều cái thì không đoán) và ghi `bt` vào computers.json.
  Chọn tay: `GET /api/computers/bluetooth` (danh sách đã ghép), `POST /api/computers/<mã>/bluetooth {"address": ...}` (rỗng = bỏ).
- **Thử tay khi có sóng thật**: `scripts/bt_desktop_probe.py` (không đối số: liệt kê thiết bị đã ghép; có địa chỉ: tra SDP, mở đường
  hầm, bắt tay TLS, GET `/sync/v1/library` không mã - đáp 401 là đạt).

## Còn lại

- **Thử máy tính <-> điện thoại trên sóng thật**: chạy `bt_desktop_probe.py <địa chỉ>`, rồi ghép bằng `bt:<địa chỉ>` + mã 6 số,
  nghe thẳng một chương, đồng bộ chỗ nghe, điều khiển trình phát, tắt Bluetooth giữa chừng. Điểm chưa chắc vì chưa thử thật: cờ
  truyền cho `WSALookupServiceNextW` (đang dùng cùng cờ với Begin như PyBluez), tên thiết bị Windows lưu có trùng tên điện thoại
  báo qua Wi-Fi không, và Windows có hiện hộp ghép nếu thiết bị chưa ghép khi `SO_BTH_AUTHENTICATE` bật.
- Giao diện "Máy tính khác" (`ui/src/desktop/OtherComputers.tsx`, chữ ở `computerRoutes.ts`) đã có: dòng "Bluetooth · <tên thiết bị>"
  cho máy ghép Bluetooth, menu "Dự phòng qua Bluetooth…" (kèm "Không dùng") cho máy ghép Wi-Fi, và các nút chọn thiết bị đã ghép ngay dưới
  ô ghép. Chưa hiện máy nào đang thật sự đi đường nào lúc này (chỉ hiện đường đã cấu hình).
- Bộ test không bao giờ chạm Bluetooth thật: `tests/conftest.py` `_no_real_bluetooth` (autouse) thay `paired_devices` bằng danh sách rỗng và
  `find_channel` / `connect_rfcomm` bằng lỗi, trừ khi bài đưa bộ giả (`dll=` / `ws2=` / `connect=`).
- ~~Tự chọn đường~~ XONG (4d74b592, `Route.kt`): điện thoại giữ cả địa chỉ Wi-Fi lẫn Bluetooth của máy tính, dò đường Wi-Fi rồi lùi về Bluetooth khi hỏng, máy tính báo lại các đường của nó mỗi lần liệt kê thư viện.
- ~~Máy tính KẾT NỐI tới điện thoại~~ viết xong 08-10 (mục trên), chờ thử sóng thật. Cần Bluetooth máy tính BẬT và một điện thoại thật.
