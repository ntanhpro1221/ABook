""""Làm trước" (docs/LISTEN_ANYTHING.md mục 3): đọc trước các chương sắp nghe vào bộ đệm clip ở luồng nền, để máy đọc chậm hơn tốc độ nghe
(RTF >= 1, hay sát 1) vẫn nghe được giọng VieNeu không phải chờ giữa các đoạn.

Giao diện gửi chữ của từng đoạn (đúng `textScript.paragraphsOf` - cùng khoá bộ đệm với lúc nghe), máy chủ làm lần lượt bằng chính
`ReadAloud.clip`. Việc nghe luôn đi trước: có clip đang được nghe đọc dở (`ReadAloud.live`) thì việc làm trước đứng chờ. Chỉ nhận chừng đoạn vừa
`share` bộ đệm (clip VieNeu là WAV: 48 kHz ~5,8 MB mỗi phút nghe) để đoạn làm trước không đẩy nhau ra khỏi bộ đệm. Một việc một lúc; gửi việc
mới thì thay việc cũ.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Mapping

from . import supertonic
from .model import VoiceError

# Ký tự lời đọc mỗi giây nghe khi chưa đo được trên chính cuốn / giọng ấy - MỘT cách ước độ dài cho mọi nơi (`listening_seconds`: "Làm trước", hộp
# Xuất sách nói listen_export.py, trình tạo sách nói actions.scan_inputs; trình phát readAloud.ts cùng số). Đo 19-10 trên clip thật (soát a63/a64):
# Supertonic F1 15,1; VieNeu Nano Ái Hân 13,8, Đức Trí 11,4; cả cuốn Edge Hoài My 13,6 kể cả quãng lặng -> ~14.
CHARS_PER_SECOND = 14
SHARE = 0.6
# WAV 16-bit đơn kênh, theo tần số mẫu thật của từng giọng; giọng khác là MP3 ~6 KB/giây
BYTES_PER_SECOND = {"vieneu:turbo/": 96_000, "vieneu:nano/": 48_000, supertonic.PREFIX + ":": 2 * supertonic.SAMPLE_RATE}
OTHER_BYTES_PER_SECOND = 6_000
CACHED_SECONDS = 0.05


def listening_seconds(chars: int, rate: float | None = None) -> float:
    """Giây nghe ước của `chars` ký tự lời đọc: theo tốc độ đo được của giọng trên chính cuốn ấy (`rate` ký tự/giây, từ clip đã đọc) nếu có, không
    thì CHARS_PER_SECOND. Nơi hiện cho người dùng ghi "khoảng"."""
    return chars / (rate if rate and rate > 0 else CHARS_PER_SECOND)


def bytes_per_second(voice: str) -> int:
    return next((rate for prefix, rate in BYTES_PER_SECOND.items() if voice.startswith(prefix)), OTHER_BYTES_PER_SECOND)


def fit(voice: str, chars: list[int], budget: int) -> int:
    """Bao nhiêu phần đầu (đoạn hay chương, mỗi phần có `chars` ký tự) vừa `budget` byte bộ đệm; luôn nhận ít nhất một."""
    used = 0.0
    rate = bytes_per_second(voice)
    count = 0
    for size in (listening_seconds(n) * rate for n in chars):
        if count and used + size > budget:
            break
        count += 1
        used += size
    return count


def accept(voice: str, texts: list[str], budget: int) -> list[str]:
    """Các đoạn đầu tiên (theo thứ tự) vừa `budget` byte bộ đệm; luôn nhận ít nhất một đoạn."""
    return texts[:fit(voice, [len(text) for text in texts], budget)]


def estimate(voice: str, chapter_chars: list[int], budget: int, rtf: float | None) -> dict[str, Any]:
    """Ước trước khi bấm "Làm trước" (cùng hình dạng `PreparePlan` của ui/src/listen/prepareAhead.ts, như PreparePlan.kt trên điện thoại): số chương nhận
    (vừa phần bộ đệm dành cho làm trước), giờ nghe của phần ấy, máy cần bao lâu (None: chưa đo tốc độ giọng này). Chương không có chữ thì bỏ."""
    sizes = [n for n in chapter_chars if n > 0]
    taken = sizes[:fit(voice, sizes, budget)]
    chars = sum(taken)
    return {"chapters": len(taken), "offered": len(sizes), "audioSeconds": round(listening_seconds(chars)),
            "secondsEstimate": round(listening_seconds(chars) * rtf) if rtf and taken else None}


class Prepare:
    """`clip(voice, text, origin, readings, book)`: ReadAloud.clip (đánh dấu là việc nền; `origin`, `readings`, `book`: gốc, cách đọc riêng và mã của cuốn, xem `start`); `live()`: số clip của người đang nghe đang làm; `budget`: byte bộ đệm dành
    cho việc làm trước; `rtf(voice)`: tốc độ đo được của giọng (ước thời gian lúc chưa làm đoạn nào), None nếu chưa đo."""

    def __init__(self, clip: Callable[[str, str, str | None, Mapping[str, str] | None, str | None], Any], live: Callable[[], int], budget: int,
                 rtf: Callable[[str], float | None] = lambda _voice: None) -> None:
        self._clip, self._live, self.budget, self._rtf = clip, live, budget, rtf
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._job: dict[str, Any] = {"state": "idle"}

    def start(self, voice: str, texts: list[str], label: str = "", origin: str | None = None,
              readings: Mapping[str, str] | None = None, book: str | None = None) -> dict[str, Any]:
        """`origin`: gốc của cuốn ("ja" / "ko"), `readings`: cách đọc riêng của cuốn - cùng thứ người nghe sẽ dùng, nên cùng khoá bộ đệm với lúc nghe;
        `book`: mã cuốn, để clip làm ra được tính vào "bản đọc đã làm" của cuốn (ClipBooks)."""
        texts = [text for text in texts if isinstance(text, str) and text.strip()]
        taken = accept(voice, texts, self.budget)
        self.cancel()
        with self._lock:
            self._stop = threading.Event()
            self._job = {"state": "running" if taken else "done", "voice": voice, "label": label, "bookId": book or "", "total": len(taken), "offered": len(texts),
                         "done": 0, "failed": 0, "chars": sum(len(text) for text in taken), "charsDone": 0, "charsTimed": 0, "seconds": 0.0,
                         "audioSeconds": round(sum(len(text) for text in taken) / CHARS_PER_SECOND), "error": "", "started": time.time()}
            if taken:
                self._thread = threading.Thread(target=self._run, args=(voice, taken, self._stop, origin, readings, book), name="readaloud-prepare", daemon=True)
                self._thread.start()
        return self.status()

    def plan(self, voice: str, chapter_chars: list[int]) -> dict[str, Any]:
        """Ước trước khi bấm (xem [estimate]) với phần bộ đệm dành cho làm trước và tốc độ đo được của giọng."""
        return estimate(voice, chapter_chars, self.budget, self._rtf(voice))

    def cancel(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(30)
        with self._lock:
            if self._job.get("state") == "running":
                self._job["state"] = "cancelled"

    def forget(self, book: str | None = None) -> None:
        """Bản đọc đã làm của cuốn `book` (hay của mọi cuốn: `None`) vừa bị xoá: việc làm trước của cuốn ấy dừng và dòng trạng thái của nó mất theo -
        không thì cuốn khác (hay chính cuốn ấy sau khi xoá) vẫn thấy "Đã làm trước ..." về những clip không còn."""
        job = self.status()
        if job.get("state") == "idle" or (book is not None and job.get("bookId") != book):
            return
        self.cancel()
        with self._lock:
            self._job = {"state": "idle"}

    def join(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def status(self) -> dict[str, Any]:
        with self._lock:
            job = dict(self._job)
        if job.get("state") in ("running", "done", "cancelled", "error"):
            left = job["chars"] - job["charsDone"]
            if job["charsTimed"] and job["seconds"]:
                job["secondsLeft"] = round(job["seconds"] / job["charsTimed"] * left)
            else:
                rtf = self._rtf(job["voice"])
                job["secondsLeft"] = round(left / CHARS_PER_SECOND * rtf) if rtf else None
        return job

    def _run(self, voice: str, texts: list[str], stop: threading.Event, origin: str | None, readings: Mapping[str, str] | None,
             book: str | None) -> None:
        for text in texts:
            while self._live() > 0 and not stop.is_set():  # người đang nghe đi trước
                time.sleep(0.2)
            if stop.is_set():
                return
            began = time.perf_counter()
            try:
                self._clip(voice, text, origin, readings, book)
                ok = True
            except VoiceError as error:
                ok = False
                if error.reason not in ("empty",):
                    with self._lock:
                        self._job.update(state="error", error=str(error))
                    return
            except ValueError:
                ok = False
            with self._lock:
                self._job["done"] += 1
                self._job["failed"] += 0 if ok else 1
                self._job["charsDone"] += len(text)
                spent = time.perf_counter() - began
                if spent > CACHED_SECONDS:  # đoạn đã có sẵn trong bộ đệm không nói gì về tốc độ
                    self._job["charsTimed"] += len(text)
                    self._job["seconds"] += spent
        with self._lock:
            if not stop.is_set():
                self._job["state"] = "done"
