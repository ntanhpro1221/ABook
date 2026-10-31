"""Chữ giao diện bản Qt theo luật chữ chung của web và điện thoại (docs/UI_PARITY.md luật 10).

"Không X được" là câu cụt khi đứng một mình ("Không mở được", "Không lưu được"): nói theo cái người nghe thấy, "Chưa X được" +
việc nên làm. Cùng luật, cùng mẫu với `ui/src/shared/copyRules.test.ts` (web) và `CopyRulesTest.kt` (điện thoại). Chú thích và
dòng ghi nhật ký (console / qWarning / qDebug ...) nằm ngoài luật.
"""
import re
from pathlib import Path

QT = Path(__file__).resolve().parent.parent / "desktop_qt"
# Câu sau dấu xuống dòng trong chuỗi ("...\nKhông đọc được") cũng là một câu: `\b` không thấy ranh giới giữa `n` và `K`.
START = r"(?:\b|(?<=\\n))"
RULE = re.compile(rf'"[^"\n]*{START}Không [^"\n]{{1,30}} được\b[^"\n]*"|`[^`\n]*{START}Không [^`\n]{{1,30}} được\b[^`\n]*`')
LOG = re.compile(r"\b(?:console\.\w+|q(?:Warning|Debug|Info|Critical)|qCWarning|qCDebug|Bench::mark)\b")


def cut_copy_offences(name: str, text: str) -> list[str]:
    found = []
    for index, line in enumerate(text.split("\n")):
        t = line.lstrip()
        if t.startswith(("//", "*", "/*")) or LOG.search(line):
            continue
        found += [f"{name}:{index + 1} {m.group(0)}" for m in RULE.finditer(line)]
    return found


def ui_sources():
    for folder, suffixes in ((QT / "qml", {".qml", ".js"}), (QT / "src", {".cpp", ".h"})):
        yield from sorted(p for p in folder.rglob("*") if p.suffix in suffixes)


def test_no_cut_short_khong_duoc_in_qt_copy():
    offences = [hit for path in ui_sources() for hit in cut_copy_offences(path.relative_to(QT).as_posix(), path.read_text(encoding="utf-8"))]
    assert offences == [], "đổi sang 'Chưa … được' (docs/UI_PARITY.md luật 10):\n" + "\n".join(offences)


def test_rule_catches_what_it_promises():
    assert len(cut_copy_offences("x.qml", 'text: "Không mở được sách"')) == 1
    assert len(cut_copy_offences("x.js", "return `Không lưu được ${name}`")) == 1
    assert len(cut_copy_offences("x.cpp", 'QStringLiteral("Không đọc được tệp nhạc mp3.")')) == 1
    assert len(cut_copy_offences("x.qml", r'notice = "Chưa đặt được ảnh bìa\nKhông đọc được file ảnh"')) == 1
    assert cut_copy_offences("x.qml", 'text: "Chưa mở được sách"') == []
    assert cut_copy_offences("x.qml", 'text: "Không có sách nào"') == []
    assert cut_copy_offences("x.qml", '// "Không mở được" là chữ cũ') == []
    assert cut_copy_offences("x.cpp", 'qWarning() << "Không mở được cổng"') == []
