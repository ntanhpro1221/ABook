"""Thử tay: máy tính nói chuyện với điện thoại QUA BLUETOOTH THẬT (chưa thử trên sóng thật khi viết - 08-10).

Chuẩn bị: điện thoại đã ghép Bluetooth với máy tính trong Cài đặt Windows; trên điện thoại mở ABook và bật "Cho máy khác nghe
thư viện này" (BluetoothShare nghe RFCOMM); Bluetooth của máy tính bật.

    runtime/.venv/Scripts/python.exe scripts/bt_desktop_probe.py                # liệt kê thiết bị đã ghép (chỉ đọc)
    runtime/.venv/Scripts/python.exe scripts/bt_desktop_probe.py AA:BB:CC:DD:EE:FF

Với địa chỉ: (1) tra SDP tìm kênh RFCOMM của dịch vụ ABook, (2) mở đường hầm (một kết nối RFCOMM), (3) bắt tay TLS qua đường hầm
và in vân tay chứng chỉ của điện thoại, (4) GET /sync/v1/library KHÔNG kèm mã thiết bị - cổng đồng bộ phải đáp 401 (chứng tỏ
LibraryServer của điện thoại trả lời qua Bluetooth; cổng đồng bộ chưa có /hello). Không ghép, không gửi mã, không ghi gì lên điện thoại.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from abook.webui import bluetooth, tls  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        devices = bluetooth.paired_devices()
        for device in devices:
            print(f"{device['address']}  {device['kind']:8}  {device['name']}")
        print(f"{len(devices)} thiết bị đã ghép (điện thoại / máy tính)" if devices else "Không có thiết bị Bluetooth nào đã ghép")
        return 0
    address = bluetooth.normalize_address(argv[1])
    if not address:
        print(f"Không phải địa chỉ Bluetooth: {argv[1]} (dạng AA:BB:CC:DD:EE:FF)")
        return 2

    print(f"1. Tra SDP dịch vụ ABook trên {address} ...")
    started = time.time()
    try:
        channel = bluetooth.find_channel(address)
    except OSError as error:
        print(f"   KHÔNG THẤY: {error}")
        return 1
    print(f"   kênh RFCOMM {channel} ({time.time() - started:.1f} giây)")

    print("2. Mở đường hầm (kết nối RFCOMM) ...")
    link = bluetooth.gateway(address)
    print(f"   cổng cục bộ 127.0.0.1:{link.port}")
    try:
        print("3. Bắt tay TLS qua đường hầm ...")
        connection = tls.PinnedHTTPSConnection("127.0.0.1", link.port, expected=None, timeout=45)
        try:
            connection.request("GET", "/sync/v1/library")  # không mã thiết bị
            response = connection.getresponse()
            body = response.read()[:200]
            print(f"   vân tay chứng chỉ của điện thoại: {connection.peer_fingerprint}")
            print(f"4. GET /sync/v1/library không mã -> {response.status} {body!r}")
            print("   ĐẠT (401 là đúng: cổng đồng bộ trả lời, đòi mã thiết bị)" if response.status == 401
                  else "   LẠ: cổng đồng bộ không đáp 401")
            return 0 if response.status == 401 else 1
        finally:
            connection.close()
    except OSError as error:
        print(f"   LỖI: {bluetooth.last_error(address) or error}")
        return 1
    finally:
        bluetooth.forget(address)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
