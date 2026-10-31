"""Nghe liền một cuốn chỉ có chữ trên app máy tính như người nghe thật: giọng Edge + nhạc theo cảnh, qua tai ABOOK_AUDIO_SINK.

Kịch bản bench "listen" (qml/BenchScenario.qml) mở chương đầu, phát ở tốc độ 1 và không làm gì nữa tới hết cuốn. Hai lượt:
  A  nhạc bật (mặc định "Theo cảnh (máy tự dựng)")
  B  nhạc tắt (lớp sửa music.playlist = "off"), để biết riêng giọng lặng ở đâu
Luật đạt ghi trước ở Corpus research/music/PLAN_lx.md mục 19.

  python -X utf8 tools/listen_audit.py run <out_dir> <label> --text 001.txt 002.txt ... --music on|off [--exe dist/ABookDesk.exe]
  python -X utf8 tools/listen_audit.py analyze <out_dir>/<A> <out_dir>/<B>
  python -X utf8 tools/listen_audit.py check <out_dir>/<lượt>   thoát 1 nếu lượt không dùng được (lỗi giọng, treo, chạm trần)
  python -X utf8 tools/listen_audit.py selftest                 (build.bat)

WAV và chữ nằm trong <out_dir>, không bao giờ commit.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

from audio_sink import frame_db, parse_marks, read_pairs, read_wav

ROOT = Path(__file__).resolve().parents[1]
INTERNAL = ROOT.parent
PYTHON = "D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe"
QT = Path("D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64")

HOP_S = 0.05            # khung đo mức
VOICE_FLOOR_DB = -45.0  # lượt B: khung trên mức này là giọng
LOW_BELOW_DB = 12.0     # khung "thấp" (chỗ ngắt giữa chữ) = dưới trung vị giọng chừng này
SILENT_DB = -60.0       # dưới mức này là im
PRESENT_WINDOW_S = 5.0  # nhạc có mặt: trong cửa sổ chừng này ...
PRESENT_SHARE = 0.8     # ... ít nhất chừng này khung thấp không im
ARRIVE_FIRST_S = 6.0    # (1) chương đầu
ARRIVE_NEXT_S = 3.0     # (1) các chương sau
DEAD_S = 1.5            # (2) lặng chết giữa chương
DEAD_PER_10MIN = 1
DEAD_MAX_S = 3.0
JOIN_MAX_S = 3.0        # (2) chỗ nối chương
LEVEL_RANGE = (-26.0, -14.0)  # (3) trung vị nhạc so với giọng
LEVEL_PEAK_DB = -10.0   # (3) cửa sổ 3 s
CUT_DB, CUT_S = 20.0, 0.3     # (5)
STALL_S = 10.0          # (0) chờ quá lâu: đang phát mà vị trí đứng yên chừng này (giữa hai đoạn giọng thường dưới 2 s)


# ---------- dựng cuốn thử ----------

class Host:
    """Máy chủ của app chạy riêng để nhập cuốn thử, với đúng môi trường riêng của lượt đo."""

    def __init__(self, env: dict) -> None:
        self.proc = subprocess.Popen([PYTHON, "-m", "abook.webui.host", "--version", "listen"], cwd=INTERNAL, env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        url = urlparse(json.loads(self.proc.stdout.readline())["ready"])
        self.base, self.token = f"http://127.0.0.1:{url.port}", parse_qs(url.query)["t"][0]

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"X-Ebook-Token": self.token, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read() or b"{}")

    def stop(self) -> None:
        try:
            self.proc.stdin.write('{"quit": true}\n')
            self.proc.stdin.flush()
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(15)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def private_env(stage: Path) -> dict:
    """LOCALAPPDATA + USERPROFILE riêng (QStandardPaths theo USERPROFILE, không theo biến LOCALAPPDATA), sở thích riêng."""
    local = stage / "local"
    profile = local / "profile"
    for sub in ("AppData/Local", "AppData/Roaming"):
        (profile / sub).mkdir(parents=True, exist_ok=True)
    return dict(LOCALAPPDATA=str(local), APPDATA=str(profile / "AppData/Roaming"), USERPROFILE=str(profile),
                ABOOK_PREFERENCES=str(stage / "prefs.json"), PYTHONIOENCODING="utf-8")


def prepare(stage: Path, texts: list[Path], music: bool) -> str:
    """Nhập các chương thành một cuốn chỉ có chữ; trả mã sách. Giọng Edge mặc định được đồng ý trước như người dùng đã bấm "Nghe"."""
    (stage / "library").mkdir(parents=True, exist_ok=True)
    (stage / "prefs.json").write_bytes(json.dumps({"libraryRoot": str(stage / "library")}).encode("utf-8"))
    ini = stage / "local" / "ABook" / "desktop_qt.ini"
    ini.parent.mkdir(parents=True, exist_ok=True)
    ini.write_bytes(b'[General]\nabook-readaloud-online-ok="[\\"edge\\"]"\n')
    source = stage / "book.txt"
    source.write_bytes(("\n\n".join(p.read_bytes().decode("utf-8").strip() for p in texts) + "\n").replace("\r\n", "\n").encode("utf-8"))
    host = Host(dict(os.environ, **private_env(stage)))
    try:
        added = host.call("POST", "/api/listen/import", {"path": str(source), "title": "Nghe liền", "separate": True, "splitChapters": True})
        book = added["id"]
        if not music:
            host.call("PUT", f"/api/books/{book}/music", {"playlist": "off"})
        chapters = next((b for b in host.call("GET", "/api/listen/library") if b.get("id") == book), None)
    finally:
        host.stop()
    (stage / "book.json").write_text(json.dumps(dict(id=book, music=music, info=chapters), ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return book


def run(out: Path, label: str, texts: list[Path], music: bool, exe: Path) -> None:
    import measure
    stage = out / label
    if (stage / "bench.json").exists():
        raise SystemExit(f"{stage} đã có kết quả; chọn nhãn khác")
    stage.mkdir(parents=True, exist_ok=True)
    book = prepare(stage, texts, music)
    sink = stage / "sink.wav"
    env = dict(private_env(stage), ABOOK_HOST_PYTHON=PYTHON, ABOOK_HOST_APP=str(INTERNAL), ABOOK_BENCH_SCENARIO="listen",
               ABOOK_BENCH_BOOK=book, ABOOK_AUDIO_SINK=str(sink), ABOOK_SMTC="1", QT_SCALE_FACTOR="1", QT_QPA_PLATFORM="offscreen",
               QT_QUICK_BACKEND="software", ABOOK_BENCH_HIDDEN_DESKTOP="1", QT_QPA_FONTDIR=str(ROOT / "fonts"),
               QT_QPA_PLATFORM_PLUGIN_PATH=str(QT / "plugins/platforms"), PATH=str(QT / "bin") + os.pathsep + os.environ["PATH"])
    got = measure.launch(exe.resolve(), env, True, timeout_seconds=3700, require_ac=False)
    if got.get("app_log"):
        shutil.copyfile(got["app_log"], stage / "app.log")
    (stage / "run.json").write_text(json.dumps(dict(ok=bool(got.get("ok")), why=got.get("why"), exe=str(exe), music=music,
                                                    exit_code=got.get("exit_code"), forced=got.get("forced_termination")), ensure_ascii=False),
                                    encoding="utf-8", newline="\n")
    if not got.get("ok"):
        raise SystemExit(f"app không chạy xong: {got.get('why')}")
    (stage / "bench.json").write_text(json.dumps(got["d"], ensure_ascii=False), encoding="utf-8", newline="\n")


# ---------- soi ----------

def load(stage: Path) -> dict:
    x, rate = read_wav(stage / "sink.wav")
    mono = x.mean(axis=1)
    epoch_ms, clock_rate = (stage / "sink.wav.clock").read_text().split()
    assert int(clock_rate) == rate
    bench = json.loads((stage / "bench.json").read_bytes())
    marks = parse_marks(bench["events"], float(epoch_ms), rate)
    hop = int(HOP_S * rate)
    return dict(rate=rate, hop=hop, db=frame_db(mono, hop), marks=marks, gaps=read_pairs(str(stage / "sink.wav") + ".gaps"),
                done=any(name == "done" for _, name in bench["events"]), timeout=any(name == "timeout" for _, name in bench["events"]),
                problems=run_problems(bench["events"]))


def run_problems(events: list) -> list[dict]:
    """Lượt không dùng được để chấm: Player báo lỗi, đang phát mà đứng yên >= STALL_S, kịch bản tự dừng vì treo, chạm trần, không xong."""
    t0 = events[0][0] if events else 0
    out, names = [], [name for _, name in events]
    for t, name in events:
        at = round((t - t0) / 1000, 1)
        if name.startswith("player_error:"):
            out.append(dict(kind="error", t=at, text=name.split(":", 1)[1].strip()))
        elif name.startswith("listen_stalled:"):
            out.append(dict(kind="stalled_end", t=at))
        elif name == "timeout":
            out.append(dict(kind="timeout", t=at))
    if "done" not in names:
        out.append(dict(kind="unfinished"))
    since = None  # (giờ, vị trí) của nhịp đầu chuỗi đang phát mà vị trí không đổi
    last = None
    for t, name in events:
        if not name.startswith("audio:tick:"):
            continue
        _, position, playing = name[len("audio:tick:"):].rsplit(":", 2)
        here = (t, float(position))
        if playing == "1" and since and here[1] == since[1]:
            last = here
            continue
        if since and last and (last[0] - since[0]) / 1000 >= STALL_S:
            out.append(dict(kind="stall", t=round((since[0] - t0) / 1000, 1), seconds=round((last[0] - since[0]) / 1000, 1), position=since[1]))
        since, last = (here if playing == "1" else None), None
    if since and last and (last[0] - since[0]) / 1000 >= STALL_S:
        out.append(dict(kind="stall", t=round((since[0] - t0) / 1000, 1), seconds=round((last[0] - since[0]) / 1000, 1), position=since[1]))
    return out


def runs_of(mask: np.ndarray) -> list[tuple[int, int]]:
    """[(đầu, cuối)) các đoạn True liên tiếp."""
    z = np.concatenate(([False], mask, [False])).astype(np.int8)
    edges = np.flatnonzero(np.diff(z))
    return list(zip(edges[::2].tolist(), edges[1::2].tolist()))


def chapters(run: dict) -> list[dict]:
    """Mỗi chương: khung bắt đầu (nhịp đầu tiên mang mã chương ấy) và khung cuối (nhịp đang phát cuối cùng).
    Nhịp đầu có thể ghi trước khi sink mở tệp (khung âm) - kẹp về 0, không thì db[âm:] lấy đuôi tệp."""
    hop, out = run["hop"], []
    for m in run["marks"]:
        if m["tag"] != "tick":
            continue
        frame = max(0, m["frame"] // hop)
        if not out or out[-1]["chapter"] != m["chapter"]:
            out.append(dict(chapter=m["chapter"], start=frame, end=frame))
        if m["playing"]:
            out[-1]["end"] = frame
    return out


def first_voice(db: np.ndarray, voice_db: float, at: int) -> int | None:
    hit = np.flatnonzero(db[at:] >= voice_db - LOW_BELOW_DB)
    return at + int(hit[0]) if len(hit) else None


def present(db: np.ndarray, voice_db: float, hop_s: float) -> np.ndarray:
    """Khung i có nhạc khi trong cửa sổ PRESENT_WINDOW_S bắt đầu ở i, ít nhất PRESENT_SHARE khung thấp không im."""
    low = db < voice_db - LOW_BELOW_DB
    heard = low & (db > SILENT_DB)
    w = int(PRESENT_WINDOW_S / hop_s)
    c_low = np.concatenate(([0], np.cumsum(low)))
    c_heard = np.concatenate(([0], np.cumsum(heard)))
    n = len(db)
    end = np.minimum(np.arange(n) + w, n)
    lows = c_low[end] - c_low[:n]
    return (lows >= 10) & ((c_heard[end] - c_heard[:n]) >= PRESENT_SHARE * lows)


def analyze(a_dir: Path, b_dir: Path) -> dict:
    A, B = load(a_dir), load(b_dir)
    hop_s = A["hop"] / A["rate"]
    voice_db = float(np.median(B["db"][B["db"] > VOICE_FLOOR_DB]))
    report = dict(voice_median_db=round(voice_db, 2), A_done=A["done"], B_done=B["done"], A_timeout=A["timeout"], B_timeout=B["timeout"])
    rules = {}

    # (0) lượt dùng được: không lỗi giọng, không treo, chạy xong (I4 31-10: 1 giờ đứng chờ clip vẫn ra "ok")
    rules["0_run"] = dict(A=A["problems"], B=B["problems"], ok=not A["problems"] and not B["problems"])

    # (1) nhạc tới - và đối chứng: lượt B không được "có nhạc"
    pres_a, pres_b = present(A["db"], voice_db, hop_s), present(B["db"], voice_db, hop_s)
    heard_a = (A["db"] < voice_db - LOW_BELOW_DB) & (A["db"] > SILENT_DB)
    arrivals = []
    for i, ch in enumerate(chapters(A)):
        v = first_voice(A["db"], voice_db, ch["start"])
        # cửa sổ đầu tiên có nhạc, rồi khung thấp có tiếng đầu tiên trong cửa sổ ấy = lúc nhạc thật sự tới
        hit = np.flatnonzero(pres_a[v: ch["end"]]) if v is not None else []
        heard = np.flatnonzero(heard_a[v + int(hit[0]):]) if len(hit) else []
        delay = round(float(hit[0] + heard[0]) * hop_s, 2) if len(heard) else None
        limit = ARRIVE_FIRST_S if i == 0 else ARRIVE_NEXT_S
        arrivals.append(dict(chapter=ch["chapter"], first_voice_s=None if v is None else round(v * hop_s, 2), music_after_s=delay,
                             ok=bool(delay is not None and delay <= limit)))
    music_events = [dict(t=round(m["frame"] / A["rate"], 2), chapter=m["chapter"], position=m["position"], credit=m["tag"][len("music:"):])
                    for m in A["marks"] if m["tag"].startswith("music:")]
    rules["1_arrival"] = dict(chapters=arrivals, control_B_present_s=round(float(pres_b.sum()) * hop_s, 1),
                              ok=bool(all(x["ok"] for x in arrivals) and pres_b.sum() == 0))

    # (2) lặng chết ở lượt B, từ tiếng giọng đầu tới tiếng giọng cuối
    bch = chapters(B)
    v0 = first_voice(B["db"], voice_db, bch[0]["start"]) if bch else None
    voiced = np.flatnonzero(B["db"] >= voice_db - LOW_BELOW_DB)
    dead_inside, joins = [], []
    if v0 is not None and len(voiced):
        span = slice(v0, int(voiced[-1]) + 1)
        boundaries = [ch["start"] for ch in bch[1:]]
        for s, e in runs_of(B["db"][span] < SILENT_DB):
            s, e = s + v0, e + v0
            seconds = (e - s) * hop_s
            if any(s - 20 <= b <= e + 20 for b in boundaries):
                joins.append(dict(t=round(s * hop_s, 2), seconds=round(seconds, 2)))
            elif seconds > DEAD_S:
                dead_inside.append(dict(t=round(s * hop_s, 2), seconds=round(seconds, 2)))
        minutes = (int(voiced[-1]) - v0) * hop_s / 60
    else:
        minutes = 0
    rules["2_dead_air"] = dict(listened_min=round(minutes, 1), over_1_5s=dead_inside, joins=joins,
                               ok=bool(minutes > 0) and len(dead_inside) <= DEAD_PER_10MIN * max(1.0, minutes / 10)
                               and all(d["seconds"] <= DEAD_MAX_S for d in dead_inside) and all(j["seconds"] <= JOIN_MAX_S for j in joins))

    # (3) mức nhạc so với giọng, trên khung chỉ nhạc của lượt A khi nhạc đã có mặt
    only = (A["db"] < voice_db - LOW_BELOW_DB) & (A["db"] > SILENT_DB) & pres_a
    rel = A["db"][only] - voice_db
    w3 = int(3 / hop_s)
    peaks = []
    for s, e in runs_of(only):
        if e - s >= w3:
            seg = 10 * np.log10(np.convolve(10 ** (A["db"][s:e] / 10), np.ones(w3) / w3, mode="valid"))
            peaks.append(float(seg.max()) - voice_db)
    median = float(np.median(rel)) if len(rel) else None
    rules["3_level"] = dict(music_only_s=round(float(only.sum()) * hop_s, 1), median_vs_voice_db=None if median is None else round(median, 2),
                            p95_vs_voice_db=None if not len(rel) else round(float(np.percentile(rel, 95)), 2),
                            max_3s_vs_voice_db=None if not peaks else round(max(peaks), 2),
                            ok=bool(median is not None and LEVEL_RANGE[0] <= median <= LEVEL_RANGE[1] and (not peaks or max(peaks) <= LEVEL_PEAK_DB)))

    # (4) lỗ của thiết bị lúc đang phát
    def playing_gaps(run):
        hop, out = run["hop"], []
        ticks = [m for m in run["marks"] if m["tag"] == "tick"]
        for at, frames in run["gaps"]:
            near = min(ticks, key=lambda m: abs(m["frame"] - at), default=None)
            if near and near["playing"]:
                out.append(dict(t=round(at / run["rate"], 3), ms=round(frames * 1000 / run["rate"], 1)))
        return out
    gaps_a, gaps_b = playing_gaps(A), playing_gaps(B)
    rules["4_device_gaps"] = dict(A=gaps_a, B=gaps_b, ok=not gaps_a and not gaps_b)

    # (5) nhạc tắt cụt: sau ít nhất 0,5 s chỉ có nhạc, từ gần mức nhạc thường (không phải đuôi một lần mờ), rơi quá CUT_DB trong < CUT_S
    # (cả lượt; đối chứng trên lượt B)
    full = (median + voice_db - 6) if median is not None else SILENT_DB

    def abrupt(db):
        band = (db < voice_db - LOW_BELOW_DB) & (db > SILENT_DB)
        k, before = int(CUT_S / hop_s), int(0.5 / hop_s)
        steady = np.convolve(band, np.ones(before + 1), mode="full")[: len(db)] >= before + 1  # khung i và `before` khung trước đều chỉ nhạc
        out, i = [], before
        while i < len(db) - k:
            if steady[i] and db[i] >= full and db[i] - db[i + 1: i + k + 1].min() > CUT_DB:
                out.append(dict(t=round(i * hop_s, 2), from_db=round(float(db[i]), 1), to_db=round(float(db[i + 1: i + k + 1].min()), 1)))
                i += int(2 / hop_s)
            else:
                i += 1
        return out
    ach = chapters(A)
    cuts, control = abrupt(A["db"]), abrupt(B["db"])
    boundaries = [ch["start"] * hop_s for ch in ach[1:]]
    for c in cuts:
        c["near_join"] = any(abs(c["t"] - b) <= 10 for b in boundaries)
    rules["5_cut"] = dict(joins=len(ach) - 1, abrupt=cuts, control_B=len(control), ok=not cuts and not control)

    # chỉ báo
    played = []
    for ch in ach:
        played.append(dict(chapter=ch["chapter"], seconds=round((ch["end"] - ch["start"]) * hop_s, 1),
                           music_share=round(float(pres_a[ch["start"]:ch["end"]].mean()), 3) if ch["end"] > ch["start"] else None,
                           tracks=len({e["credit"] for e in music_events if e["chapter"] == ch["chapter"]})))
    first_tick = next((m for m in A["marks"] if m["tag"] == "play"), None)
    report.update(rules=rules, ok=all(r["ok"] for r in rules.values()), chapters=played, music_events=music_events,
                  start_to_voice_s=None if not first_tick or not arrivals or arrivals[0]["first_voice_s"] is None
                  else round(arrivals[0]["first_voice_s"] - first_tick["frame"] / A["rate"], 2))
    out = a_dir.parent / f"report_{a_dir.name}_{b_dir.name}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return report


def selftest() -> int:
    """run_problems trên mốc giả: lượt sạch im; lỗi Player, clip kẹt giữa chương (I3), kẹt từ đầu tới trần (I4) đều bị bắt."""
    def ticks(start_s, positions, playing=1):
        return [[(start_s + i) * 1000.0, f"audio:tick:1:{p:.3f}:{playing}"] for i, p in enumerate(positions)]
    head = [[0.0, "main"]]
    clean = head + ticks(5, [i * 1.0 for i in range(60)]) + ticks(65, [59.0] * 15, 0) + [[80000.0, "listen_finished"], [80000.0, "done"]]
    error = head + ticks(5, [0.0, 1.0, 2.0]) + [[8000.0, "player_error:Giọng đang chọn đang không dùng được."], [8000.0, "listen_failed"],
                                               [8000.0, "done"]]
    middle = head + ticks(5, [float(i) for i in range(70)] + [70.0] * 14) + ticks(89, [70.0] * 15, 0) + [[104000.0, "done"]]
    never = head + ticks(5, [0.0] * 3590) + [[3600300.0, "timeout"]]
    failures = []
    for name, events, want in (("clean", clean, []), ("error", error, ["error"]), ("I3", middle, ["stall"]),
                               ("I4", never, ["timeout", "unfinished", "stall"])):
        got = [p["kind"] for p in run_problems(events)]
        if got != want:
            failures.append(f"{name}: chờ {want}, được {got}")
    print(json.dumps(dict(selftest="listen_audit", failures=failures), ensure_ascii=False))
    return 1 if failures else 0


def main() -> int:
    global INTERNAL
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("out", type=Path); r.add_argument("label")
    r.add_argument("--text", type=Path, nargs="+", required=True); r.add_argument("--music", choices=("on", "off"), required=True)
    r.add_argument("--exe", type=Path, default=ROOT / "dist/ABookDesk.exe")
    r.add_argument("--host-app", type=Path, default=INTERNAL, help="thư mục _internal của máy chủ Python (mặc định: cây của app)")
    a = sub.add_parser("analyze"); a.add_argument("a", type=Path); a.add_argument("b", type=Path)
    c = sub.add_parser("check"); c.add_argument("dir", type=Path)
    sub.add_parser("selftest")
    args = ap.parse_args()
    if args.cmd == "run":
        INTERNAL = args.host_app.resolve()
        run(args.out.resolve(), args.label, args.text, args.music == "on", args.exe)
    elif args.cmd == "check":
        problems = run_problems(json.loads((args.dir / "bench.json").read_bytes())["events"])
        print(json.dumps(dict(run=args.dir.name, ok=not problems, problems=problems), ensure_ascii=False))
        return 1 if problems else 0
    elif args.cmd == "selftest":
        return selftest()
    else:
        print(json.dumps(analyze(args.a.resolve(), args.b.resolve()), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
