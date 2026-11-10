"""Common build entry: generate copy/tokens, then enforce the raw source gate."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    for script, args in (('scripts/gen_ui_strings.py', []), ('scripts/check_ui_decimals.py', []), ('scripts/gen_native_tokens.py', []),
                         ('desktop_qt/tools/gen_theme.py', []), ('scripts/check_ui_sources.py', []),
                         ('scripts/ui_parity.py', ['--check']), ('scripts/ui_parity_qt.py', ['--check'])):
        subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/script), *args], cwd=ROOT, check=True)
