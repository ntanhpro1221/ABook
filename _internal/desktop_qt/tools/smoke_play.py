"""Phần "phát thử" của smoke_packaged.py: một cuốn trong Thư viện phát được qua đường âm thanh của bản đóng gói.

Cuốn thử là tests/fixtures/book_edits/written/python_v4.abook với chương 1 thay bằng một mp3 thật (sine 440 Hz do ffmpeg
dựng - mp3 trong fixture chỉ là byte giả) và bỏ nhạc nền (nhạc cũng ra tai, che mất giọng). Nó được giải nén vào
`<thư viện>/Sách đã nhập/` như khi người dùng nhập file. App chạy với ABOOK_SMOKE_EXIT=play: host Ready, Thư viện tải xong
và có sách, rồi Player phát cuốn đầu tiên; mã 0 khi giọng đã phát quá PLAYED_S giây. Bộ trộn ghi ra WAV (ABOOK_AUDIO_SINK,
src/filesinkdevice.h) thay loa, và `heard()` soi file ấy: phải có tiếng, và tiếng trội phải là đúng 440 Hz của chương.

Kiểm âm: `selftest()` (bộ soi im với file lặng / sai tần số / quá ngắn), và smoke_packaged.py chạy thêm một lần với chương
hỏng (byte rác, mã băm khớp) - lần ấy phải KHÔNG qua.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np

INTERNAL = Path(__file__).resolve().parents[2]
FIXTURE = INTERNAL / "tests/fixtures/book_edits/written/python_v4.abook"
CHAPTER = "chapters/00001_645.mp3"
TONE_HZ = 440.0
TONE_S = 6.0
PLAYED_S = 2.0      # main.cpp: giọng phát quá chừng này giây thì mã 0
HEARD_S = 1.5       # tai phải nghe được ít nhất chừng này giây có tiếng
WINDOW_S = 0.02
LOUD_RMS = 0.01     # cửa sổ 20 ms có RMS trên mức này (đỉnh 1,0) là có tiếng
FREQ_TOL_HZ = 5.0


def tone_mp3(seconds: float = TONE_S) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("cần ffmpeg trên PATH để dựng chương thử")
    return subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={TONE_HZ:g}:duration={seconds:g}:sample_rate=22050",
                           "-af", "volume=0.25", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "48k", "-f", "mp3", "-"],
                          capture_output=True, check=True).stdout


def library(root: Path, chapter: bytes) -> Path:
    """Thư viện `root` chứa đúng một cuốn: python_v4 với chương 1 = `chapter`, không nhạc. Trả về `root`."""
    sys.path.insert(0, str(INTERNAL))
    from abook.webui.bookfile import BookFile
    from abook.webui.packages import IMPORTED_FOLDER

    root.mkdir(parents=True, exist_ok=True)
    package = write_package(root.parent / f"{root.name}.abook", chapter)
    BookFile(package).extract(root / IMPORTED_FOLDER)
    package.unlink()
    return root


def write_package(package: Path, chapter: bytes) -> Path:
    """File `package`: python_v4 với chương 1 = `chapter` (mã băm khớp), không nhạc. Chương khác là cuốn khác - máy nhận ra
    một cuốn theo mã băm audio từng chương (fingerprints.identity_prints). Trả về `package`."""
    with zipfile.ZipFile(FIXTURE) as source, zipfile.ZipFile(package, "w") as target:
        for info in source.infolist():
            if info.filename.startswith("music/"):
                continue
            data = source.read(info.filename)
            if info.filename == CHAPTER:
                data = chapter
            elif info.filename == "book.json":
                book = json.loads(data)
                book.pop("music", None)
                files = book["package"]["files"]
                for name in [name for name in files if name.startswith("music/")]:
                    del files[name]
                files[CHAPTER] = {"size": len(chapter), "sha256": hashlib.sha256(chapter).hexdigest()}
                book["chapters"][0]["duration"] = TONE_S
                data = json.dumps(book, ensure_ascii=False).encode("utf-8")
            target.writestr(info, data)
    return package


def read_sink(path: Path) -> np.ndarray:
    """WAV float32 stereo của FileSinkDevice -> mono. Phần đầu 44 byte; app bị giết thì đầu còn ghi 0 byte, nên đọc thẳng phần sau."""
    raw = path.read_bytes()[44:] if path.is_file() else b""
    stereo = np.frombuffer(raw[: len(raw) // 8 * 8], dtype="<f4").reshape(-1, 2)
    return stereo.mean(axis=1) if len(stereo) else np.zeros(0, np.float32)


def heard(mono: np.ndarray, rate: int = 48000) -> tuple[float, float]:
    """(giây có tiếng, tần số trội Hz của phần có tiếng; 0 khi lặng)."""
    window = int(rate * WINDOW_S)
    count = len(mono) // window
    if not count:
        return 0.0, 0.0
    frames = mono[: count * window].reshape(count, window)
    loud = frames[np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1)) > LOUD_RMS]
    if not len(loud):
        return 0.0, 0.0
    signal = loud.reshape(-1)
    spectrum = np.abs(np.fft.rfft(signal * np.hanning(len(signal))))
    return len(loud) * WINDOW_S, float(np.fft.rfftfreq(len(signal), 1 / rate)[int(spectrum.argmax())])


def verdict(mono: np.ndarray, rate: int = 48000) -> str | None:
    """None khi tai nghe đúng chương thử; không thì lý do."""
    seconds, frequency = heard(mono, rate)
    if seconds < HEARD_S:
        return f"tai chỉ nghe {seconds:.2f} s có tiếng (cần {HEARD_S:g} s)"
    if abs(frequency - TONE_HZ) > FREQ_TOL_HZ:
        return f"tiếng trội {frequency:.1f} Hz, không phải {TONE_HZ:g} Hz của chương"
    return None


def selftest() -> list[str]:
    """Bộ soi qua với tiếng đúng, và bắt được file lặng / sai tần số / quá ngắn. Trả về danh sách hỏng (rỗng = ổn)."""
    rate = 48000
    t = np.arange(int(rate * 3)) / rate
    good = (0.2 * np.sin(2 * np.pi * TONE_HZ * t)).astype(np.float32)
    cases = {
        "đúng": (good, True),
        "lặng": (np.zeros_like(good), False),
        "sai tần số": ((0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), False),
        "quá ngắn": (np.concatenate([good[: rate], np.zeros(rate * 2, np.float32)]), False),
        "rất nhỏ": (good * 0.01, False),
    }
    return [name for name, (mono, ok) in cases.items() if (verdict(mono, rate) is None) != ok]


if __name__ == "__main__":
    broken = selftest()
    print("PLAY_SELFTEST " + ("OK" if not broken else "FAIL " + ", ".join(broken)))
    sys.exit(1 if broken else 0)
