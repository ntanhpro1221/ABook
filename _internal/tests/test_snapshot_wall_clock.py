"""Test ảnh Android không được dựng dữ liệu từ giờ thật (clockfix174).

book_history_light đỏ quanh nửa đêm: lượt nghe "cách đây một giờ" lấy từ System.currentTimeMillis rơi sang hôm qua,
nhóm "Hôm nay" thành "Hôm qua". Chữ nói theo ngày/giờ của giao diện đọc giờ qua `ui/data/WallClock.kt`, test ghim nó
bằng `FixedWallClock` (giờ giữa ngày, múi giờ cố định). Máy dò này giữ cả hai đầu:

1. lớp test có `captureRoboImage` không đọc đồng hồ/múi giờ máy (dữ liệu lấy từ `FixedWallClock.nowMs`/`nowSeconds`);
2. mã giao diện (`ui/**`) không đọc thẳng đồng hồ/múi giờ máy ngoài `WallClock.kt` - nếu không, một chữ mới nói theo
   ngày sẽ bỏ qua giờ đã ghim. Chỗ đọc giờ thật có lý do (TTL cache, dấu thứ tự đồng bộ) ghi `// wallclock-ok: <lý do>`.
"""
from __future__ import annotations

from pathlib import Path
import re

ANDROID = Path(__file__).resolve().parents[1] / "mobile/android/app/src"
WALL_CLOCK = re.compile(
    r"System\.currentTimeMillis\(\)|\b(?:Instant|LocalDate|LocalDateTime|LocalTime|ZonedDateTime|OffsetDateTime|Year|YearMonth)\.now\("
    r"|Calendar\.getInstance\(\s*\)|\bGregorianCalendar\(\s*\)|(?<![\w.])Date\(\s*\)|TimeZone\.getDefault\(\)|ZoneId\.systemDefault\(\)"
    r"|Clock\.system(?:DefaultZone|UTC)\(\)|\bDateFormat\.getDateInstance\(|SimpleDateFormat\([^)]*\)\.format\(\s*Date\(\s*\)"
)
OK = re.compile(r"wallclock-ok: \S")


def _code(line: str) -> str:
    """Bỏ chú thích dòng để lời giải thích nhắc System.currentTimeMillis không bị tính."""
    stripped = line.lstrip()
    if stripped.startswith(("//", "*", "/*")):
        return ""
    return line.split("//", 1)[0]


def _hits(path: Path) -> list[str]:
    out = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if WALL_CLOCK.search(_code(line)) and not OK.search(line):
            out.append(f"{path.relative_to(ANDROID).as_posix()}:{number}: {line.strip()}")
    return out


def snapshot_tests() -> list[Path]:
    return sorted(p for p in (ANDROID / "test").rglob("*.kt")
                  if "/ui/snapshot/" not in p.as_posix() and "captureRoboImage(" in p.read_text(encoding="utf-8"))


def test_snapshot_tests_never_read_the_machine_clock():
    tests = snapshot_tests()
    assert len(tests) >= 30, "không thấy các lớp test ảnh - đường dẫn đổi?"
    hits = [hit for path in tests for hit in _hits(path)]
    assert not hits, ("Test ảnh dựng dữ liệu từ giờ thật: ảnh sẽ đổi theo lúc chạy (quanh nửa đêm). Dùng "
                      "`@get:Rule val clock = FixedWallClock()` và `clock.nowSeconds`:\n" + "\n".join(hits))


def test_ui_text_reads_the_time_only_through_wall_clock():
    ui = ANDROID / "main/java/vn/abook/player/ui"
    hits = [hit for path in sorted(ui.rglob("*.kt")) if path.name != "WallClock.kt" for hit in _hits(path)]
    assert not hits, ("Giao diện đọc thẳng đồng hồ/múi giờ máy: FixedWallClock của test ảnh không ghim được chữ này. "
                      "Đọc qua WallClock.nowMs()/WallClock.zone(), hoặc ghi `// wallclock-ok: <lý do>`:\n" + "\n".join(hits))


def test_the_book_history_snapshot_pins_its_clock():
    text = (ANDROID / "test/java/vn/abook/player/ui/BookTabsScreenTest.kt").read_text(encoding="utf-8")
    assert "FixedWallClock()" in text and "clock.nowSeconds" in text


def test_detector_catches_the_old_recipe(tmp_path):
    sample = ANDROID / "test/java/vn/abook/player/ui/_detector_probe.kt"
    probe = tmp_path / "probe.kt"
    probe.write_text("val now = System.currentTimeMillis() / 1000.0\nval d = LocalDate.now()\nval c = Calendar.getInstance()\n"
                     "// System.currentTimeMillis() trong lời giải thích\nval ok = System.currentTimeMillis() // wallclock-ok: lý do\n"
                     "val z = Calendar.getInstance(zone)\n", encoding="utf-8")
    lines = [line for line in probe.read_text(encoding="utf-8").splitlines() if WALL_CLOCK.search(_code(line)) and not OK.search(line)]
    assert len(lines) == 3, lines
    assert not sample.exists()
