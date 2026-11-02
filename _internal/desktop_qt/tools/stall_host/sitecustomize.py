"""Móc gây khựng cho máy chủ của app trong lượt đo audio_sink (chỉ đồ thử, không bao giờ nằm trong bản phát hành).

audio_sink.py đặt thư mục này vào PYTHONPATH của app (máy chủ con thừa hưởng môi trường) cùng biến ABOOK_TEST_VOICE_STALL =
"<cỡ file, byte>:<từ>:<tới>:<giây>". Python nạp sitecustomize lúc khởi động; khi abook.webui.server được nạp, Handler._send_file được
bọc: yêu cầu Range đầu tiên cho file đúng cỡ ấy (chương thử; tên file trong gói không cố định) bắt đầu trong khoảng [từ, tới] (phần của cỡ file) mở một quãng khựng `giây` giây - mọi yêu cầu
như thế trong quãng ấy đứng chờ tới hết quãng rồi mới trả, như mạng mất hẳn giữa chương. Chỉ một lần mỗi tiến trình.

ABOOK_TEST_SLOW_CLIPS = "<số ký tự>:<giây>" (listen_audit.py run --slow-clips): mọi lượt đọc clip mới (không phải chỉ tra bộ đệm) của đoạn từ
<số ký tự> trở lên chờ thêm <giây> giây trước khi đọc - Edge chậm với đoạn dài (soát nghe §20: clip 22,2 s về sau ~10,7 s). Đoạn ngắn đi như thường,
nên phép thử tách đúng câu hỏi "đoạn dài có được xin đủ sớm không" khỏi lúc mở chương.

ABOOK_TEST_FAKE_VOICE = "<trễ, giây>:<giây lấy cho mỗi giây clip>[:<âm lượng>]" (listen_audit.py run --fake-voice): giọng Edge được thay bằng giọng giả không ra mạng -
một tiếng ù MP3 (trình phát chỉ nhận MP3 cho giọng; ffmpeg của imageio_ffmpeg trong venv) dài (số ký tự / FAKE_CHARS_PER_SECOND) giây, về sau trễ + hệ số x độ dài (soát nghe §20: clip 22,2 s về sau ~10,7 s, tức ~0,45 s mỗi giây).
Phép kiểm lực đọc trước không phụ thuộc Edge đang khoẻ hay đang rớt kết nối (01-11 trưa Edge đóng sớm 1005 hầu hết các lượt). Âm lượng 0 = giọng câm:
lượt "chỉ nhạc", mọi chỗ nhạc rơi đều nghe được (giọng đọc đè lên che mất lần nhạc im phụt).
ABOOK_TEST_SLOW_MUSIC = "<KB/s>[/<KB/s sau>@<giây>]:<thư mục bài>" (listen_audit.py run --slow-music): bài nhạc danh mục có trong <thư mục bài> (tên = sha1 của link + .mp3, như
App._music_file - music/files của một lượt trước) được "tải" từ file ấy với tốc độ trần <KB/s> thay vì từ mạng; đáp Range như nguồn thật (206 +
Content-Range). Nguồn nhạc thật lúc nhanh lúc chậm (01-11: incompetech ~11-200 KB/s, NA1 nhạc im phụt 14 lần khi bài đang tải dở) - phép thử hụt đệm
cần tốc độ cố định. "/<KB/s sau>@<giây>": mỗi lượt tải đổi sang tốc độ sau từ giây ấy - nguồn nhanh lúc đầu rồi tụt (bài vào rồi mới hụt).
Bài không có trong thư mục thì đi mạng như thường (ghi một dòng).
ABOOK_TEST_SLOW_MUSIC_TRACE = "<file vết>" (listen_audit.py run --slow-trace): tốc độ không đều mà theo một vết băng thông thật, co giãn cho trung bình
cả vết = <KB/s> của ABOOK_TEST_SLOW_MUSIC. Vết = log HSDPA của Riiser 2013 (datasets.simula.no/hsdpa: mỗi dòng một giây, cột 5 byte, cột 6 ms).
Vết chạy theo đồng hồ của tiến trình (mọi lượt tải cùng thấy mạng lúc ấy), hết thì quay lại đầu - phép thử lề theo dao động tốc độ tải.
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
MUSIC = os.environ.get("ABOOK_TEST_SLOW_MUSIC", "")
TRACE = os.environ.get("ABOOK_TEST_SLOW_MUSIC_TRACE", "")


class _Trace:
    """Byte tải được tính từ lúc tiến trình nạp móc, theo vết từng giây (co cho trung bình = `rate` byte/giây), quay vòng."""

    def __init__(self, path, rate):
        rows = []
        for line in open(path, encoding="utf-8", errors="replace"):
            parts = line.split()
            if len(parts) >= 6:
                rows.append(max(0.0, float(parts[4]) * 1000.0 / max(1.0, float(parts[5]))))
        scale = rate / (sum(rows) / len(rows))
        self.cum = [0.0]
        for r in rows:
            self.cum.append(self.cum[-1] + r * scale)
        self.origin = time.monotonic()

    def bytes_at(self, t):
        period, total = len(self.cum) - 1, self.cum[-1]
        laps, rest = divmod(t - self.origin, period)
        i = int(rest)
        return laps * total + self.cum[i] + (self.cum[i + 1] - self.cum[i]) * (rest - i)

    def time_for(self, target):
        """Thời điểm (đồng hồ monotonic) mà bytes_at đạt `target`."""
        import bisect
        period, total = len(self.cum) - 1, self.cum[-1]
        laps, rest = divmod(target, total)
        i = min(bisect.bisect_left(self.cum, rest), period)
        if i == 0:
            return self.origin + laps * period
        step = self.cum[i] - self.cum[i - 1]
        return self.origin + laps * period + i - 1 + ((rest - self.cum[i - 1]) / step if step > 0 else 1.0)


class _SlowTrack:
    """Câu trả lời giả của urlopen cho một bài: đọc từ file, không quá `rate` byte/giây kể từ lúc mở."""

    def __init__(self, path, rate, start, after=None, trace=None):
        self.file = open(path, "rb")
        self.file.seek(start)
        size = os.path.getsize(path)
        self.status = 206 if start else 200
        self.headers = {"Content-Length": str(size - start)}
        if start:
            self.headers["Content-Range"] = f"bytes {start}-{size - 1}/{size}"
        self.rate, self.sent, self.began = rate, 0, time.monotonic()
        self.after = after  # (giây, byte/giây sau mốc ấy) hay None
        self.trace = trace  # _Trace hay None
        self.base = trace.bytes_at(self.began) if trace else 0.0

    def read(self, n=-1):
        chunk = self.file.read(min(n if n and n > 0 else 1 << 16, 8192))
        self.sent += len(chunk)
        if self.trace:
            wait = self.trace.time_for(self.base + self.sent) - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            return chunk
        due = self.sent / self.rate
        if self.after and due > self.after[0]:
            due = self.after[0] + (self.sent - self.after[0] * self.rate) / self.after[1]
        wait = self.began + due - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        return chunk

    read1 = read

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def _music(server):
    import hashlib
    import re
    import urllib.request
    kbps, folder = MUSIC.split(":", 1)
    after = None
    if "/" in kbps:
        kbps, later = kbps.split("/", 1)
        later, at = later.split("@", 1)
        after = (float(at), float(later) * 1024)
    rate = float(kbps) * 1024
    trace = _Trace(TRACE, rate) if TRACE else None
    original = urllib.request.urlopen

    def urlopen(request, *args, **kwargs):
        url = request.full_url if isinstance(request, urllib.request.Request) else str(request)
        path = os.path.join(folder, hashlib.sha1(url.encode("utf-8")).hexdigest() + ".mp3")
        if not url.endswith(".mp3"):
            return original(request, *args, **kwargs)
        if not os.path.isfile(path):
            sys.stderr.write(f"ABOOK_TEST_SLOW_MUSIC: {url} không có trong {folder}, tải mạng\n")
            return original(request, *args, **kwargs)
        header = request.get_header("Range", "") if isinstance(request, urllib.request.Request) else ""
        match = re.match(r"bytes=(\d+)-", header or "")
        start = int(match.group(1)) if match else 0
        sys.stderr.write(f"ABOOK_TEST_SLOW_MUSIC: {url} từ byte {start}, {kbps} KB/s\n")
        track = _SlowTrack(path, rate, start, after, trace)
        if trace:
            sys.stderr.write(f"ABOOK_TEST_SLOW_MUSIC_TRACE: {os.path.basename(TRACE)} giây {(track.began - trace.origin) % (len(trace.cum) - 1):.0f}, trung bình {kbps} KB/s\n")
        return track

    urllib.request.urlopen = urlopen


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
    latency, per_second, *rest = (float(part) for part in FAKE.split(":"))
    volume = rest[0] if rest else 1.0
    import imageio_ffmpeg
    from abook.readaloud.model import Synthesis

    def synthesize(self, text, native_voice, *, rank=0, sink=None, cancelled=None):
        seconds = max(0.5, len(text) / FAKE_CHARS_PER_SECOND)
        sys.stderr.write(f"ABOOK_TEST_FAKE_VOICE: {len(text)} ký tự, clip {seconds:.1f} s, chờ {latency + per_second * seconds:.1f} s\n")
        time.sleep(latency + per_second * seconds)
        audio = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds:.3f}:sample_rate=24000",
                                "-af", f"volume={volume:g}", "-ac", "1", "-b:a", "48k", "-f", "mp3", "pipe:1"], capture_output=True, check=True,
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
            if MUSIC:
                _music(module)
        spec.loader.exec_module = exec_module
        return spec


if SPEC or SLOW or FAKE or MUSIC:
    sys.meta_path.insert(0, _After())
