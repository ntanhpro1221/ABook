"""Dòng tóm tắt của một mục gập không bao giờ chỉ là một con số trơ trọi ("1" dưới "Chương 1": người nghe không biết nó đếm gì - soát điện thoại thật 02-11).

Quét cả web (`summary={`${n}`}`) lẫn native (`summary = "${n}"`): số phải kèm tên đơn vị ("3 đoạn", "2 người").
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "ui" / "src"
NATIVE = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java"

# Chỉ một biểu thức `${...}` (hoặc chuỗi chỉ có số), không chữ nào khác.
BARE = [
    re.compile(r"""summary=\{`\$\{[^}]*\}`\}"""),
    re.compile(r"""summary\s*=\s*"\$\{[^}]*\}\""""),
    re.compile(r"""summary\s*=\s*"\$[A-Za-z_][A-Za-z0-9_.]*\""""),
]


def offenders(files):
    out = []
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(rule.search(line) for rule in BARE):
                out.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()[:140]}")
    return out


def sources():
    web = [p for p in WEB.rglob("*") if p.suffix in (".tsx", ".ts") and "node_modules" not in p.parts]
    native = [p for p in NATIVE.rglob("*.kt")]
    return web + native


def test_no_fold_summary_is_a_bare_number():
    found = offenders(sources())
    assert not found, "Tóm tắt chỉ là con số, thêm đơn vị (vd \"3 đoạn\"):\n" + "\n".join(found)


def test_the_rule_catches_bare_numbers_and_lets_labelled_ones_through(tmp_path):
    bad_web = tmp_path / "a.tsx"
    bad_web.write_text("<Fold summary={`${scenes.length}`} />\n", encoding="utf-8")
    bad_kt = tmp_path / "b.kt"
    bad_kt.write_text('Fold(t, "x", summary = "${scenes.size}") {\n', encoding="utf-8")
    ok = tmp_path / "c.kt"
    ok.write_text('Fold(t, "x", summary = "${scenes.size} đoạn") {\nFold(t, "y", summary = StudioMusicText.sceneCount(2)) {\n', encoding="utf-8")
    ok_web = tmp_path / "d.tsx"
    ok_web.write_text("<Fold summary={`${scenes.length} đoạn`} />\n", encoding="utf-8")

    def count(files):
        return sum(1 for path in files for line in path.read_text(encoding="utf-8").splitlines() if any(r.search(line) for r in BARE))

    assert count([bad_web, bad_kt]) == 2
    assert count([ok, ok_web]) == 0
