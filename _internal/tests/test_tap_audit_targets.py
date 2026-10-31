"""Mọi nhãn mà bài kiểm chạm thật (scripts/tap_audit/scenarios.json) tìm phải còn trong UI.

Đợt "UI parity phase 2" (6eb70b08) đổi nhãn ("Thêm việc với sách" -> "Thêm tuỳ chọn", bỏ dấu "…" cuối nhãn, đổi tiền tố
aria-label của menu chương) mà không sửa scenarios.json: cổng phát hành chạy 9/21. Bài này không mở trình duyệt - chỉ đối chiếu chữ:
mỗi `text` và mỗi selector `[aria-label...]` / `#id` phải khớp một chữ có trong nguồn ui/src (không tính test, gallery, perf) hay trong
dữ liệu giả của fixture. Nó chỉ bắt nhãn đổi tên; nút bị trùng tên hay không bấm được là việc của `scripts/tap_audit/run.py`.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI_SRC = ROOT / "ui" / "src"
TAP_DIR = ROOT / "scripts" / "tap_audit"
SCENARIOS = TAP_DIR / "scenarios.json"
FIXTURE = TAP_DIR / "serve_tap_fixture.py"
SKIP_DIRS = {"gallery", "perf", "node_modules"}
PLACEHOLDER = "\x00"

_COMMENT = re.compile(r"/\*.*?\*/|(?<![:\w\"'`])//[^\n]*", re.S)
_QUOTED = re.compile(r"\"((?:[^\"\\\n]|\\.)*)\"|'((?:[^'\\\n]|\\.)*)'|`((?:[^`\\]|\\.)*)`", re.S)
_JSX_TEXT = re.compile(r">([^<>{}]+)(?=[<{])")
_TEMPLATE_HOLE = re.compile(r"\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def ui_strings(src: Path = UI_SRC) -> set[str]:
    """Mọi chuỗi trong nguồn UI: chữ trong dấu nháy / template (chỗ `${...}` thành PLACEHOLDER) và chữ JSX giữa hai thẻ."""
    found: set[str] = set()
    for path in src.rglob("*"):
        if path.suffix not in {".ts", ".tsx"} or ".test." in path.name or ".spec." in path.name:
            continue
        if SKIP_DIRS & set(path.relative_to(src).parts):
            continue
        code = _COMMENT.sub(" ", path.read_text(encoding="utf-8"))
        for quoted in _QUOTED.finditer(code):
            text = next(group for group in quoted.groups() if group is not None)
            found.add(_squash(_TEMPLATE_HOLE.sub(PLACEHOLDER, text)))
        for jsx in _JSX_TEXT.finditer(code):
            found.add(_squash(jsx.group(1)))
    found.discard("")
    return found


def fixture_strings(path: Path = FIXTURE) -> set[str]:
    """Chữ trong dữ liệu giả của fixture (tên giọng, hồ sơ, sách): chỗ `{...}` của f-string thành PLACEHOLDER."""
    found = set()
    for quoted in _QUOTED.finditer(path.read_text(encoding="utf-8")):
        text = next(group for group in quoted.groups() if group is not None)
        found.add(_squash(re.sub(r"\{[^{}]*\}", PLACEHOLDER, text)))
    found.discard("")
    return found


def _pattern(candidate: str) -> re.Pattern[str] | None:
    """Mẫu của chuỗi có chỗ `${...}`; None khi phần chữ cố định quá ít (kiểu "${a} ${b}") - mẫu ấy khớp mọi thứ nên không có giá trị."""
    parts = candidate.split(PLACEHOLDER)
    if sum(ch.isalpha() for part in parts for ch in part) < 8:
        return None
    return re.compile(".{1,60}".join(re.escape(part) for part in parts), re.S)


def _matches(strings: set[str], text: str, mode: str) -> bool:
    """mode: exact = nhãn bằng đúng `text`; contains = nhãn chứa `text`; prefix = nhãn bắt đầu bằng `text`."""
    for candidate in strings:
        plain = candidate.replace(PLACEHOLDER, "${}")
        if mode == "exact" and candidate == text:
            return True
        if mode == "contains" and (text in candidate or text in plain):
            return True
        if mode == "prefix" and (candidate.startswith(text) or plain.startswith(text)):
            return True
        pattern = _pattern(candidate) if PLACEHOLDER in candidate else None
        if pattern is None:
            continue
        if mode == "exact" and pattern.fullmatch(text):
            return True
        if mode == "contains" and pattern.search(text):
            return True
        if mode == "prefix" and pattern.match(text):
            return True
    return False


_ATTR = re.compile(r"""\[aria-label(\^|\*|\$)?=(?:'([^']*)'|"([^"]*)")\]""")
_ID = re.compile(r"#([A-Za-z][\w-]*)")


