"""So RAM trước/sau bằng bộ lấy mẫu measure.py, offscreen để không mở cửa sổ hay khay thật; bốn vòng xen kẽ."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import sys

import measure


def fixture_at(target: Path, source=Path("D:/Novels/native_desk_proto/deskqt_fixture_music")) -> Path:
    if not (target / "prefs.json").exists():
        shutil.copytree(source, target, dirs_exist_ok=True)
        prefs = json.loads((target / "prefs.json").read_bytes())
        prefs.update(libraryRoot=str(target / "library"), libraryRootSeen=str(target / "library"))
        (target / "prefs.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
    # Mã sách là HMAC của đường dẫn: bản sao ở thư mục mới cần mã mới, kể cả sổ chỗ nghe đối chứng.
    os.environ["ABOOK_PREFERENCES"] = str(target / "prefs.json")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from abook.webui.library import book_id
    old = json.loads((target / "audio_books.json").read_bytes())
    titles = {"Chuyện Thử Nghe": "a", "Sách Không Mốc": "b", "Giọng Cũ": "c"}
    ids = {}
    for path in (target / "library").rglob("book.json"):
        title = json.loads(path.read_bytes()).get("title")
        if title in titles:
            ids[titles[title]] = book_id(path.parent)
    if set(ids) != {"a", "b", "c"}:
        raise RuntimeError("Thư viện thử thiếu sách")
    for path in (target / "_base").glob("*.json*"):
        content = path.read_text(encoding="utf-8")
        for key, value in old.items():
            content = content.replace(value, ids[key])
        path.write_text(content, encoding="utf-8")
    (target / "audio_books.json").write_text(json.dumps(ids), encoding="utf-8")
    return target


def reset(fixture: Path):
    # Khởi đầu cùng chỗ nghe, cả journal; chỉ thư viện thử riêng của phiên này.
    for name in ("listening.json", "listening.json.journal", "listening-node.json"):
        source = fixture / "_base" / name
        if source.exists():
            shutil.copyfile(source, fixture / name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--setup-only", action="store_true")
    ap.add_argument("--background", action="store_true", help="đo mini 10 giây, ẩn 120 giây và mở rộng, bộ phát MF thật")
    ap.add_argument("--native", action="store_true", help="chỉ kiểm audio: QPA Windows trên desktop riêng, khay bị tắt")
    args = ap.parse_args()
    if args.native and not args.background:
        ap.error("--native cần --background")
    root = Path(__file__).resolve().parent.parent
    fixture = fixture_at(root / ("build/mini-background-fixture" if args.background else "build/mini-fixture"))
    reset(fixture)
    if args.setup_only:
        print(fixture)
        return
    books = json.loads((fixture / "audio_books.json").read_bytes())
    qt = Path("D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64")
    if not (qt / "plugins/platforms/qoffscreen.dll").is_file():
        raise RuntimeError("Thiếu plugin offscreen, không được chạy app")
    local = root / ("build/mini-background-local" if args.background else "build/mini-local")
    env = {"ABOOK_PREFERENCES": str(fixture / "prefs.json"), "ABOOK_HOST_PYTHON": "D:/Novels/ABook/_internal/runtime/.venv/Scripts/pythonw.exe",
           "ABOOK_HOST_APP": str(root.parent), "ABOOK_BENCH_SCENARIO": "player", "ABOOK_BENCH_BOOK": books["a"], "ABOOK_MUTE": "1",
           "LOCALAPPDATA": str(local), "QT_SCALE_FACTOR": "1",
           "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software", "ABOOK_BENCH_HIDDEN_DESKTOP": "1",
           "QT_QPA_FONTDIR": str(root / "fonts"),
           "QT_QPA_PLATFORM_PLUGIN_PATH": str(qt / "plugins/platforms"), "PATH": str(qt / "bin") + os.pathsep + os.environ["PATH"]}
    local.mkdir(exist_ok=True)
    if args.native:
        if not (qt / "plugins/platforms/qwindows.dll").is_file():
            raise RuntimeError("Thiếu plugin Windows, không được chạy app")
        env["QT_QPA_PLATFORM"] = "windows"
        env["QT_QUICK_BACKEND"] = "rhi"
    if args.background:
        env["ABOOK_BENCH_SCENARIO"] = "mini"
        env["ABOOK_AUDIO_TRACE"] = "1"
        got = measure.launch(root / "dist/ABookDesk.exe", env, True, timeout_seconds=190)
        if not got.get("ok"):
            raise RuntimeError(got)
        (root / "build/mini-background.json").write_text(json.dumps(got, indent=2), encoding="utf-8")
        off = got["d"]["epoch_offset_ms"]
        events = {name: t + off for t, name in got["d"]["events"]}
        audio = {}
        for name in events:
            if name.startswith("audio:"):
                _, tag, chapter, position, playing = name.split(":")
                audio[tag] = {"chapter": int(chapter), "position": float(position), "playing": int(playing)}
        print("AUDIO", json.dumps(audio), flush=True)
        for phase in ("mini", "hide"):
            begin, end = events[phase + "_begin"], events[phase + "_end"]
            ram = [m for t, m, _ in got["samples"] if end - 3000 <= t <= end]
            print(phase, "seconds", round((end - begin) / 1000, 2), "RAM", round(statistics.median(ram), 2), flush=True)
        before, after = audio["hide_begin"], audio["hide_end"]
        assert before["chapter"] == after["chapter"] and after["position"] - before["position"] >= 118
        assert all(state["playing"] == 1 for state in audio.values())
        return
    rows = {"base": [], "mini": [], "conditions": "offscreen/software; QueryWorkingSet mỗi 250 ms; không có khay native; không so trực tiếp với Parsec 60 Hz"}
    for i in range(args.rounds):
        for name, exe in [("base", root / "build/mini-base/ABookDesk.exe"), ("mini", root / "dist/ABookDesk.exe")]:
            reset(fixture)
            got = measure.player_run(exe, env, True)
            got["exe_sha256"] = hashlib.sha256(exe.read_bytes()).hexdigest()
            rows[name].append(got)
            print(i + 1, name, {k: round(got[k], 2) for k in ("private_idle_loaded_mb", "private_follow_mb", "private_min_playing_mb", "private_min_settled_mb", "cold_first_frame_ms") if k in got}, flush=True)
            (root / "build/mini-ram.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
            if not got.get("ok"):
                raise RuntimeError(f"{name}: {got}")
    for name in ("base", "mini"):
        values = rows[name]
        print("MEDIAN", name, {k: round(statistics.median(r[k] for r in values if r.get("ok")), 2)
            for k in ("private_idle_loaded_mb", "private_follow_mb", "private_min_settled_mb", "cold_first_frame_ms")}, flush=True)


if __name__ == "__main__":
    main()
