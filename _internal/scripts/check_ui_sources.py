"""Fail builds on handwritten UI copy. Exceptions name an exact file and text."""
from __future__ import annotations
import json
import sys
import tempfile
import subprocess
import re
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ui_parity as web
from scripts import ui_parity_qt as qt

EXCEPTIONS = ROOT / "ui_strings/exceptions.json"


def findings():
    # The parity auditors expand references. This audit deliberately sees raw code.
    original_web, original_qt = web.expand, qt.up.expand
    web.expand = qt.up.expand = lambda source, language: source
    try:
        scans = [web.native_scan(), qt.qt_scan()]
    finally:
        web.expand, qt.up.expand = original_web, original_qt
    found = {(i.file, i.text) for scan in scans for i in scan.items
             if not i.file.endswith(("strings.generated.ts", "UiStrings.js"))}
    for path in web.KT.rglob('*.kt'):
        if path.name in ('LucidePaths.kt','Icons.kt') or 'theme' in path.relative_to(web.KT).parts:
            continue
        source=web.blank_comments(path.read_text(encoding='utf-8'))
        for pos,text in web.literals_in(source):
            callee,named=web.kt_callee_before(source,pos)
            if callee.startswith('animate') or callee in {'AnimatedContent','AnimatedVisibility','updateTransition','rememberInfiniteTransition','Crossfade'}:
                continue
            first_argument=source[:pos].rstrip().endswith('(')
            if ((first_argument and callee in {'BasicText','Caption','MenuRow','ListRow','ActionRow','SwitchRow','DisclosureRow','Label'}) or named in {'contentDescription','label','title','hint','text','placeholder','description','subtitle','caption','message'}) and re.search(r'[^\W\d_]',text):
                found.add((path.relative_to(ROOT).as_posix(),text))
    for path in qt.QML.glob('*.qml'):
        if path.name in qt.QML_SKIP or path.name == 'Theme.qml':
            continue
        tree=qt.parse_qml(web.blank_comments(path.read_text(encoding='utf-8')))
        for obj in qt.walk(tree):
            for name,(expr,line) in obj.props.items():
                if name in qt.TEXT_PROPS:
                    for text in qt.options(expr):
                        visible=html.unescape(re.sub(r'<[^>]*>', '', text))
                        if re.search(r'[^\W\d_]',visible):
                            found.add((path.relative_to(ROOT).as_posix(),text))
    for path in (ROOT/'desktop_qt/src').glob('*'):
        if path.suffix not in ('.cpp','.h') or path.name == 'uistrings.generated.h':
            continue
        source = web.blank_comments(path.read_text(encoding='utf-8'))
        for pos, text in web.literals_in(source):
            if web.HAS_VI.search(text):
                found.add((path.relative_to(ROOT).as_posix(), text))
    with tempfile.TemporaryDirectory(prefix='abook-ui-copy-') as folder:
        output = Path(folder)/'web.json'
        subprocess.run(['node', str(ROOT/'ui/scripts/ui_copy_ast.mjs'), str(output)], cwd=ROOT/'ui', check=True)
        found.update(tuple(row) for row in json.loads(output.read_text(encoding='utf-8')))
    return sorted(found)


def main():
    exceptions = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))
    allowed = {(e['file'], e['text']) for e in exceptions}
    assert all(e.get('reason', '').strip() for e in exceptions), 'Every exception needs a reason'
    bad = [x for x in findings() if x not in allowed]
    for file, text in bad:
        print(f"{file}: hardcoded UI text {text!r}", file=sys.stderr)
    print(f"UI source audit: {len(bad)} hardcoded violations; {len(allowed)} exact exceptions")
    return bool(bad)


if __name__ == '__main__':
    raise SystemExit(main())
