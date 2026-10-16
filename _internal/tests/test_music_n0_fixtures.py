"""Bộ ví dụ DÙNG CHUNG của nhạc nền theo cảnh đường N0 (điện thoại: SceneMusicTest.kt) phải còn khớp bản Python: sinh lại từ mã hiện tại phải ra đúng các file
trong tests/fixtures/music/n0/. Lệch nghĩa là luật Python đã đổi (hay bộ sinh đổi) mà bản Kotlin chưa theo - chạy lại
`runtime/.venv/Scripts/python.exe scripts/music_n0_fixtures.py`, xem git diff, rồi sửa bản Kotlin cho khớp."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "music" / "n0"


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("music_n0_fixtures", ROOT / "scripts" / "music_n0_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_shared_n0_fixtures_are_what_the_python_path_gives_now(generator):
    built = generator.build()
    on_disk = {path.name: path.read_bytes() for path in FIXTURES.glob("*.json")}
    assert sorted(built) == sorted(on_disk), "danh sách file ví dụ lệch bộ sinh"
    stale = [name for name, raw in built.items() if on_disk[name] != raw]
    assert not stale, f"ví dụ N0 đã cũ so với mã Python: {stale}"


def test_the_fixtures_are_lf_utf8_and_cover_every_branch(generator):
    for path in FIXTURES.glob("*.json"):
        raw = path.read_bytes()
        assert b"\r" not in raw, f"{path.name} có CRLF"
        raw.decode("utf-8")
    coverage = generator.coverage({path.name: path.read_bytes() for path in FIXTURES.glob("*.json")})
    assert set(coverage["reasons"]) >= {"chapter_start", "heading", "separator", "subhead", "time_jump", "length"}
    for branch in ("siblings", "stopAt", "continued", "silenced", "pinned", "pinUnavailable", "noLink", "stepDb"):
        assert coverage[branch] > 0, f"bộ ví dụ không chạm nhánh {branch}"


def test_the_invented_catalog_is_the_whole_grid_and_n0_reads_the_nine_cells_around_the_calm_target(generator):
    catalog = json.loads((FIXTURES / "catalog.json").read_text(encoding="utf-8"))
    cells = catalog["cells"]
    assert sorted(cells) == sorted(f"{v}_{a}" for v in range(5) for a in range(5)), "đường NN-lite hỏi cả các ô khác (đích V / E riêng của từng đoạn)"
    nine = {f"{v}_{a}" for v in (1, 2, 3) for a in (0, 1, 2)}
    assert {link for name in nine for link in (item["link"] for item in cells[name])} >= set(catalog["nearOrder"]), "đường N0 chỉ đọc 9 ô quanh đích êm"
    assert all(item["link"].startswith("https://example.invalid/") for items in cells.values() for item in items)
