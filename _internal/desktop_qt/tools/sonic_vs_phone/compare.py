"""Sonic của app máy tính (Sonic C, đường TimeStretch: float stereo) với Sonic của điện thoại (media3 1.11.1, đường 16-bit
mặc định của DefaultAudioSink), cùng một đoạn nguồn, ở từng tốc độ.

  python -X utf8 tools/sonic_vs_phone/compare.py [nguồn.mp3] [--start 120 --seconds 120]

Cần: gcc (mingw64), JBR của Android Studio, media3-common 1.11.1 + guava trong cache Gradle, android.jar (chỉ để nạp lớp).
Ra build/sonic-vs-phone/compare.json. Số đo: độ dài so với lý thuyết, mức so với nguồn, tương quan dạng sóng hai bản
(cửa sổ 40 ms mỗi giây), phổ trên khung có tiếng sau khi căn, số tiếng tách theo tools/audio_sink.py.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
import audio_sink as a  # noqa: E402

RATE = 48000
OUT = ROOT / "build/sonic-vs-phone"
JBR = Path("C:/Program Files/Android/Android Studio/jbr/bin")
GCC = Path("C:/Program Files/mingw64/bin/gcc.exe")
GRADLE = Path.home() / ".gradle/caches/modules-2/files-2.1"
SDK = Path.home() / "AppData/Local/Android/Sdk/platforms"


def tools():
    OUT.mkdir(parents=True, exist_ok=True)
    exe = OUT / "desk_sonic.exe"
    if not exe.exists():
        sonic = ROOT / "third_party/sonic"
        subprocess.run([str(GCC), "-O2", f"-I{sonic}", str(HERE / "desk_sonic.c"), str(sonic / "sonic.c"), "-o", str(exe), "-lm"], check=True)
    aar = next(GRADLE.glob("androidx.media3/media3-common/1.11.1/*/media3-common-1.11.1.aar"))
    jar = OUT / "media3-common-1.11.1.jar"
    if not jar.exists():
        import zipfile
        jar.write_bytes(zipfile.ZipFile(aar).read("classes.jar"))
    guava = next(GRADLE.glob("com.google.guava/guava/33*/*/guava-33*.jar"))
    android = sorted(SDK.glob("android-*/android.jar"))[-1]
    if not (OUT / "cls/PhoneSonic.class").exists():
        subprocess.run([str(JBR / "javac.exe"), "-nowarn", "-cp", str(jar), "-d", str(OUT / "cls"), str(HERE / "PhoneSonic.java")], check=True)
    return exe, ";".join(str(p) for p in (OUT / "cls", jar, guava, android))


def stft_db(y, n=1024, hop=256):
    frames = np.lib.stride_tricks.sliding_window_view(y, n)[::hop] * np.hanning(n)
    return 20 * np.log10(np.abs(np.fft.rfft(frames, axis=1)) + 1e-6)


def envelope(y, hop=480):
    k = len(y) // hop
    return np.sqrt(np.mean(y[: k * hop].reshape(k, hop) ** 2, axis=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?", default="D:/Novels/Audiobooks/book2/_book/001.mp3")
    ap.add_argument("--start", type=float, default=120)
    ap.add_argument("--seconds", type=float, default=120)
    args = ap.parse_args()
    exe, cp = tools()
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    x = subprocess.run([ffmpeg, "-v", "error", "-ss", str(args.start), "-t", str(args.seconds), "-i", args.source,
                        "-f", "f32le", "-ac", "1", "-ar", str(RATE), "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(x, dtype="<f4").copy()
    (OUT / "in.f32").write_bytes(x.tobytes())
    (OUT / "in.s16").write_bytes((np.clip(x, -1, 1) * 32767).round().astype("<i2").tobytes())
    rows = []
    for speed in (0.75, 1.25, 1.5, 2.0, 2.5, 3.0):
        subprocess.run([str(exe), str(OUT / "in.f32"), str(speed), str(OUT / "desk.f32"), str(RATE)], check=True)
        subprocess.run([str(JBR / "java.exe"), "-cp", cp, "PhoneSonic", str(OUT / "in.s16"), str(speed), str(OUT / "phone.s16"), str(RATE), "1"], check=True)
        d = np.fromfile(OUT / "desk.f32", dtype="<f4")
        p = np.fromfile(OUT / "phone.s16", dtype="<i2").astype(np.float32) / 32768
        want = len(x) / speed
        ed, ep = envelope(d), envelope(p)
        m = min(len(ed), len(ep))
        lag = int(np.argmax(np.correlate(ed[:m] - ed[:m].mean(), ep[:m][200:-200] - ep[:m].mean(), "valid"))) - 200
        cors = []
        for t in range(RATE, min(len(d), len(p)) - RATE, RATE):
            off, score = a.match_offset(p, d, t, t + lag * 480, RATE, win_s=0.04, search_s=0.02)
            if off is not None:
                cors.append(score)
        # Phổ trên khung có tiếng (khung im: nền lượng tử 16-bit của điện thoại kéo trung bình dB), sau khi căn lệch
        pa = p[lag * 480:] if lag >= 0 else np.concatenate((np.zeros(-lag * 480, np.float32), p))
        n = min(len(d), len(pa)) - 2048
        sd, sp = stft_db(d[:n]), stft_db(pa[:n])
        loud = (sd.max(1) > -20) & (sp.max(1) > -20)
        tilt = sd[loud].mean(0) - sp[loud].mean(0)
        band = lambda lo, hi: round(float(tilt[int(lo / 46.875): int(hi / 46.875)].mean()), 2)
        rows.append(dict(speed=speed,
                         desk_len_err_pct=round((len(d) / want - 1) * 100, 3), phone_len_err_pct=round((len(p) / want - 1) * 100, 3),
                         desk_vs_src_db=round(a.rms_db(d) - a.rms_db(x), 2), phone_vs_src_db=round(a.rms_db(p) - a.rms_db(x), 2),
                         lag_ms=lag * 10, waveform_corr_median=round(float(np.median(cors)), 3) if cors else None,
                         waveform_corr_p10=round(float(np.percentile(cors, 10)), 3) if cors else None,
                         lsd_db=round(float(np.sqrt(np.mean((sd[loud] - sp[loud]) ** 2))), 2),
                         band_desk_minus_phone_db={"<300": band(50, 300), "300-3k": band(300, 3000), "3k-8k": band(3000, 8000), ">8k": band(8000, 20000)},
                         clicks_desk=len(a.clicks(d, RATE)), clicks_phone=len(a.clicks(p, RATE))))
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    result = dict(source=args.source, start=args.start, seconds=args.seconds, clicks_source=len(a.clicks(x, RATE)), rows=rows)
    (OUT / "compare.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
