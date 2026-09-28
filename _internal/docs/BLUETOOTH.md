# Bluetooth - nghe và đồng bộ khi không chung Wi-Fi

Chủ sách, 27-09: *"stream Bluetooth để sau là vẫn phải làm đấy nhé"* - Bluetooth là việc bắt buộc của mạng trạm, sau các
bước Wi-Fi (điện thoại nghe máy tính, điện thoại phục vụ thư viện, máy tính <-> máy tính, điều khiển hai chiều).

## Ý tưởng: đường hầm, không phải giao thức mới

Mọi thứ giữa các máy đã là HTTP trên cổng đồng bộ (`webui/sync.py`, điện thoại `LibraryServer.kt`). Bluetooth chỉ thêm một
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
| 3 CLOSE | hết dữ liệu theo chiều này (half-close); luồng xong khi cả hai chiều đã CLOSE; bên phục vụ không mở được cổng cục bộ thì trả CLOSE ngay |
| 4 WINDOW | trả tín dụng: 4 byte số byte vừa ghi xuống socket cục bộ |

**Cửa sổ tín dụng 256 KB mỗi luồng, mỗi chiều** (như HTTP/2): gửi trong phần tín dụng, trả tín dụng sau khi đã ghi. Trình
phát ngừng đọc khi bộ đệm đầy thì chỉ luồng của nó đứng - lời gọi đồng bộ bên cạnh vẫn về ngay; bộ nhớ đệm mỗi luồng có trần.
Bên kia gửi quá tín dụng là sai giao thức - đóng luồng.

## Đã kiểm

- `tests/test_bluetooth_tunnel.py` (cặp socket thay RFCOMM): ghép mã + thư viện + gói sách qua cổng đồng bộ thật; 8 yêu cầu
  song song về ngay trong khi một luồng 4 MB nghẽn, rồi luồng ấy nhận đủ từng byte; đóng nửa chiều; đứt đường hầm đóng mọi
  luồng; cổng cục bộ chết thì luồng đóng ngay; bố cục `SOCKADDR_BTH` (30 byte) và GUID đúng ws2bth.h.
- `BtMuxTest.kt` (JVM): cùng các ca ấy cho bản Kotlin, và `speaksTheSameProtocolAsThePythonSide` - Kotlin tải 2 MB qua đầu
  Python thật (`BTMUX_PY_PORT`, chạy tay).
- **Chưa thử trên sóng thật** (28-09 đêm: Bluetooth máy tính đang tắt, cần điện thoại thật): bật Bluetooth máy tính, ghép với
  điện thoại trong Cài đặt Android, mở ABook máy tính (đồng bộ bật) → điện thoại: Tải sách → "Không chung Wi-Fi? Kết nối qua
  Bluetooth" → chọn máy tính → mã 6 số. Kiểm: nghe thẳng một chương, đồng bộ chỗ nghe, điều khiển trình phát, tắt Bluetooth
  giữa chừng rồi bật lại.

## Còn lại

- Điện thoại phục vụ qua Bluetooth (điện thoại <-> điện thoại, máy tính dùng thư viện điện thoại) - cùng BtMux vai phục vụ,
  `listenUsingRfcommWithServiceRecord` nối vào LibraryServer.
- Tự chọn đường: Wi-Fi khi được, Bluetooth khi không (hiện chọn khi ghép).
