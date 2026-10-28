"""Capture the complete web-only inventory before UI changes (not just the first 15)."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / '_internal/scripts'))
import ui_parity_qt as p

web, qt = p.web_scan(), p.qt_scan()
qi = sorted(set(qt.items), key=lambda i: (i.file, i.line, i.text))
qb = p.up.group(qi, lambda i: p.up.key_loose(i.text))
wi = sorted(set(web.items), key=lambda i: (i.file, i.line, i.text))
out = {}
for screen in ['Thư viện', 'Đang nghe']:
    texts = [i.text for i in qi if p.qt_screen(i.file) == screen and p.up.short(i.text)]
    missing = {}
    for i in wi:
        if (p.web_in_screen(i, screen) and p.up.short(i.text)
                and p.up.key_loose(i.text) not in qb
                and not ('{}' in i.text and any(p.template_hit(t, [i.text]) for t in texts))):
            missing.setdefault(p.up.key_loose(i.text), dict(label=i.text, file=i.file, line=i.line))
    out[screen] = sorted(missing.values(), key=lambda i: (i['file'], i['line']))
path = root / '_internal/desktop_qt/build/parity-before.json'
path.parent.mkdir(parents=True, exist_ok=True)
if not path.exists():
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf8', newline='\n')
report = root / 'report.md'
if not report.exists():
    lines = ['# Qt parity progress', '', 'PROGRESS: Library audit and implementation first. No commits. GUI offscreen only.', '',
             'Baseline: Thư viện 22 web-only; Đang nghe 45 web-only.',
             'Locked hash before: c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886.', '']
    for screen, entries in out.items():
        lines += ['## ' + screen, '', '| Label | Web source | Status |', '|---|---|---|']
        lines += [f"| {i['label']} | {i['file']}:{i['line']} | PROGRESS: pending audit |" for i in entries]
        lines += ['']
    report.write_text('\n'.join(lines), encoding='utf8', newline='\n')
print(json.dumps(out, ensure_ascii=False, indent=2))