def _targets(node):
    """Mọi {text|selector} lồng bất kỳ đâu trong kịch bản (steps, probe, background, touchProbe, reopenSteps, inlineReopen)."""
    if isinstance(node, dict):
        if "text" in node or "selector" in node:
            yield node
        for key, value in node.items():
            if key != "expect":
                yield from _targets(value)
    elif isinstance(node, list):
        for item in node:
            yield from _targets(item)


_MEASURE = re.compile(r"^[\d.,]+\s*(\D+)$")


def _measure_ok(strings: set[str], text: str) -> bool:
    """Giá trị tính ra từ danh sách số ("1,3×", "30 phút"): UI chỉ có đơn vị làm chữ cố định, nên đòi đơn vị còn đó."""
    measure = _MEASURE.match(_squash(text))
    return bool(measure) and any(measure.group(1).strip() in candidate for candidate in strings)


def missing_targets(scenarios: list[dict], strings: set[str]) -> list[str]:
    problems = []
    for scenario in scenarios:
        for target in _targets(scenario):
            where = f"{scenario['name']}: {json.dumps(target, ensure_ascii=False)}"
            text = target.get("text")
            if text and not _matches(strings, _squash(text), "exact" if target.get("exact") else "contains") and not _measure_ok(strings, text):
                problems.append(f"{where} - chữ không có trong ui/src")
            selector = target.get("selector", "")
            for attr in _ATTR.finditer(selector):
                op, value = attr.group(1) or "", attr.group(2) if attr.group(2) is not None else attr.group(3)
                mode = {"^": "prefix", "*": "contains", "$": "contains", "": "exact"}[op]
                if not _matches(strings, value, mode):
                    problems.append(f"{where} - aria-label{op}='{value}' không có trong ui/src")
            for ident in _ID.findall(_ATTR.sub("", selector)):
                if not any(ident in s for s in strings):
                    problems.append(f"{where} - id #{ident} không có trong ui/src")
    return problems


@pytest.fixture(scope="module")
def strings() -> set[str]:
    found = ui_strings()
    assert len(found) > 1000, "đọc nguồn UI không ra gì: sai đường dẫn ui/src?"
    return found | fixture_strings()


def test_scenario_targets_exist_in_ui(strings):
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    problems = missing_targets(scenarios, strings)
    assert not problems, "scenarios.json trỏ vào nhãn không còn trong UI:\n" + "\n".join(problems)


def test_detector_catches_the_renames_of_6eb70b08(strings):
    """Đối chứng âm: đúng các nhãn cũ của scenarios.json trước khi sửa (695eb324) phải bị bắt."""
    stale = [
        {"name": "more", "path": "#/", "steps": [{"text": "Thêm việc với sách", "exact": True}]},
        {"name": "ellipsis", "path": "#/", "steps": [{"text": "Xoá hồ sơ…", "exact": True}, {"text": "Đổi tên…", "exact": True}]},
        {"name": "prefix", "path": "#/", "steps": [{"selector": "button[aria-label^='Tuỳ chọn Ch']"}]},
    ]
    problems = missing_targets(stale, strings)
    assert len(problems) == 4, problems


def test_detector_accepts_current_labels_and_templates(strings):
    current = [
        {"name": "ok", "path": "#/", "steps": [
            {"text": "Thêm tuỳ chọn", "exact": True},
            {"text": "Tuỳ chọn dự án Một Cuốn Nào Đó"},
            {"selector": "button[aria-label^='Thêm tuỳ chọn cho Ch']"},
            {"selector": "section[aria-label='Trình phát'] button", "text": "Thêm tuỳ chọn", "exact": True},
        ]},
    ]
    assert missing_targets(current, strings) == []


def test_detector_against_committed_old_scenarios(strings):
    """Nếu có git: bản scenarios.json ở 695eb324 (trước khi sửa) phải bị bắt - không thì bỏ qua."""
    try:
        old = subprocess.run(
            ["git", "show", "695eb324:_internal/scripts/tap_audit/scenarios.json"],
            cwd=ROOT, capture_output=True, check=True, timeout=30,
        ).stdout.decode("utf-8")
    except (OSError, subprocess.SubprocessError):
        pytest.skip("không có git hay không có commit 695eb324")
    problems = missing_targets(json.loads(old), strings)
    assert problems, "bản scenarios.json cũ lẽ ra phải bị bắt"
