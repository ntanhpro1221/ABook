"""Móc gây khựng cho máy chủ của app trong lượt đo audio_sink (chỉ đồ thử, không bao giờ nằm trong bản phát hành).

audio_sink.py đặt thư mục này vào PYTHONPATH của app (máy chủ con thừa hưởng môi trường) cùng biến ABOOK_TEST_VOICE_STALL =
"<cỡ file, byte>:<từ>:<tới>:<giây>". Python nạp sitecustomize lúc khởi động; khi abook.webui.server được nạp, Handler._send_file được
bọc: yêu cầu Range đầu tiên cho file đúng cỡ ấy (chương thử; tên file trong gói không cố định) bắt đầu trong khoảng [từ, tới] (phần của cỡ file) mở một quãng khựng `giây` giây - mọi yêu cầu
như thế trong quãng ấy đứng chờ tới hết quãng rồi mới trả, như mạng mất hẳn giữa chương. Chỉ một lần mỗi tiến trình.

ABOOK_TEST_SLOW_CLIPS = "<số ký tự>:<giây>" (listen_audit.py run --slow-clips): mọi lượt đọc clip mới (không phải chỉ tra bộ đệm) của đoạn từ
<số ký tự> trở lên chờ thêm <giây> giây trước khi đọc - Edge chậm với đoạn dài (soát nghe §20: clip 22,2 s về sau ~10,7 s). Đoạn ngắn đi như thường,
nên phép thử tách đúng câu hỏi "đoạn dài có được xin đủ sớm không" khỏi lúc mở chương.

ABOOK_TEST_FAKE_VOICE = "<trễ, giây>:<giây lấy cho mỗi giây clip>" (listen_audit.py run --fake-voice): giọng Edge được thay bằng giọng giả không ra mạng -
một tiếng ù MP3 (trình phát chỉ nhận MP3 cho giọng; ffmpeg của imageio_ffmpeg trong venv) dài (số ký tự / FAKE_CHARS_PER_SECOND) giây, về sau trễ + hệ số x độ dài (soát nghe §20: clip 22,2 s về sau ~10,7 s, tức ~0,45 s mỗi giây).
Phép kiểm lực đọc trước không phụ thuộc Edge đang khoẻ hay đang rớt kết nối (01-11 trưa Edge đóng sớm 1005 hầu hết các lượt).
Không có biến thì không bọc gì: đường thường không đổi.
"""
import importlib.abc
import importlib.machinery
import os
import subprocess
import sys
import threading
import time

SPEC = os.environ.get("ABOOK_TEST_VOICE_STALL", "")
SLOW = os.environ.get("ABOOK_TEST_SLOW_CLIPS", "")
FAKE = os.environ.get("ABOOK_TEST_FAKE_VOICE", "")
FAKE_CHARS_PER_SECOND = 14


def _slow(server):
    chars, seconds = SLOW.split(":")
    chars, seconds = int(chars), float(seconds)
    service = server.readaloud.ReadAloud
    original = service.clip

    def clip(self, voice_id, text, *args, **kwargs):
        if len(text) >= chars and not kwargs.get("cached_only"):
            sys.stderr.write(f"ABOOK_TEST_SLOW_CLIPS: {len(text)} ký tự, chờ {seconds:g} s\n")
            time.sleep(seconds)
        return original(self, voice_id, text, *args, **kwargs)

    service.clip = clip


def _fake(server):
    latency, per_second = (float(part) for part in FAKE.split(":"))
    import imageio_ffmpeg
    from abook.readaloud.model import Synthesis

    def synthesize(self, text, native_voice, *, rank=0, sink=None, cancelled=None):
        seconds = max(0.5, len(text) / FAKE_CHARS_PER_SECOND)
        sys.stderr.write(f"ABOOK_TEST_FAKE_VOICE: {len(text)} ký tự, clip {seconds:.1f} s, chờ {latency + per_second * seconds:.1f} s\n")
        time.sleep(latency + per_second * seconds)
        audio = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds:.3f}:sample_rate=24000",
                                "-ac", "1", "-b:a", "48k", "-f", "mp3", "pipe:1"], capture_output=True, check=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return Synthesis(audio, [], int(seconds * 1000))

    server.readaloud.EdgeProvider.synthesize = synthesize


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
            if SPEC:
                _patch(module)
            if SLOW:
                _slow(module)
            if FAKE:
                _fake(module)
        spec.loader.exec_module = exec_module
        return spec


if SPEC or SLOW or FAKE:
    sys.meta_path.insert(0, _After())
