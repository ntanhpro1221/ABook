"""Móc gây khựng cho máy chủ của app trong lượt đo audio_sink (chỉ đồ thử, không bao giờ nằm trong bản phát hành).

audio_sink.py đặt thư mục này vào PYTHONPATH của app (máy chủ con thừa hưởng môi trường) cùng biến ABOOK_TEST_VOICE_STALL =
"<cỡ file, byte>:<từ>:<tới>:<giây>". Python nạp sitecustomize lúc khởi động; khi abook.webui.server được nạp, Handler._send_file được
bọc: yêu cầu Range đầu tiên cho file đúng cỡ ấy (chương thử; tên file trong gói không cố định) bắt đầu trong khoảng [từ, tới] (phần của cỡ file) mở một quãng khựng `giây` giây - mọi yêu cầu
như thế trong quãng ấy đứng chờ tới hết quãng rồi mới trả, như mạng mất hẳn giữa chương. Chỉ một lần mỗi tiến trình.
Không có biến thì không bọc gì: đường thường không đổi.
"""
import importlib.abc
import importlib.machinery
import os
import sys
import threading
import time

SPEC = os.environ.get("ABOOK_TEST_VOICE_STALL", "")


def _patch(server):
    size, lo, hi, seconds = SPEC.split(":")
    size, lo, hi, seconds = int(size), float(lo), float(hi), float(seconds)
    original = server.Handler._send_file
    state = dict(until=None)
    lock = threading.Lock()

    def send_file(self, path, *, cache=False):
        header = self.headers.get("Range") or ""
        if header.startswith("bytes=") and path.stat().st_size == size:
            first = header[len("bytes="):].split("-", 1)[0]
            if first.isdigit() and lo * size <= int(first) <= hi * size:
                with lock:
                    if state["until"] is None:
                        state["until"] = time.monotonic() + seconds
                        sys.stderr.write(f"ABOOK_TEST_VOICE_STALL: {path.name} từ byte {first}, {seconds:g} s\n")
                    until = state["until"]
                wait = until - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
        return original(self, path, cache=cache)

    server.Handler._send_file = send_file


class _After(importlib.abc.MetaPathFinder):
    """Bọc lúc abook.webui.server vừa nạp xong."""

    def find_spec(self, fullname, path, target=None):
        if fullname != "abook.webui.server":
            return None
        sys.meta_path.remove(self)
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec
        run = spec.loader.exec_module

        def exec_module(module):
            run(module)
            _patch(module)
        spec.loader.exec_module = exec_module
        return spec


if SPEC:
    sys.meta_path.insert(0, _After())
